"""Read-only validation that V2 preserved the original V1 evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(study_dir):
    study_dir = Path(study_dir).resolve()
    inventory_path = study_dir/"v1_training_manifest.json"
    inventory = json.loads(inventory_path.read_text())
    v1 = Path(inventory["source_study_directory"])
    records, checks = [], {}
    checks["v1_split_manifest_unchanged"] = digest(v1/"split_manifest.json") == inventory["source_manifest_sha256"]
    checks["v1_primary_state_unchanged"] = digest(v1/"study_state.json") == inventory["source_state_sha256_at_capture"]
    for record in inventory["records"]:
        directory = Path(record["run_dir"])
        actual = {name: digest(directory/name) for name in ("signals.npz", "metadata.json", "pad_summary.json")}
        matched = {name: value == record[key] for name, value, key in (
            ("signals.npz", actual["signals.npz"], "signals_sha256"),
            ("metadata.json", actual["metadata.json"], "metadata_sha256"),
            ("pad_summary.json", actual["pad_summary.json"], "summary_sha256"))}
        records.append(dict(run_id=record["run_id"], actual_sha256=actual,
                            matches_reserved_v1_inventory=matched, passed=all(matched.values())))
    checks["nine_inherited_recordings_unchanged"] = len(records) == 9 and all(row["passed"] for row in records)
    evaluations = []
    for label, state_path in (("primary", v1/"study_state.json"),
                              ("reserved_heights", v1/"held_out_heights/study_state.json")):
        state = json.loads(state_path.read_text())
        for trial_id, entry in state["trials"].items():
            if entry.get("parameters", {}).get("role") != "evaluation":
                continue
            directory = Path(entry["run_dir"])
            actual = {name: digest(directory/name) for name in ("signals.npz", "metadata.json", "pad_summary.json")}
            matched = {name: value == entry[key] for name, value, key in (
                ("signals.npz", actual["signals.npz"], "signals_sha256"),
                ("metadata.json", actual["metadata.json"], "metadata_sha256"),
                ("pad_summary.json", actual["pad_summary.json"], "summary_sha256"))}
            evaluations.append(dict(group=label, trial_id=trial_id, run_id=directory.name,
                                    actual_sha256=actual, matches_original_journal=matched, passed=all(matched.values())))
    checks["twenty_four_v1_evaluations_unchanged"] = len(evaluations) == 24 and all(row["passed"] for row in evaluations)
    state = json.loads((v1/"study_state.json").read_text())
    checks["v1_model_unchanged"] = digest(v1/"model/model.npz") == state["model"]["model_sha256"]
    return dict(audit="Preserved V1 recordings and model during V2 work; read-only hashes, no reanalysis",
                captured_at=datetime.now(timezone.utc).isoformat(), passed=all(checks.values()), checks=checks,
                v1_training_inventory_sha256=digest(inventory_path), demonstrations=records, evaluations=evaluations,
                note="This is a dated integrity snapshot, not a new acceptance analysis or a claim about V2 performance.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.study_dir)
    destination = args.study_dir/"validation/v1_integrity.json"
    destination.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "artifact": str(destination)}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
