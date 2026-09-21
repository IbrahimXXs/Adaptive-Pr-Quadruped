"""Capacity, real contact, collision geometry, and information-boundary checks."""

import json

import mujoco
import numpy as np
import pytest

from primp_project.environment.landing_pad import LANDING_GEOM, LEGS, SUPPORT_GEOMS
from primp_project.environment.weak_pad import (
    WeakPadEnv, WeakPadSpec, make_weak_pad_env, set_pad_sink_displacement, target_normal_force,
)


@pytest.fixture
def env(tmp_path):
    environment = make_weak_pad_env(WeakPadSpec(), tmp_path)
    environment.reset(random=False)
    yield environment
    environment.close()


def transition(env, force, duration=.002):
    env.mjData.time += duration
    return env._advance_weak_surface(force, duration)


def put_fl_on_target(env, penetration=.002):
    """Real kinematics/contact fixture, not a commanded force substitute."""
    target = np.r_[env.landing_pad_geometry["target_xy_m"],
                   env.weak_pad_evaluation["top_height_m"]+env.landing_pad_geometry["foot_radius_m"]-penetration]
    qpos_ids, qvel_ids = env.legs_qpos_idx["FL"], env.legs_qvel_idx["FL"]
    foot = env._feet_geom_id["FL"]
    jacobian = np.zeros((3, env.mjModel.nv))
    for _ in range(100):
        mujoco.mj_forward(env.mjModel, env.mjData)
        error = target-env.mjData.geom_xpos[foot]
        if np.linalg.norm(error) < 1e-9:
            break
        mujoco.mj_jacGeom(env.mjModel, env.mjData, jacobian, None, foot)
        env.mjData.qpos[qpos_ids] += np.clip(np.linalg.lstsq(jacobian[:, qvel_ids], error, rcond=None)[0], -.1, .1)
    mujoco.mj_forward(env.mjModel, env.mjData)
    np.testing.assert_allclose(env.mjData.geom_xpos[foot], target, atol=1e-9)


def test_strength_is_hidden_and_does_not_change_initial_geometry_or_robot(tmp_path):
    weak = WeakPadEnv(WeakPadSpec(failure_load_n=12.), tmp_path/"weak", state_obs_names=("qpos", "qvel", "feet_pos"))
    firm = WeakPadEnv(WeakPadSpec(failure_load_n=120.), tmp_path/"firm", state_obs_names=("qpos", "qvel", "feet_pos"))
    try:
        a, b = weak.reset(random=False), firm.reset(random=False)
        assert weak.landing_pad_geometry == firm.landing_pad_geometry
        for key in a:
            np.testing.assert_array_equal(a[key], b[key])
        for name in ("geom_pos", "geom_size", "geom_friction", "body_mass", "body_ipos", "body_inertia"):
            np.testing.assert_array_equal(getattr(weak.mjModel, name), getattr(firm.mjModel, name))
        assert (tmp_path/"weak/scene.xml").read_bytes() == (tmp_path/"firm/scene.xml").read_bytes()
        assert weak.mjModel.geom_bodyid[weak.mjModel.geom(LANDING_GEOM).id] == 0
        for name in (*SUPPORT_GEOMS, LANDING_GEOM):
            geom = weak.mjModel.geom(name)
            assert geom.pos[2]+geom.size[2] == pytest.approx(0.)
        public = json.dumps(weak.landing_pad_geometry)+json.dumps(weak.get_hyperparameters())
        for forbidden in ("failure_load", "overload_dwell", "sink_depth", "sink_speed", "weak_pad_evaluation"):
            assert forbidden not in public
        truth = json.loads((tmp_path/"weak/weak_pad_truth.json").read_text())
        assert truth["failure_load_n"] == 12.
        assert weak.weak_pad_evaluation["failure_time_s"] is None
        assert not weak.weak_pad_evaluation["failed"]
    finally:
        weak.close(); firm.close()


def test_threshold_is_strict_and_requires_continuous_dwell(env):
    for _ in range(20):
        transition(env, 20.)  # equality is admissible, not overload
    assert not env.weak_pad_evaluation["failed"]
    assert env.weak_pad_evaluation["overload_elapsed_s"] == 0.
    for _ in range(4):
        transition(env, 20.01)
    assert not env.weak_pad_evaluation["failed"]
    transition(env, 19.)
    assert env.weak_pad_evaluation["overload_elapsed_s"] == 0.
    for _ in range(4):
        transition(env, 23.)
    assert not env.weak_pad_evaluation["failed"]
    transition(env, 23.)
    truth = env.weak_pad_evaluation
    assert truth["failed"] and truth["overload_elapsed_s"] == pytest.approx(.010)
    assert truth["failure_trigger_force_n"] == 23.
    assert truth["failure_time_s"] == env.mjData.time
    assert truth["sink_displacement_m"] == 0.  # no retroactive sinking


def test_failure_latches_descent_is_bounded_and_supports_and_robot_are_unchanged(env):
    model = env.mjModel
    original_geoms = {name: (model.geom(name).pos.copy(), model.geom(name).size.copy()) for name in (*SUPPORT_GEOMS, "floor")}
    inertial = {name: getattr(model, name).copy() for name in ("body_mass", "body_ipos", "body_inertia")}
    qpos, qvel = env.mjData.qpos.copy(), env.mjData.qvel.copy()
    for _ in range(5):
        transition(env, 21.)
    failure_time = env.weak_pad_evaluation["failure_time_s"]
    for _ in range(100):
        transition(env, 0.)
    assert env.weak_pad_evaluation["sink_displacement_m"] == pytest.approx(.02)
    for _ in range(400):
        transition(env, 0.)
    assert env.weak_pad_evaluation["failed"]
    assert env.weak_pad_evaluation["failure_time_s"] == failure_time
    assert env.weak_pad_evaluation["sink_displacement_m"] == pytest.approx(.06)
    assert env.weak_pad_evaluation["top_height_m"] == pytest.approx(-.06)
    for name, (position, size) in original_geoms.items():
        np.testing.assert_array_equal(model.geom(name).pos, position)
        np.testing.assert_array_equal(model.geom(name).size, size)
    for name, original in inertial.items():
        np.testing.assert_array_equal(getattr(model, name), original)
    np.testing.assert_array_equal(env.mjData.qpos, qpos)
    np.testing.assert_array_equal(env.mjData.qvel, qvel)


def test_real_measured_contact_triggers_step_hook_and_observation_stays_aligned(tmp_path):
    environment = WeakPadEnv(WeakPadSpec(failure_load_n=.1, overload_dwell_s=.002), tmp_path,
                             state_obs_names=("qpos", "qvel", "feet_pos"))
    try:
        environment.reset(random=False)
        environment.mjData.qpos[2] -= .001
        put_fl_on_target(environment)
        measured = target_normal_force(environment.mjModel, environment.mjData, environment._weak_geom_id)
        assert measured > .1
        first = environment.step(np.zeros(environment.mjModel.nu))
        truth = environment.weak_pad_evaluation.copy()
        assert len(first) == 5 and truth["failed"]
        assert truth["failure_trigger_force_n"] == pytest.approx(measured)
        assert truth["sink_displacement_m"] == 0.
        second = environment.step(np.zeros(environment.mjModel.nu))
        assert environment.weak_pad_evaluation["sink_displacement_m"] == pytest.approx(.0002)
        np.testing.assert_array_equal(second[0]["qpos"], environment.mjData.qpos)
        assert environment.weak_pad_evaluation["target_normal_force_n"] == pytest.approx(
            target_normal_force(environment.mjModel, environment.mjData, environment._weak_geom_id))
        assert not any("weak" in key or "failure" in key or "sink" in key for key in second[0] | second[4])
        assert environment.mjData.time == pytest.approx(.006)
    finally:
        environment.close()


def test_commands_without_actual_target_contact_do_not_collapse_pad(env):
    assert target_normal_force(env.mjModel, env.mjData, env._weak_geom_id) == 0.
    env.step(np.ones(env.mjModel.nu)*10.)
    assert env.weak_pad_evaluation["force_before_deformation_n"] == 0.
    assert not env.weak_pad_evaluation["failed"]


def test_reset_restores_initial_surface_and_clears_failure(env):
    initial = env.mjData.qpos.copy()
    for _ in range(5):
        transition(env, 30.)
    transition(env, 0., .4)
    assert env.weak_pad_evaluation["sink_displacement_m"] == pytest.approx(.04)
    env.reset(random=False)
    assert not env.weak_pad_evaluation["failed"]
    assert env.weak_pad_evaluation["failure_time_s"] is None
    assert env.weak_pad_evaluation["failure_trigger_force_n"] is None
    assert env.weak_pad_evaluation["sink_displacement_m"] == 0.
    assert env.weak_pad_evaluation["overload_elapsed_s"] == 0.
    np.testing.assert_array_equal(env.mjData.qpos, initial)


def test_moved_world_geom_collision_and_bvh_follow_a_thin_surface():
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom name="floor" type="plane" pos="0 0 -.12" size="1 1 .01"/>
      <geom name="primp_landing_pad" type="box" pos="0 0 -.005" size=".05 .05 .005"/>
      <body pos="0 0 .019"><freejoint/><geom name="test_ball" type="sphere" size=".02" mass="1"/></body>
      </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    target = model.geom(LANDING_GEOM).id
    assert target_normal_force(model, data, target) > 0.
    qpos, qvel, mass = data.qpos.copy(), data.qvel.copy(), model.body_mass.copy()
    set_pad_sink_displacement(model, data, .06)
    assert target_normal_force(model, data, target) == 0.
    np.testing.assert_array_equal(data.qpos, qpos)
    np.testing.assert_array_equal(data.qvel, qvel)
    np.testing.assert_array_equal(model.body_mass, mass)
    data.qpos[2] = -.041  # 1 mm penetration into new z=-60 mm top
    mujoco.mj_forward(model, data)
    assert target_normal_force(model, data, target) > 0.
    leaf = next(i for i in range(model.body_bvhnum[0]) if model.bvh_nodeid[i] == target)
    assert model.bvh_aabb[leaf, 2] == pytest.approx(-.065)
    assert model.geom(LANDING_GEOM).pos[2] == pytest.approx(-.065)
    assert data.geom_xpos[target, 2] == pytest.approx(-.065)


@pytest.mark.parametrize("kwargs", [
    {"failure_load_n": 0.}, {"failure_load_n": np.inf}, {"failure_load_n": np.nan},
    {"overload_dwell_s": 0.}, {"overload_dwell_s": 2.},
    {"sink_depth_m": -.01}, {"sink_depth_m": .12},
    {"sink_speed_m_s": 0.}, {"sink_speed_m_s": .6},
])
def test_invalid_failure_models_are_rejected(kwargs):
    with pytest.raises(ValueError):
        WeakPadSpec(**kwargs)
