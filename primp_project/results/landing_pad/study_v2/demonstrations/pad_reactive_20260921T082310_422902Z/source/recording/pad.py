"""Aligned sensor/planner data, with simulator truth isolated for evaluation."""
import json
import hashlib
import shutil
from pathlib import Path
from dataclasses import asdict
import mujoco
import numpy as np
from primp_project import PROJECT_ROOT
from primp_project.recording.step import StepRecorder
from primp_project.recording.standing import json_value


class PadRecorder(StepRecorder):
    def __init__(self, run_dir, *, initial_estimate_m, planner, role, lower_duration_s,
                 sensor_profile, seed, rendered, model_path=None, known_height_m=None,
                 recovery_model_path=None, recovery_demonstration=False, initial_condition='nominal'):
        super().__init__(run_dir, 1, 5., seed, rendered, .8)
        self.metadata['lift_height_m'] = .035 if initial_condition == 'raised' else .03
        self.metadata.update(experiment='landing_pad', planner=planner, role=role,
            initial_height_estimate_m=initial_estimate_m, nominal_lower_duration_s=lower_duration_s,
            max_search_depth_m=.02, contact_compression_m=.004,
            sensor_profile=asdict(sensor_profile), model_path=str(model_path) if model_path else None,
            planner_frequency_hz=20., recovery_timeout_s=8., initial_condition=initial_condition,
            recovery_demonstration=bool(recovery_demonstration),
            requested_lift_height_m=.035 if initial_condition == 'raised' else .03,
            validation_version=2 if planner.startswith('matched_') else 1,
            recovery_model_path=str(recovery_model_path) if recovery_model_path else None)
        self.metadata['reference_limits'] = dict(
            max_foot_speed_m_s=.015, search_speed_m_s=.005, max_com_speed_m_s=.008,
            max_body_displacement_m=.012, target_xy_tolerance_m=.005,
            support_margin_m=.02, max_orientation_deviation_rad=float(np.deg2rad(2.)),
            max_orientation_rate_rad_s=.02, monotone_lowering=True)
        if role == 'demonstration':
            self.metadata['known_height_m'] = known_height_m
        if model_path:
            self.metadata['model_hashes_sha256'] = {
                name: hashlib.sha256((Path(model_path)/name).read_bytes()).hexdigest()
                for name in ('model.npz', 'model.json')
            }
        if recovery_model_path:
            path = Path(recovery_model_path)
            files = [path] if path.is_file() else sorted(p for p in path.iterdir() if p.is_file())
            self.metadata['recovery_model_hashes_sha256'] = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.metadata['conventions']['fallback_work'] = (
            'Active time and commanded foot descent/CoM travel are integrated over applied reference intervals. '
            'The preceding sample owns the interval ending at this sample; frozen or non-landing intervals do not accrue work. '
            'These are reference contributions, not physical mechanical work or count divided by planning frequency.')
        self.metadata['controller_changes']['max_downward_search_m'] = .02
        self.metadata['conventions']['information_boundary'] = (
            'Planner receives SensorObservation and initial estimate only; evaluation/scene truth is never provided.')

    def start(self, env, cfg):
        super().start(env, cfg)
        self.metadata['evaluation'] = json_value(env.landing_pad_evaluation)
        self.metadata['evaluation']['actual_pad_height_m'] = env.landing_pad_evaluation['true_height_m']
        self.metadata['landing_target_xy_m'] = env.landing_pad_geometry['target_xy_m']
        self.metadata['foot_radius_m'] = env.landing_pad_geometry['foot_radius_m']
        self.pad_geom_id = env.landing_pad_evaluation['landing_geom_id']
        self.fl_geom_id = env._feet_geom_id['FL']
        (self.run_dir/'evaluation.json').write_text(json.dumps(self.metadata['evaluation'], indent=2)+'\n')
        for folder in ('environment', 'planning', 'learning'):
            shutil.copytree(PROJECT_ROOT/folder, self.run_dir/'source'/folder, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('control/landing_pad.py', 'recording/pad.py', 'experiments/pad.py', 'analysis/pad.py', 'analysis/adaptation.py'):
            target = self.run_dir/'source'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT/name, target)

    def record_step(self, env, wrapper, *args, **kwargs):
        super().record_step(env, wrapper, *args, **kwargs)
        obs, belief = wrapper.sensor_observation, wrapper.belief
        posterior = belief.summary() if belief else dict(mean=self.metadata['initial_height_estimate_m'], std=.007,
            lower=self.metadata['initial_height_estimate_m']-.02, upper=self.metadata['initial_height_estimate_m']+.02, missing_contact=False)
        target_contact, target_force = False, 0.
        for i, contact in enumerate(self.data.contact):
            if {int(contact.geom1), int(contact.geom2)} == {self.fl_geom_id, self.pad_geom_id} and contact.efc_address >= 0:
                force = np.zeros(6)
                mujoco.mj_contactForce(self.model, self.data, i, force)
                target_contact = True
                target_force += max(0., float(force[0]))
        values = dict(
            belief_mean_m=posterior['mean'], belief_std_m=posterior['std'],
            belief_lower_m=posterior['lower'], belief_upper_m=posterior['upper'], missing_contact=posterior['missing_contact'],
            sensor_contact=obs.contacts, sensor_normal_force=obs.normal_forces,
            sensor_foot_pos_w=obs.foot_position, sensor_measurement_time_s=obs.measurement_time_s-wrapper.origin,
            planner_update=wrapper.planner_updated, planner_remaining_time_s=wrapper.remaining_time,
            planner_com_target_w=wrapper.com_target, planner_foot_target_w=wrapper.foot_target,
            planner_body_rpy=wrapper.body_orientation_ref, planner_compute_time_s=wrapper.planner_compute_time,
            reference_projection_count=wrapper.projector.clipped_references if wrapper.projector else 0,
            planner_fallback_count=wrapper.planner.fallback_count if wrapper.planner else 0,
            target_pad_contact=target_contact, target_pad_normal_force=target_force,
            foot_bottom_z_w=self.rows['feet_pos_w'][-1][0,2]-wrapper.foot_radius)
        proposal = getattr(wrapper, 'proposed_reference', None)
        values.update(
            planner_proposed_com_w=proposal.com_position if proposal else wrapper.com_target,
            planner_proposed_foot_w=proposal.foot_position if proposal else wrapper.foot_target,
            planner_proposed_body_rpy=proposal.body_rpy if proposal else wrapper.body_orientation_ref,
            learned_phase=getattr(wrapper.planner, 'phase', 0.),
            learned_duration_s=getattr(wrapper.planner, 'duration_s', 0.),
            planner_conditioning_count=getattr(wrapper.planner, 'conditioning_updates', 0),
            predictive_optimization_failures=getattr(wrapper.planner, 'optimization_failures', 0))
        planner = wrapper.planner
        landing = wrapper.phase in ('lower', 'confirm')
        fallback_active = landing and not wrapper.landing_frozen and bool(getattr(planner, 'fallback_active', False))
        active_s = descent_m = body_travel_m = 0.
        if self.rows.get('planner_fallback_active') and self.rows['planner_fallback_active'][-1] and landing:
            interval = max(0., float(self.rows['control_time_s'][-1])-float(self.rows['control_time_s'][-2]))
            active_s = interval
            descent_m = max(0., float(self.rows['planner_foot_target_w'][-1][2])-float(wrapper.foot_target[2]))
            body_travel_m = float(np.linalg.norm(wrapper.com_target-self.rows['planner_com_target_w'][-1]))
        values.update(
            sensor_com_pos_w=obs.com_position, sensor_com_vel_w=obs.com_velocity,
            sensor_body_rpy=obs.body_rpy, sensor_foot_vel_w=obs.foot_velocity,
            planner_fallback_active=fallback_active,
            planner_fallback_reason=str(getattr(planner, 'fallback_reason', '')),
            fallback_interval_s=active_s, fallback_foot_descent_m=descent_m,
            fallback_com_travel_m=body_travel_m,
            model_remaining_time_s=float(getattr(planner, 'model_remaining_time_s', 0.)),
            optimized_remaining_time_s=float(getattr(planner, 'optimized_remaining_time_s', wrapper.remaining_time)),
            feasible_remaining_time_s=float(getattr(planner, 'feasible_remaining_time_s', wrapper.remaining_time)),
            planner_fallback_events=int(getattr(planner, 'fallback_events', 0)),
            planner_recovery_active=bool(getattr(planner, 'recovery_active', False)),
            belief_noncontact_updates_enabled=getattr(belief, 'noncontact_updates', True) if belief else True)
        for key, value in values.items():
            self.rows[key].append(np.array(value, copy=True))
