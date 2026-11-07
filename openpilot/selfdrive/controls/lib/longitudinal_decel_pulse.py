"""A short, one-sided acceleration preference inside the MPC trajectory.

No following-time or distance reservoir is added. The soft ceiling leaves
physical acceleration bounds unchanged and releases after one pulse per event.
"""

import math

import numpy as np

PULSE_SECONDS = 1.8
ATTACK_JERK = 1.0
RELEASE_JERK = 0.8
CLEAR_RELEASE_JERK = 1.5
EXTRA_DECEL_MAX = 0.6


def smoothstep(value):
  value = min(1.0, max(0.0, value))
  return value * value * (3.0 - 2.0 * value)


def closing_request(distance, relative_speed, ego_speed, ego_accel, lead_speed,
                    lead_accel, base_distance, t_follow, comfort_brake):
  values = (distance, relative_speed, ego_speed, ego_accel, lead_speed,
            lead_accel, base_distance, t_follow, comfort_brake)
  if (not all(map(math.isfinite, values)) or distance <= 0.0 or base_distance <= 0.0
      or ego_speed < 0.0 or lead_speed < 0.0 or t_follow < 0.0 or comfort_brake <= 0.0):
    return 0.0, 0.0
  closing = max(0.0, -relative_speed)
  shortfall = max(0.0, base_distance + closing - distance)
  future_ego = max(0.0, ego_speed + ego_accel)
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
    if (self.phase == 'idle' and ego_speed >= 3.0 and lead.aLeadK < -0.1
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

    extra = min(EXTRA_DECEL_MAX, max(0.15, max(0.0, closing) / 1.5 + 0.03 * max(0.0, self.shortfall)))
    target = max(minimum_accel, lead.aLeadK - extra)
    clear = closing <= 0.1 or self.shortfall <= 0.0 or lead.aLeadK >= 0.05
    release_jerk = CLEAR_RELEASE_JERK if clear else RELEASE_JERK
    if self.phase == 'pulse':
      self.ceiling += np.clip(target - self.ceiling, -ATTACK_JERK * dt, release_jerk * dt)
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
      ceiling = self.ceiling + np.clip(target - self.ceiling, -ATTACK_JERK * attack_time,
                                      release_jerk * attack_time)
      ceiling += release_jerk * max(0.0, horizon - remaining)
      ceiling = min(maximum_accel, max(minimum_accel, ceiling))
      limits[index] = maximum_accel + speed_weight * (ceiling - maximum_accel)
    # x0 is fixed; never impose an impossible initial acceleration constraint.
    limits[0] = maximum_accel
    return limits
