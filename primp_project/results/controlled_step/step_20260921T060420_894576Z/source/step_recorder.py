"""Extend the aligned standing signals with controlled-step commands and gates."""

import json
import shutil
import numpy as np
from primp_project.recorder import StandingRecorder, json_value
from primp_project.controlled_step import support_margin


class StepRecorder(StandingRecorder):
    def __init__(self, run_dir, cycles, hold_seconds, seed, rendered, friction):
        super().__init__(run_dir, 0., 3., seed, rendered)
        self.metadata.update(experiment="controlled_step", selected_leg="FL", cycles=cycles,
                             hold_seconds=hold_seconds, lift_height_m=.03,
                             contact_debounce_s=.1, friction=friction, actual_completed_cycles=0)
        self.metadata['conventions'].update(
            phase="Nonperiodic command phase held over control interval; cycle starts at 1.",
            feet_desired_w="Fixed settled world anchors for supports, explicit Cartesian trajectory for FL.",
            selected_force_cap_N="FL MPC Fz upper bound at most recent solve; held between MPC updates.",
            com_target_w="Desired physical center of mass in world coordinates; controller uses mass-weighted body xipos.")
        self.metadata['controller_changes'] = {
            'xy_position_cost': 2000., 'bias_compensation_all_legs': True,
            'physical_mass_and_com': True, 'periodic_gait_and_terrain_estimation_bypassed': True,
            'schedule': 'Binary FL=0 through lift/hold/lower/confirm for entire MPC horizon',
            'support_gate_margin_m': .02, 'touchdown_normal_threshold_N': 2.,
            'max_downward_search_m': .005,
        }

    def start(self, env, cfg):
        super().start(env, cfg)
        self.metadata.pop('expected_steps', None)
        source = self.run_dir / 'source'
        source.mkdir()
        from pathlib import Path
        for name in ('controlled_step.py', 'step_recorder.py', 'run_step.py', 'analyze_step.py'):
            file = Path(__file__).parent / name
            if file.exists():
                shutil.copy2(file, source / name)

    def record_step(self, env, wrapper, *args, **kwargs):
        super().record_step(env, wrapper, *args, **kwargs)
        self.rows['phase'][-1] = np.array(wrapper.phase)
        self.rows['phase_time_s'][-1] = np.array(float(env.simulation_time)-wrapper.phase_start)
        self.rows['mpc_update'][-1] = np.array(wrapper.mpc_updated)
        extra = dict(cycle=wrapper.cycle, com_target_w=wrapper.com_target,
                     com_velocity_ref_w=wrapper.com_velocity,
                     foot_anchor_w=wrapper.foot_anchor,
                     support_margin_m=support_margin(self.rows['com_pos_w'][-1], self.rows['feet_pos_w'][-1][1:]),
                     selected_force_cap_N=wrapper.solved_force_cap,
                     contact_confirmed=wrapper.contact_confirmed,
                     landing_contact_dwell_s=wrapper.landing_dwell,
                     desired_foot_vel_w=wrapper.foot_velocity,
                     desired_foot_acc_w=wrapper.foot_acceleration,
                     unload_blend=wrapper.unload_blend)
        for key, value in extra.items():
            self.rows[key].append(np.array(value, copy=True))
        self.metadata['actual_completed_cycles'] = wrapper.completed_cycles
        self.events = wrapper.events.copy()

    def save(self, status, error=None):
        super().save(status, error)
        (self.run_dir / 'phase_events.json').write_text(json.dumps(json_value(getattr(self, 'events', [])), indent=2)+'\n')
