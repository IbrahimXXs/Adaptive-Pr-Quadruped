"""Reproduce the nine in-memory analyzer mutations without changing raw logs.

Run with the project's quadruped-pympc environment. The default prints JSON;
an explicit --output writes only the requested audit report. This script never
reruns a simulation, changes development selection, or saves mutated signals.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2
from primp_project.task_probe.analysis import evaluate_task_probe


VALIDATION = Path(__file__).resolve().parent
STUDY = VALIDATION.parent
DEVELOPMENT = STUDY.parent/'task_probe_development'
RUNS = (
    'weak_pad_fixed_force_20260921T130326_682698Z',
    'weak_pad_fixed_force_20260921T130326_683022Z',
    'weak_pad_fixed_force_20260921T130326_688211Z',
    'weak_pad_fixed_force_20260921T130435_493705Z',
    'weak_pad_fixed_force_20260921T130435_737727Z',
    'weak_pad_fixed_force_20260921T130435_920406Z',
    'weak_pad_task_sufficient_20260921T130533_840457Z',
)
MUTATED_RUN = 'weak_pad_fixed_force_20260921T130435_737727Z'
MUTATIONS = (
    'false_fixed_force_metadata',
    'command_exceeds_selected_target',
    'selected_request_disagrees_with_execution',
    'consistent_false_smaller_fixed_command',
    'requested_force_substituted_for_measured_proof',
    'tracking_reserve_consistently_weakened',
    'hidden_failure_despite_overload',
    'inconsistent_damage_displacement',
    'old_30mm_completion_with_forged_easier_target',
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(paths):
    return {str(path.relative_to(REPOSITORY_ROOT)): digest(path) for path in paths}


def mutate(name, metadata, data):
    """Return copied evidence; original arrays and metadata are never mutated."""
    metadata = copy.deepcopy(metadata)
    data = {key: value.copy() for key, value in data.items()}
    extra = data['additional_probe_count'] > 0
    active = extra & np.isin(data['phase'], ('probe_ramp', 'probe_hold'))
    if name == 'false_fixed_force_metadata':
        metadata['fixed_probe_force_n'] -= 1.
        metadata['trial_parameters']['fixed_probe_force_n'] -= 1.
    elif name == 'command_exceeds_selected_target':
        data['achieved_probe_command_n'][active] += 1.
    elif name == 'selected_request_disagrees_with_execution':
        data['selected_probe_request_n'][extra] += 1.
    elif name == 'consistent_false_smaller_fixed_command':
        metadata['fixed_probe_force_n'] -= 1.
        metadata['trial_parameters']['fixed_probe_force_n'] -= 1.
        for key in ('probe_target_load_n', 'selected_probe_request_n', 'achieved_probe_command_n'):
            data[key][extra] -= 1.
        for decision in metadata['capacity_decision_history']:
            if decision['action'] == 'PROBE':
                decision['achievable_probe_load_n'] -= 1.
                decision['requested_probe_load_n'] -= 1.
    elif name == 'requested_force_substituted_for_measured_proof':
        data['certificate_force_n'][data['certificate_valid']] += 2.
    elif name == 'tracking_reserve_consistently_weakened':
        metadata['tracking_reserve_n'] = 6.
        metadata['trial_parameters']['tracking_reserve_n'] = 6.
        data['tracking_reserve_n'][:] = 6.
        target = data['minimum_sufficient_probe_load_n']
        target[target > 0.] -= 2.
    elif name == 'hidden_failure_despite_overload':
        indices = np.flatnonzero(active)[:10]
        data['force_before_deformation_n'][indices] = metadata['evaluation']['failure_threshold_n']+1.
    elif name == 'inconsistent_damage_displacement':
        data['actual_pad_displacement_m'][:] = .06
    elif name == 'old_30mm_completion_with_forged_easier_target':
        rows = np.isin(data['phase'], ('progress_hold', 'progress_complete'))
        position = data['probe_origin_com_w'][rows, 0]+.031
        data['com_pos_w'][rows, 0] = position
        data['progress_target_w'][rows, 0] = position
    else:
        raise ValueError(f'Unknown mutation: {name}')
    return metadata, data


def audit():
    raw_paths = [DEVELOPMENT/run/filename for run in RUNS
                 for filename in ('metadata.json', 'signals.npz')]
    selection_paths = [VALIDATION/'development_protocol.json', VALIDATION/'fixed_force_selection.json',
                       VALIDATION/'evaluation_cases.json', STUDY/'split_manifest.json',
                       STUDY/'execution_freeze.json']
    raw_before, selection_before = hashes(raw_paths), hashes(selection_paths)
    report = dict(
        audit='Independent native development mutation audit of the additional task_probe validator',
        old_validator='primp_project.analysis.weak_pad_v2.evaluate_weak_pad_v2 (unchanged)',
        new_validator='primp_project.task_probe.analysis.evaluate_task_probe (additional integrity/task criteria)',
        raw_logs_modified=False, native_originals=[], mutations=[],
    )
    originals = {}
    for run in RUNS:
        directory = DEVELOPMENT/run
        metadata = json.loads((directory/'metadata.json').read_text())
        with np.load(directory/'signals.npz', allow_pickle=False) as archive:
            data = {key: archive[key] for key in archive.files}
        originals[run] = metadata, data
        result = evaluate_task_probe(metadata, data)
        report['native_originals'].append(dict(
            run=str(directory.relative_to(REPOSITORY_ROOT)), policy=metadata['probe_policy'],
            requested_progress_m=metadata['movement_optimizer_settings']['forward_progress_m'],
            fixed_probe_force_n=metadata['fixed_probe_force_n'], outcome=result['outcome'],
            baseline_outcome=result['baseline_outcome'], valid=result['task_probe_integrity_passed'],
        ))
    for name in MUTATIONS:
        metadata, data = mutate(name, *originals[MUTATED_RUN])
        baseline = evaluate_weak_pad_v2(metadata, data)
        result = evaluate_task_probe(metadata, data)
        criteria = {**result['criteria'], **result['task_probe_criteria']}
        violations = [key for key, value in criteria.items()
                      if not value['passed'] and value.get('category') == 'integrity']
        report['mutations'].append(dict(
            mutation=name, baseline_outcome=baseline['outcome'], new_outcome=result['outcome'],
            rejected=result['outcome'] == 'INVALID' and not result['physical_success'],
            failed_integrity_checks=violations,
        ))
    raw_after, selection_after = hashes(raw_paths), hashes(selection_paths)
    report.update(
        raw_sha256_before=raw_before, raw_sha256_after=raw_after,
        raw_hashes_unchanged=raw_before == raw_after,
        selection_sha256_before=selection_before, selection_sha256_after=selection_after,
        selection_hashes_unchanged=selection_before == selection_after,
        new_analyzer_sha256=digest(REPOSITORY_ROOT/'primp_project/task_probe/analysis.py'),
        frozen_v2_analyzer_sha256=digest(REPOSITORY_ROOT/'primp_project/analysis/weak_pad_v2.py'),
        audit_script_sha256=digest(__file__),
    )
    report['passed'] = (
        all(row['valid'] and row['outcome'] in ('SUCCESS', 'SAFE_STOP', 'RECOVERED_STOP')
            for row in report['native_originals'])
        and all(row['rejected'] for row in report['mutations'])
        and report['mutations'][-1]['baseline_outcome'] == 'SUCCESS'
        and report['raw_hashes_unchanged'] and report['selection_hashes_unchanged']
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write only this report; otherwise print JSON')
    args = parser.parse_args()
    result = audit()
    encoded = json.dumps(result, indent=2, allow_nan=False)+'\n'
    if args.output:
        # Prevent accidental overwriting of trial evidence or frozen selection.
        destination = args.output.resolve()
        if destination.parent != VALIDATION or destination.suffix != '.json':
            parser.error('--output must name a JSON audit report in this validation directory')
        protected = {'development_protocol.json', 'fixed_force_selection.json', 'evaluation_cases.json',
                     'evaluation_cases_template.json', 'frozen_predecessor_snapshot.json'}
        if destination.name in protected:
            parser.error('--output cannot overwrite a protocol, selection or baseline snapshot')
        destination.write_text(encoded)
        print(f"passed={result['passed']}; native originals={len(result['native_originals'])}; "
              f"mutations={len(result['mutations'])}; report={destination}")
    else:
        print(encoded, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
