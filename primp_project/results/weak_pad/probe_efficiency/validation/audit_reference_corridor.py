"""Read-only design audit of the preserved V2 load-testing recordings.

The equilibrium LP is the independent V2 audit, not the execution planner.
Hidden capacity is read only to describe old failures; it never enters an LP.
This script writes only into the separate probe-efficiency experiment folder.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


PROJECT = Path(__file__).resolve().parents[4]
V2 = PROJECT / 'results/weak_pad/study_v2'
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_audit():
    source = V2 / 'validation/audit_necessity.py'
    spec = importlib.util.spec_from_file_location('preserved_necessity_audit', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def analyze():
    audit = independent_audit()
    rows = []
    for family, capacity in [('fr_necessary_a', 66), ('fr_necessary_b', 62)]:
        for seed in (101, 509):
            trial_id = f'{family}_capacity{capacity}_adaptive_probe_seed{seed}'
            run = next((V2 / 'trials' / trial_id).glob('weak_pad_*'))
            metadata = json.loads((run / 'metadata.json').read_text())
            with np.load(run / 'signals.npz', allow_pickle=False) as archive:
                data = {key: archive[key] for key in archive.files}
            first = np.flatnonzero(data['phase'] == 'probe_ramp')[0]
            anchors = data['feet_desired_w'][first]
            origin = data['probe_origin_com_w'][first]
            bounds = audit.bounds_for(anchors,
                metadata['model_mass_kg'] * metadata['gravity_m_s2'],
                origin, metadata['movement_optimizer_settings'])
            minimum = bounds['future_full_freedoms']['weak_force_n']
            measurement = metadata['sensor_force_reserve_n']
            tracking = metadata['tracking_reserve_n']
            measured_target = minimum + measurement + tracking
            additional = data['additional_probe_count'] > 0
            late_hold = additional & (data['phase'] == 'probe_hold') & (data['phase_time_s'] > 1.)
            active_test = additional & np.isin(data['phase'], ['probe_ramp', 'probe_hold'])
            command = float(np.median(data['achieved_probe_command_n'][late_hold]))
            error = data['actual_pad_normal_force_n'][late_hold] - command
            last_decision = metadata['capacity_decision_history'][-1]
            rows.append(dict(trial_id=trial_id, family=family, seed=seed,
                source=str(run.relative_to(PROJECT)),
                hashes={name: sha(run/name) for name in ('metadata.json', 'signals.npz')},
                minimum_future_load_n=minimum,
                relaxed_30mm_minimum_future_load_n=bounds['future_relaxed_30mm_full_freedoms']['weak_force_n'],
                measurement_reserve_n=measurement, tracking_reserve_n=tracking,
                required_minimum_sensor_plateau_n=measured_target,
                declared_sensor_error_bound_n=metadata['sensor_force_error_bound_n'],
                old_probe_command_n=command,
                old_probe_actual_peak_n=float(data['actual_pad_normal_force_n'][active_test].max()),
                late_hold_actual_minus_command_min_n=float(error.min()),
                late_hold_actual_minus_command_max_n=float(error.max()),
                measured_certificate_n=float(data['certificate_force_n'].max()),
                executed_future_allocated_load_n=last_decision['chosen_future_load_n'],
                ideal_command_reduction_n=command-measured_target,
                illustrative_command_with_one_newton_execution_allowance_n=measured_target+1.,
                capacity_corridor_above_illustrative_command_below_old_command_n=[measured_target+1.,command]))
    old_failure_rows=[]
    for family, capacity in [('fr_necessary_a',34),('fr_necessary_b',29)]:
        for seed in (101,509):
            trial_id=f'{family}_capacity{capacity}_adaptive_probe_seed{seed}'
            run=next((V2/'trials'/trial_id).glob('weak_pad_*'))
            reference=next(row for row in rows if row['family']==family and row['seed']==seed)
            summary=json.loads((run/'weak_pad_summary.json').read_text())
            old_failure_rows.append(dict(trial_id=trial_id,hidden_capacity_n=capacity,
                outcome=summary['outcome'],
                relaxed_task_required_load_n=reference['relaxed_30mm_minimum_future_load_n'],
                below_even_relaxed_required_load=capacity<reference['relaxed_30mm_minimum_future_load_n']))
    return dict(protocol='reference-only; no new policy or native trial is evaluated here',
        preserved_manifest_sha256=sha(V2/'split_manifest.json'),
        preserved_execution_freeze_sha256=sha(V2/'execution_freeze.json'),
        independent_lp_source_sha256=sha(V2/'validation/audit_necessity.py'),
        audit_source_sha256=sha(__file__),
        interpretation=[
            'Minimum future load is a quasistatic optimization lower bound for the shared task, not a physical certificate.',
            'A sufficient certificate requires the minimum observed stable plateau to exceed future load plus both unchanged reserves.',
            'The illustrative additional 1 N only targets the command: 0.8 N declared sensing error and 0.2 N observed late-hold undershoot allowance. It is not a new certificate or a verified general tracking guarantee.',
            'The old four failed pads are below even the relaxed task load; these data do not show that gentler probing could complete those tasks.',
            'The new capacity sweep should test the missing corridor between sufficient proof and the old larger applied test, and include boundary failures without tuning capacities to force success.',
        ], recorded_reference_trials=rows, preserved_failed_trials=old_failure_rows)


if __name__ == '__main__':
    result=analyze()
    (OUT/'reference_corridor.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for row in result['recorded_reference_trials']:
        print(row['trial_id'], 'future', round(row['minimum_future_load_n'],3),
            'measured target',round(row['required_minimum_sensor_plateau_n'],3),
            'old command',round(row['old_probe_command_n'],3))
