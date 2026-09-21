"""V2 provenance, paired accounting, and scheduling tests without native simulation."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import numpy as np
import pytest

from primp_project.analysis import comparison_v2
from primp_project.experiments import pad_study, pad_study_v2 as study


def write_record(kwargs, directory, *, passed=True):
    directory.mkdir(parents=True)
    matched = kwargs["planner"].startswith("matched_")
    metadata = dict(
        experiment="landing_pad", role=kwargs["role"], planner=kwargs["planner"], seed=kwargs["seed"],
        sensor_profile={"name": kwargs["sensor_profile"]}, initial_height_estimate_m=kwargs["initial_estimate_m"],
        nominal_lower_duration_s=kwargs["lower_duration_s"], evaluation={"actual_pad_height_m": kwargs["actual_height_m"]},
        status="completed" if passed else "failed", dt_s=.002, robot="go2", controller="nominal",
        foot_radius_m=.022, validation_version=2 if matched else 1,
        initial_condition=kwargs.get("initial_condition", "nominal"),
        recovery_demonstration=kwargs.get("recovery_demonstration", False),
        requested_lift_height_m=.035 if kwargs.get("initial_condition") == "raised" else .03)
    if kwargs["role"] == "demonstration":
        metadata["known_height_m"] = kwargs["actual_height_m"]
    for key, field, filenames in (("model_path", "model_hashes_sha256", study.MODEL_FILES["model"]),
                                  ("recovery_model_path", "recovery_model_hashes_sha256", study.MODEL_FILES["recovery_model"])):
        if kwargs.get(key):
            metadata[field] = {name: study._sha(Path(kwargs[key])/name) for name in filenames}
    (directory/"metadata.json").write_text(json.dumps(metadata))
    # Variable intervals show why fallback count / update frequency is insufficient.
    t = np.array([0., .05, .10, .13, .18, .23, .28])
    phases = np.array(["hold", "lower", "lower", "lower", "confirm", "reload", "complete"])
    n = len(t)
    raised = .005 if kwargs.get("initial_condition") == "raised" else 0.
    feet = np.zeros((n, 4, 3)); feet[:, 0, 2] = .052+raised
    feet[:, 0, 2] -= np.linspace(0., .030, n)
    com = np.tile([0., 0., .30], (n, 1))
    com[:, 0] = np.arange(n)*.0002
    contact = np.ones((n, 4), bool); contact[1:4, 0] = False
    normal = np.full((n, 4), 40.); normal[1:4, 0] = 0.
    foot = feet[:, 0].copy(); foot[:, 2] = [.05, .04, .03, .028, .027, .027, .027]
    remaining = np.array([0., .18, .13, .10, 0., 0., 0.])
    model_remaining = remaining if kwargs["planner"] != "matched_predictive" else np.zeros(n)
    np.savez(directory/"signals.npz", control_time_s=t, phase=phases, sensor_contact=contact,
             sensor_normal_force=normal, planner_update=np.ones(n, bool),
             planner_fallback_active=np.array([False, False, True, False, False, False, False]),
             planner_fallback_count=np.arange(n)*100, planner_foot_target_w=foot, planner_com_target_w=com,
             planner_remaining_time_s=remaining, model_remaining_time_s=model_remaining,
             raw_model_remaining_time_s=remaining,
             planner_model_prior_active=(np.array([False, True, False, True, False, False, False])
                                         if kwargs["planner"] != "matched_predictive" else np.zeros(n, bool)),
             planner_recovery_active=np.array([False, False, True, True, False, False, False]),
             optimized_remaining_time_s=remaining, feasible_remaining_time_s=remaining,
             missing_contact=np.array([False, False, True, True, False, False, False]),
             feet_pos_w=feet, com_pos_w=com, sensor_foot_pos_w=feet[:, 0], sensor_com_pos_w=com,
             contact_confirmed=phases == "reload", base_rpy_rad=np.zeros((n, 3)))
    metrics = dict(peak_normal_force_first_100ms_n=5., maximum_roll_pitch_change_during_landing_deg=.1,
                   lowering_to_completion_s=12.+(.2 if kwargs["planner"] == "matched_predictive" else 0.),
                   normal_impulse_first_100ms_ns=.3)
    metrics.update(comparison_v2.raw_adaptation_metrics(directory, metadata))
    summary = dict(passed=passed, criteria={"synthetic_check": {"passed": passed}}, metrics=metrics)
    (directory/"pad_summary.json").write_text(json.dumps(summary))
    (directory/"pad_report.md").write_text("Synthetic fixture; never simulation evidence.\n")
    return directory, summary


@pytest.fixture
def inherited_study(tmp_path):
    directory = tmp_path/"v1"
    manifest, path = pad_study.ensure_manifest(directory)
    state = dict(split_manifest_sha256=study._sha(path), trials={})
    for index, spec in enumerate(manifest["demonstrations"]):
        run, _ = write_record(spec, directory/"recordings"/f"old_{index:02}")
        state["trials"][spec["trial_id"]] = dict(status="completed", passed=True, run_dir=str(run),
            signals_sha256=study._sha(run/"signals.npz"), metadata_sha256=study._sha(run/"metadata.json"),
            summary_sha256=study._sha(run/"pad_summary.json"))
    (directory/"study_state.json").write_text(json.dumps(state))
    return directory


@pytest.fixture
def fake_runner():
    calls, lock = [], threading.Lock()

    def run(**kwargs):
        with lock:
            calls.append(kwargs)
            index = len(calls)
        one_condition = (kwargs["role"] == "evaluation" and kwargs["actual_height_m"] < 0
                         and kwargs["seed"] == 17 and kwargs["initial_condition"] == "nominal")
        if one_condition and kwargs["planner"] == "matched_predictive":
            raise RuntimeError("synthetic infrastructure failure")
        passed = not (one_condition and kwargs["planner"] == "matched_no_timing_adaptation")
        return write_record(kwargs, Path(kwargs["output_group"])/f"new_{index:03}", passed=passed)

    run.calls = calls
    return run


@pytest.fixture
def fake_fitter():
    calls = []

    def fit(old, recovery, directory):
        calls.append((old, recovery))
        for folder, filenames in study.MODEL_FILES.items():
            (directory/folder).mkdir(exist_ok=True)
            for filename in filenames:
                (directory/folder/filename).write_text("synthetic model fixture")

    fit.calls = calls
    return fit


@pytest.fixture(autouse=True)
def fast_artifacts(monkeypatch):
    monkeypatch.setattr(study, "source_fingerprint", lambda scope="evaluation": f"source-{scope}")
    monkeypatch.setattr(comparison_v2, "_plot", lambda output, report: (output/"comparison.png").write_bytes(b"fixture"))


@pytest.fixture
def complete(tmp_path, inherited_study, fake_runner, fake_fitter):
    directory = tmp_path/"v2"
    state = study.run_study("all", study_dir=directory, v1_study_dir=inherited_study,
                            trial_runner=fake_runner, model_fitter=fake_fitter)
    return directory, state, fake_runner, fake_fitter


def test_reserved_split_has_exact_paired_cells_and_separate_training(inherited_study, tmp_path):
    before = {str(path): path.read_bytes() for path in inherited_study.rglob("*") if path.is_file()}
    manifest, path = study.ensure_manifest(tmp_path/"v2", v1_study_dir=inherited_study)
    assert len(manifest["demonstrations"]) == 9 and len(manifest["evaluations"]) == 60
    assert {cell["actual_height_m"] for cell in manifest["demonstrations"]} == {-.004, -.008, -.012}
    assert all(cell["initial_estimate_m"] == 0 and cell["recovery_demonstration"] for cell in manifest["demonstrations"])
    assert len({(cell["actual_height_m"], cell["seed"], cell["initial_condition"]) for cell in manifest["evaluations"]}) == 12
    assert {cell["sensor_profile"] for cell in manifest["evaluations"]} == {"noisy_delayed"}
    assert {cell["planner"] for cell in manifest["evaluations"]} == set(study.PLANNERS)
    declared = path.read_bytes()
    study.ensure_manifest(tmp_path/"v2", v1_study_dir=inherited_study)
    assert path.read_bytes() == declared
    assert before == {str(path): path.read_bytes() for path in inherited_study.rglob("*") if path.is_file()}


def test_training_uses_old_plus_new_demos_and_report_preserves_failed_denominator(complete):
    directory, state, runner, fitter = complete
    old, recovery = fitter.calls[0]
    assert len(old) == len(recovery) == 9
    assert set(old).isdisjoint(recovery)
    assert len(state["models"]["motion_training_run_ids"]) == 18
    assert len(state["models"]["recovery_training_run_ids"]) == 9
    assert len(runner.calls) == 69
    report = json.loads((directory/"comparison/comparison.json").read_text())
    assert report["attempted_evaluations"] == 60 and report["successful_evaluations"] == 58
    assert not report["missing_evaluations"] and not report["consistency_errors"]
    assert len(report["pairs"]) == 48
    learned_vs_predictive = report["paired_contrasts"][0]
    assert learned_vs_predictive["both_accepted"] == 11
    assert learned_vs_predictive["method_only_accepted"] == 1
    assert learned_vs_predictive["paired_metric_differences"]["lowering_to_completion_s"]["median"] == pytest.approx(-.2)
    assert all(group["planned"] == group["attempted"] == 12 for group in report["aggregates"])
    assert all(row["positive_remaining_time_fraction"] == 1 for row in report["trials"] if row["passed"])
    matching = [row for row in report["trials"] if row["planner"] == "matched_learned"
                and row["actual_height_m"] == -.006 and row["seed"] == 17]
    initial = {row["initial_condition"]: row for row in matching}
    assert initial["raised"]["actual_lowering_initial_foot_bottom_m"]-initial["nominal"]["actual_lowering_initial_foot_bottom_m"] == pytest.approx(.005)
    for filename in ("comparison.json", "comparison.csv", "comparison.md", "comparison.png", "paired_differences.csv"):
        assert (directory/"comparison"/filename).is_file()


def test_resume_does_not_repeat_failed_or_successful_cells_or_refit(complete):
    directory, _, runner, fitter = complete
    study.run_study("all", study_dir=directory, trial_runner=runner, model_fitter=fitter)
    assert len(runner.calls) == 69 and len(fitter.calls) == 1
    with pytest.raises(ValueError, match="Evaluation has begun"):
        study.run_study("train", study_dir=directory, model_fitter=fitter)


@pytest.mark.parametrize("name", ["signals.npz", "metadata.json", "pad_summary.json"])
def test_changed_trial_is_rejected_on_resume_and_in_report(complete, name):
    directory, state, runner, _ = complete
    entry = next(item for item in state["trials"].values() if item["parameters"]["role"] == "evaluation" and item["passed"])
    path = Path(entry["run_dir"])/name
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError, match="changed after the trial"):
        study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    report = comparison_v2.write_comparison(directory)
    assert report["successful_evaluations"] == 57 and report["consistency_errors"]
    assert len(runner.calls) == 69


@pytest.mark.parametrize("folder,filename", [("model", "model.npz"), ("recovery_model", "recovery.json")])
def test_changed_model_refuses_resume(complete, folder, filename):
    directory, _, runner, _ = complete
    (directory/folder/filename).write_text("changed")
    with pytest.raises(ValueError, match="model files changed"):
        study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 69
    assert comparison_v2.write_comparison(directory)["consistency_errors"]


def test_changed_source_refuses_resume(complete, monkeypatch):
    directory, _, runner, _ = complete
    monkeypatch.setattr(study, "source_fingerprint", lambda scope="evaluation": "modified-source")
    with pytest.raises(ValueError, match="source/model changed"):
        study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 69


def test_changed_inherited_demo_refuses_training(inherited_study, tmp_path, fake_runner, fake_fitter):
    directory = tmp_path/"v2"
    study.run_study("demo", study_dir=directory, v1_study_dir=inherited_study, trial_runner=fake_runner)
    old = next((inherited_study/"recordings").glob("*/signals.npz"))
    old.write_bytes(old.read_bytes()+b"changed")
    with pytest.raises(ValueError, match="changed after the trial"):
        study.run_study("train", study_dir=directory, model_fitter=fake_fitter)
    assert not fake_fitter.calls


def test_interrupted_attempt_stays_preserved(complete):
    directory, state, runner, _ = complete
    entry = next(item for item in state["trials"].values() if item["parameters"]["role"] == "evaluation")
    entry["status"] = "running"
    (directory/"study_state.json").write_text(json.dumps(state))
    with pytest.raises(ValueError, match="interrupted attempt remains preserved"):
        study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 69


def test_missing_cells_and_actual_initial_conditions_are_visible(tmp_path, inherited_study, fake_runner):
    directory = tmp_path/"v2"
    study.run_study("demo", study_dir=directory, v1_study_dir=inherited_study, trial_runner=fake_runner)
    report = comparison_v2.write_comparison(directory)
    assert report["attempted_evaluations"] == report["successful_evaluations"] == 0
    assert len(report["missing_evaluations"]) == 60
    assert all(group["success_fraction"] is None for group in report["aggregates"])


def test_raw_fallback_measures_intervals_and_positive_remaining_time(tmp_path):
    spec = study.protocol()["evaluations"][1]
    directory, _ = write_record(spec, tmp_path/"record")
    metadata = json.loads((directory/"metadata.json").read_text())
    result = comparison_v2.raw_adaptation_metrics(directory, metadata)
    assert result["fallback_active_time_s"] == pytest.approx(.03)
    assert result["fallback_commanded_foot_descent_m"] == pytest.approx(.002)
    assert result["fallback_commanded_com_travel_m"] == pytest.approx(.0002)
    assert result["fallback_active_plan_count"] == 1
    assert result["positive_remaining_time_fraction_after_missing"] == 1
    assert result["raw_recovery_positive_remaining_time_fraction"] == 1
    assert result["minimum_raw_recovery_remaining_time_s"] == .10
    assert result["learned_prior_active_plan_fraction"] == pytest.approx(2/3)
    assert result["remaining_time_mae_to_confirmed_reload_s"] < 1e-12
    with np.load(directory/"signals.npz") as archive:
        data = {name: archive[name] for name in archive.files}
    data["planner_remaining_time_s"][2] = 0
    data["raw_model_remaining_time_s"][2] = -.1
    np.savez(directory/"signals.npz", **data)
    result = comparison_v2.raw_adaptation_metrics(directory, metadata)
    assert result["positive_remaining_time_fraction"] == pytest.approx(2/3)
    assert result["positive_remaining_time_fraction_after_missing"] == .5
    assert result["raw_model_positive_remaining_time_fraction"] == pytest.approx(2/3)
    assert result["raw_recovery_positive_remaining_time_fraction"] == .5
    assert result["minimum_raw_recovery_remaining_time_s"] == -.1


def test_report_rejects_missing_source_attestation(complete):
    directory, state, _, _ = complete
    entry = next(item for item in state["trials"].values() if item["parameters"]["role"] == "evaluation" and item["passed"])
    del entry["actual_source_sha256"]
    (directory/"study_state.json").write_text(json.dumps(state))
    report = comparison_v2.write_comparison(directory)
    assert report["successful_evaluations"] == 57
    assert any("attestation" in error for error in report["consistency_errors"])


def test_report_rejects_recorded_model_substitution_even_with_updated_journal_hash(complete):
    directory, state, _, _ = complete
    entry = next(item for item in state["trials"].values() if item["parameters"]["role"] == "evaluation" and item["passed"])
    path = Path(entry["run_dir"])/"metadata.json"
    metadata = json.loads(path.read_text())
    metadata["recovery_model_hashes_sha256"]["recovery.npz"] = "other-model"
    path.write_text(json.dumps(metadata))
    entry["metadata_sha256"] = study._sha(path)
    (directory/"study_state.json").write_text(json.dumps(state))
    report = comparison_v2.write_comparison(directory)
    assert report["successful_evaluations"] == 57
    assert any("recovery_model hashes" in error for error in report["consistency_errors"])


def test_worker_checks_frozen_source_before_native_execution(tmp_path, monkeypatch):
    result = study._evaluation_worker({}, "different-source", {}, tmp_path)
    assert "differs before execution" in result["worker_error"]
    assert "run_dir" not in result


def test_parallel_parent_journals_every_attempt_and_resumes(tmp_path, inherited_study, fake_runner, fake_fitter, monkeypatch):
    directory = tmp_path/"v2"
    study.run_study("demo", study_dir=directory, v1_study_dir=inherited_study, trial_runner=fake_runner)
    study.run_study("train", study_dir=directory, model_fitter=fake_fitter)
    writes, actual_write = [], study._write_json
    def journal(path, value):
        if Path(path).name == "study_state.json":
            writes.append(threading.current_thread().name)
        actual_write(path, value)
    def worker(kwargs, expected_source, expected_models, directory):
        try:
            run, summary = fake_runner(**kwargs)
            return dict(run_dir=str(run), returned_summary=summary,
                        actual_source_before_sha256=expected_source, actual_source_after_sha256=expected_source)
        except RuntimeError as exc:
            return dict(worker_error=str(exc))
    monkeypatch.setattr(study, "_write_json", journal)
    monkeypatch.setattr(study, "_evaluation_worker", worker)
    monkeypatch.setattr(study, "ProcessPoolExecutor", lambda max_workers, mp_context: ThreadPoolExecutor(max_workers=max_workers))
    state = study.run_study("evaluate", study_dir=directory, workers=4)
    assert len(fake_runner.calls) == 69
    assert set(writes) == {threading.current_thread().name}
    assert all(item["status"] in ("completed", "error") for item in state["trials"].values())
    report = json.loads((directory/"comparison/comparison.json").read_text())
    assert report["attempted_evaluations"] == 60 and report["successful_evaluations"] == 58
    assert not report["consistency_errors"]
    study.run_study("evaluate", study_dir=directory, workers=4)
    assert len(fake_runner.calls) == 69


@pytest.mark.parametrize("workers", [0, 5, True, 1.5])
def test_invalid_worker_count_is_rejected(workers):
    with pytest.raises(ValueError, match="workers"):
        study.run_study("declare", workers=workers)
