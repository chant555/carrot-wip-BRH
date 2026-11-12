import math

import numpy as np
import pytest

from openpilot.selfdrive.controls.lib.longitudinal_lead_anticipation import (
  MIN_TAU, SPARE_REFERENCE_M, LeadAnticipationState, anticipated_tau, anticipation_need,
)
from openpilot.selfdrive.controls.radar_constants import LEAD_ACCEL_TAU


def need(**overrides):
  values = {'spare': 0.0, 'closing': 0.5, 'a_lead': -1.0, 'v_ego': 8.0}
  values.update(overrides)
  return anticipation_need(**values)


def test_spare_gap_leaves_the_lead_prediction_unchanged():
  assert need(spare=SPARE_REFERENCE_M + 1.0, closing=0.0) == 0.0
  assert anticipated_tau(LEAD_ACCEL_TAU, 0.0) == LEAD_ACCEL_TAU


def test_short_gap_and_braking_lead_make_braking_persistent():
  assert need(spare=-1.0) == pytest.approx(1.0)
  assert anticipated_tau(LEAD_ACCEL_TAU, 1.0) == pytest.approx(MIN_TAU)


def test_need_grows_continuously_as_spare_gap_shrinks():
  spares = np.linspace(4.0, -1.0, 51)
  needs = [need(spare=s, closing=0.0) for s in spares]
  assert all(b >= a for a, b in zip(needs, needs[1:], strict=False))
  assert max(abs(b - a) for a, b in zip(needs, needs[1:], strict=False)) < 0.1


def test_closing_counts_against_the_spare_gap():
  assert need(spare=2.0, closing=0.0) == 0.0
  assert need(spare=2.0, closing=1.5) > 0.5


@pytest.mark.parametrize('a_lead', [0.3, 0.0, -0.05, -0.1])
def test_non_braking_lead_needs_no_anticipation(a_lead):
  assert need(spare=-2.0, a_lead=a_lead) == 0.0


def test_stopping_speeds_are_left_to_the_stopping_logic():
  assert need(spare=-2.0, v_ego=1.0) == 0.0


@pytest.mark.parametrize('field', ['spare', 'closing', 'a_lead', 'v_ego'])
def test_nonfinite_inputs_need_no_anticipation(field):
  assert need(**{field: math.nan}) == 0.0


def test_tau_is_never_made_less_persistent_than_the_lead_reports():
  assert anticipated_tau(0.2, 1.0) == pytest.approx(0.2)
  assert anticipated_tau(math.nan, 0.0) == LEAD_ACCEL_TAU


def test_state_filters_need_and_resets_on_track_change_or_loss():
  state = LeadAnticipationState()
  args = {'valid': True, 'track_id': 7, 'spare': -1.0, 'closing': 0.5, 'a_lead': -1.0, 'v_ego': 8.0, 'dt': 0.05}
  first = state.update(**args)
  assert 0.0 < first < 1.0
  for _ in range(40):
    state.update(**args)
  assert state.need == pytest.approx(1.0, abs=1e-3)
  assert state.update(**{**args, 'track_id': 8}) < 0.5
  assert state.update(**{**args, 'valid': False}) == 0.0


def test_release_is_slower_than_attack():
  state = LeadAnticipationState()
  args = {'valid': True, 'track_id': 7, 'spare': -1.0, 'closing': 0.5, 'a_lead': -1.0, 'v_ego': 8.0, 'dt': 0.05}
  for _ in range(40):
    state.update(**args)
  released = state.update(**{**args, 'a_lead': 0.5})
  attack = LeadAnticipationState().update(**args)
  assert 1.0 - released < attack
