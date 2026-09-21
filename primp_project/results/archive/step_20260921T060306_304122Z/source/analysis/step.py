"""Independent acceptance checks for a controlled three-leg-support experiment.

These are engineering acceptance limits for the recorded simulation, not a
proof of stability or a hardware safety certification. No controller is loaded.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


PHASES = ("stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete")
LIMITS = {
    "minimum_hold_clearance_m": 0.02,
    "minimum_hold_support_margin_m": 0.01,
    "maximum_abs_roll_pitch_deg": 8.0,
    "maximum_selected_foot_tracking_error_m": 0.012,
    "maximum_support_foot_displacement_m": 0.01,
    "force_cap_tolerance_n": 1.0,
    "minimum_final_stance_s": 1.0,
    "minimum_landing_normal_force_n": 2.0,
    "minimum_unload_reload_duration_s": 3.0,
    "maximum_pre_lift_selected_normal_force_n": 3.0,
    "minimum_pre_lift_support_normal_force_n": 5.0,
    "minimum_pre_lift_support_margin_m": 0.02,
    "maximum_pre_lift_force_cap_n": 0.1,
    "minimum_restored_foot_normal_force_n": 5.0,
    "minimum_reload_loading_duration_s": 0.2,
}
REQUIRED = (
    "time_s", "mujoco_time_s", "control_time_s", "step", "phase", "cycle", "base_rpy_rad", "com_pos_w",
    "feet_pos_w", "feet_desired_w", "foot_anchor_w", "contact_measured", "contact_planned",
    "contact_normal_force", "contact_force_w", "grf_desired_w", "support_margin_m", "selected_force_cap_N",
    "contact_confirmed", "landing_contact_dwell_s", "desired_foot_vel_w", "desired_foot_acc_w",
    "mpc_update", "mpc_status", "qp_status", "terminated", "truncated", "numerical_warning_count",
    "torque_saturated", "actuator_torque",
)


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (np.ndarray, list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _extreme(values, maximum=True):
    return float(np.max(values) if maximum else np.min(values)) if np.size(values) else None


def _segments(values):
    return [str(value) for index, value in enumerate(values) if index == 0 or value != values[index - 1]]


def _triangle_margin(com, triangle):
    """Signed distance to the nearest triangle edge; positive is inside."""
    vertices = triangle[..., :2]
    edges = np.roll(vertices, -1, axis=1) - vertices
    delta = com[:, None, :2] - vertices
    cross = edges[..., 0] * delta[..., 1] - edges[..., 1] * delta[..., 0]
    ab, ac = vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0]
    orientation = np.sign(ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0])
    lengths = np.linalg.norm(edges, axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        margins = np.min(cross * orientation[:, None] / lengths, axis=1)
    return np.where((orientation != 0) & np.all(lengths > 1e-9, axis=1), margins, np.nan)


def analyze_step(run_dir: Path) -> dict:
    """Read recorded evidence and write step_summary.json/report/overview."""
    run_dir = Path(run_dir)
    source_dir = run_dir / "source" / "analysis"
    source_dir.mkdir(parents=True, exist_ok=True)
    analyzer_source = Path(__file__).resolve()
    analyzer_snapshot = source_dir / "step.py"
    if analyzer_snapshot.resolve() != analyzer_source:
        shutil.copy2(analyzer_source, analyzer_snapshot)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    with np.load(run_dir / "signals.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    missing = sorted(set(REQUIRED) - data.keys())
    if missing:
        raise ValueError(f"Missing step-experiment signals: {missing}")
    t = data["time_s"]
    n = len(t)
    for name in REQUIRED:
        if data[name].ndim == 0 or len(data[name]) != n:
            raise ValueError(f"Signal {name!r} does not have {n} aligned samples")
    dt = float(metadata["dt_s"])
    tolerance = max(1e-8, dt * 1e-6)
    legs = list(metadata["legs"])
    selected = legs.index(metadata["selected_leg"])
    supports = [index for index in range(4) if index != selected]
    expected_cycles = int(metadata["cycles"])
    requested_hold = float(metadata["hold_seconds"])
    lift_height = float(metadata["lift_height_m"])
    debounce = float(metadata.get("contact_debounce_s", 0.0))
    phase = data["phase"].astype(str)
    cycle = data["cycle"].astype(int)
    updates = data["mpc_update"].astype(bool)
    standing_updates = updates & (t > float(metadata.get("settling_duration_s", 0.0)) + tolerance)
    measured = data["contact_measured"].astype(bool)
    planned = data["contact_planned"].astype(bool)
    feet = data["feet_pos_w"]
    desired = data["feet_desired_w"][:, selected]
    selected_pos = feet[:, selected]
    clearance = selected_pos[:, 2] - data["foot_anchor_w"][:, 2]
    tracking = np.linalg.norm(selected_pos - desired, axis=1)
    physical_margin = _triangle_margin(data["com_pos_w"], feet[:, supports])
    tilt = np.rad2deg(np.max(np.abs(data["base_rpy_rad"][:, :2]), axis=1))
    support_drift = np.full((n, 3), np.nan)
    finite_bad = [name for name, array in data.items() if np.issubdtype(array.dtype, np.number) and not np.all(np.isfinite(array))]

    checks = {}

    def check(name, passed, requirement, observed):
        checks[name] = {"passed": bool(passed), "requirement": requirement, "observed": observed}

    check("completed", metadata.get("status") == "completed" and metadata.get("actual_completed_cycles") == expected_cycles,
          f"Completed status and exactly {expected_cycles} completed cycles",
          {"status": metadata.get("status"), "completed_cycles": metadata.get("actual_completed_cycles")})
    check("cycle_labels", n > 0 and np.array_equal(np.unique(cycle), np.arange(1, expected_cycles + 1)) and np.all(np.diff(cycle) >= 0),
          "Every requested cycle appears in chronological order", np.unique(cycle))
    check("sample_clock", n > 1 and np.allclose(t, np.arange(1, n + 1) * dt, atol=tolerance, rtol=0)
          and np.allclose(np.diff(data["mujoco_time_s"]), dt, atol=tolerance, rtol=0),
          "Continuous end-of-interval sampling with no reset or time gap", {"rows": n, "last_time_s": t[-1] if n else None})
    check("control_alignment", n > 0 and np.allclose(data["control_time_s"], t - dt, atol=tolerance, rtol=0),
          "Control timestamp equals interval endpoint minus dt", _extreme(np.abs(data["control_time_s"] - t + dt)))
    # Reconstruct the expected solve schedule independently of mpc_update.
    # The controller solves on the fixed physics-step grid, at initialization,
    # and immediately when its binary support schedule changes.
    try:
        frequency = float(metadata.get("simulation_params", {}).get("mpc_frequency"))
    except (TypeError, ValueError):
        frequency = float("nan")
    frequency_valid = np.isfinite(frequency) and np.isfinite(dt) and dt > 0 and 0 < frequency <= 1.0 / dt
    period = int(round(1.0 / (frequency * dt))) if frequency_valid else 0
    periodic = np.arange(n) % period == 0 if period > 0 else np.zeros(n, dtype=bool)
    support_changes = np.zeros(n, dtype=bool)
    support_changes[1:] = np.any(planned[1:] != planned[:-1], axis=1)
    expected_updates = periodic | support_changes
    if n:
        expected_updates[0] = True
    step_sequence_valid = np.array_equal(data["step"], np.arange(1, n + 1))
    check("mpc_update_cadence", n > 0 and period > 0 and step_sequence_valid
          and np.array_equal(updates, expected_updates),
          "MPC updates match the configured fixed-step cadence, initialization, and immediate support changes; no missing or unexplained solves",
          {"configured_frequency_hz": frequency,
           "effective_periodic_frequency_hz": 1.0 / (period * dt) if period > 0 else None,
           "period_in_physics_steps": period if period > 0 else None,
           "step_sequence_valid": step_sequence_valid,
           "expected_updates": int(np.count_nonzero(expected_updates)),
           "recorded_updates": int(np.count_nonzero(updates)),
           "extra_support_change_updates": int(np.count_nonzero(support_changes & ~periodic)),
           "missing_periodic_updates": int(np.count_nonzero(periodic & ~updates)),
           "missing_support_change_updates": int(np.count_nonzero(support_changes & ~updates)),
           "unexpected_updates": int(np.count_nonzero(updates & ~expected_updates))})
    check("finite_data", not finite_bad and n > 0, "All recorded numerical signals finite", finite_bad)
    check("no_termination", n > 0 and not np.any(data["terminated"] | data["truncated"]),
          "No termination or truncation", int(np.count_nonzero(data["terminated"] | data["truncated"])))
    check("no_numerical_warnings", n > 0 and not np.any(data["numerical_warning_count"]),
          "No MuJoCo numerical warnings", _extreme(data["numerical_warning_count"]))
    check("no_torque_saturation", n > 0 and not np.any(data["torque_saturated"]),
          "No actuator command clipping", int(np.count_nonzero(data["torque_saturated"])))
    check("qp_success", np.any(updates) and np.all(data["qp_status"][updates] == 0),
          "Every MPC update has QP status 0", Counter(map(str, data["qp_status"][updates])))
    check("nlp_status", np.any(standing_updates) and np.all(np.isin(data["mpc_status"][standing_updates], [0, 2])),
          "Post-settling MPC NLP status is 0 or 2", Counter(map(str, data["mpc_status"][standing_updates])))
    cap_excess = data["grf_desired_w"][:, selected, 2] - data["selected_force_cap_N"]
    check("selected_force_cap", np.any(updates) and np.all(cap_excess[updates] <= LIMITS["force_cap_tolerance_n"]),
          "Desired selected-foot vertical force <= configured cap + 1 N at MPC updates", _extreme(cap_excess[updates]))
    check("body_tilt", n > 0 and np.all(tilt < LIMITS["maximum_abs_roll_pitch_deg"]),
          "Maximum absolute roll or pitch < 8 degrees", _extreme(tilt))

    cycle_metrics = []
    landing_events = []
    for number in range(1, expected_cycles + 1):
        mask = cycle == number
        indices = np.flatnonzero(mask)
        compressed = _segments(phase[mask])
        expected_order = list(PHASES[:-1])
        observed_order = compressed[:-1] if compressed and compressed[-1] == "complete" else compressed
        check(f"cycle_{number}_phase_order", observed_order == expected_order,
              "All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order", compressed)
        durations = {name: float(np.count_nonzero(mask & (phase == name)) * dt) for name in PHASES}
        hold = mask & (phase == "hold")
        swing = mask & np.isin(phase, ["lift", "hold", "lower", "confirm"])
        support_required = mask & np.isin(phase, ["unload", "lift", "hold", "lower", "confirm", "reload"])
        reload = np.flatnonzero(mask & (phase == "reload"))
        unload = np.flatnonzero(mask & (phase == "unload"))
        lift = np.flatnonzero(mask & (phase == "lift"))
        shifts = np.flatnonzero(mask & (phase == "shift"))
        anchor_index = int(shifts[0]) if len(shifts) else (int(indices[0]) if len(indices) else None)
        if anchor_index is not None:
            support_drift[indices] = np.linalg.norm(feet[indices][:, supports] - feet[anchor_index, supports], axis=-1)
        support_window = mask & ~np.isin(phase, ["stand"])
        anchor_fixed = np.any(swing) and np.allclose(data["foot_anchor_w"][swing], data["foot_anchor_w"][swing][0], atol=1e-8, rtol=0)
        target_expected = data["foot_anchor_w"][hold] + np.array([0.0, 0.0, lift_height])
        hold_reference = (np.any(hold) and np.allclose(desired[hold], target_expected, atol=1e-7, rtol=0)
                          and np.allclose(data["desired_foot_vel_w"][hold], 0, atol=1e-9, rtol=0)
                          and np.allclose(data["desired_foot_acc_w"][hold], 0, atol=1e-9, rtol=0))
        check(f"cycle_{number}_hold_duration", durations["hold"] + dt + tolerance >= requested_hold,
              f"Continuous hold >= {requested_hold:g} s with at most one sample of boundary tolerance", durations["hold"])
        check(f"cycle_{number}_hold_contact", np.any(hold) and not np.any(measured[hold, selected]) and not np.any(planned[hold, selected])
              and np.all(measured[hold][:, supports]) and np.all(planned[hold][:, supports]),
              "Selected foot has neither contact nor planned support; other three have both for every hold sample",
              {"selected_measured_samples": int(np.count_nonzero(measured[hold, selected])),
               "selected_planned_samples": int(np.count_nonzero(planned[hold, selected])),
               "missing_support_measured_samples": int(np.count_nonzero(~measured[hold][:, supports])),
               "missing_support_planned_samples": int(np.count_nonzero(~planned[hold][:, supports]))})
        check(f"cycle_{number}_swing_schedule", np.any(swing) and not np.any(planned[swing, selected]) and np.all(planned[swing][:, supports]),
              "Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm",
              {"selected_planned_samples": int(np.count_nonzero(planned[swing, selected])),
               "missing_support_planned_samples": int(np.count_nonzero(~planned[swing][:, supports]))})
        check(f"cycle_{number}_support_contact_continuity", np.any(support_required) and np.all(measured[support_required][:, supports]),
              "All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload",
              int(np.count_nonzero(~measured[support_required][:, supports])))
        check(f"cycle_{number}_hold_clearance", np.any(hold) and np.all(clearance[hold] >= LIMITS["minimum_hold_clearance_m"]),
              "Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold", _extreme(clearance[hold], False))
        check(f"cycle_{number}_support_margin", np.any(hold) and np.all(physical_margin[hold] >= LIMITS["minimum_hold_support_margin_m"])
              and np.all(data["support_margin_m"][hold] >= LIMITS["minimum_hold_support_margin_m"]),
              "Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold",
              {"independent_minimum_m": _extreme(physical_margin[hold], False), "logged_minimum_m": _extreme(data["support_margin_m"][hold], False)})
        check(f"cycle_{number}_fixed_lift_reference", anchor_fixed and hold_reference,
              f"Immutable lift anchor and constant hold target {lift_height:g} m above it, with zero desired velocity/acceleration", anchor_fixed and hold_reference)
        check(f"cycle_{number}_foot_tracking", np.any(swing) and np.all(tracking[swing] < LIMITS["maximum_selected_foot_tracking_error_m"]),
              "Selected-foot 3D error < 12 mm during lift, hold, lower and confirm", _extreme(tracking[swing]))
        check(f"cycle_{number}_support_slip", np.any(support_window) and np.all(support_drift[support_window] < LIMITS["maximum_support_foot_displacement_m"]),
              "All three support feet stay within 10 mm of their fixed positions at shift entry", _extreme(support_drift[support_window]))
        lift_gate, lift_evidence = False, None
        if len(unload) and len(lift):
            prior = int(unload[-1])
            lift_gate = (
                prior == int(lift[0]) - 1
                and data["contact_normal_force"][prior, selected] < LIMITS["maximum_pre_lift_selected_normal_force_n"]
                and np.all(data["contact_normal_force"][prior, supports] > LIMITS["minimum_pre_lift_support_normal_force_n"])
                and physical_margin[prior] >= LIMITS["minimum_pre_lift_support_margin_m"]
                and 0 <= data["selected_force_cap_N"][prior] <= LIMITS["maximum_pre_lift_force_cap_n"]
            )
            lift_evidence = {
                "last_unload_time_s": float(t[prior]),
                "selected_normal_force_n": float(data["contact_normal_force"][prior, selected]),
                "minimum_support_normal_force_n": float(np.min(data["contact_normal_force"][prior, supports])),
                "physical_support_margin_m": float(physical_margin[prior]),
                "selected_force_cap_n": float(data["selected_force_cap_N"][prior]),
            }
        check(f"cycle_{number}_lift_entry_guard", lift_gate,
              "Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N", lift_evidence)
        cap_ramps = (
            len(unload) > 0 and len(reload) > 0
            and durations["unload"] + dt + tolerance >= LIMITS["minimum_unload_reload_duration_s"]
            and durations["reload"] + dt + tolerance >= LIMITS["minimum_unload_reload_duration_s"]
            and np.all(np.diff(data["selected_force_cap_N"][unload]) <= 1e-8)
            and np.all(np.diff(data["selected_force_cap_N"][reload]) >= -1e-8)
        )
        check(f"cycle_{number}_force_cap_ramps", cap_ramps,
              "Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload",
              {"unload_duration_s": durations["unload"], "reload_duration_s": durations["reload"],
               "maximum_unload_cap_increase_n": _extreme(np.diff(data["selected_force_cap_N"][unload])),
               "maximum_reload_cap_decrease_n": _extreme(-np.diff(data["selected_force_cap_N"][reload]))})
        reload_valid = False
        reload_evidence = None
        if len(reload):
            first_reload = int(reload[0])
            dwell = float(data["landing_contact_dwell_s"][first_reload])
            # The gate reads state at interval START; recorded contacts are at
            # interval END. Allow one boundary sample, never an interior gap.
            required_debounce_samples = max(1, int(np.ceil(debounce / dt - 1e-9)) - 1)
            start_debounce = first_reload - required_debounce_samples
            window = slice(max(0, start_debounce), first_reload)
            debounce_force = data["contact_normal_force"][window, selected]
            independent_debounce = (
                start_debounce >= 0
                and np.all(cycle[window] == number)
                and np.all(measured[window, selected])
                and np.all(debounce_force >= LIMITS["minimum_landing_normal_force_n"])
            )
            reload_valid = (bool(data["contact_confirmed"][first_reload]) and bool(measured[first_reload, selected])
                            and dwell > 0 and dwell + tolerance >= debounce
                            and np.any(mask[:first_reload] & (phase[:first_reload] == "confirm"))
                            and independent_debounce)
            reload_evidence = {"time_s": float(t[first_reload]), "contact_confirmed": bool(data["contact_confirmed"][first_reload]),
                               "measured_contact": bool(measured[first_reload, selected]), "dwell_s": dwell,
                               "independent_debounce_samples": required_debounce_samples,
                               "independent_debounce_duration_s": required_debounce_samples * dt,
                               "independent_debounce_min_normal_force_n": _extreme(debounce_force, False),
                               "independent_debounce_passed": independent_debounce}
        check(f"cycle_{number}_reload_gate", reload_valid,
              f"Reload follows confirm and recorded dwell >= {debounce:g} s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample", reload_evidence)

        # Touchdown confirmation proves only a small initial landing load.
        # Restored support requires every foot to carry load for the controller's
        # 0.2 s reload-completion dwell, including the next command interval.
        loading_samples = max(1, int(np.ceil(LIMITS["minimum_reload_loading_duration_s"] / dt - 1e-9)))
        recenter = np.flatnonzero(mask & (phase == "recenter"))
        reload_loaded = False
        reload_loading_evidence = None
        if len(reload) >= loading_samples and len(recenter):
            end_reload, start_recenter = int(reload[-1]), int(recenter[0])
            loading_window = np.r_[reload[-loading_samples:], start_recenter]
            forces = data["contact_normal_force"][loading_window]
            reload_loaded = (
                end_reload + 1 == start_recenter
                and np.all(np.diff(loading_window) == 1)
                and np.all(measured[loading_window]) and np.all(planned[loading_window])
                and np.all(forces > LIMITS["minimum_restored_foot_normal_force_n"])
            )
            reload_loading_evidence = {
                "reload_dwell_s": loading_samples * dt,
                "first_recenter_time_s": float(t[start_recenter]),
                "minimum_normal_force_n_by_leg": dict(zip(legs, np.min(forces, axis=0))),
                "missing_measured_or_planned_contacts": int(np.count_nonzero(~measured[loading_window] | ~planned[loading_window])),
            }
        check(f"cycle_{number}_reload_loading", reload_loaded,
              "All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample",
              reload_loading_evidence)

        landing_mask = mask & np.isin(phase, ["lower", "confirm", "reload"])
        candidates = np.flatnonzero(landing_mask & measured[:, selected])
        landing = None
        if len(candidates):
            first_contact = int(candidates[0])
            impact_window = mask & (t >= t[first_contact]) & (t <= t[first_contact] + 0.1 + tolerance)
            landing = {
                "cycle": number, "first_contact_time_s": float(t[first_contact]),
                "normal_force_at_first_contact_n": float(data["contact_normal_force"][first_contact, selected]),
                "peak_normal_force_first_100ms_n": _extreme(data["contact_normal_force"][impact_window, selected]),
                "peak_normal_force_lower_confirm_reload_n": _extreme(data["contact_normal_force"][landing_mask, selected]),
                "desired_vertical_speed_at_first_contact_m_s": float(data["desired_foot_vel_w"][first_contact, 2]),
                "finite_difference_vertical_speed_at_first_contact_m_s": float((selected_pos[first_contact, 2] - selected_pos[first_contact - 1, 2]) / dt) if first_contact else None,
            }
            landing_events.append(landing)
        cycle_metrics.append({
            "cycle": number, "phase_order": compressed, "phase_durations_s": durations,
            "support_anchor_time_s": float(t[anchor_index]) if anchor_index is not None else None,
            "hold_minimum_clearance_m": _extreme(clearance[hold], False),
            "hold_maximum_clearance_m": _extreme(clearance[hold]),
            "hold_minimum_support_margin_m": _extreme(physical_margin[hold], False),
            "hold_maximum_tracking_error_m": _extreme(tracking[hold]),
            "swing_maximum_tracking_error_m": _extreme(tracking[swing]),
            "maximum_support_foot_displacement_m": _extreme(support_drift[support_window]),
            "maximum_abs_roll_pitch_deg": _extreme(tilt[mask]),
            "landing": landing,
        })

    tail = np.zeros(n, dtype=bool)
    if n and phase[-1] == "complete":
        first_tail = n - 1
        while first_tail > 0 and phase[first_tail - 1] == "complete" and cycle[first_tail - 1] == expected_cycles:
            first_tail -= 1
        tail[first_tail:] = True
    tail_duration = float(np.count_nonzero(tail) * dt)
    check("final_four_foot_stance", tail_duration + dt + tolerance >= LIMITS["minimum_final_stance_s"]
          and np.all(measured[tail]) and np.all(planned[tail]) and np.all(cycle[tail] == expected_cycles),
          "Final complete phase lasts >= 1 s with all four feet in measured and planned contact", tail_duration)
    check("final_four_foot_loading", np.any(tail)
          and tail_duration + dt + tolerance >= LIMITS["minimum_final_stance_s"]
          and np.all(measured[tail]) and np.all(planned[tail])
          and np.all(data["contact_normal_force"][tail] > LIMITS["minimum_restored_foot_normal_force_n"]),
          "Every foot remains loaded above 5 N throughout the final complete phase (at least 1 s), with measured and planned contact",
          {"duration_s": tail_duration,
           "minimum_normal_force_n_by_leg": {
               leg: _extreme(data["contact_normal_force"][tail, index], False) for index, leg in enumerate(legs)}})
    summary = _safe({
        "passed": all(check["passed"] for check in checks.values()), "experiment": metadata.get("experiment"),
        "selected_leg": metadata["selected_leg"], "requested_cycles": expected_cycles,
        "actual_completed_cycles": metadata.get("actual_completed_cycles"), "limits": LIMITS,
        "criteria_basis": "Predeclared engineering limits for this controlled flat-ground simulation; not a stability proof.",
        "conventions": {
            "phase_duration": "Sample count × dt; row labels describe the preceding control interval.",
            "clearance": "Selected foot geometry-center height above recorded fixed pre-lift center; not absolute floor distance.",
            "support_margin": "Independently recomputed from physical CoM and the other three measured foot centers in world XY.",
            "support_displacement": "Foot geometry-center displacement from fixed per-cycle shift anchors includes rolling and contact compliance; it is not a measurement of pure tangential slip.",
            "landing_debounce": "Pre-reload sampled selected-foot contacts must remain active with normal force >= 2 N; one boundary sample is allowed for control-start versus observation-end alignment.",
            "restored_loading": "Each foot must exceed 5 N over the last 0.2 s of reload plus the first recenter sample, and throughout final standing; contact flags alone do not establish loading.",
            "mpc_cadence": "Periodic interval is round(1/(configured frequency × physics dt)), matching the controller. Initialization and support changes force solves; a support-change solve does not reset the periodic grid.",
            "force_cap": "Bounds the MPC desired vertical force at MPC updates, not the measured contact reaction.",
            "force_ramp_duration": "The 3 s minimum for unload/reload is a declared check of this milestone's fixed controller schedule, not a universal dynamics requirement.",
            "landing_impact": "Peak simulated normal contact reaction in first 100 ms after contact; not a hardware impact measurement.",
            "nlp_status": "Status 2 denotes the configured SQP iteration limit; underlying QP status must remain zero.",
        },
        "criteria": checks, "cycles": cycle_metrics, "landing_events": landing_events,
        "metrics": {"sample_count": n, "duration_s": float(t[-1]) if n else 0.0,
                    "mpc_updates": int(np.count_nonzero(updates)), "maximum_abs_roll_pitch_deg": _extreme(tilt),
                    "maximum_abs_actuator_torque_nm": _extreme(np.abs(data["actuator_torque"])),
                    "maximum_normal_force_n_by_leg": {leg: _extreme(data["contact_normal_force"][:, index]) for index, leg in enumerate(legs)},
                    "final_complete_duration_s": tail_duration,
                    "maximum_logged_vs_independent_margin_difference_m": _extreme(np.abs(data["support_margin_m"] - physical_margin))},
        "runner_status": metadata.get("status"), "runner_error": metadata.get("error"),
    })
    (run_dir / "step_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _report(run_dir, metadata, summary)
    _plot(run_dir, metadata, data, summary, physical_margin, support_drift)
    return summary


def _report(run_dir, metadata, summary):
    result = "PASS" if summary["passed"] else "FAIL"
    lines = [f"# Controlled {summary['selected_leg']} foot step — {result}", "",
             f"Completed {summary['actual_completed_cycles']} of {summary['requested_cycles']} requested cycles. "
             f"Each commanded lift is {metadata['lift_height_m'] * 1000:g} mm with a {metadata['hold_seconds']:g} s hold. "
             f"Recorded {summary['metrics']['duration_s']:.3f} s at {metadata['dt_s']:g} s per interval.", "",
             summary["criteria_basis"], "", "| Check | Result | Requirement | Observed |", "|---|---|---|---|"]
    for name, item in summary["criteria"].items():
        observed = json.dumps(item["observed"], ensure_ascii=False)
        lines.append(f"| {name} | {'PASS' if item['passed'] else 'FAIL'} | {item['requirement']} | {observed} |")
    lines += ["", "| Cycle | Hold (s) | Min clearance (mm) | Min support margin (mm) | Max hold error (mm) | Max support drift (mm) |", "|---|---:|---:|---:|---:|---:|"]
    for cycle in summary["cycles"]:
        def mm(key):
            return "unavailable" if cycle[key] is None else f"{cycle[key] * 1000:.3f}"
        lines.append(f"| {cycle['cycle']} | {cycle['phase_durations_s']['hold']:.3f} | {mm('hold_minimum_clearance_m')} | {mm('hold_minimum_support_margin_m')} | {mm('hold_maximum_tracking_error_m')} | {mm('maximum_support_foot_displacement_m')} |")
    lines += ["", "Phase durations and landing-force peaks for every cycle are in `step_summary.json`. "
              "Fixed anchors and the physical CoM support triangle provide evidence independent of the requested foot trajectory.", ""]
    lines.extend(f"- **{name.replace('_', ' ')}:** {description}" for name, description in summary["conventions"].items())
    if "contact_debounce_s" not in metadata:
        lines += ["", "Metadata does not specify a minimum debounce duration. The report checks positive recorded dwell; "
                  "it cannot validate a particular debounce threshold."]
    lines += ["", "![Controlled step overview](step_overview.png)", "", "Raw observations: `signals.npz`. Configuration/provenance: `metadata.json`."]
    if summary["runner_error"]:
        lines += ["", f"Runner error: `{str(summary['runner_error']).replace('`', '')}`."]
    (run_dir / "step_report.md").write_text("\n".join(lines) + "\n")


def _plot(run_dir, metadata, data, summary, margin, support_drift):
    t = data["time_s"]
    fig, axes = plt.subplots(4, 2, figsize=(16, 14), constrained_layout=True)
    axes = axes.ravel()
    fig.suptitle(f"Controlled {metadata['selected_leg']} flat-ground step — {'PASS' if summary['passed'] else 'FAIL'}", fontsize=16)
    if not len(t):
        for ax in axes:
            ax.set_axis_off()
        axes[0].text(0, 0.5, "No recorded samples")
    else:
        selected = list(metadata["legs"]).index(metadata["selected_leg"])
        support_names = [leg for leg in metadata["legs"] if leg != metadata["selected_leg"]]
        actual = data["feet_pos_w"][:, selected]
        desired = data["feet_desired_w"][:, selected]
        anchor_z = data["foot_anchor_w"][:, 2]
        axes[0].plot(t, (actual[:, 2] - anchor_z) * 1000, label="Measured")
        axes[0].plot(t, (desired[:, 2] - anchor_z) * 1000, "--", label="Desired")
        axes[0].set(title="Selected foot lift relative to fixed anchor", ylabel="Height (mm)")
        axes[1].plot(t, margin * 1000, label="Physical CoM / measured feet")
        axes[1].axhline(10, linestyle=":", color="#777777", label="Hold minimum")
        axes[1].set(title="Three-foot support margin", ylabel="Inside-positive margin (mm)")
        for index, name in enumerate(("roll", "pitch")):
            axes[2].plot(t, np.rad2deg(data["base_rpy_rad"][:, index]), label=name)
        axes[2].set(title="Body orientation", ylabel="Angle (deg)")
        axes[3].plot(t, data["contact_normal_force"][:, selected], label="Measured normal force")
        axes[3].plot(t, data["grf_desired_w"][:, selected, 2], "--", label="MPC desired Fz")
        axes[3].plot(t, data["selected_force_cap_N"], ":", label="Desired-force cap")
        axes[3].set(title="Selected foot unloading and landing", ylabel="Force (N)")
        for index, name in enumerate(support_names):
            axes[4].plot(t, support_drift[:, index] * 1000, label=name)
        axes[4].set(title="Support feet displacement from cycle shift anchor", ylabel="3D displacement (mm)")
        axes[5].plot(t, np.linalg.norm(actual - desired, axis=1) * 1000, label="Selected foot")
        axes[5].set(title="Selected foot Cartesian tracking error", ylabel="3D error (mm)")
        rows = np.stack([data[key][:, index] for index in range(4) for key in ("contact_measured", "contact_planned")])
        axes[6].imshow(rows, aspect="auto", interpolation="nearest", extent=(0, t[-1], 7.5, -0.5),
                       cmap=ListedColormap(["#eeeeee", "#187969"]), vmin=0, vmax=1)
        axes[6].set(title="Contact: green=on, light=off", yticks=np.arange(8),
                    yticklabels=[f"{leg} {kind}" for leg in metadata["legs"] for kind in ("measured", "planned")])
        phase_values = np.array([PHASES.index(str(phase)) if str(phase) in PHASES else -1 for phase in data["phase"]])
        axes[7].step(t, phase_values, where="post", label="Recorded control phase")
        axes[7].set(title="Sequencer progress", yticks=np.arange(len(PHASES)), yticklabels=PHASES)
        for number in range(1, int(metadata["cycles"]) + 1):
            hold_times = t[(data["cycle"] == number) & (data["phase"] == "hold")]
            if len(hold_times):
                for ax in axes:
                    ax.axvspan(hold_times[0] - metadata["dt_s"], hold_times[-1], color="#187969", alpha=0.07)
        for index, ax in enumerate(axes):
            ax.set(xlabel="Experiment time (s)", xlim=(0, max(float(t[-1]), metadata["dt_s"])))
            ax.tick_params(labelsize=8)
            if index != 6:
                ax.legend(fontsize=8, loc="best")
                ax.grid(alpha=0.2)
    fig.savefig(run_dir / "step_overview.png", dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project analyze-step", description=__doc__)
    parser.add_argument("run_dir", type=Path)
    arguments = parser.parse_args(argv)
    result = analyze_step(arguments.run_dir)
    from primp_project.recording.catalog import refresh_catalog
    refresh_catalog()
    print(json.dumps({"passed": result["passed"], "report": str(arguments.run_dir / "step_report.md")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
