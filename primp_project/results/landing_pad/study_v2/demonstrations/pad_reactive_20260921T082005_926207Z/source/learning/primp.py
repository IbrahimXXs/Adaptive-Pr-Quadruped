"""A PRIMP trajectory distribution with quadruped and timing extensions.

The relative-pose Markov construction and uncertain via-point conditioning
follow Ruan et al., PRIMP, arXiv:2305.15761, equations 6, 9 and 13. This is an
independent implementation, not the upstream package or a ProMP basis model.
The product group R3 x SO(3) x R3 couples physical CoM, body rotation and FL
translation. Height and log-duration are additional learned global contexts.
See ../docs/PRIMP_MODEL.md for the exact differences from published PRIMP.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.transform import Rotation
from scipy.special import logsumexp


FEATURE_NAMES = ("com_dx", "com_dy", "com_dz", "body_rx", "body_ry", "body_rz",
                 "foot_dx", "foot_dy", "foot_dz")
MODEL_VERSION = 1


def _finite(name, value):
    result = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _rotation_mean(rotations):
    """Right-invariant Karcher mean, satisfying sum Log(Rmean.T Ri)=0."""
    mean = rotations[0]
    for _ in range(100):
        delta = np.mean((mean.inv() * rotations).as_rotvec(), axis=0)
        mean = mean * Rotation.from_rotvec(delta)
        if np.linalg.norm(delta) < 1e-12:
            return mean
    raise ValueError("Body rotations are too dispersed for a local PRIMP model")


def relative_features(com_position, body_rotation, foot_position, *,
                      start_com_position, start_body_rotation, start_foot_position):
    """Make 9D features; rotations are scipy Rotation objects, not Euler angles."""
    return np.concatenate((np.asarray(com_position)-np.asarray(start_com_position),
                           (start_body_rotation.inv()*body_rotation).as_rotvec(),
                           np.asarray(foot_position)-np.asarray(start_foot_position)), axis=-1)


@dataclass(frozen=True)
class MotionPrediction:
    """A causal suffix; no samples before ``start_index`` are returned.

    ``duration_s`` is the predicted total lowering duration. Interpolation
    derivatives returned by sample() are with respect to normalized phase;
    divide by duration and duration squared for SI velocity/acceleration.
    """

    features: np.ndarray
    phase: np.ndarray
    duration_s: float
    start_index: int
    feature_variance: np.ndarray
    log_duration_variance: float
    joint_covariance: np.ndarray | None = None
    log_duration_mean: float | None = None
    duration_std_s: float | None = None
    mixture_heights: np.ndarray | None = None
    mixture_weights: np.ndarray | None = None
    unsupported_probability: float = 0.

    def sample(self, phase):
        if len(self.phase) == 1:
            return self.features[0].copy(), np.zeros(9), np.zeros(9)
        spline = CubicSpline(self.phase, self.features, axis=0,
                             bc_type=((1, np.zeros(9)), (1, np.zeros(9))))
        u = float(np.clip(phase, self.phase[0], self.phase[-1]))
        return spline(u), spline(u, 1), spline(u, 2)


class PRIMPMotionModel:
    """Learn local relative-motion distributions and condition their joint PDF.

    All nine channels remain coupled in each increment covariance. The joint
    PDF is the PRIMP Markov chain conditional on global height/log-duration;
    marginalizing those learned contexts adds correlations across the entire
    motion. No evaluation ground truth is accepted by condition().
    """

    def __init__(self, mean_features, context_mean, covariance, increment_covariance,
                 context_regression, metadata=None):
        self.mean_features = _finite("mean_features", mean_features)
        if self.mean_features.ndim != 2 or self.mean_features.shape[1] != 9:
            raise ValueError("mean_features must have shape [phase_points, 9]")
        self.phase_points = len(self.mean_features)
        self.context_mean = _finite("context_mean", context_mean)
        self.covariance = _finite("covariance", covariance)
        self.increment_covariance = _finite("increment_covariance", increment_covariance)
        self.context_regression = _finite("context_regression", context_regression)
        self.metadata = dict(metadata or {})
        n = self.phase_points*9+2
        if self.context_mean.shape != (2,) or self.covariance.shape != (n, n):
            raise ValueError("Invalid joint context/covariance shape")
        if not np.allclose(self.covariance, self.covariance.T, atol=1e-12):
            raise ValueError("Joint covariance must be symmetric")
        cho_factor(self.covariance, lower=True, check_finite=False)
        self._mean_rotations = Rotation.from_rotvec(self.mean_features[:, 3:6])

    @classmethod
    def fit(cls, features, heights_m, durations_s, *, training_records=None,
            translation_noise_m=2e-5, rotation_noise_rad=2e-4):
        """Fit phase-aligned measured demonstrations [D,K,9], with D>=3.

        Height labels are known pad-top offsets from the fixed support surface,
        in metres. Duration labels are measured lower-start to confirmed support
        times. These two labels are only accepted by the offline fit path.
        """
        f = _finite("features", features)
        if f.ndim != 3 or f.shape[2] != 9 or f.shape[0] < 3 or f.shape[1] < 3:
            raise ValueError("Need at least three demonstrations of shape [D,K>=3,9]")
        d, k, _ = f.shape
        heights = _finite("heights_m", heights_m)
        durations = _finite("durations_s", durations_s)
        if heights.shape != (d,) or durations.shape != (d,) or np.any(durations <= 0):
            raise ValueError("One finite height and positive duration are required per demonstration")
        if translation_noise_m <= 0 or rotation_noise_rad <= 0:
            raise ValueError("Covariance regularization must be positive")
        contexts = np.column_stack((heights, np.log(durations)))
        context_mean = contexts.mean(axis=0)
        centered_context = contexts-context_mean
        context_cov = centered_context.T@centered_context/d + np.diag([1e-10, 1e-8])
        context_factor = cho_factor(context_cov, lower=True, check_finite=False)
        means = f.mean(axis=0)
        rotations = [Rotation.from_rotvec(f[:, i, 3:6]) for i in range(k)]
        mean_rotations = [_rotation_mean(r) for r in rotations]
        for i in range(k):
            means[i, 3:6] = mean_rotations[i].as_rotvec()
        # PRIMP local coordinates are Log(mean^-1 sample), not differences of
        # rotation vectors; translations use the PCG/direct-product convention.
        local = f-means[None, :, :]
        for i in range(k):
            local[:, i, 3:6] = (mean_rotations[i].inv()*rotations[i]).as_rotvec()
        increments = np.zeros_like(local)
        increments[:, 0] = local[:, 0]
        transports = np.repeat(np.eye(9)[None], k, axis=0)
        for i in range(1, k):
            increment = f[:, i]-f[:, i-1]
            relative_rotation = rotations[i-1].inv()*rotations[i]
            relative_mean = _rotation_mean(relative_rotation)
            increment[:, 3:6] = (relative_mean.inv()*relative_rotation).as_rotvec()
            increment[:, :3] -= increment[:, :3].mean(axis=0)
            increment[:, 6:] -= increment[:, 6:].mean(axis=0)
            increments[:, i] = increment
            # Ad(mean_i-1^-1 mean_i)^-1 for R3 x SO(3) x R3.
            transports[i, 3:6, 3:6] = (mean_rotations[i-1].inv()*mean_rotations[i]).as_matrix().T
        regularization = np.diag(np.square([translation_noise_m]*3 +
                                           [rotation_noise_rad]*3 + [translation_noise_m]*3))
        regression = np.empty((k, 9, 2))
        noise = np.empty((k, 9, 9))
        for i in range(k):
            cross = increments[:, i].T@centered_context/d
            regression[i] = cho_solve(context_factor, cross.T, check_finite=False).T
            residual = increments[:, i]-centered_context@regression[i].T
            noise[i] = residual.T@residual/d + regularization
        # x_i = A_i x_(i-1) + B_i c + eps_i. The implied conditional precision
        # is exactly PRIMP's block-tridiagonal construction. Building the joint
        # covariance recursively avoids inverses of poorly scaled 9K matrices.
        n = 9*k
        covariance = np.zeros((n+2, n+2))
        covariance[n:, n:] = context_cov
        for i in range(k):
            s = slice(9*i, 9*(i+1))
            b = regression[i]
            if i == 0:
                covariance[s, n:] = b@context_cov
                covariance[s, s] = b@context_cov@b.T+noise[i]
            else:
                prev = slice(9*(i-1), 9*i)
                a = transports[i]
                covariance[s, :9*i] = a@covariance[prev, :9*i]+b@covariance[n:, :9*i]
                covariance[:9*i, s] = covariance[s, :9*i].T
                covariance[s, n:] = a@covariance[prev, n:]+b@context_cov
                cross = a@covariance[prev, n:]@b.T
                covariance[s, s] = a@covariance[prev, prev]@a.T + b@context_cov@b.T + cross+cross.T+noise[i]
            covariance[n:, s] = covariance[s, n:].T
        covariance = (covariance+covariance.T)/2
        metadata = dict(model="PRIMP product-group with height/log-duration contexts", version=MODEL_VERSION,
                        group="R3(CoM) x SO3(body) x R3(FL)", feature_names=list(FEATURE_NAMES),
                        phase_alignment="uniform normalized lowering phase; event-aligned endpoints",
                        training_demonstrations=d, phase_points=k,
                        training_height_range_m=[float(heights.min()), float(heights.max())],
                        training_duration_range_s=[float(durations.min()), float(durations.max())],
                        translation_noise_m=translation_noise_m, rotation_noise_rad=rotation_noise_rad,
                        training_records=list(training_records or []),
                        paper="https://arxiv.org/abs/2305.15761",
                        upstream_reference="https://github.com/ChirikjianLab/primp-python",
                        implementation="Independent implementation of relative-pose Gaussian chain and via-point conditioning")
        return cls(means, context_mean, covariance, noise, regression, metadata)

    def condition(self, height_mean, height_std, *, duration_s=None, duration_std_s=.1,
                  current_phase=0., current_features=None, state_std=None, waypoints=()):
        """Condition on terrain belief and already observed state, returning a suffix.

        Optional waypoints are ``(index, features9, std9)`` tuples. The initial
        state is anchored to zero unless current_features is supplied. Height
        uncertainty is observation noise: repeated calls always begin from the
        same prior, so the same belief is never spuriously counted twice.
        """
        if not np.isfinite(height_mean) or not np.isfinite(height_std) or height_std < 0:
            raise ValueError("Height belief must be finite with nonnegative standard deviation")
        if not np.isfinite(current_phase) or not 0 <= current_phase <= 1:
            raise ValueError("current_phase must lie in [0,1]")
        k = self.phase_points
        n = 9*k
        start = min(int(np.floor(current_phase*(k-1)+1e-9)), k-1)
        ids, values, variances = [n], [height_mean-self.context_mean[0]], [max(height_std**2, 1e-14)]
        if duration_s is not None:
            if not np.isfinite(duration_s) or duration_s <= 0 or not np.isfinite(duration_std_s) or duration_std_s <= 0:
                raise ValueError("Duration and its uncertainty must be positive and finite")
            ids.append(n+1)
            values.append(np.log(duration_s)-self.context_mean[1])
            variances.append((duration_std_s/duration_s)**2)
        if current_features is None and start == 0:
            current_features = np.zeros(9)
        observations = list(waypoints)
        if current_features is not None:
            if state_std is None:
                state_std = np.array([2e-5]*3+[2e-4]*3+[2e-5]*3)
            observations.append((start, current_features, state_std))
        for index, feature, std in observations:
            if isinstance(index, bool) or int(index) != index or not 0 <= index < k:
                raise ValueError("Waypoint index is outside the learned phase grid")
            index = int(index)
            feature = _finite("waypoint", feature)
            std = np.broadcast_to(_finite("waypoint uncertainty", std), (9,))
            if feature.shape != (9,) or np.any(std <= 0):
                raise ValueError("Waypoint needs nine features and positive uncertainties")
            error = feature-self.mean_features[index]
            error[3:6] = (self._mean_rotations[index].inv()*Rotation.from_rotvec(feature[3:6])).as_rotvec()
            ids.extend(range(index*9, (index+1)*9))
            values.extend(error)
            variances.extend(std**2)
        ids = np.asarray(ids)
        cross = self.covariance[:, ids]
        innovation = self.covariance[np.ix_(ids, ids)] + np.diag(variances)
        factor = cho_factor(innovation, lower=True, check_finite=False)
        gain = cho_solve(factor, cross.T, check_finite=False).T
        posterior_mean = gain@np.asarray(values)
        posterior_diagonal = np.maximum(np.diag(self.covariance)-np.sum(gain*cross, axis=1), 0.)
        local = posterior_mean[:n].reshape(k, 9)
        result = self.mean_features+local
        result[:, 3:6] = (self._mean_rotations*Rotation.from_rotvec(local[:, 3:6])).as_rotvec()
        duration = float(np.exp(self.context_mean[1]+posterior_mean[-1]))
        if not np.isfinite(duration):
            raise ValueError("Conditioned duration is nonfinite; observation lies outside model domain")
        return MotionPrediction(result[start:].copy(), np.linspace(0., 1., k)[start:], duration,
                                start, posterior_diagonal[:n].reshape(k, 9)[start:],
                                float(posterior_diagonal[-1]))

    def condition_belief(self, heights, probabilities, *, duration_s=None, duration_std_s=.1,
                        current_phase=0., current_features=None, state_std=None, waypoints=(),
                        foot_endpoint_offset_m=None, endpoint_std_m=.0005):
        """Integrate exact-height motion conditionals under a supplied posterior.

        This API treats ``q(h)`` as the terrain posterior, not as a noisy height
        measurement to multiply by the demonstration height prior. Its weights
        stay fixed even when a height is unlikely under the training data or
        a continuity waypoint. For each h, we condition the learned Gaussian on
        that exact height and the same optional waypoint observations, then use
        total expectation/covariance across q. No Gaussian approximation to q
        is needed: only its first two moments enter the affine latent mean;
        positive duration moments use the complete discrete distribution.

        ``joint_covariance`` orders the returned suffix's 9D local tangent
        coordinates followed by log-duration. It retains all within-motion,
        body/foot, and timing cross terms. Rotation covariance uses the model's
        common local SO(3) chart (the same small-angle approximation as PRIMP).
        Optional endpoint conditioning requests foot_dz = h + offset separately
        in every component; its tracking tolerance is not terrain evidence.
        """
        heights = _finite("height support", heights)
        probability = _finite("height probabilities", probabilities)
        if (heights.ndim != 1 or not len(heights) or probability.shape != heights.shape
                or np.any(probability < 0) or probability.sum() <= 0):
            raise ValueError("Height belief requires matching nonempty 1D support and nonnegative weights")
        probability = probability/probability.sum()
        if not np.isfinite(current_phase) or not 0 <= current_phase <= 1:
            raise ValueError("current_phase must lie in [0,1]")
        k, n = self.phase_points, self.phase_points*9
        start = min(int(np.floor(current_phase*(k-1)+1e-9)), k-1)
        height_mean = float(probability@heights)
        height_variance = float(probability@(heights-height_mean)**2)
        ids, values, variances, height_coefficients = [n], [height_mean-self.context_mean[0]], [0.], [1.]
        if duration_s is not None:
            if not np.isfinite(duration_s) or duration_s <= 0 or not np.isfinite(duration_std_s) or duration_std_s <= 0:
                raise ValueError("Duration and its uncertainty must be positive and finite")
            ids.append(n+1)
            values.append(np.log(duration_s)-self.context_mean[1])
            variances.append((duration_std_s/duration_s)**2)
            height_coefficients.append(0.)
        if current_features is None and start == 0:
            current_features = np.zeros(9)
        observations = list(waypoints)
        if current_features is not None:
            if state_std is None:
                state_std = np.array([2e-5]*3+[2e-4]*3+[2e-5]*3)
            observations.append((start, current_features, state_std))
        for index, feature, std in observations:
            if isinstance(index, bool) or int(index) != index or not 0 <= index < k:
                raise ValueError("Waypoint index is outside the learned phase grid")
            index = int(index)
            feature = _finite("waypoint", feature)
            std = np.broadcast_to(_finite("waypoint uncertainty", std), (9,))
            if feature.shape != (9,) or np.any(std <= 0):
                raise ValueError("Waypoint needs nine features and positive uncertainties")
            error = feature-self.mean_features[index]
            error[3:6] = (self._mean_rotations[index].inv()*Rotation.from_rotvec(feature[3:6])).as_rotvec()
            ids.extend(range(index*9, (index+1)*9))
            values.extend(error)
            variances.extend(std**2)
            height_coefficients.extend([0.]*9)
        if foot_endpoint_offset_m is not None:
            if not np.isfinite(foot_endpoint_offset_m) or not np.isfinite(endpoint_std_m) or endpoint_std_m <= 0:
                raise ValueError("Endpoint offset must be finite and tolerance positive")
            ids.append(n-1)
            values.append(height_mean+foot_endpoint_offset_m-self.mean_features[-1, 8])
            variances.append(endpoint_std_m**2)
            height_coefficients.append(1.)
        ids = np.asarray(ids)
        cross = self.covariance[:, ids]
        innovation = self.covariance[np.ix_(ids, ids)]+np.diag(variances)
        factor = cho_factor(innovation, lower=True, check_finite=False)
        gain = cho_solve(factor, cross.T, check_finite=False).T
        local_mean = gain@np.asarray(values)
        height_slope = gain@np.asarray(height_coefficients)
        # Exact-height conditional covariance is independent of h. The second
        # term is Cov_q(E[x|h]), including all body/foot/log-duration cross terms.
        component_covariance = self.covariance-gain@cross.T
        total_covariance = component_covariance+height_variance*np.outer(height_slope, height_slope)
        total_covariance = (total_covariance+total_covariance.T)/2
        local_motion = local_mean[:n].reshape(k, 9)
        result = self.mean_features+local_motion
        result[:, 3:6] = (self._mean_rotations*Rotation.from_rotvec(local_motion[:, 3:6])).as_rotvec()
        log_duration_mean = float(self.context_mean[1]+local_mean[-1])
        component_log_means = log_duration_mean+height_slope[-1]*(heights-height_mean)
        component_log_variance = max(float(component_covariance[-1, -1]), 0.)
        active = probability > 0
        log_weights = np.log(probability[active])
        duration = float(np.exp(logsumexp(log_weights+component_log_means[active]+.5*component_log_variance)))
        second_duration_moment = float(np.exp(logsumexp(log_weights+2*component_log_means[active]+2*component_log_variance)))
        if not np.isfinite(duration) or not np.isfinite(second_duration_moment):
            raise ValueError("Conditioned duration is nonfinite; belief lies outside the model domain")
        output_indices = np.r_[np.arange(start*9, n), n+1]
        covariance = total_covariance[np.ix_(output_indices, output_indices)]
        diagonal = np.maximum(np.diag(covariance), 0.)
        support = self.metadata.get("training_height_range_m", [-np.inf, np.inf])
        unsupported = float(probability[(heights < support[0]) | (heights > support[1])].sum())
        return MotionPrediction(result[start:].copy(), np.linspace(0., 1., k)[start:], duration, start,
            diagonal[:-1].reshape(k-start, 9), float(diagonal[-1]), joint_covariance=covariance,
            log_duration_mean=log_duration_mean, duration_std_s=float(np.sqrt(max(second_duration_moment-duration**2, 0.))),
            mixture_heights=heights.copy(), mixture_weights=probability.copy(), unsupported_probability=unsupported)

    def save(self, path):
        """Save numeric-only model and provenance JSON; return the npz path."""
        path = Path(path)
        if path.suffix != ".npz":
            path = path/"model.npz"
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, mean_features=self.mean_features, context_mean=self.context_mean,
                            covariance=self.covariance, increment_covariance=self.increment_covariance,
                            context_regression=self.context_regression)
        metadata = dict(self.metadata, model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        path.with_suffix(".json").write_text(json.dumps(metadata, indent=2)+"\n")
        return path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.is_dir():
            path = path/"model.npz"
        metadata = json.loads(path.with_suffix(".json").read_text())
        if metadata.get("version") != MODEL_VERSION:
            raise ValueError("Unsupported PRIMP model version")
        if metadata.get("model_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("PRIMP model hash does not match its provenance metadata")
        with np.load(path, allow_pickle=False) as arrays:
            return cls(**{key: arrays[key] for key in ("mean_features", "context_mean", "covariance",
                         "increment_covariance", "context_regression")}, metadata=metadata)
