"""Analyze the recorded Go2 standing run without modifying its raw data.

The limits below are chosen engineering checks for this flat-ground experiment,
not guarantees from a paper or a certification of hardware safety.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


LIMITS = {
    "zero_command_tolerance": 1e-12,
    "max_abs_roll_pitch_deg": 5.0,
    "max_xy_drift_m": 0.02,
    "height_range_m": 0.02,
    "rms_linear_speed_m_s": 0.03,
    "rms_angular_speed_rad_s": 0.05,
    "max_foot_displacement_m": 0.01,
}

REQUIRED_SIGNALS = (
    "time_s", "mujoco_time_s", "control_time_s", "wall_time_s", "phase", "phase_time_s",
    "base_pos_w", "base_quat_wxyz", "base_rpy_rad", "base_lin_vel_w", "base_ang_vel_b", "com_pos_w",
    "feet_pos_w", "feet_desired_w", "feet_foothold_ref_w", "contact_measured", "contact_force_w",
    "contact_normal_force", "contact_count", "contact_planned", "grf_desired_w", "gait_phase",
    "swing_time_s", "cmd_lin_vel_w", "cmd_ang_vel_w", "actuator_torque", "torque_saturated",
    "mpc_update", "mpc_status", "qp_status", "terminated", "truncated", "numerical_warning_count",
)


def _scalar(value):
    value = float(value)
    return value if np.isfinite(value) else None


def _max_abs(value):
    return _scalar(np.max(np.abs(value))) if np.size(value) else None


def _rms_norm(value):
    return _scalar(np.sqrt(np.mean(np.sum(np.square(value), axis=-1)))) if len(value) else None


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return _scalar(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _histogram(values):
    return dict(sorted(Counter(str(int(item)) for item in values).items()))


def _format(value, digits=5):
    return "unavailable" if value is None else f"{value:.{digits}g}"


def analyze_run(run_dir: Path) -> dict:
    """Write summary.json, REPORT.md and overview.png; return the summary.

    Each raw row is the END of an integration interval. The standing statistics
    exclude settling and use the first standing sample as their fixed anchor.
    Partial runs are reported as failed instead of being mistaken for success.
    """
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    with np.load(run_dir / "signals.npz", allow_pickle=False) as archive:
        signals = {name: archive[name] for name in archive.files}
    missing = sorted(set(REQUIRED_SIGNALS) - signals.keys())
    if missing:
        raise ValueError(f"Missing required recorded signals: {missing}")
    n = len(signals["time_s"])
    for name in REQUIRED_SIGNALS:
        if signals[name].ndim == 0 or len(signals[name]) != n:
            raise ValueError(f"Signal {name!r} does not contain {n} aligned rows")

    legs = metadata["legs"]
    dt = float(metadata["dt_s"])
    settling_s = float(metadata["settling_duration_s"])
    standing_s = float(metadata["standing_duration_s"])
    expected_steps = int(metadata["expected_steps"])
    expected_standing_steps = int(round(standing_s / dt))
    mpc_frequency = float(metadata["simulation_params"]["mpc_frequency"])
    mpc_period = int(round(1.0 / (mpc_frequency * dt)))
    if mpc_period < 1:
        raise ValueError("Configured MPC frequency exceeds the integration rate")
    expected_mpc_updates = (expected_steps + mpc_period - 1) // mpc_period
    total_s = settling_s + standing_s
    tolerance = max(1e-8, dt * 1e-6)
    t = signals["time_s"]
    phase = signals["phase"].astype(str)
    standing = phase == "standing"
    settling = phase == "settling"
    standing_indices = np.flatnonzero(standing)
    n_standing = len(standing_indices)
    updates = signals["mpc_update"].astype(bool)
    numeric_bad = [
        name for name, value in signals.items()
        if np.issubdtype(value.dtype, np.number) and not np.all(np.isfinite(value))
    ]

    metrics = {
        "sample_count": n,
        "standing_sample_count": n_standing,
        "settling_sample_count": int(np.count_nonzero(settling)),
        "recorded_duration_s": _scalar(t[-1]) if n else 0.0,
        "standing_interval_coverage_s": n_standing * dt,
        "mpc_solve_count": int(np.count_nonzero(updates)),
        "expected_mpc_solve_count": expected_mpc_updates,
        "configured_mpc_frequency_hz": mpc_frequency,
        "mpc_period_integration_steps": mpc_period,
        "max_control_state_alignment_error_s": _max_abs(signals["control_time_s"] - (t - dt)),
        "mpc_status_counts_at_updates": _histogram(signals["mpc_status"][updates]),
        "qp_status_counts_at_updates": _histogram(signals["qp_status"][updates]),
        "max_abs_linear_command_m_s": _max_abs(signals["cmd_lin_vel_w"]),
        "max_abs_angular_command_rad_s": _max_abs(signals["cmd_ang_vel_w"]),
        "max_abs_actuator_torque_nm": _max_abs(signals["actuator_torque"]),
        "saturated_actuator_sample_count": int(np.count_nonzero(signals["torque_saturated"])),
        "numerical_warning_count_max": int(np.max(signals["numerical_warning_count"])) if n else None,
        "terminated_sample_count": int(np.count_nonzero(signals["terminated"])),
        "truncated_sample_count": int(np.count_nonzero(signals["truncated"])),
        "nonfinite_signals": numeric_bad,
        "wall_time_last_sample_s": _scalar(signals["wall_time_s"][-1]) if n else None,
        "model_weight_n": float(metadata["model_mass_kg"]) * float(metadata["gravity_m_s2"]),
    }
    metrics["settling_contact_fraction_by_leg"] = {
        leg: _scalar(np.mean(signals["contact_measured"][settling, index])) if np.any(settling) else None
        for index, leg in enumerate(legs)
    }
    metrics["first_measured_contact_time_s_by_leg"] = {}
    for index, leg in enumerate(legs):
        contact_indices = np.flatnonzero(signals["contact_measured"][:, index])
        metrics["first_measured_contact_time_s_by_leg"][leg] = (
            _scalar(t[contact_indices[0]]) if len(contact_indices) else None
        )

    settled = {}
    if n_standing:
        anchor_index = standing_indices[0]
        base = signals["base_pos_w"][standing]
        feet = signals["feet_pos_w"][standing]
        foot_displacement = np.linalg.norm(feet - feet[0], axis=-1)
        desired_error = np.linalg.norm(signals["feet_desired_w"][standing] - feet, axis=-1)
        foothold_error = np.linalg.norm(signals["feet_foothold_ref_w"][standing] - feet, axis=-1)
        measured_fz = signals["contact_force_w"][standing, :, 2]
        desired_fz = signals["grf_desired_w"][standing, :, 2]
        settled = {
            "anchor_time_s": _scalar(t[anchor_index]),
            "anchor_base_pos_w_m": base[0],
            "anchor_feet_pos_w_m": feet[0],
            "final_base_pos_w_m": base[-1],
            "base_height_min_m": _scalar(np.min(base[:, 2])),
            "base_height_max_m": _scalar(np.max(base[:, 2])),
            "height_range_m": _scalar(np.ptp(base[:, 2])),
            "max_abs_roll_pitch_deg": _scalar(np.rad2deg(np.max(np.abs(signals["base_rpy_rad"][standing, :2])))),
            "max_xy_drift_m": _scalar(np.max(np.linalg.norm(base[:, :2] - base[0, :2], axis=-1))),
            "final_xy_drift_m": _scalar(np.linalg.norm(base[-1, :2] - base[0, :2])),
            "rms_linear_speed_m_s": _rms_norm(signals["base_lin_vel_w"][standing]),
            "rms_angular_speed_rad_s": _rms_norm(signals["base_ang_vel_b"][standing]),
            "max_foot_displacement_m": _scalar(np.max(foot_displacement)),
            "max_abs_actuator_torque_nm": _max_abs(signals["actuator_torque"][standing]),
            "all_four_feet_contact_fraction": _scalar(np.mean(np.all(signals["contact_measured"][standing], axis=1))),
            "mean_total_measured_fz_n": _scalar(np.mean(np.sum(measured_fz, axis=1))),
            "mean_total_desired_fz_n": _scalar(np.mean(np.sum(desired_fz, axis=1))),
            "per_leg": {},
        }
        settled["mean_vertical_support_to_model_weight"] = (
            settled["mean_total_measured_fz_n"] / metrics["model_weight_n"]
            if settled["mean_total_measured_fz_n"] is not None and metrics["model_weight_n"] > 0 else None
        )
        for index, leg in enumerate(legs):
            settled["per_leg"][leg] = {
                "measured_contact_fraction": _scalar(np.mean(signals["contact_measured"][standing, index])),
                "missing_contact_samples": int(np.count_nonzero(~signals["contact_measured"][standing, index].astype(bool))),
                "max_fixed_anchor_displacement_m": _scalar(np.max(foot_displacement[:, index])),
                "rms_desired_actual_distance_m": _scalar(np.sqrt(np.mean(desired_error[:, index] ** 2))),
                "max_desired_actual_distance_m": _scalar(np.max(desired_error[:, index])),
                "rms_foothold_reference_distance_m": _scalar(np.sqrt(np.mean(foothold_error[:, index] ** 2))),
                "mean_measured_fz_n": _scalar(np.mean(measured_fz[:, index])),
                "mean_desired_fz_n": _scalar(np.mean(desired_fz[:, index])),
                "rms_measured_minus_desired_fz_n": _scalar(np.sqrt(np.mean((measured_fz[:, index] - desired_fz[:, index]) ** 2))),
            }
    metrics["standing"] = settled

    criteria = {}

    def check(name, passed, requirement, observed):
        criteria[name] = {"passed": bool(passed), "requirement": requirement, "observed": observed}

    check("completed", metadata.get("status") == "completed", "Runner status is completed", metadata.get("status"))
    check("sample_count", n == expected_steps, f"Exactly {expected_steps} integration intervals", n)
    check("total_duration", n > 0 and abs(float(t[-1]) - total_s) <= tolerance,
          f"Final experiment time {total_s:g} s", metrics["recorded_duration_s"])
    check("time_grid", n > 0 and np.allclose(t, np.arange(1, n + 1) * dt, rtol=0, atol=tolerance),
          f"End-of-interval times on {dt:g} s grid, no reset or gap", n)
    check("control_state_alignment", n > 0 and np.allclose(signals["control_time_s"], t - dt, rtol=0, atol=tolerance),
          "Control timestamp is the start of its recorded state interval (time_s - dt)",
          metrics["max_control_state_alignment_error_s"])
    raw_dt = np.diff(signals["mujoco_time_s"])
    check("mujoco_clock", n > 1 and np.allclose(raw_dt, dt, rtol=0, atol=tolerance),
          "Raw MuJoCo clock advances one dt per sample without reset",
          _scalar(np.min(raw_dt)) if len(raw_dt) else None)
    expected_phase = np.where(t > settling_s + tolerance, "standing", "settling")
    expected_phase_time = np.where(standing, t - settling_s, t)
    phase_valid = (
        n_standing == expected_standing_steps
        and np.array_equal(phase, expected_phase)
        and np.allclose(signals["phase_time_s"], expected_phase_time, rtol=0, atol=tolerance)
    )
    check("standing_duration", phase_valid, f"Exactly {standing_s:g} s / {expected_standing_steps} standing intervals after settling",
          metrics["standing_interval_coverage_s"])
    check("finite_data", not numeric_bad, "Every numeric raw array is finite", numeric_bad)
    zero_command = (
        n > 0 and np.all(np.abs(signals["cmd_lin_vel_w"]) <= LIMITS["zero_command_tolerance"])
        and np.all(np.abs(signals["cmd_ang_vel_w"]) <= LIMITS["zero_command_tolerance"])
    )
    check("zero_velocity_command", zero_command, "All linear and angular command components <= 1e-12 in magnitude",
          [metrics["max_abs_linear_command_m_s"], metrics["max_abs_angular_command_rad_s"]])
    check("no_termination", n > 0 and not np.any(signals["terminated"] | signals["truncated"]),
          "No terminated or truncated sample", [metrics["terminated_sample_count"], metrics["truncated_sample_count"]])
    check("no_numerical_warnings", n > 0 and not np.any(signals["numerical_warning_count"]),
          "No MuJoCo numerical warnings", metrics["numerical_warning_count_max"])
    check("planned_full_stance", n > 0 and np.all(signals["contact_planned"]),
          "All four scheduled support flags true throughout", int(np.count_nonzero(~signals["contact_planned"].astype(bool))))
    check("measured_full_stance", n_standing > 0 and np.all(signals["contact_measured"][standing]),
          "Every foot has an active contact at every standing sample",
          {leg: item["missing_contact_samples"] for leg, item in settled.get("per_leg", {}).items()})
    cadence_matches = (
        n > 0 and metrics["mpc_solve_count"] == expected_mpc_updates
        and np.array_equal(updates, np.arange(n) % mpc_period == 0)
    )
    check("mpc_update_cadence", cadence_matches,
          f"{expected_mpc_updates} MPC updates at {mpc_frequency:g} Hz; every {mpc_period} intervals starting at control t=0",
          metrics["mpc_solve_count"])
    check("qp_success", np.any(updates) and np.all(signals["qp_status"][updates] == 0),
          "QP status 0 at every MPC update", metrics["qp_status_counts_at_updates"])
    check("nlp_status", np.any(updates) and np.all(np.isin(signals["mpc_status"][updates], [0, 2])),
          "NLP status 0 or 2 at every MPC update", metrics["mpc_status_counts_at_updates"])
    for name in ("max_abs_roll_pitch_deg", "max_xy_drift_m", "height_range_m", "rms_linear_speed_m_s", "rms_angular_speed_rad_s", "max_foot_displacement_m"):
        observed = settled.get(name)
        check(name, observed is not None and observed <= LIMITS[name], f"Standing {name} <= {LIMITS[name]:g}", observed)

    summary = _json_safe({
        "passed": all(item["passed"] for item in criteria.values()),
        "robot": metadata["robot"],
        "controller": metadata["controller"],
        "runner_status": metadata.get("status"),
        "runner_error": metadata.get("error"),
        "criteria_basis": "Chosen engineering acceptance limits for this flat-ground standing experiment; not paper guarantees.",
        "limits": LIMITS,
        "sample_convention": "Rows are interval endpoints; no t=0 row. Standing covers (settling_duration, total_duration].",
        "anchor_convention": "First standing sample, held fixed for all body and foot drift measurements.",
        "mpc_status_note": "Status 2 is the configured SQP iteration budget being reached. QP success is checked independently; full NLP convergence is not claimed.",
        "foot_error_note": "Desired and foothold-reference errors are diagnostics. Full-stance desired positions can copy sensed feet, so small errors do not demonstrate independent stance-trajectory tracking.",
        "criteria": criteria,
        "metrics": metrics,
    })
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _write_report(run_dir, metadata, summary)
    _write_plot(run_dir, signals, metadata, summary)
    return summary


def _write_report(run_dir, metadata, summary):
    metrics = summary["metrics"]
    settled = metrics["standing"]
    result = "PASS" if summary["passed"] else "FAIL"
    lines = [
        f"# Go2 zero-command standing experiment — {result}", "",
        f"Robot `{summary['robot']}`, controller `{summary['controller']}`. Recorded "
        f"{metrics['sample_count']} intervals at {metadata['dt_s']:g} s; "
        f"{_format(metrics['recorded_duration_s'])} s total, including "
        f"{metadata['settling_duration_s']:g} s settling and "
        f"{_format(metrics['standing_interval_coverage_s'])} s evaluated standing.", "",
        "Acceptance limits were chosen for this flat-ground experiment. They are not paper guarantees. "
        "All raw startup samples remain in `signals.npz`; motion/contact criteria use only the standing phase.", "",
        "Rows are interval endpoints, with no initial t=0 row. Body and foot drift use a fixed anchor at "
        f"the first standing sample, t={_format(settled.get('anchor_time_s'))} s. "
        "Coordinates are world-frame meters, orientation is Euler XYZ, and angular velocity is expressed in the base frame.", "",
        "| Check | Result | Requirement | Observed |",
        "|---|---|---|---|",
    ]
    for name, criterion in summary["criteria"].items():
        observed = criterion["observed"]
        if isinstance(observed, (dict, list)):
            observed = json.dumps(observed, sort_keys=True)
        elif isinstance(observed, (float, int)):
            observed = _format(observed)
        lines.append(f"| {name} | {'PASS' if criterion['passed'] else 'FAIL'} | {criterion['requirement']} | {observed} |")
    lines += [
        "", f"MPC updates: {metrics['mpc_solve_count']}; NLP statuses: "
        f"`{metrics['mpc_status_counts_at_updates']}`; QP statuses: `{metrics['qp_status_counts_at_updates']}`. "
        + summary["mpc_status_note"], "",
        f"Model weight: {_format(metrics['model_weight_n'])} N. Mean measured vertical support during standing: "
        f"{_format(settled.get('mean_total_measured_fz_n'))} N "
        f"({_format(settled.get('mean_vertical_support_to_model_weight'))} × model weight). "
        f"Maximum commanded actuator torque: {_format(metrics['max_abs_actuator_torque_nm'])} N·m; "
        f"clipped actuator samples: {metrics['saturated_actuator_sample_count']}.", "",
        "| Foot | Standing contact | Max fixed-anchor drift (m) | RMS desired−actual distance (m) | Mean measured / desired Fz (N) |",
        "|---|---:|---:|---:|---:|",
    ]
    for leg in metadata["legs"]:
        item = settled.get("per_leg", {}).get(leg, {})
        lines.append(
            f"| {leg} | {_format(item.get('measured_contact_fraction'))} | "
            f"{_format(item.get('max_fixed_anchor_displacement_m'))} | "
            f"{_format(item.get('rms_desired_actual_distance_m'))} | "
            f"{_format(item.get('mean_measured_fz_n'))} / {_format(item.get('mean_desired_fz_n'))} |"
        )
    lines += [
        "", summary["foot_error_note"], "",
        "No commanded base-height signal is part of this dataset. The height criterion measures variation, "
        "not absolute reference tracking; the upstream terrain estimator uses foot-center heights, so a "
        "world-z comparison against nominal hip height alone would be misleading.", "",
        "![Standing experiment overview](overview.png)", "",
        "Raw signals: `signals.npz`. Configuration and provenance: `metadata.json`. "
        "Machine-readable criteria and metrics: `summary.json`.",
    ]
    if summary["runner_error"]:
        lines += ["", f"Runner error: `{str(summary['runner_error']).replace('`', '')}`."]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def _write_plot(run_dir, signals, metadata, summary):
    t = signals["time_s"]
    fig, axes = plt.subplots(3, 3, figsize=(17, 12), constrained_layout=True)
    axes = axes.ravel()
    title_result = "PASS" if summary["passed"] else "FAIL"
    fig.suptitle(f"Go2 nominal full-stance, zero velocity command — {title_result}\n"
                 "Gray region: settling; drift anchor: first standing sample", fontsize=15)
    if not len(t):
        for ax in axes:
            ax.set_axis_off()
        axes[0].text(0.1, 0.5, "No simulation samples recorded", transform=axes[0].transAxes)
        fig.savefig(run_dir / "overview.png", dpi=160)
        plt.close(fig)
        return
    legs = metadata["legs"]
    colors = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]
    standing = signals["phase"].astype(str) == "standing"
    anchor_index = int(np.flatnonzero(standing)[0]) if np.any(standing) else 0
    base_displacement_mm = (signals["base_pos_w"] - signals["base_pos_w"][anchor_index]) * 1000
    for index, label in enumerate(("x", "y", "z")):
        axes[0].plot(t, base_displacement_mm[:, index], label=label, linewidth=1.1)
        axes[1].plot(t, np.rad2deg(signals["base_rpy_rad"][:, index]), label=("roll", "pitch", "yaw")[index], linewidth=1.1)
    axes[0].set(title="Base displacement from fixed standing anchor", ylabel="World XYZ displacement (mm)")
    axes[1].set(title="Base orientation", ylabel="Euler XYZ (deg)")
    for ax in axes[:2]:
        ax.legend(loc="best", fontsize=8)
    foot_displacement = np.linalg.norm(signals["feet_pos_w"] - signals["feet_pos_w"][anchor_index], axis=-1)
    desired_error = np.linalg.norm(signals["feet_desired_w"] - signals["feet_pos_w"], axis=-1)
    for index, leg in enumerate(legs):
        axes[2].plot(t, foot_displacement[:, index] * 1000, color=colors[index], label=leg, linewidth=1)
        positive_error_mm = np.where(desired_error[:, index] > 0, desired_error[:, index] * 1000, np.nan)
        axes[3].plot(t, positive_error_mm, color=colors[index], label=leg, linewidth=1)
        ax = axes[4 + index]
        ax.plot(t, signals["contact_force_w"][:, index, 2], color=colors[index], label="Measured", linewidth=1)
        ax.plot(t, signals["grf_desired_w"][:, index, 2], color="#333333", linestyle="--", label="MPC desired", linewidth=1)
        ax.set(title=f"{leg} vertical contact force", ylabel="World Fz (N)")
        ax.legend(loc="best", fontsize=8)
    axes[2].text(0.02, 0.96, f"Standing acceptance limit: {LIMITS['max_foot_displacement_m'] * 1000:g} mm",
                 transform=axes[2].transAxes, va="top", fontsize=8, color="#555555")
    axes[2].set(title="Foot displacement from fixed standing anchor", ylabel="3D displacement (mm)")
    axes[3].set(title="Foot desired−actual distance (diagnostic)", ylabel="3D distance (mm, log scale)", yscale="log")
    axes[2].legend(loc="best", fontsize=8)
    axes[3].legend(loc="best", fontsize=8)
    contact_rows = np.stack([
        signals[name][:, index]
        for index in range(len(legs))
        for name in ("contact_measured", "contact_planned")
    ])
    axes[8].imshow(contact_rows, aspect="auto", interpolation="nearest", origin="upper",
                   extent=(float(t[0] - metadata["dt_s"]), float(t[-1]), 7.5, -0.5),
                   cmap=ListedColormap(["#e8e8e8", "#176e6c"]), vmin=0, vmax=1)
    axes[8].set(title="Contact support: green=on, light=off", yticks=np.arange(8),
                yticklabels=[f"{leg} {kind}" for leg in legs for kind in ("measured", "planned")])
    for ax in axes:
        ax.axvspan(0, metadata["settling_duration_s"], color="#808080", alpha=0.14, linewidth=0)
        ax.axvline(metadata["settling_duration_s"], color="#777777", linewidth=0.7, linestyle=":")
        ax.set_xlabel("Experiment time (s)")
        ax.set_xlim(0, max(float(t[-1]), float(metadata["dt_s"])))
        ax.tick_params(labelsize=8)
        if ax is not axes[8]:
            ax.grid(alpha=0.2)
    fig.savefig(run_dir / "overview.png", dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project analyze-standing", description=__doc__)
    parser.add_argument("run_dir", type=Path)
    arguments = parser.parse_args(argv)
    result = analyze_run(arguments.run_dir)
    from primp_project.recording.catalog import refresh_catalog
    refresh_catalog()
    print(json.dumps({"passed": result["passed"], "report": str(arguments.run_dir / "REPORT.md")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
