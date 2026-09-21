"""Result discovery must preserve source recordings and distinguish their status."""

import json
from pathlib import Path
import pytest

from primp_project.recording.catalog import list_results, refresh_catalog


def _run(root, group, name, metadata, summary=None, report=True):
    path = root / group / name
    path.mkdir(parents=True)
    (path / "metadata.json").write_text(json.dumps(metadata))
    step = metadata.get("experiment") == "controlled_step"
    if summary is not None:
        (path / ("step_summary.json" if step else "summary.json")).write_text(json.dumps(summary))
    if report:
        (path / ("step_report.md" if step else "REPORT.md")).write_text("Historical report\n")
    (path / "signals.npz").write_bytes(b"opaque raw data: must never be opened as a NumPy file")
    return path


def test_catalog_groups_pointers_and_preserves_recordings(tmp_path):
    root = tmp_path / "results"
    baseline = _run(root, "standing", "standing_baseline", {"status": "completed", "recorded_steps": 10, "dt_s": 0.002, "purpose": "Original description"}, {"passed": True})
    latest = _run(root, "standing", "standing_recent", {"status": "completed", "purpose": "Purpose from metadata"}, {"passed": False})
    archived = _run(root, "archive", "standing_smoke", {"status": "completed"}, {"passed": True})
    (root / "standing" / "CANONICAL.txt").write_text(baseline.name + "\n")
    (root / "standing" / "LATEST.txt").write_text(latest.name + "\n")
    (root / "annotations.json").write_text(json.dumps({
        baseline.name: {"purpose": "Annotated baseline"},
        archived.name: {"purpose": "Archived smoke test", "notes": ["Preserved historical note."]},
    }))
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

    records = refresh_catalog(root)
    by_id = {record["id"]: record for record in records}

    assert by_id[baseline.name]["canonical"] is True
    assert by_id[baseline.name]["latest"] is False
    assert by_id[baseline.name]["duration_s"] == 0.02
    assert by_id[baseline.name]["purpose"] == "Annotated baseline"
    assert by_id[latest.name]["canonical"] is False
    assert by_id[latest.name]["latest"] is True
    assert by_id[latest.name]["status"] == "FAIL"
    assert by_id[latest.name]["purpose"] == "Purpose from metadata"
    assert by_id[archived.name]["group"] == "archive"
    assert "smoke" in by_id[archived.name]["purpose"]
    assert by_id[archived.name]["notes"] == ["Preserved historical note."]
    assert all(path.read_bytes() == content for path, content in before.items())
    assert json.loads((root / "catalog.json").read_text()) == records
    assert "**canonical**" in (root / "README.md").read_text()
    created = {path.relative_to(root) for path in root.rglob("*") if path.is_file()} - {path.relative_to(root) for path in before}
    assert created == {Path("README.md"), Path("catalog.json")}


def test_catalog_missing_analysis_and_report_and_failed_runner(tmp_path):
    root = tmp_path / "results"
    _run(root, "standing", "unanalyzed", {"status": "completed"}, report=False)
    _run(root, "standing", "failed", {"status": "failed", "error": "stopped"}, {"passed": True})
    _run(root, "controlled_step", "step_saved", {"status": "completed", "experiment": "controlled_step", "actual_completed_cycles": 3, "hold_seconds": 6, "friction": 0.8, "rendered": False}, {"passed": True, "metrics": {"duration_s": 96.0, "sample_count": 48000}}, report=False)

    by_id = {record["id"]: record for record in refresh_catalog(root)}

    assert by_id["unanalyzed"]["status"] == "UNANALYZED"
    assert by_id["unanalyzed"]["purpose"] == "Recorded experiment"
    assert by_id["failed"]["status"] == "FAIL"
    step = by_id["step_saved"]
    assert step["status"] == "PASS"
    assert "report" not in step["links"]
    assert step["cycles"] == 3
    assert step["samples"] == 48000
    assert step["duration_s"] == 96.0


def test_list_results_empty_root_is_supported(tmp_path, capsys):
    root = tmp_path / "isolated_results"
    assert list_results(root) == 0
    assert "0 recording(s)" in capsys.readouterr().out
    assert json.loads((root / "catalog.json").read_text()) == []


def test_nested_landing_trials_prefer_pad_validation_and_local_pointers(tmp_path):
    root = tmp_path / "results"
    run = _run(root, "landing_pad/studies/pilot/evaluation/reactive", "pad_saved", {
        "status": "completed", "experiment": "landing_pad", "role": "evaluation",
        "planner": "reactive", "actual_completed_cycles": 1, "cycles": 1,
        "initial_height_estimate_m": 0., "evaluation": {"actual_pad_height_m": -.005},
        "sensor_profile": {"name": "noisy_delayed"},
    })
    (run / "step_summary.json").write_text(json.dumps({"passed": True}))
    (run / "pad_summary.json").write_text(json.dumps({
        "passed": False, "metrics": {"duration_s": 30., "sample_count": 15000},
    }))
    (run / "pad_report.md").write_text("Pad checks failed\n")
    (run.parent / "LATEST.txt").write_text(run.name + "\n")
    (root / "landing_pad" / "CANONICAL.txt").write_text(run.relative_to(root / "landing_pad").as_posix() + "\n")
    source_metadata = run / "source" / "historical" / "metadata.json"
    source_metadata.parent.mkdir(parents=True)
    source_metadata.write_text(json.dumps({"status": "completed", "experiment": "landing_pad"}))
    before = {file: file.read_bytes() for file in run.rglob("*") if file.is_file()}
    records = refresh_catalog(root)
    assert len(records) == 1
    record = records[0]
    assert record["group"] == "landing_pad"
    assert record["experiment"] == "landing_pad"
    assert record["status"] == "FAIL"
    assert record["canonical"] and record["latest"]
    assert record["links"]["summary"].endswith("pad_summary.json")
    assert record["links"]["report"].endswith("pad_report.md")
    assert record["actual_pad_height_m"] == -.005
    assert record["samples"] == 15000 and record["duration_s"] == 30.
    assert all(file.read_bytes() == content for file, content in before.items())
    assert "noisy_delayed" in (root / "README.md").read_text()


def test_missing_pad_summary_does_not_inherit_a_passing_step_report(tmp_path):
    root = tmp_path / "results"
    run = _run(root, "landing_pad/development", "pad_without_analysis", {
        "status": "completed", "experiment": "landing_pad",
    })
    (run / "step_summary.json").write_text(json.dumps({"passed": True}))
    assert refresh_catalog(root)[0]["status"] == "UNANALYZED"


@pytest.mark.parametrize('outcome,status,physical', [
    ('SUCCESS', 'PASS', True), ('PROBLEM_COLLAPSE', 'PROBLEM_COLLAPSE', False),
    ('SAFE_STOP', 'SAFE_STOP', False), ('UNSAFE', 'UNSAFE', False),
    ('INCOMPLETE', 'INCOMPLETE', False), ('INVALID', 'INVALID', False),
])
def test_weak_pad_expected_outcomes_do_not_masquerade_as_physical_success(tmp_path, outcome, status, physical):
    root = tmp_path/'results'
    run = _run(root, 'weak_pad/study/evaluation', 'weak_record', {
        'experiment':'weak_pad', 'status':'completed', 'strategy':'adaptive', 'role':'evaluation',
        'requested_probe_force_n':45., 'recorded_steps':100, 'dt_s':.002,
    })
    # Historical generic summaries must not override weak-pad-specific results.
    (run/'step_summary.json').write_text(json.dumps({'passed':True}))
    (run/'weak_pad_summary.json').write_text(json.dumps(dict(outcome=outcome, passed=physical,
        physical_success=physical, expected_outcome_met=True, metrics={'maximum_certified_force_n':21.})))
    (run/'weak_pad_report.md').write_text('Preserved weak-pad report\n')
    before = {path:path.read_bytes() for path in run.rglob('*') if path.is_file()}
    record = refresh_catalog(root)[0]
    assert record['status'] == status and record['physical_success'] is physical
    assert record['expected_outcome_met'] is True
    assert record['links']['report'].endswith('weak_pad_report.md')
    assert record['links']['summary'].endswith('weak_pad_summary.json')
    assert record['certified_load_n'] == 21.
    assert all(path.read_bytes() == value for path,value in before.items())


def test_weak_pad_missing_or_contradictory_summary_cannot_inherit_success(tmp_path):
    root = tmp_path/'results'
    run = _run(root, 'weak_pad/development', 'weak_missing', {
        'experiment':'weak_pad', 'status':'completed'}, {'passed':True})
    (run/'step_summary.json').write_text(json.dumps({'passed':True}))
    assert refresh_catalog(root)[0]['status'] == 'UNANALYZED'
    (run/'weak_pad_summary.json').write_text(json.dumps(dict(outcome='SAFE_STOP', passed=True, physical_success=True)))
    assert refresh_catalog(root)[0]['status'] == 'INVALID'


@pytest.mark.parametrize('physical,passed,recovered,expected', [
    (False, False, True, 'RECOVERED_STOP'),
    (True, False, True, 'INVALID'), (False, True, True, 'INVALID'),
    (False, False, False, 'INVALID'), (False, False, None, 'INVALID'),
])
def test_weak_v2_recovery_is_distinct_from_completed_movement(tmp_path, physical, passed, recovered, expected):
    root = tmp_path/'results'
    run = _run(root, 'weak_pad/study_v2/evaluation', 'recovered', {
        'experiment':'weak_pad', 'protocol_version':2, 'strategy':'fixed_probe',
        'scenario':'weak_surface', 'status':'completed'})
    (run/'weak_pad_summary.json').write_text(json.dumps(dict(outcome='RECOVERED_STOP',
        physical_success=physical, passed=passed, controlled_recovery_passed=recovered)))
    (run/'media').mkdir()
    (run/'media/weak_replay.mp4').write_bytes(b'opaque offline replay')
    (run/'media/weak_replay.png').write_bytes(b'opaque rendered preview')
    before = {path:path.read_bytes() for path in run.rglob('*') if path.is_file()}
    record = refresh_catalog(root)[0]
    assert record['status'] == expected
    assert record['protocol_version'] == 2 and record['scenario'] == 'weak_surface'
    assert record['controlled_recovery_passed'] is recovered
    assert record['links']['replay'].endswith('media/weak_replay.mp4')
    assert record['links']['replay_preview'].endswith('media/weak_replay.png')
    assert 'protocol V2' in (root/'README.md').read_text()
    assert all(path.read_bytes() == value for path,value in before.items())
