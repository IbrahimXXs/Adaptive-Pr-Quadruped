"""Falsification checks for recorded step evidence; no controller imports."""

import json
from pathlib import Path
import tempfile

import numpy as np
import pytest

from primp_project import ARTIFACTS_ROOT
import primp_project.analysis.step as analysis


@pytest.fixture
def recording():
    dt = 0.01
    durations = [1.0, 1.0, 3.0, 0.5, 6.0, 1.0, 0.2, 3.0, 1.0, 1.0]
    phase = np.concatenate([np.repeat(name, round(duration / dt)) for name, duration in zip(analysis.PHASES, durations)])
    n = len(phase)
    t = np.arange(1, n + 1) * dt
    anchors = np.array([[0.2, 0.15, 0.022], [0.2, -0.15, 0.022], [-0.2, 0.15, 0.022], [-0.2, -0.15, 0.022]])
    feet = np.broadcast_to(anchors, (n, 4, 3)).copy()
    lift, hold, lower = phase == "lift", phase == "hold", phase == "lower"
    feet[lift, 0, 2] += np.linspace(0.0, 0.03, lift.sum())
    feet[hold, 0, 2] += 0.03
    feet[lower, 0, 2] += np.linspace(0.03, 0.0, lower.sum())
    measured = np.ones((n, 4), dtype=bool)
    measured[np.isin(phase, ["lift", "hold", "lower"]), 0] = False
    planned = np.ones((n, 4), dtype=bool)
    planned[np.isin(phase, ["lift", "hold", "lower", "confirm"]), 0] = False
    com = np.broadcast_to(np.r_[anchors[1:, :2].mean(axis=0), 0.28], (n, 3)).copy()
    contact_force = np.zeros((n, 4, 3))
    contact_force[:, :, 2] = measured * 37.0
    contact_force[phase == "unload", 0, 2] = 0.5
    grf = contact_force.copy()
    grf[~planned] = 0.0
    force_cap = np.where(planned[:, 0], 50.0, 0.0)
    force_cap[phase == "unload"] = np.linspace(50.0, 0.0, np.count_nonzero(phase == "unload"))
    force_cap[phase == "reload"] = np.linspace(0.0, 50.0, np.count_nonzero(phase == "reload"))
    grf[:, 0, 2] = np.minimum(grf[:, 0, 2], force_cap)
    dwell = np.zeros(n)
    confirm = phase == "confirm"
    dwell[confirm] = np.arange(1, confirm.sum() + 1) * dt
    dwell[np.isin(phase, ["reload", "recenter", "complete"])] = 0.2
    metadata = {
        "experiment": "controlled_step", "robot": "go2", "controller": "nominal",
        "selected_leg": "FL", "legs": ["FL", "FR", "RL", "RR"], "cycles": 1,
        "hold_seconds": 6.0, "lift_height_m": 0.03, "contact_debounce_s": 0.1,
        "actual_completed_cycles": 1, "status": "completed", "dt_s": dt,
    }
    signals = {
        "time_s": t, "mujoco_time_s": t + dt, "control_time_s": t - dt,
        "phase": phase, "cycle": np.ones(n, dtype=int), "base_rpy_rad": np.zeros((n, 3)),
        "com_pos_w": com, "feet_pos_w": feet, "feet_desired_w": feet.copy(),
        "foot_anchor_w": np.broadcast_to(anchors[0], (n, 3)).copy(),
        "contact_measured": measured, "contact_planned": planned,
        "contact_normal_force": contact_force[:, :, 2].copy(), "contact_force_w": contact_force,
        "grf_desired_w": grf, "support_margin_m": analysis._triangle_margin(com, feet[:, 1:]),
        "selected_force_cap_N": force_cap,
        "contact_confirmed": dwell >= 0.1, "landing_contact_dwell_s": dwell,
        "desired_foot_vel_w": np.zeros((n, 3)), "desired_foot_acc_w": np.zeros((n, 3)),
        "mpc_update": np.ones(n, dtype=bool), "mpc_status": np.full(n, 2), "qp_status": np.zeros(n, dtype=int),
        "terminated": np.zeros(n, dtype=bool), "truncated": np.zeros(n, dtype=bool),
        "numerical_warning_count": np.zeros(n, dtype=int), "torque_saturated": np.zeros((n, 12), dtype=bool),
        "actuator_torque": np.zeros((n, 12)),
    }
    debug = ARTIFACTS_ROOT / "test_tmp"
    debug.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="step-analysis-regression-", dir=debug) as directory:
        yield Path(directory), metadata, signals


def analyze_recording(recording):
    directory, metadata, signals = recording
    (directory / "metadata.json").write_text(json.dumps(metadata))
    np.savez_compressed(directory / "signals.npz", **signals)
    return analysis.analyze_step(directory)


def test_valid_evidence_produces_report_and_landing_metrics(recording):
    result = analyze_recording(recording)
    assert result["passed"], {name: value for name, value in result["criteria"].items() if not value["passed"]}
    assert result["cycles"][0]["phase_durations_s"]["hold"] == 6.0
    assert len(result["landing_events"]) == 1
    for name in ("step_summary.json", "step_report.md", "step_overview.png"):
        assert (recording[0] / name).stat().st_size > 0
    assert (recording[0] / "source" / "analysis" / "step.py").read_bytes() == Path(analysis.__file__).read_bytes()


@pytest.mark.parametrize("corruption, rejected", [
    ("short_hold", "cycle_1_hold_duration"),
    ("selected_foot_contact", "cycle_1_hold_contact"),
    ("missing_support_contact", "cycle_1_hold_contact"),
    ("planned_support_during_lower", "cycle_1_swing_schedule"),
    ("support_contact_during_unload", "cycle_1_support_contact_continuity"),
    ("outside_triangle", "cycle_1_support_margin"),
    ("changing_anchor", "cycle_1_fixed_lift_reference"),
    ("unconfirmed_reload", "cycle_1_reload_gate"),
    ("too_short_debounce", "cycle_1_reload_gate"),
    ("broken_contact_debounce", "cycle_1_reload_gate"),
    ("low_force_debounce", "cycle_1_reload_gate"),
    ("force_cap_exceeded", "selected_force_cap"),
    ("loaded_lift_entry", "cycle_1_lift_entry_guard"),
    ("reversed_unload_ramp", "cycle_1_force_cap_ramps"),
    ("saturation", "no_torque_saturation"),
    ("phase_order", "cycle_1_phase_order"),
    ("incomplete_final_stance", "final_four_foot_stance"),
])
def test_corrupted_evidence_rejects_success(recording, monkeypatch, corruption, rejected):
    # Image rendering is exercised by the successful case; these target evidence checks.
    monkeypatch.setattr(analysis, "_plot", lambda *args: None)
    _, metadata, signals = recording
    hold = int(np.flatnonzero(signals["phase"] == "hold")[0])
    reload = int(np.flatnonzero(signals["phase"] == "reload")[0])
    if corruption == "short_hold":
        metadata["hold_seconds"] = 7.0
    elif corruption == "selected_foot_contact":
        signals["contact_measured"][hold, 0] = True
    elif corruption == "missing_support_contact":
        signals["contact_measured"][hold, 1] = False
    elif corruption == "planned_support_during_lower":
        signals["contact_planned"][np.flatnonzero(signals["phase"] == "lower")[0], 0] = True
    elif corruption == "support_contact_during_unload":
        signals["contact_measured"][np.flatnonzero(signals["phase"] == "unload")[0], 1] = False
    elif corruption == "outside_triangle":
        # Leave the recorded margin positive: independent geometry must catch this.
        signals["com_pos_w"][hold, :2] = signals["feet_pos_w"][hold, 0, :2]
    elif corruption == "changing_anchor":
        signals["foot_anchor_w"][hold, 0] += 0.001
    elif corruption == "unconfirmed_reload":
        signals["contact_confirmed"][reload] = False
    elif corruption == "too_short_debounce":
        signals["landing_contact_dwell_s"][reload] = 0.02
    elif corruption == "broken_contact_debounce":
        signals["contact_measured"][reload - 5, 0] = False
    elif corruption == "low_force_debounce":
        signals["contact_normal_force"][reload - 5, 0] = 1.5
    elif corruption == "force_cap_exceeded":
        signals["grf_desired_w"][hold, 0, 2] = signals["selected_force_cap_N"][hold] + 2.0
    elif corruption == "loaded_lift_entry":
        signals["contact_normal_force"][np.flatnonzero(signals["phase"] == "unload")[-1], 0] = 4.0
    elif corruption == "reversed_unload_ramp":
        signals["selected_force_cap_N"][np.flatnonzero(signals["phase"] == "unload")[10]] += 2.0
    elif corruption == "saturation":
        signals["torque_saturated"][hold, 0] = True
    elif corruption == "phase_order":
        signals["phase"][signals["phase"] == "shift"] = "unload"
    elif corruption == "incomplete_final_stance":
        for key in signals:
            signals[key] = signals[key][:-50].copy()
    result = analyze_recording(recording)
    assert not result["passed"]
    assert not result["criteria"][rejected]["passed"]
