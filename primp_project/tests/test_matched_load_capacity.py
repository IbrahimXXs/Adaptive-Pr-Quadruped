"""Matched movement freedoms and a geometric need for a changed test posture."""
from dataclasses import replace

import numpy as np
import pytest

from primp_project.planning.load_capacity import (
    CapacityPlanningConfig, CertificateConfig, DemonstratedLoadCertificate,
    LoadObservation, MatchedCapacityPlanner, solve_load_allocation,
)


ANCHORS = np.array([[.255, .130, .02], [.165, -.170, .02],
                    [-.165, .170, .02], [-.165, -.170, .02]])
ORIGIN = np.r_[ANCHORS[1:, :2].mean(axis=0)+[-.04, 0.], .28]
WEIGHT = 150.
UPPER = np.full(4, 150.)
CONFIG = CapacityPlanningConfig(next_lift_leg=1, forward_progress_m=.04,
    minimum_support_force_n=12., probe_posture_adjustment_m=.10,
    probe_force_ceiling_n=60., requested_probe_load_n=60., maximum_probe_request_n=60.)


def proof(force):
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5,
        measurement_margin_n=1., tracking_margin_n=8.))
    for i in range(61):
        estimator.update(LoadObservation(i*.01, force, True, ANCHORS[0], np.zeros(3)))
    return estimator.certificate


def equilibrium(allocation):
    np.testing.assert_allclose(np.r_[allocation.forces_n.sum(), ANCHORS[:, :2].T@allocation.forces_n],
        WEIGHT*np.r_[1., allocation.com_position_w[:2]], atol=1e-7)


def test_identical_certificate_gives_identical_movement_for_every_test_policy():
    decisions = [MatchedCapacityPlanner(policy, CONFIG).decide(proof(50.), ANCHORS,
        WEIGHT, ORIGIN, UPPER) for policy in MatchedCapacityPlanner.POLICIES]
    for decision in decisions:
        assert decision.action == 'EXECUTE'
        assert decision.next_lift_leg == 1
        assert decision.body_target_w[0]-ORIGIN[0] >= .04-1e-9
        assert decision.support_margin_m >= .01-1e-9
        assert decision.allocated_forces_n[1] == pytest.approx(0.)
        assert decision.allocated_forces_n[0] <= 41.+1e-8
        np.testing.assert_array_equal(decision.body_target_w, decisions[0].body_target_w)
        np.testing.assert_array_equal(decision.allocated_forces_n, decisions[0].allocated_forces_n)
        np.testing.assert_array_equal(decision.mpc_force_caps_n, decisions[0].mpc_force_caps_n)


def test_fixed_probe_has_the_same_lateral_adaptation_as_the_method():
    # A 20N usable certificate makes the old fixed next pose infeasible, but
    # the matched baseline must exploit the same lateral freedom as the method.
    anchors = np.array([[.29, .15, .02], [.2, -.15, .02], [-.2, .15, .02], [-.2, -.15, .02]])
    origin = np.array([-1/15, -.05, .28])
    decisions = [MatchedCapacityPlanner(policy).decide(proof(29.), anchors,
        WEIGHT, origin, UPPER) for policy in MatchedCapacityPlanner.POLICIES]
    assert all(d.action == 'EXECUTE' for d in decisions)
    assert decisions[0].body_target_w[1] == pytest.approx(-.11, abs=1e-7)
    for decision in decisions[1:]:
        np.testing.assert_array_equal(decision.body_target_w, decisions[0].body_target_w)


def test_pose_is_necessary_even_if_fixed_test_gets_its_unreserved_physical_maximum():
    planner = MatchedCapacityPlanner('adaptive_probe', CONFIG)
    minimum = planner.minimum_future_allocation(ANCHORS, WEIGHT, ORIGIN, UPPER)
    fixed, fixed_maximum = planner.probe_allocation(ANCHORS, WEIGHT, ORIGIN,
        60., UPPER, allow_posture_change=False)
    moved, moved_maximum = planner.probe_allocation(ANCHORS, WEIGHT, ORIGIN,
        60., UPPER, allow_posture_change=True)
    assert minimum.feasible and fixed.feasible and moved.feasible
    for allocation in (minimum, fixed, moved):
        equilibrium(allocation)
    # After FR lift, only FL is ahead of the two equal-x rear anchors.
    # This lower bound holds for EVERY lateral pose and force allocation.
    physical_lower_bound = WEIGHT*(ORIGIN[0]+.04-ANCHORS[2, 0])/(ANCHORS[0, 0]-ANCHORS[2, 0])
    assert minimum.forces_n[0] == pytest.approx(physical_lower_bound)
    assert physical_lower_bound == pytest.approx(39.2857142857)
    assert fixed_maximum == pytest.approx(15.5714285714)
    assert fixed_maximum < physical_lower_bound  # No sensing reserve is needed to establish impossibility.
    ideal_fixed = solve_load_allocation(ANCHORS, WEIGHT, ORIGIN, np.zeros(4),
        UPPER, maximize_leg=0)
    assert ideal_fixed.feasible and ideal_fixed.forces_n[0] == pytest.approx(25.)
    # Even removing the 12N safety floors and the 2N probing reserve cannot
    # make the fixed test pose sufficient. This is a moment-balance limitation.
    assert ideal_fixed.forces_n[0] < physical_lower_bound
    relaxed_physical_task = WEIGHT*(ORIGIN[0]+.03-ANCHORS[2, 0])/(ANCHORS[0, 0]-ANCHORS[2, 0])
    assert ideal_fixed.forces_n[0] < relaxed_physical_task
    assert moved_maximum == pytest.approx(51.2857142857)
    assert moved.forces_n[0] == pytest.approx(moved_maximum-2.)
    assert moved.forces_n[0]-1.-8. > physical_lower_bound
    assert np.all(moved.forces_n[1:] >= 12.-1e-8)
    assert moved.support_margin_m >= .02-1e-9
    assert np.all(np.abs(moved.com_position_w[:2]-ORIGIN[:2]) <= .10+1e-9)


def test_only_actual_new_proof_authorizes_the_shared_future_task():
    original = proof(12.)
    decisions = {policy: MatchedCapacityPlanner(policy, CONFIG).decide(original,
        ANCHORS, WEIGHT, ORIGIN, UPPER) for policy in MatchedCapacityPlanner.POLICIES}
    assert decisions['fixed_probe'].action == 'SAFE_STOP'
    assert decisions['adaptive_force_fixed_posture'].action == 'SAFE_STOP'
    probe = decisions['adaptive_probe']
    assert probe.action == 'PROBE' and probe.chosen_future_load_n == 0.
    assert probe.minimum_future_load_n > probe.fixed_pose_maximum_probe_load_n
    assert original.certified_load_n == 11. and original.force_cap_n == 3.
    planner = MatchedCapacityPlanner('adaptive_probe', CONFIG)
    without_proof = planner.decide(original, ANCHORS, WEIGHT, ORIGIN, UPPER,
        allow_additional_probe=False)
    assert without_proof.action == 'SAFE_STOP'
    new_certificate = proof(probe.achievable_probe_load_n)
    after = planner.decide(new_certificate, ANCHORS, WEIGHT, ORIGIN, UPPER)
    assert after.action == 'EXECUTE'
    # The stronger test moves farther forward than the eventual task goal.
    # Progress is therefore measured from the INITIAL test origin, never reset.
    assert probe.body_target_w[0] > after.body_target_w[0]
    assert after.body_target_w[0]-ORIGIN[0] == pytest.approx(.04, abs=1e-8)
    assert after.allocated_forces_n[0]+8. <= new_certificate.certified_load_n+1e-8


def test_same_physical_force_limit_can_make_every_policy_stop():
    upper = UPPER.copy(); upper[0] = 35.
    for policy in MatchedCapacityPlanner.POLICIES:
        decision = MatchedCapacityPlanner(policy, CONFIG).decide(proof(50.),
            ANCHORS, WEIGHT, ORIGIN, upper)
        assert decision.action == 'SAFE_STOP'
        assert decision.mpc_force_caps_n[0] <= 35.


def test_calibrated_additional_constraint_limits_test_and_future_equally():
    for policy in MatchedCapacityPlanner.POLICIES:
        planner = MatchedCapacityPlanner(policy, CONFIG)
        decision = planner.decide(proof(50.), ANCHORS, WEIGHT, ORIGIN, UPPER,
            extra_matrix=[[1., 0., 0., 0.]], extra_upper=[35.])
        assert decision.action == 'SAFE_STOP'
        assert not planner.minimum_future_allocation(ANCHORS, WEIGHT, ORIGIN, UPPER,
            extra_matrix=[[1., 0., 0., 0.]], extra_upper=[35.]).feasible


def test_force_only_policy_can_reprobe_when_fixed_geometry_is_sufficient():
    anchors = np.array([[.29, .15, .02], [.2, -.15, .02], [-.2, .15, .02], [-.2, -.15, .02]])
    origin = np.array([-1/15, -.05, .28])
    config = replace(CapacityPlanningConfig(), probe_force_ceiling_n=60.)
    decision = MatchedCapacityPlanner('adaptive_force_fixed_posture', config).decide(
        proof(12.), anchors, WEIGHT, origin, UPPER)
    assert decision.action == 'PROBE'
    np.testing.assert_array_equal(decision.body_target_w, origin)
    adaptive = MatchedCapacityPlanner('adaptive_probe', config).decide(
        proof(12.), anchors, WEIGHT, origin, UPPER)
    assert adaptive.action == 'PROBE'
    # More probing freedom must not cause an unnecessary larger test or pose
    # excursion when the very same fixed-pose stronger test already suffices.
    np.testing.assert_array_equal(adaptive.body_target_w, decision.body_target_w)
    np.testing.assert_array_equal(adaptive.allocated_forces_n, decision.allocated_forces_n)
    assert adaptive.achievable_probe_load_n == decision.achievable_probe_load_n


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError, match='policy'):
        MatchedCapacityPlanner('handicapped_future_planner')
