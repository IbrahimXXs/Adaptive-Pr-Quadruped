"""Read-only V2 audit of unclipped learned timing, applied timing and fallback.

This audit does not fit models, rerun controllers, or change trial acceptance.
Forecast discrepancies compare each recorded planning tick with its subsequently
realized time to confirmed reload. Replanning and contact gates affect that
outcome, so these are descriptive closed-loop forecast errors, not independent
calibration samples or counterfactual execution of a frozen prediction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


TIME_SIGNALS = ("raw_model_remaining_time_s", "model_remaining_time_s",
                "optimized_remaining_time_s", "feasible_remaining_time_s", "planner_remaining_time_s")
PRIMARY = "matched_learned"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return dict(count=0, minimum=None, median=None, mean=None, maximum=None)
    return dict(count=len(values), minimum=float(values.min()), median=float(np.median(values)),
                mean=float(values.mean()), maximum=float(values.max()))


def error_stats(predicted, actual):
    predicted, actual = np.asarray(predicted), np.asarray(actual)
    if not len(actual):
        return dict(planning_ticks=0, mean_error_s=None, mean_absolute_error_s=None,
                    median_absolute_error_s=None, root_mean_square_error_s=None, maximum_absolute_error_s=None)
    error = predicted-actual
    return dict(planning_ticks=len(error), mean_error_s=float(error.mean()),
                mean_absolute_error_s=float(np.abs(error).mean()),
                median_absolute_error_s=float(np.median(np.abs(error))),
                root_mean_square_error_s=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error_s=float(np.abs(error).max()))


def snapshot(data, index, reload_time, radius, lower_start):
    if index is None:
        return None
    time = float(data["control_time_s"][index])
    row = dict(sample=int(index), time_s=time, seconds_since_lower=time-lower_start,
        actual_remaining_to_confirmed_reload_s=None if reload_time is None else reload_time-time,
        missing_contact=bool(data["missing_contact"][index]), recovery_active=bool(data["planner_recovery_active"][index]),
        prior_active=bool(data["planner_model_prior_active"][index]),
        belief_support_mass=float(data["planner_belief_support_mass"][index]),
        fallback_active=bool(data["planner_fallback_active"][index]), fallback_reason=str(data["planner_fallback_reason"][index]),
        belief_mean_m=float(data["belief_mean_m"][index]), belief_std_m=float(data["belief_std_m"][index]),
        current_geometric_phase=float(data["planner_current_state_phase"][index]),
        measured_foot_bottom_m=float(data["sensor_foot_pos_w"][index, 2]-radius),
        measured_com_z_m=float(data["sensor_com_pos_w"][index, 2]),
        proposed_com_z_m=float(data["planner_proposed_com_w"][index, 2]),
        applied_com_z_m=float(data["planner_com_target_w"][index, 2]),
        proposed_foot_z_m=float(data["planner_proposed_foot_w"][index, 2]),
        applied_foot_z_m=float(data["planner_foot_target_w"][index, 2]))
    row.update({name: float(data[name][index]) for name in TIME_SIGNALS})
    return row


def fallback_intervals(data):
    """Integrate left-endpoint fallback flags over applied control intervals."""
    time = data["control_time_s"]
    landing = np.isin(data["phase"].astype(str), ["lower", "confirm"])
    flags = data["planner_fallback_active"].astype(bool)
    reasons = data["planner_fallback_reason"].astype(str)
    indexes = np.flatnonzero(flags[:-1] & landing[:-1] & landing[1:])+1
    intervals = []
    for i in indexes:
        left = i-1
        reason = str(reasons[left])
        if not intervals or intervals[-1]["end_sample"] != left or intervals[-1]["reason"] != reason:
            intervals.append(dict(start_sample=int(left), end_sample=int(left),
                start_time_s=float(time[left]), end_time_s=float(time[left]), reason=reason,
                active_time_s=0., commanded_foot_descent_m=0., commanded_com_travel_m=0., planning_updates=0))
        current = intervals[-1]
        current["end_sample"], current["end_time_s"] = int(i), float(time[i])
        current["active_time_s"] += float(time[i]-time[left])
        current["commanded_foot_descent_m"] += max(0., float(data["planner_foot_target_w"][left, 2]-data["planner_foot_target_w"][i, 2]))
        current["commanded_com_travel_m"] += float(np.linalg.norm(data["planner_com_target_w"][i]-data["planner_com_target_w"][left]))
        current["planning_updates"] += int(data["planner_update"][left])
    integrated = dict(active_time_s=sum(x["active_time_s"] for x in intervals),
        commanded_foot_descent_m=sum(x["commanded_foot_descent_m"] for x in intervals),
        commanded_com_travel_m=sum(x["commanded_com_travel_m"] for x in intervals))
    signals = dict(active_time_s="fallback_interval_s", commanded_foot_descent_m="fallback_foot_descent_m",
                   commanded_com_travel_m="fallback_com_travel_m")
    differences = {key: float(integrated[key]-np.sum(data[value])) for key, value in signals.items()}
    if any(abs(difference) > 1e-9 for difference in differences.values()):
        raise ValueError(f"Recorded fallback work differs from applied-reference integration: {differences}")
    return intervals, dict(integrated, recorded_minus_recomputed_max_abs_error=max(map(abs, differences.values()), default=0.))


def audit_run(run_dir, spec, entry=None):
    run_dir = Path(run_dir)
    files = {"signals_sha256": run_dir/"signals.npz", "metadata_sha256": run_dir/"metadata.json",
             "summary_sha256": run_dir/"pad_summary.json"}
    hashes = {key: sha(path) for key, path in files.items()}
    if entry is not None:
        for key, value in hashes.items():
            if entry.get(key) != value:
                raise ValueError(f"Frozen trial hash differs: {run_dir.name}/{key}")
    metadata = json.loads(files["metadata_sha256"].read_text())
    summary = json.loads(files["summary_sha256"].read_text())
    required = set(TIME_SIGNALS) | {"control_time_s", "phase", "contact_confirmed", "missing_contact", "planner_update",
        "sensor_contact", "sensor_normal_force", "planner_recovery_active", "planner_model_prior_active", "planner_belief_support_mass",
        "planner_fallback_active", "planner_fallback_reason", "belief_mean_m", "belief_std_m", "planner_current_state_phase",
        "sensor_foot_pos_w", "sensor_com_pos_w", "planner_proposed_com_w", "planner_com_target_w", "planner_proposed_foot_w",
        "planner_foot_target_w", "fallback_interval_s", "fallback_foot_descent_m", "fallback_com_travel_m"}
    with np.load(files["signals_sha256"], allow_pickle=False) as source:
        data = {key: np.array(source[key], copy=True) for key in required}
    time = data["control_time_s"]
    phase = data["phase"].astype(str)
    lower = np.flatnonzero(phase == "lower")
    reloads = np.flatnonzero((phase == "reload") & data["contact_confirmed"].astype(bool))
    lower_start = float(time[lower[0]]) if len(lower) else float(time[0])
    reload_time = float(time[reloads[0]]) if len(reloads) else None
    landing = np.isin(phase, ["lower", "confirm"])
    loaded = data["sensor_contact"][:, 0].astype(bool) & (data["sensor_normal_force"][:, 0] >= 2.)
    updates = landing & data["planner_update"].astype(bool) & ~loaded
    if reload_time is not None:
        updates &= time < reload_time
    indexes = np.flatnonzero(updates)
    prior = data["planner_model_prior_active"].astype(bool)
    recovery = data["planner_recovery_active"].astype(bool)
    fallback = data["planner_fallback_active"].astype(bool)
    support = data["planner_belief_support_mass"]
    missing = data["missing_contact"].astype(bool)
    first_missing_rows = np.flatnonzero(landing & missing)
    missing_index = int(first_missing_rows[0]) if len(first_missing_rows) else None
    missing_time = float(time[missing_index]) if missing_index is not None else None
    use = updates & prior & ~fallback & (support >= .5-1e-12)
    masks = dict(all_unsupported_planning_updates=updates,
        active_supported_prior=use, active_supported_nominal_prior=use & ~recovery,
        active_supported_recovery_prior=use & recovery,
        active_99percent_supported_recovery_prior=use & recovery & (support >= .99-1e-12),
        fallback_updates=updates & fallback,
        inactive_prior_without_fallback=updates & ~prior & ~fallback)
    errors = {}
    for name, mask in masks.items():
        actual = reload_time-time[mask] if reload_time is not None else np.array([])
        errors[name] = {key: error_stats(data[key][mask] if reload_time is not None else [], actual) for key in TIME_SIGNALS}
    radius = float(metadata["foot_radius_m"])
    def get_snapshot(index):
        return snapshot(data, index, reload_time, radius, lower_start)
    events = dict(first_unsupported_plan=get_snapshot(int(indexes[0]) if len(indexes) else None),
                  last_unsupported_plan=get_snapshot(int(indexes[-1]) if len(indexes) else None),
                  first_missing_observation=get_snapshot(missing_index))
    if missing_index is not None:
        before, after = indexes[indexes < missing_index], indexes[indexes >= missing_index]
        events["last_plan_before_missing"] = get_snapshot(int(before[-1]) if len(before) else None)
        events["first_plan_at_or_after_missing"] = get_snapshot(int(after[0]) if len(after) else None)
        for delay in (.25, .5, 1.):
            rows = indexes[time[indexes] >= missing_time+delay-1e-12]
            events[f"first_plan_after_missing_{delay:g}s"] = get_snapshot(int(rows[0]) if len(rows) else None)
    intervals, fallback_totals = fallback_intervals(data)
    applied_intervals = landing[:-1] & landing[1:]
    dt = np.diff(time)
    descent = np.maximum(0., -np.diff(data["planner_foot_target_w"][:, 2]))
    prior_executing = applied_intervals & prior[:-1] & ~fallback[:-1] & ~loaded[:-1]
    unsupported_intervals = applied_intervals & ~loaded[:-1]
    post_missing_intervals = applied_intervals & (time[:-1] >= missing_time) if missing_time is not None else np.zeros(len(dt), dtype=bool)
    applied_work = dict(landing_commanded_foot_descent_m=float(descent[applied_intervals].sum()),
        post_missing_commanded_foot_descent_m=float(descent[post_missing_intervals].sum()),
        prior_active_unsupported_execution_time_s=float(dt[prior_executing].sum()),
        unsupported_execution_time_s=float(dt[unsupported_intervals].sum()))
    before_after = None
    if missing_index is not None and events["last_plan_before_missing"] and events["first_plan_at_or_after_missing"]:
        a, b = events["last_plan_before_missing"], events["first_plan_at_or_after_missing"]
        keys = TIME_SIGNALS+("belief_mean_m", "proposed_com_z_m", "applied_com_z_m", "proposed_foot_z_m", "applied_foot_z_m")
        before_after = {key: b[key]-a[key] for key in keys}
    post = updates & (time >= missing_time) if missing_time is not None else np.zeros(len(time), dtype=bool)
    ranges = {name: stats(data[name][post]) for name in TIME_SIGNALS}
    report = dict(trial_id=spec["trial_id"], run_id=run_dir.name, run_dir=str(run_dir.resolve()),
        parameters=spec, hashes=hashes, passed=summary.get("passed") is True,
        failed_criteria=[name for name, criterion in summary.get("criteria", {}).items() if not criterion.get("passed", False)],
        lower_start_time_s=lower_start, confirmed_reload_time_s=reload_time,
        confirmed_reload_observed=reload_time is not None, first_missing_contact_time_s=missing_time,
        modeled_time_prior_enabled=spec["planner"] != "matched_no_timing_adaptation",
        unsupported_planning_updates=int(updates.sum()), active_prior_updates=int(use.sum()),
        recovery_prior_updates=int((use & recovery).sum()), fallback_planning_updates=int((updates & fallback).sum()),
        active_prior_fraction=float(use.sum()/updates.sum()) if updates.any() else None,
        applied_reference_work=applied_work,
        fallback_totals=fallback_totals, fallback_intervals=intervals,
        event_snapshots=events, first_missing_transition_delta=before_after,
        raw_post_missing_timing=ranges, forecast_errors_by_execution_mask=errors,
        prior_active_support_mass=stats(support[use]), raw_model_time=stats(data["raw_model_remaining_time_s"][updates]),
        model_floor_changed_plan_count=int(np.count_nonzero(updates & (np.abs(data["model_remaining_time_s"]-data["raw_model_remaining_time_s"]) > 1e-10))),
        feasible_time_exceeds_raw_model_plan_count=int(np.count_nonzero(updates & (data["feasible_remaining_time_s"] > data["raw_model_remaining_time_s"]+1e-10))),
        feasible_minus_raw_model_time_s=stats((data["feasible_remaining_time_s"]-data["raw_model_remaining_time_s"])[updates]),
        planning_timeline=[get_snapshot(int(i)) for i in indexes])
    if hashes != {key: sha(path) for key, path in files.items()}:
        raise RuntimeError(f"Canonical files changed during read-only audit: {run_dir}")
    return report


def aggregate(records):
    complete = [row for row in records if row.get("run_id")]
    groups = {}
    for planner in sorted({row["parameters"]["planner"] for row in records}):
        rows = [row for row in complete if row["parameters"]["planner"] == planner]
        error_groups = {}
        for mask in ("active_supported_prior", "active_supported_nominal_prior", "active_supported_recovery_prior",
                     "active_99percent_supported_recovery_prior", "fallback_updates"):
            error_groups[mask] = {}
            for signal in TIME_SIGNALS:
                metrics = [row["forecast_errors_by_execution_mask"][mask][signal] for row in rows]
                values = [metric["mean_absolute_error_s"] for metric in metrics if metric["planning_ticks"]]
                bias = [metric["mean_error_s"] for metric in metrics if metric["planning_ticks"]]
                error_groups[mask][signal] = dict(trials_with_observations=len(values), per_trial_mae_s=stats(values),
                    per_trial_mean_error_s=stats(bias), correlated_planning_ticks=sum(metric["planning_ticks"] for metric in metrics))
        first_missing = [row["event_snapshots"].get("first_plan_at_or_after_missing") for row in rows]
        first_missing = [event for event in first_missing if event is not None]
        first_missing_stats = {key: stats([event[key] for event in first_missing if event[key] is not None])
            for key in ("raw_model_remaining_time_s", "planner_remaining_time_s",
                        "actual_remaining_to_confirmed_reload_s", "belief_support_mass")}
        groups[planner] = dict(manifest_trials=sum(row["parameters"]["planner"] == planner for row in records),
            audited_trials=len(rows), passed_trials=sum(row["passed"] for row in rows),
            trials_with_confirmed_reload=sum(row["confirmed_reload_observed"] for row in rows),
            trials_with_missing_contact=sum(row["first_missing_contact_time_s"] is not None for row in rows),
            trials_with_active_recovery_prior=sum(row["recovery_prior_updates"] > 0 for row in rows),
            trials_with_fallback=sum(row["fallback_totals"]["active_time_s"] > 0 for row in rows),
            fallback_time_s=stats([row["fallback_totals"]["active_time_s"] for row in rows]),
            fallback_foot_descent_m=stats([row["fallback_totals"]["commanded_foot_descent_m"] for row in rows]),
            active_prior_fraction=stats([row["active_prior_fraction"] for row in rows if row["active_prior_fraction"] is not None]),
            raw_model_minimum_remaining_s=min((row["raw_model_time"]["minimum"] for row in rows if row["raw_model_time"]["count"]), default=None),
            model_floor_changed_plan_count=sum(row["model_floor_changed_plan_count"] for row in rows),
            first_missing_replan=first_missing_stats,
            first_missing_raw_time_increase_s=stats([row["first_missing_transition_delta"]["raw_model_remaining_time_s"]
                for row in rows if row["first_missing_transition_delta"] is not None]),
            forecast_errors=error_groups)
    return groups


def make_plot(records, path):
    rows = sorted([row for row in records if row.get("run_id") and row["parameters"]["planner"] == PRIMARY],
                  key=lambda row: (row["parameters"]["actual_height_m"], row["parameters"]["initial_condition"], row["parameters"]["seed"]))
    if not rows:
        return
    columns, nrows = 4, int(np.ceil(len(rows)/4))
    figure, axes = plt.subplots(nrows, columns, figsize=(17, 3.4*nrows), squeeze=False, constrained_layout=True)
    for ax, row in zip(axes.ravel(), rows):
        timeline = row["planning_timeline"]
        x = np.array([point["seconds_since_lower"] for point in timeline])
        curves = (("actual_remaining_to_confirmed_reload_s", "Realized time to reload", "black", "-"),
            ("raw_model_remaining_time_s", "Unclipped learned time", "tab:blue", "-"),
            ("optimized_remaining_time_s", "Optimized time", "tab:orange", "--"),
            ("planner_remaining_time_s", "Applied feasible time", "tab:green", ":"))
        for key, label, color, style in curves:
            values = [point[key] for point in timeline]
            if values and all(value is not None for value in values):
                ax.plot(x, values, label=label, color=color, linestyle=style, linewidth=1.15)
        active = np.array([point["prior_active"] and not point["fallback_active"] for point in timeline])
        if len(timeline):
            y = np.array([point["raw_model_remaining_time_s"] for point in timeline])
            ax.scatter(x[~active], y[~active], marker="x", s=11, color="tab:red", label="Learned prior inactive")
        for interval in row["fallback_intervals"]:
            ax.axvspan(interval["start_time_s"]-row["lower_start_time_s"], interval["end_time_s"]-row["lower_start_time_s"], color="tab:red", alpha=.08)
        if row["first_missing_contact_time_s"] is not None:
            ax.axvline(row["first_missing_contact_time_s"]-row["lower_start_time_s"], color="gray", linestyle="--", linewidth=.8)
        spec = row["parameters"]
        ax.set_title(f"{spec['actual_height_m']*1000:+g} mm | {spec['initial_condition']} | seed {spec['seed']}", fontsize=10)
        ax.set(xlabel="Seconds since lowering began", ylabel="Remaining seconds")
        ax.grid(alpha=.15)
    for ax in axes.ravel()[len(rows):]:
        ax.set_visible(False)
    axes.ravel()[0].legend(fontsize=7, loc="upper right")
    figure.suptitle("Full learned planner: raw model forecasts versus realized and feasible time\nGray line: missing contact; red shading: explicitly recorded fallback", fontsize=13)
    figure.savefig(path, dpi=165)
    plt.close(figure)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--allow-partial", action="store_true", help="Mark missing/running cells explicitly; do not infer complete-study findings")
    args = parser.parse_args(argv)
    directory = args.study_dir.resolve()
    manifest_path, state_path, freeze_path = (directory/name for name in ("split_manifest.json", "study_state.json", "execution_freeze.json"))
    manifest, state, freeze = (json.loads(path.read_text()) for path in (manifest_path, state_path, freeze_path))
    if sha(manifest_path) != freeze["split_manifest_sha256"] or state["split_manifest_sha256"] != sha(manifest_path):
        raise ValueError("Study manifest does not match frozen provenance")
    for name, expected in freeze["model_files"].items():
        if sha(directory/name) != expected:
            raise ValueError(f"Frozen model changed: {name}")
    incomplete = [spec["trial_id"] for spec in manifest["evaluations"]
                  if state["trials"].get(spec["trial_id"], {}).get("status") not in ("completed", "error")]
    if incomplete and not args.allow_partial:
        raise ValueError(f"Wait for the formal study to finish: {len(incomplete)} cells remain incomplete")
    specifications = [spec for spec in manifest["evaluations"] if spec["planner"] != "matched_predictive"]
    records = []
    for spec in specifications:
        entry = state["trials"].get(spec["trial_id"], {})
        if entry.get("status") not in ("completed", "error") or not entry.get("run_dir"):
            records.append(dict(trial_id=spec["trial_id"], parameters=spec, status=entry.get("status", "not_run"),
                                error=entry.get("error"), run_id=None, passed=False))
            continue
        if entry.get("source_sha256") != freeze["source_sha256"] or entry.get("model_files") != freeze["model_files"]:
            raise ValueError(f"Trial source/model provenance differs from execution freeze: {spec['trial_id']}")
        records.append(audit_run(entry["run_dir"], spec, entry))
    output = directory/"validation"
    output.mkdir(parents=True, exist_ok=True)
    report = dict(version=2, study_complete=not incomplete, total_evaluation_cells=len(manifest["evaluations"]),
        expected_learned_and_ablation_cells=len(specifications), expected_full_learned_cells=sum(spec["planner"] == PRIMARY for spec in specifications),
        audited_cells=sum(row.get("run_id") is not None for row in records), incomplete_evaluation_cells=incomplete,
        provenance=dict(split_manifest_sha256=sha(manifest_path), study_state_sha256=sha(state_path), execution_freeze_sha256=sha(freeze_path),
                        frozen_source_sha256=freeze["source_sha256"], model_files=freeze["model_files"], reproduction_script_sha256=sha(__file__)),
        conventions=dict(primary_planner=PRIMARY, independent_unit="trial, not correlated planning tick",
            prediction_target="Realized control time until first contact-confirmed reload; failures without reload are censored and retained",
            evaluation_mask="lower/confirm planning updates without sensor-confirmed FL loading (contact and >=2 N)",
            active_prior_mask="actual prior active, no fallback, and >=50% supplied posterior mass in training support",
            strict_recovery_mask="As active prior, recovery mode and >=99% posterior support mass",
            raw_time="raw_model_remaining_time_s before the 0.1 s model floor and optimizer/feasibility constraints",
            optimized_time="Optimizer-selected feasible horizon, not a statistical contact-time forecast; its discrepancy from realized completion is reported separately",
            applied_time="planner_remaining_time_s after shared feasible-reference projection",
            no_timing_ablation="Raw learned time is logged for inspection but its timing prior is removed from the objective",
            fallback="Explicit contiguous left-endpoint flags integrated against actual applied references; no learned-prior credit",
            interpretation="Descriptive closed-loop forecast discrepancies under continued replanning; no zero-error calibration or performance superiority claim"),
        by_variant=aggregate(records),
        full_learned_by_height={f"{height:+g}": aggregate([row for row in records
            if row["parameters"]["planner"] == PRIMARY and row["parameters"]["actual_height_m"] == height]).get(PRIMARY, {})
            for height in sorted({spec["actual_height_m"] for spec in specifications if spec["planner"] == PRIMARY})},
        trials=records)
    path = output/"learned_execution_audit.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    make_plot(records, output/"learned_execution_audit.png")
    for name, expected in freeze["model_files"].items():
        if sha(directory/name) != expected:
            raise RuntimeError(f"Model changed during read-only audit: {name}")
    print(json.dumps(dict(audited=report["audited_cells"], complete=report["study_complete"], by_variant=report["by_variant"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
