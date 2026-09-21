"""Study provenance and failure accounting, using recorded synthetic signals.

The runner is replaced; the real training, serialization, journal validation and
comparison code are exercised. These fixtures are never simulation evidence.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from primp_project.analysis.comparison import write_comparison
from primp_project.experiments import pad_study
from primp_project.learning import PRIMPMotionModel


@pytest.fixture
def fake_runner():
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        evaluation = kwargs["role"] == "evaluation"
        # Both a valid failed result and an infrastructure exception must stay
        # in the denominator; neither may trigger silent reruns.
        if (evaluation and kwargs["planner"] == "predictive" and kwargs["actual_height_m"] < 0
                and kwargs["sensor_profile"] == "noisy_delayed"):
            raise RuntimeError("synthetic infrastructure failure")
        passed = not (evaluation and kwargs["planner"] == "learned" and kwargs["actual_height_m"] > 0
                      and kwargs["sensor_profile"] == "noisy_delayed")
        directory = Path(kwargs["output_group"])/f"synthetic_{len(calls):02d}"
        directory.mkdir(parents=True)
        metadata = dict(
            experiment="landing_pad", role=kwargs["role"], planner=kwargs["planner"], seed=kwargs["seed"],
            sensor_profile={"name": kwargs["sensor_profile"]}, initial_height_estimate_m=kwargs["initial_estimate_m"],
            nominal_lower_duration_s=kwargs["lower_duration_s"],
            evaluation={"actual_pad_height_m": kwargs["actual_height_m"]},
            status="completed" if passed else "failed", dt_s=.002, robot="go2", controller="nominal")
        if kwargs["role"] == "demonstration":
            metadata["known_height_m"] = kwargs["actual_height_m"]
        (directory/"metadata.json").write_text(json.dumps(metadata))
        summary = dict(passed=passed, criteria={"synthetic_check": {"passed": passed}}, metrics={
            "peak_normal_force_first_100ms_n": 5., "maximum_roll_pitch_change_during_landing_deg": .1,
            "lowering_to_completion_s": 12., "normal_impulse_first_100ms_ns": .3})
        (directory/"pad_summary.json").write_text(json.dumps(summary))
        phases = np.array(["hold"]+["lower"]*8+["confirm"]*2+["reload"])
        n = len(phases)
        com = np.tile([0., 0., .3], (n, 1))
        feet = np.zeros((n, 4, 3))
        com[:, 2] += np.linspace(0., .35*kwargs["actual_height_m"], n)
        feet[:, 0, 2] = np.linspace(.05, .02+kwargs["actual_height_m"], n)
        np.savez(directory/"signals.npz", phase=phases, control_time_s=np.linspace(0., kwargs["lower_duration_s"], n),
                 contact_confirmed=phases == "reload", com_pos_w=com, feet_pos_w=feet, base_rpy_rad=np.zeros((n, 3)))
        return directory, summary

    run.calls = calls
    return run


@pytest.fixture
def completed_study(tmp_path, fake_runner):
    directory = tmp_path/"study"
    state = pad_study.run_study("all", study_dir=directory, trial_runner=fake_runner)
    return directory, state, fake_runner


def test_declared_split_and_training_use_only_nine_known_clean_demos(completed_study):
    directory, state, runner = completed_study
    manifest = json.loads((directory/"split_manifest.json").read_text())
    assert len(manifest["demonstrations"]) == 9
    assert len(manifest["evaluations"]) == 18
    assert all(cell["actual_height_m"] == cell["initial_estimate_m"] for cell in manifest["demonstrations"])
    assert {cell["sensor_profile"] for cell in manifest["demonstrations"]} == {"clean"}
    model = PRIMPMotionModel.load(directory/"model")
    assert model.metadata["training_demonstrations"] == 9
    assert {record["role"] for record in model.metadata["training_records"]} == {"demonstration"}
    assert model.metadata["training_height_range_m"] == [-.01, .01]
    expected = {Path(entry["run_dir"]).name for entry in state["trials"].values()
                if entry["parameters"]["role"] == "demonstration"}
    assert set(state["model"]["training_run_ids"]) == expected
    assert len(runner.calls) == 27


def test_failures_are_reported_and_all_stage_resume_never_cherry_picks(completed_study):
    directory, _, runner = completed_study
    report = json.loads((directory/"comparison/comparison.json").read_text())
    assert report["attempted_evaluations"] == 18
    assert report["successful_evaluations"] == 16
    assert not report["missing_evaluations"]
    assert len(report["trials"]) == 18
    assert sum(row["status"] == "error" for row in report["trials"]) == 1
    assert sum(not row["passed"] for row in report["trials"]) == 2
    assert not report["consistency_errors"]
    for extension in ("csv", "json", "md", "png"):
        assert (directory/"comparison"/f"comparison.{extension}").is_file()
    pad_study.run_study("all", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 27


def test_training_cannot_change_after_evaluation_starts(completed_study):
    directory, _, runner = completed_study
    before = (directory/"model/model.npz").read_bytes()
    with pytest.raises(ValueError, match="Evaluation has begun"):
        pad_study.run_study("train", study_dir=directory, trial_runner=runner)
    assert (directory/"model/model.npz").read_bytes() == before


@pytest.mark.parametrize("filename", ["signals.npz", "metadata.json", "pad_summary.json"])
def test_resume_and_comparison_reject_changed_recording_hashes(completed_study, filename):
    directory, state, runner = completed_study
    entry = next(value for value in state["trials"].values()
                 if value["parameters"]["role"] == "evaluation" and value["passed"])
    path = Path(entry["run_dir"])/filename
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError, match="changed after the trial"):
        pad_study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    report = write_comparison(directory)
    assert report["consistency_errors"]
    assert report["successful_evaluations"] == 15
    assert len(runner.calls) == 27


def test_evaluation_resume_rejects_changed_source(completed_study, monkeypatch):
    directory, _, runner = completed_study
    monkeypatch.setattr(pad_study, "source_fingerprint", lambda scope="evaluation": "different-source")
    with pytest.raises(ValueError, match="code/model differs"):
        pad_study.run_study("evaluate", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 27


def test_missing_evaluation_cells_are_explicit_not_implicit_successes(tmp_path, fake_runner):
    directory = tmp_path/"study"
    pad_study.run_study("demo", study_dir=directory, trial_runner=fake_runner)
    report = write_comparison(directory)
    assert report["expected_evaluations"] == 18
    assert report["attempted_evaluations"] == 0
    assert report["successful_evaluations"] == 0
    assert len(report["missing_evaluations"]) == 18
    assert all(group["success_fraction"] is None for group in report["aggregates"])


def test_failed_demonstration_stops_before_training(tmp_path, fake_runner):
    def failed_demo(**kwargs):
        directory, summary = fake_runner(**kwargs)
        summary["passed"] = False
        (directory/"pad_summary.json").write_text(json.dumps(summary))
        return directory, summary

    directory = tmp_path/"study"
    with pytest.raises(RuntimeError, match="training stopped"):
        pad_study.run_study("demo", study_dir=directory, trial_runner=failed_demo)
    assert len(fake_runner.calls) == 1
    assert not (directory/"model/model.npz").exists()
    state = json.loads((directory/"study_state.json").read_text())
    assert len(state["trials"]) == 1
    assert not next(iter(state["trials"].values()))["passed"]


def test_no_evaluation_before_a_fitted_model(tmp_path, fake_runner):
    with pytest.raises(ValueError, match="Train and preserve"):
        pad_study.run_study("evaluate", study_dir=tmp_path/"study", trial_runner=fake_runner)
    assert not fake_runner.calls


def test_training_rejects_evaluation_record_substituted_for_demo(tmp_path, fake_runner):
    directory = tmp_path/"study"
    state = pad_study.run_study("demo", study_dir=directory, trial_runner=fake_runner)
    entry = next(iter(state["trials"].values()))
    metadata_path = Path(entry["run_dir"])/"metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["role"] = "evaluation"
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="does not match declared cell"):
        pad_study.run_study("train", study_dir=directory, trial_runner=fake_runner)
    assert not (directory/"model/model.npz").exists()


def test_supplement_predeclares_six_untouched_heights_without_changing_primary(completed_study):
    directory, _, _ = completed_study
    original = (directory/"split_manifest.json").read_bytes()
    manifest, path = pad_study.ensure_held_out_manifest(directory)
    assert path == directory/"held_out_heights/split_manifest.json"
    assert len(manifest["evaluations"]) == 6
    assert not manifest["demonstrations"]
    heights = {cell["actual_height_m"] for cell in manifest["evaluations"]}
    assert heights == {-.0075, .0075}
    assert heights.isdisjoint({-.01, -.005, 0., .005, .01})
    assert {cell["planner"] for cell in manifest["evaluations"]} == {"reactive", "predictive", "learned"}
    assert {cell["sensor_profile"] for cell in manifest["evaluations"]} == {"clean"}
    assert all(cell["initial_estimate_m"] == 0. and cell["role"] == "evaluation" for cell in manifest["evaluations"])
    assert (directory/"split_manifest.json").read_bytes() == original
    first_declaration = path.read_bytes()
    pad_study.ensure_held_out_manifest(directory)
    assert path.read_bytes() == first_declaration


def test_supplement_uses_unchanged_original_model_and_resumes_all_six_cells(completed_study):
    directory, _, runner = completed_study
    before_model = (directory/"model/model.npz").read_bytes()
    before_primary = (directory/"study_state.json").read_bytes()
    state = pad_study.run_held_out_heights(study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 33
    assert len(state["trials"]) == 6
    assert all(entry["passed"] for entry in state["trials"].values())
    assert (directory/"model/model.npz").read_bytes() == before_model
    assert (directory/"study_state.json").read_bytes() == before_primary
    supplement = directory/"held_out_heights"
    report = json.loads((supplement/"comparison/comparison.json").read_text())
    assert report["attempted_evaluations"] == 6 and report["successful_evaluations"] == 6
    assert "±7.5 mm" in report["interpretation"] and "±5 mm" not in report["interpretation"]
    assert "live engineering development" in report["interpretation"]
    assert not report["consistency_errors"]
    for entry in state["trials"].values():
        assert Path(entry["run_dir"]).parent == supplement/"recordings"
        if entry["parameters"]["planner"] == "learned":
            assert entry["model_sha256"] == state["model"]["model_sha256"]
    pad_study.run_study("heldout", study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 33


def test_supplement_cannot_run_before_primary_or_with_different_controller(tmp_path, fake_runner, monkeypatch):
    directory = tmp_path/"study"
    pad_study.run_study("demo", study_dir=directory, trial_runner=fake_runner)
    pad_study.run_study("train", study_dir=directory, trial_runner=fake_runner)
    # Declaration is allowed before the paired pilot starts; execution waits.
    pad_study.ensure_held_out_manifest(directory)
    with pytest.raises(ValueError, match="eighteen declared"):
        pad_study.run_held_out_heights(study_dir=directory, trial_runner=fake_runner)
    assert len(fake_runner.calls) == 9
    pad_study.run_study("evaluate", study_dir=directory, trial_runner=fake_runner)
    monkeypatch.setattr(pad_study, "source_fingerprint", lambda scope="evaluation": "different-controller")
    with pytest.raises(ValueError, match="source/controller unchanged"):
        pad_study.run_held_out_heights(study_dir=directory, trial_runner=fake_runner)
    assert len(fake_runner.calls) == 27


def test_supplement_rejects_changed_inherited_model(completed_study):
    directory, _, runner = completed_study
    pad_study.ensure_held_out_manifest(directory)
    path = directory/"model/model.npz"
    path.write_bytes(path.read_bytes()+b"changed")
    with pytest.raises(ValueError, match="original nine-demonstration model"):
        pad_study.run_held_out_heights(study_dir=directory, trial_runner=runner)
    assert len(runner.calls) == 27
