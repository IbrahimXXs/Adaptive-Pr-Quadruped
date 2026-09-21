"""One development-selected test amplitude with matched movement authority."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from primp_project.control.weak_pad_v2 import WeakPadV2Wrapper
from primp_project.planning.load_capacity import (
    CapacityDecision, CapacityPlanningConfig, CertificateConfig,
    DemonstratedLoadCertificate, LoadObservation, MatchedCapacityPlanner,
)
from primp_project.probe_efficiency.control import MinimumSufficientWrapper
from primp_project.probe_efficiency.planner import MinimumSufficientCapacityPlanner
from primp_project.task_probe.control import FixedForceWrapper
from primp_project.task_probe.planner import FixedForceCapacityPlanner


ANCHORS = np.array([[.255, .130, .02], [.165, -.170, .02],
                    [-.165, .170, .02], [-.165, -.170, .02]])
ORIGIN = np.r_[ANCHORS[1:, :2].mean(axis=0)+[-.04, 0.], .28]
WEIGHT, UPPER = 150., np.full(4, 150.)
CONFIG = CapacityPlanningConfig(next_lift_leg=1, forward_progress_m=.04,
    minimum_support_force_n=12., probe_posture_adjustment_m=.10,
    probe_force_ceiling_n=60., requested_probe_load_n=60., maximum_probe_request_n=60.)


def proof(force):
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5,
        measurement_margin_n=1., tracking_margin_n=8.))
    for i in range(61):
        estimator.update(LoadObservation(i*.01, force, True, ANCHORS[0], np.zeros(3)))
    return estimator.certificate


def decide(planner, certificate, **kwargs):
    return planner.decide(certificate, ANCHORS, WEIGHT, ORIGIN, UPPER, **kwargs)


def fixed(config=CONFIG, force=47., **kwargs):
    return FixedForceCapacityPlanner(config, fixed_probe_force_n=force,
        sensor_force_error_bound_n=.8, **kwargs)


def test_same_fixed_force_is_used_when_task_load_changes():
    tasks = [replace(CONFIG, forward_progress_m=distance) for distance in (.03, .039)]
    decisions = [decide(fixed(task), proof(12.)) for task in tasks]
    assert all(d.action == 'PROBE' for d in decisions)
    assert decisions[0].minimum_future_load_n < decisions[1].minimum_future_load_n
    assert all(d.requested_probe_load_n == d.achievable_probe_load_n == 47. for d in decisions)
    np.testing.assert_array_equal(decisions[0].body_target_w, decisions[1].body_target_w)
    np.testing.assert_array_equal(decisions[0].allocated_forces_n, decisions[1].allocated_forces_n)
    # The task-conditioned policy uses different commands on those same tasks.
    adaptive = [decide(MinimumSufficientCapacityPlanner(task,
        sensor_force_error_bound_n=.8), proof(12.)) for task in tasks]
    assert all(d.action == 'PROBE' for d in adaptive)
    assert adaptive[0].achievable_probe_load_n < adaptive[1].achievable_probe_load_n


def test_known_under_test_is_performed_then_measured_proof_causes_safe_stop():
    planner = fixed()
    request = decide(planner, proof(12.))
    assert request.action == 'PROBE'
    assert not planner.last_probe_target.predicted_sufficient_for_task
    assert planner.last_probe_target.predicted_usable_force_cap_n == 37.
    # Even ideal measurement of this command leaves less usable capacity
    # than the harder task requires. The fixed policy does not raise its test.
    actual = proof(47.)
    after = decide(planner, actual, allow_additional_probe=False)
    assert after.action == 'SAFE_STOP'
    assert after.usable_force_cap_n == 38.
    assert after.minimum_future_load_n > after.usable_force_cap_n
    assert after.requested_probe_load_n == 0.


def test_same_measured_fixed_test_can_authorize_the_easier_task():
    planner = fixed(replace(CONFIG, forward_progress_m=.03))
    request = decide(planner, proof(12.))
    assert request.action == 'PROBE' and planner.last_probe_target.predicted_sufficient_for_task
    # Worst declared negative force error and expected undershoot still leave
    # enough measured proof here. A command alone is never substituted for it.
    after = decide(planner, proof(47.-.8-.2), allow_additional_probe=False)
    assert after.action == 'EXECUTE'
    assert after.allocated_forces_n[0] <= 37.+1e-8


def test_identical_certificate_produces_the_identical_frozen_future_decision():
    actual = proof(55.)
    baseline = decide(MatchedCapacityPlanner('adaptive_probe', CONFIG), actual)
    policies = [fixed(), MinimumSufficientCapacityPlanner(CONFIG, sensor_force_error_bound_n=.8)]
    assert baseline.action == 'EXECUTE'
    for planner in policies:
        result = decide(planner, actual)
        for field in baseline.__dataclass_fields__:
            np.testing.assert_equal(getattr(result, field), getattr(baseline, field))


def test_no_certificate_is_created_from_the_fixed_request():
    actual = proof(12.)
    request = decide(fixed(), actual)
    assert request.action == 'PROBE' and request.chosen_future_load_n == 0.
    assert request.usable_force_cap_n == actual.force_cap_n == 3.
    assert actual.certified_load_n == 11.
    assert decide(fixed(), actual, allow_additional_probe=False).action == 'SAFE_STOP'


def test_posture_freedom_and_achievability_reserve_are_preserved():
    request = decide(fixed(), proof(12.))
    assert request.action == 'PROBE'
    assert request.fixed_pose_maximum_probe_load_n < 47.
    assert request.maximum_achievable_probe_load_n-2. >= 47.
    assert np.all(np.abs(request.body_target_w[:2]-ORIGIN[:2]) <= .10+1e-9)
    assert request.support_margin_m >= CONFIG.original_tripod_margin_m-1e-9
    assert np.all(request.allocated_forces_n[1:] >= CONFIG.minimum_support_force_n-1e-9)
    np.testing.assert_allclose(ANCHORS[:, :2].T@request.allocated_forces_n,
        WEIGHT*request.body_target_w[:2], atol=1e-8)


def test_fixed_pose_is_preferred_when_it_can_apply_the_exact_fixed_command():
    anchors = np.array([[.29, .15, .02], [.2, -.15, .02], [-.2, .15, .02], [-.2, -.15, .02]])
    origin = np.array([-1/15, -.05, .28])
    config = replace(CONFIG, next_lift_leg=2, minimum_support_force_n=5.)
    result = fixed(config, 22.).decide(proof(12.), anchors, WEIGHT, origin, UPPER)
    assert result.action == 'PROBE' and result.achievable_probe_load_n == 22.
    np.testing.assert_array_equal(result.body_target_w, origin)


def test_unachievable_fixed_command_is_not_silently_clipped_to_another_test():
    result = decide(fixed(force=52.), proof(12.))
    assert result.action == 'SAFE_STOP'
    assert 'exactly' in result.reason
    assert result.achievable_probe_load_n == result.requested_probe_load_n == 0.


def test_fixed_command_is_not_increased_or_offset_by_sensing_allowances():
    planner = fixed()
    result = decide(planner, proof(12.))
    assert planner.last_probe_target.sensor_force_error_bound_n == .8
    assert planner.last_probe_target.probe_undershoot_allowance_n == .2
    assert result.achievable_probe_load_n == 47.
    assert planner.last_probe_target.predicted_certified_load_n == 45.
    assert planner.last_probe_target.commanded_force_is_not_measured_proof


def test_futile_retest_and_exhausted_test_budget_stop():
    # The old certificate is insufficient for this task but already stronger
    # than the fixed command's conservative predicted observation.
    result = decide(fixed(), proof(47.5))
    assert result.action == 'SAFE_STOP' and 'no increase' in result.reason
    result = decide(fixed(), proof(12.), allow_additional_probe=False)
    assert result.action == 'SAFE_STOP'


def test_geometrically_impossible_task_does_not_trigger_pointless_probing():
    result = decide(fixed(), proof(12.), extra_matrix=[[1., 0., 0., 0.]], extra_upper=[30.])
    assert result.action == 'SAFE_STOP' and 'geometrically infeasible' in result.reason


def test_request_budget_remains_shared_and_not_overridden_by_fixed_setting():
    result = decide(fixed(replace(CONFIG, maximum_probe_request_n=45.)), proof(12.))
    assert result.action == 'SAFE_STOP' and 'request limit' in result.reason


def test_invalidated_proof_cannot_authorize_future_motion():
    result = decide(fixed(), replace(proof(55.), valid=False), allow_additional_probe=False)
    assert result.action == 'SAFE_STOP' and result.usable_force_cap_n == 0.


def test_hidden_failure_capacity_is_not_an_input():
    with pytest.raises(TypeError, match='failure_threshold_n'):
        decide(fixed(), proof(12.), failure_threshold_n=47.)


@pytest.mark.parametrize('force', [0., -1., np.nan, np.inf])
def test_nonphysical_fixed_force_is_rejected(force):
    with pytest.raises(ValueError, match='finite and positive'):
        fixed(force=force)


def test_sensor_bound_cannot_exceed_the_same_certificate_reserve():
    planner = FixedForceCapacityPlanner(CONFIG, fixed_probe_force_n=47., sensor_force_error_bound_n=1.1)
    with pytest.raises(ValueError, match='sensing reserve'):
        decide(planner, proof(12.))


@pytest.mark.parametrize('action,phase', [('EXECUTE', 'progress_shift'),
    ('PROBE', 'reprobe_posture'), ('SAFE_STOP', 'safe_stop')])
def test_same_decision_takes_the_frozen_wrapper_transition(monkeypatch, action, phase):
    import primp_project.planning.load_capacity as frozen_planning
    import primp_project.task_probe.control as fixed_control
    decision = CapacityDecision(action, 'matched injected decision', ORIGIN+[.04, .02, 0.],
        np.array([47., 20., 50., 33.]), UPPER, next_lift_leg=1, next_lift_height_m=.03,
        next_hold_s=1., certified_load_n=11., usable_force_cap_n=3.,
        nominal_required_load_n=40., chosen_future_load_n=0., requested_probe_load_n=47.,
        achievable_probe_load_n=47., maximum_achievable_probe_load_n=51.)
    planner = SimpleNamespace(decide=lambda *a, **k: decision, last_probe_target=None)
    monkeypatch.setattr(frozen_planning, 'MatchedCapacityPlanner', lambda *a, **k: planner)
    monkeypatch.setattr(fixed_control, 'FixedForceCapacityPlanner', lambda *a, **k: planner)
    wrappers = []
    for cls in (WeakPadV2Wrapper, FixedForceWrapper):
        w = cls.__new__(cls)
        w.capacity_config=CONFIG; w.strategy='adaptive_probe'; w.anchors=ANCHORS.copy()
        w.certificate_estimator=SimpleNamespace(certificate=proof(12.))
        w.weight=WEIGHT; w.probe_origin_com=ORIGIN.copy(); w.com_target=ORIGIN.copy()
        w.additional_probe_count=0; w.origin=2.; w.decision_history=[]; w.future_plan_active=True
        w.fixed_probe_force_n=47.; w.sensor_force_error_bound_n=.8; w.probe_undershoot_allowance_n=.2
        w.enter=lambda p,t,w=w: setattr(w,'entered',(p,t))
        w._choose_movement(7.)
        wrappers.append(w)
    baseline,new=wrappers
    assert baseline.entered == new.entered == (phase,7.)
    for field in ('required_pad_force_n','movement_feasible','strategy_state',
                  'additional_probe_count','future_plan_active','progress_target',
                  'reprobe_target','reprobe_start','maximum_achievable_probe_force_n'):
        assert hasattr(new,field)==hasattr(baseline,field)
        if hasattr(new,field):np.testing.assert_equal(getattr(new,field),getattr(baseline,field))


def test_both_wrappers_inherit_the_same_frozen_physical_execution():
    for method in ('enter','_configure_capacity_planner','_monitor_certificate',
                   '_start_recovery','_handle_certificate_invalidation','update_phase',
                   'references','compute_actions'):
        assert getattr(FixedForceWrapper,method) is getattr(MinimumSufficientWrapper,method)
        assert getattr(FixedForceWrapper,method) is getattr(WeakPadV2Wrapper,method)
