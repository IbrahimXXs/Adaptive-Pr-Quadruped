"""Read-only independent audit of the predeclared 60-cell V2 evaluation.

Run from any directory with the project's conda Python. Only this validation
folder's JSON output is written; canonical runs, summaries and models are read.
Without --require-complete the report describes the completed subset explicitly.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


PROJECT = next(parent for parent in Path(__file__).resolve().parents
               if (parent/'control/controlled_step.py').is_file())
REPOSITORY = PROJECT.parent
sys.path.insert(0, str(REPOSITORY))
STUDY = Path(__file__).resolve().parent.parent
HASH_FILES = {'signals.npz': 'signals_sha256', 'metadata.json': 'metadata_sha256',
              'pad_summary.json': 'summary_sha256'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def minimum(values):
    array = np.asarray(values)
    return float(array.min()) if array.size else None


def maximum(values):
    array = np.asarray(values)
    return float(array.max()) if array.size else None


def percentiles(values):
    values = np.asarray(values, dtype=float)
    if not values.size:
        return None
    return dict(count=int(values.size), mean=float(values.mean()),
                p50=float(np.percentile(values, 50)), p95=float(np.percentile(values, 95)),
                p99=float(np.percentile(values, 99)), maximum=float(values.max()))


def verify_record_hashes(directory, record):
    actual = {name: digest(directory/name) for name in HASH_FILES}
    return actual, {name: actual[name] == record.get(field) for name, field in HASH_FILES.items()}


def provenance_records(records):
    rows = []
    for record in records:
        directory = Path(record.get('run_directory', record.get('run_dir')))
        actual, checks = verify_record_hashes(directory, record)
        rows.append(dict(run_id=directory.name, passed=all(checks.values()),
                         checks=checks, recording_hashes=actual))
    return rows


def audit_entry(spec, entry, frozen, study):
    # This function performs no analyzer invocation that can regenerate reports.
    from primp_project.analysis.pad import reference_checks

    directory = Path(entry['run_dir'])
    metadata = read_json(directory/'metadata.json')
    summary = read_json(directory/'pad_summary.json')
    with np.load(directory/'signals.npz', allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    time = np.asarray(data['control_time_s'], dtype=float)
    n, dt = len(time), float(metadata['dt_s'])
    phase = data['phase'].astype(str)
    landing = np.isin(phase, ['lower', 'confirm'])
    lower = np.flatnonzero(phase == 'lower')
    reload = np.flatnonzero(phase == 'reload')
    recenter = np.flatnonzero(phase == 'recenter')
    final = phase == 'complete'
    selected = metadata['legs'].index(metadata['selected_leg'])
    contacts = data['contact_measured'].astype(bool)
    force = data['contact_normal_force']
    pad_contact = data['target_pad_contact'].astype(bool)
    pad_force = data['target_pad_normal_force']
    planned = data['contact_planned'].astype(bool)
    mpc = data['mpc_update'].astype(bool)
    planner = data['planner_update'].astype(bool)
    loaded = data['sensor_contact'][:, selected].astype(bool) & (data['sensor_normal_force'][:, selected] >= 2.)
    active = landing & ~loaded
    updates = active & planner
    expected_mpc = np.arange(n) % 5 == 0
    expected_mpc[1:] |= np.any(planned[1:] != planned[:-1], axis=1)
    expected_planner = np.zeros(n, bool)
    due, previous_active = 0, False
    for i, is_active in enumerate(active):
        if is_active and (not previous_active or i >= due):
            expected_planner[i], due = True, i+25
        previous_active = is_active

    # Fifty complete 2-ms sample intervals, stricter than a 49-sample gate.
    debounce_count = round(.1/dt)
    before_reload = np.arange(reload[0]-debounce_count, reload[0]) if len(reload) and reload[0] >= debounce_count else np.array([], int)
    last_reload = np.r_[reload[-round(.2/dt):], recenter[:1]] if len(reload) >= round(.2/dt) and len(recenter) else np.array([], int)
    remaining_keys = ['planner_remaining_time_s', 'optimized_remaining_time_s', 'feasible_remaining_time_s']
    if spec['planner'] != 'matched_predictive':
        remaining_keys += ['model_remaining_time_s', 'raw_model_remaining_time_s']
    recovery_updates = updates & data['planner_recovery_active'].astype(bool)
    prior = data['planner_model_prior_active'].astype(bool)
    fallback = data['planner_fallback_active'].astype(bool)
    # Previous-sample ownership accounts for interrupted interpolation segments.
    accounted = fallback[:-1] & landing[:-1] & landing[1:]
    duration = np.r_[0., np.where(accounted, np.diff(time), 0.)]
    applied_foot = data['feet_desired_w'][:, selected]
    applied_com = data['com_target_w']
    descent = np.r_[0., np.where(accounted, np.maximum(0., -np.diff(applied_foot[:, 2])), 0.)]
    body_travel = np.r_[0., np.where(accounted, np.linalg.norm(np.diff(applied_com, axis=0), axis=1), 0.)]
    fallback_expected = {'fallback_interval_s': duration, 'fallback_foot_descent_m': descent,
                         'fallback_com_travel_m': body_travel}
    raw_hashes, hash_checks = verify_record_hashes(directory, entry)
    model_hashes = {f'model/{name}': value for name, value in metadata.get('model_hashes_sha256', {}).items()}
    model_hashes.update({f'recovery_model/{name}': value for name, value in metadata.get('recovery_model_hashes_sha256', {}).items()})
    snapshots = {str(path.relative_to(directory/'source')): digest(path)
                 for path in sorted((directory/'source').rglob('*.py')) if path.name != 'catalog.py'}
    snapshot_matches = {}
    for name, value in snapshots.items():
        original = (REPOSITORY if name.startswith('quadruped_pympc/') else PROJECT)/name
        snapshot_matches[name] = original.is_file() and digest(original) == value
    ref_checks = reference_checks(metadata, data)
    fixed_keys = ('robot', 'controller', 'dt_s', 'mpc_params', 'simulation_params', 'controller_changes',
                  'reference_limits', 'friction', 'hold_seconds', 'initial_height_estimate_m',
                  'nominal_lower_duration_s', 'contact_debounce_s', 'max_search_depth_m',
                  'contact_compression_m', 'planner_frequency_hz', 'recovery_timeout_s')
    common_settings = {key: metadata[key] for key in fixed_keys}
    sensor_settings = {key: value for key, value in metadata['sensor_profile'].items() if key != 'seed'}
    spec_matches = (entry.get('parameters') == spec and metadata['planner'] == spec['planner']
        and metadata['evaluation']['actual_pad_height_m'] == spec['actual_height_m']
        and metadata['initial_height_estimate_m'] == spec['initial_estimate_m']
        and metadata['seed'] == spec['seed'] and metadata['sensor_profile']['seed'] == spec['seed']
        and metadata['sensor_profile']['name'] == spec['sensor_profile']
        and metadata['initial_condition'] == spec['initial_condition']
        and metadata['requested_lift_height_m'] == (.035 if spec['initial_condition'] == 'raised' else .03)
        and metadata['role'] == spec['role'] and metadata['recovery_demonstration'] is False)
    negative = spec['actual_height_m'] < spec['initial_estimate_m']-.002
    missing = np.flatnonzero(landing & data['missing_contact'].astype(bool))
    touch = np.flatnonzero(landing & pad_contact)
    actual_recovery = (not negative or (len(missing) > 0 and len(touch) > 0 and len(reload) > 0
        and missing[0] < touch[0] and data['feet_pos_w'][touch[0], selected, 2] < data['feet_pos_w'][missing[0], selected, 2]
        and np.all(~planned[missing[0]:reload[0], selected])
        and np.all(contacts[missing[0]:reload[0], 1:]) and np.all(force[missing[0]:reload[0], 1:] > 5.)))
    timing = {key: minimum(data[key][updates]) for key in remaining_keys}
    checks = {
        'completed_record': entry['status'] == 'completed' and metadata['status'] == 'completed',
        'summary_acceptance_matches_state': bool(summary['passed']) == bool(entry['passed']),
        'trial_matches_predeclared_cell': bool(spec_matches),
        'raw_metadata_summary_hashes': all(hash_checks.values()),
        'frozen_source_attestation': entry.get('source_sha256') == frozen.get('source_sha256') == entry.get('actual_source_sha256'),
        'frozen_model_attestation': entry.get('model_files') == frozen.get('model_files') == model_hashes,
        'archived_source_matches_current_frozen_files': bool(snapshots) and all(snapshot_matches.values()),
        'exact_500hz_control_grid': n > 0 and dt == .002 and np.allclose(np.diff(time), dt, atol=1e-9, rtol=0),
        'exact_100hz_mpc_plus_support_transitions': metadata['simulation_params']['mpc_frequency'] == 100 and np.array_equal(mpc, expected_mpc),
        'all_mpc_qps_successful': np.any(mpc) and np.all(data['qp_status'][mpc] == 0),
        'exact_20hz_planner_pause_resume': metadata['planner_frequency_hz'] == 20 and np.any(expected_planner) and np.array_equal(planner, expected_planner),
        'true_pad_loaded_100ms_before_reload': len(before_reload) == debounce_count and np.all(pad_contact[before_reload]) and np.all(pad_force[before_reload] >= 2.),
        'all_feet_loaded_final_200ms_reload': bool(len(last_reload)) and np.all(contacts[last_reload]) and np.all(force[last_reload] > 5.) and np.all(pad_contact[last_reload]) and np.all(pad_force[last_reload] > 5.),
        'all_feet_loaded_through_final_stand': np.any(final) and np.all(contacts[final]) and np.all(force[final] > 5.) and np.all(pad_contact[final]) and np.all(pad_force[final] > 5.),
        'positive_unclipped_remaining_duration': np.any(updates) and all(np.all(np.isfinite(data[key][updates])) and np.all(data[key][updates] > 0.) for key in remaining_keys),
        'current_sensor_foot_anchor': np.any(updates) and np.allclose(data['planner_anchor_foot_w'][updates], data['sensor_foot_pos_w'][updates], atol=1e-12, rtol=0),
        'current_sensor_body_anchor': np.any(updates) and np.allclose(data['planner_anchor_com_w'][updates], data['sensor_com_pos_w'][updates], atol=1e-12, rtol=0),
        'fallback_and_prior_mutually_exclusive': not np.any(fallback & prior),
        'learned_prior_actually_executed': np.any(updates & prior) if spec['planner'] != 'matched_predictive' else not np.any(prior),
        'fallback_intervals_independently_accounted': all(np.allclose(data[key], value, atol=1e-10, rtol=0) for key, value in fallback_expected.items()),
        'fallback_only_while_unsupported_landing': not np.any(fallback & (~landing | loaded)),
        'fallback_reason_present_when_active': np.all(data['planner_fallback_reason'][fallback].astype(str) != ''),
        'recorded_planner_targets_are_applied_references': np.allclose(data['planner_foot_target_w'][landing], applied_foot[landing], atol=1e-12, rtol=0) and np.allclose(data['planner_com_target_w'][landing], applied_com[landing], atol=1e-12, rtol=0),
        'noncontact_ablation_configuration': np.all(data['belief_noncontact_updates_enabled'][landing] == (spec['planner'] != 'matched_no_noncontact_updates')),
        'physical_recovery_after_missing_contact': bool(actual_recovery),
        'shared_reference_checks': all(value['passed'] for value in ref_checks.values()),
    }
    checks = {key: bool(value) for key, value in checks.items()}
    reasons = Counter(data['planner_fallback_reason'][updates & fallback].astype(str).tolist())
    optimizer_failure_count = data['predictive_optimization_failures'].astype(int)
    optimizer_failure_increments = np.r_[optimizer_failure_count[0], np.diff(optimizer_failure_count)]
    failure_ticks = updates & (data['planner_fallback_reason'].astype(str) == 'optimizer_failure')
    checks['optimizer_failure_count_matches_fallback_events'] = bool(
        np.array_equal(optimizer_failure_increments, failure_ticks.astype(int)))
    first = lower[0] if len(lower) else None
    row = dict(trial_id=spec['trial_id'], run_directory=str(directory), planner=spec['planner'],
        actual_height_m=spec['actual_height_m'], seed=spec['seed'], initial_condition=spec['initial_condition'],
        recorded_passed=bool(summary['passed']), audit_passed=all(checks.values()), checks=checks,
        shared_reference_checks=ref_checks, recording_hashes=raw_hashes,
        source_sha256=entry.get('source_sha256'), model_files=model_hashes,
        archived_source_sha256=object_digest(snapshots), archived_source_files=snapshots,
        controller_settings_sha256=object_digest(common_settings), sensor_settings_sha256=object_digest(sensor_settings),
        mpc_updates=int(mpc.sum()), planner_updates=int(planner.sum()),
        mpc_failed_qps=int(np.count_nonzero(data['qp_status'][mpc])),
        reference_optimizer_failures=int(data['predictive_optimization_failures'].max()),
        planner_compute_time_s=percentiles(data['planner_compute_time_s'][planner]),
        mpc_compute_time_s=percentiles(data['solver_time_s'][mpc]),
        planner_over_50ms_updates=int(np.count_nonzero(data['planner_compute_time_s'][planner] > .05)),
        minimum_pre_reload_pad_force_n=minimum(pad_force[before_reload]),
        pre_reload_window_samples=len(before_reload), pre_reload_window_duration_s=len(before_reload)*dt,
        minimum_last_reload_each_foot_force_n=force[last_reload].min(axis=0).tolist() if len(last_reload) else None,
        minimum_final_each_foot_force_n=force[final].min(axis=0).tolist() if np.any(final) else None,
        remaining_time_minima_s=timing, recovery_planning_updates=int(recovery_updates.sum()),
        minimum_raw_recovery_time_s=minimum(data['raw_model_remaining_time_s'][recovery_updates]),
        learned_prior_updates=int(np.count_nonzero(updates & prior)),
        fallback_plan_updates=int(np.count_nonzero(updates & fallback)), fallback_reasons=dict(reasons),
        fallback_integrated_time_s=float(duration.sum()), fallback_integrated_foot_descent_m=float(descent.sum()),
        fallback_integrated_com_travel_m=float(body_travel.sum()),
        fallback_recorded_totals={key: float(data[key].sum()) for key in fallback_expected},
        actual_initial_foot_bottom_m=float(data['feet_pos_w'][first, selected, 2]-metadata['foot_radius_m']) if first is not None else None,
        sensed_initial_foot_bottom_m=float(data['sensor_foot_pos_w'][first, 2]-metadata['foot_radius_m']) if first is not None else None,
        actual_initial_com_w=data['com_pos_w'][first].tolist() if first is not None else None,
        sensed_initial_com_w=data['sensor_com_pos_w'][first].tolist() if first is not None else None)
    return row, data['planner_compute_time_s'][planner], data['solver_time_s'][mpc]


def build_report(study=STUDY):
    from primp_project.experiments.pad_study_v2 import source_fingerprint

    study = Path(study).resolve()
    # Bind the report to the exact bookkeeping snapshot read, even while the
    # parent atomically adds more completed trials during a partial audit.
    state_bytes = (study/'study_state.json').read_bytes()
    state = json.loads(state_bytes)
    state_snapshot_hash = hashlib.sha256(state_bytes).hexdigest()
    manifest = read_json(study/'split_manifest.json')
    freeze_path = study/'execution_freeze.json'
    frozen = read_json(freeze_path) if freeze_path.exists() else {}
    specs = manifest['evaluations']
    variant_names = ('matched_predictive', 'matched_learned', 'matched_no_body_foot_correlation',
                     'matched_no_timing_adaptation', 'matched_no_noncontact_updates')
    expected_cells = {(planner, height, seed, initial) for planner in variant_names
                      for height in (-.006, .006) for seed in (17, 29, 43)
                      for initial in ('nominal', 'raised')}
    declared_cells = {(spec['planner'], spec['actual_height_m'], spec['seed'], spec['initial_condition']) for spec in specs}
    rows, pending, errors = [], [], []
    planner_compute, mpc_compute = [], []
    for spec in specs:
        entry = state['trials'].get(spec['trial_id'], {})
        if entry.get('status') != 'completed':
            pending.append(dict(trial_id=spec['trial_id'], status=entry.get('status', 'not_started'), error=entry.get('error')))
            continue
        try:
            row, planning, mpc = audit_entry(spec, entry, frozen, study)
            rows.append(row)
            planner_compute.extend(planning.tolist())
            mpc_compute.extend(mpc.tolist())
        except Exception as exc:
            errors.append(dict(trial_id=spec['trial_id'], error=f'{type(exc).__name__}: {exc}'))
    model_files = {name: digest(study/name) for name in state['models']['files']}
    inventory = read_json(study/'v1_training_manifest.json')
    old_records = provenance_records(inventory['records'])
    nominal_metadata = read_json(study/'model/model.json')
    recovery_metadata = read_json(study/'recovery_model/recovery.json')
    model_records = provenance_records(nominal_metadata['training_records'])
    recovery_records = provenance_records(recovery_metadata['training_records'])
    demo_records = provenance_records([state['trials'][spec['trial_id']] for spec in manifest['demonstrations']])
    nominal_ids = [record['run_id'] for record in nominal_metadata['training_records']]
    recovery_ids = [record['run_id'] for record in recovery_metadata['training_records']]
    current_source = source_fingerprint()
    pairs = defaultdict(dict)
    for row in rows:
        pairs[(row['planner'], row['actual_height_m'], row['seed'])][row['initial_condition']] = row
    initial_pairs = []
    for (planner, height, seed), pair in sorted(pairs.items()):
        if set(pair) != {'nominal', 'raised'}:
            continue
        nominal, raised = pair['nominal'], pair['raised']
        delta = raised['actual_initial_foot_bottom_m']-nominal['actual_initial_foot_bottom_m']
        initial_pairs.append(dict(planner=planner, actual_height_m=height, seed=seed,
            actual_foot_clearance_difference_m=delta,
            sensed_foot_clearance_difference_m=raised['sensed_initial_foot_bottom_m']-nominal['sensed_initial_foot_bottom_m'],
            raised_clearance_physically_distinct=bool(.003 < delta < .007)))
    common = dict(
        manifest_has_60_distinct_cells=len(specs) == 60 and len({spec['trial_id'] for spec in specs}) == 60,
        manifest_contains_exact_predeclared_cross_product=declared_cells == expected_cells,
        state_manifest_hash=state['split_manifest_sha256'] == digest(study/'split_manifest.json'),
        execution_freeze_present=bool(frozen),
        freeze_manifest_hash=frozen.get('split_manifest_sha256') == digest(study/'split_manifest.json'),
        freeze_v1_training_inventory_hash=frozen.get('v1_training_manifest_sha256') == digest(study/'v1_training_manifest.json'),
        frozen_source_matches_current=frozen.get('source_sha256') == current_source,
        frozen_models_match_files=frozen.get('model_files') == state['models']['files'] == model_files,
        identical_controller_settings=len({row['controller_settings_sha256'] for row in rows}) <= 1,
        identical_sensor_settings_except_seed=len({row['sensor_settings_sha256'] for row in rows}) <= 1,
        identical_archived_runtime_source=len({row['archived_source_sha256'] for row in rows}) <= 1,
        nine_v1_training_recordings_preserved=len(old_records) == 9 and all(row['passed'] for row in old_records),
        nine_v2_recovery_recordings_preserved=len(demo_records) == 9 and all(row['passed'] for row in demo_records),
        eighteen_motion_model_training_records_preserved=len(model_records) == 18 and all(row['passed'] for row in model_records),
        nine_recovery_model_training_records_preserved=len(recovery_records) == 9 and all(row['passed'] for row in recovery_records),
        fitted_training_inventory_matches_state=len(set(nominal_ids)) == 18 and len(set(recovery_ids)) == 9
            and set(nominal_ids) == set(state['models']['motion_training_run_ids'])
            and set(recovery_ids) == set(state['models']['recovery_training_run_ids']),
        evaluation_heights_excluded_from_model_training=all(record['known_height_m'] not in (-.006, .006)
            for record in nominal_metadata['training_records']+recovery_metadata['training_records']),
        no_evaluation_data_in_training=not ({row['run_directory'] for row in rows} & {record['run_directory'] for record in nominal_metadata['training_records']+recovery_metadata['training_records']}),
        completed_initial_condition_pairs_physically_distinct=all(row['raised_clearance_physically_distinct'] for row in initial_pairs),
        no_audit_errors=not errors)
    all_complete = len(rows) == 60 and not pending and not errors
    available_passed = all(common.values()) and all(row['audit_passed'] for row in rows)
    grouped = {}
    for planner in sorted({spec['planner'] for spec in specs}):
        group = [row for row in rows if row['planner'] == planner]
        grouped[planner] = dict(completed=len(group), recorded_passes=sum(row['recorded_passed'] for row in group),
            audit_passes=sum(row['audit_passed'] for row in group),
            planner_updates=sum(row['planner_updates'] for row in group),
            learned_prior_updates=sum(row['learned_prior_updates'] for row in group),
            fallback_updates=sum(row['fallback_plan_updates'] for row in group),
            fallback_duration_s=sum(row['fallback_integrated_time_s'] for row in group),
            fallback_foot_descent_m=sum(row['fallback_integrated_foot_descent_m'] for row in group),
            fallback_com_travel_m=sum(row['fallback_integrated_com_travel_m'] for row in group),
            optimizer_failures=sum(row['reference_optimizer_failures'] for row in group),
            mpc_failed_qps=sum(row['mpc_failed_qps'] for row in group),
            planner_over_50ms_updates=sum(row['planner_over_50ms_updates'] for row in group))
    return dict(version=2, created_at=datetime.now(timezone.utc).isoformat(),
        audit='Independent raw-signal audit; shared reference_checks is pure; no canonical files are rewritten',
        status='complete' if all_complete else 'partial', all_60_complete=all_complete,
        passed=all_complete and available_passed, available_checks_passed=available_passed,
        expected_trials=60, completed_trials=len(rows), recorded_passes=sum(row['recorded_passed'] for row in rows),
        audit_passes=sum(row['audit_passed'] for row in rows), common_checks=common,
        bookkeeping_hashes={'study_state.json': state_snapshot_hash,
            **{name: digest(study/name) for name in ('split_manifest.json', 'v1_training_manifest.json')}},
        state_changed_during_audit=digest(study/'study_state.json') != state_snapshot_hash,
        freeze_sha256=digest(freeze_path) if frozen else None, frozen_source_sha256=frozen.get('source_sha256'),
        current_source_sha256=current_source, model_files=model_files,
        planner_compute_time_s=percentiles(planner_compute), mpc_compute_time_s=percentiles(mpc_compute),
        minimum_true_pre_reload_force_n=minimum([row['minimum_pre_reload_pad_force_n'] for row in rows if row['minimum_pre_reload_pad_force_n'] is not None]),
        minimum_final_foot_force_n=minimum([force for row in rows for force in row['minimum_final_each_foot_force_n'] or []]),
        paired_initial_conditions=initial_pairs, grouped=grouped, pending=pending, errors=errors,
        training_provenance=dict(v1_inventory=old_records, v2_demonstrations=demo_records,
                                 nominal_model=model_records, recovery_model=recovery_records), trials=rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-dir', type=Path, default=STUDY)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('execution_audit.json'))
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args(argv)
    # Outputs are deliberately restricted to the owned validation directory.
    output = args.output.resolve()
    if output.parent != Path(__file__).resolve().parent or output.suffix != '.json':
        parser.error('Audit output must be a JSON file in this validation directory')
    report = build_report(args.study_dir)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: report[key] for key in ('status', 'all_60_complete', 'completed_trials',
        'recorded_passes', 'audit_passes', 'available_checks_passed', 'passed', 'common_checks', 'errors')}, indent=2))
    return int((args.require_complete and not report['all_60_complete']) or not report['available_checks_passed'])


if __name__ == '__main__':
    raise SystemExit(main())
