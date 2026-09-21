"""Record aligned simulation observations without modifying the live dynamics."""

from collections import defaultdict
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from primp_project import PROJECT_ROOT, REPOSITORY_ROOT

LEGS = ("FL", "FR", "RL", "RR")


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def stack_legs(value):
    return np.stack([np.asarray(value[leg]).reshape(3) for leg in LEGS]).copy()


def ground_contacts(model, data, feet_geom_ids):
    """Active static-ground contacts; sum world force ON each foot, in newtons."""
    counts = np.zeros(4, dtype=np.int32)
    force = np.zeros((4, 3))
    normal_force = np.zeros(4)
    wrench = np.zeros(6)
    foot_index = {int(geom): i for i, geom in enumerate(feet_geom_ids)}
    for contact_id, contact in enumerate(data.contact):
        if contact.efc_address < 0:
            continue
        if contact.geom2 in foot_index and model.geom_bodyid[contact.geom1] == 0:
            leg, sign = foot_index[contact.geom2], 1.0
        elif contact.geom1 in foot_index and model.geom_bodyid[contact.geom2] == 0:
            leg, sign = foot_index[contact.geom1], -1.0
        else:
            continue
        mujoco.mj_contactForce(model, data, contact_id, wrench)
        force[leg] += sign * contact.frame.reshape(3, 3).T @ wrench[:3]
        normal_force[leg] += wrench[0]
        counts[leg] += 1
    return counts > 0, force, normal_force, counts


class StandingRecorder:
    def __init__(self, run_dir, standing_duration_s, settling_duration_s, seed, rendered):
        self.run_dir = Path(run_dir)
        self.rows = defaultdict(list)
        self.started = False
        self.metadata = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "standing_duration_s": standing_duration_s,
            "settling_duration_s": settling_duration_s,
            "seed": seed,
            "rendered": rendered,
            "legs": LEGS,
            "status": "initializing",
            "conventions": {
                "sample": "Post-step state on copied MjData, refreshed with mj_forward; live MjData is unchanged.",
                "time_s": "Seconds since reset returned; initial MuJoCo time is retained separately.",
                "control_time_s": "Start of the integration interval; desired positions/forces and command held over this interval.",
                "contact_force_w": "Instantaneous simulated constraint reaction at sample state under held control, ON the foot, world XYZ, N; not an integrated impulse or hardware sensor.",
                "contact_measured": "At least one active constraint (efc_address >= 0) between exact foot geom and a world-body geom. Intended for static flat terrain.",
                "feet_pos_w": "Foot geometry center in world XYZ metres; not ground contact point.",
                "feet_desired_w": "wb.last_des_foot_pos: swing trajectory sample or stance MPC foothold. Stance targets follow recent measured positions, not fixed world anchors.",
                "feet_foothold_ref_w": "Foothold planner touchdown reference, separate from instantaneous desired foot position.",
                "contact_planned": "wb.current_contact used for current torque; distinct from physical contact.",
                "gait_phase": "Raw PGG phase, dimensionless. FULL_STANCE resets phase to constant offsets; it is not elapsed standing phase.",
                "phase": "settling or standing; phase_time_s measures elapsed seconds within that phase.",
                "base_quat_wxyz": "Unit quaternion, scalar first; base_rpy_rad is extrinsic XYZ roll/pitch/yaw in radians.",
                "base_ang_vel_b": "Angular velocity in base frame, rad/s; linear velocities and all positions are world frame.",
                "com_pos_w": "Physical model CoM from body-mass-weighted xipos, independent of the controller's CoM estimate.",
                "mpc_status": "Held latest acados NLP status; count solves only where mpc_update is true. Status 2 is expected with default one-iteration SQP.",
                "qp_status": "Maximum absolute underlying QP status from latest solve (0 means success).",
                "solver_time_s": "Latest acados solve time; wall_time_s is recorder elapsed wall time, including rendering and logging.",
                "actuator_torque": "Applied torque after clipping, model actuator order, Nm; torque_saturated reports pre-clip limit violations.",
            },
        }

    def write_metadata(self):
        (self.run_dir / "metadata.json").write_text(json.dumps(json_value(self.metadata), indent=2) + "\n")

    def start(self, env, cfg):
        self.model = env.mjModel
        self.data = mujoco.MjData(self.model)
        self.feet_geom_ids = np.array([env._feet_geom_id[leg] for leg in LEGS])
        self.origin_time = float(env.simulation_time)
        self.wall_start = time.perf_counter()
        self.dt = float(env.simulation_dt)
        self.mpc_period = round(1 / (cfg.simulation_params["mpc_frequency"] * self.dt))
        mujoco.mj_copyData(self.data, self.model, env.mjData)
        mujoco.mj_forward(self.model, self.data)
        initial_contact, _, _, _ = ground_contacts(self.model, self.data, self.feet_geom_ids)
        versions = {}
        for package in ("mujoco", "gym-quadruped", "numpy", "scipy", "casadi", "acados-template"):
            versions[package] = importlib.metadata.version(package)
        repo = REPOSITORY_ROOT
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        patch = subprocess.run(["git", "diff", "--", "quadruped_pympc/config.py", "simulation/simulation.py"], cwd=repo, capture_output=True, text=True, check=True).stdout
        (self.run_dir / "source_changes.patch").write_text(patch)
        # Preserve package paths in new recordings. Historical snapshots retain
        # the exact source and layout that produced those measurements.
        import shutil
        for relative in ("__init__.py", "__main__.py", "experiments/standing.py",
                         "recording/standing.py", "recording/catalog.py", "analysis/standing.py"):
            target = self.run_dir / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / relative, target)
        self.metadata.update({
            "status": "running", "robot": cfg.robot, "controller": cfg.mpc_params["type"],
            "dt_s": self.dt, "sample_rate_hz": 1 / self.dt,
            "expected_steps": round((self.metadata["standing_duration_s"] + self.metadata["settling_duration_s"]) / self.dt),
            "initial_mujoco_time_s": self.origin_time, "initial_qpos": env.mjData.qpos.copy(),
            "initial_qvel": env.mjData.qvel.copy(), "model_mass_kg": float(self.model.body_mass.sum()),
            "initial_contact_measured": initial_contact,
            "initial_feet_pos_w": self.data.geom_xpos[self.feet_geom_ids].copy(),
            "gravity_m_s2": float(np.linalg.norm(self.model.opt.gravity)), "config_mass_kg": cfg.mass,
            "mpc_params": cfg.mpc_params, "simulation_params": cfg.simulation_params,
            "git_commit": revision, "packages": versions, "actuator_names": [self.model.actuator(i).name for i in range(self.model.nu)],
        })
        self.started = True
        self.write_metadata()

    def record_step(self, env, wrapper, episode, control_step, control_time, action,
                    torque_saturated, cmd_lin, cmd_ang, terminated, truncated):
        # mj_step updates qpos but leaves derived geometry/contact fields stale.
        # Recompute diagnostics on a copy so recording cannot change the controller.
        mujoco.mj_copyData(self.data, self.model, env.mjData)
        mujoco.mj_forward(self.model, self.data)
        t = float(self.data.time - self.origin_time)
        settle = self.metadata["settling_duration_s"]
        standing = t > settle + self.dt * 1e-6
        wb = wrapper.wb_interface
        measured, forces, normal, counts = ground_contacts(self.model, self.data, self.feet_geom_ids)
        controller = wrapper.srbd_controller_interface.controller
        solver = controller.acados_ocp_solver
        qp = np.asarray(solver.get_stats("qp_stat"), dtype=int)
        row = {
            "time_s": t, "mujoco_time_s": float(self.data.time),
            "control_time_s": float(control_time - self.origin_time),
            "wall_time_s": time.perf_counter() - self.wall_start,
            "phase": "standing" if standing else "settling",
            "phase_time_s": max(0.0, t - settle) if standing else t,
            "episode": episode, "step": control_step + 1,
            "base_pos_w": self.data.qpos[:3], "base_quat_wxyz": self.data.qpos[3:7],
            "base_rpy_rad": Rotation.from_quat(self.data.qpos[3:7], scalar_first=True).as_euler("xyz"),
            "base_lin_vel_w": self.data.qvel[:3], "base_ang_vel_b": self.data.qvel[3:6],
            "com_pos_w": np.sum(self.model.body_mass[:, None] * self.data.xipos, axis=0) / self.model.body_mass.sum(),
            "qpos": self.data.qpos, "qvel": self.data.qvel,
            "feet_pos_w": self.data.geom_xpos[self.feet_geom_ids],
            "feet_desired_w": stack_legs(wb.last_des_foot_pos),
            "feet_foothold_ref_w": stack_legs(wrapper.get_obs()["ref_feet_pos"]),
            "feet_mpc_foothold_w": stack_legs(wrapper.nmpc_footholds),
            "contact_measured": measured, "contact_force_w": forces,
            "contact_normal_force": normal, "contact_count": counts,
            "contact_planned": np.asarray(wb.current_contact, dtype=bool),
            "grf_desired_w": stack_legs(wrapper.nmpc_GRFs),
            "gait_phase": wb.pgg.phase_signal, "swing_time_s": wb.stc.swing_time,
            "cmd_lin_vel_w": cmd_lin, "cmd_ang_vel_w": cmd_ang,
            "actuator_torque": action, "torque_saturated": torque_saturated,
            "mpc_update": control_step % self.mpc_period == 0,
            "mpc_status": int(controller.previous_status),
            "qp_status": int(np.max(np.abs(qp), initial=0)),
            "solver_time_s": float(solver.get_stats("time_tot")),
            "terminated": bool(terminated), "truncated": bool(truncated),
            "numerical_warning_count": int(sum(w.number for w in env.mjData.warning)),
        }
        for key, value in row.items():
            self.rows[key].append(np.array(value, copy=True))

    def save(self, status, error=None):
        self.metadata["status"] = status
        self.metadata["error"] = error
        self.metadata["recorded_steps"] = len(self.rows.get("time_s", []))
        self.write_metadata()
        if not self.rows:
            return
        arrays = {key: np.asarray(value) for key, value in self.rows.items()}
        np.savez_compressed(self.run_dir / "signals.npz", **arrays)
        # CSV is deliberately explicit and flat for inspection without custom tools.
        headers, columns = [], []
        xyz = ("x", "y", "z")
        for key, array in arrays.items():
            flat = array.reshape(len(array), -1)
            for i in range(flat.shape[1]):
                if array.ndim == 3 and array.shape[1:] == (4, 3):
                    suffix = f"_{LEGS[i // 3]}_{xyz[i % 3]}"
                elif array.ndim == 2 and key in {"contact_measured", "contact_planned", "contact_normal_force", "contact_count", "gait_phase", "swing_time_s"}:
                    suffix = f"_{LEGS[i]}"
                elif array.ndim == 2 and array.shape[1] == 3:
                    suffix = f"_{xyz[i]}"
                elif array.ndim == 2 and key == "base_quat_wxyz":
                    suffix = f"_{'wxyz'[i]}"
                else:
                    suffix = f"_{i}" if flat.shape[1] > 1 else ""
                headers.append(key + suffix)
                columns.append(flat[:, i])
        with (self.run_dir / "samples.csv").open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(zip(*columns))
        with (self.run_dir / "contact_events.csv").open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["time_s", "leg", "event", "phase", "planned_support", "normal_force_N"])
            previous = np.asarray(self.metadata["initial_contact_measured"], dtype=bool)
            for i, contact in enumerate(arrays["contact_measured"]):
                for leg in np.flatnonzero(contact != previous):
                    writer.writerow([arrays["time_s"][i], LEGS[leg], "touchdown" if contact[leg] else "liftoff",
                                     arrays["phase"][i], arrays["contact_planned"][i, leg], arrays["contact_normal_force"][i, leg]])
                previous = contact
