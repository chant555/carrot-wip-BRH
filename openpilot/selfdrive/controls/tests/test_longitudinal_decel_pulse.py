from types import SimpleNamespace

import numpy as np
import pytest

import openpilot.selfdrive.controls.lib.longitudinal_decel_pulse as decel_pulse
from openpilot.selfdrive.controls.lib.longitudinal_decel_pulse import (
  ATTACK_JERK, ONSET_SHAPE_AMPLITUDE, ONSET_SHAPE_SECONDS, LeadDecelPulse, closing_request, onset_descent, PULSE_SECONDS,
)

TIMES = 10.0 * (np.arange(13) / 12.0) ** 2


def inputs(**overrides):
  lead = SimpleNamespace(status=True, radar=True, radarTrackId=48, dRel=15.0, vRel=-0.8, vLead=9.2, aLeadK=-0.4)
  values = {
    'enabled': True,
    'lead': lead,
    'track_frames': 10,
    'dt': 0.05,
    'ego_speed': 10.0,
    'measured_accel': 0.4,
    'planned_accel': 0.4,
    'base_distance': 18.0,
    't_follow': 0.8,
    'comfort_brake': 2.4,
    'times': TIMES,
    'minimum_accel': -3.5,
    'maximum_accel': 1.5,
  }
  values.update(overrides)
  return values


def test_pulse_is_a_short_one_sided_bound_on_one_trajectory():
  state = LeadDecelPulse()
  limits = state.acceleration_limits(**inputs())
  assert state.phase == 'pulse'
  assert np.all(limits <= 1.5) and np.all(limits >= -3.5)
  assert limits[0] == 1.5  # never constrain fixed x0 below its acceleration
  assert limits[-1] == 1.5  # no permanent brake bound in the far horizon
  assert np.min(limits[1:]) < 0.0
  assert np.all(-2.0 <= limits)  # stronger existing braking remains feasible


@pytest.mark.parametrize('override', [{'enabled': False}, {'track_frames': 2}, {'dt': 0.2}, {'measured_accel': float('nan')}])
def test_invalid_or_disabled_inputs_immediately_remove_only_added_bound(override):
  state = LeadDecelPulse()
  state.acceleration_limits(**inputs())
  np.testing.assert_array_equal(state.acceleration_limits(**inputs(**override)), np.full(13, 1.5))
  assert state.phase == 'idle'


@pytest.mark.parametrize('field,value', [('status', False), ('radar', False), ('radarTrackId', -1), ('dRel', float('nan')), ('vRel', float('inf'))])
def test_lost_or_invalid_lead_cannot_retain_bound(field, value):
  state = LeadDecelPulse()
  args = inputs()
  state.acceleration_limits(**args)
  setattr(args['lead'], field, value)
  np.testing.assert_array_equal(state.acceleration_limits(**args), np.full(13, 1.5))
  assert state.phase == 'idle'


def test_track_replacement_does_not_inherit_previous_elapsed_time():
  state = LeadDecelPulse()
  for _ in range(10):
    state.acceleration_limits(**inputs())
  args = inputs()
  args['lead'].radarTrackId = 99
  state.acceleration_limits(**args)
  assert state.elapsed == pytest.approx(0.05)
  assert state.track_id == 99


def test_one_pulse_per_continuous_braking_event():
  state = LeadDecelPulse()
  phases = []
  for _ in range(200):
    state.acceleration_limits(**inputs())
    phases.append(state.phase)
  assert sum(x == 'pulse' for x in phases) <= PULSE_SECONDS / 0.05
  assert phases[-1] == 'done'


def test_100_repeated_braking_events_have_identical_bounds():
  state = LeadDecelPulse()
  cycles = []
  for _ in range(100):
    cycles.append(np.array([state.acceleration_limits(**inputs()) for _ in range(100)]))
    args = inputs()
    args['lead'].vRel = 0.5
    args['lead'].aLeadK = 0.3
    for _ in range(60):
      state.acceleration_limits(**args)
  for cycle in cycles[1:]:
    np.testing.assert_array_equal(cycle, cycles[0])


def test_low_speed_request_is_inactive_and_limits_are_unmodified():
  state = LeadDecelPulse()
  np.testing.assert_array_equal(state.acceleration_limits(**inputs(ego_speed=1.0)), np.full(13, 1.5))


def test_opening_or_distant_lead_does_not_trigger_initial_braking():
  for field, value in [('dRel', 60.0), ('vRel', 0.5), ('aLeadK', 0.8)]:
    args = inputs()
    setattr(args['lead'], field, value)
    state = LeadDecelPulse()
    np.testing.assert_array_equal(state.acceleration_limits(**args), np.full(13, 1.5))


def test_forecast_does_not_mutate_gap_or_following_time():
  args = inputs()
  state = LeadDecelPulse()
  before = (args['lead'].dRel, args['base_distance'], args['t_follow'])
  for _ in range(100):
    state.acceleration_limits(**args)
  assert (args['lead'].dRel, args['base_distance'], args['t_follow']) == before


def test_bad_forecast_parameters_do_not_generate_a_request():
  assert closing_request(15.0, -0.5, 10.0, 0.0, 9.5, -0.4, 18.0, 0.8, 0.0) == (0.0, 0.0)


def test_soft_pulse_leaves_physical_bounds_obstacles_and_following_time_intact():
  from pathlib import Path
  from openpilot.selfdrive.controls.tests.test_longitudinal_gap_recovery import load_mpc_update, run_update

  cls = load_mpc_update(Path(__file__).resolve().parents[1] / 'lib/longitudinal_mpc_lib/long_mpc.py')
  args = {'distance': 12.0, 'speed': 10.0, 'lead_speed': 9.2, 'lead_accel': -0.4, 'ego_accel': 0.4}
  off = run_update(cls, **args)
  on = run_update(cls, **args, decel_enabled=True)
  np.testing.assert_array_equal(on.params[:, :8], off.params[:, :8])
  np.testing.assert_array_equal(on.yref, off.yref)
  assert on.t_follow == off.t_follow
  for i in range(12):
    np.testing.assert_array_equal(on.solver.weights[i, 'Zl'][:4], [1e6, 1e6, 1e6, 100.0])
    assert on.solver.weights[i, 'Zl'][4] > 0.0
    assert off.solver.weights[i, 'Zl'][4] == 0.0
  assert min(on.params[:, 8]) < min(on.params[:, 1])


@pytest.mark.parametrize('overrides', [{'reset': True}, {'lane_change': True}, {'mode': 'blended'}, {'status': False}, {'radar': False}, {'frames': 2}])
def test_mpc_excludes_reset_lane_change_blended_and_untrusted_lead(overrides):
  from pathlib import Path
  from openpilot.selfdrive.controls.tests.test_longitudinal_gap_recovery import load_mpc_update, run_update

  cls = load_mpc_update(Path(__file__).resolve().parents[1] / 'lib/longitudinal_mpc_lib/long_mpc.py')
  mpc = run_update(cls, distance=12.0, speed=10.0, lead_speed=9.2, lead_accel=-0.4, ego_accel=0.4, decel_enabled=True, **overrides)
  np.testing.assert_array_equal(mpc.params[:, 8], mpc.params[:, 1])
  assert mpc.solver.weights[0, 'Zl'][4] == 0.0


@pytest.mark.parametrize('block', ['none', 'stale', 'future', 'invalid', 'gas', 'brake', 'stop', 'reset', 'force', 'lane'])
def test_planner_only_enables_pulse_with_fresh_valid_active_inputs(block):
  import ast
  from pathlib import Path
  from types import SimpleNamespace as NS

  path = Path(__file__).resolve().parents[1] / 'lib/longitudinal_planner.py'
  tree = ast.parse(path.read_text())
  expression = next(n.value for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == 'lead_decel_enabled')

  class Messages(dict):
    def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self.recv_time = {'radarState': 9.8 if block == 'stale' else 10.1 if block == 'future' else 9.9}

    def all_checks(self, service_list):
      assert service_list == ['radarState', 'carState']
      return block != 'invalid'

  sm = Messages(carState=NS(gasPressed=block == 'gas', brakePressed=block == 'brake'))
  scope = {
    'sm': sm,
    'reset_state': block == 'reset',
    'force_slow_decel': block == 'force',
    'self': NS(output_should_stop=block == 'stop'),
    'carrot': NS(lane_change_active=block == 'lane'),
    'time': NS(monotonic=lambda: 10.0),
  }
  assert eval(compile(ast.Expression(expression), str(path), 'eval'), scope) == (block == 'none')


def test_onset_shape_keeps_total_descent_of_original_entry():
  assert onset_descent(0.0, ONSET_SHAPE_SECONDS) == pytest.approx(ATTACK_JERK * ONSET_SHAPE_SECONDS)
  assert onset_descent(ONSET_SHAPE_SECONDS, 0.5) == pytest.approx(ATTACK_JERK * 0.5)
  assert onset_descent(0.0, 3.0) == pytest.approx(ATTACK_JERK * 3.0)


def test_onset_shape_is_softer_early_and_catches_up_later():
  half = ONSET_SHAPE_SECONDS / 2
  assert onset_descent(0.0, half) < ATTACK_JERK * half
  assert onset_descent(half, half) > ATTACK_JERK * half
  # Largest temporary shortfall of the ceiling descent stays small.
  assert ATTACK_JERK * half - onset_descent(0.0, half) == pytest.approx(ATTACK_JERK * ONSET_SHAPE_AMPLITUDE * ONSET_SHAPE_SECONDS / np.pi)


def test_onset_slope_is_continuous_and_bounded():
  ages = np.arange(0.0, ONSET_SHAPE_SECONDS + 0.5, 0.01)
  slopes = np.array([onset_descent(age, 1e-4) / 1e-4 for age in ages])
  assert np.all(slopes >= ATTACK_JERK * (1 - ONSET_SHAPE_AMPLITUDE) - 1e-3)
  assert np.all(slopes <= ATTACK_JERK * (1 + ONSET_SHAPE_AMPLITUDE) + 1e-3)
  assert np.max(np.abs(np.diff(slopes))) < 0.01


def test_zero_amplitude_matches_original_linear_entry(monkeypatch):
  monkeypatch.setattr(decel_pulse, 'ONSET_SHAPE_AMPLITUDE', 0.0)
  for start, duration in [(0.0, 0.05), (0.3, 0.05), (0.0, 1.0), (0.7, 2.0)]:
    assert onset_descent(start, duration) == pytest.approx(ATTACK_JERK * duration)


def test_live_ceiling_matches_original_entry_after_shape_period():
  shaped, linear = [], []
  for amplitude, out in ((ONSET_SHAPE_AMPLITUDE, shaped), (0.0, linear)):
    decel_pulse.ONSET_SHAPE_AMPLITUDE = amplitude
    try:
      state = LeadDecelPulse()
      args = inputs()
      args['lead'].aLeadK = -1.2
      for _ in range(int(round((ONSET_SHAPE_SECONDS + 0.1) / 0.05))):
        state.acceleration_limits(**args)
        out.append(state.ceiling)
        args['planned_accel'] = state.ceiling  # the plan follows the ceiling, so the live floor moves too
    finally:
      decel_pulse.ONSET_SHAPE_AMPLITUDE = ONSET_SHAPE_AMPLITUDE
  assert shaped[5] > linear[5]  # softer early
  assert linear[-1] > -1.8  # still descending, so the comparison is not a saturated floor
  assert shaped[-1] == pytest.approx(linear[-1], abs=1e-9)
