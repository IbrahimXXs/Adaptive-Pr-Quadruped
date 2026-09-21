"""Index selected formal replay artifacts without modifying native recordings."""
import hashlib
import json
from pathlib import Path


SELECTION = (
    ("fr_necessary_a_capacity66_adaptive_force_fixed_posture_seed101", "66 N, adaptive force with fixed posture", "SAFE_STOP"),
    ("fr_necessary_a_capacity66_adaptive_probe_seed101", "66 N, adaptive probe", "SUCCESS"),
    ("fr_necessary_a_capacity34_adaptive_probe_seed101", "34 N, adaptive probe", "RECOVERED_STOP"),
)


def index(study):
    study = Path(study).resolve()
    state = json.loads((study/"study_state.json").read_text())
    records = []
    for trial_id, label, expected in SELECTION:
        trial = state["trials"][trial_id]
        if trial["status"] != "completed":
            raise ValueError(f"Selected native trial is not complete: {trial_id}")
        run = Path(trial["run_dir"])
        summary = json.loads((run/"weak_pad_summary.json").read_text())
        replay_path = run/"media/weak_replay.json"
        replay = json.loads(replay_path.read_text())
        if trial["outcome"] != expected or not replay["decode_validation"]["all_frames_decoded"]:
            raise ValueError(f"Unexpected outcome or incomplete replay decode: {trial_id}")
        if not replay.get("visual_validation", {}).get("preview_inspected"):
            raise ValueError(f"Preview still needs independent visual review: {trial_id}")
        raw_hash = hashlib.sha256((run/"signals.npz").read_bytes()).hexdigest()
        if raw_hash != trial["signals_sha256"] or raw_hash != replay["signals_sha256"]:
            raise ValueError(f"Native evidence changed: {trial_id}")
        records.append(dict(trial_id=trial_id, label=label, outcome=trial["outcome"],
            physical_success=summary["physical_success"],
            video=Path(replay["video"]).relative_to(study).as_posix(),
            preview=Path(replay["preview"]).relative_to(study).as_posix(),
            replay_manifest=replay_path.relative_to(study).as_posix(),
            raw_sha256=raw_hash, decoded_frames=replay["decode_validation"]["decoded_frames"],
            preview_measured_state=replay["visual_validation"]["measured_preview_state"]))
    directory = study/"media"
    directory.mkdir(parents=True, exist_ok=True)
    output = dict(controller_rerun=False, native_signals_unchanged=True,
        condition_comparison="The 66 N pair shares trial conditions; the 34 N case demonstrates recovery on a weaker surface.",
        all_frames_decoded=True, all_previews_visually_reviewed=True, records=records)
    (directory/"index.json").write_text(json.dumps(output, indent=2)+"\n")
    lines = ["# Formal weak-pad V2 replays", "",
        "These videos restore recorded robot states and measured pad deformation. No controller was rerun. "
        "The overlays show actual target loading, certified capacity, installed force cap, and physical body movement relative to the first probe. "
        "Hidden pad strength is displayed only as evaluation truth.", "",
        "| Condition and policy | Outcome | Evidence |", "| --- | --- | --- |"]
    for item in records:
        lines.append(f"| {item['label']} | {item['outcome']} | [Video](../{item['video']}) · [Preview](../{item['preview']}) · [Provenance](../{item['replay_manifest']}) |")
    lines.extend(["", "The 66 N trials share the same condition and seed. The 34 N trial tests recovery on a weaker pad. "
        "SAFE_STOP and RECOVERED_STOP are distinct from completed movement. A forward body excursion during a stronger probe alone does not establish task success.", "",
        "Every video frame was decoded, every preview was visually reviewed, and raw recording hashes match the study journal. "
        "[Machine-readable checks](index.json).", ""])
    (directory/"README.md").write_text("\n".join(lines))
    return output


if __name__ == "__main__":
    result = index(Path(__file__).resolve().parent.parent)
    print(json.dumps(result, indent=2))
