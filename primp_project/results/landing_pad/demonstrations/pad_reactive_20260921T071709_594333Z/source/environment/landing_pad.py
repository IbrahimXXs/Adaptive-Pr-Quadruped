"""An independent landing surface, with terrain truth confined to simulation.

The stock gym-quadruped constructor accepts named scenes only and writes its
generated XML into site-packages.  This small environment adapter initializes
the inherited reset/step/render API from project-owned MJCF instead. Robot
assets are included read-only from the installed package. Physics, actuator,
joint, and contact methods remain gym-quadruped's implementations.

The front-left foot starts on a fixed launch pad, then moves 9 cm forward onto
the separate landing pad. Three support pads and the launch pad always have
top z=0. A lowered floor makes negative landing heights physically reachable.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import gymnasium as gym
from gymnasium import spaces
import gym_quadruped.quadruped_env as gym_env_module
from gym_quadruped.quadruped_env import QuadrupedEnv
from gym_quadruped.robot_cfgs import get_robot_config
from gym_quadruped.utils.math_utils import _process_range
from gym_quadruped.utils.quadruped_utils import (
    LegsAttr, configure_observation_space, extract_mj_joint_info,
)
import mujoco
import numpy as np

LEGS = ("FL", "FR", "RL", "RR")
LANDING_GEOM = "primp_landing_pad"
SUPPORT_GEOMS = tuple(f"primp_support_{leg}" for leg in LEGS)


@dataclass(frozen=True)
class LandingPadSpec:
    """Simulator/evaluator settings; never an input to an adaptation planner."""

    true_height_m: float = 0.0
    target_offset_xy_m: tuple[float, float] = (0.09, 0.0)
    pad_half_size_xy_m: tuple[float, float] = (0.032, 0.065)
    floor_height_m: float = -0.12

    def __post_init__(self):
        values = [self.true_height_m, self.floor_height_m,
                  *self.target_offset_xy_m, *self.pad_half_size_xy_m]
        if not np.all(np.isfinite(values)):
            raise ValueError("Landing scene dimensions must be finite")
        if not -.025 <= self.true_height_m <= .025:
            raise ValueError("Initial landing experiments are bounded to +/-25 mm")
        if self.floor_height_m > -.08:
            raise ValueError("The floor must be below all permitted landing heights")
        if len(self.target_offset_xy_m) != 2 or len(self.pad_half_size_xy_m) != 2:
            raise ValueError("Pad offset and half-size need exactly two XY coordinates")
        if min(self.pad_half_size_xy_m) <= .022:
            raise ValueError("The landing pad must be wider than the Go2 foot radius")
        if not .075 <= self.target_offset_xy_m[0] <= .12 or abs(self.target_offset_xy_m[1]) > .015:
            raise ValueError("Target offset must stay within the verified front-foot workspace")
        if self.target_offset_xy_m[0] - self.pad_half_size_xy_m[0] <= .032:
            raise ValueError("Landing pad must not overlap the fixed launch pad")


def _numbers(values):
    return " ".join(f"{float(value):.12g}" for value in values)


def _make_scene(robot_cfg, spec, scene_dir):
    scene_dir = Path(scene_dir).resolve()
    scene_dir.mkdir(parents=True, exist_ok=True)
    robot_asset = (Path(gym_env_module.__file__).resolve().parent / "robot_model"
                   / robot_cfg.mjcf_filename)
    root = ET.Element("mujoco", model="primp_adjustable_landing_pad")
    ET.SubElement(root, "include", file=str(robot_asset))
    ET.SubElement(root, "statistic", center="0 0 0.1", extent="0.9")
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "headlight", diffuse="0.5 0.5 0.5", ambient="0.35 0.35 0.35")
    ET.SubElement(visual, "global", azimuth="-130", elevation="-25")
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", pos="0 0 3", dir="0 0 -1", directional="true")
    ET.SubElement(world, "geom", name="floor", type="plane", size="0 0 0.05",
                  pos=_numbers((0, 0, spec.floor_height_m)), rgba="0.75 0.78 0.8 1")
    # Nominal launch centers come from robot kinematics, independent of terrain
    # truth. Compile in memory, with the only floor far below the robot.
    nominal_model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    nominal_data = mujoco.MjData(nominal_model)
    mujoco.mj_resetDataKeyframe(nominal_model, nominal_data, 0)
    mujoco.mj_forward(nominal_model, nominal_data)
    feet_ids = [nominal_model.geom(robot_cfg.feet_geom_names[leg]).id for leg in LEGS]
    centers = nominal_data.geom_xpos[feet_ids, :2].copy()
    foot_radius = float(nominal_model.geom_size[feet_ids[0], 0])
    if any(nominal_model.geom_type[i] != mujoco.mjtGeom.mjGEOM_SPHERE for i in feet_ids):
        raise ValueError("Landing height observations require spherical Go2 foot geoms")
    bottom = spec.floor_height_m + .01

    def add_pad(name, xy, top, half_xy, rgba):
        ET.SubElement(world, "geom", name=name, type="box",
                      pos=_numbers((*xy, (top+bottom)/2)),
                      size=_numbers((*half_xy, (top-bottom)/2)),
                      rgba=rgba, friction="0.8 0.005 0", condim="3")

    for leg, name, xy in zip(LEGS, SUPPORT_GEOMS, centers, strict=True):
        half_xy = (.032, .065) if leg == "FL" else (.075, .075)
        add_pad(name, xy, 0.0, half_xy, "0.3 0.36 0.43 1")
    target_xy = centers[0] + spec.target_offset_xy_m
    add_pad(LANDING_GEOM, target_xy, spec.true_height_m,
            spec.pad_half_size_xy_m, "0.18 0.6 0.72 1")
    scene_path = scene_dir / "scene.xml"
    ET.indent(root)
    ET.ElementTree(root).write(scene_path, encoding="unicode")
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    geometry = {
        "target_xy_m": target_xy.tolist(),
        "target_offset_xy_m": list(spec.target_offset_xy_m),
        "launch_support_xy_m": centers.tolist(),
        "foot_radius_m": foot_radius,
        "pad_half_size_xy_m": list(spec.pad_half_size_xy_m),
        "fixed_surface_height_m": 0.0,
    }
    truth = {
        "schema_version": 1,
        "scene_type": "independent_landing_pad",
        "true_height_m": spec.true_height_m,
        "scene_spec": asdict(spec),
        "landing_geom_name": LANDING_GEOM,
        "landing_geom_id": model.geom(LANDING_GEOM).id,
        "support_geom_names": list(SUPPORT_GEOMS),
        "support_geom_ids": [model.geom(name).id for name in SUPPORT_GEOMS],
        "support_top_heights_m": [0.0] * 4,
        "scene_path": str(scene_path),
        "geometry": geometry,
    }
    (scene_dir / "evaluation_truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    return model, geometry, truth


class LandingPadEnv(QuadrupedEnv):
    """The existing gym environment API initialized with the landing scene.

    Only ``landing_pad_geometry`` is permissible nominal geometry for control.
    ``landing_pad_evaluation`` belongs exclusively to simulation recording and
    evaluation. Planners receive copied sensor observations, never this object.
    """

    def __init__(self, spec, scene_dir, *, robot="go2", scene="flat", sim_dt=.002,
                 state_obs_names=(), base_vel_command_type="human",
                 ref_base_lin_vel=0., ref_base_ang_vel=0., ground_friction_coeff=.8):
        gym.Env.__init__(self)
        if robot != "go2":
            raise ValueError("The adjustable landing-pad geometry is verified for Go2 only")
        self.robot_name = robot
        self.robot_cfg = get_robot_config(robot)
        self.base_vel_command_type = base_vel_command_type
        self.base_lin_vel_range = _process_range(ref_base_lin_vel)
        self.base_ang_vel_range = _process_range(ref_base_ang_vel)
        self.ground_friction_coeff_range = _process_range(ground_friction_coeff)
        self.legs_order = LEGS
        self.is_paused = False
        self.terrain_limits = (1., -1., 1., -1.)
        self._init_args = {
            "robot": robot, "scene": "primp_landing_pad", "sim_dt": sim_dt,
            "state_obs_names": state_obs_names,
            "base_vel_command_type": base_vel_command_type,
            "ref_base_lin_vel": ref_base_lin_vel,
            "ref_base_ang_vel": ref_base_ang_vel,
            "ground_friction_coeff": ground_friction_coeff,
        }
        self.mjModel, self.landing_pad_geometry, self.landing_pad_evaluation = _make_scene(
            self.robot_cfg, spec, scene_dir)
        self.mjModel.opt.timestep = sim_dt
        self.mjData = mujoco.MjData(self.mjModel)
        self._ghost_mjData = mujoco.MjData(self.mjModel)
        self.joint_info = extract_mj_joint_info(self.mjModel)
        self.legs_qpos_idx = LegsAttr(None, None, None, None)
        self.legs_qvel_idx = LegsAttr(None, None, None, None)
        self.legs_tau_idx = LegsAttr(None, None, None, None)
        for leg in LEGS:
            for field, joint_field in ((self.legs_qpos_idx, "qpos_idx"),
                                       (self.legs_qvel_idx, "qvel_idx"),
                                       (self.legs_tau_idx, "tau_idx")):
                field[leg] = [index for name in self.robot_cfg.leg_joints[leg]
                              for index in getattr(self.joint_info[name], joint_field)]
        self._feet_geom_id = LegsAttr(None, None, None, None)
        self._feet_body_id = LegsAttr(None, None, None, None)
        self._find_feet_model_attrs(self.robot_cfg.feet_geom_names)
        limits = self.mjModel.actuator_forcerange
        limited = self.mjModel.actuator_forcelimited.astype(bool)
        self.action_space = spaces.Box(
            low=np.where(limited, limits[:, 0], -np.inf).astype(np.float32),
            high=np.where(limited, limits[:, 1], np.inf).astype(np.float32), dtype=np.float32)
        self.state_obs_names = state_obs_names
        self.observation_space = configure_observation_space(self.mjModel, state_obs_names)
        self.sensors = []
        self.external_disturbances_kwargs = None
        self.viewer = None
        self.step_num = 0
        self._ref_base_lin_vel_H, self._ref_base_ang_yaw_dot = None, None
        self._geom_ids, self._ghost_robots_geom = {}, {}

    def _set_ground_friction(self, tangential_coeff=1.0, torsional_coeff=.005, rolling_coeff=0.):
        super()._set_ground_friction(tangential_coeff, torsional_coeff, rolling_coeff)
        # Stock gym only recognizes floor/terrain names. Include our named pads
        # so every condition uses the same requested friction coefficient.
        for name in (*SUPPORT_GEOMS, LANDING_GEOM):
            self.mjModel.geom_friction[self.mjModel.geom(name).id] = (
                tangential_coeff, torsional_coeff, rolling_coeff)


def make_landing_pad_env(spec, scene_dir, **kwargs):
    """Environment-factory hook: bind spec/scene_dir, pass simulator kwargs."""
    return LandingPadEnv(spec, scene_dir, **kwargs)
