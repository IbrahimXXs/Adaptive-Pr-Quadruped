"""Matched reference optimization with optional learned motion distributions.

Every variant optimizes the same body XYZ/RPY, foot XYZ, and remaining duration
under identical limits. The predictive variant omits the learned Gaussian prior;
ablations modify only its body/foot covariance or timing terms. Terrain belief
and physical reach determine common goals and positive remaining-time bounds.
"""

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import Bounds, LinearConstraint, minimize
from scipy.spatial.transform import Rotation

from .baselines import support_halfspaces
from .observations import MotionReference


VARIANTS = ("predictive", "learned", "no_body_foot_correlation", "no_timing_adaptation", "no_noncontact_updates")


def _reference_state(reference):
    return np.r_[reference.com_position, reference.body_rpy, reference.foot_position]


def _interpolation_matrix(phase, desired):
    """Linear covariance sampling, including the final log-duration channel."""
    k, n = len(phase), len(desired)
    matrix = np.zeros((n*9+1, k*9+1))
    for row, value in enumerate(desired):
        right = min(int(np.searchsorted(phase, value, side="right")), k-1)
        left = max(0, right-1)
        weight = 0. if left == right else np.clip((value-phase[left])/(phase[right]-phase[left]), 0., 1.)
        matrix[row*9:(row+1)*9, left*9:(left+1)*9] += (1-weight)*np.eye(9)
        matrix[row*9:(row+1)*9, right*9:(right+1)*9] += weight*np.eye(9)
    matrix[-1, -1] = 1.
    return matrix


class MatchedPlanner:
    """One optimizer whose only variant-dependent ingredients are learned priors."""

    def __init__(self, context, model=None, recovery_model=None, variant="predictive", horizon=5):
        if variant not in VARIANTS or horizon < 2:
            raise ValueError("Unknown matched-planner variant or invalid horizon")
        if variant != "predictive" and model is None:
            raise ValueError("Learned matched variants require a fitted motion model")
        self.context, self.model, self.recovery_model = context, model, recovery_model
        self.variant, self.horizon = variant, int(horizon)
        self.accepted = MotionReference(context.start_com_position, np.zeros(3), context.start_body_rpy,
            context.start_foot_position, np.zeros(3), np.zeros(3), context.nominal_duration_s)
        self.proposed_preload_m = self.accepted_preload_m = 0.
        self.optimization_successes = self.optimization_failures = 0
        self.conditioning_updates = 0
        self.last_optimization = {}
        self.fallback_active, self.fallback_reason = False, ""
        self.fallback_count = self.fallback_events = 0
        self.fallback_displacement_m = self.fallback_added_time_s = 0.
        self.fallback_command_distance_m = self.fallback_time_s = 0.
        self.model_remaining_time_s = self.optimized_remaining_time_s = self.feasible_remaining_time_s = context.nominal_duration_s
        self.raw_model_remaining_time_s = context.nominal_duration_s
        self.model_features_active = False
        self.belief_support_mass = 1.
        self.recovery_active = False
        self.planning_anchor_foot_w = np.array(context.start_foot_position, copy=True)
        self.planning_anchor_com_w = np.array(context.start_com_position, copy=True)
        self.planning_current_state_phase = 0.
        self.phase = 0.
        self.duration_s = context.nominal_duration_s
        self._was_fallback = False
        self._prior = None
        self._prior_signature = None
        self._prior_time = -np.inf
        self._scales = np.array([.01]*3+[.02]*3+[.01]*3)

    def accept_reference(self, reference, *, preload_m=None):
        preload = self.proposed_preload_m if preload_m is None else float(preload_m)
        if not np.isfinite(preload) or not 0 <= preload <= self.context.contact_compression_m+1e-12:
            raise ValueError("Accepted preload must lie within its configured allowance")
        self.accepted, self.accepted_preload_m = reference, preload
        self.feasible_remaining_time_s = max(.1, float(reference.remaining_time_s))

    def _accepted_features(self):
        c, a = self.context, self.accepted
        rotation = (Rotation.from_euler("xyz", c.start_body_rpy).inv()*Rotation.from_euler("xyz", a.body_rpy)).as_rotvec()
        features = np.r_[a.com_position-c.start_com_position, rotation, a.foot_position-c.start_foot_position]
        features[8] += self.accepted_preload_m
        return features

    def _learned_prior(self, observation, belief, phase, baseline_time):
        if self.variant == "predictive":
            self.model_features_active = False
            self.model_remaining_time_s = baseline_time
            self.raw_model_remaining_time_s = baseline_time
            self.belief_support_mass = 1.
            return None, ""
        recovery = self.recovery_active
        if recovery and self.recovery_model is None:
            self.model_features_active = False
            self.belief_support_mass = 0.
            self.model_remaining_time_s = baseline_time
            self.raw_model_remaining_time_s = baseline_time
            return None, "recovery_prior_unavailable"
        selected_model = self.recovery_model if recovery else self.model
        heights = np.asarray(belief.heights)-self.context.support_height_estimate
        weights = np.asarray(belief.probability)
        # Recovery origins are current measured state, so refresh each tick.
        # Nominal suffixes refresh at 100 ms or meaningful belief changes.
        signature = (recovery, round(belief.mean/.00025), round(belief.std/.00025), round(phase*40))
        refresh = recovery or self._prior is None or signature != self._prior_signature or observation.time_s-self._prior_time >= .1-1e-9
        if refresh:
            if recovery:
                prediction = selected_model.condition_belief(heights, weights,
                    current_foot_bottom_m=observation.foot_position[2]-self.context.foot_radius-self.context.support_height_estimate)
                origins = (observation.com_position, observation.body_rpy, observation.foot_position)
                start_phase = 0.
            else:
                prediction = selected_model.condition_belief(heights, weights, current_phase=phase,
                    current_features=self._accepted_features(), state_std=np.array([.0005]*3+[.0002]*3+[.0005]*3),
                    foot_endpoint_offset_m=self.context.support_height_estimate+self.context.foot_radius-self.context.start_foot_position[2])
                origins = (self.context.start_com_position, self.context.start_body_rpy, self.context.start_foot_position)
                start_phase = phase
            self._prior = prediction, origins, start_phase
            self._prior_signature, self._prior_time = signature, observation.time_s
            self.conditioning_updates += 1
        prediction, origins, start_phase = self._prior
        self.belief_support_mass = float(np.clip(1-getattr(prediction, "unsupported_probability", 0.), 0., 1.))
        factor = max(.01, 1-start_phase)
        self.raw_model_remaining_time_s = float(prediction.duration_s)*factor
        self.model_remaining_time_s = max(.1, self.raw_model_remaining_time_s)
        sample_phase = start_phase+(1-start_phase)*np.linspace(1/self.horizon, 1., self.horizon)
        features = np.stack([prediction.sample(value)[0] for value in sample_phase])
        mean = features.copy()
        mean[:, :3] += origins[0]
        mean[:, 3:6] = (Rotation.from_euler("xyz", origins[1])*Rotation.from_rotvec(features[:, 3:6])).as_euler("xyz")
        mean[:, 6:9] += origins[2]
        mean[:, 8] -= self.context.contact_compression_m
        sampling = _interpolation_matrix(np.asarray(prediction.phase), sample_phase)
        covariance = sampling@np.asarray(prediction.joint_covariance)@sampling.T
        log_time = float(getattr(prediction, "log_duration_mean", np.log(prediction.duration_s)))+np.log(factor)
        if self.variant == "no_body_foot_correlation":
            body = np.array([9*i+j for i in range(self.horizon) for j in range(6)])
            foot = np.array([9*i+j for i in range(self.horizon) for j in range(6, 9)])
            # Remove DIRECT body/foot correlation conditional on log time.
            # The correlation mediated by timing remains; all three marginal
            # distributions remain unchanged and positive semidefiniteness is
            # preserved by block-diagonalizing the conditional covariance.
            mediated = np.outer(covariance[body, -1], covariance[-1, foot])/max(covariance[-1, -1], 1e-15)
            covariance[np.ix_(body, foot)] = mediated
            covariance[np.ix_(foot, body)] = mediated.T
        if self.variant == "no_timing_adaptation":
            covariance[-1, :-1] = covariance[:-1, -1] = 0.
            log_time = np.log(baseline_time)
            covariance[-1, -1] = .25
        self.model_features_active = self.belief_support_mass >= .5
        return (mean, covariance, log_time), "prior_out_of_support" if self.belief_support_mass < .5 else ""

    def _record_fallback(self, reason, reference, prior_time):
        self.fallback_active, self.fallback_reason = bool(reason), reason
        self.fallback_displacement_m = self.fallback_added_time_s = 0.
        if reason:
            self.fallback_count += 1
            self.fallback_events += int(not self._was_fallback)
            self.fallback_displacement_m = float(np.linalg.norm(reference.foot_position-self.accepted.foot_position))
            self.fallback_added_time_s = max(0., reference.remaining_time_s-prior_time)
            self.fallback_command_distance_m += self.fallback_displacement_m
            self.fallback_time_s += self.context.planning_dt
        self._was_fallback = bool(reason)

    def plan(self, observation, belief):
        c, n = self.context, self.horizon
        self.planning_anchor_foot_w = np.array(observation.foot_position, copy=True)
        self.planning_anchor_com_w = np.array(observation.com_position, copy=True)
        # A light or transient touch can clear the belief's missing flag before
        # support is confirmed. Keep the current-state recovery model active for
        # the remainder of this landing; the executor owns the completion gate.
        self.recovery_active = self.recovery_active or bool(belief.missing_contact)
        q0 = _reference_state(self.accepted)
        loaded = bool(observation.contacts[0] and observation.normal_forces[0] >= 2.)
        speed = min(c.max_foot_speed, c.search_speed) if self.recovery_active else c.max_foot_speed
        physical_goal = float(belief.quantile(.25))+c.foot_radius
        goal_z = max(c.minimum_foot_z, min(q0[8], physical_goal-c.contact_compression_m))
        reason = ""
        if not loaded and goal_z >= q0[8]-.0001:
            goal_z = max(c.minimum_foot_z, q0[8]-c.search_speed*.5)
            reason = "bounded_search_beyond_belief_target"
        physical_gap = max(0., observation.foot_position[2]-physical_goal+c.contact_compression_m)
        minimum_time = max(.15, physical_gap/max(speed, .001), (q0[8]-goal_z)/max(speed, .001))
        elapsed = max(0., observation.time_s-c.start_time_s)
        baseline_time = max(minimum_time, c.nominal_duration_s-elapsed)
        max_time = max(minimum_time+.2, min(8., c.nominal_duration_s+8-elapsed))
        denominator = max(.005, c.start_foot_position[2]-(belief.mean+c.foot_radius))
        self.phase = float(np.clip((c.start_foot_position[2]-observation.foot_position[2])/denominator, 0., .95))
        self.planning_current_state_phase = self.phase
        prior, prior_reason = self._learned_prior(observation, belief, self.phase, baseline_time)
        reason = reason or prior_reason
        body_goal = np.array(c.start_com_position, copy=True)
        height = np.clip(belief.mean-c.support_height_estimate, -.02, .02)
        body_goal += np.array([.1*height, 0., .3*height])
        body_goal[:2] += .25*(observation.support_anchors[:, :2].mean(axis=0)-observation.com_position[:2])
        endpoint = np.r_[body_goal, c.start_body_rpy, c.target_xy, goal_z]
        fractions = np.linspace(1/n, 1., n)
        conventional = q0+fractions[:, None]*(endpoint-q0)
        goal = (conventional-q0)/self._scales
        weights = np.array([3., 3., 5., .5, .5, .5, 4., 4., 12.])
        difference = np.eye(n)-np.eye(n, k=-1)
        acceleration = difference@difference
        prior_mean = precision = None
        if prior is not None and self.model_features_active:
            mean, covariance, log_time = prior
            full_scale = np.r_[np.tile(self._scales, n), 1.]
            covariance = covariance/full_scale[:, None]/full_scale[None, :]
            floor = np.r_[np.tile(np.array([.0008]*3+[.002]*3+[.001]*3)/self._scales, n), .08]
            covariance += np.diag(floor**2)
            covariance = (covariance+covariance.T)/2
            precision = cho_solve(cho_factor(covariance, lower=True), np.eye(len(covariance)))
            prior_mean = np.r_[((mean-q0)/self._scales).ravel(), log_time]

        def objective(z):
            x, duration = z[:-1].reshape(n, 9), z[-1]
            error, smooth = x-goal, acceleration@x
            timing = np.log(duration/baseline_time)
            value = np.sum(weights*error**2)+.04*np.sum(smooth**2)+timing**2+.02*duration
            gradient = np.r_[(2*weights*error+.08*acceleration.T@smooth).ravel(), 2*timing/duration+.02]
            if precision is not None:
                residual = np.r_[x.ravel(), np.log(duration)]-prior_mean
                derivative = precision@residual
                strength = .03*self.belief_support_mass
                value += strength*float(residual@derivative)
                gradient[:-1] += 2*strength*derivative[:-1]
                if self.variant != "no_timing_adaptation":
                    gradient[-1] += 2*strength*derivative[-1]/duration
                else:
                    # Remove the learned time term altogether, including the
                    # constant-time residual in the objective used by SLSQP.
                    value -= strength*residual[-1]*derivative[-1]
            return float(value), gradient

        lower = np.r_[c.start_com_position-c.max_body_displacement,
                      c.start_body_rpy-np.deg2rad(2.), c.target_xy-.005, c.minimum_foot_z]
        upper = np.r_[c.start_com_position+c.max_body_displacement,
                      c.start_body_rpy+np.deg2rad(2.), c.target_xy+.005, c.start_foot_position[2]+.002]
        bounds = Bounds(np.r_[np.tile((lower-q0)/self._scales, n), minimum_time],
                        np.r_[np.tile((upper-q0)/self._scales, n), max_time])
        normals, offsets = support_halfspaces(observation.support_anchors, c.support_margin)
        matrix, low, high = [], [], []
        for i in range(n):
            for normal, offset in zip(normals, offsets):
                row = np.zeros(n*9+1); row[i*9:i*9+2] = normal*self._scales[:2]
                matrix.append(row); low.append(offset-normal@q0[:2]); high.append(np.inf)
            row = np.zeros(n*9+1); row[i*9+8] = self._scales[8]
            if i: row[(i-1)*9+8] = -self._scales[8]
            matrix.append(row); low.append(-np.inf); high.append(0.)
            for component in range(3, 6):
                for sign in (-1., 1.):
                    row = np.zeros(n*9+1); row[i*9+component] = sign*self._scales[component]
                    if i: row[(i-1)*9+component] = -sign*self._scales[component]
                    row[-1] = -.02/n
                    matrix.append(row); low.append(-np.inf); high.append(0.)
        terminal = np.zeros(n*9+1); terminal[(n-1)*9+8] = self._scales[8]
        matrix.append(terminal); low.append(-np.inf); high.append(goal_z-q0[8])
        linear = LinearConstraint(np.asarray(matrix), np.asarray(low), np.asarray(high))

        def speed_constraints(z):
            x, duration = z[:-1].reshape(n, 9), z[-1]
            delta = difference@x*self._scales
            values, jacobian = [], []
            for i in range(n):
                for components, limit in ((slice(0, 3), c.max_com_speed), (slice(6, 9), speed)):
                    vector = delta[i, components]
                    length = np.linalg.norm(vector)
                    values.append((limit*duration/n-length)/.01)
                    row = np.zeros(n*9+1)
                    unit = vector/max(length, 1e-12)*self._scales[components]/.01
                    indexes = np.arange(9)[components]
                    row[i*9+indexes] = -unit
                    if i: row[(i-1)*9+indexes] = unit
                    row[-1] = limit/n/.01
                    jacobian.append(row)
            return np.asarray(values), np.asarray(jacobian)

        initial_time = float(np.clip(self.model_remaining_time_s if precision is not None and self.variant != "no_timing_adaptation" else baseline_time, minimum_time, max_time))
        initial = np.r_[goal.ravel(), initial_time]
        initial = np.clip(initial, bounds.lb, bounds.ub)
        solution = minimize(objective, initial, jac=True, method="SLSQP", bounds=bounds,
            constraints=[linear, {"type":"ineq", "fun":lambda z:speed_constraints(z)[0], "jac":lambda z:speed_constraints(z)[1]}],
            options={"maxiter":70, "ftol":1e-7, "disp":False})
        linear_value = linear.A@solution.x
        violation = max(0., float(np.max(linear.lb-linear_value)), float(np.max(linear_value-linear.ub)),
                        -float(np.min(speed_constraints(solution.x)[0])))
        success = bool(solution.success and violation < 1e-5)
        self.last_optimization = dict(success=success, iterations=int(solution.nit), constraint_violation=violation,
            horizon=n, variables=n*9+1, objective=float(solution.fun), variant=self.variant,
            learned_prior_active=bool(precision is not None), message=str(solution.message))
        if success:
            self.optimization_successes += 1
            duration = float(solution.x[-1])
            first = q0+solution.x[:9]*self._scales
            velocity = (first-q0)/(duration/n)
            next_state = q0+velocity*c.planning_dt
        else:
            self.optimization_failures += 1
            reason = "optimizer_failure"
            duration = baseline_time
            velocity = np.zeros(9)
            velocity[8] = -min(speed, max(0., q0[8]-c.minimum_foot_z)/c.planning_dt)
            next_state = q0+velocity*c.planning_dt
        if loaded:
            next_state, velocity = q0.copy(), np.zeros(9)
        self.optimized_remaining_time_s = max(.1, duration)
        self.feasible_remaining_time_s = max(.1, duration, minimum_time)
        self.duration_s = self.feasible_remaining_time_s
        self.proposed_preload_m = c.contact_compression_m
        reference = MotionReference(next_state[:3], velocity[:3], next_state[3:6], next_state[6:9],
            velocity[6:9], np.zeros(3), self.feasible_remaining_time_s)
        self._record_fallback(reason, reference, self.model_remaining_time_s)
        return reference
