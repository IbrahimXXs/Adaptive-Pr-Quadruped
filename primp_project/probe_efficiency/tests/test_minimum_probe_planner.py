"""Proof authority and the force target of the minimum-sufficient policy."""
from dataclasses import replace

import numpy as np
import pytest

from primp_project.planning.load_capacity import (
    CapacityPlanningConfig, CertificateConfig, DemonstratedLoadCertificate,
    LoadObservation, MatchedCapacityPlanner,
)
from primp_project.probe_efficiency.planner import MinimumSufficientCapacityPlanner


ANCHORS = np.array([[.29, .15, .02], [.2, -.15, .02],
                    [-.2, .15, .02], [-.2, -.15, .02]])
ORIGIN = np.array([-1/15, -.05, .28])
WEIGHT = 150.
UPPER = np.full(4, WEIGHT)
CONFIG = CapacityPlanningConfig(forward_progress_m=.04, probe_force_ceiling_n=60.,
    requested_probe_load_n=60., maximum_probe_request_n=60.)


def exact_planner(config=CONFIG):
    return MinimumSufficientCapacityPlanner(config, probe_undershoot_allowance_n=0.)


def measured_proof(force, *, sensing=1., tracking=8.):
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5,
        measurement_margin_n=sensing, tracking_margin_n=tracking))
    for i in range(61):
        estimator.update(LoadObservation(i*.01, force, True, ANCHORS[0], np.zeros(3)))
    return estimator.certificate


def decide(planner, certificate, **kwargs):
    return planner.decide(certificate, ANCHORS, WEIGHT, ORIGIN, UPPER, **kwargs)


def test_sufficient_certificate_gets_identical_frozen_future_decision():
    proof = measured_proof(30.)
    baseline = decide(MatchedCapacityPlanner('adaptive_probe', CONFIG), proof)
    new = decide(exact_planner(), proof)
    assert baseline.action == new.action == 'EXECUTE'
    for name in baseline.__dataclass_fields__:
        np.testing.assert_equal(getattr(new, name), getattr(baseline, name))


def test_minimum_request_retains_all_reserves_without_maximum_test():
    planner = exact_planner()
    proof = measured_proof(12.)
    result = decide(planner, proof)
    maximum_policy = decide(MatchedCapacityPlanner('adaptive_probe', CONFIG), proof)
    assert result.action == maximum_policy.action == 'PROBE'
    assert result.minimum_future_load_n == pytest.approx(10.)
    assert result.requested_probe_load_n == pytest.approx(10.+1.+8.+.001)
    assert result.achievable_probe_load_n == result.requested_probe_load_n
    assert result.achievable_probe_load_n < maximum_policy.achievable_probe_load_n-10.
    assert result.usable_force_cap_n == proof.force_cap_n == 3.
    assert result.chosen_future_load_n == 0.
    target = planner.last_probe_target
    assert target.minimum_sufficient_probe_load_n == result.requested_probe_load_n
    assert target.measurement_reserve_n == 1. and target.tracking_reserve_n == 8.
    assert target.target_tolerance_n == .001
    assert target.commanded_force_is_not_measured_proof
    assert 'measurement_reserve_n' in target.formula


def test_fixed_posture_is_used_when_it_can_apply_the_minimum_test():
    result = decide(exact_planner(), measured_proof(12.))
    assert result.action == 'PROBE'
    np.testing.assert_array_equal(result.body_target_w, ORIGIN)
    np.testing.assert_allclose(ANCHORS[:, :2].T@result.allocated_forces_n,
                               WEIGHT*ORIGIN[:2], atol=1e-8)
    assert result.allocated_forces_n.sum() == pytest.approx(WEIGHT)
    assert np.all(result.allocated_forces_n[1:] >= CONFIG.minimum_support_force_n)
    assert result.support_margin_m >= CONFIG.original_tripod_margin_m


def test_predicted_minimal_test_is_sufficient_but_smaller_proof_is_not():
    planner = exact_planner()
    request = decide(planner, measured_proof(12.))
    successful = decide(planner, measured_proof(request.achievable_probe_load_n),
                        allow_additional_probe=False)
    insufficient = decide(planner, measured_proof(request.achievable_probe_load_n-.1),
                          allow_additional_probe=False)
    assert successful.action == 'EXECUTE'
    assert successful.allocated_forces_n[0] <= request.minimum_future_load_n+.001+1e-8
    assert insufficient.action == 'SAFE_STOP'


def test_target_tolerance_is_not_reused_to_relax_measured_proof():
    planner = exact_planner()
    request = decide(planner, measured_proof(12.))
    # Being within the 0.001 N target tolerance does not forgive a measured
    # usable cap even 0.000001 N below the shared optimizer's required load.
    measured = request.minimum_future_load_n+1.+8.-.000001
    result = decide(planner, measured_proof(measured), allow_additional_probe=False)
    assert result.action == 'SAFE_STOP'
    assert result.usable_force_cap_n < request.minimum_future_load_n


def test_command_does_not_manufacture_new_measured_proof():
    planner = exact_planner()
    proof = measured_proof(12.)
    request = decide(planner, proof)
    assert request.action == 'PROBE'
    assert proof.certified_load_n == 11. and proof.force_cap_n == 3.
    without_new_measurement = decide(planner, proof, allow_additional_probe=False)
    assert without_new_measurement.action == 'SAFE_STOP'
    assert without_new_measurement.certified_load_n == proof.certified_load_n


def test_negative_sensor_error_cannot_be_replaced_with_requested_force():
    planner = exact_planner()
    request = decide(planner, measured_proof(12.))
    # Applied force equal to the target does not imply a sufficient measured
    # lower bound when the permitted sensor bias is negative.
    actual_applied = request.achievable_probe_load_n
    measured = actual_applied-.5
    result = decide(planner, measured_proof(measured), allow_additional_probe=False)
    assert result.action == 'SAFE_STOP'
    assert result.certified_load_n <= actual_applied


def test_custom_certificate_reserves_are_used_without_reduction():
    planner = exact_planner()
    proof = measured_proof(12., sensing=1.2, tracking=9.)
    result = decide(planner, proof)
    assert result.action == 'PROBE'
    assert result.requested_probe_load_n == pytest.approx(10.+1.2+9.+.001)
    assert planner.last_probe_target.measurement_reserve_n == 1.2
    assert planner.last_probe_target.tracking_reserve_n == 9.


def test_command_allowance_is_separate_from_measured_sufficiency():
    planner = MinimumSufficientCapacityPlanner(CONFIG, sensor_force_error_bound_n=.8)
    result = decide(planner, measured_proof(12.))
    assert result.action == 'PROBE'
    target = planner.last_probe_target
    assert target.minimum_sufficient_probe_load_n == pytest.approx(19.001)
    assert target.probe_undershoot_allowance_n == .2
    assert target.sensor_force_error_bound_n == .8
    assert result.requested_probe_load_n == pytest.approx(20.001)
    assert target.requested_probe_load_n == result.requested_probe_load_n
    # Declared worst negative observation error plus expected undershoot
    # still predicts the unchanged measured lower-bound requirement.
    measured = result.requested_probe_load_n-.8-.2
    actual_proof = measured_proof(measured)
    assert actual_proof.measurement_margin_n == 1.
    assert actual_proof.tracking_margin_n == 8.
    assert decide(planner, actual_proof, allow_additional_probe=False).action == 'EXECUTE'
    # The allowance cannot manufacture proof when actual tracking is worse.
    assert decide(planner, measured_proof(measured-.1),
                  allow_additional_probe=False).action == 'SAFE_STOP'


def test_command_error_bound_cannot_exceed_certificate_sensing_reserve():
    planner = MinimumSufficientCapacityPlanner(CONFIG, sensor_force_error_bound_n=1.01)
    with pytest.raises(ValueError, match='sensing reserve'):
        decide(planner, measured_proof(12.))


@pytest.mark.parametrize('kwargs', [
    {'sensor_force_error_bound_n': -.1}, {'probe_undershoot_allowance_n': -.1},
    {'sensor_force_error_bound_n': np.nan}, {'probe_undershoot_allowance_n': np.inf},
])
def test_nonphysical_command_allowances_are_rejected(kwargs):
    with pytest.raises(ValueError, match='allowances'):
        MinimumSufficientCapacityPlanner(CONFIG, **kwargs)


def test_small_but_necessary_proof_increase_is_not_arbitrarily_rejected():
    planner = exact_planner()
    proof = measured_proof(18.75)  # Needs only 0.25 N more usable cap.
    result = decide(planner, proof)
    assert result.action == 'PROBE'
    assert result.achievable_probe_load_n-proof.measured_min_force_n < 1.
    assert decide(planner, measured_proof(result.achievable_probe_load_n),
                  allow_additional_probe=False).action == 'EXECUTE'


def test_changed_posture_is_selected_only_when_fixed_posture_cannot_suffice():
    anchors = np.array([[.255, .130, .02], [.165, -.170, .02],
                        [-.165, .170, .02], [-.165, -.170, .02]])
    origin = np.r_[anchors[1:, :2].mean(axis=0)+[-.04, 0.], .28]
    config = replace(CONFIG, next_lift_leg=1, minimum_support_force_n=12.,
                     probe_posture_adjustment_m=.10)
    planner = exact_planner(config)
    result = planner.decide(measured_proof(12.), anchors, WEIGHT, origin, UPPER)
    assert result.action == 'PROBE'
    assert result.minimum_future_load_n > result.fixed_pose_maximum_probe_load_n
    assert result.achievable_probe_load_n == pytest.approx(result.minimum_future_load_n+9.001)
    assert result.achievable_probe_load_n <= result.maximum_achievable_probe_load_n-2.+1e-9
    assert np.linalg.norm(result.body_target_w[:2]-origin[:2]) > .01
    assert np.all(np.abs(result.body_target_w[:2]-origin[:2]) <= .10+1e-9)
    after = planner.decide(measured_proof(result.achievable_probe_load_n),
                            anchors, WEIGHT, origin, UPPER, allow_additional_probe=False)
    assert after.action == 'EXECUTE'
    assert after.body_target_w[0]-origin[0] == pytest.approx(.04)


def test_same_additional_force_constraint_can_make_the_task_infeasible():
    planner = exact_planner()
    result = decide(planner, measured_proof(30.),
                    extra_matrix=[[1., 0., 0., 0.]], extra_upper=[9.])
    assert result.action == 'SAFE_STOP'
    assert planner.last_probe_target.minimum_future_load_n is None
    assert planner.last_probe_target.minimum_sufficient_probe_load_n is None


def test_insufficient_request_limit_stops_without_requesting_an_inadequate_test():
    planner = MinimumSufficientCapacityPlanner(replace(CONFIG, maximum_probe_request_n=18.))
    result = decide(planner, measured_proof(12.))
    assert result.action == 'SAFE_STOP'
    assert result.requested_probe_load_n == result.achievable_probe_load_n == 0.
    assert 'request limit' in result.reason


def test_invalidated_certificate_does_not_authorize_movement():
    invalid = replace(measured_proof(30.), valid=False)
    result = decide(exact_planner(), invalid,
                    allow_additional_probe=False)
    assert result.action == 'SAFE_STOP' and result.usable_force_cap_n == 0.


def test_hidden_failure_threshold_is_not_an_input():
    planner = exact_planner()
    with pytest.raises(TypeError, match='failure_threshold_n'):
        decide(planner, measured_proof(12.), failure_threshold_n=22.)


@pytest.mark.parametrize('tolerance', [0., -.001, .1, np.nan, np.inf])
def test_large_or_nonphysical_padding_cannot_be_called_numerical_tolerance(tolerance):
    with pytest.raises(ValueError, match='tolerance'):
        MinimumSufficientCapacityPlanner(CONFIG, target_tolerance_n=tolerance)
