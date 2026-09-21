"""Independently audit the matched probe-efficiency recordings without control.

The preserved independent V2 audit supplies geometry and certificate-history
checks, not the production analyzer. New checks reconstruct task-load bounds,
target arithmetic, hidden-pad failure, task completion, and matched prefixes.
Nothing in the canonical recordings or frozen V2 study is rewritten.
"""
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


STUDY = Path(__file__).resolve().parent.parent
PROJECT = STUDY.parents[2]
ROOT = PROJECT.parent
LEGACY = PROJECT / 'results/weak_pad/study_v2/validation'
MOVEMENT = ('progress_shift', 'next_unload', 'next_lift', 'progress_hold', 'progress_complete')
PROBE = ('probe_ramp', 'probe_hold', 'probe_release', 'reprobe_posture')
RECOVERY = ('recovery_unload', 'recovery_lift', 'recovery_hold')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_module(name):
    spec = importlib.util.spec_from_file_location('independent_' + name, LEGACY / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_trial(spec, entry, frozen, physics, geometry):
    run = Path(entry['run_dir'])
    metadata = json.loads((run / 'metadata.json').read_text())
    summary = json.loads((run / 'probe_efficiency_summary.json').read_text())
    with np.load(run / 'signals.npz', allow_pickle=False) as archive:
        d = {name: archive[name] for name in archive.files}
    failed_checks = []

    def check(name, passed):
        if not passed:
            failed_checks.append(name)

    for key, name in [('signals_sha256', 'signals.npz'), ('metadata_sha256', 'metadata.json'),
                      ('summary_sha256', 'probe_efficiency_summary.json'),
                      ('baseline_summary_sha256', 'weak_pad_summary.json')]:
        check('immutable_' + name, entry.get(key) == sha(run / name))
    check('execution_source_frozen', entry.get('source_sha256') == frozen['source']['sha256'])
    expected = dict(spec['parameters'], strategy='adaptive_probe', probe_policy=spec['probe_policy'], seed=spec['seed'], role=spec.get('role', 'evaluation'))
    threshold = expected.pop('failure_threshold_n')
    check('declared_public_inputs', expected == metadata['trial_parameters'])
    check('truth_not_public', 'failure_threshold_n' not in metadata['trial_parameters'])
    evaluation = metadata['evaluation']
    check('declared_hidden_capacity', threshold == evaluation.get('failure_threshold_n', evaluation.get('failure_load_n')))

    t = d['control_time_s']; dt = float(metadata['dt_s']); n = len(t)
    phase = d['phase'].astype(str); normal = d['contact_normal_force']
    contacts = d['contact_measured'].astype(bool); valid = d['certificate_valid'].astype(bool)
    actual = d['actual_pad_normal_force_n']; certificate = d['certificate_force_n']
    cap = d['applied_pad_force_cap_n']; reserve = d['tracking_reserve_n']
    check('uniform_control_clock', np.allclose(np.diff(t), dt, atol=1e-8, rtol=0.))
    check('sensor_clock', np.allclose(d['sensor_observation_time_s'], t, atol=1e-8, rtol=0.))
    period = round(1 / (metadata['simulation_params']['mpc_frequency'] * dt))
    check('periodic_mpc', np.all(d['mpc_update'][::period]))
    change = np.r_[False, np.any(d['contact_planned'][1:] != d['contact_planned'][:-1], axis=1)]
    check('contact_transition_mpc', np.all(d['mpc_update'][change]))
    check('successful_qp', not np.any(d['qp_status'][d['mpc_update'].astype(bool)]))
    sensing = metadata['sensor_config']
    error = d['sensor_pad_normal_force_n'][1:] - np.maximum(0., normal[:-1, 0] + sensing['force_bias_n'])
    check('bounded_force_observations', np.max(np.abs(error)) <= sensing['force_noise_n'] + 1e-8)
    check('bounded_position_observations', np.max(np.abs(d['sensor_pad_foot_pos_w'][1:] - d['feet_pos_w'][:-1, 0]))
          <= sensing['position_noise_m'] + 1e-8)
    first_valid = np.flatnonzero(valid)
    if len(first_valid):
        check('continuous_certificate_monitoring', np.all(d['certificate_monitor_update'][first_valid[0]:]))
        lost = np.flatnonzero(valid[:-1] & ~valid[1:]) + 1
        if len(lost) and not np.any(d['certificate_reset'][lost[0]:]):
            check('no_implicit_certificate_revival', not np.any(valid[lost[0]:]))
    certificate_audit = physics.certificate_history(d, metadata)
    check('independent_certificate_evidence', certificate_audit['verified'])
    qualifying_proofs = True
    for end in np.unique(d['probe_evidence_end_time_s'][valid]):
        row = int(np.flatnonzero(valid & (d['probe_evidence_end_time_s'] == end))[0])
        start = d['probe_evidence_start_time_s'][row]
        evidence_rows = (t >= start-1e-8) & (t <= end+1e-8)
        qualifying_proofs &= (np.all(d['certificate_observation_phase'][evidence_rows] == 'probe_hold')
            and np.all(d['certificate_allow_increase'][evidence_rows]))
    check('every_demonstration_sample_is_a_qualifying_hold', qualifying_proofs)

    # Reconstruct the hidden failure latch strictly from physical load and dwell.
    overloaded = np.flatnonzero(d['force_before_deformation_n'] > threshold)
    groups = np.split(overloaded, np.flatnonzero(np.diff(overloaded) != 1) + 1)
    needed = int(np.ceil(evaluation['overload_dwell_s'] / dt - 1e-10))
    triggering = [group for group in groups if len(group) >= needed]
    failure_index = int(triggering[0][needed - 1]) if triggering else None
    failed = np.zeros(n, bool)
    sink = np.zeros(n)
    if failure_index is not None:
        failed[failure_index:] = True
        sink[failure_index:] = np.minimum(evaluation['sink_depth_m'],
            evaluation['sink_speed_m_s'] * (t[failure_index:] - t[failure_index]))
    check('load_threshold_and_dwell_caused_damage', np.array_equal(failed, d['pad_failed'].astype(bool)))
    check('physical_pad_displacement', np.allclose(sink, d['pad_sink_displacement_m'], atol=1e-8, rtol=0.))

    probe = np.isin(phase, PROBE); movement = np.isin(phase, MOVEMENT)
    deliberate = np.isin(phase, ('probe_ramp', 'probe_hold'))
    recovery = np.isin(phase, RECOVERY)
    tilt = np.rad2deg(np.max(np.abs(d['base_rpy_rad'][:, :2]), axis=1))
    tripod = (np.all(contacts[:, 1:] & (normal[:, 1:] >= 5.), axis=1)
        & (physics.triangle_margin(d['com_pos_w'], d['feet_pos_w'][:, 1:]) >= .005) & (tilt <= 8.))
    check('available_original_tripod_through_testing_recovery', np.all(tripod[probe | recovery]))
    check('no_future_execution_after_pad_failure', not np.any(movement & failed))
    check('future_movement_requires_valid_certificate', np.all(valid[movement]))
    certified = (movement | (phase == 'safe_stop')) & valid
    check('future_actual_force_within_demonstrated_bound', np.all(actual[certified] <= certificate[certified] + 1e-6))
    check('future_caps_retain_tracking_reserve', np.all(cap[certified] <= np.maximum(0., certificate[certified] - reserve[certified]) + 1e-6))
    check('desired_future_force_within_installed_cap', np.all(d['grf_desired_w'][certified,0,2]
          <= cap[certified] + metadata['force_tolerance_n']))
    posture = phase == 'reprobe_posture'
    check('reposition_preserves_existing_proof', np.all(valid[posture]) and
          np.all(actual[posture] <= certificate[posture] + 1e-6))

    first_probe = int(np.flatnonzero(phase == 'probe_ramp')[0])
    anchors = d['feet_desired_w'][first_probe]
    origin = d['probe_origin_com_w'][first_probe]
    weight = metadata['model_mass_kg'] * metadata['gravity_m_s2']
    minimum = geometry.equilibrium_problem(anchors, weight, origin,
        metadata['movement_optimizer_settings'], mode='future')
    check('independent_future_feasibility', minimum['feasible'])
    minimum_force = minimum.get('weak_force_n', 0.)
    history = metadata['capacity_decision_history']
    check('logged_future_lower_bound', bool(history) and abs(history[0]['minimum_future_load_n'] - minimum_force) < 1e-7)
    additional = d['additional_probe_count'] > 0
    target_rows = additional & deliberate
    selected_target = float(np.median(d['achieved_probe_command_n'][target_rows])) if np.any(target_rows) else None
    tolerance = float(d['target_tolerance_n'][np.flatnonzero(additional)[0]]) if np.any(additional) else .001
    measured_target = minimum_force + metadata['sensor_force_reserve_n'] + metadata['tracking_reserve_n'] + tolerance
    allowance = metadata['sensor_force_error_bound_n'] + metadata['trial_parameters']['probe_undershoot_allowance_n']
    if spec['probe_policy'] == 'minimum_sufficient' and np.any(target_rows):
        check('minimum_measured_target_formula', np.allclose(d['minimum_sufficient_probe_load_n'][target_rows], measured_target, atol=1e-7, rtol=0.))
        check('command_has_only_declared_allowance', np.allclose(d['achieved_probe_command_n'][target_rows], measured_target + allowance, atol=1e-7, rtol=0.))

    next_leg = int(metadata['next_leg_index'])
    progress = d['com_pos_w'][:, 0] - origin[0]
    clearance = d['feet_pos_w'][:, next_leg, 2] - d['next_lift_anchor_w'][:, 2]
    others = [i for i in range(4) if i != next_leg]
    simultaneous = (movement & (progress >= .03 - 1e-6) & (clearance >= .02 - 1e-6)
        & ~contacts[:, next_leg] & np.all(contacts[:, others] & (normal[:, others] >= 2.), axis=1)
        & valid & ~failed)
    success_duration, _ = physics.longest(simultaneous, dt)
    outcome = summary['outcome']
    if outcome == 'SUCCESS':
        check('physical_task_completed', success_duration >= 1. - 1e-8 and failure_index is None)
        check('terminal_success', bool(d['task_complete_declared'][-1]))
    recovery_hold = 0.
    if outcome == 'RECOVERED_STOP':
        check('damage_triggered_during_testing', failure_index is not None and probe[failure_index])
        check('controlled_recovery_present', np.any(recovery))
        if np.any(recovery):
            first_recovery = np.flatnonzero(recovery)[0]
            anchor = d['feet_pos_w'][first_recovery, 0, 2]
            recovered = (recovery & tripod & ~contacts[:, 0] & (normal[:, 0] < 2.) & (actual < 2.)
                & (d['feet_pos_w'][:, 0, 2] - anchor >= .025 - 1e-6))
            recovery_hold, _ = physics.longest(recovered, dt)
            tail = t >= t[-1] - 2. + dt - 1e-8
            check('terminal_stable_recovery', np.all(recovered[tail]) and recovery_hold >= 2.)
        check('recovery_not_task_completion', bool(d['recovered_stop_declared'][-1]) and not np.any(d['task_complete_declared']))
    if outcome == 'SAFE_STOP':
        final = t >= t[-1] - .5
        check('intact_safe_stop', failure_index is None and np.all(tripod[final]) and not np.any(d['task_complete_declared']))

    transition = np.isin(phase, ('probe_release', 'reprobe_posture')) & valid
    return dict(trial_id=spec['trial_id'], case_id=spec['case_id'], seed=spec['seed'],
        probe_policy=spec['probe_policy'], outcome=outcome, verified=not failed_checks,
        failed_checks=failed_checks, hidden_capacity_n=threshold,
        minimum_future_load_n=minimum_force, required_minimum_sensor_plateau_n=measured_target,
        selected_additional_command_n=selected_target, declared_execution_allowance_n=allowance,
        maximum_actual_probe_force_n=float(actual[probe].max()), pad_damaged=failure_index is not None,
        failure_time_s=float(t[failure_index]) if failure_index is not None else None,
        failure_phase=str(phase[failure_index]) if failure_index is not None else None,
        probe_time_s=float(probe.sum()*dt), active_ramp_hold_time_s=float(deliberate.sum()*dt),
        physical_progress_hold_s=success_duration, recovery_stable_hold_s=recovery_hold,
        future_maximum_actual_minus_cap_n=float(np.max(actual[certified] - cap[certified])) if np.any(certified) else None,
        transition_maximum_actual_minus_cap_n=float(np.max(actual[transition] - cap[transition])) if np.any(transition) else None,
        certificate_history=certificate_audit,
        source_data_hashes={name: sha(run/name) for name in ('metadata.json', 'signals.npz', 'probe_efficiency_summary.json')})


def build():
    manifest = json.loads((STUDY/'split_manifest.json').read_text())
    state = json.loads((STUDY/'study_state.json').read_text())
    frozen = json.loads((STUDY/'execution_freeze.json').read_text())
    physics = read_module('audit_execution'); geometry = read_module('audit_necessity')
    source_verified = all(sha(ROOT/name) == digest for name, digest in frozen['source']['files'].items())
    rows = [audit_trial(spec, state['trials'][spec['trial_id']], frozen, physics, geometry)
        for spec in manifest['trials'] if state['trials'].get(spec['trial_id'], {}).get('status') == 'completed']
    prefixes = physics.compare_common_prefix(manifest, state)
    grouped = defaultdict(dict)
    for row in rows:
        grouped[(row['case_id'], row['seed'])][row['probe_policy']] = row
    pairs = []
    for (case, seed), pair in grouped.items():
        if set(pair) != {'maximum_feasible', 'minimum_sufficient'}:
            continue
        larger, smaller = pair['maximum_feasible'], pair['minimum_sufficient']
        pairs.append(dict(case_id=case, seed=seed, hidden_capacity_n=larger['hidden_capacity_n'],
            maximum_outcome=larger['outcome'], minimum_outcome=smaller['outcome'],
            avoided_damage_with_completed_task=(larger['pad_damaged'] and smaller['outcome'] == 'SUCCESS' and not smaller['pad_damaged']),
            both_completed_intact=(larger['outcome'] == smaller['outcome'] == 'SUCCESS' and not larger['pad_damaged'] and not smaller['pad_damaged']),
            minimum_minus_maximum_probe_time_s=smaller['probe_time_s']-larger['probe_time_s'],
            minimum_minus_maximum_peak_probe_force_n=smaller['maximum_actual_probe_force_n']-larger['maximum_actual_probe_force_n']))
    by_policy = {policy: dict(outcomes=dict(Counter(row['outcome'] for row in rows if row['probe_policy'] == policy)),
        damaged_pads=sum(row['pad_damaged'] for row in rows if row['probe_policy'] == policy))
        for policy in ('maximum_feasible', 'minimum_sufficient')}
    return dict(expected_trials=len(manifest['trials']), completed_trials=len(rows),
        complete=len(rows) == len(manifest['trials']), frozen_source_verified=source_verified,
        verified=source_verified and all(row['verified'] for row in rows) and all(row['verified'] for row in prefixes),
        study_manifest_sha256=sha(STUDY/'split_manifest.json'), execution_freeze_sha256=sha(STUDY/'execution_freeze.json'),
        independent_audit_source_sha256=sha(__file__), by_policy=by_policy,
        independent_helper_sha256={name:sha(LEGACY/name) for name in ('audit_execution.py','audit_necessity.py')},
        avoided_damage_pairs_with_completed_task=sum(pair['avoided_damage_with_completed_task'] for pair in pairs),
        matched_prefixes=prefixes, paired_outcomes=pairs, trials=rows,
        limitations=['Task-specific simulator evidence; no general tracking guarantee.',
            'All physical samples within one trial are correlated; the seed is the declared repeat unit.',
            'Probe time on a damaged, early-terminated attempt is not a faster successful test.',
            'The four preserved weak-pad V2 failures remain below even the relaxed movement load.'])


if __name__ == '__main__':
    report = build()
    (STUDY/'validation/independent_execution_audit.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key:report[key] for key in ('complete','completed_trials','verified','by_policy','avoided_damage_pairs_with_completed_task')}))
