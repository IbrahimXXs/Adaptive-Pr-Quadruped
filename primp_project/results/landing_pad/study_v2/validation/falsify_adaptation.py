"""Falsify V2 validation using in-memory copies of one reserved recording."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from primp_project.analysis.adaptation import adaptation_checks


def main():
    directory = Path(__file__).resolve().parents[1]
    state = json.loads((directory/'study_state.json').read_text())
    trial_id = 'eval_matched_learned_h-6mm_seed17_nominal'
    entry = state['trials'][trial_id]
    run = Path(entry['run_dir'])
    metadata = json.loads((run/'metadata.json').read_text())
    with np.load(run/'signals.npz', allow_pickle=False) as archive:
        original = {key: archive[key] for key in archive.files}
    checks, _ = adaptation_checks(metadata, original)
    if not all(value['passed'] for value in checks.values()):
        raise ValueError('The unmodified source recording must pass first')
    active = np.flatnonzero(original['planner_update'].astype(bool) & original['planner_recovery_active'].astype(bool))
    row = int(active[0])
    cases = []

    def falsify(name, criterion, change):
        data = {key: value.copy() for key, value in original.items()}
        change(data)
        result, _ = adaptation_checks(metadata, data)
        rejected = not result[criterion]['passed']
        cases.append(dict(corruption=name, expected_criterion=criterion, rejected=rejected))
        if not rejected:
            raise AssertionError(name)

    falsify('Expired raw learned recovery time concealed by positive feasible time',
            'pad_positive_remaining_duration', lambda d: d['raw_model_remaining_time_s'].__setitem__(row, 0.))
    falsify('Expired applied recovery time', 'pad_positive_remaining_duration',
            lambda d: d['planner_remaining_time_s'].__setitem__(row, 0.))
    falsify('Stale measured foot anchor', 'pad_current_state_replanning',
            lambda d: d['planner_anchor_foot_w'].__setitem__((row, 2), d['planner_anchor_foot_w'][row, 2]+.001))
    falsify('Unreported fallback duration', 'pad_fallback_work_accounting',
            lambda d: d['fallback_interval_s'].__setitem__(slice(None), 0.))
    falsify('Fabricated fallback descent', 'pad_fallback_work_accounting',
            lambda d: d['fallback_foot_descent_m'].__setitem__(row, .001))
    fallback = int(np.flatnonzero(original['planner_fallback_active'])[0])
    falsify('Fallback simultaneously credited to learned prior', 'pad_fallback_prior_exclusion',
            lambda d: d['planner_model_prior_active'].__setitem__(fallback, True))
    falsify('Learned label without actual prior execution', 'pad_prior_execution',
            lambda d: d['planner_model_prior_active'].__setitem__(slice(None), False))
    result = dict(passed=True, source_trial_id=trial_id, source_recording=str(run),
                  signals_sha256=hashlib.sha256((run/'signals.npz').read_bytes()).hexdigest(),
                  method='In-memory corruption only; canonical files are never rewritten', cases=cases)
    (Path(__file__).parent/'falsification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
