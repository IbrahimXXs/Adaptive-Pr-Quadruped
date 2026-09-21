"""Execute blind, sensor-conditioned landing references with the existing MPC."""

from time import perf_counter
import numpy as np
from primp_project.control.controlled_step import ControlledStepWrapper, smooth_motion, support_margin
from primp_project.planning import (
    SensorObservation, SensorStream, LandingContext, GroundHeightBelief,
    ReactivePlanner, ConventionalPredictivePlanner, LearnedMotionPlanner, FeasibilityProjector,
)


class LandingPadWrapper(ControlledStepWrapper):
    def __init__(self, env, *, initial_estimate_m, planner_name, lower_duration_s,
                 sensor_profile, model=None, **kwargs):
        super().__init__(env, cycles=1, hold_seconds=5., **kwargs)
        # This whitelist contains geometry known before a trial, never pad truth.
        geometry = env.landing_pad_geometry
        self.target_xy = np.array(geometry['target_xy_m'])
        self.foot_radius = float(geometry['foot_radius_m'])
        self.initial_estimate = initial_estimate_m
        self.planner_name, self.lower_duration = planner_name, lower_duration_s
        self.sensor_stream = SensorStream(sensor_profile)
        self.model = model
        self.belief = self.planner = self.context = self.projector = None
        self.sensor_observation = None
        self.body_orientation_ref = np.zeros(3)
        self.planner_updated = False
        self.planner_compute_time = 0.
        self.remaining_time = lower_duration_s
        self.landing_frozen = False
        self.lower_start = None

    def enter(self, phase, t):
        if phase == 'lower':
            obs = self.sensor_observation
            self.lower_start = t
            self.context = LandingContext(
                initial_height_estimate=self.initial_estimate, foot_radius=self.foot_radius,
                start_time_s=t, start_foot_position=self.foot_target,
                start_com_position=self.com_target, start_body_rpy=self.body_orientation_ref,
                target_xy=self.target_xy, nominal_duration_s=self.lower_duration)
            self.belief = GroundHeightBelief(self.context)
            if self.planner_name == 'reactive':
                self.planner = ReactivePlanner(self.context)
            elif self.planner_name == 'predictive':
                self.planner = ConventionalPredictivePlanner(self.context)
            else:
                if self.model is None:
                    raise ValueError('Learned planner requires a fitted model')
                self.planner = LearnedMotionPlanner(self.context, self.model)
            self.projector = FeasibilityProjector(self.context)
            self.segment_start = self.segment_end = self.projector.previous
            self.next_plan_time = self.segment_time = t
        elif phase == 'reload':
            self.landed_body = self.com_target.copy()
            self.landed_orientation = self.body_orientation_ref.copy()
            self.anchors[0] = self.sensor_observation.foot_position
        super().enter(phase, t)

    def update_phase(self, t, feet, com, contacts, normal, velocity):
        self.planner_updated = False
        self.sensor_observation = self.sensor_stream.observe(SensorObservation(
            time_s=t, com_position=com, com_velocity=self.env.mjData.subtree_linvel[0],
            body_rpy=self.env.base_ori_euler_xyz, foot_position=feet[0],
            foot_velocity=self.env.feet_vel(frame='world').FL,
            contacts=contacts, normal_forces=normal, support_anchors=self.anchors[1:]))
        obs = self.sensor_observation
        if self.belief is not None:
            self.belief.update(obs)
        if self.phase not in ('lower', 'confirm'):
            return super().update_phase(t, feet, com, contacts, normal, velocity)
        self.margin = support_margin(com, feet[1:])
        if not (np.all(contacts[1:]) and np.all(normal[1:] > 5.) and self.margin > .02):
            raise RuntimeError('Three-leg support lost during landing/search')
        touching = bool(obs.contacts[0] and obs.normal_forces[0] >= 2.)
        if touching:
            if self.contact_dwell_since is None:
                self.contact_dwell_since = t
            self.landing_dwell = t-self.contact_dwell_since
            self.landing_frozen = True
            if self.phase == 'lower':
                self.enter('confirm', t)
            elif self.landing_dwell >= .1-1e-9:
                self.contact_confirmed = True
                self.landing_target = self.foot_target.copy()
                self.enter('reload', t)
        else:
            self.contact_dwell_since, self.landing_dwell = None, 0.
            self.landing_frozen = False
            if self.phase == 'lower' and t-self.lower_start >= self.lower_duration:
                self.enter('confirm', t)
        if self.phase in ('lower', 'confirm') and t-self.lower_start > self.lower_duration+8.:
            raise RuntimeError('No confirmed landing within bounded descent/time limits')

    def references(self, t):
        phase, elapsed = self.phase, t-self.phase_start
        if phase in ('lower', 'confirm'):
            self.planned = np.array([0, 1, 1, 1])
            self.force_cap, self.unload_blend = 0., 1.
            if self.landing_frozen:
                self.com_velocity = np.zeros(3)
                self.foot_velocity = self.foot_acceleration = np.zeros(3)
                return
            if t >= self.next_plan_time-1e-9:
                start = perf_counter()
                proposed = self.planner.plan(self.sensor_observation, self.belief)
                self.segment_start = self.segment_end
                self.segment_end = self.projector.project(proposed, self.sensor_observation)
                self.segment_time = t
                self.next_plan_time = t+self.context.planning_dt
                self.planner_compute_time = perf_counter()-start
                self.planner_updated = True
                self.remaining_time = self.segment_end.remaining_time_s
            # Linear position interpolation preserves the shared speed bounds;
            # velocity is the same segment slope used by the Cartesian tracker.
            dt = self.context.planning_dt
            u = np.clip((t-self.segment_time)/dt, 0., 1.)
            a, b = self.segment_start, self.segment_end
            self.com_target = (1-u)*a.com_position+u*b.com_position
            self.com_velocity = (b.com_position-a.com_position)/dt
            self.body_orientation_ref = (1-u)*a.body_rpy+u*b.body_rpy
            self.foot_target = (1-u)*a.foot_position+u*b.foot_position
            self.foot_velocity = (b.foot_position-a.foot_position)/dt
            self.foot_acceleration = np.zeros(3)
            return
        super().references(t)
        high = self.foot_anchor + np.array([0., 0., self.lift_height])
        high[:2] = self.target_xy
        if phase == 'lift':
            self.foot_target, self.foot_velocity, self.foot_acceleration = smooth_motion(self.foot_anchor, high, elapsed, 2.)
        elif phase == 'hold':
            self.foot_target = high
        elif phase == 'reload':
            self.com_target = self.landed_body.copy()
            self.body_orientation_ref = self.landed_orientation.copy()
        elif phase == 'recenter':
            self.com_target, self.com_velocity, _ = smooth_motion(self.landed_body, self.center_target, elapsed, 4.)
            self.body_orientation_ref = smooth_motion(self.landed_orientation, np.zeros(3), elapsed, 4.)[0]
            self.foot_target = self.anchors[0].copy()
        elif phase == 'complete':
            self.foot_target = self.anchors[0].copy()
            self.body_orientation_ref = np.zeros(3)
