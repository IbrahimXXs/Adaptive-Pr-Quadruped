"""Offline V2 replay with measured loading and origin-referenced motion labels.

Only recorded robot/pad states are replayed. This presentation script adds
evaluation annotations to the existing renderer without changing runtime code.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from primp_project.visualization import weak_pad as replay


def render(run_dir, *, preview_only=False):
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir/"metadata.json").read_text())
    with np.load(run_dir/"signals.npz", allow_pickle=False) as archive:
        evidence = {key: archive[key] for key in (
            "time_s", "phase", "actual_pad_normal_force_n", "certificate_force_n",
            "applied_pad_force_cap_n", "com_pos_w", "probe_origin_com_w", "feet_pos_w", "next_lift_anchor_w")}
    probe = np.flatnonzero(evidence["phase"] == "probe_ramp")
    first_probe = int(probe[0]) if len(probe) else None
    origin = evidence["probe_origin_com_w"][first_probe] if first_probe is not None else None
    recover = np.flatnonzero(np.char.find(evidence["phase"].astype(str), "recovery") >= 0)
    first_recovery = int(recover[0]) if len(recover) else None
    next_leg = metadata.get("next_leg", "RL")
    leg_index = ["FL", "FR", "RL", "RR"].index(next_leg)
    original_overlay = replay._overlay

    def overlay(frame, index, states, meta, truth):
        frame = original_overlay(frame, index, states, meta, truth)
        cv2.rectangle(frame, (0, 103), (frame.shape[1], 157), (244, 246, 248), -1)
        line = (f"Actual target load: {evidence['actual_pad_normal_force_n'][index]:.1f} N"
                f"    certified: {evidence['certificate_force_n'][index]:.1f} N"
                f"    installed cap: {evidence['applied_pad_force_cap_n'][index]:.1f} N")
        cv2.putText(frame, line, (16, 124), cv2.FONT_HERSHEY_SIMPLEX, .49, (37, 43, 49), 1, cv2.LINE_AA)
        if first_probe is None or index < first_probe:
            motion = "Motion relative to first probe: before test"
        else:
            advance = (evidence["com_pos_w"][index, 0]-origin[0])*1000.
            motion = f"Body X from first probe: {advance:+.1f} mm"
            if first_recovery is not None and index >= first_recovery:
                lift = (evidence["feet_pos_w"][index, 0, 2]-evidence["feet_pos_w"][first_recovery, 0, 2])*1000.
                motion += f"    FL recovery clearance: {lift:+.1f} mm"
            else:
                lift = (evidence["feet_pos_w"][index, leg_index, 2]-evidence["next_lift_anchor_w"][index, 2])*1000.
                motion += f"    {next_leg} clearance: {lift:+.1f} mm"
        cv2.putText(frame, motion, (16, 148), cv2.FONT_HERSHEY_SIMPLEX, .49, (37, 43, 49), 1, cv2.LINE_AA)
        return frame

    replay._overlay = overlay
    try:
        result = replay.render_replay(run_dir, fps=20, preview_only=preview_only)
        if not preview_only and evidence["phase"][-1] == "safe_stop":
            start = float(evidence["time_s"][np.flatnonzero(evidence["phase"] == "safe_stop")[0]])
            preview = replay.render_replay(run_dir, fps=20, start_s=start, preview_only=True)
            result["preview_time_s"] = preview["preview_time_s"]
        if preview_only:
            return result
        result["overlay_evidence"] = dict(
            source="Recorded actual target force, certificate, installed cap and measured body/feet",
            progress="Physical CoM world-X minus its first confirmed probe origin; stronger probing is not task completion",
            recovery_lift="Measured FL Z change from first recovery sample",
            next_leg=next_leg, first_probe_sample=first_probe, first_recovery_sample=first_recovery,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        video = Path(result["video"])
        decoder = cv2.VideoCapture(str(video))
        count, dimensions_valid = 0, True
        while True:
            ok, frame = decoder.read()
            if not ok:
                break
            count += 1
            dimensions_valid &= frame.shape == (720, 960, 3)
        decoder.release()
        if count != result["frame_count"] or not dimensions_valid:
            raise RuntimeError("Full video decoding failed")
        result["decode_validation"] = dict(all_frames_decoded=True, decoded_frames=count, resolution_valid=True)
        result["video_sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
        video.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
        return result
    finally:
        replay._overlay = original_overlay


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(render(args.run_dir, preview_only=args.preview_only), indent=2))
