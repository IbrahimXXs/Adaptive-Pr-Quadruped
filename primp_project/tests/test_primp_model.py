"""Numerical invariants and training/evaluation separation for the learned model."""

import hashlib
import json

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from primp_project.learning import PRIMPMotionModel, fit_runs, relative_features


@pytest.fixture
def demonstrations():
    heights = np.linspace(-.012, .012, 12)
    durations = np.exp(np.log(4.)-15*heights + .03*np.cos(np.arange(12)))
    u = np.linspace(0., 1., 17)
    smooth = 10*u**3-15*u**4+6*u**5
    features = np.zeros((len(heights), len(u), 9))
    for i, height in enumerate(heights):
        features[i, :, 0] = .1*height*smooth
        features[i, :, 2] = .35*height*smooth
        features[i, :, 4] = .7*height*smooth
        features[i, :, 8] = (-.03+height)*smooth
    return features, heights, durations


@pytest.fixture
def model(demonstrations):
    return PRIMPMotionModel.fit(*demonstrations)


def test_height_conditions_coordinated_body_foot_orientation_and_timing(model):
    low = model.condition(-.006, .0001)
    high = model.condition(.006, .0001)
    assert high.features[-1, 8]-low.features[-1, 8] == pytest.approx(.012, abs=4e-5)
    assert high.features[-1, 2]-low.features[-1, 2] == pytest.approx(.35*.012, abs=4e-5)
    assert high.features[-1, 4]-low.features[-1, 4] == pytest.approx(.7*.012, abs=4e-5)
    assert low.duration_s > high.duration_s+.5
    assert model.increment_covariance.shape == (17, 9, 9)
    assert np.abs(model.covariance[8, -2]) < np.abs(model.covariance[16*9+8, -2])


def test_conditional_precision_is_primp_markov_chain(model):
    # Given the global extension contexts, PRIMP has only adjacent time blocks.
    c = model.covariance
    residual = c[:-2, :-2]-c[:-2, -2:]@np.linalg.solve(c[-2:, -2:], c[-2:, :-2])
    precision = np.linalg.inv(residual)
    scale = np.max(np.abs(precision))
    for i in range(model.phase_points):
        for j in range(model.phase_points):
            if abs(i-j) > 1:
                assert np.max(np.abs(precision[i*9:(i+1)*9, j*9:(j+1)*9])) < scale*1e-7


def test_covariance_positive_and_conditioning_reduces_uncertainty(model):
    assert np.linalg.eigvalsh(model.covariance).min() > 0
    vague = model.condition(.005, .1)
    precise = model.condition(.005, .0001)
    assert np.all(precise.feature_variance <= vague.feature_variance+1e-12)
    assert np.all(precise.feature_variance >= 0)
    assert precise.log_duration_variance <= vague.log_duration_variance


def test_reconditioning_does_not_count_same_belief_twice(model):
    first = model.condition(-.005, .001)
    second = model.condition(-.005, .001)
    np.testing.assert_array_equal(first.features, second.features)
    np.testing.assert_array_equal(first.feature_variance, second.feature_variance)


def test_observed_current_pose_conditions_only_returned_suffix(model):
    actual = model.condition(0., .005).features[8].copy()
    actual[2] -= .002
    actual[8] -= .003
    result = model.condition(-.005, .001, current_phase=.5, current_features=actual,
                             state_std=np.full(9, 1e-7))
    assert result.start_index == 8
    assert result.phase[0] == .5
    assert len(result.features) == 9
    np.testing.assert_allclose(result.features[0], actual, atol=2e-7)
    assert result.features[-1, 8] < actual[8]


def test_uncertain_via_pose_reaches_requested_pose(model):
    waypoint = model.condition(0., .001).features[12].copy()
    waypoint[6] = .003
    waypoint[4] = .01
    result = model.condition(0., .001, waypoints=[(12, waypoint, np.full(9, 1e-8))])
    np.testing.assert_allclose(result.features[12], waypoint, atol=1e-7)


def test_explicit_duration_observation(model):
    p = model.condition(0., .01, duration_s=5., duration_std_s=.001)
    assert p.duration_s == pytest.approx(5., abs=.001)


def test_sampling_is_finite_and_has_zero_endpoint_velocity(model):
    p = model.condition(.005, .001)
    for u in np.linspace(0., 1., 101):
        values, velocity, acceleration = p.sample(u)
        assert np.all(np.isfinite(np.r_[values, velocity, acceleration]))
    np.testing.assert_allclose(p.sample(0.)[1], 0., atol=1e-12)
    np.testing.assert_allclose(p.sample(1.)[1], 0., atol=1e-12)
    last = model.condition(0., .001, current_phase=1.)
    np.testing.assert_array_equal(last.sample(1.)[1], np.zeros(9))


def test_so3_mean_crosses_rotation_vector_branch_without_averaging_to_zero():
    f = np.zeros((3, 3, 9))
    for i, angle in enumerate([179., 180., 181.]):
        f[i, :, 5] = Rotation.from_euler("z", angle, degrees=True).as_rotvec()[2]
    m = PRIMPMotionModel.fit(f, [-.01, 0., .01], [3., 4., 5.])
    assert abs(np.linalg.norm(m.mean_features[1, 3:6])-np.pi) < 1e-10


def test_relative_rotation_is_a_group_operation():
    origin = Rotation.from_euler("xyz", [0.2, -.1, 3.1])
    delta = Rotation.from_rotvec([.01, .02, .03])
    result = relative_features([1., 2., 3.], origin*delta, [4., 5., 6.],
                              start_com_position=[1., 2., 2.], start_body_rotation=origin,
                              start_foot_position=[3., 5., 6.])
    np.testing.assert_allclose(result, [0., 0., 1., .01, .02, .03, 1., 0., 0.], atol=1e-12)


def test_numeric_model_roundtrip_and_hash_validation(model, tmp_path):
    path = model.save(tmp_path)
    loaded = PRIMPMotionModel.load(path)
    np.testing.assert_array_equal(loaded.condition(.005, .001).features,
                                  model.condition(.005, .001).features)
    with np.load(path, allow_pickle=False) as arrays:
        assert all(arrays[name].dtype != object for name in arrays.files)
    path.write_bytes(path.read_bytes()+b"tampered")
    with pytest.raises(ValueError, match="hash"):
        PRIMPMotionModel.load(path)


@pytest.mark.parametrize("kw", [dict(height_std=-1.), dict(height_mean=np.nan),
                                    dict(current_phase=1.1), dict(duration_s=0.),
                                    dict(duration_std_s=0., duration_s=4.)])
def test_invalid_belief_or_time_rejected(model, kw):
    args = dict(height_mean=0., height_std=.001)
    args.update(kw)
    with pytest.raises(ValueError):
        model.condition(**args)


def test_fit_rejects_bad_data(demonstrations):
    f, h, d = demonstrations
    f = f.copy()
    f[0, 2, 8] = np.nan
    with pytest.raises(ValueError, match="finite"):
        PRIMPMotionModel.fit(f, h, d)
    with pytest.raises(ValueError, match="three demonstrations"):
        PRIMPMotionModel.fit(np.nan_to_num(f[:2]), h[:2], d[:2])


@pytest.fixture
def training_runs(tmp_path):
    dirs = []
    for i, height in enumerate([-.01, 0., .01]):
        run = tmp_path/f"demo_{i}"
        run.mkdir()
        dirs.append(run)
        metadata = dict(experiment="landing_pad", role="demonstration", status="completed",
                        known_height_m=height, nominal_lower_duration_s=3.+i,
                        evaluation={"actual_pad_height_m": 99.})  # Deliberate trap: never a label.
        (run/"metadata.json").write_text(json.dumps(metadata))
        (run/"pad_summary.json").write_text(json.dumps(dict(passed=True)))
        n = 12
        phase = np.array(["hold"]+["lower"]*8+["confirm"]*2+["reload"])
        com = np.tile([0., 0., .3], (n, 1))
        com[:, 2] += np.linspace(0., .35*height, n)
        feet = np.zeros((n, 4, 3))
        feet[:, 0, 2] = np.linspace(.05, .02+height, n)
        np.savez(run/"signals.npz", phase=phase, control_time_s=np.linspace(0., 3.+i, n),
                 contact_confirmed=phase == "reload", com_pos_w=com, feet_pos_w=feet,
                 base_rpy_rad=np.zeros((n, 3)))
    return dirs


def test_training_extraction_uses_only_training_labels_and_records_hashes(training_runs):
    model = fit_runs(training_runs, phase_points=11)
    assert model.context_mean[0] == pytest.approx(0.)
    assert model.metadata["training_height_range_m"] == [-.01, .01]
    assert len(model.metadata["training_records"]) == 3
    record = model.metadata["training_records"][0]
    assert record["signals_sha256"] == hashlib.sha256((training_runs[0]/"signals.npz").read_bytes()).hexdigest()
    assert np.all(model.mean_features[0] == 0.)


@pytest.mark.parametrize("change", [dict(role="evaluation"), dict(role="development"),
                                      dict(status="failed"), dict(experiment="controlled_step")])
def test_evaluation_or_failed_training_runs_are_rejected(training_runs, change):
    path = training_runs[0]/"metadata.json"
    metadata = json.loads(path.read_text())
    metadata.update(change)
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        fit_runs(training_runs)


def test_failed_analyzer_or_missing_confirmation_is_rejected(training_runs):
    path = training_runs[0]/"pad_summary.json"
    path.write_text(json.dumps(dict(passed=False)))
    with pytest.raises(ValueError, match="failed or incomplete"):
        fit_runs(training_runs)
    path.write_text(json.dumps(dict(passed=True)))
    path = training_runs[0]/"signals.npz"
    with np.load(path) as arrays:
        data = {name: arrays[name] for name in arrays.files}
    data["contact_confirmed"][:] = False
    np.savez(path, **data)
    with pytest.raises(ValueError, match="not contact-confirmed"):
        fit_runs(training_runs)


def test_duplicate_training_run_is_rejected(training_runs):
    with pytest.raises(ValueError, match="Duplicate"):
        fit_runs(training_runs+[training_runs[0]])
