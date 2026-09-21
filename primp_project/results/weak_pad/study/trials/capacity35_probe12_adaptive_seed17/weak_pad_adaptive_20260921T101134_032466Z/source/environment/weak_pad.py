"""A hidden-load-limit landing pad with deterministic irreversible collapse.

This is a deliberately simple simulator model: capacity is a time-invariant
normal-load threshold at the same contact location. There is no fatigue,
stochastic failure, material identification, or added robot/platform mass.
After a sustained overload, the world-body box descends kinematically. Its
pose, collision bounding volume, and resulting contacts are updated together.
Only the simulator/evaluator receives capacity and deformation truth.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import mujoco
import numpy as np

from .landing_pad import LANDING_GEOM, LandingPadEnv, LandingPadSpec


@dataclass(frozen=True)
class WeakPadSpec:
    """Hidden simulation parameters; not planner context or observations."""

    failure_load_n: float = 20.
    overload_dwell_s: float = .010
    sink_depth_m: float = .060
    sink_speed_m_s: float = .10

    def __post_init__(self):
        values = asdict(self)
        if not all(np.isfinite(value) for value in values.values()):
            raise ValueError("Weak-pad parameters must be finite")
        if not 0 < self.failure_load_n <= 1e6:
            raise ValueError("Failure load must be positive and at most 1e6 N")
        if not 0 < self.overload_dwell_s <= 1.:
            raise ValueError("Overload dwell must be positive and at most one second")
        if not 0 < self.sink_depth_m <= .09:
            raise ValueError("Sink depth must be positive and at most 90 mm above the lowered floor")
        if not 0 < self.sink_speed_m_s <= .5:
            raise ValueError("Sink speed must be positive and at most 0.5 m/s")


def target_normal_force(model, data, geom_id):
    """Actual sum of nonnegative contact-frame normal forces on the target.

    All target contacts count, not just FL, so unrelated robot impacts cannot
    bypass its capacity. Intended trials use the same FL top-surface contact.
    This is simulator truth and must not be passed to a planner as a pad sensor.
    """
    force, total = np.zeros(6), 0.
    for index, contact in enumerate(data.contact):
        if geom_id in (int(contact.geom1), int(contact.geom2)) and contact.efc_address >= 0:
            mujoco.mj_contactForce(model, data, index, force)
            total += max(0., float(force[0]))
    return total


def set_pad_sink_displacement(model, data, displacement_m):
    """Set a saved weak-pad displacement and refresh collision/render state.

    The weak target initially has top z=0 and remains an axis-aligned world
    geom. Updating only geom_pos leaves its static world-body BVH stale, so its
    leaf and ancestors are updated as well. No physics step, robot-state change,
    or model mass/inertia change occurs. Offline replay uses this same helper.
    Returns whether the pad position changed.
    """
    displacement = float(displacement_m)
    if not np.isfinite(displacement) or not 0 <= displacement <= .09+1e-12:
        raise ValueError("Recorded sink displacement must lie between 0 and 90 mm")
    geom = model.geom(LANDING_GEOM)
    geom_id = geom.id
    if model.geom_bodyid[geom_id] != 0 or model.geom_type[geom_id] != mujoco.mjtGeom.mjGEOM_BOX:
        raise ValueError("Weak-pad deformation requires a world-body box")
    expected_z = -float(geom.size[2])-displacement
    change = expected_z-float(geom.pos[2])
    if change == 0.:
        return False
    start, count = int(model.body_bvhadr[0]), int(model.body_bvhnum[0])
    indices = np.arange(start, start+count)
    leaves = indices[model.bvh_nodeid[indices] == geom_id]
    if len(leaves) != 1:
        raise ValueError("Expected exactly one world BVH leaf for the landing pad")
    geom.pos[2] = expected_z
    model.bvh_aabb[leaves[0], 2] += change
    # Children have greater tree depth; sorting makes the update independent of
    # the compiler's array ordering. World-body BVH child IDs are model indices.
    for index in indices[np.argsort(model.bvh_depth[indices])[::-1]]:
        children = model.bvh_child[index]
        children = children[children >= 0]
        if len(children):
            boxes = model.bvh_aabb[children]
            low = np.min(boxes[:, :3]-boxes[:, 3:], axis=0)
            high = np.max(boxes[:, :3]+boxes[:, 3:], axis=0)
            model.bvh_aabb[index, :3] = (low+high)/2
            model.bvh_aabb[index, 3:] = (high-low)/2
    mujoco.mj_forward(model, data)
    return True


class WeakPadEnv(LandingPadEnv):
    """The existing environment API plus evaluator-only load/collapse truth.

    ``landing_pad_geometry`` is the unchanged permissible nominal geometry.
    Neither hidden capacity nor failure/deformation state is added to returned
    observations, step info, or get_hyperparameters(). The controller must use
    its normal allowed foot/contact/force observations to infer weak support.
    """

    def __init__(self, spec, scene_dir, **kwargs):
        if not isinstance(spec, WeakPadSpec):
            raise TypeError("WeakPadEnv requires a WeakPadSpec")
        self._weak_spec = spec
        super().__init__(LandingPadSpec(true_height_m=0.), scene_dir, **kwargs)
        self._weak_geom_id = self.mjModel.geom(LANDING_GEOM).id
        self._weak_failure_time = None
        self._weak_trigger_force = None
        self._weak_overload_elapsed = 0.
        self.weak_pad_evaluation = {}
        self._publish_weak_state(0.)
        self._init_args["scene"] = "primp_weak_landing_pad"
        initial_truth = dict(
            schema_version=1, scene_type="normal_load_limited_weak_pad",
            initial_top_height_m=0., landing_geom_name=LANDING_GEOM,
            landing_geom_id=self._weak_geom_id, **asdict(spec),
            failure_model="Strictly over threshold for continuous dwell; irreversible prescribed descent on subsequent steps",
            force_convention="Sum of nonnegative contact-frame normal forces involving the target geom",
            assumptions=["time-invariant threshold", "same contact location", "no fatigue", "no stochastic failure",
                         "kinematic surface descent, not a structural material model", "robot mass and CoM model unchanged"],
        )
        # Keep the original landing truth intact and add a separate evaluator
        # artifact; robot/planner-visible geometry is identical across strengths.
        (Path(scene_dir)/"weak_pad_truth.json").write_text(json.dumps(initial_truth, indent=2)+"\n")

    def _publish_weak_state(self, force_before_deformation):
        geom = self.mjModel.geom(LANDING_GEOM)
        top = float(geom.pos[2]+geom.size[2])
        self.weak_pad_evaluation.update(
            schema_version=1, **asdict(self._weak_spec), failed=self._weak_failure_time is not None,
            failure_time_s=self._weak_failure_time, failure_trigger_force_n=self._weak_trigger_force,
            overload_elapsed_s=float(self._weak_overload_elapsed),
            force_before_deformation_n=float(force_before_deformation),
            target_normal_force_n=target_normal_force(self.mjModel, self.mjData, self._weak_geom_id),
            sink_displacement_m=-top, top_height_m=top, simulation_time_s=float(self.mjData.time))

    def _advance_weak_surface(self, force_before_deformation, interval_s):
        """Simulator transition driven only by measured load and elapsed time.

        Kept separate for deterministic threshold/dwell tests. Production only
        calls this with the force measured from the immediately preceding
        native step, never with commanded or controller-reported force.
        """
        force, interval = float(force_before_deformation), float(interval_s)
        if not np.isfinite(force) or force < 0 or not np.isfinite(interval) or interval <= 0:
            raise ValueError("Weak-pad transitions require nonnegative finite force and positive elapsed time")
        failed_before = self._weak_failure_time is not None
        if not failed_before:
            if force > self._weak_spec.failure_load_n:
                self._weak_overload_elapsed += interval
            else:
                self._weak_overload_elapsed = 0.
            if self._weak_overload_elapsed+1e-12 >= self._weak_spec.overload_dwell_s:
                self._weak_failure_time = float(self.mjData.time)
                self._weak_trigger_force = force
        moved = False
        if failed_before:
            displacement = min(self._weak_spec.sink_depth_m,
                               self._weak_spec.sink_speed_m_s*(float(self.mjData.time)-self._weak_failure_time))
            moved = set_pad_sink_displacement(self.mjModel, self.mjData, displacement)
        self._publish_weak_state(force)
        return moved

    def step(self, action):
        before = float(self.mjData.time)
        observation, reward, terminated, truncated, info = super().step(action)
        measured_force = target_normal_force(self.mjModel, self.mjData, self._weak_geom_id)
        moved = self._advance_weak_surface(measured_force, float(self.mjData.time)-before)
        if moved:
            # The inherited observations were computed before deformation.
            # Refresh them and safety information against the new surface pose.
            observation = self._get_obs()
            reward = self._compute_reward()
            invalid, contacts = self._check_for_invalid_contacts()
            terminated = terminated or invalid or self._check_out_of_terrain_bounds()
            if invalid:
                info["invalid_contacts"] = contacts
        return observation, reward, terminated, truncated, info

    def reset(self, *args, **kwargs):
        set_pad_sink_displacement(self.mjModel, self.mjData, 0.)
        self._weak_failure_time = None
        self._weak_trigger_force = None
        self._weak_overload_elapsed = 0.
        observation = super().reset(*args, **kwargs)
        self._publish_weak_state(0.)
        return observation


def make_weak_pad_env(spec, scene_dir, **kwargs):
    """Bind hidden simulator spec and artifact directory to environment factory."""
    return WeakPadEnv(spec, scene_dir, **kwargs)
