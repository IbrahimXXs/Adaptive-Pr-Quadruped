"""Independent evidence, loading and outcome checks for a weak landing pad.

A collapse may demonstrate the intended problem while still being a physical
failure. A conservative safe stop is distinct from completing the movement.
This analyzer reads simulator truth only for evaluation; no controller is run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .step import _safe, _triangle_margin


REQUIRED = (
    "time_s", "control_time_s", "step", "phase", "com_pos_w", "base_rpy_rad",
    "feet_pos_w", "feet_desired_w", "contact_measured", "contact_normal_force",
    "contact_planned", "grf_desired_w", "mpc_update", "mpc_status", "qp_status",
    "requested_probe_force_n", "achieved_probe_command_n", "sensor_pad_normal_force_n",
    "actual_pad_normal_force_n", "pad_contact", "certificate_force_n", "certificate_valid",
    "certificate_update", "probe_evidence_start_time_s", "probe_evidence_end_time_s",
    "planned_pad_force_n", "applied_pad_force_cap_n", "required_pad_force_n", "tracking_reserve_n",
    "commanded_next_leg_lift_m", "strategy_state", "safe_stop_declared", "task_complete_declared",
    "future_plan_active", "pad_sink_displacement_m", "pad_failed", "force_before_deformation_n",
    "sensor_pad_foot_pos_w", "sensor_pad_foot_vel_w", "sensor_contact_measured",
)
EXPECTED = {"unaware": "PROBLEM_COLLAPSE", "conservative": "SAFE_STOP", "adaptive": "SUCCESS"}


def _longest(time, condition, dt):
    indexes = np.flatnonzero(condition)
    if not len(indexes):
        return 0., None
    groups = np.split(indexes, np.flatnonzero(np.diff(indexes) != 1)+1)
    longest = max(groups, key=len)
    return float(time[longest[-1]]-time[longest[0]]+dt), (int(longest[0]), int(longest[-1]))


def _truth_leaks(value, path=""):
    leaks = []
    if isinstance(value, dict):
        for key, child in value.items():
            if not path and key in ("evaluation", "evaluation_final"):
                continue
            here = f"{path}.{key}" if path else str(key)
            if str(key) in {"failure_load_n", "failure_threshold_n", "true_capacity_n", "actual_capacity_n"}:
                leaks.append(here)
            leaks.extend(_truth_leaks(child, here))
    return leaks


def evaluate_weak_pad(metadata, data):
    """Return falsifiable checks without modifying recordings or trusting requests."""
    missing = sorted(set(REQUIRED)-data.keys())
    if missing:
        raise ValueError(f"Missing weak-pad evidence: {missing}")
    n = len(data["control_time_s"])
    if n < 2 or any(np.asarray(data[name]).ndim == 0 or len(data[name]) != n for name in REQUIRED):
        raise ValueError("Weak-pad evidence needs at least two aligned samples")
    data = {name: np.asarray(value) for name, value in data.items()}
    t = np.asarray(data["control_time_s"], dtype=float)
    dt = float(metadata["dt_s"])
    strategy = metadata.get("strategy")
    legs = list(metadata.get("legs", ["FL", "FR", "RL", "RR"]))
    selected = legs.index(metadata.get("selected_leg", "FL"))
    next_leg = legs.index(metadata.get("next_lift_leg", metadata.get("next_leg", "RL")))
    original_supports = [i for i in range(4) if i != selected]
    future_supports = [i for i in range(4) if i != next_leg]
    valid = data["certificate_valid"].astype(bool)
    certificate = data["certificate_force_n"].astype(float)
    future = data["future_plan_active"].astype(bool)
    failed = data["pad_failed"].astype(bool)
    pad_contact = data["pad_contact"].astype(bool)
    actual_force = data["actual_pad_normal_force_n"].astype(float)
    measured_force = data["sensor_pad_normal_force_n"].astype(float)
    contacts = data["contact_measured"].astype(bool)
    normal = data["contact_normal_force"].astype(float)
    phase = data["phase"].astype(str)
    probe = np.char.find(phase, "probe") >= 0
    force_tolerance = float(metadata.get("force_tolerance_n", .1))
    dwell = float(metadata.get("probe_dwell_s", .5))
    sensor_reserve = float(metadata.get("sensor_force_reserve_n", 1.))
    motion_limit = float(metadata.get("max_probe_motion_m", .002))
    tracking = data["tracking_reserve_n"].astype(float)
    max_tilt = float(metadata.get("maximum_abs_roll_pitch_deg", 8.))
    tilt = np.rad2deg(np.max(np.abs(data["base_rpy_rad"][:, :2]), axis=1))
    checks = {}

    def check(name, passed, requirement, observed=None, category="integrity"):
        checks[name] = dict(passed=bool(passed), category=category, requirement=requirement, observed=_safe(observed))

    finite_bad = [name for name, values in data.items() if np.issubdtype(values.dtype, np.number) and not np.all(np.isfinite(values))]
    check("finite_data", not finite_bad, "All recorded numeric evidence is finite", finite_bad)
    check("configuration", metadata.get("experiment") == "weak_pad" and strategy in EXPECTED
          and next_leg != selected and np.isfinite(dt) and dt > 0 and np.isfinite(dwell) and dwell >= .1
          and 0 <= force_tolerance <= .5 and sensor_reserve > 0 and 0 < motion_limit <= .005
          and np.all(tracking > 0) and 0 < max_tilt <= 8.,
          "Declared experiment, timing, finite force reserves and bounded movement checks", dict(strategy=strategy, dwell_s=dwell))
    check("completed_recording", metadata.get("status") == "completed", "Recording ends through the experiment's controlled completion/stop path", metadata.get("status"))
    check("sample_clock", np.allclose(np.diff(t), dt, atol=1e-8, rtol=0)
          and np.array_equal(data["step"], np.arange(1, n+1))
          and np.allclose(data["time_s"]-t, dt, atol=1e-8, rtol=0),
          "Continuous physics timestamps and aligned control/measurement intervals")
    try:
        frequency = float(metadata["simulation_params"]["mpc_frequency"])
        period = round(1/(frequency*dt)) if frequency > 0 and dt > 0 else 0
    except (ValueError, KeyError, TypeError):
        period = 0
    expected_updates = np.arange(n) % period == 0 if period > 0 else np.zeros(n, dtype=bool)
    expected_updates[0] = True
    expected_updates[1:] |= np.any(data["contact_planned"][1:] != data["contact_planned"][:-1], axis=1)
    # Tightening an applied cap is an additional justified immediate solve.
    cap_changes = np.r_[False, np.abs(np.diff(data["applied_pad_force_cap_n"])) > 1e-9]
    updates = data["mpc_update"].astype(bool)
    check("mpc_update_cadence", period > 0 and np.all(updates[expected_updates])
          and not np.any(updates & ~(expected_updates | cap_changes)),
          "Every periodic/support-change solve occurs; extra solves must install a changed force cap",
          dict(missing_required=int(np.count_nonzero(expected_updates & ~updates)), unexpected=int(np.count_nonzero(updates & ~(expected_updates | cap_changes)))))
    check("solver_success", not np.any(data["mpc_status"][updates]) and not np.any(data["qp_status"][updates]),
          "All recorded MPC and QP solves succeed")
    check("strength_truth_boundary", not _truth_leaks(metadata), "Hidden pad capacity occurs only in evaluator metadata", _truth_leaks(metadata))

    evaluation = metadata.get("evaluation", {})
    threshold = float(evaluation.get("failure_threshold_n", evaluation.get("failure_load_n", np.nan)))
    overload_dwell = float(evaluation.get("overload_dwell_s", .010))
    sink_speed = float(evaluation.get("sink_speed_m_s", .10))
    sink_depth = float(evaluation.get("sink_depth_m", .060))
    truth_valid = all(np.isfinite(x) and x > 0 for x in (threshold, overload_dwell, sink_speed, sink_depth))
    expected_failure = np.zeros(n, dtype=bool)
    overload, first_failure = 0., None
    if truth_valid:
        for i, force in enumerate(data["force_before_deformation_n"]):
            if first_failure is None:
                overload = overload+dt if force > threshold else 0.
                if overload+1e-12 >= overload_dwell:
                    first_failure = i
            expected_failure[i] = first_failure is not None
    predicted_sink = np.zeros(n)
    if first_failure is not None:
        predicted_sink[first_failure:] = np.minimum(sink_depth, sink_speed*(t[first_failure:]-t[first_failure]))
    check("physical_failure_model", truth_valid and np.array_equal(failed, expected_failure)
          and np.allclose(data["pad_sink_displacement_m"], predicted_sink, atol=1e-8, rtol=0),
          "Latched failure and subsequent deformation follow actual overload dwell, not commanded loading",
          dict(first_failure_time_s=None if first_failure is None else t[first_failure], maximum_sink_m=float(np.max(data["pad_sink_displacement_m"]))))

    original_grounded = np.all(contacts[:, original_supports] & (normal[:, original_supports] >= 5.), axis=1)
    original_margin = _triangle_margin(data["com_pos_w"], data["feet_pos_w"][:, original_supports])
    probe_rows = np.flatnonzero(probe)
    initial_probe = int(probe_rows[0]) if len(probe_rows) else None
    check("probe_observed", initial_probe is not None, "A probe phase is physically recorded", category="evidence")
    # Every new certificate or changed evidence window is audited. A request,
    # allocated load, peak force, or a later overload cannot substitute for dwell.
    changed = np.r_[True, (np.abs(np.diff(certificate)) > 1e-8)
                    | (np.diff(data["probe_evidence_start_time_s"]) != 0)]
    changed |= np.r_[True, np.diff(data["probe_evidence_end_time_s"]) != 0]
    changed |= data["certificate_update"].astype(bool) | np.r_[True, valid[1:] != valid[:-1]]
    audits = []
    for i in np.flatnonzero(valid & changed):
        start = float(data["probe_evidence_start_time_s"][i])
        end = float(data["probe_evidence_end_time_s"][i])
        rows = np.flatnonzero((t >= start-1e-8) & (t <= end+1e-8))
        span = float(t[rows[-1]]-t[rows[0]]) if len(rows) else 0.
        measured_min = float(np.min(measured_force[rows])) if len(rows) else float("nan")
        actual_min = float(np.min(actual_force[rows])) if len(rows) else float("nan")
        movement = float(np.max(np.linalg.norm(data["sensor_pad_foot_pos_w"][rows]-data["sensor_pad_foot_pos_w"][rows[0]], axis=1))) if len(rows) else float("inf")
        capacity = float(certificate[i])
        proof = (len(rows) >= 2 and start <= end <= t[i]+1e-8 and span >= dwell-dt-1e-8
                 and np.all(probe[rows]) and np.all(original_grounded[rows]) and np.all(original_margin[rows] >= .005)
                 and np.all(pad_contact[rows]) and np.all(data["sensor_contact_measured"][rows, selected])
                 and not np.any(failed[rows]) and np.all(tilt[rows] <= max_tilt)
                 and movement <= motion_limit+1e-8 and np.max(data["pad_sink_displacement_m"][rows]) <= motion_limit
                 and np.ptp(measured_force[rows]) <= 1.5+1e-8
                 and np.max(np.linalg.norm(data["sensor_pad_foot_vel_w"][rows], axis=1)) <= .005+1e-8
                 and capacity > 0 and capacity <= measured_min-sensor_reserve+force_tolerance
                 and capacity <= actual_min+force_tolerance)
        audits.append(dict(sample=int(i), time_s=float(t[i]), evidence_start_s=start, evidence_end_s=end,
            observed_dwell_s=span, measured_min_force_n=measured_min, actual_min_force_n=actual_min,
            requested_force_n=float(data["requested_probe_force_n"][i]), certificate_force_n=capacity,
            measured_foot_motion_m=movement, passed=bool(proof)))
    proof_ok = bool(audits) and all(a["passed"] for a in audits)
    check("actual_dwell_certificate", proof_ok, "Every capacity certificate is bounded by sustained actual achieved loading and measured-force reserve, with original three supports stable", audits, "evidence")
    check("certificate_changes_logged", not np.any(valid & (certificate <= 0)), "A valid certificate has strictly positive tested capacity", category="evidence")
    check("future_declared", np.any(future), "A future plan or conservative stop is reached", category="decision")
    check("future_valid_certificate", np.any(future) and np.all(valid[future]), "Every future loading interval has a valid measured-evidence certificate", category="safety")
    permitted = certificate-tracking
    desired_mpc_force = data["grf_desired_w"][:, selected, 2]
    check("planned_force_with_reserve", np.any(future) and np.all(data["planned_pad_force_n"][future] <= permitted[future]+force_tolerance)
          and np.all(data["applied_pad_force_cap_n"][future] <= permitted[future]+force_tolerance)
          and np.all(desired_mpc_force[future] <= data["applied_pad_force_cap_n"][future]+force_tolerance),
          "Every planned/installed MPC load respects certificate minus declared tracking reserve", category="safety")
    check("actual_future_loading", np.any(future) and np.all(actual_force[future] <= certificate[future]+force_tolerance),
          "Actual future target loading stays below tested capacity throughout, independently of the MPC cap",
          dict(maximum_actual_n=float(np.max(actual_force[future])) if np.any(future) else None,
               maximum_excess_n=float(np.max((actual_force-certificate)[future])) if np.any(future) else None), "safety")
    check("pad_survives", not np.any(failed), "No weak-pad failure occurs", category="safety")
    check("body_stable", np.all(tilt <= max_tilt), "Measured roll and pitch stay within the declared stability limit", float(np.max(tilt)), "safety")

    forward_direction = np.asarray(metadata.get("forward_direction_w", metadata.get("progression_axis", [1., 0., 0.])), dtype=float)
    axis_valid = forward_direction.shape == (3,) and np.all(np.isfinite(forward_direction)) and abs(np.linalg.norm(forward_direction)-1.) <= 1e-6
    initial_com = data["com_pos_w"][initial_probe] if initial_probe is not None else data["com_pos_w"][0]
    anchor = data["feet_pos_w"][initial_probe, next_leg] if initial_probe is not None else data["feet_pos_w"][0, next_leg]
    advance = (data["com_pos_w"]-initial_com)@forward_direction if axis_valid else np.full(n, -np.inf)
    clearance = data["feet_pos_w"][:, next_leg, 2]-anchor[2]
    actual_lift = (clearance >= .020-1e-6) & ~contacts[:, next_leg] & (normal[:, next_leg] < 2.)
    grounded_future = np.all(contacts[:, future_supports] & (normal[:, future_supports] >= 2.), axis=1)
    future_margin = _triangle_margin(data["com_pos_w"], data["feet_pos_w"][:, future_supports])
    progress = future & actual_lift & (advance >= .030-1e-6) & grounded_future & (future_margin >= .005) & valid & ~failed
    progress_dwell, progress_window = _longest(t, progress, dt)
    meaningful = axis_valid and progress_dwell >= 1.-dt-1e-8
    check("meaningful_progress", meaningful, "Measured CoM advances >=30 mm while another foot is actually >=20 mm airborne for >=1 s, with three other measured supports", dict(maximum_forward_m=float(np.max(advance)), maximum_clearance_m=float(np.max(clearance)), simultaneous_hold_s=progress_dwell), "task")
    check("airborne_contact_schedule", not np.any(actual_lift & data["contact_planned"][:, next_leg]), "A physically lifted foot is not still scheduled as a support", category="task")
    stopped = data["safe_stop_declared"].astype(bool)
    stop_dwell, _ = _longest(t, stopped & original_grounded & (original_margin >= .005) & ~failed, dt)
    stop_valid = (np.any(stopped) and stop_dwell >= .5-dt-1e-8 and not np.any(actual_lift[future])
                  and np.any(data["required_pad_force_n"][future] > permitted[future]+force_tolerance)
                  and not np.any(data["task_complete_declared"]))
    check("conservative_stop", stop_valid, "An infeasible untested movement causes a sustained safe stop on the original three legs without claiming task completion", dict(stable_stop_s=stop_dwell), "task")
    probe_survived = bool(audits) and any(a["passed"] for a in audits)
    requested_shortfall = max((a["requested_force_n"]-a["actual_min_force_n"] for a in audits if a["passed"]), default=0.)
    check("requested_force_is_not_achieved", requested_shortfall >= 1., "At least 1 N of requested probe loading remains unachieved and cannot be certified", requested_shortfall, "evidence")
    problem = (probe_survived and first_failure is not None and bool(future[first_failure])
               and np.max(data["pad_sink_displacement_m"]) >= .002-1e-8
               and any(a["passed"] and a["evidence_end_s"] < t[first_failure] for a in audits))
    check("collapse_after_light_probe", problem, "A survived actual probe is followed by actual future overload and >=2 mm physical pad collapse", category="problem")

    integrity = all(c["passed"] for c in checks.values() if c["category"] == "integrity")
    evidence = all(c["passed"] for c in checks.values() if c["category"] == "evidence")
    safe = all(c["passed"] for c in checks.values() if c["category"] == "safety")
    physical_success = bool(integrity and evidence and safe and meaningful
                            and checks["airborne_contact_schedule"]["passed"] and np.any(data["task_complete_declared"]))
    outcome = "SUCCESS" if physical_success else "PROBLEM_COLLAPSE" if integrity and problem else "SAFE_STOP" if integrity and evidence and safe and stop_valid else "UNSAFE" if np.any(failed) or not safe else "INCOMPLETE"
    if not integrity:
        outcome = "INVALID"
    expected_met = outcome == EXPECTED.get(strategy)
    return _safe(dict(version=1, experiment="weak_pad", strategy=strategy, role=metadata.get("role"),
        outcome=outcome, expected_outcome=EXPECTED.get(strategy), expected_outcome_met=expected_met,
        physical_success=physical_success, physical_safety_passed=safe, passed=physical_success,
        criteria=checks, metrics=dict(duration_s=float(t[-1]-t[0]+dt), probe_requested_shortfall_n=requested_shortfall,
            maximum_certified_force_n=float(np.max(certificate[valid])) if np.any(valid) else None,
            maximum_actual_future_pad_force_n=float(np.max(actual_force[future])) if np.any(future) else None,
            maximum_forward_com_motion_m=float(np.max(advance)), maximum_next_foot_clearance_m=float(np.max(clearance)),
            simultaneous_progress_hold_s=progress_dwell, progress_window_samples=progress_window,
            maximum_roll_pitch_deg=float(np.max(tilt)), maximum_pad_sink_m=float(np.max(data["pad_sink_displacement_m"])),
            pad_failed=bool(np.any(failed)), certificate_updates_audited=len(audits), stable_safe_stop_s=stop_dwell),
        evaluation=evaluation, conventions=dict(passed="Only physical movement SUCCESS; expected collapse and SAFE_STOP are not task completion",
            expected_outcome_met="Protocol outcome validation, distinct from physical success", capacity="Sustained achieved minimum measured force minus measurement reserve; future caps also subtract tracking reserve")))


def analyze_weak_pad(run_dir):
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir/"metadata.json").read_text())
    with np.load(run_dir/"signals.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    result = evaluate_weak_pad(metadata, data)
    result["run_id"] = run_dir.name
    (run_dir/"weak_pad_summary.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    text = [f"# Weak-pad result: {result['outcome']}", "",
        f"Strategy: **{result['strategy']}**. Expected outcome met: **{result['expected_outcome_met']}**. Physical movement success: **{result['physical_success']}**.", "",
        "A survived probe establishes a tested load bound; a requested load or MPC cap alone does not establish capacity.", "",
        "| Check | Result | Requirement |", "| --- | --- | --- |"]
    for name, criterion in result["criteria"].items():
        text.append(f"| {name} | {'pass' if criterion['passed'] else 'not met'} | {criterion['requirement']} |")
    (run_dir/"weak_pad_report.md").write_text("\n".join(text)+"\n")
    t = data["control_time_s"]
    figure, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, constrained_layout=True)
    for key, label in (("requested_probe_force_n", "Requested probe"), ("sensor_pad_normal_force_n", "Measured pad load"),
                       ("certificate_force_n", "Certified load"), ("applied_pad_force_cap_n", "Installed MPC cap")):
        axes[0].plot(t, data[key], label=label, linewidth=1)
    axes[0].axhline(float(result["evaluation"].get("failure_threshold_n", result["evaluation"].get("failure_load_n"))), color="red", linestyle="--", label="Hidden threshold (evaluation only)")
    axes[0].set(ylabel="Normal force (N)")
    axes[0].legend(fontsize=8, ncol=2)
    axes[1].plot(t, 1000*data["pad_sink_displacement_m"], label="Actual pad sink")
    axes[1].set(ylabel="Pad displacement (mm)")
    selected = list(metadata.get("legs", ["FL", "FR", "RL", "RR"])).index(metadata.get("next_lift_leg", "RL"))
    axes[2].plot(t, 1000*(data["com_pos_w"][:, 0]-data["com_pos_w"][0, 0]), label="Measured CoM X from run start")
    axes[2].plot(t, 1000*(data["feet_pos_w"][:, selected, 2]-data["feet_pos_w"][0, selected, 2]), label="Next-foot clearance from run start")
    axes[2].set(xlabel="Control time (s)", ylabel="Measured motion (mm)")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.15)
    figure.suptitle(f"{result['strategy']}: {result['outcome']} — expected outcome is distinct from task success")
    figure.savefig(run_dir/"weak_pad_overview.png", dpi=160)
    plt.close(figure)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    result = analyze_weak_pad(args.run_dir)
    print(json.dumps(dict(outcome=result["outcome"], expected_outcome_met=result["expected_outcome_met"], physical_success=result["physical_success"])))
    return 0 if result["expected_outcome_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
