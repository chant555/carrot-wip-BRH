"""C4 (IONIQ 5 PE): the upstream automatic stock SCC MAIN request stays off.

Stock MAIN turning on makes Carrot cruise available on this car, so with
AutoCruiseControl it could engage without a driver button press.
"""
import pytest

from opendbc.car import structs
from opendbc.car.hyundai.values import CAR, HyundaiFlags
from opendbc.car.hyundai.tests.test_alt2_adas_buttons import cluster_main_request


def _with_fingerprint(monkeypatch, fingerprint):
  original = structs.CarParams

  def car_params(**kwargs):
    return original(carFingerprint=fingerprint, **kwargs)
  monkeypatch.setattr(structs, "CarParams", car_params)


def _main_frames(frames):
  return [frame for frame, values in frames
          if values["CRUISE_BUTTONS"] == 8 or values.get("ADAPTIVE_CRUISE_MAIN_BTN", 0)]


@pytest.mark.parametrize("alt2", (False, True))
def test_c4_does_not_request_stock_main_while_carrot_disabled(monkeypatch, alt2):
  _with_fingerprint(monkeypatch, CAR.HYUNDAI_IONIQ_5_PE)
  frames = cluster_main_request(monkeypatch, alt2=alt2)
  assert frames, "button messages must still be produced"
  assert _main_frames(frames) == []


@pytest.mark.parametrize("alt2", (False, True))
def test_other_camera_scc_cars_keep_upstream_main_request(monkeypatch, alt2):
  _with_fingerprint(monkeypatch, CAR.KIA_EV9)
  frames = cluster_main_request(monkeypatch, alt2=alt2)
  assert _main_frames(frames) == ([22, 24, 26, 222, 224, 226] if alt2 else [12, 14, 16, 212, 214, 216])


def test_c4_driver_main_button_is_still_forwarded(monkeypatch):
  _with_fingerprint(monkeypatch, CAR.HYUNDAI_IONIQ_5_PE)
  frames = cluster_main_request(monkeypatch, alt2=False, driver={"ADAPTIVE_CRUISE_MAIN_BTN": 1})
  assert frames and all(values["ADAPTIVE_CRUISE_MAIN_BTN"] == 1 for _, values in frames)


def test_flags_used_by_c4_match_the_gate():
  # The gate depends on CameraSCC; keep this assumption visible.
  assert HyundaiFlags.CAMERA_SCC.value
