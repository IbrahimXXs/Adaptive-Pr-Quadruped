"""Test a new contact, then execute only load-certified support transitions.

No simulator failure threshold or pad displacement enters this controller.
Only foot contact, measured load, kinematics and known robot geometry are used.
"""
import numpy as np
from gym_quadruped.utils.quadruped_utils import LegsAttr
from primp_project.control.landing_pad import LandingPadWrapper
from primp_project.control.controlled_step import ControlledStepWrapper, smooth_motion, support_margin
from primp_project.recording.standing import LEGS, ground_contacts, stack_legs


class WeakPadWrapper(LandingPadWrapper):
    def __init__(self, env, *, strategy, requested_probe_force_n=45., probe_command_limit_n=22.,
                 measurement_reserve_n=1., tracking_reserve_n=6., **kwargs):
        from primp_project.planning import SENSOR_PROFILES
        super().__init__(env, initial_estimate_m=0., planner_name='reactive',
                         lower_duration_s=4., sensor_profile=SENSOR_PROFILES['clean'], **kwargs)
        self.strategy = strategy
        self.requested_probe_force_n = float(requested_probe_force_n)
        self.probe_command_limit_n = float(probe_command_limit_n)
        self.measurement_reserve_n = float(measurement_reserve_n)
        self.tracking_reserve_n = float(tracking_reserve_n)
        self.probe_dwell_s = .5
        from primp_project.planning.load_capacity import CertificateConfig, DemonstratedLoadCertificate
        self.certificate_estimator = DemonstratedLoadCertificate(CertificateConfig(
            dwell_s=.5, measurement_margin_n=measurement_reserve_n, tracking_margin_n=tracking_reserve_n))
        self.probe_evidence = []
        self.certificate_force_n = 0.
        self.certificate_valid = self.certificate_update = False
        self.probe_evidence_start_time_s = self.probe_evidence_end_time_s = -1.
        self.achieved_probe_command_n = 0.
        self.required_pad_force_n = 0.
        self.future_plan_active = False
        self.safe_stop_declared = self.task_complete_declared = False
        self.strategy_state = 'approach'
        self.force_caps = np.full(4, self.weight)
        self.force_floors = np.zeros(4)
        self.solved_force_caps = self.force_caps.copy()
        self.blends = np.zeros(4)
        self.desired_feet = self.anchors.copy()
        self.desired_velocities = self.desired_accelerations = np.zeros((4,3))
        self.next_leg = 2
        self.commanded_next_leg_lift_m = 0.
        self.probe_origin_com = self.tripod_target.copy()
        self.progress_target = self.tripod_target.copy()
        self.decision = None
        self.sensor_normal = np.zeros(4)
        self.sensor_contacts = np.zeros(4, bool)
        self.next_lift_anchor = self.anchors[2].copy()
        self.progress_hold_since = None

    def enter(self, phase, t):
        if phase == 'reload' and self.strategy != 'unaware':
            self.landed_body = self.com_target.copy()
            self.landed_orientation = self.body_orientation_ref.copy()
            self.anchors[0] = self.sensor_observation.foot_position
            self.landing_target = self.anchors[0].copy()
            self.probe_origin_com = self.physical_com().copy()
            self.next_lift_anchor = self.anchors[self.next_leg].copy()
            self.probe_initial_force = max(0., float(self.nmpc_GRFs.FL[2]))
            self.strategy_state = 'probing'
            phase = 'probe_ramp'
            self._configure_capacity_planner()
            self.achieved_probe_command_n = min(self.requested_probe_force_n,
                self.probe_command_limit_n, self.achievable_probe_force_n)
        if phase == 'probe_hold':
            self.probe_evidence = []
        if phase == 'probe_release':
            self.release_start_cap = self.achieved_probe_command_n+.2
        if phase == 'plan':
            self.future_plan_active = True
            self._choose_movement(t)
            return
        if phase == 'progress_shift':
            self.move_start = self.com_target.copy()
        if phase == 'next_unload':
            self.next_unload_start = max(2., float(self.nmpc_GRFs.RL[2]))
        if phase == 'safe_stop':
            self.safe_stop_declared = True
            self.strategy_state = 'SAFE_STOP'
        if phase == 'progress_complete':
            self.task_complete_declared = True
            self.strategy_state = 'SUCCESS'
            self.completed_cycles = 1
        # Initial approach retains the validated landing controller unchanged.
        if phase in ('stand','shift','unload','lift','hold','lower','confirm','reload','recenter','complete'):
            return super().enter(phase, t)
        return ControlledStepWrapper.enter(self, phase, t)

    def _configure_capacity_planner(self):
        from primp_project.planning.load_capacity import CapacityPlanner, CapacityPlanningConfig
        self.capacity_planner = CapacityPlanner('adaptive' if self.strategy=='adaptive' else 'baseline',
            CapacityPlanningConfig(forward_progress_m=.04, next_lift_height_m=.03, next_hold_s=1.))
        allocation, self.achievable_probe_force_n = self.capacity_planner.probe_allocation(
            self.anchors, self.weight, self.probe_origin_com, self.requested_probe_force_n,
            np.full(4,self.weight), allow_posture_change=False)
        if not allocation.feasible:
            raise RuntimeError('No balanced original-tripod probing posture')

    def _choose_movement(self, t):
        self.decision = self.capacity_planner.decide(self.certificate_estimator.certificate,
            self.anchors, self.weight, self.probe_origin_com, np.full(4,self.weight),
            allow_additional_probe=False)
        self.required_pad_force_n = float(self.decision.nominal_required_load_n)
        self.strategy_state = str(self.decision.action)
        if self.decision.action == 'EXECUTE':
            self.progress_target = self.decision.body_target_w.copy()
            self.enter('progress_shift', t)
        else:
            self.enter('safe_stop', t)

    def update_phase(self, t, feet, com, contacts, normal, velocity):
        self.sensor_normal, self.sensor_contacts = normal.copy(), contacts.copy()
        self.certificate_update = False
        elapsed = t-self.phase_start
        if self.phase in ('stand','shift','unload','lift','hold','lower','confirm','reload','recenter','complete'):
            # An unaware trial records visible sinking, then stops on observable
            # foot descent. The hidden simulator failure flag is never read.
            if self.strategy == 'unaware' and self.phase in ('reload','recenter','complete'):
                if feet[0,2] < self.anchors[0,2]-.015:
                    self.strategy_state = 'OBSERVED_SINK'
                    self.experiment_complete = True
                    return
            return super().update_phase(t, feet, com, contacts, normal, velocity)
        self.margin = support_margin(com, feet[1:])
        if self.phase in ('probe_ramp','probe_hold','probe_release','safe_stop'):
            if not (np.all(contacts[1:]) and np.all(normal[1:] > 5.) and self.margin > .015):
                raise RuntimeError('Original three-leg support lost during foothold test/stop')
            if feet[0,2] < self.anchors[0,2]-.008:
                raise RuntimeError('Observed sinking during probe: abort without capacity certificate')
        if self.phase == 'probe_ramp' and elapsed >= 4.:
            self.enter('probe_hold', t)
        elif self.phase == 'probe_hold':
            from primp_project.planning.load_capacity import LoadObservation
            old_revision = self.certificate_estimator.certificate.revision
            certificate = self.certificate_estimator.update(LoadObservation(
                t-self.origin, float(normal[0]), bool(contacts[0]), feet[0],
                self.env.feet_vel(frame='world').FL))
            self.certificate_force_n = certificate.certified_load_n
            self.certificate_valid = certificate.valid
            self.certificate_update = certificate.revision != old_revision
            if certificate.valid:
                self.probe_evidence_start_time_s = certificate.evidence_start_s
                self.probe_evidence_end_time_s = certificate.evidence_end_s
            if elapsed >= 2. and self.certificate_valid:
                self.enter('probe_release', t)
            elif elapsed > 5.:
                raise RuntimeError('No stable measured probing load established')
        elif self.phase == 'probe_release' and elapsed >= 2.:
            if self.guarded(normal[0] <= self.certificate_force_n-.5, t, .2):
                self.enter('plan', t)
            elif elapsed > 5.:
                raise RuntimeError('Probe load did not settle within certified future limit')
        elif self.phase == 'safe_stop' and elapsed >= 3.:
            self.experiment_complete = True
        elif self.phase == 'progress_shift' and elapsed >= 5.:
            if self.guarded(np.linalg.norm(com[:2]-self.progress_target[:2]) < .008
                            and np.linalg.norm(velocity) < .025, t, .3):
                self.enter('next_unload', t)
            elif elapsed > 9.:
                raise RuntimeError('Certified body movement did not settle')
        elif self.phase == 'next_unload' and elapsed >= 3.:
            if self.guarded(normal[self.next_leg] < 3., t, .1):
                self.enter('next_lift', t)
            elif elapsed > 5.:
                raise RuntimeError('Next leg did not unload')
        elif self.phase == 'next_lift' and elapsed >= 2.:
            if self.guarded(not contacts[self.next_leg] and feet[self.next_leg,2]-self.next_lift_anchor[2] > .025, t, .2):
                self.enter('progress_hold', t)
            elif elapsed > 4.:
                raise RuntimeError('Next leg did not establish airborne clearance')
        elif self.phase == 'progress_hold':
            progressed = (com[0]-self.probe_origin_com[0] >= .03 and
                          not contacts[self.next_leg] and
                          feet[self.next_leg,2]-self.next_lift_anchor[2] >= .02)
            if self.guarded(progressed, t, 1.2):
                self.enter('progress_complete', t)
            elif elapsed > 5.:
                raise RuntimeError('Meaningful forward motion and second-leg lift were not sustained')
        elif self.phase == 'progress_complete' and elapsed >= 1.:
            self.experiment_complete = True

    def references(self, t):
        phase, elapsed = self.phase, t-self.phase_start
        if phase in ('stand','shift','unload','lift','hold','lower','confirm','reload','recenter','complete'):
            super().references(t)
            self.force_caps = np.full(4,self.weight)
            self.force_caps[0] = self.force_cap
            self.force_floors = np.zeros(4)
            self.blends = np.array([self.unload_blend,0.,0.,0.])
            self.desired_feet = self.anchors.copy()
            self.desired_feet[0] = self.foot_target
            self.desired_velocities = np.zeros((4,3))
            self.desired_accelerations = np.zeros((4,3))
            self.desired_velocities[0], self.desired_accelerations[0] = self.foot_velocity, self.foot_acceleration
            return
        self.com_target = self.landed_body.copy()
        self.com_velocity = np.zeros(3)
        self.planned = np.ones(4,dtype=int)
        self.force_caps = np.full(4,self.weight)
        self.force_floors = np.zeros(4)
        self.blends = np.zeros(4)
        self.desired_feet = self.anchors.copy()
        self.desired_velocities = np.zeros((4,3))
        self.desired_accelerations = np.zeros((4,3))
        usable = max(0., self.certificate_force_n-self.tracking_reserve_n)
        if phase in ('probe_ramp','probe_hold'):
            command = float(smooth_motion(self.probe_initial_force,self.achieved_probe_command_n,elapsed,4.)[0]) if phase=='probe_ramp' else self.achieved_probe_command_n
            self.force_caps[0] = command+.2
            self.force_floors[0] = max(0.,command-.2)
        elif phase == 'probe_release':
            self.force_caps[0] = float(smooth_motion(self.release_start_cap,usable,elapsed,2.)[0])
        else:
            self.force_caps[0] = usable
        if phase == 'progress_shift':
            self.com_target,self.com_velocity,_ = smooth_motion(self.move_start,self.progress_target,elapsed,5.)
        elif phase in ('next_unload','next_lift','progress_hold','progress_complete'):
            self.com_target = self.progress_target.copy()
            if phase == 'next_unload':
                f=float(smooth_motion(0.,1.,elapsed,3.)[0])
                self.force_caps[self.next_leg]=(1-f)*self.next_unload_start
                self.blends[self.next_leg]=f
            else:
                self.planned[self.next_leg]=0
                self.force_caps[self.next_leg]=0.
                self.blends[self.next_leg]=1.
                high=self.next_lift_anchor+np.array([0.,0.,.03])
                if phase=='next_lift':
                    p,v,a=smooth_motion(self.next_lift_anchor,high,elapsed,2.)
                    self.desired_feet[self.next_leg]=p
                    self.desired_velocities[self.next_leg]=v
                    self.desired_accelerations[self.next_leg]=a
                else:
                    self.desired_feet[self.next_leg]=high
        self.commanded_next_leg_lift_m=float(self.desired_feet[self.next_leg,2]-self.next_lift_anchor[2])
        self.force_cap=float(self.force_caps[0])
        self.unload_blend=float(self.blends[0])
        self.foot_target=self.desired_feet[0].copy()
        self.foot_velocity=self.desired_velocities[0].copy()
        self.foot_acceleration=self.desired_accelerations[0].copy()

    def compute_actions(self, *args, **kwargs):
        a = self.command_signature.bind(self, *args, **kwargs).arguments
        t = float(self.env.simulation_time)
        feet = stack_legs(a['feet_pos'])
        com = self.physical_com()
        contacts, _, normal, _ = ground_contacts(self.env.mjModel, self.env.mjData, self.feet_ids)
        self.update_phase(t, feet, com, contacts, normal, a['base_lin_vel'])
        self.references(t)
        if t-self.origin > 3 and (np.max(np.abs(a['base_ori_euler_xyz'][:2])) > np.deg2rad(8) or a['base_pos'][2] < .22):
            raise RuntimeError("Body stability limit exceeded")
        wb = self.wb_interface
        wb.previous_contact = wb.current_contact.copy()
        wb.current_contact = self.planned.copy()
        wb.stc.swing_time = [t-self.phase_start if flag == 0 else 0. for flag in self.planned]
        desired = self.desired_feet.copy()
        wb.last_des_foot_pos = LegsAttr(**dict(zip(LEGS, desired)))
        state = dict(position=com, linear_velocity=self.env.mjData.subtree_linvel[0].copy(), orientation=a['base_ori_euler_xyz'], angular_velocity=a['base_ang_vel'])
        reference = dict(ref_position=self.com_target, ref_linear_velocity=self.com_velocity,
                         ref_orientation=getattr(self, 'body_orientation_ref', np.zeros(3)),
                         ref_angular_velocity=np.zeros(3))
        for i, leg in enumerate(LEGS):
            state[f'foot_{leg}'] = feet[i]
            reference[f'ref_foot_{leg}'] = desired[i:i+1]
            reference[f'ref_foot_{leg}_constraints'] = None
        controller = self.srbd_controller_interface.controller
        period = round(1/(self.mpc_frequency*a['simulation_dt']))
        self.mpc_updated = a['step_num'] % period == 0 or self.last_solve_planned is None or not np.array_equal(self.planned, self.last_solve_planned)
        if self.mpc_updated:
            solver = controller.acados_ocp_solver
            upper = controller.ocp.constraints.uh.copy()
            lower = controller.ocp.constraints.lh.copy()
            upper[[4, 9, 14, 19]] = self.force_caps
            lower[[4, 9, 14, 19]] = self.force_floors
            for j in range(controller.horizon):
                solver.constraints_set(j, 'uh', upper)
                solver.constraints_set(j, 'lh', lower)
                solver.cost_set(j, 'W', self.W)
            solver.cost_set(controller.horizon, 'W', self.W_e)
            sequence = np.repeat(self.planned[:, None], controller.horizon, axis=1)
            force, footholds, predicted, status = controller.compute_control(
                state, reference, sequence, inertia=a['inertia'], mass=self.mass)
            qp = np.asarray(solver.get_stats('qp_stat'))
            if status not in (0, 2) or np.any(qp != 0) or not np.all(np.isfinite(force)):
                raise RuntimeError(f"MPC solve failed: status={status}, QP={qp}")
            if force[2] > self.force_cap + 1. or force[2] < -1.:
                raise RuntimeError(f"MPC force cap violated: {force[2]} > {self.force_cap}")
            self.nmpc_GRFs = LegsAttr(**{leg: force[3*i:3*i+3]*self.planned[i] for i, leg in enumerate(LEGS)})
            self.nmpc_footholds = LegsAttr(**dict(zip(LEGS, footholds)))
            self.nmpc_predicted_state = predicted
            self.last_solve_planned = self.planned.copy()
            self.solved_force_cap = self.force_cap
            self.solved_force_caps = self.force_caps.copy()
        tau = a['tau']
        for i, leg in enumerate(LEGS):
            idx = a['legs_qvel_idx'][leg]
            J = a['feet_jac'][leg][:, idx]
            # Inverse-dynamics bias supports leg self-weight during unloading/hold.
            value = -J.T @ self.nmpc_GRFs[leg] + a['legs_qfrc_bias'][leg]
            if self.blends[i] > 0:
                error = desired[i]-feet[i]
                velocity_error = self.desired_velocities[i]-a['feet_vel'][leg]
                feedback = wb.stc.position_gain_fb*error + wb.stc.velocity_gain_fb*velocity_error
                acceleration = self.desired_accelerations[i]+feedback
                Jdot = a['feet_jac_dot'][leg][:, idx]
                correction = J.T @ feedback + a['legs_mass_matrix'][leg] @ np.linalg.pinv(J) @ (acceleration-Jdot @ a['qvel'][idx])
                value += self.blends[i]*correction
            if wb.stc.use_friction_compensation:
                value -= a['legs_qfrc_passive'][leg]
            tau[leg] = value
        self.quadrupedpympc_observables = {
            'ref_base_height': self.com_target[2], 'ref_base_angles': reference['ref_orientation'],
            'ref_feet_pos': wb.last_des_foot_pos, 'nmpc_GRFs': self.nmpc_GRFs,
            'nmpc_footholds': self.nmpc_footholds, 'swing_time': wb.stc.swing_time,
            'phase_signal': wb.pgg.phase_signal, 'lift_off_positions': LegsAttr(**dict(zip(LEGS, self.anchors))),
        }
        return tau
