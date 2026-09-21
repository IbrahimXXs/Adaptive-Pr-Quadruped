"""Compare the frozen controller's matched old and new B/62 seed101 pilots."""
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'study_v2/trials/fr_necessary_b_capacity62_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111734_321818Z'
NEW = ROOT / 'probe_efficiency_development/weak_pad_maximum_feasible_20260921T121521_781558Z'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    with np.load(OLD/'signals.npz', allow_pickle=False) as archive:
        previous = {key:archive[key] for key in archive.files}
    with np.load(NEW/'signals.npz', allow_pickle=False) as archive:
        current = {key:archive[key] for key in archive.files}
    excluded = ['wall_time_s', 'solver_time_s']
    checks = {}
    for key in sorted(set(previous) & set(current) - set(excluded)):
        old, new = previous[key], current[key]
        checks[key] = dict(same_shape=old.shape == new.shape,
            identical=bool(np.array_equal(old,new)),
            max_absolute_difference=float(np.max(np.abs(old.astype(float)-new.astype(float))))
                if old.shape == new.shape and old.dtype.kind != 'U' else None)
    return dict(old_run=str(OLD), new_run=str(NEW),
        old_signals_sha256=sha(OLD/'signals.npz'), new_signals_sha256=sha(NEW/'signals.npz'),
        audit_source_sha256=sha(__file__), excluded_nonphysical_wall_times=excluded,
        identical_all_compared_fields=all(row['identical'] for row in checks.values()),
        compared_field_count=len(checks), checks=checks)


if __name__ == '__main__':
    report = build()
    Path(__file__).with_name('baseline_behavior_equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['identical_all_compared_fields'], report['compared_field_count'])
