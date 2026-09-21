"""Reject expired recovery clocks and misattributed fallback independently."""
import numpy as np
import pytest
from primp_project.analysis.adaptation import adaptation_checks


def evidence():
    n = 8
    metadata = dict(validation_version=2, planner='matched_learned', foot_radius_m=.022)
    foot = np.zeros((n, 3))
    foot[:, 2] = .022-np.arange(n)*.0001
    data = dict(control_time_s=np.arange(n)*.02, phase=np.array(['lower']*n),
                sensor_contact=np.zeros((n, 4), dtype=bool), sensor_normal_force=np.zeros((n, 4)),
                planner_update=np.ones(n, dtype=bool), planner_remaining_time_s=np.ones(n),
                model_remaining_time_s=np.ones(n), optimized_remaining_time_s=np.ones(n),
                feasible_remaining_time_s=np.ones(n), sensor_com_pos_w=np.zeros((n, 3)),
                raw_model_remaining_time_s=np.ones(n), planner_anchor_foot_w=foot.copy(),
                planner_anchor_com_w=np.zeros((n, 3)),
                sensor_body_rpy=np.zeros((n, 3)), sensor_foot_vel_w=np.zeros((n, 3)),
                sensor_foot_pos_w=foot.copy(), planner_foot_target_w=foot,
                planner_com_target_w=np.zeros((n, 3)), missing_contact=np.ones(n, dtype=bool),
                planner_fallback_active=np.array([0, 1, 1, 0, 0, 1, 0, 0], dtype=bool),
                planner_fallback_reason=np.array(['']*n),
                belief_noncontact_updates_enabled=np.ones(n, dtype=bool))
    owned = np.r_[False, data['planner_fallback_active'][:-1]]
    data['planner_model_prior_active'] = ~data['planner_fallback_active']
    data['planner_recovery_active'] = np.ones(n, dtype=bool)
    data.update(fallback_interval_s=owned*.02, fallback_foot_descent_m=owned*.0001,
                fallback_com_travel_m=np.zeros(n))
    return metadata, data


def test_fallback_work_uses_executed_intervals_not_update_count():
    checks, metrics = adaptation_checks(*evidence())
    assert all(c['passed'] for c in checks.values())
    assert metrics['fallback_active_time_s'] == pytest.approx(.06)
    assert metrics['fallback_commanded_foot_descent_m'] == pytest.approx(.0003)


@pytest.mark.parametrize('key', ['planner_remaining_time_s', 'model_remaining_time_s',
                               'optimized_remaining_time_s', 'feasible_remaining_time_s', 'raw_model_remaining_time_s'])
@pytest.mark.parametrize('bad', [0., -1., np.nan])
def test_expired_or_invalid_missed_contact_clock_is_rejected(key, bad):
    metadata, data = evidence()
    data[key][3] = bad
    checks, _ = adaptation_checks(metadata, data)
    assert not checks['pad_positive_remaining_duration']['passed']


@pytest.mark.parametrize('key', ['fallback_interval_s', 'fallback_foot_descent_m', 'fallback_com_travel_m'])
def test_falsified_fallback_contribution_is_rejected(key):
    metadata, data = evidence()
    data[key][4] += .1
    checks, _ = adaptation_checks(metadata, data)
    assert not checks['pad_fallback_work_accounting']['passed']


def test_missing_instrumentation_is_failure_and_legacy_contract_is_preserved():
    metadata, data = evidence()
    del data['fallback_interval_s']
    assert not adaptation_checks(metadata, data)[0]['pad_adaptation_signals']['passed']
    assert adaptation_checks(dict(validation_version=1), {}) == ({}, {})


def test_noncontact_ablation_must_match_recorded_configuration():
    metadata, data = evidence()
    metadata['planner'] = 'matched_no_noncontact_updates'
    assert not adaptation_checks(metadata, data)[0]['pad_noncontact_ablation_configuration']['passed']
    data['belief_noncontact_updates_enabled'][:] = False
    assert adaptation_checks(metadata, data)[0]['pad_noncontact_ablation_configuration']['passed']


def test_stale_measured_state_anchor_is_rejected():
    metadata, data = evidence()
    data['planner_anchor_foot_w'][3, 2] += .001
    assert not adaptation_checks(metadata, data)[0]['pad_current_state_replanning']['passed']


def test_mixed_fallback_and_learned_attribution_is_rejected():
    metadata, data = evidence()
    data['planner_model_prior_active'][1] = True
    assert not adaptation_checks(metadata, data)[0]['pad_fallback_prior_exclusion']['passed']


def test_learned_label_with_no_actual_prior_use_is_rejected():
    metadata, data = evidence()
    data['planner_model_prior_active'][:] = False
    assert not adaptation_checks(metadata, data)[0]['pad_prior_execution']['passed']
