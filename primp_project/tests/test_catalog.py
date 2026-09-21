"""Result discovery must preserve source recordings and distinguish their status."""

import json
from pathlib import Path

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
