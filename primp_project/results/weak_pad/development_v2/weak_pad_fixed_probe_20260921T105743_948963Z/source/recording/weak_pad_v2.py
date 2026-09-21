"""Observe matched probe policies, continuous certification and physical recovery."""
from dataclasses import asdict
import hashlib
import json
import shutil
import numpy as np
from primp_project import PROJECT_ROOT
from primp_project.recording.weak_pad import WeakPadRecorder
from primp_project.recording.standing import json_value,LEGS
from primp_project.planning.load_capacity import CapacityPlanningConfig


class WeakPadV2Recorder(WeakPadRecorder):
    def __init__(self,run_dir,*,trial_parameters,rendered):
        p=trial_parameters
        super().__init__(run_dir,strategy=p['strategy'],requested_probe_force_n=p['requested_probe_force_n'],
            probe_command_limit_n=p['initial_probe_force_n'],measurement_reserve_n=p['measurement_reserve_n'],
            tracking_reserve_n=p['tracking_reserve_n'],seed=p['seed'],rendered=rendered,role=p['role'])
        settings=dict(forward_progress_m=.04,next_lift_height_m=.03,next_hold_s=1.,
            maximum_probe_request_n=p['requested_probe_force_n'],requested_probe_load_n=p['requested_probe_force_n'],
            probe_force_ceiling_n=p['maximum_probe_force_n'])
        settings.update(p['planning_config'])
        config=CapacityPlanningConfig(**settings)
        self.metadata.update(protocol_version=2,trial_parameters=json_value(p),scenario=p['scenario'],
            next_leg=LEGS[config.next_lift_leg],next_leg_index=config.next_lift_leg,
            movement_optimizer_id='shared_quasistatic_body_force_qp_v2',
            movement_optimizer_settings=asdict(config),
            movement_optimizer_config_sha256=hashlib.sha256(json.dumps(asdict(config),sort_keys=True).encode()).hexdigest(),
            sensor_config=p['sensor_config'],sensor_force_error_bound_n=abs(p['sensor_config'].get('force_bias_n',0.))+p['sensor_config'].get('force_noise_n',0.),
            sensor_position_error_bound_m=p['sensor_config'].get('position_noise_m',0.),sensor_delay_s=0.,
            recovery_minimum_tripod_hold_s=2.,recovery_maximum_unload_delay_s=1.5,
            recovery_maximum_abs_roll_pitch_deg=8.,recovery_minimum_foot_clearance_m=.025,
            required_forward_progress_m=.03,required_next_leg_lift_m=.02,
            required_progress_hold_s=1.)
        self.metadata['conventions'].update(
            certificate_observation_phase='State before processing this control interval observation; command phase may transition afterwards.',
            sensor_force_error_bound_n='Capacity-channel bounded force bias+uniform noise; existing MPC state/other-leg channels remain ideal.',
            forward_progress='World X relative to the first confirmed probing posture; the global movement goal stays fixed during further tests.')

    def start(self,env,cfg):
        super().start(env,cfg)
        self.metadata['initial_state']=json_value(getattr(env,'weak_pad_initial_state',{}))
        for name in ('control/weak_pad_v2.py','recording/weak_pad_v2.py','experiments/weak_pad_v2.py',
                     'analysis/weak_pad_v2.py','environment/weak_pad_initial_state.py'):
            p=PROJECT_ROOT/name
            if p.exists():
                dst=self.run_dir/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)

    def record_step(self,env,wrapper,*args,**kwargs):
        super().record_step(env,wrapper,*args,**kwargs)
        fields=('certificate_monitor_update','certificate_revision','certificate_invalidation_reason',
            'certificate_evidence_anchor_w','certificate_allow_increase','certificate_reset',
            'certificate_observation_phase','sensor_observation_time_s','sensor_force_error_bound_n',
            'recovery_triggered','recovered_stop_declared','recovery_trigger_reason',
            'recovery_start_time_s','recovery_foot_anchor_w','movement_feasible')
        for field in fields:self.rows[field].append(np.array(getattr(wrapper,field),copy=True))
        self.metadata['recovered_stop_declared']=wrapper.recovered_stop_declared
        self.metadata['recovery_trigger_reason']=wrapper.recovery_trigger_reason
