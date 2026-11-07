"""Native regression for the extra soft constraint's cold-start convergence."""
from types import SimpleNamespace as NS

import numpy as np
import pytest


@pytest.mark.parametrize('mode', ['acc', 'blended'])
def test_cold_start_solves_a_consistent_trajectory(mode):
  pytest.importorskip('casadi')
  from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc, N, T_IDXS

  mpc = LongitudinalMpc(mode=mode)
  carrot = NS(mode=mode, myDrivingMode=3, jerk_factor=.7, comfort_brake=2.4,
              stop_distance=5.8, v_cruise=100/3.6, stop_dist=1000.,
              trafficStopDistanceAdjust=0., lane_change_active=False,
              leadAccelResponse=3, get_T_FOLLOW=lambda *args, **kwargs: .8)
  lead = NS(status=True, radar=True, radarTrackId=48, dRel=12., vRel=0.,
            vLead=0., aLeadK=-.4, aLeadTau=1.5, modelProb=1.)
  absent = NS(status=False, radar=False, radarTrackId=-1, modelProb=0.)
  mpc.set_accel_limits(-2., 1.7)
  # A cold trajectory with a large discrepancy from the new stopped-lead input.
  mpc.set_cur_state(9.75609756, .4)
  mpc.update(carrot, False, NS(leadOne=lead, leadTwo=absent), 100/3.6,
             *(np.zeros(N+1) for _ in range(4)), measured_a_ego=.4,
             lead_track_frames=(1, 0), lead_decel_enabled=True)
  assert mpc.solution_status == 0
  assert mpc.solver.get_stats('statistics')[1, -1] == 0
  dt = np.diff(T_IDXS)
  x, j = mpc.x_sol, mpc.j_solution
  np.testing.assert_allclose(np.diff(x[:, 2]), j * dt, rtol=0., atol=1e-5)
  np.testing.assert_allclose(np.diff(x[:, 1]), x[:-1, 2] * dt + .5 * j * dt**2, rtol=0., atol=1e-5)
  np.testing.assert_allclose(np.diff(x[:, 0]), x[:-1, 1] * dt + .5 * x[:-1, 2] * dt**2 + j * dt**3 / 6, rtol=0., atol=1e-5)
