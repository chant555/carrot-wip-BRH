"""IONIQ 5 PE standalone hold: no automatic cruise request or widened interlocks."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from openpilot.cereal import car
from openpilot.selfdrive.car.cruise import VCruiseCarrot
from opendbc.car.hyundai.values import CAR


def setup_hold():
  h = VCruiseCarrot.__new__(VCruiseCarrot)
  h.CP = NS(carFingerprint=CAR.HYUNDAI_IONIQ_5_PE, openpilotLongitudinalControl=True, pcmCruise=False)
  h.autoCruiseControl = 1
  h.autoCruiseControl_cancel_timer = 0
  h.soft_hold_on_cancel = False
  h._cruise_cancel_state = True
  h._steering_interlock_active = False
  h._hold_interlock_active = False
  h._cruise_available = True
  h._cruise_ready = False
  h._paddle_decel_active = False
  h.carrot_cruise_active = False
  h.enabled_last = False
  h._gas_pressed_count = -1
  h._gas_pressed_count_last = 0
  h._gas_pressed_value = 0
  h._gas_tok_timer = 40
  h._gas_tok = False
  h._brake_pressed_count = 0
  h._soft_hold_count = 0
  h._soft_hold_active = 0
  h._independent_soft_hold_driven = True  # Existing hold scenarios start after qualifying driving.
  h._activate_cruise = 0
  h._cancel_timer = 0
  h.disengage_on_accelerator = False
  h._add_log = Mock()
  cs = car.CarState(gasPressed=False, brakePressed=True, vEgo=0., gearShifter='drive',
                   canValid=True, independentSoftHoldReady=True, cruiseState={'available': True})
  return h, cs


@pytest.mark.parametrize('available', [False, True])
@pytest.mark.parametrize('cancel', [False, True])
def test_brake_release_holds_without_engaging_and_gas_stays_cancelled(cancel, available):
  h, cs = setup_hold()
  cs.cruiseState.available = h._cruise_available = available
  h._cruise_cancel_state = cancel
  cc = car.CarControl(enabled=False)
  for tick in range(61):
    h._prepare_brake_gas(cs, cc)
    if tick < 60:
      assert h._soft_hold_active == 0
  assert h._soft_hold_active == 1
  cs.brakePressed = False
  for _ in range(100):
    h._prepare_brake_gas(cs, cc)
    assert h._update_cruise_state(cs, cc, 30) == 30
    assert h._soft_hold_active == 2
    assert h._activate_cruise == 0
  cs.gasPressed, cs.gas = True, .2
  h._prepare_brake_gas(cs, cc)
  assert h._soft_hold_active == 0 and h._cruise_cancel_state
  h._cruise_control(1, -1, 'automatic gas/lead resume')
  assert h._activate_cruise <= 0


@pytest.mark.parametrize('block', ['not_ready', 'auto_off', 'not_driven', 'gear', 'speed', 'can', 'gas', 'avh', 'parking', 'steering'])
def test_standalone_hold_keeps_entry_interlocks(block):
  h, cs = setup_hold()
  if block == 'not_ready': cs.independentSoftHoldReady = False
  if block == 'auto_off': h.autoCruiseControl = 0
  if block == 'not_driven': h._independent_soft_hold_driven = False
  if block == 'gear': cs.gearShifter = 'reverse'
  if block == 'speed': cs.vEgo = .1
  if block == 'can': cs.canValid = False
  if block == 'gas': cs.gasPressed, cs.gas = True, .2
  if block == 'avh': cs.brakeHoldActive = True
  if block == 'parking': cs.parkingBrake = True
  if block == 'steering': h._steering_interlock_active = True
  for _ in range(100): h._prepare_brake_gas(cs, car.CarControl(enabled=False))
  assert h._soft_hold_count == h._soft_hold_active == 0


@pytest.mark.parametrize('fingerprint,longitudinal,pcm,expected', [
  (CAR.HYUNDAI_IONIQ_5_PE, True, False, True),
  (CAR.HYUNDAI_IONIQ_5_PE, False, False, False),
  (CAR.HYUNDAI_IONIQ_5_PE, True, True, False),
  (CAR.HYUNDAI_IONIQ_5, True, False, False),
])
def test_vehicle_scope(fingerprint, longitudinal, pcm, expected):
  h, _ = setup_hold()
  h.CP = NS(carFingerprint=fingerprint, openpilotLongitudinalControl=longitudinal, pcmCruise=pcm)
  assert h._independent_soft_hold() is expected


def test_already_engaged_hold_does_not_change_engagement():
  h, cs = setup_hold()
  h._cruise_cancel_state = False
  h._soft_hold_active = 1
  h._brake_pressed_count = -1
  assert h._update_cruise_state(cs, car.CarControl(enabled=True), 30) == 30
  assert h._activate_cruise == 0 and not h._cruise_cancel_state


def test_independent_state_drives_existing_zero_accel_stop_request():
  from opendbc.car.hyundai.tests.test_stopping import make_cs, send
  from opendbc.car.hyundai.stopping import CanfdStopping
  h, cs = setup_hold()
  cc = car.CarControl(enabled=False)
  for _ in range(61): h._prepare_brake_gas(cs, cc)
  cs.brakePressed = False
  h._prepare_brake_gas(cs, cc)
  h._update_cruise_state(cs, cc, 30)
  vehicle = make_cs()
  vehicle.softHoldActive = h._soft_hold_active
  vehicle.out.vEgo = vehicle.out.vEgoRaw = 0.
  vehicle.out.brakePressed = False
  vehicle.out.wheelSpeeds = NS(fl=0., fr=0., rl=0., rr=0.)
  controller = CanfdStopping()
  for _ in range(150):
    values = send(True, controller, vehicle, enabled=False, stopping=False, accel=0.)
    assert values['StopReq'] == values['ACCMode'] == 1
    assert values['aReqRaw'] == values['aReqValue'] == 0.
    assert h._activate_cruise == 0


@pytest.mark.parametrize('available', [False, True])
@pytest.mark.parametrize('press_frames,expected_hold', [(1, 0), (30, 0), (60, 0), (61, 2)])
def test_second_brake_tap_releases_hold_but_long_press_rearms(press_frames, expected_hold, available):
  from opendbc.car.hyundai.tests.test_stopping import make_cs, send
  from opendbc.car.hyundai.stopping import CanfdStopping
  h, cs = setup_hold()
  cs.cruiseState.available = h._cruise_available = available
  h.params = NS(get_bool=lambda key: False)
  h.v_cruise_kph = 30
  h.v_ego_kph_set = 0
  h.autoGasTokSpeed = 10
  h.xState = 0
  h.d_rel = 0
  h.desiredSpeed = 30
  h._auto_speed_up = lambda speed: speed
  cc = car.CarControl(enabled=False)
  for _ in range(61): h._prepare_brake_gas(cs, cc)
  cs.brakePressed = False
  h._prepare_brake_gas(cs, cc)
  h._update_cruise_state(cs, cc, 30)
  assert h._soft_hold_active == 2

  cs.brakePressed = True
  for _ in range(press_frames):
    h._prepare_brake_gas(cs, cc)
    h._update_cruise_state(cs, cc, 30)
  cs.brakePressed = False
  for _ in range(3):
    h._prepare_brake_gas(cs, cc)
    h._update_cruise_state(cs, cc, 30)
    assert h._soft_hold_active == expected_hold
    assert h._activate_cruise == 0

  vehicle = make_cs()
  vehicle.softHoldActive = h._soft_hold_active
  vehicle.out.brakePressed = False
  vehicle.out.vEgo = vehicle.out.vEgoRaw = 0.
  vehicle.out.wheelSpeeds = NS(fl=0., fr=0., rl=0., rr=0.)
  values = send(True, CanfdStopping(), vehicle, enabled=False, stopping=False, accel=0.)
  assert values['StopReq'] == int(expected_hold > 0)


@pytest.mark.parametrize("ready_count,expected", [(0, False), (199, False), (200, True), (201, True)])
def test_vehicle_readiness_does_not_require_any_cruise_button(ready_count, expected):
  from opendbc.car.hyundai.carstate import CarState
  vehicle = CarState.__new__(CarState)
  vehicle.CP = setup_hold()[0].CP
  vehicle.controls_ready_count = ready_count
  vehicle.main_enabled = False
  assert vehicle._independent_soft_hold_ready() is expected
  assert not vehicle.main_enabled
  vehicle.CP.carFingerprint = CAR.HYUNDAI_IONIQ_5
  assert not vehicle._independent_soft_hold_ready()


@pytest.mark.parametrize('camera', [True, False])
@pytest.mark.parametrize('block', [None, 'not_ready', 'can', 'gas', 'parking', 'avh', 'gear', 'no_controller'])
def test_pre_button_hold_output_and_interlocks(camera, block):
  from opendbc.car.hyundai.tests.test_stopping import make_cs, send
  from opendbc.car.hyundai.stopping import CanfdStopping
  cs = make_cs()
  cs.softHoldActive = 2
  cs.out.cruiseState.available = False
  cs.out.independentSoftHoldReady = True
  cs.out.vEgo = cs.out.vEgoRaw = 0.
  cs.out.wheelSpeeds = NS(fl=0., fr=0., rl=0., rr=0.)
  if block == 'not_ready': cs.out.independentSoftHoldReady = False
  if block == 'can': cs.out.canValid = False
  if block == 'gas': cs.out.gasPressed = True
  if block == 'parking': cs.out.parkingBrake = True
  if block == 'avh': cs.out.brakeHoldActive = True
  if block == 'gear': cs.out.gearShifter = 'reverse'
  controller = None if block == 'no_controller' else CanfdStopping()
  values = send(camera, controller, cs, enabled=False, stopping=False, accel=1.5, previous_value=1.5)
  assert values['StopReq'] == values['ACCMode'] == int(block is None)
  assert values['aReqRaw'] == values['aReqValue'] == 0.
  assert not cs.out.cruiseState.available
  # Readiness alone may never enable ordinary longitudinal control.
  cs.softHoldActive = 0
  values = send(camera, controller, cs, enabled=True, stopping=True, accel=1.5)
  assert values['StopReq'] == values['ACCMode'] == 0
  assert values['aReqRaw'] == values['aReqValue'] == 0.


def setup_full_cruise_update():
  from collections import defaultdict
  h, cs = setup_hold()
  cs.cruiseState.available = False
  h.frame = 0
  h.v_cruise_kph = h.v_cruise_cluster_kph = 30
  h._cruise_speed_min, h._cruise_speed_max = 10, 160
  h.speed_from_pcm = 0
  h.cruise_state_available_last = False
  h.update_params = lambda metric: None
  h._update_carrot_man = lambda sm: None
  h.toyota_pcm_speed_sync = NS(update=lambda *args, **kwargs: None)
  # Preserve real state transitions; only unrelated button parsing is isolated.
  h.bluetooth_commands = NS(read=lambda **kwargs: None)
  h.button_cnt = 0
  h._paddle_mode = 0
  h._prepare_buttons = lambda cs, speed, remote: (speed, 0, False)
  h._carrot_command = lambda speed, button, long: (speed, button, long)
  h._auto_speed_up = lambda speed: speed
  h.params = NS(get_bool=lambda key: False)
  h.autoGasTokSpeed, h.xState, h.d_rel, h.desiredSpeed = 10, 0, 0, 30
  class SM(dict):
    alive = defaultdict(bool)
  sm = SM(carControl=car.CarControl(enabled=False))
  return h, cs, sm


def test_full_cruise_update_preserves_pre_button_hold_and_clears_readiness_loss():
  h, cs, sm = setup_full_cruise_update()
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 1
  cs.brakePressed = False
  for _ in range(100):
    h.update_v_cruise(cs, sm, True)
    assert h._soft_hold_active == 2 and h._activate_cruise == 0
    assert not cs.cruiseState.available
  cs.independentSoftHoldReady = False
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == h._soft_hold_count == 0


@pytest.mark.parametrize('previous_gear', ['park', 'reverse', 'neutral'])
def test_drive_history_resets_and_elapsed_time_cannot_arm_independent_hold(previous_gear):
  h, cs, sm = setup_full_cruise_update()
  cs.gearShifter = previous_gear
  h.update_v_cruise(cs, sm, True)
  cs.gearShifter = 'drive'
  for _ in range(1200): h.update_v_cruise(cs, sm, True)
  assert h.autoCruiseControl_cancel_timer == 0
  assert h._soft_hold_count == h._soft_hold_active == 0
  assert not h._independent_soft_hold_driven


@pytest.mark.parametrize('speed,can_valid,timeout,expected', [
  (15.99, True, False, False), (16., True, False, True), (20., True, False, True),
  (20., False, False, False), (20., True, True, False),
  (float('nan'), True, False, False), (float('inf'), True, False, False),
])
def test_speed_history_boundary_and_validity(speed, can_valid, timeout, expected):
  h, cs, sm = setup_full_cruise_update()
  h._independent_soft_hold_driven = False
  h.autoCruiseControl_cancel_timer = 1000
  cs.vEgo, cs.canValid, cs.canTimeout = speed / 3.6, can_valid, timeout
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  cs.vEgo, cs.canValid, cs.canTimeout, cs.brakePressed = 0., True, False, True
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == int(expected)
  assert h.autoCruiseControl_cancel_timer > 0  # Hold no longer waits for this timer.
  assert h._activate_cruise == 0


@pytest.mark.parametrize('gear', ['park', 'reverse', 'neutral'])
def test_gear_change_drops_active_hold_and_requires_new_driving(gear):
  h, cs, sm = setup_full_cruise_update()
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 2
  cs.gearShifter = gear
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 0 and not h._independent_soft_hold_driven
  cs.gearShifter, cs.brakePressed = 'drive', True
  for _ in range(1200): h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 0
  cs.vEgo, cs.brakePressed = 16 / 3.6, False
  h.update_v_cruise(cs, sm, True)
  cs.vEgo, cs.brakePressed = 0., True
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 2 and h._activate_cruise == 0


def test_brake_tap_keeps_drive_history_and_can_rearm_without_accelerating():
  h, cs, sm = setup_full_cruise_update()
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  cs.brakePressed = True
  for _ in range(30): h.update_v_cruise(cs, sm, True)
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 0 and h._independent_soft_hold_driven
  cs.brakePressed = True
  for _ in range(61): h.update_v_cruise(cs, sm, True)
  cs.brakePressed = False
  h.update_v_cruise(cs, sm, True)
  assert h._soft_hold_active == 2 and h._activate_cruise == 0


@pytest.mark.parametrize('speed', [0., 20.])
def test_automatic_cruise_keeps_ten_second_timer_independent_of_speed_history(speed):
  h, cs, sm = setup_full_cruise_update()
  cs.cruiseState.available = True
  cs.gearShifter = 'park'
  h.update_v_cruise(cs, sm, True)
  assert h.autoCruiseControl_cancel_timer == 1000
  cs.gearShifter, cs.brakePressed, cs.vEgo = 'drive', False, speed / 3.6
  for _ in range(999): h.update_v_cruise(cs, sm, True)
  assert h._independent_soft_hold_driven == (speed >= 16)
  assert h.autoCruiseControl_cancel_timer == 1
  h._cruise_cancel_state = False
  h._cruise_control(1, -1, 'automatic request')
  assert h._activate_cruise == 0
  h.update_v_cruise(cs, sm, True)
  h._cruise_control(1, -1, 'automatic request')
  assert h.autoCruiseControl_cancel_timer == 0 and h._activate_cruise == 1


@pytest.mark.parametrize('ready', [False, True])
@pytest.mark.parametrize('direction', [0, 1, 2])
def test_independent_hold_schema_roundtrip_does_not_alias_auto_indicator(ready, direction):
  state = car.CarState(independentSoftHoldReady=ready, autoTurnSignalDirection=direction,
                       tbtRightRearBlocked=True, laneLineInfoMonoTime=123456789)
  with car.CarState.from_bytes(state.to_bytes()) as decoded:
    assert decoded.independentSoftHoldReady == ready
    assert decoded.autoTurnSignalDirection == direction
    assert decoded.tbtRightRearBlocked
    assert decoded.laneLineInfoMonoTime == 123456789
  # Upstream owns @112 (laneLineInfoMonoTime) since 7e88bb72; the user field moved to @113.
  assert car.CarState.schema.fields['independentSoftHoldReady'].proto.ordinal.explicit == 113
  assert car.CarState.schema.fields['laneLineInfoMonoTime'].proto.ordinal.explicit == 112
  assert car.CarState.schema.fields['autoTurnSignalDirection'].proto.ordinal.explicit == 105
