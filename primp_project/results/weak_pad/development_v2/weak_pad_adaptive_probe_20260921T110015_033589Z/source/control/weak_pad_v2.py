"""Matched movement optimization, bounded test policies and probe-failure recovery."""
from dataclasses import asdict
import numpy as np
from primp_project.control.weak_pad import WeakPadWrapper
from primp_project.control.controlled_step import ControlledStepWrapper, smooth_motion, support_margin
from primp_project.planning.load_capacity import CapacityPlanningConfig, CapacityPlanner

STRATEGIES=('fixed_probe','adaptive_force_fixed_posture','adaptive_probe')
PROBE_PHASES=('probe_ramp','probe_hold','probe_release','reprobe_posture')
RECOVERY_PHASES=('recovery_unload','recovery_lift','recovery_hold')


class WeakPadV2Wrapper(WeakPadWrapper):
    def __init__(self,env,*,strategy,initial_probe_force_n=22.,requested_probe_force_n=60.,
                 maximum_probe_force_n=60.,planning_config=None,probe_offset_xy_m=(0.,0.),
                 sensor_config=None,seed=17,measurement_reserve_n=1.,tracking_reserve_n=8.,**kwargs):
        if strategy not in STRATEGIES:raise ValueError('Unknown matched probing policy')
        settings=dict(forward_progress_m=.04,next_lift_height_m=.03,next_hold_s=1.,
            maximum_probe_request_n=requested_probe_force_n,requested_probe_load_n=requested_probe_force_n,
            probe_force_ceiling_n=maximum_probe_force_n)
        settings.update(planning_config or {})
        self.capacity_config=CapacityPlanningConfig(**settings)
        self.probe_offset_xy=np.asarray(probe_offset_xy_m,dtype=float)
        if self.probe_offset_xy.shape!=(2,) or not np.all(np.isfinite(self.probe_offset_xy)):
            raise ValueError('Probe posture offset must be finite XY')
        self.sensor_config=dict(force_bias_n=0.,force_noise_n=0.,position_noise_m=0.)
        self.sensor_config.update(sensor_config or {})
        if set(self.sensor_config)!={'force_bias_n','force_noise_n','position_noise_m'}:
            raise ValueError('Unknown capacity sensing parameter')
        vals=np.array(list(self.sensor_config.values()),float)
        if not np.all(np.isfinite(vals)) or min(self.sensor_config['force_noise_n'],self.sensor_config['position_noise_m'])<0:
            raise ValueError('Sensing bounds must be finite and noise amplitudes nonnegative')
        self.sensor_force_error_bound_n=abs(self.sensor_config['force_bias_n'])+self.sensor_config['force_noise_n']
        if self.sensor_force_error_bound_n>measurement_reserve_n:
            raise ValueError('Force measurement reserve must cover the declared error bound')
        if self.sensor_config['position_noise_m']>.0002:
            raise ValueError('Initial sensing validation permits at most0.2 mm bounded position noise')
        self.sensor_rng=np.random.default_rng(seed)
        self.sensor_observation_time_s=0.
        self.certificate_allow_increase=False
        self.certificate_observation_phase="stand"
        self.certificate_reset=False
        self.recovery_triggered=self.recovered_stop_declared=False
        self.recovery_trigger_reason=''
        self.recovery_start_time_s=-1.
        self.recovery_foot_anchor_w=np.zeros(3)
        self.recovery_body_target=np.zeros(3)
        self.movement_feasible=False
        self.raw_feet=np.zeros((4,3));self.raw_normal=np.zeros(4)
        super().__init__(env,strategy=strategy,requested_probe_force_n=requested_probe_force_n,
            probe_command_limit_n=initial_probe_force_n,measurement_reserve_n=measurement_reserve_n,
            tracking_reserve_n=tracking_reserve_n,**kwargs)
        self.next_leg=self.capacity_config.next_lift_leg
        self.next_lift_anchor=self.anchors[self.next_leg].copy()

    def enter(self,phase,t):
        if phase in RECOVERY_PHASES:
            return ControlledStepWrapper.enter(self,phase,t)
        result=super().enter(phase,t)
        if phase=='shift':
            self.tripod_target[:2]+=self.probe_offset_xy
        return result

    def _configure_capacity_planner(self):
        # Policy changes probing only; all policies share the same future QP.
        self.capacity_planner=CapacityPlanner('adaptive',self.capacity_config)
        allocation,self.maximum_achievable_probe_force_n=self.capacity_planner.probe_allocation(
            self.anchors,self.weight,self.probe_origin_com,self.requested_probe_force_n,
            np.full(4,self.weight),allow_posture_change=False)
        if not allocation.feasible:raise RuntimeError('No feasible balanced initial test')
        self.achievable_probe_force_n=float(allocation.forces_n[0])

    def _choose_movement(self,t):
        # Replaced by the common matched policy decision API when configured.
        from primp_project.planning.load_capacity import MatchedCapacityPlanner
        planner=MatchedCapacityPlanner(self.strategy,self.capacity_config)
        self.decision=planner.decide(self.certificate_estimator.certificate,self.anchors,self.weight,
            self.probe_origin_com,np.full(4,self.weight),
            allow_additional_probe=self.additional_probe_count<1)
        self.decision_history.append(dict(time_s=t-self.origin,**asdict(self.decision)))
        self.required_pad_force_n=float(self.decision.nominal_required_load_n)
        self.movement_feasible=self.decision.action=='EXECUTE'
        self.strategy_state=self.decision.action
        if self.decision.action=='EXECUTE':
            self.progress_target=self.decision.body_target_w.copy()
            self.enter('progress_shift',t)
        elif self.decision.action=='PROBE':
            self.future_plan_active=False
            self.additional_probe_count+=1
            self.maximum_achievable_probe_force_n=self.decision.maximum_achievable_probe_load_n
            self.reprobe_target=self.decision.body_target_w.copy()
            self.reprobe_start=self.com_target.copy()
            self.enter('reprobe_posture',t)
        else:
            self.enter('safe_stop',t)

    def _monitor_certificate(self,t,foot_position,foot_velocity,contact,normal_force):
        self.certificate_observation_phase=self.phase
        self.certificate_allow_increase=self.phase=='probe_hold'
        return super()._monitor_certificate(t,foot_position,foot_velocity,contact,normal_force)

    def _start_recovery(self,t,feet,com,contacts,normal,reason):
        if self.recovery_triggered:return
        # The failure response is limited to phases where the original tripod
        # is physically present. No hidden failure bit or true pad height is read.
        if not (np.all(contacts[1:]) and np.all(normal[1:]>5.) and support_margin(com,feet[1:])>.015):
            raise RuntimeError('Cannot claim controlled probe recovery without the original tripod')
        self.certificate_estimator.invalidate(str(reason))
        self.certificate_force_n=0.;self.certificate_valid=False
        self.certificate_update=True
        self.certificate_revision=self.certificate_estimator.certificate.revision
        self.certificate_invalidation_reason=self.certificate_estimator.certificate.invalidation_reason
        self.future_plan_active=False
        self.recovery_triggered=True;self.recovery_trigger_reason=str(reason)
        self.recovery_start_time_s=t-self.origin
        self.recovery_foot_anchor_w=self.anchors[0].copy()
        self.recovery_start_foot=feet[0].copy()
        self.recovery_body_target=com.copy();self.recovery_body_target[2]=self.landed_body[2]
        self.strategy_state='RECOVERING'
        self.enter('recovery_unload',t)

    def _handle_certificate_invalidation(self,t,feet,com,contacts,normal):
        if self.phase in PROBE_PHASES or self.phase in ('safe_stop','progress_shift'):
            self._start_recovery(t,feet,com,contacts,normal,self.certificate_invalidation_reason)
        else:
            super()._handle_certificate_invalidation(t,feet,com,contacts,normal)

    def update_phase(self,t,feet,com,contacts,normal,velocity):
        self.raw_feet,self.raw_normal=feet.copy(),normal.copy()
        measured_feet=feet.copy();measured_normal=normal.copy()
        c=self.sensor_config
        measured_feet[0]+=self.sensor_rng.uniform(-c['position_noise_m'],c['position_noise_m'],3)
        measured_normal[0]=max(0.,normal[0]+c['force_bias_n']+self.sensor_rng.uniform(-c['force_noise_n'],c['force_noise_n']))
        self.sensor_observation_time_s=t-self.origin
        self.certificate_reset=False
        if self.phase in PROBE_PHASES and measured_feet[0,2]<self.anchors[0,2]-.0025:
            self._start_recovery(t,measured_feet,com,contacts,measured_normal,'observed_downward_surface_motion')
        super().update_phase(t,measured_feet,com,contacts,measured_normal,velocity)
        if self.phase not in RECOVERY_PHASES:return
        elapsed=t-self.phase_start
        original_supported=np.all(contacts[1:]) and np.all(measured_normal[1:]>5.) and support_margin(com,measured_feet[1:])>.015
        if not original_supported:raise RuntimeError('Original tripod lost support during controlled recovery')
        if self.phase=='recovery_unload':
            if elapsed>=.3 and self.guarded(measured_normal[0]<2.,t,.1):
                self.recovery_lift_start=measured_feet[0].copy()
                self.enter('recovery_lift',t)
            elif elapsed>1.5:raise RuntimeError('Failed foothold did not unload within recovery bound')
        elif self.phase=='recovery_lift':
            if elapsed>=2. and self.guarded(not contacts[0] and measured_feet[0,2]-self.recovery_foot_anchor_w[2]>.025,t,.2):
                self.enter('recovery_hold',t)
            elif elapsed>4.:raise RuntimeError('Recovery foot clearance was not established')
        else:
            stable=(not contacts[0] and measured_normal[0]<2.
                    and measured_feet[0,2]-self.recovery_foot_anchor_w[2]>.025
                    and np.linalg.norm(velocity)<.02)
            if self.guarded(stable,t,2.5):
                self.recovered_stop_declared=True
                self.strategy_state='RECOVERED_STOP'
                self.experiment_complete=True
            elif elapsed>6.:raise RuntimeError('Recovered tripod did not settle')

    def references(self,t):
        if self.phase not in RECOVERY_PHASES:
            super().references(t)
            if self.phase in PROBE_PHASES or self.phase=='safe_stop':
                self.force_floors[1:]=self.capacity_config.minimum_support_force_n
            elif self.future_plan_active:
                for i in range(4):
                    if i not in (0,self.next_leg):self.force_floors[i]=self.capacity_config.minimum_support_force_n
            return
        elapsed=t-self.phase_start
        self.com_target=self.recovery_body_target.copy();self.com_velocity=np.zeros(3)
        self.planned=np.array([0,1,1,1])
        self.force_caps=np.full(4,self.weight);self.force_caps[0]=0.
        self.force_floors=np.r_[0.,np.full(3,self.capacity_config.minimum_support_force_n)];self.blends=np.array([1.,0.,0.,0.])
        self.desired_feet=self.anchors.copy()
        self.desired_velocities=np.zeros((4,3));self.desired_accelerations=np.zeros((4,3))
        high=self.recovery_foot_anchor_w+np.array([0.,0.,.035])
        if self.phase=='recovery_unload':
            self.desired_feet[0]=self.recovery_start_foot
        elif self.phase=='recovery_lift':
            p,v,a=smooth_motion(self.recovery_lift_start,high,elapsed,2.)
            self.desired_feet[0]=p;self.desired_velocities[0]=v;self.desired_accelerations[0]=a
        else:self.desired_feet[0]=high
        self.force_cap=0.;self.unload_blend=1.
        self.foot_target=self.desired_feet[0].copy()
        self.foot_velocity=self.desired_velocities[0].copy();self.foot_acceleration=self.desired_accelerations[0].copy()
