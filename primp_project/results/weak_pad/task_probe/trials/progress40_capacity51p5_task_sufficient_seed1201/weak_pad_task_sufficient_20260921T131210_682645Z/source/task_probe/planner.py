"""A single fixed-force probing policy beside the frozen task-conditioned one.

The fixed command must be chosen on development conditions before evaluation.
Task information decides whether movement is certified, never the test force.
"""
from dataclasses import dataclass, replace

import numpy as np

from primp_project.planning.load_capacity import MatchedCapacityPlanner
from primp_project.planning.observations import immutable_array


@dataclass(frozen=True)
class FixedProbeTarget:
    fixed_probe_force_n: float
    minimum_future_load_n: float | None
    measurement_reserve_n: float
    tracking_reserve_n: float
    sensor_force_error_bound_n: float
    probe_undershoot_allowance_n: float
    predicted_certified_load_n: float
    predicted_usable_force_cap_n: float
    predicted_sufficient_for_task: bool
    command_formula: str = 'fixed_probe_force_n; unchanged across evaluation tasks'
    commanded_force_is_not_measured_proof: bool = True


class FixedForceCapacityPlanner(MatchedCapacityPlanner):
    """Execute certified movement or apply one task-independent test amplitude.

    The future optimizer, posture freedom, force bounds and probe achievability
    reserve are inherited without modification. If the fixed command cannot
    be applied at the initial pose, the same allowed posture change is tried.
    If neither can robustly apply that exact command, the policy stops; it
    neither clips to a different test nor raises the force for a harder task.

    A test may increase the demonstrated bound while remaining insufficient
    for the next movement. The fixed policy still performs that test. Future
    execution always needs an actually observed sufficient certificate; an
    under-test followed by a safe stop is a valid outcome of this policy.
    """

    POLICY = 'fixed_force'

    def __init__(self, config, *, fixed_probe_force_n,
                 sensor_force_error_bound_n=0., probe_undershoot_allowance_n=.2):
        super().__init__('adaptive_probe', config)
        if not np.isfinite(fixed_probe_force_n) or fixed_probe_force_n <= 0:
            raise ValueError('Fixed probe force must be finite and positive')
        allowances = np.array([sensor_force_error_bound_n, probe_undershoot_allowance_n], float)
        if not np.all(np.isfinite(allowances)) or np.any(allowances < 0):
            raise ValueError('Command prediction allowances must be finite and nonnegative')
        self.fixed_probe_force_n = float(fixed_probe_force_n)
        self.sensor_force_error_bound_n = float(sensor_force_error_bound_n)
        self.probe_undershoot_allowance_n = float(probe_undershoot_allowance_n)
        self.last_probe_target = None

    def decide(self, certificate, anchors_w, weight_n, probe_com_w, force_upper_n,
               *, allow_additional_probe=True, extra_matrix=None, extra_upper=None):
        c = self.config
        anchors = immutable_array(anchors_w, (4, 3))
        origin = immutable_array(probe_com_w, (3,))
        upper = immutable_array(force_upper_n, (4,))
        sensing, tracking = float(certificate.measurement_margin_n), float(certificate.tracking_margin_n)
        if not np.all(np.isfinite([sensing, tracking])) or min(sensing, tracking) < 0:
            raise ValueError('Measured certificate reserves must be finite and nonnegative')
        if self.sensor_force_error_bound_n > sensing+1e-12:
            raise ValueError('Sensor error bound exceeds the unchanged certificate sensing reserve')

        minimum = self.minimum_future_allocation(anchors, weight_n, origin, upper,
            extra_matrix=extra_matrix, extra_upper=extra_upper)
        minimum_load = float(minimum.forces_n[c.weak_leg]) if minimum.feasible else None
        predicted_certificate = max(0., self.fixed_probe_force_n-sensing
            -self.sensor_force_error_bound_n-self.probe_undershoot_allowance_n)
        predicted_cap = max(0., predicted_certificate-tracking)
        predicted_future = self._future(anchors, weight_n, origin, upper, predicted_cap,
            extra_matrix, extra_upper, adapt=True)
        self.last_probe_target = FixedProbeTarget(self.fixed_probe_force_n, minimum_load,
            sensing, tracking, self.sensor_force_error_bound_n, self.probe_undershoot_allowance_n,
            predicted_certificate, predicted_cap, bool(predicted_future.feasible))

        # Preserve the entire measured-certificate EXECUTE decision, including
        # the same body movement, force allocation and task progress origin.
        current = super().decide(certificate, anchors, weight_n, origin, upper,
            allow_additional_probe=False, extra_matrix=extra_matrix, extra_upper=extra_upper)
        if current.action == 'EXECUTE' or not allow_additional_probe or not minimum.feasible:
            return current

        request_limit = min(c.maximum_probe_request_n, c.requested_probe_load_n,
                            c.probe_force_ceiling_n)
        if self.fixed_probe_force_n > request_limit+1e-9:
            return replace(current, reason='Fixed test exceeds the unchanged declared request limit')
        demonstrated = certificate.certified_load_n if certificate.valid else 0.
        if predicted_certificate <= demonstrated+1e-9:
            return replace(current, reason='The fixed test predicts no increase in demonstrated load')

        for allow_posture_change in (False, True):
            probe_plan, maximum = self.probe_allocation(anchors, weight_n, origin,
                self.fixed_probe_force_n, upper, allow_posture_change=allow_posture_change,
                extra_matrix=extra_matrix, extra_upper=extra_upper)
            achievable = float(probe_plan.forces_n[c.weak_leg])
            if not probe_plan.feasible or abs(achievable-self.fixed_probe_force_n) > 1e-9:
                continue
            test_caps = upper.copy()
            test_caps[c.weak_leg] = achievable
            return replace(current, action='PROBE',
                reason='Apply the development-selected fixed test, then reassess measured proof',
                body_target_w=probe_plan.com_position_w,
                allocated_forces_n=probe_plan.forces_n, mpc_force_caps_n=test_caps,
                chosen_future_load_n=0., requested_probe_load_n=self.fixed_probe_force_n,
                achievable_probe_load_n=achievable,
                maximum_achievable_probe_load_n=maximum,
                support_margin_m=probe_plan.support_margin_m)

        return replace(current, reason='No allowed probing posture can apply the fixed test exactly')
