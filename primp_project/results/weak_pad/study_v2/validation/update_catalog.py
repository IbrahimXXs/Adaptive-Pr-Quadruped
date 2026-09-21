"""Label the completed held-out study and refresh only the result inventory."""
from collections import Counter
import json
from pathlib import Path

from primp_project.recording.catalog import refresh_catalog


def update(study):
    study = Path(study).resolve()
    state = json.loads((study/"study_state.json").read_text())
    manifest = json.loads((study/"split_manifest.json").read_text())
    expected = {trial["trial_id"] for trial in manifest["trials"]}
    if set(state["trials"]) != expected or any(value["status"] != "completed" for value in state["trials"].values()):
        raise ValueError("Wait for every predeclared trial before the final inventory update")
    root = study.parent.parent
    annotation_path = root/"annotations.json"
    annotations = json.loads(annotation_path.read_text())
    run_ids = set()
    for trial in manifest["trials"]:
        trial_id = trial["trial_id"]
        run_id = Path(state["trials"][trial_id]["run_dir"]).name
        run_ids.add(run_id)
        entry = annotations.setdefault(run_id, {})
        entry["purpose"] = f"Weak foothold V2 held-out evaluation: {trial['case_id']}, {trial['strategy']}, seed {trial['seed']}"
        entry.setdefault("notes", [])
    annotation_path.write_text(json.dumps(annotations, indent=2, ensure_ascii=False)+"\n")
    records = refresh_catalog(root)
    formal = [record for record in records if record["id"] in run_ids]
    if len(formal) != len(expected):
        raise ValueError("Catalog did not find every completed formal recording")
    output = dict(total_catalog_recordings=len(records), formal_v2_recordings=len(formal),
        formal_outcomes=dict(Counter(record["outcome"] for record in formal)),
        formal_catalog_statuses=dict(Counter(record["status"] for record in formal)),
        protocol_v2_recordings=sum(record.get("protocol_version") == 2 for record in records),
        all_recovered_stops_distinct_from_success=all(
            record["status"] == "RECOVERED_STOP" and record["physical_success"] is False
            for record in formal if record["outcome"] == "RECOVERED_STOP"),
        raw_recordings_modified=False)
    (study/"validation/catalog_validation.json").write_text(json.dumps(output, indent=2)+"\n")
    return output


if __name__ == "__main__":
    print(json.dumps(update(Path(__file__).resolve().parent.parent), indent=2))
