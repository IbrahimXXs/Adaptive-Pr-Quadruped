"""Posterior integration must not multiply an estimator posterior by p_train(h)."""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from primp_project.learning import PRIMPMotionModel


@pytest.fixture
def model():
    heights = np.linspace(-.012, .012, 13)
    durations = np.exp(np.log(4.)-24*heights+.06*np.cos(np.arange(len(heights))))
    phase = np.linspace(0., 1., 13)
    f = np.zeros((len(heights), len(phase), 9))
    for i, h in enumerate(heights):
        f[i, :, 2] = .35*h*phase
        f[i, :, 4] = .7*h*phase
        f[i, :, 8] = (-.03+h)*phase
    return PRIMPMotionModel.fit(f, heights, durations)


def _local_vector(model, prediction):
    start = prediction.start_index
    difference = prediction.features-model.mean_features[start:]
    difference[:, 3:6] = (Rotation.from_rotvec(model.mean_features[start:, 3:6]).inv()
                          * Rotation.from_rotvec(prediction.features[:, 3:6])).as_rotvec()
    return np.r_[difference.ravel(), prediction.log_duration_mean]


def test_external_posterior_mean_does_not_shrink_toward_training_prior(model):
    heights = np.array([.018, .024, .029])  # Entire support lies outside training.
    weights = np.array([.12, .31, .57])
    posterior = model.condition_belief(heights, weights)
    assert posterior.features[-1, 8]+.03 == pytest.approx(weights@heights, abs=8e-8)
    assert posterior.features[-1, 2] == pytest.approx(.35*(weights@heights), abs=5e-8)
    np.testing.assert_allclose(posterior.mixture_weights, weights, atol=1e-15)
    assert posterior.unsupported_probability == pytest.approx(1.)
    # The retained V1 observation API combines its input with the training
    # prior, which is deliberately a different and unsuitable operation here.
    old = model.condition(weights@heights, .02)
    assert old.features[-1, 8]+.03 < (weights@heights)*.3


def test_arbitrary_multimodal_mixture_preserves_full_total_covariance(model):
    heights = np.array([-.02, -.005, .003, .025])
    weights = np.array([.08, .17, .25, .5])
    current = model.condition_belief([-.01], [1.]).features[6].copy()
    current[2] += .002
    kwargs = dict(current_phase=.5, current_features=current, state_std=np.full(9, .0002))
    mixture = model.condition_belief(heights, weights, **kwargs)
    components = [model.condition_belief([h], [1.], **kwargs) for h in heights]
    means = np.asarray([_local_vector(model, p) for p in components])
    expected_mean = weights@means
    expected_covariance = sum(w*(p.joint_covariance+np.outer(m-expected_mean, m-expected_mean))
                              for w, p, m in zip(weights, components, means))
    np.testing.assert_allclose(_local_vector(model, mixture), expected_mean, atol=2e-12)
    np.testing.assert_allclose(mixture.joint_covariance, expected_covariance, atol=2e-12)
    np.testing.assert_allclose(mixture.mixture_weights, weights, atol=1e-15)
    np.testing.assert_allclose(np.diag(mixture.joint_covariance)[:-1], mixture.feature_variance.ravel())
    assert mixture.log_duration_variance == pytest.approx(mixture.joint_covariance[-1, -1])
    assert np.linalg.eigvalsh(mixture.joint_covariance).min() > -1e-12
    # Body/foot and foot/time correlations survive marginalizing the context.
    final_body_z, final_foot_z = -8, -2
    assert abs(mixture.joint_covariance[final_body_z, final_foot_z]) > 1e-9
    assert abs(mixture.joint_covariance[final_foot_z, -1]) > 1e-8
    expected_duration = sum(w*p.duration_s for w, p in zip(weights, components))
    expected_duration_second = sum(w*(p.duration_s**2+p.duration_std_s**2)
                                   for w, p in zip(weights, components))
    assert mixture.duration_s == pytest.approx(expected_duration, rel=1e-12)
    assert mixture.duration_std_s**2 == pytest.approx(expected_duration_second-expected_duration**2, abs=1e-12)


def test_exact_height_component_matches_independent_gaussian_solve(model):
    # At phase >0 without a current waypoint there is only one observation, h.
    h = -.0073
    prediction = model.condition_belief([h], [1.], current_phase=.25)
    height_index = model.phase_points*9
    gain = model.covariance[:, height_index]/model.covariance[height_index, height_index]
    expected_mean = gain*(h-model.context_mean[0])
    expected_covariance = model.covariance-np.outer(gain, model.covariance[height_index])
    ids = np.r_[np.arange(prediction.start_index*9, height_index), height_index+1]
    expected_mean[-1] += model.context_mean[1]
    np.testing.assert_allclose(_local_vector(model, prediction), expected_mean[ids], atol=1e-12)
    np.testing.assert_allclose(prediction.joint_covariance, expected_covariance[np.ix_(ids, ids)], atol=1e-12)


def test_endpoint_conditioning_uses_each_fixed_height_and_preserves_terrain_variance(model):
    heights, weights = np.array([-.006, .008]), np.array([.2, .8])
    prediction = model.condition_belief(heights, weights, foot_endpoint_offset_m=-.035, endpoint_std_m=1e-8)
    assert prediction.features[-1, 8] == pytest.approx(weights@heights-.035, abs=1e-7)
    assert prediction.feature_variance[-1, 8] == pytest.approx(weights@(heights-weights@heights)**2, rel=1e-5)
    np.testing.assert_allclose(prediction.mixture_weights, weights)


def test_241_grid_weights_and_uncertainty_are_retained(model):
    heights = np.linspace(-.03, .01, 241)
    weights = np.exp(-((heights+.02)/.004)**2)+.2*np.exp(-((heights-.006)/.001)**2)
    weights[80:140] = 0.
    prediction = model.condition_belief(heights, weights)
    np.testing.assert_allclose(prediction.mixture_weights, weights/weights.sum(), rtol=1e-14)
    assert len(prediction.mixture_heights) == 241
    assert prediction.joint_covariance.shape == (model.phase_points*9+1,)*2
    assert 0 < prediction.unsupported_probability < 1
    assert prediction.duration_std_s > 0


@pytest.mark.parametrize("heights, weights", [([], []), ([0], [0]), ([0], [-1]),
    ([0, 1], [1]), ([[0]], [[1]]), ([np.nan], [1]), ([0], [np.inf])])
def test_invalid_posterior_is_rejected(model, heights, weights):
    with pytest.raises(ValueError):
        model.condition_belief(heights, weights)


def test_zero_mass_and_large_unnormalized_weights_are_safe(model):
    with_zero = model.condition_belief([-.005, .5], [1e308, 0.])
    only = model.condition_belief([-.005], [1.])
    np.testing.assert_allclose(with_zero.features, only.features)
    np.testing.assert_allclose(with_zero.joint_covariance, only.joint_covariance)
    assert with_zero.duration_s == pytest.approx(only.duration_s)
    assert with_zero.unsupported_probability == 0.
