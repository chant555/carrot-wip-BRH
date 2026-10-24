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
  h._activate_cruise = 0
  h._cancel_timer = 0
  h.disengage_on_accelerator = False
  h._add_log = Mock()
  cs = car.CarState(gasPressed=False, brakePressed=True, vEgo=0., gearShifter='drive',
                   canValid=True, cruiseState={'available': True})
  return h, cs


@pytest.mark.parametrize('cancel', [False, True])
def test_brake_release_holds_without_engaging_and_gas_stays_cancelled(cancel):
  h, cs = setup_hold()
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


@pytest.mark.parametrize('block', ['unavailable', 'auto_off', 'timer', 'gear', 'speed', 'can', 'gas', 'avh', 'parking', 'steering'])
def test_standalone_hold_keeps_entry_interlocks(block):
  h, cs = setup_hold()
  if block == 'unavailable': cs.cruiseState.available = False
  if block == 'auto_off': h.autoCruiseControl = 0
  if block == 'timer': h.autoCruiseControl_cancel_timer = 1
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


@pytest.mark.parametrize('press_frames,expected_hold', [(1, 0), (30, 0), (60, 0), (61, 2)])
def test_second_brake_tap_releases_hold_but_long_press_rearms(press_frames, expected_hold):
  from opendbc.car.hyundai.tests.test_stopping import make_cs, send
  from opendbc.car.hyundai.stopping import CanfdStopping
  h, cs = setup_hold()
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
