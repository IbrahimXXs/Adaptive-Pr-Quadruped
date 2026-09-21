"""Measured-load certificates and quasi-static planning for a weak foothold.

Only sensor values, robot geometry and declared robot/sensing limits enter this
module. A certificate is a demonstrated lower bound, not an estimate of the
unknown failure threshold. The vertical-force model checks gravity and roll/
pitch moment balance; execution still needs the existing whole-body controller.
"""
from collections import deque
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, minimize

from .baselines import support_halfspaces
from .observations import immutable_array


LEGS = ('FL', 'FR', 'RL', 'RR')


@dataclass(frozen=True)
class LoadObservation:
    """Actual applied normal force and measured foothold motion, never a request."""
    time_s: float
    normal_force_n: float
    contact: bool
    foot_position_w: np.ndarray
    foot_velocity_w: np.ndarray
    surface_position_w: np.ndarray | None = None

    def __post_init__(self):
        if not np.isfinite(self.time_s) or not np.isfinite(self.normal_force_n) or self.normal_force_n < 0:
            raise ValueError('Observation time/force must be finite and force nonnegative')
        for name in ('foot_position_w', 'foot_velocity_w'):
            object.__setattr__(self, name, immutable_array(getattr(self, name), (3,)))
        if self.surface_position_w is not None:
            object.__setattr__(self, 'surface_position_w', immutable_array(self.surface_position_w, (3,)))


@dataclass(frozen=True)
class CertificateConfig:
    dwell_s: float = .6
    maximum_sample_gap_s: float = .02
    measurement_margin_n: float = .3
    tracking_margin_n: float = 2.
    plateau_range_n: float = 1.5
    maximum_foot_motion_m: float = .001
    maximum_surface_motion_m: float = .001
    maximum_foot_speed_m_s: float = .005
    invalidation_motion_m: float = .0025
    invalidation_horizontal_motion_m: float = .01

    def __post_init__(self):
        values = np.array(list(self.__dict__.values()), dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values <= 0):
            raise ValueError('Certificate sensing and stability limits must be positive and finite')


@dataclass(frozen=True)
class LoadCertificate:
    valid: bool = False
    certified_load_n: float = 0.
    force_cap_n: float = 0.
    measured_min_force_n: float = 0.
    evidence_start_s: float | None = None
    evidence_end_s: float | None = None
    dwell_s: float = 0.
    foot_motion_m: float = 0.
    surface_motion_m: float = 0.
    measurement_margin_n: float = .3
    tracking_margin_n: float = 2.
    revision: int = 0
    invalidation_reason: str = 'no_demonstrated_plateau'


class DemonstratedLoadCertificate:
    """Accumulate contiguous stable applied-load plateaus on one fixed foothold.

    A certificate may increase only from a whole measured dwell window. Its
    cap reserves both sensing error and future tracking overshoot. Losing the
    contact or vertically moving the tested foothold invalidates it. Small
    horizontal foot rolling is permitted only under the explicit assumption
    that normal-load strength is uniform inside the configured local radius.
    """

    def __init__(self, config=CertificateConfig()):
        self.config = config
        self.certificate = LoadCertificate(measurement_margin_n=config.measurement_margin_n,
            tracking_margin_n=config.tracking_margin_n)
        self.samples = deque()
        self.last_time_s = -np.inf
        self.invalidated_contact = False
        self.certified_foot_position_w = None
        self.certified_surface_position_w = None

    def invalidate(self, reason):
        self.invalidated_contact |= self.certificate.valid
        self.samples.clear()
        self.certified_foot_position_w = self.certified_surface_position_w = None
        self.certificate = LoadCertificate(measurement_margin_n=self.config.measurement_margin_n,
            tracking_margin_n=self.config.tracking_margin_n,
            revision=self.certificate.revision+int(self.certificate.valid), invalidation_reason=str(reason))
        return self.certificate

    def reset(self):
        """Explicitly begin a new foothold assessment after leaving this one."""
        self.__init__(self.config)
        return self.certificate

    def update(self, observation, *, allow_increase=True):
        """Validate the site continuously; accrue proof only in designated tests.

        ``allow_increase=False`` monitors contact and tested-position validity
        without upgrading capacity from ordinary execution or preserving a
        partial evidence window across an unobserved probe interruption.
        """
        c = self.config
        if observation.time_s < self.last_time_s-1e-12:
            raise ValueError('Load observations must have monotonically increasing timestamps')
        if observation.time_s <= self.last_time_s+1e-12:
            return self.certificate
        gap = observation.time_s-self.last_time_s
        self.last_time_s = observation.time_s
        if self.invalidated_contact:
            return self.certificate
        if not observation.contact:
            return self.invalidate('lost_contact')
        if self.certified_foot_position_w is not None:
            movement = observation.foot_position_w-self.certified_foot_position_w
            moved = (abs(movement[2]) > c.invalidation_motion_m
                     or np.linalg.norm(movement[:2]) > c.invalidation_horizontal_motion_m)
            if observation.surface_position_w is not None and self.certified_surface_position_w is not None:
                moved |= np.linalg.norm(observation.surface_position_w-self.certified_surface_position_w) > c.invalidation_motion_m
            if moved:
                return self.invalidate('tested_foothold_moved')
        if not allow_increase:
            self.samples.clear()
            return self.certificate
        if gap > c.maximum_sample_gap_s+1e-12:
            self.samples.clear()
        self.samples.append(observation)
        # Retain the boundary sample needed to demonstrate at least a full dwell.
        cutoff = observation.time_s-c.dwell_s
        while len(self.samples) > 1 and self.samples[1].time_s <= cutoff+1e-12:
            self.samples.popleft()
        if observation.time_s-self.samples[0].time_s < c.dwell_s-1e-10:
            return self.certificate
        force = np.array([sample.normal_force_n for sample in self.samples])
        feet = np.stack([sample.foot_position_w for sample in self.samples])
        speed = max(np.linalg.norm(sample.foot_velocity_w) for sample in self.samples)
        foot_motion = float(np.max(np.linalg.norm(feet-feet[0], axis=1)))
        surfaces = [sample.surface_position_w for sample in self.samples]
        surface_available = all(value is not None for value in surfaces)
        surface_consistent = surface_available or all(value is None for value in surfaces)
        surface_motion = float(np.max(np.linalg.norm(np.stack(surfaces)-surfaces[0], axis=1))) if surface_available else 0.
        stable = (np.ptp(force) <= c.plateau_range_n and speed <= c.maximum_foot_speed_m_s
                  and foot_motion <= c.maximum_foot_motion_m and surface_motion <= c.maximum_surface_motion_m
                  and surface_consistent)
        certified = max(0., float(force.min())-c.measurement_margin_n)
        cap = max(0., certified-c.tracking_margin_n)
        if not stable or cap <= 0 or certified <= self.certificate.certified_load_n+1e-10:
            return self.certificate
        self.certificate = LoadCertificate(True, certified, cap, float(force.min()),
            float(self.samples[0].time_s), float(observation.time_s), float(observation.time_s-self.samples[0].time_s),
            foot_motion, surface_motion, c.measurement_margin_n, c.tracking_margin_n,
            self.certificate.revision+1, '')
        self.certified_foot_position_w = observation.foot_position_w.copy()
        self.certified_surface_position_w = observation.surface_position_w.copy() if surface_available else None
        return self.certificate


@dataclass(frozen=True)
class ForceAllocation:
    feasible: bool
    forces_n: np.ndarray
    com_position_w: np.ndarray
    support_margin_m: float
    reason: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'forces_n', immutable_array(self.forces_n, (4,)))
        object.__setattr__(self, 'com_position_w', immutable_array(self.com_position_w, (3,)))


def _force_problem(anchors_w, weight_n, lower_n, upper_n, extra_matrix=None, extra_upper=None):
    anchors = immutable_array(anchors_w, (4, 3))
    lower, upper = immutable_array(lower_n, (4,)), immutable_array(upper_n, (4,))
    if weight_n <= 0 or not np.isfinite(weight_n) or np.any(lower < 0) or np.any(upper < lower):
        raise ValueError('Weight and ordered force bounds must be physical')
    aeq = np.vstack([np.ones(4), anchors[:, :2].T])
    if extra_matrix is None:
        aub, bub = None, None
    else:
        aub, bub = np.asarray(extra_matrix, float), np.asarray(extra_upper, float)
        if aub.ndim != 2 or aub.shape[1] != 4 or bub.shape != (len(aub),) or not np.all(np.isfinite(aub)) or not np.all(np.isfinite(bub)):
            raise ValueError('Additional calibrated force/torque inequalities must have shapes (K,4), (K,)')
    return anchors, lower, upper, aeq, aub, bub


def solve_load_allocation(anchors_w, weight_n, com_position_w, lower_n, upper_n,
                          *, maximize_leg=None, extra_matrix=None, extra_upper=None):
    """LP with exact sum(F), sum(xF), sum(yF) equilibrium and optional limits."""
    anchors, lower, upper, aeq, aub, bub = _force_problem(anchors_w, weight_n, lower_n, upper_n, extra_matrix, extra_upper)
    com = immutable_array(com_position_w, (3,))
    objective = np.zeros(4)
    if maximize_leg is not None:
        objective[int(maximize_leg)] = -1.
    result = linprog(objective, A_ub=aub, b_ub=bub, A_eq=aeq,
                     b_eq=weight_n*np.r_[1., com[:2]], bounds=list(zip(lower, upper)), method='highs')
    active = upper > 1e-10
    margin = 0.
    if np.count_nonzero(active) == 3:
        normals, offsets = support_halfspaces(anchors[active], 0.)
        margin = float(np.min(normals@com[:2]-offsets))
    return ForceAllocation(bool(result.success), result.x if result.success else np.zeros(4), com, margin,
                           '' if result.success else str(result.message))


@dataclass(frozen=True)
class CapacityPlanningConfig:
    weak_leg: int = 0
    next_lift_leg: int = 2
    forward_progress_m: float = .03
    nominal_lateral_shift_m: float = -.02
    maximum_lateral_adjustment_m: float = .08
    maximum_extra_forward_m: float = .01
    support_margin_m: float = .01
    original_tripod_margin_m: float = .02
    minimum_support_force_n: float = 5.
    next_lift_height_m: float = .02
    next_hold_s: float = 1.
    probe_posture_adjustment_m: float = .015
    maximum_probe_request_n: float = 60.
    requested_probe_load_n: float = 45.
    probe_force_ceiling_n: float = 30.
    probe_robustness_margin_n: float = 2.

    def __post_init__(self):
        if self.weak_leg not in range(4) or self.next_lift_leg not in range(4) or self.weak_leg == self.next_lift_leg:
            raise ValueError('Weak and next swing legs must be distinct valid legs')
        values = [value for key, value in self.__dict__.items() if key not in ('weak_leg', 'next_lift_leg', 'nominal_lateral_shift_m')]
        if not np.all(np.isfinite(values)) or min(values) <= 0 or not np.isfinite(self.nominal_lateral_shift_m):
            raise ValueError('Planner physical bounds must be positive and finite')


@dataclass(frozen=True)
class CapacityDecision:
    action: str
    reason: str
    body_target_w: np.ndarray
    allocated_forces_n: np.ndarray
    mpc_force_caps_n: np.ndarray
    next_lift_leg: int
    next_lift_height_m: float
    next_hold_s: float
    certified_load_n: float
    usable_force_cap_n: float
    nominal_required_load_n: float
    chosen_future_load_n: float
    requested_probe_load_n: float = 0.
    achievable_probe_load_n: float = 0.
    maximum_achievable_probe_load_n: float = 0.
    support_margin_m: float = 0.

    def __post_init__(self):
        if self.action not in ('EXECUTE', 'PROBE', 'SAFE_STOP'):
            raise ValueError('Invalid capacity decision')
        object.__setattr__(self, 'body_target_w', immutable_array(self.body_target_w, (3,)))
        for name in ('allocated_forces_n', 'mpc_force_caps_n'):
            object.__setattr__(self, name, immutable_array(getattr(self, name), (4,)))


class CapacityPlanner:
    """Fixed-next-motion baseline or constrained body/force adaptation.

    Probe allocations may deliberately exceed a prior demonstrated capacity,
    but the original three supports remain geometrically sufficient by
    themselves. A PROBE decision does not authorize the subsequent leg lift;
    only a new measured certificate can do so.
    """

    def __init__(self, variant='adaptive', config=CapacityPlanningConfig()):
        if variant not in ('baseline', 'adaptive'):
            raise ValueError('Capacity planner variant must be baseline or adaptive')
        self.variant, self.config = variant, config

    def _future(self, anchors, weight, probe, upper, weak_cap, extra_matrix, extra_upper, *, adapt):
        c = self.config
        lower = np.full(4, c.minimum_support_force_n)
        lower[c.weak_leg] = lower[c.next_lift_leg] = 0.
        upper = np.array(upper, copy=True)
        upper[c.weak_leg] = min(upper[c.weak_leg], max(0., weak_cap))
        upper[c.next_lift_leg] = 0.
        nominal = np.array(probe, copy=True)+[c.forward_progress_m, c.nominal_lateral_shift_m, 0.]
        if not adapt:
            answer = solve_load_allocation(anchors, weight, nominal, lower, upper,
                                          extra_matrix=extra_matrix, extra_upper=extra_upper)
            return replace(answer, feasible=answer.feasible and answer.support_margin_m >= c.support_margin_m-1e-9)
        _, lower, upper, aeq, aub, bub = _force_problem(anchors, weight, lower, upper, extra_matrix, extra_upper)
        # Variables are [F_FL,F_FR,F_RL,F_RR, CoM_x,CoM_y].
        equality = np.c_[aeq, np.array([[0., 0.], [-weight, 0.], [0., -weight]])]
        normals, offsets = support_halfspaces(anchors[np.arange(4) != c.next_lift_leg], c.support_margin_m)
        inequality = np.c_[np.zeros((3, 4)), -normals]
        bound = -offsets
        if aub is not None:
            inequality = np.vstack([inequality, np.c_[aub, np.zeros((len(aub), 2))]])
            bound = np.r_[bound, bub]
        low = np.r_[lower, probe[0]+c.forward_progress_m, probe[1]-c.maximum_lateral_adjustment_m]
        high = np.r_[upper, probe[0]+c.forward_progress_m+c.maximum_extra_forward_m,
                     probe[1]+c.maximum_lateral_adjustment_m]
        feasible = linprog(np.zeros(6), A_ub=inequality, b_ub=bound, A_eq=equality,
                           b_eq=[weight, 0., 0.], bounds=list(zip(low, high)), method='highs')
        if not feasible.success:
            return ForceAllocation(False, np.zeros(4), nominal, -1., 'No feasible future body/force allocation')

        def objective(value):
            displacement = (value[4:]-nominal[:2])/.03
            force_cost = value[:4]/weight
            gradient = np.r_[.02*force_cost/weight, 2*displacement/.03]
            return float(displacement@displacement+.01*(force_cost@force_cost)), gradient

        solution = minimize(objective, feasible.x, jac=True, method='SLSQP', bounds=Bounds(low, high),
            constraints=[LinearConstraint(equality, [weight, 0., 0.], [weight, 0., 0.]),
                         LinearConstraint(inequality, -np.inf, bound)], options={'ftol':1e-10, 'maxiter':100})
        value = solution.x if solution.success else feasible.x
        com = np.r_[value[4:], probe[2]]
        margin = float(np.min(normals@com[:2]-(offsets-c.support_margin_m)))
        return ForceAllocation(True, value[:4], com, margin)

    def probe_allocation(self, anchors_w, weight_n, probe_com_w, requested_load_n, force_upper_n,
                         *, allow_posture_change=True, extra_matrix=None, extra_upper=None):
        """Return a realizable force plateau, distinct from an arbitrary request."""
        c = self.config
        probe = immutable_array(probe_com_w, (3,))
        lower = np.full(4, c.minimum_support_force_n)
        lower[c.weak_leg] = 0.
        anchors, lower, upper, aeq, aub, bub = _force_problem(anchors_w, weight_n, lower, force_upper_n, extra_matrix, extra_upper)
        if requested_load_n <= 0 or not np.isfinite(requested_load_n):
            raise ValueError('Requested probe load must be positive and finite')
        normals, offsets = support_halfspaces(anchors[np.arange(4) != c.weak_leg], c.original_tripod_margin_m)
        equality = np.c_[aeq, np.array([[0., 0.], [-weight_n, 0.], [0., -weight_n]])]
        inequality = np.c_[np.zeros((3, 4)), -normals]
        bound = -offsets
        if aub is not None:
            inequality = np.vstack([inequality, np.c_[aub, np.zeros((len(aub), 2))]])
            bound = np.r_[bound, bub]
        adjustment = c.probe_posture_adjustment_m if allow_posture_change else 0.
        bounds = list(zip(np.r_[lower, probe[:2]-adjustment], np.r_[upper, probe[:2]+adjustment]))
        objective = np.zeros(6); objective[c.weak_leg] = -1.
        maximum = linprog(objective, A_ub=inequality, b_ub=bound, A_eq=equality,
                          b_eq=[weight_n, 0., 0.], bounds=bounds, method='highs')
        if not maximum.success:
            return ForceAllocation(False, np.zeros(4), probe, -1., 'No safe original-tripod probe allocation'), 0.
        achievable = min(float(requested_load_n), c.probe_force_ceiling_n,
                         max(0., float(maximum.x[c.weak_leg])-c.probe_robustness_margin_n))
        if achievable <= 0:
            return ForceAllocation(False, np.zeros(4), probe, -1., 'No robust positive probe plateau is achievable'), float(maximum.x[c.weak_leg])
        bounds[c.weak_leg] = (achievable, achievable)
        target = linprog(np.zeros(6), A_ub=inequality, b_ub=bound, A_eq=equality,
                         b_eq=[weight_n, 0., 0.], bounds=bounds, method='highs')
        if not target.success:
            return ForceAllocation(False, np.zeros(4), probe, -1., 'Requested test force is not realizable'), float(maximum.x[c.weak_leg])
        com = np.r_[target.x[4:], probe[2]]
        margin = float(np.min(normals@com[:2]-(offsets-c.original_tripod_margin_m)))
        return ForceAllocation(True, target.x[:4], com, margin), float(maximum.x[c.weak_leg])

    def decide(self, certificate, anchors_w, weight_n, probe_com_w, force_upper_n,
               *, allow_additional_probe=True, extra_matrix=None, extra_upper=None):
        c = self.config
        anchors, probe = immutable_array(anchors_w, (4, 3)), immutable_array(probe_com_w, (3,))
        upper = immutable_array(force_upper_n, (4,))
        nominal = self._future(anchors, weight_n, probe, upper, upper[c.weak_leg], extra_matrix, extra_upper, adapt=False)
        nominal_required = float(nominal.forces_n[c.weak_leg]) if nominal.feasible else 0.
        cap = certificate.force_cap_n if certificate.valid else 0.
        future = self._future(anchors, weight_n, probe, upper, cap, extra_matrix, extra_upper, adapt=self.variant == 'adaptive')
        caps = upper.copy(); caps[c.weak_leg] = cap; caps[c.next_lift_leg] = 0.
        common = dict(next_lift_leg=c.next_lift_leg, next_lift_height_m=c.next_lift_height_m,
            next_hold_s=c.next_hold_s, certified_load_n=certificate.certified_load_n,
            usable_force_cap_n=cap, nominal_required_load_n=nominal_required)
        if certificate.valid and future.feasible:
            return CapacityDecision('EXECUTE', 'Future motion fits demonstrated loading', future.com_position_w,
                future.forces_n, caps, chosen_future_load_n=float(future.forces_n[c.weak_leg]),
                support_margin_m=future.support_margin_m, **common)
        if self.variant == 'adaptive' and allow_additional_probe:
            requested = min(c.maximum_probe_request_n, c.requested_probe_load_n)
            probe_plan, maximum = self.probe_allocation(anchors, weight_n, probe, requested, upper,
                extra_matrix=extra_matrix, extra_upper=extra_upper)
            tested_cap = max(0., probe_plan.forces_n[c.weak_leg]-certificate.measurement_margin_n-certificate.tracking_margin_n)
            after_probe = self._future(anchors, weight_n, probe, upper, tested_cap, extra_matrix, extra_upper, adapt=True)
            if probe_plan.feasible and after_probe.feasible and tested_cap > cap+1.:
                probe_caps = upper.copy(); probe_caps[c.weak_leg] = probe_plan.forces_n[c.weak_leg]
                return CapacityDecision('PROBE', 'A stronger measured plateau is required before leg lift',
                    probe_plan.com_position_w, probe_plan.forces_n, probe_caps, chosen_future_load_n=0.,
                    requested_probe_load_n=requested, achievable_probe_load_n=float(probe_plan.forces_n[c.weak_leg]),
                    maximum_achievable_probe_load_n=maximum, support_margin_m=probe_plan.support_margin_m, **common)
        # SAFE_STOP means keep the original supporting tripod; zero allocation
        # here is not a torque command and must not be passed to execution.
        return CapacityDecision('SAFE_STOP', 'No certified feasible next movement', probe, np.zeros(4),
            np.array([cap if i == c.weak_leg else upper[i] for i in range(4)]),
            chosen_future_load_n=0., **common)
