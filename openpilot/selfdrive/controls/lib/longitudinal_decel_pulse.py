"""A short, one-sided acceleration preference inside the MPC trajectory.

No following-time or distance reservoir is added. The soft ceiling leaves
physical acceleration bounds unchanged and releases after one pulse per event.
"""

import math

import numpy as np

PULSE_SECONDS = 1.8
ATTACK_JERK = 1.0
# C4 2026-11-08: the 0000012b drive felt a slight bump 0.25-0.45 s into the pulse.
# The entry slope dips below ATTACK_JERK early and rises above it later, with the
# same total descent by ONSET_SHAPE_SECONDS, so the bump softens without spending
# less braking than the original entry.
ONSET_SHAPE_AMPLITUDE = 0.20
ONSET_SHAPE_SECONDS = 1.6
# C4 2026-11-09: above stop-and-go speeds the pulse reacted to every small lead
# deceleration even with spare distance (0000012c: 4-7 brake/accel switches per
# minute above 60 km/h vs about 1 without the pulse). Small lead decelerations
# (median -0.6 m/s^2 there) are ignored at speed, while real braking still gets the
# early response: the lead deceleration needed to start a pulse rises with speed.
# The minimum extra deceleration is only added when the gap is actually short.
LEAD_DECEL_TRIGGER_LOW = 0.1         # m/s^2 at or below LEAD_DECEL_TRIGGER_LOW_SPEED
LEAD_DECEL_TRIGGER_HIGH = 1.0        # m/s^2 at or above LEAD_DECEL_TRIGGER_HIGH_SPEED
LEAD_DECEL_TRIGGER_LOW_SPEED = 20.0 / 3.6   # m/s
LEAD_DECEL_TRIGGER_HIGH_SPEED = 50.0 / 3.6  # m/s
EXTRA_DECEL_MIN = 0.15
EXTRA_MIN_GAP_SHORTFALL = 1.0       # m below the base distance for the full minimum
RELEASE_JERK = 0.8
CLEAR_RELEASE_JERK = 1.5
EXTRA_DECEL_MAX = 0.6


def smoothstep(value):
  value = min(1.0, max(0.0, value))
  return value * value * (3.0 - 2.0 * value)


def onset_descent(start, duration):
  """Ceiling descent allowed between pulse ages start and start + duration.

  The slope multiplier is 1 - A*sin(2*pi*age/T) for age < T and 1 afterwards. It
  is continuous, never below 1 - A, and integrates to exactly T over [0, T].
  """
  def cumulative(age):
    age = max(0.0, age)
    if age >= ONSET_SHAPE_SECONDS:
      return age
    period = ONSET_SHAPE_SECONDS
    return age + ONSET_SHAPE_AMPLITUDE * period / (2.0 * math.pi) * (math.cos(2.0 * math.pi * age / period) - 1.0)
  return ATTACK_JERK * (cumulative(start + max(0.0, duration)) - cumulative(start))


def lead_decel_trigger(ego_speed):
  """Lead deceleration (positive m/s^2) needed to start a pulse at this speed."""
  blend = smoothstep((ego_speed - LEAD_DECEL_TRIGGER_LOW_SPEED) / (LEAD_DECEL_TRIGGER_HIGH_SPEED - LEAD_DECEL_TRIGGER_LOW_SPEED))
  return LEAD_DECEL_TRIGGER_LOW + (LEAD_DECEL_TRIGGER_HIGH - LEAD_DECEL_TRIGGER_LOW) * blend


def closing_request(distance, relative_speed, ego_speed, ego_accel, lead_speed,
                    lead_accel, base_distance, t_follow, comfort_brake):
  values = (distance, relative_speed, ego_speed, ego_accel, lead_speed,
            lead_accel, base_distance, t_follow, comfort_brake)
  if (not all(map(math.isfinite, values)) or distance <= 0.0 or base_distance <= 0.0
      or ego_speed < 0.0 or lead_speed < 0.0 or t_follow < 0.0 or comfort_brake <= 0.0):
    return 0.0, 0.0
  closing = max(0.0, -relative_speed)
  shortfall = max(0.0, base_distance + closing - distance)
  # The ego's own acceleration toward cruise speed must not create a predicted
  # shortfall by itself: at 72 km/h, +0.33 m/s^2 grows the 1 s base distance by
  # about 3 m. Only braking of the ego is carried into the future target.
  future_ego = max(0.0, ego_speed + min(0.0, ego_accel))
  future_lead = max(0.0, lead_speed + lead_accel)
  future_base = (base_distance + (future_ego**2 - ego_speed**2) / (2.0 * comfort_brake)
                 + t_follow * (future_ego - ego_speed) - (future_lead**2 - lead_speed**2) / 5.0)
  future_distance = distance + relative_speed + 0.5 * (lead_accel - ego_accel)
  shortfall = max(shortfall, future_base - future_distance)
  predicted_closing = max(0.0, -relative_speed + 0.6 * (ego_accel - lead_accel))
  strength = (smoothstep((0.2 - relative_speed) / 0.4)
              * smoothstep((predicted_closing - 0.2) / 0.8)
              * smoothstep(shortfall / max(2.0, 0.25 * base_distance))
              * smoothstep((ego_speed - 2.0) / 3.0)
              * (1.0 - smoothstep((lead_accel - 0.1) / 0.4)))
  return strength, shortfall


class LeadDecelPulse:
  def __init__(self):
    self.reset()

  def reset(self):
    self.track_id = None
    self.phase = 'idle'
    self.elapsed = 0.0
    self.rearm_time = 0.0
    self.ceiling = None
    self.strength = 0.0
    self.shortfall = 0.0

  @property
  def cost_weight(self):
    # Blend in the objective over sixteen planner frames, avoiding a sudden new
    # horizon-wide cost when the braking-event gate first becomes true.
    return smoothstep(self.elapsed / 0.8) if self.phase in ('pulse', 'release') else 0.0

  def acceleration_limits(self, *, enabled, lead, track_frames, dt, ego_speed,
                          measured_accel, planned_accel, base_distance, t_follow,
                          comfort_brake, times, minimum_accel, maximum_accel):
    limits = np.full_like(times, maximum_accel, dtype=float)
    values = (dt, ego_speed, measured_accel, planned_accel, base_distance, t_follow,
              comfort_brake, minimum_accel, maximum_accel)
    if (not enabled or not lead.status or not lead.radar or lead.radarTrackId < 0 or track_frames < 3
        or not all(map(math.isfinite, values)) or not 0.0 < dt <= 0.1
        or ego_speed < 0.0 or minimum_accel > maximum_accel
        or not all(math.isfinite(x) for x in (lead.dRel, lead.vRel, lead.vLead, lead.aLeadK))
        or lead.dRel <= 0.0 or lead.vLead < 0.0):
      self.reset()
      return limits
    if self.track_id != lead.radarTrackId:
      self.reset()
      self.track_id = lead.radarTrackId
    self.strength, self.shortfall = closing_request(
      lead.dRel, lead.vRel, ego_speed, measured_accel, lead.vLead, lead.aLeadK,
      base_distance, t_follow, comfort_brake)
    closing = -lead.vRel
    recovering = lead.aLeadK > -0.05 and (lead.aLeadK > 0.15 or closing < 0.1)
    self.rearm_time = self.rearm_time + dt if recovering else 0.0
    if self.phase == 'done' and self.rearm_time >= 0.5:
      self.phase = 'idle'
    if (self.phase == 'idle' and ego_speed >= 3.0 and lead.aLeadK < -lead_decel_trigger(ego_speed)
        and closing > -0.1 and self.shortfall > 0.0 and self.strength > 0.15):
      self.phase = 'pulse'
      self.elapsed = 0.0
      self.ceiling = planned_accel
    if self.phase == 'pulse':
      self.elapsed += dt
      if (self.elapsed >= PULSE_SECONDS or (closing <= 0.05 and self.elapsed >= 0.3)
          or lead.aLeadK >= 0.05 or self.shortfall <= 0.0):
        self.phase = 'release'
    if self.phase not in ('pulse', 'release'):
      return limits

    # Ask for more than the lead's own deceleration only as far as the gap is
    # actually short now; with spare distance the lead's brief braking is absorbed.
    extra_min = EXTRA_DECEL_MIN * smoothstep((base_distance - lead.dRel) / EXTRA_MIN_GAP_SHORTFALL)
    extra = min(EXTRA_DECEL_MAX, max(extra_min, max(0.0, closing) / 1.5 + 0.03 * max(0.0, self.shortfall)))
    target = max(minimum_accel, lead.aLeadK - extra)
    clear = closing <= 0.1 or self.shortfall <= 0.0 or lead.aLeadK >= 0.05
    release_jerk = CLEAR_RELEASE_JERK if clear else RELEASE_JERK
    if self.phase == 'pulse':
      self.ceiling += np.clip(target - self.ceiling, -onset_descent(self.elapsed - dt, dt), release_jerk * dt)
    else:
      self.ceiling = min(maximum_accel, self.ceiling + release_jerk * dt)
      if self.ceiling >= maximum_accel:
        self.phase = 'done'
        self.ceiling = None
        return limits

    # Do not carry a tighter live ceiling than the current planned acceleration
    # plus the bounded supplement. Future states remain solver-owned.
    self.ceiling = max(minimum_accel, planned_accel - EXTRA_DECEL_MAX, self.ceiling)
    remaining = max(0.0, PULSE_SECONDS - self.elapsed) if self.phase == 'pulse' else 0.0
    speed_weight = smoothstep((ego_speed - 2.0) / 3.0)
    for index, horizon in enumerate(times):
      attack_time = min(horizon, remaining)
      ceiling = self.ceiling + np.clip(target - self.ceiling, -onset_descent(self.elapsed, attack_time),
                                      release_jerk * attack_time)
      ceiling += release_jerk * max(0.0, horizon - remaining)
      ceiling = min(maximum_accel, max(minimum_accel, ceiling))
      limits[index] = maximum_accel + speed_weight * (ceiling - maximum_accel)
    # x0 is fixed; never impose an impossible initial acceleration constraint.
    limits[0] = maximum_accel
    return limits
