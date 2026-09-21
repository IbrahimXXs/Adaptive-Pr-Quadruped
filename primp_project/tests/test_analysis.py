"""Rejection regressions using temporary copies of an actual recorded run.

Run after recording a successful short run. PRIMP_ANALYSIS_BASELINE can select
a particular run directory; otherwise the smallest completed local run is used.
No recorded experiment or large checked-in fixture is modified.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pytest

from primp_project import ARTIFACTS_ROOT, RESULTS_ROOT
from primp_project.analysis.standing import analyze_run


@pytest.fixture(scope="module")
def recorded_baseline():
    explicit = os.environ.get("PRIMP_ANALYSIS_BASELINE")
    candidates = [Path(explicit)] if explicit else sorted(RESULTS_ROOT.glob("*/standing_*"))
    usable = []
    for candidate in candidates:
        if not (candidate / "signals.npz").is_file() or not (candidate / "metadata.json").is_file():
            continue
        metadata = json.loads((candidate / "metadata.json").read_text())
        if metadata.get("status") == "completed":
            usable.append((metadata["expected_steps"], candidate, metadata))
    if not usable:
        pytest.skip("Record a completed standing run before running analysis regressions")
    _, source, metadata = min(usable, key=lambda item: item[0])
    with np.load(source / "signals.npz", allow_pickle=False) as archive:
        signals = {name: archive[name].copy() for name in archive.files}
    return metadata, signals


@pytest.fixture
def temporary_recording(recorded_baseline):
    metadata, original = recorded_baseline
    debug = ARTIFACTS_ROOT / "test_tmp"
    debug.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="analysis-regression-", dir=debug) as directory:
        run_dir = Path(directory)
        yield run_dir, deepcopy(metadata), {name: values.copy() for name, values in original.items()}


def analyze_copy(recording):
    run_dir, metadata, signals = recording
    (run_dir / "metadata.json").write_text(json.dumps(metadata))
    np.savez_compressed(run_dir / "signals.npz", **signals)
    return analyze_run(run_dir)


def test_actual_baseline_passes_with_state_and_control_alignment(temporary_recording):
    summary = analyze_copy(temporary_recording)
    assert summary["passed"], {name: result for name, result in summary["criteria"].items() if not result["passed"]}
    assert summary["criteria"]["control_state_alignment"]["passed"]
    assert summary["criteria"]["mpc_update_cadence"]["passed"]
    for filename in ("summary.json", "REPORT.md", "overview.png"):
        assert (temporary_recording[0] / filename).stat().st_size > 0


@pytest.mark.parametrize(
    "corruption, rejected_criterion",
    [
        ("truncated_run", "sample_count"),
        ("nonzero_command", "zero_velocity_command"),
        ("missing_contact", "measured_full_stance"),
        ("shifted_control_time", "control_state_alignment"),
        ("missing_mpc_update", "mpc_update_cadence"),
    ],
)
def test_invalid_recording_cannot_report_success(temporary_recording, corruption, rejected_criterion):
    _, metadata, signals = temporary_recording
    first_standing = int(np.flatnonzero(signals["phase"] == "standing")[0])
    if corruption == "truncated_run":
        # Retain 'completed' metadata to ensure data checks catch a short file.
        for name in signals:
            signals[name] = signals[name][:-10].copy()
    elif corruption == "nonzero_command":
        signals["cmd_lin_vel_w"][first_standing, 0] = 0.1
    elif corruption == "missing_contact":
        signals["contact_measured"][first_standing, 0] = False
    elif corruption == "shifted_control_time":
        signals["control_time_s"][first_standing] += metadata["dt_s"]
    elif corruption == "missing_mpc_update":
        signals["mpc_update"][np.flatnonzero(signals["mpc_update"])[0]] = False
    summary = analyze_copy(temporary_recording)
    assert not summary["passed"]
    assert not summary["criteria"][rejected_criterion]["passed"]
