from types import SimpleNamespace as NS
import pytest

from opendbc.car.common.blinker import OneTouchBlinkerLimit, ONE_TOUCH_MAX_S
from opendbc.car.hyundai.hyundaicanfd import _blink_hold_side


def car(side=1, count=0, lamp=0, lever=0):
  return NS(leftBlinker=side == 1, rightBlinker=side == 2, blinkerLever=lever,
            blinkerLamp=lamp, leftBlinkerStalkCount=count if side == 1 else 0,
            rightBlinkerStalkCount=count if side == 2 else 0)


@pytest.mark.parametrize('side', [1, 2])
@pytest.mark.parametrize('dt', [0.01, 0.05])
def test_four_actual_lightings_bound_both_queued_and_current_hold(side, dt):
  limit = OneTouchBlinkerLimit()
  limit.update(car(side), dt)
  limit.update(car(side, 1, side, 1), dt)
  md = NS(laneLines=[], meta=NS(laneChangeBlinkerHold='left' if side == 1 else 'right'))
  state = {}
  for flash in range(1, 5):
    if flash > 1:
      limit.update(car(side, 1, 0), dt)
      limit.update(car(side, 1, side), dt)
    assert _blink_hold_side(md, side + 2, state, limit) == (side + 2 if flash < 4 else 0)
  for _ in range(50):
    limit.update(car(side, 1, 0), dt)
    assert _blink_hold_side(md, side + 2, state, limit) == 0
  # A fresh physical press renews the budget even while the lamp is still on.
  limit.update(car(side, 2, side, 1), dt)
  assert not limit.expired and limit.flashes == 1
  assert _blink_hold_side(md, side + 2, state, limit) == side + 2


@pytest.mark.parametrize('lamp', [0, 1])
def test_missing_edges_have_a_deadline_and_latched_lever_is_not_one_touch(lamp):
  limit = OneTouchBlinkerLimit()
  limit.update(car(), 0.05)
  limit.update(car(count=1, lamp=lamp, lever=1), 0.05)
  for _ in range(round(ONE_TOUCH_MAX_S / 0.05)):
    limit.update(car(count=1, lamp=lamp), 0.05)
  assert limit.expired
  limit.update(car(count=2, lamp=1, lever=2), 0.05)
  assert limit.allows(1)
  for _ in range(200):
    limit.update(car(count=2, lamp=1, lever=2), 0.05)
  assert limit.allows(1)


def test_counter_wrap_is_a_fresh_request_and_process_start_is_not_a_phantom_press():
  limit = OneTouchBlinkerLimit()
  limit.update(car(count=255, lamp=1), 0.05)
  assert limit.side == 0
  limit.update(car(count=0, lamp=1, lever=1), 0.05)
  assert limit.side == 1 and limit.flashes == 1


def test_legacy_car_without_physical_feedback_is_unchanged():
  limit = OneTouchBlinkerLimit()
  for _ in range(200):
    limit.update(NS(leftBlinker=True, rightBlinker=False), 0.05)
  assert limit.allows(1) and limit.allows(2)
