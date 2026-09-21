"""A contact-gated, nonperiodic front-left step on known flat ground.

This wrapper deliberately bypasses the periodic gait/terrain/swing generators.
It retains the nominal centroidal MPC and its robot model, with experiment-local
XY costs, binary support masks, force bounds, and Cartesian leg control.
"""

import inspect
import numpy as np
from gym_quadruped.utils.quadruped_utils import LegsAttr

from quadruped_pympc import config as cfg
from quadruped_pympc.quadruped_pympc_wrapper import QuadrupedPyMPC_Wrapper
from primp_project.recorder import LEGS, ground_contacts, stack_legs


def smooth_motion(start, end, elapsed, duration):
    """Quintic interpolation with zero endpoint velocity and acceleration."""
    u = np.clip(elapsed / duration, 0.0, 1.0)
    delta = np.asarray(end) - np.asarray(start)
    s = 10*u**3 - 15*u**4 + 6*u**5
    ds = (30*u**2 - 60*u**3 + 30*u**4) / duration
    dds = (60*u - 180*u**2 + 120*u**3) / duration**2
    return np.asarray(start) + s*delta, ds*delta, dds*delta


def support_margin(point, feet):
    """Signed shortest edge distance to a convex three-foot support triangle."""
    vertices = np.asarray(feet)[:, :2]
    center = vertices.mean(axis=0)
    vertices = vertices[np.argsort(np.arctan2(vertices[:, 1]-center[1], vertices[:, 0]-center[0]))]
    edge = np.roll(vertices, -1, axis=0) - vertices
    offset = np.asarray(point)[:2] - vertices
    cross = edge[:, 0]*offset[:, 1] - edge[:, 1]*offset[:, 0]
    return float(np.min(cross / np.linalg.norm(edge, axis=1)))


class ControlledStepWrapper(QuadrupedPyMPC_Wrapper):
    def __init__(self, env, *, cycles=3, hold_seconds=6.0, **kwargs):
        super().__init__(**kwargs)
        self.env = env
        self.cycles = cycles
        self.hold_seconds = hold_seconds
        self.lift_height = .03
        self.phase = "stand"
        self.phase_start = float(env.simulation_time)
        self.origin = self.phase_start
        self.cycle = 1
        self.completed_cycles = 0
        self.experiment_complete = False
        self.events = []
        self.guard_since = None
        self.contact_confirmed = False
        self.landing_dwell = 0.0
        self.contact_dwell_since = None
        self.mass = float(env.mjModel.body_mass.sum())
        self.weight = self.mass * 9.81
        self.feet_ids = np.array([env._feet_geom_id[leg] for leg in LEGS])
        self.anchors = stack_legs(env.feet_pos(frame="world"))
        self.center_target = self.physical_com()
        self.center_target[2] += cfg.simulation_params['ref_z'] - env.base_pos[2]
        self.tripod_target = self.center_target.copy()
        self.com_target = self.center_target.copy()
        self.com_velocity = np.zeros(3)
        self.foot_anchor = self.anchors[0].copy()
        self.foot_target = self.foot_anchor.copy()
        self.foot_velocity = np.zeros(3)
        self.foot_acceleration = np.zeros(3)
        self.force_cap = self.weight
        self.unload_blend = 0.0
        self.planned = np.ones(4, dtype=int)
        self.last_solve_planned = None
        self.solved_force_cap = self.force_cap
        self.margin = support_margin(self.physical_com(), self.anchors[1:])
        self.command_signature = inspect.signature(QuadrupedPyMPC_Wrapper.compute_actions)
        controller = self.srbd_controller_interface.controller
        if (controller.use_foothold_constraints or controller.use_stability_constraints
                or controller.use_DDP or controller.use_RTI or cfg.mpc_params['optimize_step_freq']):
            raise ValueError("Controlled step requires the existing nominal SQP controller without optional constraint/gait variants")
        self.W = controller.ocp.cost.W.copy()
        self.W_e = controller.ocp.cost.W_e.copy()
        self.W[0, 0] = self.W[1, 1] = 2000.0
        self.W_e[0, 0] = self.W_e[1, 1] = 2000.0

    def physical_com(self):
        return np.sum(self.env.mjModel.body_mass[:, None] * self.env.mjData.xipos, axis=0) / self.mass

    def enter(self, phase, t):
        self.events.append({"time_s": t-self.origin, "cycle": self.cycle,
                            "from": self.phase, "to": phase})
        self.phase, self.phase_start, self.guard_since = phase, t, None
        print(f"Step {self.cycle}/{self.cycles}: {phase} at {t-self.origin:.3f} s", flush=True)

    def guarded(self, condition, t, dwell=.2):
        if not condition:
            self.guard_since = None
        elif self.guard_since is None:
            self.guard_since = t
        return self.guard_since is not None and t-self.guard_since >= dwell-1e-9

    def update_phase(self, t, feet, com, contacts, normal, velocity):
        elapsed = t-self.phase_start
        self.margin = support_margin(com, feet[1:])
        stable_three = np.all(contacts[1:]) and np.all(normal[1:] > 5) and self.margin > .02
        if self.phase == "stand" and elapsed >= 3:
            if self.guarded(np.all(contacts) and np.linalg.norm(velocity) < .02, t):
                self.anchors = feet.copy()
                self.foot_anchor = feet[0].copy()
                self.tripod_target = self.center_target.copy()
                self.tripod_target[:2] = feet[1:, :2].mean(axis=0)
                self.enter("shift", t)
            elif elapsed > 6:
                raise RuntimeError("Four-foot stand did not settle")
        elif self.phase == "shift" and elapsed >= 4:
            if self.guarded(stable_three and np.linalg.norm(velocity) < .02, t):
                self.unload_initial_cap = max(float(normal[0]), float(self.nmpc_GRFs.FL[2]), 5.)
                self.enter("unload", t)
            elif elapsed > 8:
                raise RuntimeError(f"Body shift did not establish tripod margin: {self.margin:.4f} m")
        elif self.phase == "unload" and elapsed >= 3:
            if self.guarded(stable_three and normal[0] < 3.0, t, .1):
                self.enter("lift", t)
            elif elapsed > 5:
                raise RuntimeError(f"Foot did not unload: {normal[0]:.2f} N")
        elif self.phase == "lift" and elapsed >= 2:
            if self.guarded(stable_three and not contacts[0] and feet[0, 2]-self.foot_anchor[2] > .025, t):
                self.enter("hold", t)
            elif elapsed > 4:
                raise RuntimeError("Foot did not establish airborne hold")
        elif self.phase == "hold":
            if not stable_three or contacts[0] or feet[0, 2]-self.foot_anchor[2] < .02:
                raise RuntimeError("Sustained three-leg hold lost support or foot clearance")
            if elapsed >= self.hold_seconds-1e-9:
                self.enter("lower", t)
        elif self.phase in ("lower", "confirm"):
            # Require actual loading, not a geometric proximity flag alone.
            touching = bool(contacts[0] and normal[0] >= 2.)
            if touching:
                if self.contact_dwell_since is None:
                    self.contact_dwell_since = t
                self.landing_dwell = t-self.contact_dwell_since
            else:
                self.contact_dwell_since, self.landing_dwell = None, 0.
            if self.phase == "lower" and touching:
                self.enter("confirm", t)
            elif self.landing_dwell >= .1-1e-9:
                self.contact_confirmed = True
                self.landing_target = self.foot_target.copy()
                self.enter("reload", t)
            elif self.phase == "lower" and elapsed >= 4:
                self.enter("confirm", t)
            elif self.phase == "confirm" and elapsed > 2:
                raise RuntimeError("No confirmed touchdown within bounded 5 mm ground search")
        elif self.phase == "reload" and elapsed >= 3:
            if self.guarded(np.all(contacts) and np.all(normal > 5.), t):
                self.enter("recenter", t)
            elif elapsed > 5:
                raise RuntimeError("Four-foot loading was not restored")
        elif self.phase == "recenter" and elapsed >= 4:
            if self.guarded(np.all(contacts) and np.linalg.norm(velocity) < .02, t):
                self.completed_cycles += 1
                if self.completed_cycles == self.cycles:
                    self.enter("complete", t)
                else:
                    self.cycle += 1
                    self.contact_confirmed = False
                    self.contact_dwell_since, self.landing_dwell = None, 0.
                    self.enter("stand", t)
            elif elapsed > 8:
                raise RuntimeError("Body did not recenter")
        elif self.phase == "complete" and elapsed >= 2:
            self.experiment_complete = True

    def references(self, t):
        elapsed = t-self.phase_start
        phase = self.phase
        self.com_velocity = np.zeros(3)
        if phase in ("stand", "complete"):
            self.com_target = self.center_target.copy()
        elif phase == "shift":
            self.com_target, self.com_velocity, _ = smooth_motion(self.center_target, self.tripod_target, elapsed, 4.)
        elif phase == "recenter":
            self.com_target, self.com_velocity, _ = smooth_motion(self.tripod_target, self.center_target, elapsed, 4.)
        else:
            self.com_target = self.tripod_target.copy()
        high = self.foot_anchor + np.array([0, 0, self.lift_height])
        self.foot_target = self.foot_anchor.copy()
        self.foot_velocity, self.foot_acceleration = np.zeros(3), np.zeros(3)
        self.planned = np.ones(4, dtype=int)
        self.force_cap, self.unload_blend = self.weight, 0.
        if phase == "unload":
            fraction = float(smooth_motion(0., 1., elapsed, 3.)[0])
            self.force_cap = (1-fraction)*self.unload_initial_cap
            self.unload_blend = fraction
        elif phase in ("lift", "hold", "lower", "confirm"):
            self.planned[0] = 0
            self.force_cap, self.unload_blend = 0., 1.
            if phase == "lift":
                self.foot_target, self.foot_velocity, self.foot_acceleration = smooth_motion(self.foot_anchor, high, elapsed, 2.)
            elif phase == "hold":
                self.foot_target = high
            elif phase == "lower":
                self.foot_target, self.foot_velocity, self.foot_acceleration = smooth_motion(high, self.foot_anchor, elapsed, 4.)
            else:
                # A smooth, limited search supplies a small detectable contact load.
                self.foot_target, self.foot_velocity, self.foot_acceleration = smooth_motion(
                    self.foot_anchor, self.foot_anchor-np.array([0., 0., .005]), elapsed, 2.)
        elif phase == "reload":
            fraction = float(smooth_motion(0., 1., elapsed, 3.)[0])
            self.force_cap = fraction*self.weight
            self.unload_blend = 1-fraction
            self.foot_target = self.landing_target.copy()

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
        wb.stc.swing_time = [t-self.phase_start if self.planned[0] == 0 else 0., 0., 0., 0.]
        desired = self.anchors.copy()
        desired[0] = self.foot_target
        wb.last_des_foot_pos = LegsAttr(**dict(zip(LEGS, desired)))
        state = dict(position=com, linear_velocity=a['base_lin_vel'], orientation=a['base_ori_euler_xyz'], angular_velocity=a['base_ang_vel'])
        reference = dict(ref_position=self.com_target, ref_linear_velocity=self.com_velocity,
                         ref_orientation=np.zeros(3), ref_angular_velocity=np.zeros(3))
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
            upper[4] = self.force_cap
            lower[[4, 9, 14, 19]] = 0.
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
        tau = a['tau']
        for i, leg in enumerate(LEGS):
            idx = a['legs_qvel_idx'][leg]
            J = a['feet_jac'][leg][:, idx]
            # Inverse-dynamics bias supports leg self-weight during unloading/hold.
            value = -J.T @ self.nmpc_GRFs[leg] + a['legs_qfrc_bias'][leg]
            if i == 0 and self.unload_blend > 0:
                error = self.foot_target-feet[0]
                velocity_error = self.foot_velocity-a['feet_vel'][leg]
                feedback = wb.stc.position_gain_fb*error + wb.stc.velocity_gain_fb*velocity_error
                acceleration = self.foot_acceleration+feedback
                Jdot = a['feet_jac_dot'][leg][:, idx]
                correction = J.T @ feedback + a['legs_mass_matrix'][leg] @ np.linalg.pinv(J) @ (acceleration-Jdot @ a['qvel'][idx])
                value += self.unload_blend*correction
            if wb.stc.use_friction_compensation:
                value -= a['legs_qfrc_passive'][leg]
            tau[leg] = value
        self.quadrupedpympc_observables = {
            'ref_base_height': self.com_target[2], 'ref_base_angles': np.zeros(3),
            'ref_feet_pos': wb.last_des_foot_pos, 'nmpc_GRFs': self.nmpc_GRFs,
            'nmpc_footholds': self.nmpc_footholds, 'swing_time': wb.stc.swing_time,
            'phase_signal': wb.pgg.phase_signal, 'lift_off_positions': LegsAttr(**dict(zip(LEGS, self.anchors))),
        }
        return tau
