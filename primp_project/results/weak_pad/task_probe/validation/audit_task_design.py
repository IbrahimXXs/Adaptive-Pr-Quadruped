"""Independent analytic design for task-dependent versus one fixed test force.

No native experiment runs here. The original B/62 N/seed101 recording supplies
only allowed measured geometry. Hidden strength never enters an equilibrium LP.
The development tournament, not this analysis, must select the fixed command.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


STUDY = Path(__file__).resolve().parent.parent
PROJECT = STUDY.parents[2]
SOURCE = PROJECT/'results/weak_pad/study_v2/validation/audit_necessity.py'
REFERENCE = PROJECT/'results/weak_pad/study_v2/trials/fr_necessary_b_capacity62_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111734_321818Z'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    spec = importlib.util.spec_from_file_location('independent_task_geometry', SOURCE)
    geometry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(geometry)
    metadata = json.loads((REFERENCE/'metadata.json').read_text())
    with np.load(REFERENCE/'signals.npz', allow_pickle=False) as archive:
        data = {key:archive[key] for key in archive.files}
    first = int(np.flatnonzero(data['phase']=='probe_ramp')[0])
    anchors = data['feet_desired_w'][first]
    origin = data['probe_origin_com_w'][first]
    weight = metadata['model_mass_kg']*metadata['gravity_m_s2']
    settings = metadata['movement_optimizer_settings']
    maximum = geometry.equilibrium_problem(anchors,weight,origin,settings,mode='moved_probe')
    robust_maximum = maximum['weak_force_n']-settings['probe_robustness_margin_n']
    candidates = [50.57,52.5,53.]
    tasks = []
    for purpose, forward in [('development_low',.034),('evaluation_low',.036),
                             ('evaluation_nominal_control',.040),('evaluation_high',.044),
                             ('development_high',.045)]:
        changed = dict(settings,forward_progress_m=forward)
        minimum = geometry.equilibrium_problem(anchors,weight,origin,changed,mode='future')
        force = minimum['weak_force_n']
        measured = force+1.+8.+.001
        command = measured+.8+.2
        tasks.append(dict(purpose=purpose,forward_progress_m=forward,
            minimum_future_load_n=force,required_minimum_measured_plateau_n=measured,
            task_derived_probe_command_n=command,
            remaining_probe_achievability_slack_n=robust_maximum-command,
            future_lp=minimum,
            fixed_candidates=[dict(command_n=candidate,
                geometrically_achievable=candidate<=robust_maximum,
                exceeds_task_command_with_all_declared_allowances=candidate>=command,
                optimistic_posttest_cap_n=candidate-1.-8.,
                optimistic_future_feasible=candidate-1.-8.>=force)
                for candidate in candidates]))
    return dict(kind='ANALYTIC DESIGN ONLY; native outcomes and fixed-force selection are not inferred',
        reference_recording=str(REFERENCE.relative_to(PROJECT)),
        reference_hashes={name:sha(REFERENCE/name) for name in ('metadata.json','signals.npz')},
        audit_source_sha256=sha(__file__),independent_lp_source_sha256=sha(SOURCE),
        first_probe_sample=first,anchors_from_allowed_observations_w=anchors.tolist(),
        initial_probe_origin_w=origin.tolist(),weight_n=weight,
        unchanged_movement_settings_except_progress=settings,
        robust_maximum_moved_posture_probe_n=robust_maximum,
        target_arithmetic=dict(sensing_reserve_n=1.,tracking_reserve_n=8.,
            numerical_tolerance_n=.001,command_sensor_error_allowance_n=.8,
            empirical_probe_undershoot_allowance_n=.2),
        development_protocol=dict(tasks_forward_m=[.034,.045],fixed_command_candidates_n=candidates,
            hidden_capacity_n=62.,seed=101,trial_count=6,
            selection='Smallest single command whose native trials complete both development tasks undamaged; no formal data may change the scalar.',
            retain_all_attempts=True),
        evaluation_protocol=dict(tasks_forward_m=[.036,.040,.044],hidden_capacities_n=[51.5,55.],
            seeds=[311,1201],policies=['development_selected_fixed_force','task_derived_minimum_sufficient'],
            trial_count=24,task_range='Interpolate inside the wider development 34–45 mm range.',
            novelty='New physical task/capacity combinations and seeds; geometry is known, and 40 mm is a nominal-demand control.',
            task_tracking_requirement='In addition to unchanged V2 safety/progress criteria, verify actual task-specific terminal progress under a declared common tracking tolerance.'),
        tasks=tasks,
        limitations=['Equilibrium feasibility and requested force do not demonstrate physical execution or surface survival.',
            'The selected fixed command must come from the native six-cell development tournament.',
            'Both policies retain the same pose and load freedoms; only additional test amplitude policy differs.',
            'The higher-demand weak-capacity case can expose damage under both policies; stopping and recovery are separate from completion.',
            'Only the simulator and evaluator receive hidden pad strength.'])


if __name__=='__main__':
    result=build()
    Path(__file__).with_name('analytic_task_design.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for task in result['tasks']:
        print(task['purpose'],task['forward_progress_m'],round(task['minimum_future_load_n'],6),
            round(task['task_derived_probe_command_n'],6))
