"""Independent V2 timing and fallback accounting from applied references."""
import numpy as np


def adaptation_checks(metadata, data):
    """Return checks and metrics; preserve the historical V1 validation contract."""
    if int(metadata.get('validation_version', 1)) < 2:
        return {}, {}
    required = ('planner_fallback_active', 'planner_fallback_reason', 'fallback_interval_s',
                'fallback_foot_descent_m', 'fallback_com_travel_m', 'model_remaining_time_s',
                'optimized_remaining_time_s', 'feasible_remaining_time_s', 'sensor_com_pos_w',
                'sensor_body_rpy', 'sensor_foot_vel_w', 'belief_noncontact_updates_enabled',
                'raw_model_remaining_time_s', 'planner_anchor_foot_w', 'planner_anchor_com_w')
    missing = sorted(set(required)-data.keys())
    checks = {}

    def check(name, passed, requirement, observed):
        checks['pad_'+name] = dict(passed=bool(passed), requirement=requirement, observed=observed)

    check('adaptation_signals', not missing, 'V2 records timing, measured state and applied fallback contributions', missing)
    if missing:
        return checks, {}
    t = np.asarray(data['control_time_s'], dtype=float)
    n = len(t)
    aligned = all(len(data[k]) == n for k in required)
    check('adaptation_alignment', aligned, 'V2 adaptation signals have one entry per control sample', None)
    if not aligned:
        return checks, {}
    landing = np.isin(data['phase'].astype(str), ['lower', 'confirm'])
    loaded = data['sensor_contact'][:, 0].astype(bool) & (data['sensor_normal_force'][:, 0] >= 2.)
    active = landing & ~loaded
    updates = active & data['planner_update'].astype(bool)
    timing_keys = ['planner_remaining_time_s', 'optimized_remaining_time_s', 'feasible_remaining_time_s']
    if metadata['planner'] != 'matched_predictive':
        timing_keys += ['model_remaining_time_s', 'raw_model_remaining_time_s']
    finite = all(np.all(np.isfinite(data[k])) for k in required if k != 'planner_fallback_reason')
    positive = np.any(updates) and all(np.all(data[k][updates] > 0.) for k in timing_keys)
    check('positive_remaining_duration', finite and positive,
          'Every unsupported planning update replans finite, strictly positive remaining time, including learned time',
          {k: float(np.min(data[k][updates])) if np.any(updates) else None for k in timing_keys})
    current_state = (np.any(updates) and
                     np.allclose(data['planner_anchor_foot_w'][updates], data['sensor_foot_pos_w'][updates], atol=1e-12, rtol=0) and
                     np.allclose(data['planner_anchor_com_w'][updates], data['sensor_com_pos_w'][updates], atol=1e-12, rtol=0))
    check('current_state_replanning', current_state,
          'Every active planning tick uses the contemporaneous allowed measured body and foot state', None)
    flags = data['planner_fallback_active'].astype(bool)
    accounted = np.r_[False, flags[:-1] & landing[:-1] & landing[1:]]
    interval = np.r_[0., np.diff(t)]
    foot = data['planner_foot_target_w']
    com = data['planner_com_target_w']
    expected_time = np.where(accounted, interval, 0.)
    expected_descent = np.where(accounted, np.r_[0., np.maximum(0., -np.diff(foot[:, 2]))], 0.)
    expected_body = np.where(accounted, np.r_[0., np.linalg.norm(np.diff(com, axis=0), axis=1)], 0.)
    correct = (not np.any(flags & (~landing | loaded)) and
               np.allclose(data['fallback_interval_s'], expected_time, atol=1e-10, rtol=0) and
               np.allclose(data['fallback_foot_descent_m'], expected_descent, atol=1e-10, rtol=0) and
               np.allclose(data['fallback_com_travel_m'], expected_body, atol=1e-10, rtol=0))
    check('fallback_work_accounting', correct,
          'Fallback contribution equals independently integrated applied reference intervals, including interrupted segments',
          dict(active_time_s=float(expected_time.sum()), foot_descent_m=float(expected_descent.sum()),
               com_travel_m=float(expected_body.sum())))
    ablation = metadata['planner'] == 'matched_no_noncontact_updates'
    check('noncontact_ablation_configuration', np.all(data['belief_noncontact_updates_enabled'][landing] == (not ablation)),
          'Only the no-noncontact-update ablation disables censored belief updates', bool(ablation))
    metrics = dict(fallback_active_time_s=float(expected_time.sum()),
                   fallback_commanded_foot_descent_m=float(expected_descent.sum()),
                   fallback_commanded_com_travel_m=float(expected_body.sum()),
                   fallback_active_plan_count=int(np.count_nonzero(flags & updates)),
                   minimum_unsupported_remaining_time_s=float(np.min(data['planner_remaining_time_s'][updates])) if np.any(updates) else None,
                   missing_contact_planning_updates=int(np.count_nonzero(updates & data['missing_contact'].astype(bool))))
    rows = np.flatnonzero(landing)
    if len(rows):
        metrics['lowering_initial_measured_foot_bottom_m'] = float(data['sensor_foot_pos_w'][rows[0], 2]-metadata['foot_radius_m'])
        metrics['lowering_initial_measured_com_w'] = data['sensor_com_pos_w'][rows[0]].tolist()
    return checks, metrics
