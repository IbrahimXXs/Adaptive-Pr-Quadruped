"""Audit native settled-stance necessity using the same full future feasible set."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np

from primp_project.planning.load_capacity import (
    CapacityPlanningConfig, MatchedCapacityPlanner, solve_load_allocation,
)


def audit(run):
    run = Path(run)
    metadata = json.loads((run/"metadata.json").read_text())
    with np.load(run/"signals.npz", allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    first = int(np.flatnonzero(data["phase"] == "probe_ramp")[0])
    anchors = data["feet_desired_w"][first].copy()
    origin = data["probe_origin_com_w"][first].copy()
    weight = metadata["model_mass_kg"]*metadata["gravity_m_s2"]
    upper = np.full(4, weight)
    config = CapacityPlanningConfig(**metadata["movement_optimizer_settings"])
    planner = MatchedCapacityPlanner("adaptive_probe", config)
    _, fixed_maximum = planner.probe_allocation(anchors, weight, origin, 60., upper, allow_posture_change=False)
    moved, moved_maximum = planner.probe_allocation(anchors, weight, origin, 60., upper, allow_posture_change=True)
    ideal = solve_load_allocation(anchors, weight, origin, np.zeros(4), upper, maximize_leg=0)
    minima = {}
    for progress in (.04, .03):
        variant = MatchedCapacityPlanner("adaptive_probe", replace(config, forward_progress_m=progress))
        answer = variant.minimum_future_allocation(anchors, weight, origin, upper)
        minima[str(progress)] = dict(feasible=bool(answer.feasible),
            minimum_future_FL_n=float(answer.forces_n[0]), body_target_w=answer.com_position_w.tolist(),
            support_margin_m=float(answer.support_margin_m), forces_n=answer.forces_n.tolist())
    future = data["future_plan_active"].astype(bool)
    final = data["phase"] == "progress_complete"
    certificate = data["certificate_force_n"]
    cap = data["applied_pad_force_cap_n"]
    command = data["grf_desired_w"][:, 0, 2]
    actual = data["actual_pad_normal_force_n"]
    advance = data["com_pos_w"][:, 0]-origin[0]
    lifted = config.next_lift_leg
    lift = data["feet_pos_w"][:, lifted, 2]-data["next_lift_anchor_w"][:, 2]
    return dict(run_id=run.name, raw_sha256=hashlib.sha256((run/"signals.npz").read_bytes()).hexdigest(),
        first_probe_sample=first, control_time_s=float(data["control_time_s"][first]),
        anchors_from_applied_feet_reference_w=anchors.tolist(),
        anchors_match_independent_prior_physics_max_error_m=float(np.max(np.abs(anchors-data["feet_pos_w"][first-1]))),
        initial_probe_com_w=origin.tolist(), weight_n=weight,
        fixed_raw_maximum_probe_n=fixed_maximum,
        ideal_fixed_maximum_without_force_floors_n=float(ideal.forces_n[0]),
        moved_raw_maximum_probe_n=moved_maximum, moved_robust_probe_command_n=float(moved.forces_n[0]),
        future_global_minima=minima,
        necessary_even_without_original_support_force_floors=bool(ideal.forces_n[0] < min(v["minimum_future_FL_n"] for v in minima.values())),
        initial_certificate_n=float(metadata["capacity_decision_history"][0]["certified_load_n"]),
        stronger_certificate_n=float(certificate[future].min()),
        minimum_installed_future_cap_n=float(cap[future].min()), maximum_installed_future_cap_n=float(cap[future].max()),
        maximum_commanded_future_FL_n=float(command[future].max()), maximum_actual_future_FL_n=float(actual[future].max()),
        maximum_actual_minus_certificate_n=float(np.max((actual-certificate)[future])),
        maximum_command_minus_cap_n=float(np.max((command-cap)[future])),
        final_actual_forward_progress_range_m=[float(advance[final].min()), float(advance[final].max())],
        final_actual_FR_clearance_range_m=[float(lift[final].min()), float(lift[final].max())],
        next_lift_leg="FR", final_FR_contact_absent=bool(not np.any(data["contact_measured"][final, lifted])),
        final_other3_min_force_n=float(data["contact_normal_force"][final][:, [0, 2, 3]].min()),
        note="No controller rerun; global LP minima include full identical future lateral/longitudinal freedoms for all policies; no surface strength used in planning.")


if __name__ == "__main__":
    result = audit("primp_project/results/weak_pad/development_v2/weak_pad_adaptive_probe_20260921T110509_467417Z")
    output = Path(__file__).resolve().parent/"necessary_posture_dev02_audit.json"
    output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
