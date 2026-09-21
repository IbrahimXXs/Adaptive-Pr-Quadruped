"""Select a fixed additional test while inheriting frozen V2 execution."""
from dataclasses import asdict

import numpy as np

from primp_project.control.weak_pad_v2 import WeakPadV2Wrapper
from .planner import FixedForceCapacityPlanner


class FixedForceWrapper(WeakPadV2Wrapper):
    def __init__(self, env, *, fixed_probe_force_n,
                 probe_undershoot_allowance_n=.2, **kwargs):
        self.fixed_probe_force_n = fixed_probe_force_n
        self.probe_undershoot_allowance_n = probe_undershoot_allowance_n
        self.fixed_probe_target = None
        super().__init__(env, **kwargs)

    def _choose_movement(self, t):
        planner = FixedForceCapacityPlanner(self.capacity_config,
            fixed_probe_force_n=self.fixed_probe_force_n,
            sensor_force_error_bound_n=self.sensor_force_error_bound_n,
            probe_undershoot_allowance_n=self.probe_undershoot_allowance_n)
        self.decision = planner.decide(self.certificate_estimator.certificate,
            self.anchors, self.weight, self.probe_origin_com, np.full(4, self.weight),
            allow_additional_probe=self.additional_probe_count < 1)
        self.fixed_probe_target = asdict(planner.last_probe_target) if planner.last_probe_target else None
        self.decision_history.append(dict(time_s=t-self.origin, **asdict(self.decision),
            fixed_probe_target=self.fixed_probe_target))
        # Frozen transitions: only the selected additional-test decision changes.
        self.required_pad_force_n = float(self.decision.nominal_required_load_n)
        self.movement_feasible = self.decision.action == 'EXECUTE'
        self.strategy_state = self.decision.action
        if self.decision.action == 'EXECUTE':
            self.progress_target = self.decision.body_target_w.copy()
            self.enter('progress_shift', t)
        elif self.decision.action == 'PROBE':
            self.future_plan_active = False
            self.additional_probe_count += 1
            self.maximum_achievable_probe_force_n = self.decision.maximum_achievable_probe_load_n
            self.reprobe_target = self.decision.body_target_w.copy()
            self.reprobe_start = self.com_target.copy()
            self.enter('reprobe_posture', t)
        else:
            self.enter('safe_stop', t)
