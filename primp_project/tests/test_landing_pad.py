"""Physical scene checks: independent height, exposed target, and valid launch."""

import json

import mujoco
import numpy as np
import pytest

from primp_project.environment.landing_pad import (
    LANDING_GEOM, LEGS, SUPPORT_GEOMS, LandingPadEnv, LandingPadSpec,
)
from primp_project.recording.standing import ground_contacts


@pytest.mark.parametrize("height", [-.01, 0., .01])
def test_only_landing_surface_height_changes(tmp_path, height):
    baseline = LandingPadEnv(LandingPadSpec(), tmp_path / "baseline")
    trial = LandingPadEnv(LandingPadSpec(true_height_m=height), tmp_path / "trial")
    try:
        baseline.reset(random=False)
        trial.reset(random=False)
        model = trial.mjModel
        target_id = model.geom(LANDING_GEOM).id
        assert model.geom_bodyid[target_id] == 0
        assert model.geom_pos[target_id, 2] + model.geom_size[target_id, 2] == pytest.approx(height)
        # Independent changes must not disturb either the other three support
        # surfaces or the original front-left launch surface.
        for name in (*SUPPORT_GEOMS, "floor"):
            original, changed = baseline.mjModel.geom(name), model.geom(name)
            np.testing.assert_array_equal(original.pos, changed.pos)
            np.testing.assert_array_equal(original.size, changed.size)
        np.testing.assert_array_equal(baseline.mjData.qpos, trial.mjData.qpos)
        np.testing.assert_array_equal(baseline.mjData.qvel, trial.mjData.qvel)
        assert baseline.landing_pad_geometry == trial.landing_pad_geometry
        assert model.geom("floor").pos[2] < height - .05
        # A downward ray reaches the target, including negative heights. This
        # detects the common mistake of leaving a z=0 floor over a lowered pad.
        hit = np.array([-1], dtype=np.int32)
        origin = np.r_[trial.landing_pad_geometry["target_xy_m"], .06]
        distance = mujoco.mj_ray(model, trial.mjData, origin, np.array([0., 0., -1.]),
                                None, True, -1, hit)
        assert hit[0] == target_id
        assert distance == pytest.approx(.06-height, abs=1e-10)
    finally:
        baseline.close()
        trial.close()


def test_launch_has_four_real_support_contacts_and_valid_env_api(tmp_path):
    env = LandingPadEnv(LandingPadSpec(true_height_m=-.01), tmp_path,
                        ground_friction_coeff=.65,
                        state_obs_names=("qpos", "qvel", "feet_pos"))
    try:
        observation = env.reset(random=False)
        assert set(observation) == {"qpos", "qvel", "feet_pos"}
        assert env.mjModel.nq == 19 and env.mjModel.nv == 18 and env.mjModel.nu == 12
        assert sorted(index for leg in LEGS for index in env.legs_tau_idx[leg]) == list(range(12))
        # Reset lifts feet just clear of the surfaces. Lower the body by 2 mm
        # to check actual collision pairs on all four separate launch pads.
        env.mjData.qpos[2] -= .002
        mujoco.mj_forward(env.mjModel, env.mjData)
        foot_ids = np.array([env._feet_geom_id[leg] for leg in LEGS])
        contacts, _, _, _ = ground_contacts(env.mjModel, env.mjData, foot_ids)
        assert np.all(contacts)
        invalid, _ = env._check_for_invalid_contacts()
        assert not invalid
        observed = set()
        for contact in env.mjData.contact:
            for leg, foot_id in zip(LEGS, foot_ids, strict=True):
                if foot_id in (contact.geom1, contact.geom2):
                    other = contact.geom2 if contact.geom1 == foot_id else contact.geom1
                    assert env.mjModel.geom(other).name == f"primp_support_{leg}"
                    observed.add(leg)
        assert observed == set(LEGS)
        for name in (*SUPPORT_GEOMS, LANDING_GEOM, "floor"):
            assert env.mjModel.geom(name).friction[0] == pytest.approx(.65)
        result = env.step(np.zeros(env.mjModel.nu))
        assert len(result) == 5
        assert not result[2] and not result[3]
        assert env.simulation_time == pytest.approx(.004)
    finally:
        env.close()


def test_scene_artifacts_and_truth_are_separate_from_allowed_geometry(tmp_path):
    env = LandingPadEnv(LandingPadSpec(true_height_m=.007), tmp_path)
    try:
        assert (tmp_path / "scene.xml").is_file()
        truth = json.loads((tmp_path / "evaluation_truth.json").read_text())
        assert truth == json.loads(json.dumps(env.landing_pad_evaluation))
        assert truth["true_height_m"] == .007
        assert "true_height_m" not in env.landing_pad_geometry
        assert "scene_path" not in env.landing_pad_geometry
        assert "scene_spec" not in env.landing_pad_geometry
        assert "true_height_m" not in env.get_hyperparameters()
        assert len(env.landing_pad_geometry["target_xy_m"]) == 2
    finally:
        env.close()


@pytest.mark.parametrize("kwargs", [
    {"true_height_m": .03}, {"true_height_m": np.nan},
    {"floor_height_m": -.02}, {"target_offset_xy_m": (.01, 0)},
    {"pad_half_size_xy_m": (.08, .06)},
])
def test_invalid_scene_geometry_rejected(kwargs):
    with pytest.raises(ValueError):
        LandingPadSpec(**kwargs)
