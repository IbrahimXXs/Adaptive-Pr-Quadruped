"""Render recorded MuJoCo states to video without rerunning the controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

# Offscreen EGL is available with this workspace's graphics driver; an explicit
# caller choice (e.g. glfw/osmesa) is respected. Set this before importing MuJoCo.
os.environ.setdefault("MUJOCO_GL", "egl")

import cv2
import mujoco
import numpy as np


def _overlay(frame, *, t, phase, metadata, contacts):
    """Draw evidence labels on the rendered BGR frame."""
    width = frame.shape[1]
    cv2.rectangle(frame, (0, 0), (width, 102), (244, 246, 248), -1)
    actual = metadata["evaluation"]["actual_pad_height_m"]*1000
    estimate = metadata["initial_height_estimate_m"]*1000
    lines = [
        "RECORDED SIMULATION  |  EVALUATION REPLAY",
        f"t = {t:5.2f} s     phase: {phase}     planner: {metadata.get('planner', 'unknown')}",
        f"Orange target: actual {actual:+g} mm   |   initial estimate {estimate:+g} mm",
    ]
    for line, y, scale in zip(lines, (27, 56, 84), (.63, .63, .57), strict=True):
        cv2.putText(frame, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    (37, 43, 49), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (0, frame.shape[0]-47), (width, frame.shape[0]), (244, 246, 248), -1)
    labels = "    ".join(f"{leg}: {'CONTACT' if bool(contact) else 'AIR'}"
                          for leg, contact in zip(("FL", "FR", "RL", "RR"), contacts, strict=True))
    cv2.putText(frame, labels, (18, frame.shape[0]-18), cv2.FONT_HERSHEY_SIMPLEX,
                .57, (37, 43, 49), 1, cv2.LINE_AA)
    return frame


def render_replay(run_dir, *, output=None, fps=30, width=960, height=720,
                  speed=1., start_s=0., end_s=None, preview_only=False):
    """Replay saved qpos/qvel and scene.xml; write MP4, PNG, and provenance.

    No simulation steps, controller imports, or planner imports occur. The
    nearest recorded state at/after each requested frame time is forwarded only
    for rendering. Overlay contact labels come directly from recorded contacts.
    """
    run_dir = Path(run_dir).resolve()
    if not 1 <= fps <= 30 or not 320 <= width <= 960 or not 240 <= height <= 720:
        raise ValueError("Replay supports 1–30 fps and dimensions up to 960x720")
    if not np.isfinite(speed) or speed <= 0 or not np.isfinite(start_s) or start_s < 0:
        raise ValueError("Replay speed must be positive and start time nonnegative")
    metadata = json.loads((run_dir / "metadata.json").read_text())
    if metadata.get("experiment") != "landing_pad":
        raise ValueError("Replay expects a landing-pad recording with a saved scene")
    with np.load(run_dir / "signals.npz", allow_pickle=False) as archive:
        states = {key: archive[key] for key in ("time_s", "qpos", "qvel", "phase", "contact_measured")}
    times = states["time_s"]
    if len(times) < 2 or np.any(np.diff(times) <= 0):
        raise ValueError("Replay requires a nonempty monotonic recorded clock")
    finish = float(times[-1]) if end_s is None else min(float(end_s), float(times[-1]))
    if not np.isfinite(finish) or start_s >= finish:
        raise ValueError("Replay interval must intersect the recording")
    frame_times = np.arange(max(start_s, float(times[0])), finish+1e-10, speed/fps)
    indices = np.clip(np.searchsorted(times, frame_times), 0, len(times)-1)
    scene_path = run_dir / "scene" / "scene.xml"
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    model.vis.global_.offwidth = width
    model.vis.global_.offheight = height
    # Presentation changes only; source MJCF and measured states stay untouched.
    model.geom("primp_landing_pad").rgba[:] = (1., .43, .08, 1.)
    model.vis.headlight.ambient[:] = (.5, .5, .5)
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    camera.lookat[:] = (.005, .0, .13)
    camera.distance = 1.25
    camera.azimuth = -65
    camera.elevation = -25
    options = mujoco.MjvOption()
    options.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = False
    output = Path(output).resolve() if output else run_dir / "replay.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    preview = output.with_suffix(".png")
    renderer = mujoco.Renderer(model, height=height, width=width)
    writer = None
    codec = None

    def render(index):
        data.qpos[:] = states["qpos"][index]
        data.qvel[:] = states["qvel"][index]
        data.time = times[index]
        mujoco.mj_forward(model, data)
        renderer.update_scene(data, camera=camera, scene_option=options)
        frame = cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)
        return _overlay(frame, t=times[index], phase=str(states["phase"][index]),
                        metadata=metadata, contacts=states["contact_measured"][index])

    try:
        hold = np.flatnonzero(states["phase"] == "hold")
        preview_index = int(hold[len(hold)//2]) if len(hold) else int(indices[len(indices)//2])
        if not cv2.imwrite(str(preview), render(preview_index)):
            raise RuntimeError("Could not write replay preview")
        if preview_only:
            return {"preview": str(preview), "preview_time_s": float(times[preview_index])}
        # H.264 is preferred when OpenCV's installed backend includes it. The
        # usual minimal Linux build supports MPEG-4 Part 2 in an MP4 container.
        for candidate in ("avc1", "mp4v"):
            writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*candidate),
                                     float(fps), (width, height))
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
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if not readable or frames != len(indices):
        raise RuntimeError(f"Replay decode validation failed: {frames} frames, expected {len(indices)}")
    result = {
        "run_id": run_dir.name, "video": str(output), "preview": str(preview),
        "codec": codec, "fps": fps, "resolution": [width, height], "frame_count": frames,
        "playback_speed": speed, "recorded_start_time_s": float(times[indices[0]]),
        "recorded_end_time_s": float(times[indices[-1]]), "preview_time_s": float(times[preview_index]),
        "signals_sha256": hashlib.sha256((run_dir / "signals.npz").read_bytes()).hexdigest(),
        "scene_sha256": hashlib.sha256(scene_path.read_bytes()).hexdigest(),
        "method": "Recorded qpos/qvel plus mj_forward for visualization; no mj_step or controller execution.",
        "presentation": "Target pad recolored orange; fixed camera and recorded-value labels added for evaluation replay.",
    }
    output.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--speed", type=float, default=1.)
    parser.add_argument("--start", type=float, default=0.)
    parser.add_argument("--end", type=float)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args(argv)
    result = render_replay(args.run_dir, output=args.output, fps=args.fps,
                           speed=args.speed, start_s=args.start, end_s=args.end,
                           preview_only=args.preview_only)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
