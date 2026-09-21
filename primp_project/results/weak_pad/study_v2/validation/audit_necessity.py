"""Reconstruct formal front-leg testing necessity without calling the planner.

Reads completed canonical recordings only. LPs are assembled independently from
the recorded settled anchors, initial physical CoM, and frozen movement bounds.
No controller, environment, planner helper, or simulator strength is used.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull


STUDY = Path(__file__).resolve().parent.parent
POLICIES = ('fixed_probe', 'adaptive_force_fixed_posture', 'adaptive_probe')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equilibrium_problem(anchors, weight, origin, settings, *, mode,
                        progress=None, remove_floors=False):
    """Variables: four vertical forces followed by physical CoM X and Y."""
    weak = int(settings['weak_leg']); swing = int(settings['next_lift_leg'])
    floor = 0. if remove_floors else float(settings['minimum_support_force_n'])
    low = np.full(4, floor); low[weak] = 0.
    high = np.full(4, weight)
    equality = np.array([
        [1., 1., 1., 1., 0., 0.],
        [*anchors[:, 0], -weight, 0.],
        [*anchors[:, 1], 0., -weight],
    ])
    if mode == 'future':
        low[swing] = high[swing] = 0.
        active = np.arange(4) != swing
        margin = float(settings['support_margin_m'])
        minimum_forward = float(settings['forward_progress_m'] if progress is None else progress)
        # Relaxing required progress to 30mm DOES NOT shrink the original
        # upper forward bound, lateral freedoms, or any other feasible freedom.
        x_bounds = (origin[0]+minimum_forward,
            origin[0]+settings['forward_progress_m']+settings['maximum_extra_forward_m'])
        y_bounds = (origin[1]-settings['maximum_lateral_adjustment_m'],
                    origin[1]+settings['maximum_lateral_adjustment_m'])
        objective = np.zeros(6); objective[weak] = 1.
    else:
        active = np.arange(4) != weak
        margin = float(settings['original_tripod_margin_m'])
        shift = float(settings['probe_posture_adjustment_m']) if mode == 'moved_probe' else 0.
        x_bounds = (origin[0]-shift, origin[0]+shift)
        y_bounds = (origin[1]-shift, origin[1]+shift)
        objective = np.zeros(6); objective[weak] = -1.
    hull = ConvexHull(anchors[active, :2])
    # QHull equations have outward unit normals: n*x + b <= 0.
    inequalities = np.c_[np.zeros((len(hull.equations), 4)), hull.equations[:, :2]]
    right = -hull.equations[:, 2]-margin
    answer = linprog(objective, A_eq=equality, b_eq=[weight, 0., 0.],
        A_ub=inequalities, b_ub=right,
        bounds=[*zip(low, high), x_bounds, y_bounds], method='highs')
    if not answer.success:
        return dict(feasible=False, solver_message=str(answer.message))
    return dict(feasible=True, weak_force_n=float(answer.x[weak]),
        forces_n=answer.x[:4].tolist(), com_xy_w=answer.x[4:].tolist(),
        minimum_triangle_margin_m=float(np.min(-hull.equations[:, :2]@answer.x[4:]-hull.equations[:, 2])),
        maximum_equilibrium_residual=float(np.max(np.abs(equality@answer.x-[weight, 0., 0.]))))


def bounds_for(anchors, weight, origin, settings):
    result = {
        'fixed_probe_declared_floors': equilibrium_problem(anchors, weight, origin, settings, mode='fixed_probe'),
        'fixed_probe_no_force_floors': equilibrium_problem(anchors, weight, origin, settings, mode='fixed_probe', remove_floors=True),
        'moved_probe_declared_floors': equilibrium_problem(anchors, weight, origin, settings, mode='moved_probe'),
        'future_full_freedoms': equilibrium_problem(anchors, weight, origin, settings, mode='future'),
        'future_relaxed_30mm_full_freedoms': equilibrium_problem(anchors, weight, origin, settings, mode='future', progress=.03),
    }
    feasible = all(item['feasible'] for item in result.values())
    result['all_lps_feasible'] = feasible
    result['necessity_margin_without_force_floors_n'] = (
        result['future_relaxed_30mm_full_freedoms']['weak_force_n']
        -result['fixed_probe_no_force_floors']['weak_force_n']) if feasible else None
    return result


def audit_record(spec, entry):
    run = Path(entry['run_dir'])
    metadata = json.loads((run/'metadata.json').read_text())
    summary = json.loads((run/'weak_pad_summary.json').read_text())
    settings = metadata['movement_optimizer_settings']
    with np.load(run/'signals.npz', allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    ramp = np.flatnonzero(data['phase'].astype(str) == 'probe_ramp')
    if not len(ramp) or ramp[0] == 0:
        return dict(trial_id=spec['trial_id'], passed=False, error='No independently aligned first probe snapshot')
    first = int(ramp[0])
    sensed = data['feet_desired_w'][first].copy()
    physical = data['feet_pos_w'][first-1].copy()
    expected_sensed = physical.copy(); expected_sensed[0] = data['sensor_pad_foot_pos_w'][first]
    origin = data['probe_origin_com_w'][first].copy()
    weight = float(metadata['model_mass_kg']*metadata['gravity_m_s2'])
    hashes = {key: sha(run/name) for key, name in (
        ('signals_sha256', 'signals.npz'), ('metadata_sha256', 'metadata.json'), ('summary_sha256', 'weak_pad_summary.json'))}
    sensed_bounds = bounds_for(sensed, weight, origin, settings)
    physical_bounds = bounds_for(physical, weight, origin, settings)
    errors = dict(sensed_anchor_alignment_m=float(np.max(np.abs(sensed-expected_sensed))),
        origin_prior_physics_alignment_m=float(np.max(np.abs(origin-data['com_pos_w'][first-1]))),
        sensor_position_component_error_m=float(np.max(np.abs(sensed-physical))))
    passed = (all(hashes[key] == entry[key] for key in hashes)
        and errors['sensed_anchor_alignment_m'] < 1e-10
        and errors['origin_prior_physics_alignment_m'] < 1e-10
        and errors['sensor_position_component_error_m'] <= metadata['sensor_position_error_bound_m']+1e-10
        and sensed_bounds['all_lps_feasible'] and physical_bounds['all_lps_feasible'])
    if spec['family'].startswith('fr_necessary'):
        passed &= (sensed_bounds['necessity_margin_without_force_floors_n'] > 0
                   and physical_bounds['necessity_margin_without_force_floors_n'] > 0)
    history = metadata.get('capacity_decision_history', [])
    if history:
        errors['logged_minimum_future_force_error_n'] = abs(
            history[0]['minimum_future_load_n']-sensed_bounds['future_full_freedoms']['weak_force_n'])
        errors['logged_fixed_pose_force_error_n'] = abs(
            history[0]['fixed_pose_maximum_probe_load_n']-sensed_bounds['fixed_probe_declared_floors']['weak_force_n'])
        passed &= max(errors['logged_minimum_future_force_error_n'], errors['logged_fixed_pose_force_error_n']) < 1e-7
    final = data['phase'].astype(str) == 'progress_complete'
    progress = data['com_pos_w'][:, 0]-origin[0]
    future = np.isin(data['phase'].astype(str), ['progress_shift', 'next_unload', 'next_lift', 'progress_hold', 'progress_complete'])
    execution = None
    if np.any(final):
        lift = data['feet_pos_w'][:, int(settings['next_lift_leg']), 2]-data['next_lift_anchor_w'][:, 2]
        execution = dict(final_forward_range_m=[float(progress[final].min()), float(progress[final].max())],
            final_next_foot_lift_range_m=[float(lift[final].min()), float(lift[final].max())],
            future_certificate_min_n=float(data['certificate_force_n'][future].min()),
            future_actual_peak_n=float(data['actual_pad_normal_force_n'][future].max()))
    return dict(trial_id=spec['trial_id'], case_id=spec['case_id'], family=spec['family'],
        seed=spec['seed'], strategy=spec['strategy'], outcome=summary['outcome'], passed=bool(passed),
        hashes=hashes, first_probe_sample=first, first_probe_time_s=float(data['control_time_s'][first]),
        sensed_anchors_w=sensed.tolist(), prior_physics_anchors_w=physical.tolist(),
        initial_probe_com_w=origin.tolist(), movement_settings=settings,
        sensor_snapshot_errors=errors, sensed_bounds=sensed_bounds, physical_bounds=physical_bounds,
        successful_execution=execution)


def build():
    manifest = json.loads((STUDY/'split_manifest.json').read_text())
    state = json.loads((STUDY/'study_state.json').read_text())
    specs = [spec for spec in manifest['trials'] if spec['parameters']['planning_config']['next_lift_leg'] == 1]
    rows = [audit_record(spec, state['trials'][spec['trial_id']]) for spec in specs
            if state['trials'].get(spec['trial_id'], {}).get('status') == 'completed']
    groups = defaultdict(list)
    for row in rows:
        groups[(row['case_id'], row['seed'])].append(row)
    matches = []
    for (case, seed), group in groups.items():
        complete = set(row['strategy'] for row in group) == set(POLICIES)
        same_settings = all(row['movement_settings'] == group[0]['movement_settings'] for row in group)
        maximum_anchor_difference = max(float(np.max(np.abs(np.asarray(row['sensed_anchors_w'])
            -np.asarray(group[0]['sensed_anchors_w'])))) for row in group)
        maximum_origin_difference = max(float(np.max(np.abs(np.asarray(row['initial_probe_com_w'])
            -np.asarray(group[0]['initial_probe_com_w'])))) for row in group)
        matches.append(dict(case_id=case, seed=seed, policies=len(group), complete=complete,
            identical_movement_settings=same_settings,
            maximum_cross_policy_anchor_difference_m=maximum_anchor_difference,
            maximum_cross_policy_origin_difference_m=maximum_origin_difference,
            passed=same_settings and max(maximum_anchor_difference, maximum_origin_difference) < 1e-10))
    return dict(version=2, complete=len(rows) == len(specs), expected_fr_trials=len(specs),
        completed_fr_trials=len(rows),
        all_completed_records_pass=all(row['passed'] for row in rows) and all(row['passed'] for row in matches),
        manifest_sha256=sha(STUDY/'split_manifest.json'), execution_freeze_sha256=sha(STUDY/'execution_freeze.json'),
        audit_source_sha256=sha(__file__),
        method='Independent scipy LPs and ConvexHull inequalities; no execution-planner methods or hidden pad strength',
        relaxed_task='Lower forward requirement30mm; original upper-forward and all lateral freedoms retained',
        reference_alignment='First applied probe references equal permitted observations; independent prior physics and sensing bounds checked',
        matched_initial_conditions=matches, trials=rows)


if __name__ == '__main__':
    report = build()
    target = STUDY/'validation'/'necessity_audit.json'
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: report[key] for key in ('complete', 'expected_fr_trials',
        'completed_fr_trials', 'all_completed_records_pass')}))
