"""Recovery learning uses measured current states and positive event time labels."""

import hashlib
import json

import numpy as np
import pytest

from primp_project.learning import RecoveryMotionModel, fit_recovery_runs, fit_runs


@pytest.fixture
def model():
    clearances = np.linspace(.0005, .012, 14)
    remaining = .2+clearances/.004
    phase = np.linspace(0., 1., 17)
    f = np.zeros((len(clearances), len(phase), 9))
    for i, clearance in enumerate(clearances):
        f[i, :, 2] = -.25*clearance*phase
        f[i, :, 4] = .5*clearance*phase
        f[i, :, 8] = -clearance*phase
    return RecoveryMotionModel.fit(f, clearances, remaining)


def test_remaining_time_depends_on_current_measured_clearance_not_exhausted_phase(model):
    near = model.condition_belief([-.004], [1.], current_foot_bottom_m=-.003)
    far = model.condition_belief([-.004], [1.], current_foot_bottom_m=.006)
    assert 0 < near.duration_s < far.duration_s
    assert far.duration_s > 2*near.duration_s
    assert near.phase[0] == far.phase[0] == 0.
    assert near.start_index == far.start_index == 0
    np.testing.assert_allclose(far.features[0], np.zeros(9), atol=1e-12)
    assert far.features[-1, 8] == pytest.approx(-.01, abs=1e-7)
    assert far.features[-1, 2] == pytest.approx(-.0025, abs=1e-7)
    # A lower belief at the same measured state predicts extra physical time.
    deeper = model.condition_belief([-.008], [1.], current_foot_bottom_m=-.003)
    assert deeper.duration_s > near.duration_s
    assert deeper.features[-1, 8] < near.features[-1, 8]


def test_recovery_preserves_supplied_height_weights_and_cross_covariance(model):
    heights, weights = np.array([-.008, -.003]), np.array([.8, .2])
    prediction = model.condition_belief(heights, weights, current_foot_bottom_m=.001)
    np.testing.assert_allclose(prediction.mixture_heights, heights)
    np.testing.assert_allclose(prediction.mixture_weights, weights)
    assert prediction.joint_covariance.shape == (17*9+1,)*2
    assert abs(prediction.joint_covariance[-2, -1]) > 1e-5
    assert prediction.unsupported_probability == 0
    unsupported = model.condition_belief([-.04, -.003], weights, current_foot_bottom_m=.001)
    assert unsupported.unsupported_probability == pytest.approx(.8)


def test_separate_recovery_artifact_roundtrip_and_hash_guard(model, tmp_path):
    path = model.save(tmp_path)
    assert path.name == "recovery.npz"
    assert path.with_suffix(".json").exists()
    loaded = RecoveryMotionModel.load(tmp_path)
    original = model.condition_belief([-.004], [1.], current_foot_bottom_m=.003)
    restored = loaded.condition_belief([-.004], [1.], current_foot_bottom_m=.003)
    np.testing.assert_array_equal(original.features, restored.features)
    np.testing.assert_array_equal(original.joint_covariance, restored.joint_covariance)
    path.write_bytes(path.read_bytes()+b"corrupt")
    with pytest.raises(ValueError, match="hash"):
        RecoveryMotionModel.load(tmp_path)


@pytest.fixture
def recovery_runs(tmp_path):
    directories = []
    for i, height in enumerate([-.004, -.008, -.012]):
        directory = tmp_path/f"recovery_{i}"
        directory.mkdir()
        directories.append(directory)
        metadata = dict(experiment="landing_pad", role="demonstration", status="completed",
            recovery_demonstration=True, known_height_m=height, initial_height_estimate_m=0.,
            nominal_lower_duration_s=3.+i, foot_radius_m=.02,
            evaluation={"actual_pad_height_m": 99.})
        (directory/"metadata.json").write_text(json.dumps(metadata))
        (directory/"pad_summary.json").write_text(json.dumps(dict(passed=True)))
        n = 101
        phase = np.array(["hold"]*5+["lower"]*75+["confirm"]*20+["reload"])
        time = np.linspace(0., 3.+i, n)
        com = np.tile([.1, .2, .3], (n, 1))
        com[:, 2] += np.linspace(0., -.25*(.03-height), n)
        feet = np.zeros((n, 4, 3))
        feet[:, 0] = np.column_stack((np.full(n, .2), np.full(n, .1), np.linspace(.05, .02+height, n)))
        body_rpy = np.zeros((n, 3))
        body_rpy[:, 1] = np.linspace(0., .5*(.03-height), n)
        np.savez(directory/"signals.npz", phase=phase, control_time_s=time,
            contact_confirmed=phase == "reload", com_pos_w=com, feet_pos_w=feet,
            feet_pos_des_w=feet+99., base_rpy_rad=body_rpy, missing_contact=np.arange(n) >= 60)
    return directories


def test_extracts_measured_relative_windows_and_event_time_with_provenance(recovery_runs, tmp_path):
    split = tmp_path/"split.json"
    split.write_text('{"fitting":"demonstrations_only"}')
    model = fit_recovery_runs(recovery_runs, phase_points=13, split_manifest_path=split,
                              window_stride_s=.2, min_remaining_s=.15)
    meta = model.metadata
    assert meta["training_demonstrations"] == 3
    assert meta["training_windows"] > 10
    assert len(meta["training_records"]) == 3
    assert len(meta["window_records"]) == meta["training_windows"]
    assert meta["split_manifest_sha256"] == hashlib.sha256(split.read_bytes()).hexdigest()
    assert meta["context_variable"] == "measured_clearance_to_surface_m"
    for window in meta["window_records"]:
        assert window["start_sample"] >= 60
        assert window["reload_sample"] == 100
        assert window["remaining_duration_s"] >= .15-1e-12
        assert window["remaining_duration_s"] == pytest.approx(window["reload_time_s"]-window["start_time_s"])
        assert window["known_height_m"] < 0
        assert window["clearance_to_known_surface_m"] == pytest.approx(window["measured_foot_bottom_m"]-window["known_height_m"])
    np.testing.assert_allclose(model.motion_model.mean_features[0], np.zeros(9), atol=1e-12)
    mean_clearance = np.mean([w["clearance_to_known_surface_m"] for w in meta["window_records"]])
    assert model.motion_model.mean_features[-1, 8] == pytest.approx(-mean_clearance)
    record = meta["training_records"][0]
    assert record["signals_sha256"] == hashlib.sha256((recovery_runs[0]/"signals.npz").read_bytes()).hexdigest()
    full = fit_runs(recovery_runs, phase_points=13)
    assert full.metadata["training_demonstrations"] == 3
    assert full.metadata["training_height_range_m"] == [-.012, -.004]


@pytest.mark.parametrize("change", [dict(role="evaluation"), dict(role="development"),
    dict(recovery_demonstration=False), dict(recovery_demonstration="true"),
    dict(status="failed"), dict(foot_radius_m=0), dict(known_height_m=float("nan"))])
def test_recovery_extraction_rejects_unqualified_data(recovery_runs, change):
    path = recovery_runs[0]/"metadata.json"
    metadata = json.loads(path.read_text())
    metadata.update(change)
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        fit_recovery_runs(recovery_runs)


def test_nominal_extraction_requires_explicit_permission_for_mismatched_demonstration(recovery_runs):
    path = recovery_runs[0]/"metadata.json"
    metadata = json.loads(path.read_text())
    metadata.pop("recovery_demonstration")
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="mismatched"):
        fit_runs(recovery_runs)


def test_recovery_extraction_rejects_absent_missing_event_and_failed_support(recovery_runs):
    path = recovery_runs[0]/"signals.npz"
    with np.load(path) as arrays:
        data = {name: arrays[name] for name in arrays.files}
    data["missing_contact"][:] = False
    np.savez(path, **data)
    with pytest.raises(ValueError, match="no missing-contact"):
        fit_recovery_runs(recovery_runs)
    data["missing_contact"][60:] = True
    data["contact_confirmed"][:] = False
    np.savez(path, **data)
    with pytest.raises(ValueError, match="not contact-confirmed"):
        fit_recovery_runs(recovery_runs)


def test_recovery_windows_cannot_hide_failed_summary_or_duplicate_trials(recovery_runs):
    with pytest.raises(ValueError, match="Duplicate"):
        fit_recovery_runs(recovery_runs+[recovery_runs[0]])
    path = recovery_runs[0]/"pad_summary.json"
    path.write_text('{"passed": false}')
    with pytest.raises(ValueError, match="failed or incomplete"):
        fit_recovery_runs(recovery_runs)
