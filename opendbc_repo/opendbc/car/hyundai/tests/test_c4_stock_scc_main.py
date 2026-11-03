"""C4 (IONIQ 5 PE): keep the upstream stock SCC MAIN request, decoupled from Carrot standby.

Upstream 8d055419 turns stock SCC MAIN on while Carrot is disengaged so the cluster
shows corner-radar objects. On C4, stock MainMode_ACC used to set Carrot main_enabled,
which would make cruise available and let AutoCruiseControl engage without a button.
C4 keeps the request but Carrot standby follows only the driver's MAIN/SET/RES buttons.
The cluster/HUD (0x161) still shows the gray standby view for stock MAIN, because it
draws lead and corner objects only while 0x161 reports cruise main on.
"""
from types import SimpleNamespace

import pytest

from opendbc.can import CANPacker
from opendbc.can.parser import get_raw_value
from opendbc.car import structs
from opendbc.car.hyundai import hyundaicanfd
from opendbc.car.hyundai.carstate import CarState
from opendbc.car.hyundai.values import CAR, Buttons, HyundaiFlags
from opendbc.car.hyundai.tests.test_alt2_adas_buttons import cluster_main_request


def _with_fingerprint(monkeypatch, fingerprint):
  original = structs.CarParams

  def car_params(**kwargs):
    return original(carFingerprint=fingerprint, **kwargs)
  monkeypatch.setattr(structs, "CarParams", car_params)


def _main_frames(frames):
  return [frame for frame, values in frames
          if values["CRUISE_BUTTONS"] == 8 or values.get("ADAPTIVE_CRUISE_MAIN_BTN", 0)]


@pytest.mark.parametrize("fingerprint", (CAR.HYUNDAI_IONIQ_5_PE, CAR.KIA_EV9))
@pytest.mark.parametrize("alt2", (False, True))
def test_stock_main_request_is_kept_for_c4_and_other_cars(monkeypatch, fingerprint, alt2):
  _with_fingerprint(monkeypatch, fingerprint)
  frames = cluster_main_request(monkeypatch, alt2=alt2)
  # The harness uses CRUISE_BUTTONS_ALT (0x1AA). C4 itself uses CRUISE_BUTTONS (0x1CF)
  # through the same cruise_buttons_msg path. MAIN pulses every 2 s while stock MAIN is off.
  assert _main_frames(frames) == ([22, 24, 26, 222, 224, 226] if alt2 else [12, 14, 16, 212, 214, 216])


def test_c4_driver_buttons_still_take_precedence(monkeypatch):
  _with_fingerprint(monkeypatch, CAR.HYUNDAI_IONIQ_5_PE)
  frames = cluster_main_request(monkeypatch, alt2=False, driver={"CRUISE_BUTTONS": 1})
  assert frames and _main_frames(frames) == []


def carstate(fingerprint, *, main_enabled=False, manual_off=False, main_mode_acc=True):
  cs = CarState.__new__(CarState)
  cs.CP = SimpleNamespace(openpilotLongitudinalControl=True, carFingerprint=fingerprint)
  cs.main_enabled = main_enabled
  cs.manual_main_off_latched = manual_off
  cs.MainMode_ACC = main_mode_acc
  return cs


def test_c4_stock_main_on_does_not_make_cruise_standby():
  cs = carstate(CAR.HYUNDAI_IONIQ_5_PE)
  for _ in range(200):
    cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=False)
  assert not cs.main_enabled


def test_other_cars_keep_following_stock_main():
  cs = carstate(CAR.KIA_EV9)
  cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=False)
  assert cs.main_enabled


@pytest.mark.parametrize("button", (Buttons.RES_ACCEL, Buttons.SET_DECEL))
def test_c4_set_or_res_still_enables_standby(button):
  cs = carstate(CAR.HYUNDAI_IONIQ_5_PE, main_mode_acc=False)
  cs._update_canfd_main_enabled(button, main_button_released=False)
  assert cs.main_enabled and not cs.manual_main_off_latched


def test_c4_main_button_toggles_standby_on_and_off():
  cs = carstate(CAR.HYUNDAI_IONIQ_5_PE)
  cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=True)
  assert cs.main_enabled
  cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=True)
  assert not cs.main_enabled and cs.manual_main_off_latched
  # The automatic stock MAIN request may turn MainMode_ACC on again; standby stays off.
  cs.MainMode_ACC = True
  for _ in range(50):
    cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=False)
  assert not cs.main_enabled


def test_c4_standby_stays_on_after_driver_enable_even_if_stock_main_drops():
  cs = carstate(CAR.HYUNDAI_IONIQ_5_PE, main_mode_acc=False)
  cs._update_canfd_main_enabled(Buttons.SET_DECEL, main_button_released=False)
  cs.MainMode_ACC = False
  cs._update_canfd_main_enabled(Buttons.NONE, main_button_released=False)
  assert cs.main_enabled


CLUSTER_MAIN = ("SETSPEED", "SETSPEED_HUD", "DISTANCE_CAR", "DISTANCE_LEAD", "HDA_ICON")


def cluster_161(monkeypatch, fingerprint=CAR.HYUNDAI_IONIQ_5_PE, *, standby=False, stock_main=True,
                manual_off=False, longitudinal=True, lead=True):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, "Params", lambda: SimpleNamespace(get_int=lambda key: 0, get=lambda key: "0"))
  packer = CANPacker("hyundai_canfd_generated")
  definition = packer.dbc.name_to_msg["ADRV_0x161"]
  stock = {key: 0 for key in definition.sigs}
  radar = log.RadarState.new_message()
  if lead:
    radar.leadOne.status, radar.leadOne.dRel = True, 30.
  state = SimpleNamespace(
    adrv_0x161=stock, out=structs.CarState(), modelV2=None, lfahda_cluster=None, radarState=radar,
    cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
    MainMode_ACC=stock_main, manual_main_off_latched=manual_off,
  )
  state.out.cruiseState.available = standby
  control = structs.CarControl(enabled=False)
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=fingerprint,
                       openpilotLongitudinalControl=longitudinal)
  messages = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
                                               control.hudControl, 0, False, False, 0, False, 0, 0)
  assert [(address, bus) for address, _, bus in messages] == [(0x161, 0)]
  values = {key: get_raw_value(messages[0][1], sig) for key, sig in definition.sigs.items()}
  values.pop("CHECKSUM"), values.pop("COUNTER")
  return values


def test_c4_cluster_shows_standby_view_for_stock_main(monkeypatch):
  values = cluster_161(monkeypatch)
  assert {key: values[key] for key in CLUSTER_MAIN} == dict.fromkeys(CLUSTER_MAIN, 1)


def test_c4_cluster_for_stock_main_matches_driver_standby(monkeypatch):
  # Same 0x161 as "cruise on and paused" (gray icon), where the driver saw lead and side cars.
  assert cluster_161(monkeypatch) == cluster_161(monkeypatch, standby=True, stock_main=False)


@pytest.mark.parametrize("case", ({"stock_main": False}, {"manual_off": True}, {"longitudinal": False},
                                  {"fingerprint": CAR.KIA_EV9}))
def test_cluster_main_off_when_not_c4_stock_main(monkeypatch, case):
  values = cluster_161(monkeypatch, **case)
  assert {key: values[key] for key in CLUSTER_MAIN} == dict.fromkeys(CLUSTER_MAIN, 0)


def test_c4_cluster_lead_needs_a_lead(monkeypatch):
  values = cluster_161(monkeypatch, lead=False)
  assert values["DISTANCE_LEAD"] == 0 and values["DISTANCE_CAR"] == 1
