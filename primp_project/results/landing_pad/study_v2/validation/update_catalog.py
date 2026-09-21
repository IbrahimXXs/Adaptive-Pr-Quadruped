"""Label V2 recordings without changing any recorded metadata or acceptance."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from primp_project.recording.catalog import refresh_catalog


def update(study_dir=Path(__file__).resolve().parents[1]):
    study_dir = Path(study_dir).resolve()
    results = study_dir.parents[1]
    path = results/"annotations.json"
    annotations = json.loads(path.read_text()) if path.exists() else {}
    state = json.loads((study_dir/"study_state.json").read_text())
    identifiers = {Path(entry["run_dir"]).name: key for key, entry in state["trials"].items() if entry.get("run_dir")}
    names = {"reactive": "reactive", "matched_predictive": "matched predictive",
             "matched_learned": "complete learned", "matched_no_body_foot_correlation": "no direct body-foot correlation",
             "matched_no_timing_adaptation": "no learned timing adaptation",
             "matched_no_noncontact_updates": "no noncontact belief updates"}
    count = 0
    for group in ("demonstrations", "development", "evaluation"):
        for metadata_path in sorted((study_dir/group).glob("*/metadata.json")):
            metadata = json.loads(metadata_path.read_text())
            run = metadata_path.parent
            height = metadata["evaluation"]["actual_pad_height_m"]*1000
            planner = names[metadata["planner"]]
            initial = metadata["initial_condition"]
            notes = []
            if group == "demonstrations":
                purpose = f"V2 recovery training: {height:+g} mm, zero estimate, {metadata['nominal_lower_duration_s']:g} s nominal lowering"
                notes.append("One of nine new recovery demonstrations; eligible for the 18-record nominal model and nine-record recovery model. Overlapping windows are not independent trials.")
            elif group == "evaluation":
                purpose = f"V2 formal paired evaluation: {planner}, {height:+g} mm, seed {metadata['seed']}, {initial} clearance"
                notes.append(f"Reserved study cell {identifiers.get(run.name, 'awaiting journal completion')}; shares frozen source/model and records measured initial condition. One preserved attempt, excluded from fitting.")
            else:
                purpose = f"V2 development: {planner}, {height:+g} mm, {initial} clearance"
                notes.append("Unreserved development condition before the formal source freeze; excluded from training and all formal success denominators.")
                summary = json.loads((run/"pad_summary.json").read_text())
                failed = [key for key, value in summary["criteria"].items() if not value["passed"]]
                if failed == ["pad_belief_bounds"]:
                    purpose = "V2 preserved analyzer false rejection: skewed posterior credible interval"
                    notes.append("Retained FAIL: the valid posterior mean lay about 1.2 micrometres outside its 5th/95th percentiles. Means need not lie inside a central credible interval. The analyzer was corrected before freeze; controller/estimator were unchanged and a separate rerun passed. No physical fall.")
            annotations[run.name] = dict(purpose=purpose, notes=notes)
            count += 1
    path.write_text(json.dumps(annotations, indent=2)+"\n")
    records = refresh_catalog(results)
    selected = [record for record in records if record["id"] in annotations and "V2" in annotations[record["id"]]["purpose"]]
    result = dict(annotated_v2_recordings=count, total_recordings=len(records),
                  v2_status_counts={status: sum(record["status"] == status for record in selected)
                                    for status in ("PASS", "FAIL", "UNANALYZED")})
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    update()
