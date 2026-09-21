"""Falsify pad-specific acceptance without executing a controller."""

import json

import numpy as np
import pytest

import primp_project.analysis.pad as analysis
import primp_project.analysis.step as step_analysis
from primp_project.tests.test_step_analysis import recording


@pytest.fixture
def pad_recording(recording):
    directory, metadata, signals = recording
    # The original step fixture lowers 30 mm in one second. Extend only its
    # lowering segment so this pad fixture obeys the independently checked
    # 15 mm/s nominal and 5 mm/s near-surface command limits.
    original_lower = np.flatnonzero(signals["phase"] == "lower")
    indexes = np.r_[np.arange(original_lower[0]), np.repeat(original_lower, 3),
                    np.arange(original_lower[-1]+1, len(signals["phase"]))]
    for key in signals:
        signals[key] = signals[key][indexes].copy()
    n = len(signals["time_s"])
    phase = signals["phase"]
    lower = np.flatnonzero(phase == "lower")
    dt = metadata["dt_s"]
    signals["step"] = np.arange(1, n+1)
    signals["time_s"] = signals["step"]*dt
    signals["control_time_s"] = signals["time_s"]-dt
    signals["mujoco_time_s"] = signals["time_s"]+dt
    bottom = np.r_[np.linspace(.03, .001, 250), np.linspace(.001, 0., 50)]
    signals["feet_pos_w"][lower, 0, 2] = .022+bottom
    signals["feet_desired_w"][lower, 0, 2] = .022+bottom
    transition = np.r_[False, np.any(np.diff(signals["contact_planned"].astype(int), axis=0), axis=1)]
    signals["mpc_update"] = ((signals["step"]-1) % 5 == 0) | transition
    on_pad = np.isin(phase, ["confirm", "reload", "recenter", "complete"])
    target_xy = signals["foot_anchor_w"][0, :2].copy()
    # Reuse the independently validated step fixture. The separate simulator
    # geometry is verified in test_landing_pad; target-specific contacts here
    # represent the evaluator's distinct geom-ID measurement.
    metadata.update(
        experiment="landing_pad", role="evaluation", planner="reactive",
        initial_height_estimate_m=0., landing_target_xy_m=target_xy.tolist(),
        foot_radius_m=.022, nominal_lower_duration_s=3., max_search_depth_m=.02,
        contact_compression_m=.004,
        planner_frequency_hz=20.,
        evaluation={"actual_pad_height_m": 0., "support_top_heights_m": [0.] * 4},
    )
    signals.update(
        belief_mean_m=np.zeros(n), belief_std_m=np.full(n, .002),
        belief_lower_m=np.full(n, -.01), belief_upper_m=np.full(n, .01),
        missing_contact=np.zeros(n, dtype=bool),
        sensor_contact=signals["contact_measured"].copy(),
        sensor_normal_force=signals["contact_normal_force"].copy(),
        sensor_foot_pos_w=signals["feet_pos_w"][:, 0].copy(),
        sensor_measurement_time_s=signals["control_time_s"].copy(),
        planner_update=np.zeros(n, dtype=bool), planner_remaining_time_s=np.zeros(n),
        planner_com_target_w=signals["com_pos_w"].copy(),
        planner_foot_target_w=signals["feet_desired_w"][:, 0].copy(),
        planner_body_rpy=np.zeros((n, 3)), planner_compute_time_s=np.zeros(n),
        reference_projection_count=np.zeros(n, dtype=int), planner_fallback_count=np.zeros(n, dtype=int),
        target_pad_contact=on_pad,
        target_pad_normal_force=np.where(on_pad, signals["contact_normal_force"][:, 0], 0.),
        foot_bottom_z_w=signals["feet_pos_w"][:, 0, 2]-.022,
    )
    signals["planner_compute_time_s"][lower] = .0005
    signals["planner_update"][lower[::5]] = True
    return directory, metadata, signals


def evaluate(recording):
    directory, metadata, signals = recording
    (directory / "metadata.json").write_text(json.dumps(metadata))
    np.savez_compressed(directory / "signals.npz", **signals)
    return analysis.analyze_pad(directory)


def test_valid_pad_evidence_retains_base_checks_and_reports_metrics(pad_recording):
    result = evaluate(pad_recording)
    assert result["passed"], {key: item for key, item in result["criteria"].items() if not item["passed"]}
    for key in ("mpc_update_cadence", "cycle_1_reload_loading", "final_four_foot_loading",
                "pad_final_target_loading", "pad_target_reload_loading", "pad_target_contact_before_reload"):
        assert result["criteria"][key]["passed"]
    assert result["metrics"]["peak_normal_force_first_100ms_n"] == 37.
    assert result["metrics"]["normal_impulse_first_100ms_ns"] == pytest.approx(3.7)
    assert result["metrics"]["planner_mean_compute_time_s"] == pytest.approx(.0005)
    assert result["metrics"]["observed_contact_timing"] == "approximately_planned"
    assert result["metrics"]["height_belief_final_error_m"] == 0.
    for name in ("pad_summary.json", "pad_report.md", "pad_overview.png", "step_summary.json"):
        assert (pad_recording[0] / name).stat().st_size > 0


def test_skew_belief_mean_need_not_lie_inside_central_credible_interval(pad_recording, monkeypatch):
    monkeypatch.setattr(analysis, '_plot', lambda *args: None)
    monkeypatch.setattr(step_analysis, '_plot', lambda *args: None)
    _, _, signals = pad_recording
    # 96% at zero and 4% at +10 mm: mean +0.4 mm, both central
    # discrete 5/95% quantiles zero. This is a valid bounded posterior.
    signals['belief_mean_m'][:] = .0004
    signals['belief_lower_m'][:] = signals['belief_upper_m'][:] = 0.
    signals['belief_std_m'][:] = np.sqrt(.96*.0004**2+.04*.0096**2)
    assert evaluate(pad_recording)['criteria']['pad_belief_bounds']['passed']


def test_belief_mean_outside_declared_terrain_support_is_rejected(pad_recording, monkeypatch):
    monkeypatch.setattr(analysis, '_plot', lambda *args: None)
    monkeypatch.setattr(step_analysis, '_plot', lambda *args: None)
    pad_recording[2]['belief_mean_m'][10] = .021
    assert not evaluate(pad_recording)['criteria']['pad_belief_bounds']['passed']


@pytest.mark.parametrize("corruption, criterion", [
    ("wrong_pad_final", "pad_final_target_loading"),
    ("wrong_pad_debounce", "pad_target_contact_before_reload"),
    ("wrong_pad_reload", "pad_target_reload_loading"),
    ("unbounded_search", "pad_bounded_descent"),
    ("false_bottom", "pad_foot_bottom_consistency"),
    ("excess_target_force", "pad_target_force_consistency"),
    ("moving_support", "pad_fixed_support_surfaces"),
    ("future_sensor", "pad_sensor_causality"),
    ("negative_planner_time", "pad_planner_execution"),
    ("invalid_belief", "pad_belief_bounds"),
    ("truth_leak", "pad_truth_separation_schema"),
    ("evaluation_known_height", "pad_truth_separation_schema"),
    ("missing_mpc_update", "mpc_update_cadence"),
    ("missing_final_loading", "final_four_foot_loading"),
])
def test_corrupted_pad_evidence_rejected(pad_recording, monkeypatch, corruption, criterion):
    monkeypatch.setattr(analysis, "_plot", lambda *args: None)
    monkeypatch.setattr(step_analysis, "_plot", lambda *args: None)
    _, metadata, signals = pad_recording
    final = np.flatnonzero(signals["phase"] == "complete")
    reload = np.flatnonzero(signals["phase"] == "reload")
    lower = np.flatnonzero(signals["phase"] == "lower")
    if corruption == "wrong_pad_final":
        signals["target_pad_contact"][final[1]] = False
        signals["target_pad_normal_force"][final[1]] = 0
    elif corruption == "wrong_pad_debounce":
        signals["target_pad_contact"][reload[0]-3] = False
        signals["target_pad_normal_force"][reload[0]-3] = 0
    elif corruption == "wrong_pad_reload":
        signals["target_pad_normal_force"][reload[-3]] = 4
    elif corruption == "unbounded_search":
        signals["feet_desired_w"][lower[-1], 0, 2] = -.02
    elif corruption == "false_bottom":
        signals["foot_bottom_z_w"][lower[0]] += .001
    elif corruption == "excess_target_force":
        signals["target_pad_normal_force"][final[0]] = 100
    elif corruption == "moving_support":
        metadata["evaluation"]["support_top_heights_m"][2] = .001
    elif corruption == "future_sensor":
        signals["sensor_measurement_time_s"][lower[0]] += .002
    elif corruption == "negative_planner_time":
        signals["planner_compute_time_s"][lower[0]] = -.001
    elif corruption == "invalid_belief":
        signals["belief_lower_m"][lower[0]] = .02
    elif corruption == "truth_leak":
        metadata["planner_context"] = {"actual_pad_height_m": 0.}
    elif corruption == "evaluation_known_height":
        metadata["known_height_m"] = 0.
    elif corruption == "missing_mpc_update":
        signals["mpc_update"][10] = False
    elif corruption == "missing_final_loading":
        signals["contact_normal_force"][final[1], 2] = 4.
    result = evaluate(pad_recording)
    assert not result["passed"]
    assert not result["criteria"][criterion]["passed"]


def test_lower_height_and_missing_contact_are_evaluation_metrics(pad_recording, monkeypatch):
    monkeypatch.setattr(analysis, "_plot", lambda *args: None)
    monkeypatch.setattr(step_analysis, "_plot", lambda *args: None)
    _, metadata, signals = pad_recording
    metadata["evaluation"]["actual_pad_height_m"] = -.01
    lower = np.flatnonzero(signals["phase"] == "lower")
    signals["missing_contact"][lower[-20]:] = True
    signals["belief_mean_m"][lower[-10]:] = -.01
    result = evaluate(pad_recording)
    assert result["evaluation"]["height_condition"] == "lower"
    assert result["metrics"]["missing_contact_observed"]
    assert result["metrics"]["missing_contact_before_physical_touchdown"]
    assert result["metrics"]["recovery_to_touchdown_s"] > 0
    assert result["metrics"]["height_belief_final_error_m"] == 0.


def test_known_height_is_allowed_only_for_demonstrations(pad_recording, monkeypatch):
    monkeypatch.setattr(analysis, "_plot", lambda *args: None)
    monkeypatch.setattr(step_analysis, "_plot", lambda *args: None)
    _, metadata, _ = pad_recording
    metadata.update(role="demonstration", known_height_m=0.)
    assert evaluate(pad_recording)["criteria"]["pad_truth_separation_schema"]["passed"]


def test_fallback_is_reported_without_relabeling_successful_safe_execution(pad_recording, monkeypatch):
    monkeypatch.setattr(analysis, "_plot", lambda *args: None)
    monkeypatch.setattr(step_analysis, "_plot", lambda *args: None)
    pad_recording[2]["planner_fallback_count"][-1] = 1
    result = evaluate(pad_recording)
    assert result["passed"]
    assert result["metrics"]["planner_fallback_count"] == 1


@pytest.mark.parametrize("corruption, criterion", [
    ("foot_speed", "pad_commanded_foot_speed"),
    ("com_speed", "pad_commanded_com_speed"),
    ("upward_motion", "pad_monotone_lowering"),
    ("body_displacement", "pad_commanded_body_displacement"),
    ("target_xy", "pad_commanded_target_xy"),
    ("orientation_displacement", "pad_commanded_orientation"),
    ("orientation_rate", "pad_commanded_orientation"),
    ("recovery_speed", "pad_commanded_recovery_speed"),
    ("motion_during_freeze", "pad_contact_reference_freeze"),
    ("missing_update", "pad_planner_update_cadence"),
    ("extra_update", "pad_planner_update_cadence"),
    ("update_during_freeze", "pad_planner_update_cadence"),
    ("wrong_frequency", "pad_planner_update_cadence"),
    ("loosened_limit", "pad_reference_limit_configuration"),
    ("nonfinite_reference", "pad_finite_planner_signals"),
])
def test_applied_reference_corruptions_rejected_independently_of_claimed_velocities(pad_recording, corruption, criterion):
    _, metadata, signals = pad_recording
    lower = np.flatnonzero(signals["phase"] == "lower")
    confirm = np.flatnonzero(signals["phase"] == "confirm")
    i = lower[100]
    if corruption == "foot_speed":
        signals["feet_desired_w"][i, 0, 2] -= .0004
    elif corruption == "com_speed":
        signals["planner_com_target_w"][i, 0] += .0002
    elif corruption == "upward_motion":
        signals["feet_desired_w"][i, 0, 2] = signals["feet_desired_w"][i-1, 0, 2]+.00001
    elif corruption == "body_displacement":
        signals["planner_com_target_w"][lower, 0] += np.linspace(0., .013, len(lower))
    elif corruption == "target_xy":
        signals["feet_desired_w"][lower, 0, 0] += .006
    elif corruption == "orientation_displacement":
        signals["planner_body_rpy"][lower, 0] = np.linspace(0., .04, len(lower))
    elif corruption == "orientation_rate":
        signals["planner_body_rpy"][i, 0] = .001
    elif corruption == "recovery_speed":
        # 6 mm/s remains legal nominally, but violates the slow-search bound.
        i = lower[-15]
        signals["feet_desired_w"][i+1, 0, 2] = signals["feet_desired_w"][i, 0, 2]-.00006
    elif corruption == "motion_during_freeze":
        signals["feet_desired_w"][confirm[5], 0, 2] -= .00001
    elif corruption == "missing_update":
        signals["planner_update"][lower[20]] = False
    elif corruption == "extra_update":
        signals["planner_update"][lower[21]] = True
    elif corruption == "update_during_freeze":
        signals["planner_update"][confirm[1]] = True
    elif corruption == "wrong_frequency":
        metadata["planner_frequency_hz"] = 10.
    elif corruption == "loosened_limit":
        metadata["reference_limits"] = {"max_foot_speed_m_s": .03}
    elif corruption == "nonfinite_reference":
        signals["planner_body_rpy"][i, 0] = np.nan
    checks = analysis.reference_checks(metadata, signals)
    assert not checks[criterion]["passed"], checks


def test_planner_resumes_immediately_after_interrupted_contact_then_restarts_cadence(pad_recording):
    _, metadata, signals = pad_recording
    lower = np.flatnonzero(signals["phase"] == "lower")
    first, end = lower[11], lower[18]
    signals["sensor_contact"][first:end, 0] = True
    signals["sensor_normal_force"][first:end, 0] = 2.
    signals["planner_update"][first:lower[-1]+1] = False
    signals["planner_update"][end:lower[-1]+1:5] = True
    assert analysis.reference_checks(metadata, signals)["pad_planner_update_cadence"]["passed"]
    signals["planner_update"][end] = False
    assert not analysis.reference_checks(metadata, signals)["pad_planner_update_cadence"]["passed"]


def test_recovery_limit_uses_the_observation_that_planned_each_segment(pad_recording):
    _, metadata, signals = pad_recording
    lower = np.flatnonzero(signals["phase"] == "lower")
    first = lower[100]
    # A missing-contact observation arrives one control tick after a plan.
    # The already running 10 mm/s segment may complete until the next update.
    signals["sensor_foot_pos_w"][first+1:first+10, 2] = .022
    signals["feet_desired_w"][first:first+6, 0, 2] = .04-np.arange(6)*.0001
    signals["feet_desired_w"][first+6:first+11, 0, 2] = .0395-np.arange(1, 6)*.00004
    check = analysis.reference_checks(metadata, signals)["pad_commanded_recovery_speed"]
    assert check["passed"], check
    signals["feet_desired_w"][first+6, 0, 2] = signals["feet_desired_w"][first+5, 0, 2]-.00006
    assert not analysis.reference_checks(metadata, signals)["pad_commanded_recovery_speed"]["passed"]
