"""Descriptive, failure-preserving comparison of the predeclared landing pilot."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from primp_project import RESULTS_ROOT


METRICS = (
    "peak_normal_force_first_100ms_n", "normal_impulse_first_100ms_ns",
    "maximum_roll_pitch_change_during_landing_deg",
    "maximum_com_reference_error_during_landing_m",
    "lowering_to_touchdown_s", "lowering_to_completion_s", "completion_time_s",
    "height_belief_error_at_contact_confirmation_m", "planner_mean_compute_time_s",
    "planner_maximum_compute_time_s", "reference_projection_count", "planner_fallback_count",
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_json(path):
    return json.loads(Path(path).read_text())


def _number(value):
    return bool(isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value))


def _median(rows, metric):
    values = [row[metric] for row in rows if row["passed"] and _number(row.get(metric))]
    return float(np.median(values)) if values else None


def _format(value, digits=3):
    return f"{value:.{digits}f}" if _number(value) else "—"


def write_comparison(study_dir, *, output_dir=None):
    """Report all declared evaluation cells, including errors and missing runs.

    Success denominators use completed attempts; a separate coverage count
    makes unrun cells explicit. Metric summaries use successful trials only
    and always show their sample counts. No hypothesis test or winner is inferred.
    """
    study_dir = Path(study_dir).resolve()
    output_dir = Path(output_dir) if output_dir is not None else study_dir/"comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = study_dir/"split_manifest.json"
    manifest = _read_json(manifest_path)
    state = _read_json(study_dir/"study_state.json")
    if state.get("split_manifest_sha256") != _sha(manifest_path):
        raise ValueError("Split manifest was changed after trial bookkeeping began")
    rows, detail, controller_settings, consistency_errors = [], [], {}, []
    for spec in manifest["evaluations"]:
        trial_id = spec["trial_id"]
        entry = state.get("trials", {}).get(trial_id, {})
        run_dir = Path(entry["run_dir"]) if entry.get("run_dir") else None
        summary, metadata, read_error = {}, {}, None
        if run_dir is not None:
            try:
                summary = _read_json(run_dir/"pad_summary.json")
                metadata = _read_json(run_dir/"metadata.json")
                for key, name in (("summary_sha256", "pad_summary.json"),
                                  ("metadata_sha256", "metadata.json"), ("signals_sha256", "signals.npz")):
                    if entry.get(key) and entry[key] != _sha(run_dir/name):
                        raise ValueError(f"{name} hash differs from completed attempt")
            except (ValueError, OSError) as exc:
                read_error = str(exc)
                consistency_errors.append(f"{trial_id}: {read_error}")
        attempted = bool(entry) and entry.get("status") != "running"
        passed = bool(attempted and entry.get("passed") and summary.get("passed") and read_error is None)
        failed_checks = [name for name, item in summary.get("criteria", {}).items()
                         if isinstance(item, dict) and item.get("passed") is not True]
        row = dict(trial_id=trial_id, run_id=run_dir.name if run_dir else None,
                   planner=spec["planner"], actual_height_m=spec["actual_height_m"],
                   initial_estimate_m=spec["initial_estimate_m"], sensor_profile=spec["sensor_profile"],
                   seed=spec["seed"], status=entry.get("status", "not_run"), attempted=attempted,
                   passed=passed, run_directory=str(run_dir) if run_dir else None,
                   error=read_error or entry.get("error") or summary.get("runner_error"),
                   failed_criteria="; ".join(failed_checks), source_sha256=entry.get("source_sha256"),
                   model_sha256=entry.get("model_sha256"))
        metrics = summary.get("metrics", {})
        row.update({name: metrics.get(name) if _number(metrics.get(name)) else None for name in METRICS})
        row["observed_contact_timing"] = metrics.get("observed_contact_timing")
        row["missing_contact_observed"] = metrics.get("missing_contact_observed")
        rows.append(row)
        detail.append(dict(trial_id=trial_id, declared_parameters=spec, journal_entry=entry, summary=summary))
        if metadata:
            controller_settings[trial_id] = {name: metadata.get(name) for name in (
                "robot", "controller", "dt_s", "friction", "cycles", "hold_seconds", "foot_radius_m",
                "contact_debounce_s", "max_search_depth_m", "contact_compression_m", "nominal_lower_duration_s")}
            controller_settings[trial_id]["mpc_frequency"] = metadata.get("simulation_params", {}).get("mpc_frequency")
    planners = list(dict.fromkeys(spec["planner"] for spec in manifest["evaluations"]))
    aggregates = []
    for planner in planners:
        planner_rows = [row for row in rows if row["planner"] == planner]
        attempted = sum(row["attempted"] for row in planner_rows)
        successful = sum(row["passed"] for row in planner_rows)
        medians = {name: _median(planner_rows, name) for name in METRICS}
        counts = {name: sum(row["passed"] and _number(row.get(name)) for row in planner_rows) for name in METRICS}
        fallback_rows = [row for row in planner_rows if row["attempted"] and _number(row.get("planner_fallback_count"))]
        aggregates.append(dict(planner=planner, planned=len(planner_rows), attempted=attempted,
                               successful=successful, success_fraction=successful/attempted if attempted else None,
                               trials_with_recorded_fallback_count=len(fallback_rows),
                               trials_with_fallback=sum(row["planner_fallback_count"] > 0 for row in fallback_rows),
                               total_fallback_updates=int(sum(row["planner_fallback_count"] for row in fallback_rows)),
                               success_only_metric_medians=medians, success_only_metric_sample_counts=counts))
    signatures = {json.dumps(value, sort_keys=True) for value in controller_settings.values()}
    source_hashes = sorted({row["source_sha256"] for row in rows if row["source_sha256"]})
    if len(signatures) > 1:
        consistency_errors.append("Execution-controller settings differ across recorded evaluation trials")
    if len(source_hashes) > 1:
        consistency_errors.append("Evaluation attempts used different source fingerprints")
    if "held_out_heights" in manifest.get("study", ""):
        height_scope = ("The ±7.5 mm heights were predeclared before these trials and were excluded from demonstration fitting "
                        "and live engineering development. Sensing is clean. The original trained model and the controller/source "
                        "from the paired eighteen-cell pilot remain fixed; no refitting uses these six trials. ")
    else:
        height_scope = ("The ±5 mm heights were excluded from demonstration fitting but were exercised during reactive-controller development; "
                        "they are training-held-out heights, not untouched engineering test cases. "
                        "Noisy/delayed sensing is reserved for evaluation and is excluded from demonstration fitting and development. "
                        "The 0 mm height is a calibration condition. ")
    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(), study_directory=str(study_dir),
        split_manifest_sha256=_sha(manifest_path), protocol=manifest,
        expected_evaluations=len(rows), attempted_evaluations=sum(row["attempted"] for row in rows),
        successful_evaluations=sum(row["passed"] for row in rows),
        missing_evaluations=[row["trial_id"] for row in rows if not row["attempted"]],
        consistency_errors=consistency_errors, shared_controller_settings=controller_settings,
        source_fingerprints=source_hashes, model=state.get("model"),
        aggregates=aggregates, trials=rows, details=detail,
        interpretation=("Descriptive pilot with one seed and one attempt per planner/height/sensing cell. "
                        +height_scope+
                        "Failed and missing cells remain visible. Impact and completion summaries below use successful trials only, "
                        "so compare them alongside success and coverage. These data do not establish statistical superiority."),
        impact_convention="Measured simulated pad-normal reaction during the first 100 ms after physical contact, including static load.",
        body_convention="Roll/pitch change from lowering entry; intentional body motion contributes. CoM reference error is separately recorded.",
    )
    (output_dir/"comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    with (output_dir/"comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["trial_id"])
        writer.writeheader()
        writer.writerows(rows)
    _markdown(output_dir, report)
    _plot(output_dir, report)
    return report


def _markdown(output_dir, report):
    lines = ["# Landing-pad planner comparison", "", report["interpretation"], "",
             f"Coverage: **{report['attempted_evaluations']}/{report['expected_evaluations']}** declared evaluation cells attempted; "
             f"**{report['successful_evaluations']}** accepted trials.", "",
             "The CSV contains every declared cell. JSON includes the split, model provenance, raw acceptance summaries, and consistency checks.", "",
             "| Planner | Accepted / attempted / planned | Median impact peak (N) | Median tilt change (deg) | Median lowering-to-completion (s) | Median fallback updates | Trials using fallback |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in report["aggregates"]:
        metrics = item["success_only_metric_medians"]
        lines.append(f"| {item['planner']} | {item['successful']} / {item['attempted']} / {item['planned']} | "
                     f"{_format(metrics['peak_normal_force_first_100ms_n'])} | "
                     f"{_format(metrics['maximum_roll_pitch_change_during_landing_deg'])} | "
                     f"{_format(metrics['lowering_to_completion_s'])} | "
                     f"{_format(metrics['planner_fallback_count'], 1)} | "
                     f"{item['trials_with_fallback']} / {item['trials_with_recorded_fallback_count']} |")
    lines += ["", "Metric medians include accepted trials only. The JSON records the sample count for every metric.", "",
              "Fallback counts identify departures from a planner's nominal motion: learned-motion fallback extends descent after model phase 1; "
              "predictive-planner fallback handles optimization failure. Native contact-triggered recovery in the other planners is not counted as learned-motion fallback.", ""]
    learned = next((item for item in report["aggregates"] if item["planner"] == "learned"), None)
    if learned is not None:
        lines += [f"The learned planner used bounded fallback in **{learned['trials_with_fallback']} / "
                  f"{learned['trials_with_recorded_fallback_count']}** trials with recorded counts "
                  f"(**{learned['total_fallback_updates']} planning updates** total). Success therefore includes the common recovery behavior when invoked.", ""]
    lines += ["| Planner | Height (mm) | Sensing | Accepted | Impact peak (N) | Tilt change (deg) | Lowering-to-completion (s) | Fallback updates | Recording |",
              "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for row in report["trials"]:
        status = "PASS" if row["passed"] else "FAIL" if row["attempted"] else "NOT RUN"
        run = row["run_id"] or "—"
        if row["run_directory"]:
            # Relative links keep the results folder portable.
            import os
            relative = Path(os.path.relpath(Path(row['run_directory'])/'pad_report.md', output_dir)).as_posix()
            run = f"[{run}](<{relative}>)"
        lines.append(f"| {row['planner']} | {1000*row['actual_height_m']:+g} | {row['sensor_profile']} | {status} | "
                     f"{_format(row['peak_normal_force_first_100ms_n'])} | "
                     f"{_format(row['maximum_roll_pitch_change_during_landing_deg'])} | "
                     f"{_format(row['lowering_to_completion_s'])} | "
                     f"{_format(row['planner_fallback_count'], 0)} | {run} |")
    failures = [row for row in report["trials"] if row["attempted"] and not row["passed"]]
    if failures:
        lines += ["", "Failed attempts remain part of the comparison:", ""]
        lines.extend(f"- `{row['trial_id']}`: {row['error'] or row['failed_criteria'] or 'Acceptance failed; inspect the recording.'}"
                     for row in failures)
    if report["consistency_errors"]:
        lines += ["", "Comparison consistency checks:", ""]
        lines.extend(f"- {error}" for error in report["consistency_errors"])
    lines += ["", report["impact_convention"], "", report["body_convention"], "",
              "![Pilot comparison](comparison.png)", "",
              "No planner ranking is inferred from this small pilot. Broader repetitions and predeclared held-out conditions are needed before making performance claims."]
    (output_dir/"comparison.md").write_text("\n".join(lines)+"\n")


def _plot(output_dir, report):
    planners = [item["planner"] for item in report["aggregates"]]
    positions = np.arange(len(planners))
    colors = ["#356a9a", "#c38332", "#50835e"][:len(planners)]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    ax = axes[0, 0]
    fractions = [item["success_fraction"] if item["success_fraction"] is not None else 0.
                 for item in report["aggregates"]]
    ax.bar(positions, fractions, color=colors)
    ax.set_ylim(0, 1.15)
    ax.set(title="Acceptance and coverage", ylabel="Accepted / attempted")
    for x, item in zip(positions, report["aggregates"]):
        ax.text(x, fractions[x]+.025, f"{item['successful']}/{item['attempted']} ({item['planned']} planned)", ha="center", fontsize=9)
    charts = [(axes[0, 1], "peak_normal_force_first_100ms_n", "Landing impact", "Peak pad normal force (N)"),
              (axes[1, 0], "maximum_roll_pitch_change_during_landing_deg", "Body disturbance", "Maximum roll/pitch change (deg)"),
              (axes[1, 1], "lowering_to_completion_s", "Completion time", "Lowering start to completion (s)")]
    for ax, metric, title, ylabel in charts:
        for x, planner in enumerate(planners):
            rows = [row for row in report["trials"] if row["planner"] == planner and row["passed"] and _number(row.get(metric))]
            for sensor, marker, shift in (("clean", "o", -.1), ("noisy_delayed", "^", .1)):
                values = [row[metric] for row in rows if row["sensor_profile"] == sensor]
                if values:
                    ax.scatter(np.full(len(values), x+shift), values, marker=marker, color=colors[x],
                               alpha=.8, label=sensor if x == 0 else None)
            median = _median(rows, metric)
            if median is not None:
                ax.hlines(median, x-.28, x+.28, color="black", linewidth=2)
        ax.set(title=title+" (accepted trials)", ylabel=ylabel)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=8)
    for ax in axes.ravel():
        ax.set_xticks(positions, planners)
        ax.grid(axis="y", alpha=.2)
    fig.suptitle("Landing-pad pilot · fixed seed · descriptive comparison")
    fig.savefig(output_dir/"comparison.png", dpi=170)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project compare-pad", description=__doc__)
    parser.add_argument("study_dir", type=Path, nargs="?", default=RESULTS_ROOT/"landing_pad"/"study")
    args = parser.parse_args(argv)
    report = write_comparison(args.study_dir)
    print(f"Comparison: {args.study_dir/'comparison'/'comparison.md'}")
    return 0 if not report["consistency_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
