"""Initial body/stance variations change measured kinematics, not capacity."""

import json

import mujoco
import numpy as np
import pytest

from primp_project.environment.landing_pad import LandingPadEnv, LandingPadSpec, SUPPORT_GEOMS
from primp_project.environment.weak_pad import (
    WeakPadEnv, WeakPadInitialState, WeakPadSpec, set_pad_sink_displacement,
)


VARIED = WeakPadInitialState(
    body_offset_xy_m=(.012, -.008),
    foot_offsets_xy_m=((0., 0.), (.010, -.012), (-.010, 0.), (-.005, -.012)),
)


def test_zero_offset_keeps_original_scene_and_initial_robot_state(tmp_path):
    original = LandingPadEnv(LandingPadSpec(), tmp_path/"original")
    weak = WeakPadEnv(WeakPadSpec(), tmp_path/"weak", initial_state=WeakPadInitialState())
    try:
        original.reset(random=False, seed=17)
        weak.reset(random=False, seed=17)
        assert (tmp_path/"original/scene.xml").read_bytes() == (tmp_path/"weak/scene.xml").read_bytes()
        np.testing.assert_array_equal(original.mjData.qpos, weak.mjData.qpos)
        np.testing.assert_array_equal(original.mjData.qvel, weak.mjData.qvel)
        assert not (tmp_path/"weak/robot_initial.xml").exists()
        assert weak.landing_pad_geometry == original.landing_pad_geometry
    finally:
        original.close()
        weak.close()


@pytest.mark.parametrize("initial", [
    WeakPadInitialState(body_offset_xy_m=(.02, -.01)),
    WeakPadInitialState(foot_offsets_xy_m=((0., 0.), (0., -.02), (0., .01), (0., -.02))),
    VARIED,
    WeakPadInitialState(body_offset_xy_m=(-.035, .02),
                        foot_offsets_xy_m=((.02, .005), (-.015, -.015), (-.015, .015), (.02, -.015))),
])
def test_declared_variation_matches_actual_robot_and_fixed_support_geometry(tmp_path, initial):
    nominal = WeakPadEnv(WeakPadSpec(), tmp_path/"nominal")
    varied = WeakPadEnv(WeakPadSpec(), tmp_path/"varied", initial_state=initial)
    try:
        nominal.reset(random=False, seed=17)
        varied.reset(random=False, seed=17)
        nominal_feet = np.asarray(nominal.weak_pad_initial_state["reset_foot_pos_w"])
        varied_feet = np.asarray(varied.weak_pad_initial_state["reset_foot_pos_w"])
        np.testing.assert_allclose(varied.mjData.qpos[:2]-nominal.mjData.qpos[:2], initial.body_offset_xy_m, atol=1e-10)
        np.testing.assert_allclose(varied_feet[:, :2]-nominal_feet[:, :2], initial.foot_offsets_xy_m, atol=1e-8)
        np.testing.assert_allclose(varied_feet[:, 2], nominal_feet[:, 2], atol=1e-8)
        np.testing.assert_array_equal(varied.mjModel.key_qpos[0, 3:7], nominal.mjModel.key_qpos[0, 3:7])
        np.testing.assert_allclose(varied.mjData.qpos[3:7], nominal.mjData.qpos[3:7], atol=1e-12, rtol=0)
        for name in ("body_mass", "body_ipos", "body_inertia", "body_iquat", "jnt_range", "dof_armature",
                     "actuator_gainprm", "actuator_biasprm", "actuator_forcerange"):
            np.testing.assert_array_equal(getattr(varied.mjModel, name), getattr(nominal.mjModel, name))
        for i, name in enumerate(SUPPORT_GEOMS):
            geom = varied.mjModel.geom(name)
            np.testing.assert_allclose(geom.pos[:2], varied_feet[i, :2], atol=1e-8)
            assert geom.pos[2]+geom.size[2] == pytest.approx(0.)
            assert varied.mjModel.geom_bodyid[geom.id] == 0
        np.testing.assert_allclose(varied.landing_pad_geometry["target_xy_m"], varied_feet[0, :2]+[.09, 0.], atol=1e-8)
        assert varied.weak_pad_initial_state["maximum_foot_target_error_m"] < 1e-8
        assert varied.weak_pad_initial_state["minimum_joint_limit_margin_rad"] > .1
        assert np.all(varied_feet[:, 2] > varied.landing_pad_geometry["foot_radius_m"])
        assert not varied._check_for_invalid_contacts()[0]
    finally:
        nominal.close()
        varied.close()


def test_strength_does_not_change_varied_initial_observations_or_public_geometry(tmp_path):
    weak = WeakPadEnv(WeakPadSpec(failure_load_n=15.), tmp_path/"weak", initial_state=VARIED,
                      state_obs_names=("qpos", "qvel", "feet_pos"))
    firm = WeakPadEnv(WeakPadSpec(failure_load_n=150.), tmp_path/"firm", initial_state=VARIED,
                      state_obs_names=("qpos", "qvel", "feet_pos"))
    try:
        weak_obs, firm_obs = weak.reset(random=False, seed=17), firm.reset(random=False, seed=17)
        assert weak.weak_pad_initial_state == firm.weak_pad_initial_state
        assert weak.landing_pad_geometry == firm.landing_pad_geometry
        for name in weak_obs:
            np.testing.assert_array_equal(weak_obs[name], firm_obs[name])
        for name in ("key_qpos", "geom_pos", "geom_size", "body_mass", "body_ipos", "body_inertia"):
            np.testing.assert_array_equal(getattr(weak.mjModel, name), getattr(firm.mjModel, name))
        public = json.dumps(weak.weak_pad_initial_state)+json.dumps(weak.landing_pad_geometry)
        for word in ("failure_load", "overload_dwell", "sink_depth", "sink_speed", "weak_pad_evaluation"):
            assert word not in public
        assert weak.weak_pad_evaluation["failure_load_n"] == 15.
        assert firm.weak_pad_evaluation["failure_load_n"] == 150.
    finally:
        weak.close()
        firm.close()


def test_varied_fixed_supports_do_not_move_and_reset_and_replay_keep_the_declared_pose(tmp_path):
    env = WeakPadEnv(WeakPadSpec(), tmp_path, initial_state=VARIED)
    try:
        env.reset(random=False, seed=17)
        initial_qpos, initial_qvel = env.mjData.qpos.copy(), env.mjData.qvel.copy()
        supports = np.stack([env.mjModel.geom(name).pos.copy() for name in SUPPORT_GEOMS])
        set_pad_sink_displacement(env.mjModel, env.mjData, .045)
        np.testing.assert_array_equal(np.stack([env.mjModel.geom(name).pos for name in SUPPORT_GEOMS]), supports)
        env.reset(random=False, seed=17)
        np.testing.assert_array_equal(env.mjData.qpos, initial_qpos)
        np.testing.assert_array_equal(env.mjData.qvel, initial_qvel)
        replay_model = mujoco.MjModel.from_xml_path(str(tmp_path/"scene.xml"))
        np.testing.assert_array_equal(replay_model.key_qpos, env.mjModel.key_qpos)
        np.testing.assert_array_equal(replay_model.geom_pos, env.mjModel.geom_pos)
        declared = json.loads((tmp_path/"initial_state.json").read_text())
        np.testing.assert_allclose(declared["keyframe_qpos"], replay_model.key_qpos[0], atol=1e-14)
    finally:
        env.close()


@pytest.mark.parametrize("kwargs", [
    {"body_offset_xy_m": (0.,)}, {"body_offset_xy_m": (0., 0., 0.)},
    {"body_offset_xy_m": (.041, 0.)}, {"body_offset_xy_m": (np.nan, 0.)},
    {"foot_offsets_xy_m": ((0., 0.),) * 3},
    {"foot_offsets_xy_m": ((0., np.inf),) * 4},
    {"foot_offsets_xy_m": ((0., -.041),) * 4},
])
def test_invalid_initial_conditions_are_rejected(kwargs):
    with pytest.raises(ValueError):
        WeakPadInitialState(**kwargs)
