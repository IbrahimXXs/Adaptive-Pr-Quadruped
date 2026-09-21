"""Independent validation and comparison metrics for landing-pad trials.

Terrain truth is read here for evaluation only. Every controlled-step check is
retained, including MPC solve cadence, measured reload loading, and final stance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .step import _extreme, _safe, analyze_step


REQUIRED = (
    "belief_mean_m", "belief_std_m", "belief_lower_m", "belief_upper_m",
    "missing_contact", "sensor_contact", "sensor_normal_force", "sensor_foot_pos_w",
    "sensor_measurement_time_s", "planner_update", "planner_remaining_time_s",
    "planner_com_target_w", "planner_foot_target_w", "planner_body_rpy",
    "planner_compute_time_s", "reference_projection_count", "planner_fallback_count",
    "target_pad_contact", "target_pad_normal_force", "foot_bottom_z_w",
)


def _truth_fields(value, prefix=""):
    """Schema audit only; numeric inference or arbitrary hidden code needs review."""
    found = []
    if isinstance(value, dict):
        for name, child in value.items():
            if not prefix and name == "evaluation":
                continue
            path = f"{prefix}.{name}" if prefix else name
            if re.search(r"(?:true|actual).*height|height.*(?:true|actual)", str(name), re.I):
                found.append(path)
            found.extend(_truth_fields(child, path))
    return found


def analyze_pad(run_dir: Path) -> dict:
    """Write pad_summary.json, pad_report.md and pad_overview.png for one trial."""
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    with np.load(run_dir / "signals.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    missing = sorted(set(REQUIRED) - data.keys())
    if missing:
        raise ValueError(f"Missing landing-pad signals: {missing}")
    n = len(data["time_s"])
    for name in REQUIRED:
        if data[name].ndim == 0 or len(data[name]) != n:
            raise ValueError(f"Landing signal {name!r} does not have {n} aligned samples")
    base = analyze_step(run_dir)
    checks = dict(base["criteria"])

    def check(name, passed, requirement, observed):
        checks[f"pad_{name}"] = {"passed": bool(passed), "requirement": requirement, "observed": observed}

    dt = float(metadata["dt_s"])
    t = data["time_s"]
    phase = data["phase"].astype(str)
    selected = list(metadata["legs"]).index(metadata["selected_leg"])
    radius = float(metadata["foot_radius_m"])
    estimate = float(metadata["initial_height_estimate_m"])
    evaluation = metadata.get("evaluation", {})
    actual = float(evaluation.get("actual_pad_height_m", np.nan))
    target = np.asarray(metadata["landing_target_xy_m"], dtype=float)
    floor = estimate - float(metadata["max_search_depth_m"]) - float(metadata["contact_compression_m"])
    bottom = data["feet_pos_w"][:, selected, 2] - radius
    desired_bottom = data["feet_desired_w"][:, selected, 2] - radius
    target_contact = data["target_pad_contact"].astype(bool)
    target_force = data["target_pad_normal_force"]
    lower = np.flatnonzero(phase == "lower")
    reload = np.flatnonzero(phase == "reload")
    recenter = np.flatnonzero(phase == "recenter")
    final = phase == "complete"
    landing = np.isin(phase, ["lower", "confirm", "reload", "recenter", "complete"])
    candidates = np.flatnonzero(landing & target_contact)
    touchdown = int(candidates[0]) if len(candidates) else None
    command_min = _extreme(desired_bottom[landing], False)
    metadata_valid = (metadata.get("experiment") == "landing_pad" and int(metadata.get("cycles", 0)) == 1
                      and np.isfinite(actual) and np.isfinite(estimate) and np.isfinite(radius)
                      and radius > 0 and target.shape == (2,) and np.all(np.isfinite(target))
                      and 0 < float(metadata["max_search_depth_m"]) <= .03
                      and 0 <= float(metadata["contact_compression_m"]) <= .005)
    check("configuration", metadata_valid, "One landing-pad cycle with finite geometry and bounded search settings",
          {"experiment": metadata.get("experiment"), "cycles": metadata.get("cycles"),
           "max_search_depth_m": metadata["max_search_depth_m"], "contact_compression_m": metadata["contact_compression_m"]})
    fixed_heights = np.asarray(evaluation.get("support_top_heights_m", []), dtype=float)
    check("fixed_support_surfaces", fixed_heights.shape == (4,) and np.all(fixed_heights == 0),
          "All four fixed launch/support surfaces have top z=0; only the separate landing pad changes",
          fixed_heights)
    leak = _truth_fields(metadata) + [name for name in data if _truth_fields({name: None})]
    if metadata.get("role") != "demonstration" and "known_height_m" in metadata:
        leak.append("known_height_m outside demonstration")
    check("truth_separation_schema", not leak,
          "Actual height appears only in evaluation metadata; known height labels are confined to demonstrations",
          leak)
    check("bounded_descent", command_min is not None and command_min >= floor - 1e-8,
          "Commanded foot bottom stays above initial estimate minus search depth and contact compression",
          {"minimum_commanded_bottom_m": command_min, "minimum_allowed_bottom_m": floor})
    check("physical_reach", np.any(landing) and np.all(bottom[landing] >= estimate-.04),
          "Measured foot bottom never extends more than 40 mm below the initial estimate",
          {"minimum_actual_bottom_m": _extreme(bottom[landing], False), "minimum_allowed_bottom_m": estimate-.04})
    check("foot_bottom_consistency", n > 0 and np.allclose(data["foot_bottom_z_w"], bottom, atol=1e-9, rtol=0),
          "Evaluation foot-bottom signal equals measured sphere center minus known radius",
          _extreme(np.abs(data["foot_bottom_z_w"]-bottom)))
    force_consistent = (n > 0 and np.all(target_force >= -1e-9)
                        and np.all(target_force <= data["contact_normal_force"][:, selected]+1e-5)
                        and not np.any(target_contact & ~data["contact_measured"][:, selected].astype(bool))
                        and np.all(np.abs(target_force[~target_contact]) <= 1e-8))
    check("target_force_consistency", force_consistent,
          "Target-pad forces/contact are a nonnegative subset of measured selected-foot ground contact",
          {"maximum_target_force_n": _extreme(target_force),
           "maximum_target_minus_total_normal_n": _extreme(target_force-data["contact_normal_force"][:, selected])})
    check("final_target_loading", np.any(final) and np.all(target_contact[final])
          and np.all(target_force[final] > 5)
          and np.all(np.linalg.norm(data["feet_pos_w"][final, selected, :2]-target, axis=1) < .02),
          "Final standing loads the actual separate target pad above 5 N and stays within 20 mm of its center",
          {"minimum_normal_force_n": _extreme(target_force[final], False),
           "maximum_xy_target_error_m": _extreme(np.linalg.norm(data["feet_pos_w"][final, selected, :2]-target, axis=1)),
           "missing_target_contact_samples": int(np.count_nonzero(~target_contact[final]))})
    check("final_height_consistency", np.any(final) and np.all(np.abs(bottom[final]-actual) <= .005),
          "Loaded final foot bottom is within 5 mm of the simulator's true pad top, allowing contact compliance",
          _extreme(np.abs(bottom[final]-actual)))
    debounce_samples = max(1, int(np.ceil(float(metadata["contact_debounce_s"])/dt-1e-9))-1)
    contact_gate = False
    if len(reload) and reload[0] >= debounce_samples:
        window = slice(int(reload[0])-debounce_samples, int(reload[0]))
        contact_gate = np.all(target_contact[window]) and np.all(target_force[window] >= 2.)
    check("target_contact_before_reload", contact_gate,
          "Independent target-pad contact carries at least 2 N throughout the pre-reload debounce window",
          {"required_samples": debounce_samples, "first_reload_time_s": t[reload[0]] if len(reload) else None})
    restored = False
    restore_min = None
    if len(reload) and len(recenter):
        samples = max(1, int(np.ceil(.2/dt-1e-9)))
        window = np.r_[reload[-samples:], recenter[0]]
        restored = (len(reload) >= samples and np.all(target_contact[window]) and np.all(target_force[window] > 5))
        restore_min = _extreme(target_force[window], False)
    check("target_reload_loading", restored,
          "Actual target pad is loaded above 5 N over the last 0.2 s of reload and first recenter sample", restore_min)
    valid_belief = (n > 0 and np.all(data["belief_std_m"] >= 0)
                    and np.all(data["belief_lower_m"] <= data["belief_mean_m"])
                    and np.all(data["belief_mean_m"] <= data["belief_upper_m"]))
    check("belief_bounds", valid_belief, "Belief has nonnegative uncertainty and ordered lower/mean/upper values", None)
    sensor_time = data["sensor_measurement_time_s"] - float(metadata.get("sensor_time_origin_s", 0.))
    check("sensor_causality", n > 0 and np.all(sensor_time <= data["control_time_s"]+1e-8)
          and np.all(np.diff(sensor_time) >= -1e-8),
          "Sensor timestamps are monotonic and never later than the consuming control interval start",
          {"maximum_future_lead_s": _extreme(sensor_time-data["control_time_s"])})
    updates = data["planner_update"].astype(bool)
    check("planner_execution", np.any(updates) and np.all(data["planner_compute_time_s"] >= 0)
          and np.all(data["planner_remaining_time_s"] >= 0),
          "Planner executes with finite nonnegative timing; bounded recovery fallback is reported separately",
          {"updates": int(np.count_nonzero(updates)), "maximum_fallback_count": _extreme(data["planner_fallback_count"])})

    first_lower = int(lower[0]) if len(lower) else None
    lower_start = float(data["control_time_s"][first_lower]) if first_lower is not None else None
    deadline = lower_start + float(metadata["nominal_lower_duration_s"]) if lower_start is not None else None
    touch_time = float(t[touchdown]) if touchdown is not None else None
    missing_rows = np.flatnonzero(data["missing_contact"].astype(bool) & landing)
    missing_time = float(data["control_time_s"][missing_rows[0]]) if len(missing_rows) else None
    body_window = np.arange(first_lower, n) if first_lower is not None else np.array([], dtype=int)
    impact = np.zeros(n, dtype=bool)
    if touchdown is not None:
        # Exactly 100 ms worth of interval-end samples, including touchdown.
        impact = (t >= touch_time-1e-9) & (t < touch_time+.1-1e-9)
    actual_delta = actual-estimate
    terrain_class = "higher" if actual_delta > .002 else "lower" if actual_delta < -.002 else "approximately_correct"
    elapsed_difference = touch_time-deadline if touch_time is not None and deadline is not None else None
    timing_class = ("no_touchdown" if elapsed_difference is None else "early" if elapsed_difference < -.25
                    else "late" if elapsed_difference > .25 else "approximately_planned")
    tilt_change = (np.rad2deg(data["base_rpy_rad"][body_window, :2]-data["base_rpy_rad"][first_lower, :2])
                   if first_lower is not None else np.empty((0, 2)))
    com_reference = data.get("com_target_w", data["planner_com_target_w"])
    metrics = dict(base["metrics"])
    metrics.update({
        "success": all(item["passed"] for item in checks.values()),
        "completion_time_s": float(t[-1]) if n else None,
        "lowering_to_touchdown_s": touch_time-lower_start if touch_time is not None and lower_start is not None else None,
        "lowering_to_completion_s": float(t[-1])-lower_start if n and lower_start is not None else None,
        "first_target_touchdown_time_s": touch_time, "nominal_touchdown_deadline_s": deadline,
        "touchdown_minus_nominal_deadline_s": elapsed_difference,
        "observed_contact_timing": timing_class,
        "missing_contact_observed": bool(len(missing_rows)), "first_missing_contact_time_s": missing_time,
        "missing_contact_before_physical_touchdown": (missing_time < touch_time if missing_time is not None and touch_time is not None else False),
        "recovery_to_touchdown_s": max(0., touch_time-missing_time) if missing_time is not None and touch_time is not None else 0.,
        "peak_normal_force_first_100ms_n": _extreme(target_force[impact]),
        "normal_impulse_first_100ms_ns": float(np.sum(target_force[impact])*dt) if np.any(impact) else None,
        "maximum_roll_pitch_change_during_landing_deg": _extreme(np.abs(tilt_change)),
        "maximum_com_reference_error_during_landing_m": _extreme(np.linalg.norm(data["com_pos_w"][body_window]-com_reference[body_window], axis=1)),
        "maximum_body_rotation_during_landing_deg": _extreme(np.rad2deg(np.linalg.norm(data["base_rpy_rad"][body_window]-data["base_rpy_rad"][first_lower], axis=1))) if first_lower is not None else None,
        "height_belief_final_error_m": float(data["belief_mean_m"][-1])-actual if n else None,
        "height_belief_error_at_contact_confirmation_m": float(data["belief_mean_m"][reload[0]])-actual if len(reload) else None,
        "planner_update_count": int(np.count_nonzero(updates)),
        "planner_mean_compute_time_s": float(np.mean(data["planner_compute_time_s"][updates])) if np.any(updates) else None,
        "planner_maximum_compute_time_s": _extreme(data["planner_compute_time_s"][updates]),
        "reference_projection_count": _extreme(data["reference_projection_count"]),
        "planner_fallback_count": _extreme(data["planner_fallback_count"]),
        "learned_conditioning_updates": _extreme(data["planner_conditioning_count"]) if "planner_conditioning_count" in data else None,
        "learned_duration_min_s": _extreme(data["learned_duration_s"][updates], False) if metadata.get("planner") == "learned" and "learned_duration_s" in data else None,
        "learned_duration_max_s": _extreme(data["learned_duration_s"][updates]) if metadata.get("planner") == "learned" and "learned_duration_s" in data else None,
        "predictive_optimization_failures": _extreme(data["predictive_optimization_failures"]) if "predictive_optimization_failures" in data else None,
    })
    summary = _safe({
        "passed": metrics["success"], "run_id": run_dir.name,
        "experiment": "landing_pad", "role": metadata.get("role"),
        "planner": metadata.get("planner"), "criteria": checks, "metrics": metrics,
        "evaluation": {"actual_pad_height_m": actual, "initial_height_estimate_m": estimate,
                       "height_difference_m": actual_delta, "height_condition": terrain_class},
        "base_summary_file": "step_summary.json", "runner_error": metadata.get("error"),
        "conventions": {
            "impact": "Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.",
            "body_disturbance": "Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.",
            "timing": "Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.",
            "height_truth": "Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.",
            "completion": "All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.",
        },
    })
    source = run_dir / "source" / "analysis"
    source.mkdir(parents=True, exist_ok=True)
    if (source / "pad.py").resolve() != Path(__file__).resolve():
        shutil.copy2(__file__, source / "pad.py")
    (run_dir / "pad_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False)+"\n")
    _report(run_dir, summary)
    _plot(run_dir, metadata, data, summary)
    return summary


def _report(run_dir, summary):
    lines = [f"# Adjustable landing pad — {'PASS' if summary['passed'] else 'FAIL'}", "",
             f"Planner: **{summary['planner']}**. Role: **{summary['role']}**. "
             f"Height condition: **{summary['evaluation']['height_condition']}**.", "",
             "| Metric | Value |", "|---|---:|"]
    for name, value in summary["metrics"].items():
        if not isinstance(value, dict):
            lines.append(f"| {name} | {value} |")
    lines += ["", "| Check | Result | Observed |", "|---|---|---|"]
    for name, value in summary["criteria"].items():
        lines.append(f"| {name} | {'PASS' if value['passed'] else 'FAIL'} | {json.dumps(value['observed'])} |")
    lines += ["", *[f"- **{key}:** {value}" for key, value in summary["conventions"].items()], "",
              "![Landing-pad evidence](pad_overview.png)", "",
              "Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. "
              "Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`."]
    (run_dir / "pad_report.md").write_text("\n".join(lines)+"\n")


def _plot(run_dir, metadata, data, summary):
    t = data["time_s"]
    selected = list(metadata["legs"]).index(metadata["selected_leg"])
    radius = float(metadata["foot_radius_m"])
    fig, axes = plt.subplots(3, 2, figsize=(13, 11), constrained_layout=True)
    axes = axes.ravel()
    fig.suptitle(f"{metadata['planner']} · {summary['evaluation']['height_condition']} · {'PASS' if summary['passed'] else 'FAIL'}")
    axes[0].plot(t, data["foot_bottom_z_w"]*1000, label="Measured foot bottom")
    axes[0].plot(t, (data["feet_desired_w"][:, selected, 2]-radius)*1000, "--", label="Commanded foot bottom")
    axes[0].axhline(summary["evaluation"]["actual_pad_height_m"]*1000, color="black", label="Pad truth (evaluation)")
    axes[0].set(title="Landing surface and foot", ylabel="World height (mm)")
    axes[1].plot(t, data["belief_mean_m"]*1000, label="Sensor-only belief mean")
    axes[1].fill_between(t, data["belief_lower_m"]*1000, data["belief_upper_m"]*1000, alpha=.2, label="Belief bounds")
    axes[1].axhline(summary["evaluation"]["actual_pad_height_m"]*1000, color="black", label="Pad truth (evaluation)")
    axes[1].set(title="Ground-height belief", ylabel="Height (mm)")
    axes[2].plot(t, data["target_pad_normal_force"], label="Target-pad measured normal")
    axes[2].plot(t, data["selected_force_cap_N"], "--", label="MPC force cap")
    axes[2].set(title="Landing and restored support", ylabel="Force (N)")
    for index, name in enumerate(("roll", "pitch")):
        axes[3].plot(t, np.rad2deg(data["base_rpy_rad"][:, index]), label=name)
    axes[3].set(title="Body attitude", ylabel="Angle (deg)")
    for index, name in enumerate(("x", "y", "z")):
        axes[4].plot(t, data["com_pos_w"][:, index]*1000, label=f"Measured {name}")
        if "com_target_w" in data:
            axes[4].plot(t, data["com_target_w"][:, index]*1000, "--", alpha=.6, label=f"Desired {name}")
    axes[4].set(title="Coordinated body motion", ylabel="CoM position (mm)")
    axes[5].plot(t, data["planner_remaining_time_s"], label="Planned remaining duration")
    axes[5].step(t, data["missing_contact"], where="post", label="Missing-contact flag")
    axes[5].set(title="Timing adaptation", ylabel="Seconds / flag")
    for axis in axes:
        axis.set(xlabel="Experiment time (s)")
        axis.grid(alpha=.2)
        axis.legend(fontsize=7)
    fig.savefig(run_dir / "pad_overview.png", dpi=150)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    result = analyze_pad(args.run_dir)
    print(json.dumps({"passed": result["passed"], "report": str(args.run_dir / "pad_report.md")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
