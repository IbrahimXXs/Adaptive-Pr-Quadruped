"""Discover experiment recordings and maintain their lightweight result index.

Only metadata and analysis summaries are read. Regenerating the index never
rewrites a recording, its reports, or its historical source snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path

from primp_project import PROJECT_ROOT


GROUPS = ("standing", "controlled_step", "landing_pad", "archive")


def _pointer_ids(group: Path, filename: str) -> set[str]:
    path = group / filename
    if not path.is_file():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def _read_json(path: Path) -> tuple[dict, str | None]:
    if not path.is_file():
        return {}, None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value, None
    except (OSError, ValueError) as exc:
        return {}, f"Cannot read {path.name}: {exc}"


def _number(value: object) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _record(run: Path, root: Path, canonical: set[str], latest: set[str], annotation: dict) -> dict:
    metadata, metadata_error = _read_json(run / "metadata.json")
    is_pad = metadata.get("experiment") == "landing_pad" or (run / "pad_summary.json").is_file()
    is_step = metadata.get("experiment") == "controlled_step" or run.name.startswith("step_")
    is_motion = is_step or is_pad
    # Pad reports add terrain/contact checks to step validation. A passing
    # underlying step report must never conceal missing/failing pad validation.
    summary_name = "pad_summary.json" if is_pad else "step_summary.json" if is_step else "summary.json"
    summary, summary_error = _read_json(run / summary_name)
    metrics = summary.get("metrics", {})
    notes = [error for error in (metadata_error, summary_error) if error]
    notes.extend(annotation.get("notes", []))
    runner_status = metadata.get("status", "unknown")
    if runner_status in {"failed", "error", "interrupted", "aborted"} or metadata.get("error"):
        status = "FAIL"
    elif summary.get("passed") is False:
        status = "FAIL"
    elif summary.get("passed") is True and runner_status == "completed":
        status = "PASS"
    else:
        status = "UNANALYZED"
    samples = _number(metrics.get("sample_count", metadata.get("recorded_steps")))
    duration = _number(metrics.get("duration_s", metrics.get("recorded_duration_s")))
    if duration is None and samples is not None:
        dt = _number(metadata.get("dt_s"))
        if dt is not None:
            duration = samples * dt
    links = {}
    candidates = {
        "report": "pad_report.md" if is_pad else "step_report.md" if is_step else "REPORT.md",
        "plot": "pad_overview.png" if is_pad else "step_overview.png" if is_step else "overview.png",
        "summary": summary_name,
        "npz": "signals.npz",
        "csv": "samples.csv",
        "config": "metadata.json",
        "contact_events": "contact_events.csv",
        "phase_events": "phase_events.json",
        "source_patch": "source_changes.patch",
        "source_snapshot": "source",
        "scene": "scene/scene.xml",
        "evaluation_truth": "scene/evaluation_truth.json",
    }
    for key, name in candidates.items():
        path = run / name
        if path.exists():
            links[key] = path.relative_to(root).as_posix()
    return {
        "id": run.name,
        "path": run.relative_to(root).as_posix(),
        "group": run.relative_to(root).parts[0],
        "purpose": annotation.get("purpose") or metadata.get("purpose") or "Recorded experiment",
        "canonical": run.name in canonical,
        "latest": run.name in latest,
        "experiment": "landing_pad" if is_pad else "controlled_step" if is_step else "standing",
        "status": status,
        "runner_status": runner_status,
        "created_utc": metadata.get("created_utc"),
        "duration_s": duration,
        "samples": samples,
        "cycles": metadata.get("actual_completed_cycles", summary.get("actual_completed_cycles")) if is_motion else None,
        "requested_cycles": metadata.get("cycles") if is_motion else None,
        "hold_seconds": metadata.get("hold_seconds") if is_motion else None,
        "standing_seconds": metadata.get("standing_duration_s") if not is_motion else None,
        "settling_seconds": metadata.get("settling_duration_s") if not is_motion else None,
        "role": metadata.get("role"),
        "planner": metadata.get("planner"),
        "initial_height_estimate_m": metadata.get("initial_height_estimate_m"),
        "actual_pad_height_m": metadata.get("evaluation", {}).get("actual_pad_height_m"),
        "sensor_profile": metadata.get("sensor_profile"),
        "friction": metadata.get("friction"),
        "rendered": metadata.get("rendered"),
        "links": links,
        "notes": notes,
    }


def _format_number(value: object, suffix: str = "") -> str:
    number = _number(value)
    return f"{number:g}{suffix}" if number is not None else "—"


def _markdown(records: list[dict]) -> str:
    lines = [
        "# Recorded experiments",
        "",
        "This index is generated from each recording's metadata and saved analysis summary. "
        "PASS means that run passed its recorded acceptance checks; the duration and conditions "
        "below define what was tested. UNANALYZED means a completed passing analysis is unavailable.",
        "",
        "**Start with the canonical standing and controlled-step baselines.** "
        "`CANONICAL.txt` selects a group's reference recording; `LATEST.txt` identifies its most "
        "recent recording and does not imply that it passed. New runs are saved in their experiment "
        "group and added to this index automatically.",
        "",
        "The archive retains completed smoke and development runs for provenance. "
        "Historical metadata, raw signals, events, patches, and source snapshots are preserved "
        "as recorded; old paths within them describe the layout at recording time. "
        "No archived run is counted toward a later milestone merely because its own checks passed.",
        "",
        "Machine-readable inventory: [catalog.json](catalog.json). "
        "Refresh or list recordings with `python -m primp_project results` from the repository root.",
        "",
        "Human-readable purposes and historical notes live in `annotations.json`, keyed by "
        "recording ID. Edit that file to label a recording without changing its original "
        "metadata; an annotation takes precedence over a purpose saved in metadata.",
    ]
    labels = {"standing": "Standing", "controlled_step": "Controlled step", "landing_pad": "Adjustable landing pad", "archive": "Archive"}
    for group in GROUPS:
        selected = [record for record in records if record["group"] == group]
        lines.extend(["", f"## {labels[group]}", ""])
        if not selected:
            lines.append("No recordings yet.")
            continue
        lines.extend([
            "| Recording / purpose | Result | Duration | Samples | Conditions | Files |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ])
        for record in selected:
            flags = []
            if record["canonical"]:
                flags.append("**canonical**")
            if record["latest"]:
                flags.append("latest")
            flag_text = f" · {', '.join(flags)}" if flags else ""
            purpose = f"[{record['id']}]({record['path']}/)<br>{record['purpose']}{flag_text}"
            viewer = "viewer on" if record["rendered"] is True else "headless" if record["rendered"] is False else "viewer unknown"
            conditions = [viewer]
            if record["experiment"] == "landing_pad":
                sensors = record["sensor_profile"]
                if isinstance(sensors, dict):
                    sensors = sensors.get("name", "unspecified")
                conditions.extend([
                    str(record["planner"] or "planner unspecified"),
                    str(record["role"] or "role unspecified"),
                    f"actual z={_format_number(record['actual_pad_height_m'], ' m')}",
                    f"estimate z={_format_number(record['initial_height_estimate_m'], ' m')}",
                    f"sensors: {sensors or 'unspecified'}",
                ])
            elif record["experiment"] == "controlled_step":
                cycle_label = "cycle" if record["cycles"] == 1 else "cycles"
                conditions.extend([
                    f"{_format_number(record['cycles'])} {cycle_label}",
                    f"{_format_number(record['hold_seconds'], ' s')} hold",
                    f"μ={_format_number(record['friction'])}",
                ])
            else:
                conditions.append(f"{_format_number(record['standing_seconds'], ' s')} standing + {_format_number(record['settling_seconds'], ' s')} settling")
            files = " · ".join(
                f"[{label}]({record['links'][key]})"
                for key, label in (("report", "report"), ("plot", "plot"), ("npz", "NPZ"), ("csv", "CSV"), ("config", "config"))
                if key in record["links"]
            )
            sample_text = f"{record['samples']:,}" if record["samples"] is not None else "—"
            lines.append(f"| {purpose} | **{record['status']}** | {_format_number(record['duration_s'], ' s')} | {sample_text} | {'; '.join(conditions)} | {files} |")
        notes = [(record, note) for record in selected for note in record["notes"]]
        if notes:
            lines.append("")
            lines.extend(f"- `{record['id']}`: {note}" for record, note in notes)
    lines.extend([
        "",
        "Each recording directory keeps its raw `signals.npz` and `samples.csv`, configuration in "
        "`metadata.json`, contact events, and its analysis report and plot. Controlled-step runs "
        "also include phase events and source snapshots. Landing-pad runs add pad-specific "
        "reports, sensor/planner signals, and simulator-only terrain truth. Demonstration and "
        "evaluation recordings are indexed recursively within their study folders. Test and console logs are organized "
        "separately under `primp_project/artifacts/`.",
        "",
    ])
    return "\n".join(lines)


def refresh_catalog(results_root: Path | str | None = None) -> list[dict]:
    """Index recordings, writing only catalog.json and README.md in results_root."""
    root = Path(results_root) if results_root is not None else PROJECT_ROOT / "results"
    annotations, annotation_error = _read_json(root / "annotations.json")
    if annotation_error:
        raise ValueError(annotation_error)
    records = []
    for name in GROUPS:
        group = root / name
        for metadata in sorted(group.rglob("metadata.json")):
            relative = metadata.parent.relative_to(group)
            # Source snapshots and scene/model artifacts are not recordings.
            if not relative.parts or any(part in {"source", "scene", "model", "models"} for part in relative.parts):
                continue
            canonical, latest = set(), set()
            parent = metadata.parent.parent
            while parent == group or group in parent.parents:
                for filename, selected in (("CANONICAL.txt", canonical), ("LATEST.txt", latest)):
                    pointers = _pointer_ids(parent, filename)
                    if metadata.parent.name in pointers or metadata.parent.relative_to(parent).as_posix() in pointers:
                        selected.add(metadata.parent.name)
                if parent == group:
                    break
                parent = parent.parent
            annotation = annotations.get(metadata.parent.name, {})
            if not isinstance(annotation, dict):
                raise ValueError(f"Annotation for {metadata.parent.name} must be a JSON object")
            notes = annotation.get("notes", [])
            if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
                raise ValueError(f"Annotation notes for {metadata.parent.name} must be a list of strings")
            records.append(_record(metadata.parent, root, canonical, latest, annotation))
    root.mkdir(parents=True, exist_ok=True)
    (root / "catalog.json").write_text(json.dumps(records, indent=2, allow_nan=False) + "\n")
    (root / "README.md").write_text(_markdown(records))
    return records


def list_results(results_root: Path | str | None = None) -> int:
    """Refresh the inventory and print a compact listing for the project CLI."""
    records = refresh_catalog(results_root)
    for record in records:
        tags = ", ".join(tag for tag in ("canonical" if record["canonical"] else "", "latest" if record["latest"] else "") if tag)
        suffix = f" [{tags}]" if tags else ""
        print(f"{record['status']:10} {record['path']} — {record['purpose']}{suffix}")
    print(f"{len(records)} recording(s); see results/README.md for reports, plots, and data.")
    return 0
