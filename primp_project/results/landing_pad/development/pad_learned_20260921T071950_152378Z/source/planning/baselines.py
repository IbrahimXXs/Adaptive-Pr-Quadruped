"""Coordinated reactive, predictive, and learned landing references.

All planners consume only sensor observations and the same height belief. They
return the next planning tick's reference. The executor applies the shared
projector and interpolates between successive references at its control rate.
"""

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize
from scipy.spatial.transform import Rotation

from .observations import MotionReference


def support_halfspaces(anchors, margin):
    vertices = np.asarray(anchors)[:, :2]
    center = vertices.mean(axis=0)
    vertices = vertices[np.argsort(np.arctan2(vertices[:, 1]-center[1], vertices[:, 0]-center[0]))]
    edges = np.roll(vertices, -1, axis=0)-vertices
    lengths = np.linalg.norm(edges, axis=1)
    if np.any(lengths < 1e-8):
        raise ValueError("Support anchors must form a nondegenerate triangle")
    inward = np.column_stack((-edges[:, 1], edges[:, 0])) / lengths[:, None]
    offsets = np.einsum("ij,ij->i", inward, vertices)+margin
    side_a, side_b = vertices[1]-vertices[0], vertices[2]-vertices[0]
    if side_a[0]*side_b[1]-side_a[1]*side_b[0] < 1e-8:
        raise ValueError("Support anchors must form a nondegenerate triangle")
    return inward, offsets


class FeasibilityProjector:
    """Common geometric/rate limits, without access to actual terrain height."""

    def __init__(self, context):
        self.context = context
        self.previous = MotionReference(context.start_com_position, np.zeros(3),
                                        context.start_body_rpy, context.start_foot_position,
                                        np.zeros(3), np.zeros(3), context.nominal_duration_s)
        self.clipped_references = 0

    def project(self, reference, observation, dt=None):
        c = self.context
        dt = c.planning_dt if dt is None else float(dt)
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("Projection time step must be positive")
        prior = self.previous
        foot = np.array(reference.foot_position, copy=True)
        # Permit only the already selected landing location, with a bounded
        # residual XY correction; no planner can silently choose another pad.
        foot[:2] = np.clip(foot[:2], c.target_xy-.005, c.target_xy+.005)
        foot[2] = np.clip(foot[2], c.minimum_foot_z, c.start_foot_position[2]+.002)
        # This executor performs one lowering action. Belief changes must not
        # lift a lightly touching foot before the common loading gate succeeds.
        foot[2] = min(foot[2], prior.foot_position[2])
        foot_limit = c.max_foot_speed
        if (observation.foot_position[2]-c.foot_radius <= c.initial_height_estimate+.0005
                and not observation.contacts[0]):
            foot_limit = min(foot_limit, c.search_speed)
        delta = foot-prior.foot_position
        max_step = foot_limit*dt
        distance = np.linalg.norm(delta)
        if distance > max_step:
            delta *= max_step/distance
        foot = prior.foot_position+delta
        foot_velocity = delta/dt
        com = np.clip(reference.com_position, c.start_com_position-c.max_body_displacement,
                      c.start_com_position+c.max_body_displacement)
        com_delta = com-prior.com_position
        com_distance = np.linalg.norm(com_delta)
        if com_distance > c.max_com_speed*dt:
            com_delta *= c.max_com_speed*dt/com_distance
        com = prior.com_position+com_delta
        normals, offsets = support_halfspaces(observation.support_anchors, c.support_margin)
        # Projection onto the 3 halfspaces; the small requested displacement
        # keeps this near the strictly feasible starting tripod reference.
        for _ in range(20):
            errors = offsets-normals@com[:2]
            if errors.max() <= 1e-9:
                break
            edge = int(np.argmax(errors))
            com[:2] += errors[edge]*normals[edge]
        if np.min(normals@com[:2]-offsets) < -1e-7:
            raise ValueError("Requested support margin is infeasible")
        com_velocity = (com-prior.com_position)/dt
        rpy = np.clip(reference.body_rpy, c.start_body_rpy-np.deg2rad(2), c.start_body_rpy+np.deg2rad(2))
        rpy = prior.body_rpy + np.clip(rpy-prior.body_rpy, -.02*dt, .02*dt)
        acceleration = (foot_velocity-prior.foot_velocity)/dt
        result = MotionReference(com, com_velocity, rpy, foot, foot_velocity,
                                 acceleration, reference.remaining_time_s)
        if (np.linalg.norm(result.foot_position-reference.foot_position) > 1e-8
                or np.linalg.norm(result.com_position-reference.com_position) > 1e-8
                or np.linalg.norm(result.body_rpy-reference.body_rpy) > 1e-8):
            self.clipped_references += 1
        self.previous = result
        return result


class ReactivePlanner:
    """Contact-triggered slow search with coordinated body and timing changes."""

    def __init__(self, context):
        self.context = context
        self.last_time = context.start_time_s
        self.foot = np.array(context.start_foot_position, copy=True)
        self.com = np.array(context.start_com_position, copy=True)
        self.fallback_count = 0

    def plan(self, observation, belief):
        c = self.context
        dt = c.planning_dt
        nominal_speed = min(c.max_foot_speed, max(.002, (c.start_foot_position[2]-c.initial_height_estimate-c.foot_radius+c.contact_compression_m)/c.nominal_duration_s))
        speed = min(nominal_speed, c.search_speed) if belief.missing_contact else nominal_speed
        old_foot = self.foot.copy()
        old_com = self.com.copy()
        self.foot[:2] = c.target_xy
        if not (observation.contacts[0] and observation.normal_forces[0] >= 2.):
            self.foot[2] = max(c.minimum_foot_z, self.foot[2]-speed*dt)
        # During a deeper search, lowering the body preserves leg extension;
        # moving toward the support centroid restores margin after disturbance.
        adjustment = np.clip(belief.mean-c.support_height_estimate, -.02, .02)
        self.com = np.array(c.start_com_position, copy=True)
        self.com[2] += .3*adjustment
        centroid = observation.support_anchors[:, :2].mean(axis=0)
        self.com[:2] += .25*(centroid-observation.com_position[:2])
        self.com[0] += .1*adjustment
        remaining = max(0., (self.foot[2]-belief.mean-c.foot_radius+c.contact_compression_m)/max(speed, .001))
        self.last_time = observation.time_s
        return MotionReference(self.com, (self.com-old_com)/dt, c.start_body_rpy,
                               self.foot, (self.foot-old_foot)/dt, np.zeros(3), remaining)


class ConventionalPredictivePlanner:
    """Finite-horizon constrained quadratic reference optimization.

    Eight future body XYZ / foot-Z positions are optimized jointly. Constraints
    enforce tripod margin, reach, bounded body speed, and monotone bounded foot
    descent. Costs couple body height to leg extension and penalize acceleration.
    The first optimized action is executed; remaining landing time follows from
    the optimized descent speed and the same sensor-derived height posterior.
    This reference planner is separate from the shared low-level centroidal MPC.
    """

    def __init__(self, context, horizon=8, prediction_dt=.2):
        if horizon < 2 or prediction_dt <= 0:
            raise ValueError("Predictive horizon must contain at least two positive intervals")
        self.context = context
        self.horizon = int(horizon)
        self.prediction_dt = float(prediction_dt)
        self.previous = np.r_[context.start_com_position, context.start_foot_position[2]]
        self.previous_velocity = np.zeros(4)
        self.optimization_successes = 0
        self.optimization_failures = 0
        self.last_optimization = {}
        self.fallback_count = 0
        self._fallback = ReactivePlanner(context)

    def plan(self, observation, belief):
        c, n, dt = self.context, self.horizon, self.prediction_dt
        previous = self.previous.copy()
        nominal_speed = min(c.max_foot_speed, max(.002, (c.start_foot_position[2]-c.initial_height_estimate-c.foot_radius+c.contact_compression_m)/c.nominal_duration_s))
        speed = min(nominal_speed, c.search_speed) if belief.missing_contact else nominal_speed
        if observation.contacts[0] and observation.normal_forces[0] >= 2.:
            speed = 0.
        # A small preload displacement permits measurable contact; an unseen
        # surface may only be sought within the common bounded descent region.
        goal_z = max(c.minimum_foot_z, belief.quantile(.25)+c.foot_radius-c.contact_compression_m)
        body_goal = np.array(c.start_com_position, copy=True)
        height_delta = np.clip(belief.mean-c.support_height_estimate, -.02, .02)
        body_goal[2] += .3*height_delta
        body_goal[0] += .1*height_delta
        body_goal[:2] += .25*(observation.support_anchors[:, :2].mean(axis=0)-observation.com_position[:2])
        goal = np.tile(np.r_[body_goal, goal_z], (n, 1))
        goal[:, 3] = np.maximum(goal_z, previous[3]-speed*dt*np.arange(1, n+1))
        # Optimize offsets in centimetres for a well-scaled small dense QP.
        scale = .01
        goal_scaled = (goal-previous)/scale
        weights = np.array([3., 3., 5., 12.])
        diff = np.eye(n)-np.eye(n, k=-1)
        accel = diff@diff
        initial_velocity = self.previous_velocity*dt/scale

        def objective(flat):
            x = flat.reshape(n, 4)
            error = x-goal_scaled
            smooth = accel@x
            smooth[0] -= initial_velocity
            # Body/foot coordination is optimized, not applied after the solve.
            leg = x[:, 2]-.3*x[:, 3]-(goal_scaled[:, 2]-.3*goal_scaled[:, 3])
            cost = np.sum(weights*error**2)+.1*np.sum(smooth**2)+2*np.sum(leg**2)
            gradient = 2*weights*error+.2*accel.T@smooth
            gradient[:, 2] += 4*leg
            gradient[:, 3] -= 1.2*leg
            return float(cost), gradient.ravel()

        lower_pos = np.r_[c.start_com_position-c.max_body_displacement, c.minimum_foot_z]
        upper_pos = np.r_[c.start_com_position+c.max_body_displacement, c.start_foot_position[2]+.002]
        bounds = Bounds(np.tile((lower_pos-previous)/scale, n), np.tile((upper_pos-previous)/scale, n))
        transition = np.kron(diff, np.eye(4))
        vmax = np.r_[np.full(3, c.max_com_speed), speed]*dt/scale
        vlo = -vmax
        vhi = vmax.copy()
        vhi[3] = 0.
        normals, offsets = support_halfspaces(observation.support_anchors, c.support_margin)
        polygon = np.zeros((3*n, 4*n))
        for i in range(n):
            polygon[3*i:3*i+3, 4*i:4*i+2] = normals
        matrix = np.vstack((transition, polygon))
        lower = np.r_[np.tile(vlo, n), np.tile((offsets-normals@previous[:2])/scale, n)]
        upper = np.r_[np.tile(vhi, n), np.full(3*n, np.inf)]
        initial = np.clip(goal_scaled, (lower_pos-previous)/scale, (upper_pos-previous)/scale).ravel()
        result = minimize(objective, initial, jac=True, method="SLSQP", bounds=bounds,
                          constraints=LinearConstraint(matrix, lower, upper),
                          options={"maxiter": 60, "ftol": 1e-8, "disp": False})
        residual = max(float(np.max(lower-matrix@result.x)), float(np.max(matrix@result.x-upper)))
        self.last_optimization = dict(success=bool(result.success and residual < 1e-5),
                                      iterations=int(result.nit), constraint_violation=max(0., residual),
                                      horizon=n, prediction_dt=dt, objective=float(result.fun))
        if not self.last_optimization["success"]:
            self.optimization_failures += 1
            self.fallback_count += 1
            self._fallback.foot = np.r_[c.target_xy, previous[3]]
            fallback = self._fallback.plan(observation, belief)
            self.previous = np.r_[fallback.com_position, fallback.foot_position[2]]
            self.previous_velocity = np.r_[fallback.com_velocity, fallback.foot_velocity[2]]
            return fallback
        self.optimization_successes += 1
        horizon_positions = previous+scale*result.x.reshape(n, 4)
        velocity = (horizon_positions[0]-previous)/dt
        next_position = previous+velocity*c.planning_dt
        self.previous = next_position
        self.previous_velocity = velocity
        remaining = max(0., (next_position[3]-belief.mean-c.foot_radius+c.contact_compression_m)/max(-velocity[3], .001))
        return MotionReference(next_position[:3], velocity[:3], c.start_body_rpy,
                               np.r_[c.target_xy, next_position[3]], np.array([0., 0., velocity[3]]),
                               np.zeros(3), remaining)


class LearnedMotionPlanner:
    """Adapt a learned PRIMP motion using the shared posterior and sensors."""

    def __init__(self, context, model):
        self.context = context
        self.model = model
        self.phase = 0.
        self.duration_s = context.nominal_duration_s
        self.fallback_count = 0
        self.last_prediction = None
        self.conditioning_updates = 0
        self._conditioned_belief = None
        self._conditioned_time = -np.inf
        self._recovery_foot_z = None
        self._last_foot_z = None

    def plan(self, observation, belief):
        c = self.context
        relative_rotation = (Rotation.from_euler("xyz", c.start_body_rpy).inv()
                             * Rotation.from_euler("xyz", observation.body_rpy)).as_rotvec()
        measured = np.r_[observation.com_position-c.start_com_position,
                         relative_rotation, observation.foot_position-c.start_foot_position]
        belief_state = (belief.mean, belief.std, belief.missing_contact, belief.contact_observed)
        changed = (self._conditioned_belief is None
                   or abs(belief_state[0]-self._conditioned_belief[0]) >= .0005
                   or abs(belief_state[1]-self._conditioned_belief[1]) >= .0005
                   or belief_state[2:] != self._conditioned_belief[2:])
        # Re-anchoring a zero-slope suffix at every tick would erase the learned
        # velocity repeatedly. Retain the conditioned motion between meaningful
        # sensor-belief changes and let its phase advance continuously.
        if self.last_prediction is None or (changed and observation.time_s-self._conditioned_time >= .1-1e-9):
            self.last_prediction = self.model.condition(
                height_mean=belief.mean-c.support_height_estimate, height_std=belief.std,
                current_phase=self.phase, current_features=measured,
                # The model's 20 micrometre covariance regularizer describes
                # numerical fit uncertainty, not measurement accuracy. Use the
                # same conservative 0.5 mm observation floor for every sensing
                # condition, covering the bounded noisy profile without giving
                # clean evaluation a different estimator tuning. Orientation
                # sensing is unperturbed; retain the 0.2 mrad rotation floor.
                state_std=np.array([.0005]*3+[.0002]*3+[.0005]*3),
            )
            self._conditioned_belief = belief_state
            self._conditioned_time = observation.time_s
            self.conditioning_updates += 1
        prediction = self.last_prediction
        self.duration_s = max(float(prediction.duration_s), c.planning_dt)
        next_phase = min(1., self.phase+c.planning_dt/self.duration_s)
        target, derivative, second_derivative = prediction.sample(next_phase)
        velocity = derivative/self.duration_s
        acceleration = second_derivative/self.duration_s**2
        self.phase = next_phase
        rpy = (Rotation.from_euler("xyz", c.start_body_rpy)*Rotation.from_rotvec(target[3:6])).as_euler("xyz")
        foot = c.start_foot_position+target[6:9]
        com = c.start_com_position+target[:3]
        # The learned channels are measured motion, whereas Cartesian impedance
        # needs a small virtual penetration to produce a measurable support
        # load. This shared servo allowance is not a learned terrain correction.
        preload_phase = np.clip((next_phase-.7)/.3, 0., 1.)
        preload = 10*preload_phase**3-15*preload_phase**4+6*preload_phase**5
        preload_rate = (30*preload_phase**2-60*preload_phase**3+30*preload_phase**4)/(.3*self.duration_s)
        preload_acc = (60*preload_phase-180*preload_phase**2+120*preload_phase**3)/(.3*self.duration_s)**2
        foot[2] -= c.contact_compression_m*preload
        velocity[8] -= c.contact_compression_m*preload_rate
        acceleration[8] -= c.contact_compression_m*preload_acc
        # The distribution is finite. If its endpoint was reached without
        # contact, the common bounded recovery remains available and is counted.
        loaded_contact = bool(observation.contacts[0] and observation.normal_forces[0] >= 2.)
        if next_phase >= 1.-1e-9 and not loaded_contact:
            self.fallback_count += 1
            if self._recovery_foot_z is None:
                self._recovery_foot_z = min(foot[2], self._last_foot_z if self._last_foot_z is not None else foot[2])
            # Integrate the commanded descent, not a tiny offset from measured
            # position; the latter can stall with a weak spring/contact load.
            self._recovery_foot_z = max(c.minimum_foot_z, self._recovery_foot_z-c.search_speed*c.planning_dt)
            foot[2] = max(c.minimum_foot_z, min(foot[2], self._recovery_foot_z))
            velocity[8] = -c.search_speed
        self._last_foot_z = float(foot[2])
        return MotionReference(com, velocity[:3], rpy, foot, velocity[6:9], acceleration[6:9],
                               max(0., (1.-self.phase)*self.duration_s))
