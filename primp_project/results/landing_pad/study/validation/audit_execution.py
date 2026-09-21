"""Read-only independent audit of completed frozen landing-pad evaluations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import numpy as np


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent/'control/controlled_step.py').is_file())
PRIMARY_STATE = ROOT/'results/landing_pad/study/study_state.json'
HELDOUT_STATE = ROOT/'results/landing_pad/study/held_out_heights/study_state.json'
OUT = ROOT/'artifacts/validation/landing_pad/final_execution_audit.json'
VERSIONED = ROOT/'results/landing_pad/study/validation'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit_entry(key, entry):
    p = Path(entry['run_dir'])
    m = json.loads((p/'metadata.json').read_text())
    with np.load(p/'signals.npz', allow_pickle=False) as archive:
        s = {name: archive[name] for name in archive.files}
    dt, n = float(m['dt_s']), len(s['time_s'])
    phase = s['phase'].astype(str)
    reload = int(np.flatnonzero(phase == 'reload')[0])
    window = slice(reload-round(.1/dt), reload)
    final = phase == 'complete'
    planned = s['contact_planned'].astype(bool)
    expected_mpc = np.arange(n) % 5 == 0
    expected_mpc[1:] |= np.any(planned[1:] != planned[:-1], axis=1)
    motion = np.isin(phase, ['lower', 'confirm'])
    active = motion & ~(s['sensor_contact'][:, 0].astype(bool) & (s['sensor_normal_force'][:, 0] >= 2.))
    expected_planner = np.zeros(n, bool)
    next_update, previous_active = 0, False
    for i, is_active in enumerate(active):
        if is_active and (not previous_active or i >= next_update):
            expected_planner[i] = True
            next_update = i+25
        previous_active = is_active
    valid_intervals = motion[:-1] & motion[1:]
    elapsed = np.diff(s['control_time_s'])
    foot_velocity = np.diff(s['feet_desired_w'][:, 0], axis=0)/elapsed[:, None]
    body_velocity = np.diff(s['com_target_w'], axis=0)/elapsed[:, None]
    foot_speed, body_speed = np.linalg.norm(foot_velocity, axis=1), np.linalg.norm(body_velocity, axis=1)
    last_planner = np.maximum.accumulate(np.where(s['planner_update'], np.arange(n), -1))
    previous = np.maximum(last_planner, 0)
    slow = ((s['sensor_foot_pos_w'][previous, 2]-m['foot_radius_m'] <= m['initial_height_estimate_m']+.0005)
            & ~s['sensor_contact'][previous, 0].astype(bool) & (last_planner >= 0))
    recovery_intervals = valid_intervals & slow[:-1]
    delayed = m['sensor_profile']['name'] == 'noisy_delayed'
    first_touch = np.flatnonzero(motion & s['target_pad_contact'].astype(bool))
    missing = np.flatnonzero(motion & s['missing_contact'].astype(bool))
    lower_pad = m['evaluation']['actual_pad_height_m'] < m['initial_height_estimate_m']-.002
    actual_recovery = (not lower_pad or (len(missing) > 0 and len(first_touch) > 0
        and missing[0] < first_touch[0] and s['feet_pos_w'][first_touch[0], 0, 2] < s['feet_pos_w'][missing[0], 0, 2]
        and np.all(planned[missing[0]:reload, 0] == 0)
        and np.all(s['contact_measured'][missing[0]:reload, 1:])
        and np.all(s['contact_normal_force'][missing[0]:reload, 1:] > 5.)))
    files = {'signals.npz': 'signals_sha256', 'metadata.json': 'metadata_sha256', 'pad_summary.json': 'summary_sha256'}
    integrity = {name: digest(p/name) == entry[field] for name, field in files.items()}
    model_hashes = m.get('model_hashes_sha256', {})
    model_integrity = all(digest(Path(m['model_path'])/name) == expected for name, expected in model_hashes.items())
    checks = {
        'completed': entry['status'] == 'completed' and m['status'] == 'completed',
        'true_contact_continuous_100ms_before_reload': bool(np.all(s['target_pad_contact'][window]) and np.all(s['target_pad_normal_force'][window] >= 2.)),
        'all_four_feet_loaded_over_5n_through_final_stand': bool(np.any(final) and np.all(s['contact_measured'][final]) and np.all(s['contact_normal_force'][final] > 5.)),
        'exact_100hz_mpc_plus_support_transitions': bool(dt == .002 and m['simulation_params']['mpc_frequency'] == 100 and np.array_equal(s['mpc_update'], expected_mpc)),
        'all_mpc_qps_successful': bool(np.all(s['qp_status'][s['mpc_update'].astype(bool)] == 0)),
        'exact_20hz_planning_plus_contact_pause_resume': bool(m['planner_frequency_hz'] == 20 and np.array_equal(s['planner_update'], expected_planner)),
        'nominal_foot_speed_bound': bool(np.all(foot_speed[valid_intervals] <= .015+1e-7)),
        'body_speed_bound': bool(np.all(body_speed[valid_intervals] <= .008+1e-7)),
        'bounded_slow_recovery_speed': bool(np.all(foot_speed[recovery_intervals] <= .005+1e-7)),
        'monotone_applied_lowering': bool(np.all(foot_velocity[valid_intervals, 2] <= 1e-7)),
        'physical_recovery_after_missing_contact': bool(actual_recovery),
        'recording_hash_integrity': all(integrity.values()),
        'learned_model_file_integrity': bool(model_integrity and (m['planner'] != 'learned' or model_hashes.get('model.npz') == entry['model_sha256'])),
    }
    settings = {name: m[name] for name in ('robot','controller','dt_s','mpc_params','simulation_params','controller_changes',
        'reference_limits','friction','hold_seconds','initial_height_estimate_m','nominal_lower_duration_s','seed')}
    snapshots = {}
    for folder in ('control', 'planning', 'learning', 'environment', 'recording'):
        for source in sorted((p/'source'/folder).glob('*.py')):
            if source.name != 'catalog.py':
                snapshots[str(source.relative_to(p/'source'))] = digest(source)
    return dict(trial_id=key, run_directory=str(p), planner=m['planner'], sensor_profile=m['sensor_profile']['name'],
        actual_height_m=m['evaluation']['actual_pad_height_m'], noisy=delayed, passed=all(checks.values()), checks=checks,
        true_minimum_pad_force_before_reload_n=float(s['target_pad_normal_force'][window].min()),
        true_pre_reload_window_samples=round(.1/dt), true_pre_reload_window_duration_s=round(.1/dt)*dt,
        minimum_each_final_foot_force_n=s['contact_normal_force'][final].min(axis=0).tolist(),
        maximum_nominal_foot_speed_m_s=float(foot_speed[valid_intervals].max()),
        maximum_body_speed_m_s=float(body_speed[valid_intervals].max()),
        maximum_recovery_speed_m_s=float(foot_speed[recovery_intervals].max()) if recovery_intervals.any() else None,
        mpc_updates=int(s['mpc_update'].sum()), planner_updates=int(s['planner_update'].sum()),
        fallback_ticks=int(s['planner_fallback_count'].max()), missing_contact_observed=bool(len(missing)),
        settings_sha256=json_digest(settings), source_sha256=entry['source_sha256'],
        model_sha256=entry['model_sha256'], snapshot_sha256=json_digest(snapshots), snapshot_files=snapshots,
        recording_hashes={name:digest(p/name) for name in files})


def main():
    state = json.loads(PRIMARY_STATE.read_text())
    heldout = json.loads(HELDOUT_STATE.read_text())
    primary_entries = [(name, entry) for name, entry in state['trials'].items() if name.startswith('eval_')]
    heldout_entries = [(name, entry) for name, entry in heldout['trials'].items() if name.startswith('heldout_')]
    entries = primary_entries+heldout_entries
    if len(entries) != 24 or any(entry['status'] != 'completed' for _, entry in entries):
        raise RuntimeError('Final audit waits until all 18 primary and 6 held-out trials are complete')
    completed = [(name, entry) for name, entry in entries if entry['status'] == 'completed']
    rows = [audit_entry(name, entry) for name, entry in completed]
    source = {row['source_sha256'] for row in rows}
    model = {row['model_sha256'] for row in rows if row['model_sha256'] is not None}
    settings = {row['settings_sha256'] for row in rows}
    snapshots = {row['snapshot_sha256'] for row in rows}
    from primp_project.experiments.pad_study import source_fingerprint
    common = dict(all_24_complete=len(rows)==24, primary_18_complete=len(primary_entries)==18,
        heldout_6_complete=len(heldout_entries)==6, identical_controller_settings=len(settings)==1,
        identical_frozen_source=len(source)==1, current_source_matches_frozen=source=={source_fingerprint()},
        identical_archived_runtime_source=len(snapshots)==1, identical_learned_model=len(model)==1)
    noisy = [row for row in rows if row['noisy']]
    model_metadata = json.loads((ROOT/'results/landing_pad/study/model/model.json').read_text())
    demonstrations = []
    for record in model_metadata['training_records']:
        run = Path(record['run_directory'])
        fields = {'signals.npz':'signals_sha256', 'metadata.json':'metadata_sha256', 'pad_summary.json':'summary_sha256'}
        preserved = {name: digest(run/name) == record[field] for name, field in fields.items()}
        demonstrations.append(dict(run_id=record['run_id'], passed=all(preserved.values()),
            preserved=preserved, original_model_provenance_hashes={name:record[field] for name,field in fields.items()}))
    common['nine_training_recordings_preserved_against_model_provenance'] = len(demonstrations)==9 and all(row['passed'] for row in demonstrations)
    output = dict(created_at=datetime.now(timezone.utc).isoformat(),
        audit='Independent raw-signal execution audit; no analyzer invocation or canonical-file writes',
        passed=all(common.values()) and all(row['passed'] for row in rows),
        completed_trials=len(rows), primary_trials=len(primary_entries), heldout_trials=len(heldout_entries),
        noisy_trials=len(noisy), common_checks=common, training_demonstration_integrity=demonstrations,
        minimum_noisy_true_pad_force_before_reload_n=min(row['true_minimum_pad_force_before_reload_n'] for row in noisy),
        minimum_final_foot_loading_n=min(min(row['minimum_each_final_foot_force_n']) for row in rows),
        frozen_source_sha256=sorted(source), model_sha256=sorted(model), trials=rows)
    OUT.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    VERSIONED.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT, VERSIONED/OUT.name)
    if Path(__file__).resolve() != (VERSIONED/'audit_execution.py').resolve():
        shutil.copy2(__file__, VERSIONED/'audit_execution.py')
    print(json.dumps({key:value for key,value in output.items() if key not in ('trials', 'training_demonstration_integrity')},indent=2))


if __name__ == '__main__':
    main()
