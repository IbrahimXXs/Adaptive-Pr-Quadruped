"""Aligned sensor, requested force, certified capacity and simulator-only truth."""
from dataclasses import asdict
import shutil
import numpy as np
from primp_project import PROJECT_ROOT
from primp_project.recording.step import StepRecorder
from primp_project.recording.standing import json_value


class WeakPadRecorder(StepRecorder):
    def __init__(self, run_dir, *, strategy, requested_probe_force_n, probe_command_limit_n,
                 measurement_reserve_n, tracking_reserve_n, seed, rendered, role):
        super().__init__(run_dir, 1, 5., seed, rendered, .8)
        self.metadata.update(experiment='weak_pad', strategy=strategy, role=role,
            requested_probe_force_n=requested_probe_force_n, probe_command_limit_n=probe_command_limit_n,
            probe_dwell_s=.5, sensor_force_reserve_n=measurement_reserve_n,
            tracking_reserve_n=tracking_reserve_n, next_leg='RL', next_leg_index=2,
            required_forward_progress_m=.03, required_next_leg_lift_m=.02,
            required_progress_hold_s=1., max_probe_motion_m=.001,
            progression_axis=[1.,0.,0.], force_tolerance_n=.5,
            assumptions=['Time-invariant monotone normal-force threshold at the same contact location.',
                'Uniform strength within 10 mm horizontal contact motion; >2.5 mm vertical motion invalidates the test.',
                'No fatigue, shear failure, history-dependent damage or rate-dependent strength.',
                'A stable test supplies a demonstrated load bound, never the exact breaking force.'])

    def start(self, env, cfg):
        super().start(env,cfg)
        self.metadata['evaluation']=dict(env.weak_pad_evaluation)
        self.metadata['evaluation']['failure_threshold_n']=self.metadata['evaluation']['failure_load_n']
        for name in ('control/weak_pad.py','environment/weak_pad.py','planning/load_capacity.py',
                     'recording/weak_pad.py','experiments/weak_pad.py','analysis/weak_pad.py'):
            p=PROJECT_ROOT/name
            if p.exists():
                dest=self.run_dir/'source'/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,dest)

    def record_step(self, env, wrapper, *args, **kwargs):
        super().record_step(env,wrapper,*args,**kwargs)
        ev=env.weak_pad_evaluation
        extra=dict(
            requested_probe_force_n=wrapper.requested_probe_force_n,
            additional_probe_count=wrapper.additional_probe_count,
            achieved_probe_command_n=wrapper.achieved_probe_command_n,
            maximum_achievable_probe_force_n=wrapper.maximum_achievable_probe_force_n,
            sensor_pad_normal_force_n=wrapper.sensor_normal[0],
            sensor_contact_measured=wrapper.sensor_contacts,
            sensor_pad_foot_pos_w=wrapper.sensor_foot_position,
            sensor_pad_foot_vel_w=wrapper.sensor_foot_velocity,
            actual_pad_normal_force_n=ev['target_normal_force_n'],
            force_before_deformation_n=ev['force_before_deformation_n'],
            pad_contact=bool(self.rows['contact_measured'][-1][0]),
            certificate_force_n=wrapper.certificate_force_n,
            certificate_valid=wrapper.certificate_valid, certificate_update=wrapper.certificate_update,
            probe_evidence_start_time_s=wrapper.probe_evidence_start_time_s,
            probe_evidence_end_time_s=wrapper.probe_evidence_end_time_s,
            planned_pad_force_n=float(wrapper.nmpc_GRFs.FL[2]),
            applied_pad_force_cap_n=float(wrapper.solved_force_caps[0]),
            force_caps_n=wrapper.solved_force_caps,
            required_pad_force_n=wrapper.required_pad_force_n,
            tracking_reserve_n=wrapper.tracking_reserve_n,
            commanded_next_leg_lift_m=wrapper.commanded_next_leg_lift_m,
            strategy_state=wrapper.strategy_state,
            safe_stop_declared=wrapper.safe_stop_declared,
            task_complete_declared=wrapper.task_complete_declared,
            future_plan_active=wrapper.future_plan_active,
            pad_sink_displacement_m=ev['sink_displacement_m'],
            actual_pad_displacement_m=ev['sink_displacement_m'],
            pad_failed=ev['failed'], overload_elapsed_s=ev['overload_elapsed_s'],
            probe_origin_com_w=wrapper.probe_origin_com,
            progress_target_w=wrapper.progress_target,
            next_lift_anchor_w=wrapper.next_lift_anchor,
            experiment_complete=wrapper.experiment_complete)
        for key,value in extra.items():
            self.rows[key].append(np.array(value,copy=True))
        self.metadata['evaluation_final']=json_value(ev)
        self.metadata['terminal_state']=wrapper.strategy_state
        self.metadata['probe_origin_com_w']=wrapper.probe_origin_com.tolist()
        self.metadata['experiment_complete']=wrapper.experiment_complete
        if wrapper.decision is not None:
            self.metadata['capacity_decision']=json_value(asdict(wrapper.decision))
        self.metadata['additional_probe_count']=wrapper.additional_probe_count
        self.metadata['capacity_decision_history']=json_value(wrapper.decision_history)
