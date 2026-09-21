"""Additional-test targets alongside unchanged V2 physical measurements."""
import shutil

import numpy as np

from primp_project import PROJECT_ROOT
from primp_project.recording.weak_pad_v2 import WeakPadV2Recorder


class ProbeEfficiencyRecorder(WeakPadV2Recorder):
    def __init__(self, run_dir, *, trial_parameters, rendered):
        super().__init__(run_dir, trial_parameters=trial_parameters, rendered=rendered)
        p = trial_parameters
        self.metadata.update(study_name='probe_efficiency', probe_efficiency_version=1,
            probe_policy=p['probe_policy'], target_tolerance_n=p['target_tolerance_n'],
            probe_undershoot_allowance_n=p['probe_undershoot_allowance_n'])
        self.metadata['conventions'].update(
            minimum_sufficient_probe_load_n='Required measured plateau: minimum future load + unchanged measurement and tracking reserves + numerical tolerance.',
            probe_target_load_n='Selected additional test command; differs from requested force budget, MPC output, and actual measured load.',
            probe_execution_allowance='Minimum policy command also accounts for the declared force observation error bound and empirical probe undershoot allowance. This predicts targeting only and supplies no capacity certificate.')

    def start(self, env, cfg):
        super().start(env, cfg)
        for source in (PROJECT_ROOT/'probe_efficiency').glob('*.py'):
            dest = self.run_dir/'source'/'probe_efficiency'/source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

    def record_step(self, env, wrapper, *args, **kwargs):
        super().record_step(env, wrapper, *args, **kwargs)
        decision = wrapper.decision
        minimum = float(decision.minimum_future_load_n) if decision is not None else 0.
        target = minimum + self.metadata['sensor_force_reserve_n'] + wrapper.tracking_reserve_n + self.metadata['target_tolerance_n'] if decision is not None else 0.
        selected = next((d for d in reversed(wrapper.decision_history) if d['action'] == 'PROBE'), None)
        values = dict(minimum_future_load_n=minimum,
            minimum_sufficient_probe_load_n=target,
            probe_target_load_n=float(selected['achievable_probe_load_n']) if selected else 0.,
            selected_probe_request_n=float(selected['requested_probe_load_n']) if selected else 0.,
            target_tolerance_n=self.metadata['target_tolerance_n'],
            probe_execution_allowance_n=wrapper.sensor_force_error_bound_n+self.metadata['probe_undershoot_allowance_n'])
        for key, value in values.items():
            self.rows[key].append(np.array(value, copy=True))
