"""Choose the smallest test that could certify the frozen future optimizer.

The requested force is a planning prediction, never evidence of applied force.
Only the existing measured-load estimator can authorize subsequent movement.
All geometry, future movement optimization, reserves, and probe achievability
constraints come from the frozen V2 implementation.
"""
from dataclasses import dataclass, replace

import numpy as np

from primp_project.planning.load_capacity import MatchedCapacityPlanner
from primp_project.planning.observations import immutable_array


@dataclass(frozen=True)
class MinimumProbeTarget:
    """Transparent target arithmetic; none of these values is a certificate."""

    minimum_future_load_n: float | None
    measurement_reserve_n: float
    tracking_reserve_n: float
    target_tolerance_n: float
    minimum_sufficient_probe_load_n: float | None
    sensor_force_error_bound_n: float
    probe_undershoot_allowance_n: float
    requested_probe_load_n: float | None
    formula: str = (
        'minimum_future_load_n + measurement_reserve_n '
        '+ tracking_reserve_n + target_tolerance_n'
    )
    commanded_force_is_not_measured_proof: bool = True
    command_formula: str = (
        'minimum_sufficient_probe_load_n + sensor_force_error_bound_n '
        '+ probe_undershoot_allowance_n'
    )


class MinimumSufficientCapacityPlanner(MatchedCapacityPlanner):
    """Retain the shared movement QP; minimize the requested additional test.

    The minimum load is an LP bound over exactly the frozen future feasible
    set. Adding the certificate's unchanged sensing and tracking reserves
    gives the predicted sufficient measured plateau. A 0.001 N tolerance
    avoids selecting precisely on a numerical feasibility boundary; it is
    not an allowance for unmeasured tracking or sensing errors.

    The existing fixed-pose probe allocator is tried first, then the same
    allowed posture changes. Its existing 2 N achievability reserve remains
    unchanged. The separate command allowance accounts for the declared
    sensor error bound and an explicit expected undershoot (default 0.2 N).
    That execution allowance is a planning assumption, not a guarantee and
    never relaxes the measured certificate. No simulator capacity enters the
    policy. A real plateau below the needed bound cannot authorize movement.
    """

    POLICY = 'minimum_sufficient_probe'

    def __init__(self, config, *, target_tolerance_n=0.001,
                 sensor_force_error_bound_n=0., probe_undershoot_allowance_n=.2):
        super().__init__('adaptive_probe', config)
        if not np.isfinite(target_tolerance_n) or not 0 < target_tolerance_n <= .01:
            raise ValueError('Target feasibility tolerance must be in (0, 0.01] N')
        self.target_tolerance_n = float(target_tolerance_n)
        allowances = np.array([sensor_force_error_bound_n, probe_undershoot_allowance_n], float)
        if not np.all(np.isfinite(allowances)) or np.any(allowances < 0):
            raise ValueError('Command allowances must be finite and nonnegative')
        self.sensor_force_error_bound_n = float(sensor_force_error_bound_n)
        self.probe_undershoot_allowance_n = float(probe_undershoot_allowance_n)
        self.last_probe_target = None

    def decide(self, certificate, anchors_w, weight_n, probe_com_w, force_upper_n,
               *, allow_additional_probe=True, extra_matrix=None, extra_upper=None):
        c = self.config
        anchors = immutable_array(anchors_w, (4, 3))
        origin = immutable_array(probe_com_w, (3,))
        upper = immutable_array(force_upper_n, (4,))
        sensing = float(certificate.measurement_margin_n)
        tracking = float(certificate.tracking_margin_n)
        if not np.all(np.isfinite([sensing, tracking])) or min(sensing, tracking) < 0:
            raise ValueError('Measured certificate reserves must be finite and nonnegative')
        if self.sensor_force_error_bound_n > sensing+1e-12:
            raise ValueError('Sensor error bound exceeds the unchanged certificate sensing reserve')

        minimum = self.minimum_future_allocation(anchors, weight_n, origin, upper,
            extra_matrix=extra_matrix, extra_upper=extra_upper)
        minimum_load = float(minimum.forces_n[c.weak_leg]) if minimum.feasible else None
        measured_target = (minimum_load+sensing+tracking+self.target_tolerance_n
                           if minimum_load is not None else None)
        command_allowance = self.sensor_force_error_bound_n+self.probe_undershoot_allowance_n
        target = measured_target+command_allowance if measured_target is not None else None
        self.last_probe_target = MinimumProbeTarget(minimum_load, sensing,
            tracking, self.target_tolerance_n, measured_target,
            self.sensor_force_error_bound_n, self.probe_undershoot_allowance_n, target)

        # This call supplies exactly the original EXECUTE decision, including
        # the same QP, body target, allocation, caps, and progress origin.
        current = super().decide(certificate, anchors, weight_n, origin, upper,
            allow_additional_probe=False, extra_matrix=extra_matrix,
            extra_upper=extra_upper)
        if current.action == 'EXECUTE' or not allow_additional_probe or not minimum.feasible:
            return current

        request_limit = min(c.maximum_probe_request_n, c.requested_probe_load_n,
                            c.probe_force_ceiling_n)
        if target > request_limit+1e-9:
            return replace(current, reason='Minimum sufficient test exceeds the declared request limit')

        for allow_posture_change in (False, True):
            probe_plan, maximum = self.probe_allocation(anchors, weight_n, origin,
                target, upper, allow_posture_change=allow_posture_change,
                extra_matrix=extra_matrix, extra_upper=extra_upper)
            actual_target = float(probe_plan.forces_n[c.weak_leg])
            if not probe_plan.feasible or actual_target < target-1e-9:
                continue
            predicted_cap = max(0., actual_target-command_allowance-sensing-tracking)
            future = self._future(anchors, weight_n, origin, upper, predicted_cap,
                extra_matrix, extra_upper, adapt=True)
            if not future.feasible or predicted_cap <= current.usable_force_cap_n+1e-9:
                continue
            test_caps = upper.copy()
            test_caps[c.weak_leg] = actual_target
            return replace(current, action='PROBE',
                reason='Request the minimum sufficient plateau plus declared command allowances',
                body_target_w=probe_plan.com_position_w,
                allocated_forces_n=probe_plan.forces_n, mpc_force_caps_n=test_caps,
                chosen_future_load_n=0., requested_probe_load_n=target,
                achievable_probe_load_n=actual_target,
                maximum_achievable_probe_load_n=maximum,
                support_margin_m=probe_plan.support_margin_m)

        return replace(current, reason='No allowed probing posture can apply the minimum sufficient test')
