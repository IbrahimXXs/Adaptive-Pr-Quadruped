"""Reproduce geometric necessity and static reach checks, without a controller."""
from dataclasses import asdict
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.optimize import least_squares

from primp_project.environment.weak_pad import WeakPadEnv, WeakPadInitialState, WeakPadSpec
from primp_project.planning.load_capacity import (
    CapacityPlanningConfig, LoadCertificate, MatchedCapacityPlanner, solve_load_allocation,
)


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


def static_pose(model, anchors, target_com, forces, *, lift_fr=False):
    data = mujoco.MjData(model)
    foot_ids = [model.geom(leg).id for leg in ("FL", "FR", "RL", "RR")]
    base_id = model.body("base").id
    qpos_ids = np.r_[np.arange(3), np.arange(7, model.nq)]
    qvel_ids = np.r_[np.arange(3), np.arange(6, model.nv)]
    key = model.key_qpos[0].copy()
    low = np.r_[[-.3, -.3, .22], model.jnt_range[1:, 0]+1e-5]
    high = np.r_[[.3, .3, .36], model.jnt_range[1:, 1]-1e-5]
    targets = anchors.copy()
    if lift_fr:
        targets[1, 2] += .03
    jacobian = np.zeros((3, model.nv))

    def restore(value):
        data.qpos[:] = key
        data.qpos[qpos_ids] = value
        data.qvel[:] = 0.
        mujoco.mj_forward(model, data)

    def residual(value):
        restore(value)
        return np.r_[(data.geom_xpos[foot_ids]-targets).ravel(), data.subtree_com[base_id]-target_com]

    def derivative(value):
        restore(value)
        rows = []
        for foot_id in foot_ids:
            mujoco.mj_jacGeom(model, data, jacobian, None, foot_id)
            rows.append(jacobian[:, qvel_ids].copy())
        mujoco.mj_jacSubtreeCom(model, data, jacobian, base_id)
        return np.vstack([*rows, jacobian[:, qvel_ids].copy()])

    guess = key[qpos_ids].copy()
    guess[:2], guess[2] = target_com[:2], .28
    solution = least_squares(residual, guess, jac=derivative, bounds=(low, high),
        xtol=1e-13, ftol=1e-13, gtol=1e-13, max_nfev=300)
    maximum_error = float(np.max(np.abs(residual(solution.x))))
    external = np.zeros(model.nv)
    for foot_id, force in zip(foot_ids, forces, strict=True):
        mujoco.mj_jacGeom(model, data, jacobian, None, foot_id)
        external += jacobian.T@np.array([0., 0., force])
    required = data.qfrc_bias-external
    torques = required[6:]
    # Go2 uses unit-gear motors with control bounds, not actuator-force bounds.
    # Disabled forcerange entries are zeros and must not be treated as limits.
    assert np.all(model.actuator_gear[:, 0] == 1.)
    low_torque = np.where(model.actuator_ctrllimited, model.actuator_ctrlrange[:, 0], -np.inf)
    high_torque = np.where(model.actuator_ctrllimited, model.actuator_ctrlrange[:, 1], np.inf)
    low_torque = np.maximum(low_torque, np.where(model.actuator_forcelimited, model.actuator_forcerange[:, 0], -np.inf))
    high_torque = np.minimum(high_torque, np.where(model.actuator_forcelimited, model.actuator_forcerange[:, 1], np.inf))
    bounded = bool(np.all(torques >= low_torque) and np.all(torques <= high_torque))
    return dict(kinematic_residual_max_m=maximum_error,
        joint_margin_rad=float(np.min(np.minimum(solution.x[3:]-low[3:], high[3:]-solution.x[3:]))),
        max_joint_torque_nm=float(np.max(np.abs(torques))),
        all_actuator_force_bounds_satisfied=bounded,
        effective_actuator_torque_bounds_nm=np.c_[low_torque, high_torque],
        free_base_equilibrium_residual_max=float(np.max(np.abs(required[:6]))),
        target_com_w=target_com, actual_com_w=data.subtree_com[base_id].copy(),
        body_pos_w=data.qpos[:3].copy(), forces_n=forces,
        qpos=data.qpos.copy(), foot_pos_w=data.geom_xpos[foot_ids].copy(),
        required_joint_torque_nm=torques.copy(),
        passed=bool(maximum_error < 1e-8 and bounded and np.max(np.abs(required[:6])) < 1e-7))


def verify(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    initial = WeakPadInitialState(foot_offsets_xy_m=(
        (-.035, -.020), (-.035, -.020), (.035, .020), (.035, -.020)))
    config = CapacityPlanningConfig(next_lift_leg=1, forward_progress_m=.04,
        minimum_support_force_n=12., probe_posture_adjustment_m=.10,
        probe_force_ceiling_n=60., requested_probe_load_n=60., maximum_probe_request_n=60.)
    env = WeakPadEnv(WeakPadSpec(failure_load_n=70.), directory/"necessity_scene", initial_state=initial)
    try:
        env.reset(random=False, seed=17)
        mujoco.mj_forward(env.mjModel, env.mjData)
        model = env.mjModel
        feet = np.asarray([env.mjData.geom_xpos[env._feet_geom_id[leg]] for leg in ("FL", "FR", "RL", "RR")])
        anchors = feet.copy()
        anchors[0, :2] = env.landing_pad_geometry["target_xy_m"]
        anchors[:, 2] = env.landing_pad_geometry["foot_radius_m"]
        weight = float(model.body_mass.sum()*9.81)
        com_height = float(env.mjData.subtree_com[model.body("base").id, 2]+.28-env.mjData.qpos[2])
        origin = np.r_[feet[1:, :2].mean(axis=0)+[-.04, 0.], com_height]
        upper = np.full(4, weight)
        planner = MatchedCapacityPlanner("adaptive_probe", config)
        minimum = planner.minimum_future_allocation(anchors, weight, origin, upper)
        fixed, fixed_maximum = planner.probe_allocation(anchors, weight, origin, 60., upper, allow_posture_change=False)
        moved, moved_maximum = planner.probe_allocation(anchors, weight, origin, 60., upper, allow_posture_change=True)
        initial_test, _ = planner.probe_allocation(anchors, weight, origin, 12., upper, allow_posture_change=False)
        ideal = solve_load_allocation(anchors, weight, origin, np.zeros(4), upper, maximize_leg=0)
        predicted_certificate = LoadCertificate(valid=True, certified_load_n=moved.forces_n[0]-1.,
            force_cap_n=moved.forces_n[0]-9., measurement_margin_n=1., tracking_margin_n=8.)
        future = planner.decide(predicted_certificate, anchors, weight, origin, upper, allow_additional_probe=False)
        poses = dict(initial_probe=static_pose(model, anchors, origin, initial_test.forces_n),
            moved_probe=static_pose(model, anchors, moved.com_position_w, moved.forces_n),
            future_lift=static_pose(model, anchors, future.body_target_w, future.allocated_forces_n, lift_fr=True))
        proof = dict(case="necessity_geometry", initial_state=asdict(initial),
            method="Deterministic MuJoCo reset/forward kinematics and static LP/IK; no controller trajectory or settling",
            model_mass_kg=float(model.body_mass.sum()), weight_n=weight,
            reset_feet_pos_w=feet, post_landing_anchors_w=anchors,
            initial_probe_com_w=origin, nominal_base_height_m=.28, planning_config=asdict(config),
            fixed_raw_maximum_probe_n=fixed_maximum, moved_raw_maximum_probe_n=moved_maximum,
            moved_robust_probe_n=float(moved.forces_n[0]),
            moved_usable_cap_after_1N_measurement_and_8N_tracking_n=float(moved.forces_n[0]-9.),
            minimum_future_weak_load_n=float(minimum.forces_n[0]),
            ideal_fixed_maximum_without_force_floors_n=float(ideal.forces_n[0]),
            static_pose_feasibility=poses,
            static_feasibility_convention="Predicted static loading is not a measured certificate or closed-loop robustness guarantee",
            necessity_confirmed=bool(fixed_maximum < minimum.forces_n[0]
                and ideal.forces_n[0] < minimum.forces_n[0] < moved.forces_n[0]-9.),
            all_static_pose_checks_passed=all(value["passed"] for value in poses.values()))
        for name, value in (("minimum_future", minimum), ("fixed_probe", fixed), ("moved_probe", moved), ("ideal_fixed_probe", ideal)):
            proof[name] = asdict(value)
        parameters = dict(strategy="adaptive_probe", scenario="necessity_geometry", failure_threshold_n=70.,
            initial_probe_force_n=12., requested_probe_force_n=60., maximum_probe_force_n=60.,
            measurement_reserve_n=1., tracking_reserve_n=8., planning_config=asdict(config),
            probe_offset_xy_m=[-.04, 0.], initial_state=asdict(initial), seed=17, role="development")
        (directory/"necessity_development_parameters.json").write_text(json.dumps(parameters, indent=2)+"\n")
        (directory/"necessity_geometry.json").write_text(json.dumps(json_value(proof), indent=2)+"\n")
        return proof
    finally:
        env.close()


if __name__ == "__main__":
    report = verify(Path(__file__).resolve().parent)
    print(json.dumps({key: report[key] for key in ("necessity_confirmed", "all_static_pose_checks_passed",
        "fixed_raw_maximum_probe_n", "minimum_future_weak_load_n", "moved_robust_probe_n")}, indent=2))
