"""Reproduce independent analyzer checks without changing native recordings."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from primp_project.analysis.weak_pad import evaluate_weak_pad


def run_review(run_dir):
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    with np.load(run_dir / "signals.npz", allow_pickle=False) as archive:
        recorded = {key: archive[key] for key in archive.files}
    result = dict(
        source_sha256=hashlib.sha256(Path("primp_project/analysis/weak_pad.py").read_bytes()).hexdigest(),
        source_run=str(run_dir),
        raw_sha256=hashlib.sha256((run_dir / "signals.npz").read_bytes()).hexdigest(),
        base_outcome=evaluate_weak_pad(metadata, recorded)["outcome"],
        mutations_in_memory_only=True,
        cases={},
    )
    for name in (
        "lost_support_during_probe", "lost_support_at_completion",
        "incomplete_terminal_declaration", "hide_overload_with_future_flag",
        "list_nested_truth_leak", "short_certificate_dwell",
        "requested_certificate", "missing_mpc_update", "no_actual_progress",
    ):
        current = {key: value.copy() for key, value in recorded.items()}
        current_metadata = json.loads(json.dumps(metadata))
        if name == "lost_support_during_probe":
            index = np.flatnonzero(current["phase"] == "probe_ramp")[20]
            current["contact_measured"][index, 1] = False
            current["contact_normal_force"][index, 1] = 0.
        elif name == "lost_support_at_completion":
            current["contact_measured"][-100:, 1] = False
            current["contact_normal_force"][-100:, 1] = 0.
        elif name == "incomplete_terminal_declaration":
            current_metadata["experiment_complete"] = False
            current["task_complete_declared"][-100:] = False
        elif name == "hide_overload_with_future_flag":
            index = np.flatnonzero(current["phase"] == "progress_complete")[-100]
            current["future_plan_active"][index] = False
            current["actual_pad_normal_force_n"][index] = current["certificate_force_n"][index] + 1.
            current["force_before_deformation_n"][index] = current["actual_pad_normal_force_n"][index]
        elif name == "list_nested_truth_leak":
            current_metadata["planner_inputs"] = [{"failure_load_n": 35.}]
        elif name == "short_certificate_dwell":
            mask = current["certificate_valid"].astype(bool)
            current["probe_evidence_start_time_s"][mask] = current["probe_evidence_end_time_s"][mask] - .05
        elif name == "requested_certificate":
            mask = current["certificate_valid"].astype(bool)
            current["certificate_force_n"][mask] = current["requested_probe_force_n"][mask]
        elif name == "missing_mpc_update":
            current["mpc_update"][np.flatnonzero(current["mpc_update"])[50]] = False
        elif name == "no_actual_progress":
            mask = current["future_plan_active"].astype(bool)
            index = np.flatnonzero(np.char.find(current["phase"].astype(str), "probe") >= 0)[0]
            current["com_pos_w"][mask] = current["com_pos_w"][index]
        outcome = evaluate_weak_pad(current_metadata, current)
        result["cases"][name] = dict(
            outcome=outcome["outcome"], physical_success=outcome["physical_success"],
            failed_checks=[key for key, check in outcome["criteria"].items() if not check["passed"]],
        )
    result["all_mutations_rejected"] = all(not case["physical_success"] for case in result["cases"].values())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_review(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
