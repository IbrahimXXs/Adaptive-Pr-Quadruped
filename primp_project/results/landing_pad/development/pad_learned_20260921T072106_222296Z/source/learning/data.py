"""Strict, provenance-recorded extraction of successful training trials only."""

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .primp import PRIMPMotionModel, relative_features


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_runs(run_dirs, *, phase_points=41, split_manifest_path=None):
    """Fit measured lowering trajectories from successful demonstration folders.

    Evaluation/development folders are rejected, even if their simulator truth
    happens to be present. Labels come from ``known_height_m``, never from the
    evaluation truth dictionary. The split manifest, when supplied, is recorded
    verbatim by hash; run IDs and hashes are always included in model metadata.
    """
    if isinstance(phase_points, bool) or int(phase_points) != phase_points or phase_points < 3:
        raise ValueError("phase_points must be an integer of at least three")
    run_dirs = [Path(p).resolve() for p in run_dirs]
    if len(run_dirs) != len(set(run_dirs)):
        raise ValueError("Duplicate training run supplied")
    features, heights, durations, records = [], [], [], []
    for run in run_dirs:
        metadata_path, signals_path, summary_path = (run/name for name in
                                                    ("metadata.json", "signals.npz", "pad_summary.json"))
        metadata = json.loads(metadata_path.read_text())
        summary = json.loads(summary_path.read_text())
        if metadata.get("experiment") != "landing_pad" or metadata.get("role") != "demonstration":
            raise ValueError(f"{run.name}: only landing-pad demonstration runs may train the model")
        if metadata.get("status") != "completed" or summary.get("passed") is not True:
            raise ValueError(f"{run.name}: failed or incomplete demonstrations are not training data")
        if "known_height_m" not in metadata:
            raise ValueError(f"{run.name}: missing offline known-height training label")
        height = float(metadata["known_height_m"])
        if not np.isfinite(height):
            raise ValueError(f"{run.name}: nonfinite training height")
        with np.load(signals_path, allow_pickle=False) as s:
            phases = s["phase"]
            lower_rows = np.flatnonzero(phases == "lower")
            reload_rows = np.flatnonzero(phases == "reload")
            if not len(lower_rows) or not len(reload_rows):
                raise ValueError(f"{run.name}: missing lowering or confirmed-reload event")
            first = int(lower_rows[0])
            reload_rows = reload_rows[reload_rows > first]
            if not len(reload_rows):
                raise ValueError(f"{run.name}: reload must follow lowering")
            last = int(reload_rows[0])
            if "contact_confirmed" not in s or not bool(s["contact_confirmed"][last]):
                raise ValueError(f"{run.name}: reload was not contact-confirmed")
            time = np.asarray(s["control_time_s"][first:last+1], dtype=float)
            if len(time) < 3 or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0):
                raise ValueError(f"{run.name}: invalid lowering timestamps")
            time -= time[0]
            duration = float(time[-1])
            phase = time/duration
            grid = np.linspace(0., 1., phase_points)
            com = np.asarray(s["com_pos_w"][first:last+1], dtype=float)
            foot = np.asarray(s["feet_pos_w"][first:last+1, 0], dtype=float)
            # Conversion precedes interpolation; wrapped Euler components are
            # never averaged or linearly interpolated.
            rotations = Rotation.from_euler("xyz", s["base_rpy_rad"][first:last+1])
            com_sample = np.column_stack([np.interp(grid, phase, com[:, j]) for j in range(3)])
            foot_sample = np.column_stack([np.interp(grid, phase, foot[:, j]) for j in range(3)])
            rotation_sample = Slerp(phase, rotations)(grid)
            features.append(relative_features(com_sample, rotation_sample, foot_sample,
                            start_com_position=com[0], start_body_rotation=rotations[0],
                            start_foot_position=foot[0]))
            heights.append(height)
            durations.append(duration)
        records.append(dict(run_id=run.name, run_directory=str(run), role="demonstration",
                            signals_sha256=_sha256(signals_path), metadata_sha256=_sha256(metadata_path),
                            summary_sha256=_sha256(summary_path), known_height_m=height,
                            measured_lowering_duration_s=duration,
                            nominal_lower_duration_s=metadata.get("nominal_lower_duration_s")))
    model = PRIMPMotionModel.fit(np.asarray(features), heights, durations, training_records=records)
    manifest_bytes = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    model.metadata["training_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    if split_manifest_path is not None:
        manifest = Path(split_manifest_path).resolve()
        model.metadata["split_manifest"] = str(manifest)
        model.metadata["split_manifest_sha256"] = _sha256(manifest)
    model.metadata["demonstration_source"] = "Successful scripted-controller simulation trials; measured states"
    model.metadata["segment"] = "First lower phase through first contact-confirmed reload sample"
    return model
