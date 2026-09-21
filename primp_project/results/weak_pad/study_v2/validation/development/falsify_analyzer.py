"""Native-record V2 analyzer falsification; input recordings stay untouched."""
import hashlib
import json
from pathlib import Path

import numpy as np

from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2


SOURCES = {
    "success": "weak_pad_fixed_probe_20260921T105743_948963Z",
    "recovery": "weak_pad_fixed_probe_20260921T105745_065855Z",
}


def review():
    root = Path("primp_project/results/weak_pad/development_v2")
    original_metadata, recorded = {}, {}
    report = dict(source_sha256=hashlib.sha256(Path("primp_project/analysis/weak_pad_v2.py").read_bytes()).hexdigest(),
        base_source_sha256=hashlib.sha256(Path("primp_project/analysis/weak_pad.py").read_bytes()).hexdigest(),
        mutations_in_memory_only=True, raw_files_unchanged=True, raw_sha256={}, baseline_outcomes={}, cases={})
    for kind, run_id in SOURCES.items():
        run = root/run_id
        original_metadata[kind] = json.loads((run/"metadata.json").read_text())
        with np.load(run/"signals.npz", allow_pickle=False) as archive:
            recorded[kind] = {key: archive[key] for key in archive.files}
        report["raw_sha256"][kind] = hashlib.sha256((run/"signals.npz").read_bytes()).hexdigest()
        report["baseline_outcomes"][kind] = evaluate_weak_pad_v2(original_metadata[kind], recorded[kind])["outcome"]

    for kind, name in (
        ("success", "unsupported_position_noise"), ("success", "unaccounted_sensor_delay"),
        ("success", "realized_sensor_error"), ("success", "missed_monitor"),
        ("success", "aligned_transient_contact_loss"),
        ("recovery", "no_actual_recovery_lift"), ("recovery", "no_commanded_recovery_lift"),
        ("recovery", "lost_terminal_support"), ("recovery", "recovery_before_failure_then_probe_resumed"),
        ("recovery", "recovery_keeps_commanding_load"),
        ("recovery", "recovery_two_phase_rows_hide_support_loss"),
    ):
        metadata = json.loads(json.dumps(original_metadata[kind]))
        data = {key: value.copy() for key, value in recorded[kind].items()}
        if name == "unsupported_position_noise":
            metadata["sensor_config"]["position_noise_m"] = .1
        elif name == "unaccounted_sensor_delay":
            metadata["sensor_delay_s"] = .04
        elif name == "realized_sensor_error":
            index = np.flatnonzero(data["phase"] == "progress_hold")[100]
            data["sensor_pad_normal_force_n"][index] += 1.
        elif name == "missed_monitor":
            index = np.flatnonzero(data["phase"] == "probe_release")[100]
            data["certificate_monitor_update"][index] = False
        elif name == "aligned_transient_contact_loss":
            index = np.flatnonzero(data["phase"] == "probe_release")[100]
            data["contact_measured"][index, 0] = False
            data["contact_normal_force"][index, 0] = 0.
            data["actual_pad_normal_force_n"][index] = 0.
            data["force_before_deformation_n"][index] = 0.
            data["pad_contact"][index] = False
            data["sensor_contact_measured"][index+1, 0] = False
            data["sensor_pad_normal_force_n"][index+1] = 0.
            data["certificate_valid"][index+1] = False
            data["certificate_invalidation_reason"][index+1] = "lost_contact"
        elif name in ("no_actual_recovery_lift", "no_commanded_recovery_lift"):
            rows = np.flatnonzero(np.char.find(data["phase"].astype(str), "recovery") >= 0)
            anchor_z = data["feet_pos_w"][rows[0], 0, 2]
            if name == "no_actual_recovery_lift":
                data["feet_pos_w"][rows, 0, 2] = anchor_z
                data["sensor_pad_foot_pos_w"][1:] = data["feet_pos_w"][:-1, 0]
            else:
                data["feet_desired_w"][rows, 0, 2] = anchor_z
        elif name == "lost_terminal_support":
            data["contact_measured"][-1, 1] = False
            data["contact_normal_force"][-1, 1] = 0.
        elif name == "recovery_before_failure_then_probe_resumed":
            index = np.flatnonzero(data["phase"] == "probe_ramp")[100]
            data["phase"][index] = "recovery_unload"
            data["recovery_triggered"][index] = True
            data["recovery_start_time_s"][index] = data["control_time_s"][index]
            data["recovery_foot_anchor_w"][index] = data["recovery_foot_anchor_w"][-1]
        elif name == "recovery_keeps_commanding_load":
            rows = np.flatnonzero(data["phase"] == "recovery_hold")
            data["grf_desired_w"][rows, 0, 2] = 30.
            data["planned_pad_force_n"][rows] = 30.
            data["applied_pad_force_cap_n"][rows] = 30.
        elif name == "recovery_two_phase_rows_hide_support_loss":
            index = np.flatnonzero(data["phase"] == "recovery_unload")[10]
            data["phase"][index:index+2] = "stand"
            data["contact_measured"][index, 1] = False
            data["contact_normal_force"][index, 1] = 0.
            data["sensor_contact_measured"][index+1, 1] = False
        result = evaluate_weak_pad_v2(metadata, data)
        report["cases"][name] = dict(baseline=kind, outcome=result["outcome"],
            rejected=result["outcome"] not in ("SUCCESS", "RECOVERED_STOP", "SAFE_STOP"),
            failed_checks=[key for key, value in result["criteria"].items() if not value["passed"]])
    report["all_mutations_rejected"] = all(value["rejected"] for value in report["cases"].values())
    return report


if __name__ == "__main__":
    result = review()
    path = Path(__file__).resolve().parent/"analyzer_review_after.json"
    path.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
