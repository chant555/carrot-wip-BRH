"""Gap-aware persistence of a braking lead in the MPC lead prediction (C4).

The MPC extrapolates the lead with a(t) = aLeadK * exp(-tau * t^2 / 2): with
the radar's default tau of 1.5 a lead's deceleration is assumed to fade to 5 %
within two seconds. When the gap is already short, or is being closed quickly,
a lead that starts braking usually keeps braking, so that assumption makes the
plan react late and close in (0000012x drives). When there is spare gap, the
fading assumption is what lets the plan absorb the lead's braking instead of
copying it, which is the comfortable behaviour the driver preferred.

This module lowers tau, continuously, by how little spare gap there is, and
by the same need lowers the MPC's acceleration-change and jerk costs so the plan
acts on that prediction now instead of spreading it over the horizon, and widens
the MPC's existing soft danger zone toward the full desired distance. It adds no
constraint, no separate acceleration request and no latch, so the single MPC
trajectory still owns speed, acceleration and jerk.
"""

import math

from openpilot.selfdrive.controls.radar_constants import LEAD_ACCEL_TAU

LEAD_DECEL_DEADBAND = 0.10   # m/s^2: lead decelerations below this are noise
LEAD_DECEL_FULL = 0.60       # m/s^2 of lead deceleration for full persistence
SPARE_REFERENCE_M = 3.0      # spare gap (after one second of closing) where persistence stops
CLOSING_LOOKAHEAD_S = 1.0    # seconds of current closing counted against the spare gap
MIN_TAU = 0.05               # most persistent lead deceleration: ~90 % left after 2 s
MIN_SPEED = 2.0              # m/s: below this the stopping logic owns the plan
FULL_SPEED = 5.0             # m/s
HIGH_SPEED_START = 50.0 / 3.6  # m/s: above this the need is weakened
HIGH_SPEED_END = 60.0 / 3.6    # m/s
HIGH_SPEED_NEED_SCALE = 0.5    # need scale at and above HIGH_SPEED_END
NEED_ATTACK_S = 0.20         # filter time constants of the anticipation need
NEED_RELEASE_S = 0.80
A_CHANGE_COST_FACTOR_MIN = 0.05  # acceleration-change cost factor at full need
JERK_COST_FACTOR_MIN = 0.15      # jerk cost factor at full need
# Danger-zone widening is kept available but off: with it the ego braked harder
# than the lead again (simulation candidates d1/d3, 2026-11-13).
DANGER_FACTOR_FULL = 0.8         # danger-zone fraction of the desired distance at full need


def smoothstep(value):
  value = min(1.0, max(0.0, value))
  return value * value * (3.0 - 2.0 * value)


def anticipation_need(*, spare, closing, a_lead, v_ego):
  """0 with spare gap or a non-braking lead, 1 with no spare gap and a braking lead."""
  values = (spare, closing, a_lead, v_ego)
  if not all(math.isfinite(value) for value in values):
    return 0.0
  effective_spare = spare - max(0.0, closing) * CLOSING_LOOKAHEAD_S
  gap_need = smoothstep((SPARE_REFERENCE_M - effective_spare) / SPARE_REFERENCE_M)
  braking = smoothstep((-a_lead - LEAD_DECEL_DEADBAND) / (LEAD_DECEL_FULL - LEAD_DECEL_DEADBAND))
  speed = smoothstep((v_ego - MIN_SPEED) / (FULL_SPEED - MIN_SPEED))
  high_speed = 1.0 - (1.0 - HIGH_SPEED_NEED_SCALE) * smoothstep((v_ego - HIGH_SPEED_START) / (HIGH_SPEED_END - HIGH_SPEED_START))
  return gap_need * braking * speed * high_speed


def anticipated_tau(lead_tau, need):
  """Blend the lead's own tau toward MIN_TAU by the anticipation need."""
  base = lead_tau if math.isfinite(lead_tau) and lead_tau > 0.0 else LEAD_ACCEL_TAU
  need = min(1.0, max(0.0, need)) if math.isfinite(need) else 0.0
  return base + (min(base, MIN_TAU) - base) * need


def anticipation_cost_factors(need):
  """MPC (acceleration-change, jerk) cost factors; 1.0 leaves the costs unchanged."""
  need = min(1.0, max(0.0, need)) if math.isfinite(need) else 0.0
  return (1.0 - need * (1.0 - A_CHANGE_COST_FACTOR_MIN), 1.0 - need * (1.0 - JERK_COST_FACTOR_MIN))


def anticipation_danger_factor(base_factor, need):
  """Blend the MPC danger-zone factor toward DANGER_FACTOR_FULL; never below the base."""
  need = min(1.0, max(0.0, need)) if math.isfinite(need) else 0.0
  return base_factor + (max(base_factor, DANGER_FACTOR_FULL) - base_factor) * need


class LeadAnticipationState:
  """Per-lead filtered need; resets when the radar track changes or is lost."""

  def __init__(self):
    self.reset()

  def reset(self):
    self.track_id = None
    self.need = 0.0

  def update(self, *, valid, track_id, spare, closing, a_lead, v_ego, dt):
    if not valid or track_id is None or track_id < 0 or not (0.0 < dt <= 0.2):
      self.reset()
      return 0.0
    if track_id != self.track_id:
      self.reset()
      self.track_id = track_id
    target = anticipation_need(spare=spare, closing=closing, a_lead=a_lead, v_ego=v_ego)
    time_constant = NEED_ATTACK_S if target > self.need else NEED_RELEASE_S
    self.need += (target - self.need) * (1.0 - math.exp(-dt / time_constant))
    return self.need
