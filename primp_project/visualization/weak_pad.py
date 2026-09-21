"""Replay measured robot states and recorded weak-pad deformation offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

import cv2
import mujoco
import numpy as np

from primp_project.environment.weak_pad import set_pad_sink_displacement


def restore_frame(model, data, qpos, qvel, time_s, sink_displacement_m):
    """Restore both robot and surface state; never execute a physics step."""
    data.qpos[:] = qpos
    data.qvel[:] = qvel
    data.time = float(time_s)
    moved = set_pad_sink_displacement(model, data, sink_displacement_m)
    if not moved:
        mujoco.mj_forward(model, data)


def read_recording(run_dir):
    """Validate the additional recorded geometry needed beyond robot qpos."""
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir/"metadata.json").read_text())
    if metadata.get("experiment") != "weak_pad":
        raise ValueError("Weak replay requires a weak_pad recording")
    with np.load(run_dir/"signals.npz", allow_pickle=False) as archive:
        required = ("time_s", "qpos", "qvel", "phase", "contact_measured",
                    "pad_sink_displacement_m", "pad_failed")
        missing = sorted(set(required)-set(archive.files))
        if missing:
            raise ValueError(f"Weak replay requires recorded robot and deformation signals: {missing}")
        states = {name: archive[name] for name in required}
    times = np.asarray(states["time_s"], dtype=float)
    if len(times) < 2 or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("Weak replay requires a monotonic recorded clock")
    if any(len(value) != len(times) for value in states.values()):
        raise ValueError("Robot, contact, and surface replay signals must align")
    truth = json.loads((run_dir/"scene/weak_pad_truth.json").read_text())
    sink = np.asarray(states["pad_sink_displacement_m"], dtype=float)
    if (not np.all(np.isfinite(sink)) or np.any(sink < -1e-12)
            or np.any(sink > float(truth["sink_depth_m"])+1e-12) or np.any(np.diff(sink) < -1e-12)):
        raise ValueError("Recorded deformation must be finite, irreversible, and bounded by the simulator depth")
    if np.any((sink > 1e-12) & ~states["pad_failed"].astype(bool)):
        raise ValueError("Recorded sinking cannot precede simulator failure")
    return metadata, truth, states


def _overlay(frame, index, states, metadata, truth):
    width, height = frame.shape[1], frame.shape[0]
    cv2.rectangle(frame, (0, 0), (width, 104), (244, 246, 248), -1)
    failed = bool(states["pad_failed"][index])
    sink = float(states["pad_sink_displacement_m"][index])*1000
    lines = [
        "RECORDED SIMULATION  |  WEAK-PAD EVALUATION REPLAY",
        f"t = {states['time_s'][index]:5.2f} s    phase: {states['phase'][index]}    strategy: {metadata.get('strategy', 'unknown')}",
        f"Hidden capacity: {truth['failure_load_n']:g} N    pad: {'FAILED' if failed else 'INTACT'}    actual sink: {sink:.1f} mm",
    ]
    for text, y, scale in zip(lines, (27, 57, 86), (.58, .56, .55), strict=True):
        cv2.putText(frame, text, (16, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (37, 43, 49), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (0, height-44), (width, height), (244, 246, 248), -1)
    labels = "    ".join(f"{leg}: {'CONTACT' if contact else 'AIR'}"
                         for leg, contact in zip(("FL", "FR", "RL", "RR"), states["contact_measured"][index], strict=True))
    cv2.putText(frame, labels, (16, height-16), cv2.FONT_HERSHEY_SIMPLEX, .56, (37, 43, 49), 1, cv2.LINE_AA)
    return frame


def render_replay(run_dir, *, output=None, fps=20, width=960, height=720,
                  speed=1., start_s=0., end_s=None, preview_only=False):
    """Write replay MP4/PNG/JSON from measured robot and pad states only."""
    run_dir = Path(run_dir).resolve()
    if not 1 <= fps <= 30 or not 320 <= width <= 960 or not 240 <= height <= 720:
        raise ValueError("Weak replay supports 1–30 fps and dimensions up to 960x720")
    if not np.isfinite(speed) or speed <= 0 or not np.isfinite(start_s) or start_s < 0:
        raise ValueError("Replay speed must be positive and start time nonnegative")
    metadata, truth, states = read_recording(run_dir)
    times = states["time_s"]
    finish = float(times[-1]) if end_s is None else min(float(end_s), float(times[-1]))
    if not np.isfinite(finish) or start_s >= finish:
        raise ValueError("Replay interval must intersect the recording")
    frame_times = np.arange(max(start_s, float(times[0])), finish+1e-10, speed/fps)
    indices = np.clip(np.searchsorted(times, frame_times), 0, len(times)-1)
    scene_path = run_dir/"scene/scene.xml"
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    model.vis.global_.offwidth, model.vis.global_.offheight = width, height
    model.geom("primp_landing_pad").rgba[:] = (1., .43, .08, 1.)
    model.vis.headlight.ambient[:] = (.5, .5, .5)
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    camera.lookat[:] = (.035, 0., .11)
    camera.distance, camera.azimuth, camera.elevation = 1.25, -65, -25
    options = mujoco.MjvOption()
    options.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = False
    output = Path(output).resolve() if output else run_dir/"media/weak_replay.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    preview = output.with_suffix(".png")
    renderer = mujoco.Renderer(model, height=height, width=width)
    writer, codec = None, None

    def render(index):
        restore_frame(model, data, states["qpos"][index], states["qvel"][index],
                      times[index], states["pad_sink_displacement_m"][index])
        renderer.update_scene(data, camera=camera, scene_option=options)
        frame = cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)
        return _overlay(frame, index, states, metadata, truth)

    try:
        # Show collapse when present, otherwise the subsequent airborne-foot
        # progression rather than an unrelated middle-of-recording probe.
        sunk = np.flatnonzero(states["pad_sink_displacement_m"] > .003)
        progressed = np.flatnonzero(states["phase"].astype(str) == "progress_hold")
        preview_index = (int(sunk[-1]) if len(sunk) else int(progressed[len(progressed)//2])
                         if len(progressed) else int(indices[len(indices)//2]))
        if not cv2.imwrite(str(preview), render(preview_index)):
            raise RuntimeError("Could not write weak-pad replay preview")
        if preview_only:
            return dict(preview=str(preview), preview_time_s=float(times[preview_index]))
        for candidate in ("avc1", "mp4v"):
            writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*candidate), float(fps), (width, height))
            if writer.isOpened():
                codec = candidate
                break
            writer.release()
        if codec is None:
            raise RuntimeError("Installed OpenCV has no usable MP4 encoder")
        for index in indices:
            writer.write(render(int(index)))
        writer.release()
        writer = None
    finally:
        if writer is not None:
            writer.release()
        renderer.close()
    capture = cv2.VideoCapture(str(output))
    try:
        readable, _ = capture.read()
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if not readable or frame_count != len(indices):
        raise RuntimeError("Weak replay decode validation failed")
    result = dict(run_id=run_dir.name, video=str(output), preview=str(preview),
        codec=codec, fps=fps, resolution=[width, height], frame_count=frame_count, playback_speed=speed,
        recorded_start_time_s=float(times[indices[0]]), recorded_end_time_s=float(times[indices[-1]]),
        preview_time_s=float(times[preview_index]),
        signals_sha256=hashlib.sha256((run_dir/"signals.npz").read_bytes()).hexdigest(),
        scene_sha256=hashlib.sha256(scene_path.read_bytes()).hexdigest(),
        weak_truth_sha256=hashlib.sha256((run_dir/"scene/weak_pad_truth.json").read_bytes()).hexdigest(),
        method="Restore recorded qpos/qvel and pad_sink_displacement_m with mj_forward; no mj_step or controller execution",
        presentation="Orange weak target; hidden capacity, failure, and sink shown only as evaluation-replay truth")
    output.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--speed", type=float, default=1.)
    parser.add_argument("--start", type=float, default=0.)
    parser.add_argument("--end", type=float)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(render_replay(args.run_dir, output=args.output, fps=args.fps, speed=args.speed,
                                  start_s=args.start, end_s=args.end, preview_only=args.preview_only), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
