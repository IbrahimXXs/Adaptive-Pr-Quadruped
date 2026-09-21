"""Paired, failure-preserving analysis of the separate matched-planner V2 study."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from primp_project.experiments.pad_study_v2 import (
    DEFAULT_STUDY_DIR, PLANNERS, _now, _sha, _write_json,
    validate_record, validate_v1_sources,
)
from .comparison import METRICS as BASE_METRICS, _number, _format


ADAPTATION_METRICS = (
    "fallback_active_time_s", "fallback_commanded_foot_descent_m",
    "fallback_commanded_com_travel_m", "fallback_active_plan_count",
    "minimum_unsupported_remaining_time_s", "missing_contact_planning_updates",
    "minimum_raw_model_remaining_time_s", "minimum_raw_recovery_remaining_time_s",
    "recovery_planning_updates", "learned_prior_active_plan_count", "learned_prior_active_plan_fraction",
    "positive_remaining_time_fraction", "positive_remaining_time_fraction_after_missing",
    "raw_model_positive_remaining_time_fraction", "raw_recovery_positive_remaining_time_fraction",
    "model_positive_remaining_time_fraction", "optimized_positive_remaining_time_fraction",
    "feasible_positive_remaining_time_fraction", "remaining_time_mae_to_confirmed_reload_s",
    "remaining_time_mae_after_missing_s", "lowering_initial_measured_foot_bottom_m",
    "actual_lowering_initial_foot_bottom_m", "actual_lowering_initial_com_z_m",
)
METRICS = BASE_METRICS+ADAPTATION_METRICS
CONTRASTS = (
    ("matched_learned", "matched_predictive"),
    ("matched_no_body_foot_correlation", "matched_learned"),
    ("matched_no_timing_adaptation", "matched_learned"),
    ("matched_no_noncontact_updates", "matched_learned"),
)


def raw_adaptation_metrics(run_dir, metadata):
    """Recompute actual fallback work and timing from recorded applied intervals.

    Fallback counters alone do not establish motion. The preceding sample owns
    the current command-difference interval, including interrupted segments.
    """
    with np.load(Path(run_dir)/"signals.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    required = ("control_time_s", "phase", "sensor_contact", "sensor_normal_force", "planner_update",
                "planner_fallback_active", "planner_foot_target_w", "planner_com_target_w",
                "planner_remaining_time_s", "model_remaining_time_s", "optimized_remaining_time_s",
                "feasible_remaining_time_s", "missing_contact", "feet_pos_w", "com_pos_w",
                "sensor_foot_pos_w", "raw_model_remaining_time_s", "planner_model_prior_active",
                "planner_recovery_active")
    absent = sorted(set(required)-data.keys())
    if absent:
        raise ValueError(f"Missing V2 comparison signals: {absent}")
    t = np.asarray(data["control_time_s"], dtype=float)
    if len(t) < 2 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("V2 comparison requires monotonic aligned samples")
    if any(len(data[name]) != len(t) for name in required):
        raise ValueError("V2 comparison signals are misaligned")
    landing = np.isin(data["phase"].astype(str), ["lower", "confirm"])
    loaded = data["sensor_contact"][:, 0].astype(bool) & (data["sensor_normal_force"][:, 0] >= 2.)
    updates = landing & ~loaded & data["planner_update"].astype(bool)
    missing = updates & data["missing_contact"].astype(bool)
    flags = data["planner_fallback_active"].astype(bool)
    prior = data["planner_model_prior_active"].astype(bool)
    recovery = updates & data["planner_recovery_active"].astype(bool)
    intervals = np.r_[False, flags[:-1] & landing[:-1] & landing[1:]]
    dt = np.r_[0., np.diff(t)]
    foot_descent = np.r_[0., np.maximum(0., -np.diff(data["planner_foot_target_w"][:, 2]))]
    body_travel = np.r_[0., np.linalg.norm(np.diff(data["planner_com_target_w"], axis=0), axis=1)]

    def fraction(signal, mask):
        values = np.asarray(data[signal])[mask]
        return float(np.mean(np.isfinite(values) & (values > 0))) if len(values) else None

    result = dict(
        fallback_active_time_s=float(dt[intervals].sum()),
        fallback_commanded_foot_descent_m=float(foot_descent[intervals].sum()),
        fallback_commanded_com_travel_m=float(body_travel[intervals].sum()),
        fallback_active_plan_count=int(np.count_nonzero(flags & updates)),
        minimum_unsupported_remaining_time_s=float(np.min(data["planner_remaining_time_s"][updates])) if np.any(updates) else None,
        minimum_raw_model_remaining_time_s=float(np.min(data["raw_model_remaining_time_s"][updates])) if np.any(updates) else None,
        minimum_raw_recovery_remaining_time_s=float(np.min(data["raw_model_remaining_time_s"][recovery])) if np.any(recovery) else None,
        recovery_planning_updates=int(np.count_nonzero(recovery)),
        learned_prior_active_plan_count=int(np.count_nonzero(prior & updates)),
        learned_prior_active_plan_fraction=float(np.mean(prior[updates])) if np.any(updates) else None,
        missing_contact_planning_updates=int(np.count_nonzero(missing)),
        positive_remaining_time_fraction=fraction("planner_remaining_time_s", updates),
        positive_remaining_time_fraction_after_missing=fraction("planner_remaining_time_s", missing),
        raw_model_positive_remaining_time_fraction=(fraction("raw_model_remaining_time_s", updates)
            if metadata["planner"] != "matched_predictive" else None),
        raw_recovery_positive_remaining_time_fraction=(fraction("raw_model_remaining_time_s", recovery)
            if metadata["planner"] != "matched_predictive" else None),
        model_positive_remaining_time_fraction=(fraction("model_remaining_time_s", updates)
            if metadata["planner"] != "matched_predictive" else None),
        optimized_positive_remaining_time_fraction=fraction("optimized_remaining_time_s", updates),
        feasible_positive_remaining_time_fraction=fraction("feasible_remaining_time_s", updates),
    )
    rows = np.flatnonzero(landing)
    if len(rows):
        first = int(rows[0])
        radius = float(metadata["foot_radius_m"])
        result.update(
            lowering_initial_measured_foot_bottom_m=float(data["sensor_foot_pos_w"][first, 2]-radius),
            lowering_initial_measured_com_w=data.get("sensor_com_pos_w", data["com_pos_w"])[first].tolist(),
            actual_lowering_initial_foot_bottom_m=float(data["feet_pos_w"][first, 0, 2]-radius),
            actual_lowering_initial_com_z_m=float(data["com_pos_w"][first, 2]),
        )
    reload_rows = np.flatnonzero(data["phase"].astype(str) == "reload")
    for key, mask in (("remaining_time_mae_to_confirmed_reload_s", updates),
                      ("remaining_time_mae_after_missing_s", missing)):
        result[key] = (float(np.mean(np.abs(data["planner_remaining_time_s"][mask]-(t[reload_rows[0]]-t[mask]))))
                       if len(reload_rows) and np.any(mask) else None)
    return result


def _median(rows, key):
    values = [row[key] for row in rows if row["passed"] and _number(row.get(key))]
    return float(np.median(values)) if values else None


def _paired(rows):
    indexed = {(row["planner"], row["actual_height_m"], row["seed"], row["initial_condition"]): row for row in rows}
    keys = sorted({(row["actual_height_m"], row["seed"], row["initial_condition"]) for row in rows})
    pairs, summaries = [], []
    for method, reference in CONTRASTS:
        contrast_rows = []
        for key in keys:
            a, b = indexed[(method, *key)], indexed[(reference, *key)]
            both = a["passed"] and b["passed"]
            differences = {metric: a[metric]-b[metric] if both and _number(a.get(metric)) and _number(b.get(metric)) else None
                           for metric in METRICS}
            pair = dict(method=method, reference=reference, actual_height_m=key[0], seed=key[1],
                        initial_condition=key[2], method_trial_id=a["trial_id"], reference_trial_id=b["trial_id"],
                        method_passed=a["passed"], reference_passed=b["passed"],
                        both_accepted=both, differences_method_minus_reference=differences)
            pairs.append(pair)
            contrast_rows.append(pair)
        medians = {}
        for metric in METRICS:
            values = [row["differences_method_minus_reference"][metric] for row in contrast_rows
                      if _number(row["differences_method_minus_reference"].get(metric))]
            medians[metric] = dict(median=float(np.median(values)) if values else None, paired_samples=len(values),
                                   method_lower=sum(value < 0 for value in values), equal=sum(value == 0 for value in values),
                                   method_higher=sum(value > 0 for value in values))
        summaries.append(dict(method=method, reference=reference, declared_pairs=len(keys),
                              both_accepted=sum(row["both_accepted"] for row in contrast_rows),
                              method_only_accepted=sum(row["method_passed"] and not row["reference_passed"] for row in contrast_rows),
                              reference_only_accepted=sum(row["reference_passed"] and not row["method_passed"] for row in contrast_rows),
                              paired_metric_differences=medians))
    return pairs, summaries


def write_comparison(study_dir=DEFAULT_STUDY_DIR, *, output_dir=None):
    directory = Path(study_dir).resolve()
    output = Path(output_dir) if output_dir is not None else directory/"comparison"
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = directory/"split_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    state = json.loads((directory/"study_state.json").read_text())
    if state["split_manifest_sha256"] != _sha(manifest_path):
        raise ValueError("V2 split manifest changed after trial bookkeeping")
    freeze_path = directory/"execution_freeze.json"
    frozen = json.loads(freeze_path.read_text()) if freeze_path.exists() else None
    errors, rows, detail = [], [], []
    try:
        inventory_path = directory/"v1_training_manifest.json"
        if manifest["v1_training_manifest_sha256"] != _sha(inventory_path):
            raise ValueError("Inherited V1 training inventory changed")
        validate_v1_sources(json.loads(inventory_path.read_text()))
    except (ValueError, OSError) as exc:
        errors.append(f"V1 training integrity: {exc}")
    if frozen:
        if frozen["split_manifest_sha256"] != _sha(manifest_path):
            errors.append("Execution freeze refers to another split manifest")
        for name, digest in frozen["model_files"].items():
            if not (directory/name).is_file() or _sha(directory/name) != digest:
                errors.append(f"Frozen model artifact changed: {name}")
    settings = {}
    for spec in manifest["evaluations"]:
        entry = state.get("trials", {}).get(spec["trial_id"], {})
        run = Path(entry["run_dir"]) if entry.get("run_dir") else None
        metadata, summary, raw, problem = {}, {}, {}, None
        if entry and (not frozen or entry.get("source_sha256") != frozen["source_sha256"]
                      or entry.get("model_files") != frozen["model_files"]):
            problem = "Attempt source/model differs from the execution freeze"
        if run:
            try:
                summary = validate_record(run, spec, entry)
                metadata = json.loads((run/"metadata.json").read_text())
                if int(metadata.get("validation_version", 0)) != 2:
                    raise ValueError("Matched evaluation requires V2 adaptation validation")
                if not frozen or entry.get("actual_source_sha256") != frozen["source_sha256"]:
                    raise ValueError("Trial lacks an attestation of the frozen execution source")
                for folder, field in (("model", "model_hashes_sha256"),
                                      ("recovery_model", "recovery_model_hashes_sha256")):
                    expected = {Path(name).name: digest for name, digest in frozen["model_files"].items()
                                if Path(name).parent.as_posix() == folder}
                    observed = metadata.get(field, {})
                    if any(observed.get(name) != digest for name, digest in expected.items()):
                        raise ValueError(f"Recorded {folder} hashes differ from frozen artifacts")
                raw = raw_adaptation_metrics(run, metadata)
                for name in ("fallback_active_time_s", "fallback_commanded_foot_descent_m", "fallback_commanded_com_travel_m",
                             "minimum_raw_model_remaining_time_s", "minimum_raw_recovery_remaining_time_s",
                             "recovery_planning_updates", "learned_prior_active_plan_count", "learned_prior_active_plan_fraction"):
                    value = summary.get("metrics", {}).get(name)
                    if value is None and raw[name] is None:
                        continue
                    if not _number(value) or not _number(raw[name]) or not np.isclose(value, raw[name], atol=1e-10, rtol=0):
                        raise ValueError(f"Saved {name} differs from independently reconstructed execution signals")
                settings[spec["trial_id"]] = {name: metadata.get(name) for name in (
                    "robot", "controller", "dt_s", "friction", "cycles", "hold_seconds", "foot_radius_m",
                    "contact_debounce_s", "max_search_depth_m", "contact_compression_m", "nominal_lower_duration_s")}
                settings[spec["trial_id"]]["mpc_frequency"] = metadata.get("simulation_params", {}).get("mpc_frequency")
            except (ValueError, OSError, KeyError) as exc:
                problem = str(exc)
        if problem:
            errors.append(f"{spec['trial_id']}: {problem}")
        attempted = bool(entry) and entry.get("status") != "running"
        passed = bool(attempted and entry.get("passed") and summary.get("passed") and problem is None)
        row = {key: spec[key] for key in ("trial_id", "planner", "actual_height_m", "initial_estimate_m",
                                          "sensor_profile", "seed", "initial_condition")}
        row.update(run_id=run.name if run else None, run_directory=str(run) if run else None,
                   attempted=attempted, passed=passed, status=entry.get("status", "not_run"),
                   error=problem or entry.get("error") or summary.get("runner_error"),
                   source_sha256=entry.get("source_sha256"), model_files=entry.get("model_files"),
                   requested_lift_height_m=metadata.get("requested_lift_height_m"))
        metrics = summary.get("metrics", {}) | raw
        row.update({name: metrics.get(name) if _number(metrics.get(name)) else None for name in METRICS})
        row["lowering_initial_measured_com_w"] = metrics.get("lowering_initial_measured_com_w")
        row["failed_criteria"] = [name for name, item in summary.get("criteria", {}).items() if item.get("passed") is not True]
        rows.append(row)
        detail.append(dict(trial_id=spec["trial_id"], parameters=spec, journal_entry=entry, summary=summary))
    if len({json.dumps(value, sort_keys=True) for value in settings.values()}) > 1:
        errors.append("Shared controller settings differ across V2 evaluation cells")
    aggregates = []
    for planner in PLANNERS:
        selected = [row for row in rows if row["planner"] == planner]
        attempted = sum(row["attempted"] for row in selected)
        aggregates.append(dict(planner=planner, planned=len(selected), attempted=attempted,
            successful=sum(row["passed"] for row in selected),
            success_fraction=sum(row["passed"] for row in selected)/attempted if attempted else None,
            success_only_metric_medians={name: _median(selected, name) for name in METRICS},
            success_only_metric_sample_counts={name: sum(row["passed"] and _number(row.get(name)) for row in selected) for name in METRICS},
            trials_with_fallback_motion=sum((_number(row.get("fallback_commanded_foot_descent_m"))
                                            and row["fallback_commanded_foot_descent_m"] > 1e-8) for row in selected)))
    pairs, contrasts = _paired(rows)
    report = dict(version=2, generated_at=_now(), study_directory=str(directory), protocol=manifest,
                  execution_freeze=frozen, expected_evaluations=len(rows),
                  attempted_evaluations=sum(row["attempted"] for row in rows),
                  successful_evaluations=sum(row["passed"] for row in rows),
                  missing_evaluations=[row["trial_id"] for row in rows if not row["attempted"]],
                  consistency_errors=errors, shared_controller_settings=settings,
                  aggregates=aggregates, paired_contrasts=contrasts, pairs=pairs, trials=rows, details=detail,
                  interpretation="Five matched variants across twelve paired height/seed/initial-condition cells. "
                  "Each ablation is compared with the complete learned variant; the complete learned variant is compared with matched predictive. "
                  "Failures and missing cells remain in coverage/success accounting. Metric differences require both paired trials to pass. "
                  "Three noise seeds and two initial clearances support descriptive repeatability checks, not an automatic superiority claim.",
                  fallback_convention="Actual applied fallback time and displacement are independently integrated with the preceding sample owning each interval. "
                  "Counts are reported separately and cannot substitute for active work.",
                  timing_convention="Positive remaining-time fractions use unsupported planning updates. MAE compares the proposed remaining time with measured time to confirmed reload, "
                  "including confirmation dwell; it is an execution calibration diagnostic, not a prospective statistical guarantee.")
    _write_json(output/"comparison.json", report)
    with (output/"comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    with (output/"paired_differences.csv").open("w", newline="") as stream:
        flat = [{key: value for key, value in pair.items() if key != "differences_method_minus_reference"}
                | {f"delta_{key}": value for key, value in pair["differences_method_minus_reference"].items()} for pair in pairs]
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader(); writer.writerows(flat)
    _markdown(output, report)
    _plot(output, report)
    return report


def _markdown(output, report):
    lines = ["# V2 matched-planner comparison", "", report["interpretation"], "",
             f"Coverage: **{report['attempted_evaluations']}/{report['expected_evaluations']}**; "
             f"accepted: **{report['successful_evaluations']}**.", "",
             "| Variant | Accepted / attempted / planned | Median peak (N) | Median lower-to-completion (s) | Median fallback time (s) | Median fallback descent (mm) | Positive remaining-time fraction |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in report["aggregates"]:
        m = item["success_only_metric_medians"]
        descent = m["fallback_commanded_foot_descent_m"]
        lines.append(f"| {item['planner']} | {item['successful']}/{item['attempted']}/{item['planned']} | "
                     f"{_format(m['peak_normal_force_first_100ms_n'])} | {_format(m['lowering_to_completion_s'])} | "
                     f"{_format(m['fallback_active_time_s'])} | {_format(descent*1000 if descent is not None else None)} | "
                     f"{_format(m['positive_remaining_time_fraction'])} |")
    lines += ["", "Medians use accepted trials only; JSON records every sample count and paired success outcome.", "",
              "| Variant | Raw model time positive fraction | Raw recovery time positive fraction | Median minimum raw recovery time (s) | Median learned-prior use fraction |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for item in report["aggregates"]:
        m = item["success_only_metric_medians"]
        raw = m['minimum_raw_recovery_remaining_time_s'] if item['planner'] != 'matched_predictive' else None
        lines.append(f"| {item['planner']} | {_format(m['raw_model_positive_remaining_time_fraction'])} | "
                     f"{_format(m['raw_recovery_positive_remaining_time_fraction'])} | {_format(raw)} | "
                     f"{_format(m['learned_prior_active_plan_fraction'])} |")
    lines += ["", "Raw model timing is measured before feasibility floors; the conventional baseline has no learned-model timing.", "",
              "| Paired contrast | Accepted pairs | Median completion-time difference (s) | Median fallback-time difference (s) |",
              "| --- | ---: | ---: | ---: |"]
    for pair in report["paired_contrasts"]:
        m = pair["paired_metric_differences"]
        lines.append(f"| {pair['method']} minus {pair['reference']} | {pair['both_accepted']}/{pair['declared_pairs']} | "
                     f"{_format(m['lowering_to_completion_s']['median'])} | {_format(m['fallback_active_time_s']['median'])} |")
    lines += ["", "The CSV files contain every trial and each paired metric difference. "
              "Actual initial foot and CoM states are included alongside nominal/raised labels.", "",
              report["fallback_convention"], "", report["timing_convention"], "",
              "| Trial | Initial condition | Seed | Accepted | Recording |", "| --- | --- | ---: | --- | --- |"]
    for row in report["trials"]:
        label = "PASS" if row["passed"] else "FAIL" if row["attempted"] else "NOT RUN"
        link = "—"
        if row["run_directory"]:
            relative = Path(os.path.relpath(Path(row["run_directory"])/"pad_report.md", output)).as_posix()
            link = f"[{row['run_id']}](<{relative}>)"
        lines.append(f"| {row['trial_id']} | {row['initial_condition']} | {row['seed']} | {label} | {link} |")
    if report["consistency_errors"]:
        lines += ["", "Consistency errors:", "", *[f"- {value}" for value in report["consistency_errors"]]]
    lines += ["", "![V2 comparison](comparison.png)", "",
              "No ranking is assigned automatically. Inspect paired differences, failure coverage, initial states, and remaining-time calibration before drawing conclusions."]
    (output/"comparison.md").write_text("\n".join(lines)+"\n")


def _plot(output, report):
    labels = ("Predictive", "Learned", "No body/foot\ncorrelation", "No timing\nadaptation", "No noncontact\nupdates")
    metrics = (("peak_normal_force_first_100ms_n", "Peak landing reaction (N)"),
               ("lowering_to_completion_s", "Lowering to completion (s)"),
               ("fallback_active_time_s", "Applied fallback time (s)"),
               ("remaining_time_mae_to_confirmed_reload_s", "Remaining-time MAE (s)"))
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    for ax, (metric, title) in zip(axes.ravel(), metrics, strict=True):
        for index, planner in enumerate(PLANNERS):
            for condition, marker, shift in (("nominal", "o", -.1), ("raised", "^", .1)):
                values = [row[metric] for row in report["trials"] if row["planner"] == planner
                          and row["initial_condition"] == condition and row["passed"] and _number(row.get(metric))]
                ax.scatter(np.full(len(values), index+shift), values, marker=marker,
                           alpha=.7, label=condition if index == 0 else None)
        ax.set(title=title, xticks=np.arange(len(PLANNERS)), xticklabels=labels)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle(f"V2 matched variants · {report['successful_evaluations']}/{report['expected_evaluations']} accepted · paired conditions")
    fig.savefig(output/"comparison.png", dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_dir", type=Path, nargs="?", default=DEFAULT_STUDY_DIR)
    args = parser.parse_args(argv)
    result = write_comparison(args.study_dir)
    return 0 if not result["consistency_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
