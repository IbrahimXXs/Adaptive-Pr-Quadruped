"""Public, reproducible initial kinematics for varied weak-pad conditions.

Offsets describe actual robot poses and foot anchors, never surface strength.
Each support box follows its declared initial foot anchor when constructing the
scene, then remains fixed. The robot's mass and inertial model are unchanged.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from .landing_pad import LANDING_GEOM, LEGS, SUPPORT_GEOMS, _make_scene


@dataclass(frozen=True)
class WeakPadInitialState:
    """Allowed kinematics relative to Go2's nominal home stance, in metres.

    Body XY and all four foot XY offsets are independent. Leg inverse
    kinematics keeps the nominal foot heights and base orientation/height.
    The standard environment reset subsequently lifts the whole pose clear of
    initial penetration, exactly as for the unmodified nominal home keyframe.
    """

    body_offset_xy_m: tuple[float, float] = (0., 0.)
    foot_offsets_xy_m: tuple[tuple[float, float], ...] = ((0., 0.),) * 4

    def __post_init__(self):
        body = np.asarray(self.body_offset_xy_m, dtype=float)
        feet = np.asarray(self.foot_offsets_xy_m, dtype=float)
        if body.shape != (2,) or feet.shape != (4, 2):
            raise ValueError("Initial body XY needs two values and foot XY offsets need FL/FR/RL/RR rows")
        if not np.all(np.isfinite(body)) or not np.all(np.isfinite(feet)):
            raise ValueError("Initial kinematic offsets must be finite")
        if np.max(np.abs(body)) > .04 or np.max(np.abs(feet)) > .04:
            raise ValueError("Initial body and foot offsets are bounded to 40 mm per axis")
        object.__setattr__(self, "body_offset_xy_m", tuple(float(x) for x in body))
        object.__setattr__(self, "foot_offsets_xy_m", tuple(tuple(float(x) for x in row) for row in feet))

    @property
    def is_nominal(self):
        return not np.any(self.body_offset_xy_m) and not np.any(self.foot_offsets_xy_m)


def _numbers(values):
    return " ".join(f"{float(value):.17g}" for value in values)


def _kinematic_home(model, robot_cfg, initial_state):
    """Find a bounded joint pose without advancing physics or moving the base."""
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)
    foot_ids = [model.geom(robot_cfg.feet_geom_names[leg]).id for leg in LEGS]
    nominal_feet = data.geom_xpos[foot_ids].copy()
    target_feet = nominal_feet.copy()
    target_feet[:, :2] += initial_state.foot_offsets_xy_m
    data.qpos[:2] += initial_state.body_offset_xy_m
    jacobian = np.zeros((3, model.nv))
    joint_margins = []
    for leg, foot_id, target in zip(LEGS, foot_ids, target_feet, strict=True):
        joint_ids = np.array([model.joint(name).id for name in robot_cfg.leg_joints[leg]])
        if not np.all(model.jnt_type[joint_ids] == mujoco.mjtJoint.mjJNT_HINGE):
            raise ValueError("Varied initial stance requires three scalar leg joints")
        qpos_ids, qvel_ids = model.jnt_qposadr[joint_ids], model.jnt_dofadr[joint_ids]
        lower, upper = model.jnt_range[joint_ids].T
        for _ in range(100):
            mujoco.mj_forward(model, data)
            error = target-data.geom_xpos[foot_id]
            if np.linalg.norm(error) < 1e-10:
                break
            mujoco.mj_jacGeom(model, data, jacobian, None, foot_id)
            delta = np.linalg.lstsq(jacobian[:, qvel_ids], error, rcond=None)[0]
            data.qpos[qpos_ids] = np.clip(data.qpos[qpos_ids]+np.clip(delta, -.08, .08),
                                          lower+1e-5, upper-1e-5)
        mujoco.mj_forward(model, data)
        if np.linalg.norm(target-data.geom_xpos[foot_id]) > 1e-8:
            raise ValueError(f"Initial {leg} foot offset is not reachable within joint limits")
        joint_margins.extend(np.minimum(data.qpos[qpos_ids]-lower, upper-data.qpos[qpos_ids]))
    mujoco.mj_forward(model, data)
    actual_feet = data.geom_xpos[foot_ids].copy()
    return data.qpos.copy(), dict(
        nominal_keyframe_foot_pos_w=nominal_feet.tolist(),
        requested_keyframe_foot_pos_w=target_feet.tolist(),
        keyframe_foot_pos_w=actual_feet.tolist(),
        keyframe_base_pos_w=data.qpos[:3].tolist(),
        keyframe_com_pos_w=data.subtree_com[model.body("base").id].tolist(),
        maximum_foot_target_error_m=float(np.max(np.linalg.norm(actual_feet-target_feet, axis=1))),
        minimum_joint_limit_margin_rad=float(np.min(joint_margins)),
    )


def make_initial_scene(robot_cfg, landing_spec, scene_dir, initial_state):
    """Construct project-owned MJCF with the declared initial stance geometry."""
    if not isinstance(initial_state, WeakPadInitialState):
        raise TypeError("Initial stance requires WeakPadInitialState")
    model, geometry, truth = _make_scene(robot_cfg, landing_spec, scene_dir)
    scene_dir = Path(scene_dir).resolve()
    qpos, diagnostics = _kinematic_home(model, robot_cfg, initial_state)
    if not initial_state.is_nominal:
        scene_path = scene_dir/"scene.xml"
        scene = ET.parse(scene_path)
        include = scene.getroot().find("include")
        robot_path = Path(include.attrib["file"])
        robot = ET.parse(robot_path)
        keys = robot.getroot().findall("keyframe/key")
        if not keys:
            raise ValueError("Robot MJCF must declare its home keyframe")
        keys[0].set("qpos", _numbers(qpos))
        # Only home qpos changes. Keep all installed assets read-only and retain
        # the original MJCF attributes without a lossy model/XML round trip.
        for element in robot.getroot().iter():
            if "file" in element.attrib:
                element.set("file", str((robot_path.parent/element.attrib["file"]).resolve()))
        robot_copy = scene_dir/"robot_initial.xml"
        ET.indent(robot.getroot())
        robot.write(robot_copy, encoding="unicode")
        include.set("file", str(robot_copy))
        centers = np.asarray(diagnostics["keyframe_foot_pos_w"])[:, :2]
        target_xy = centers[0]+landing_spec.target_offset_xy_m
        for name, xy in zip((*SUPPORT_GEOMS, LANDING_GEOM), [*centers, target_xy], strict=True):
            geom = scene.getroot().find(f"worldbody/geom[@name='{name}']")
            position = np.fromstring(geom.attrib["pos"], sep=" ")
            position[:2] = xy
            geom.set("pos", _numbers(position))
        ET.indent(scene.getroot())
        scene.write(scene_path, encoding="unicode")
        varied = mujoco.MjModel.from_xml_path(str(scene_path))
        for name in ("body_mass", "body_ipos", "body_inertia", "body_iquat", "jnt_range",
                     "dof_armature", "actuator_gainprm", "actuator_biasprm", "actuator_forcerange"):
            if not np.array_equal(getattr(varied, name), getattr(model, name)):
                raise ValueError(f"Initial-state construction unexpectedly changed robot {name}")
        model = varied
        geometry.update(target_xy_m=target_xy.tolist(), launch_support_xy_m=centers.tolist())
        truth["geometry"] = geometry
        (scene_dir/"evaluation_truth.json").write_text(json.dumps(truth, indent=2)+"\n")
    public = dict(schema_version=1, **asdict(initial_state), **diagnostics,
                  keyframe_qpos=qpos.tolist(), fixed_support_xy_m=geometry["launch_support_xy_m"],
                  target_xy_m=geometry["target_xy_m"],
                  convention="Public initial kinematics; rigid supports fixed within each trial; no strength truth")
    (scene_dir/"initial_state.json").write_text(json.dumps(public, indent=2)+"\n")
    return model, geometry, truth
