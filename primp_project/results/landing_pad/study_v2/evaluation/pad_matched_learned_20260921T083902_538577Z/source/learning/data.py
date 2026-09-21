"""Strict, provenance-recorded extraction of successful training trials only."""

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .primp import PRIMPMotionModel, relative_features
from .recovery import RecoveryMotionModel


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _training_paths(run_dirs, phase_points):
    if isinstance(phase_points, bool) or int(phase_points) != phase_points or phase_points < 3:
        raise ValueError("phase_points must be an integer of at least three")
    run_dirs = [Path(p).resolve() for p in run_dirs]
    if len(run_dirs) != len(set(run_dirs)):
        raise ValueError("Duplicate training run supplied")
    return run_dirs


def _training_metadata(run, *, require_recovery=False):
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
    recovery = metadata.get("recovery_demonstration") is True
    if require_recovery and not recovery:
        raise ValueError(f"{run.name}: recovery training requires explicit recovery_demonstration metadata")
    if "initial_height_estimate_m" in metadata:
        estimate = float(metadata["initial_height_estimate_m"])
        if not np.isfinite(estimate):
            raise ValueError(f"{run.name}: nonfinite initial height estimate")
        if abs(estimate-height) > 1e-9 and not recovery:
            raise ValueError(f"{run.name}: a mismatched height estimate requires explicit recovery_demonstration metadata")
    record = dict(run_id=run.name, run_directory=str(run), role="demonstration",
        signals_sha256=_sha256(signals_path), metadata_sha256=_sha256(metadata_path),
        summary_sha256=_sha256(summary_path), known_height_m=height,
        nominal_lower_duration_s=metadata.get("nominal_lower_duration_s"))
    # Preserve existing V1 record conventions when the newer marker is absent.
    if "recovery_demonstration" in metadata:
        record["recovery_demonstration"] = recovery
    return metadata, height, record, signals_path


def _lowering_bounds(signals, run):
    phases = signals["phase"]
    lower_rows = np.flatnonzero(phases == "lower")
    reload_rows = np.flatnonzero(phases == "reload")
    if not len(lower_rows) or not len(reload_rows):
        raise ValueError(f"{run.name}: missing lowering or confirmed-reload event")
    first = int(lower_rows[0])
    reload_rows = reload_rows[reload_rows > first]
    if not len(reload_rows):
        raise ValueError(f"{run.name}: reload must follow lowering")
    last = int(reload_rows[0])
    if "contact_confirmed" not in signals or not bool(signals["contact_confirmed"][last]):
        raise ValueError(f"{run.name}: reload was not contact-confirmed")
    time = np.asarray(signals["control_time_s"][first:last+1], dtype=float)
    if len(time) < 3 or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0):
        raise ValueError(f"{run.name}: invalid lowering timestamps")
    return first, last


def _measured_window(signals, first, last, phase_points):
    time = np.asarray(signals["control_time_s"][first:last+1], dtype=float)
    duration = float(time[-1]-time[0])
    if len(time) < 3 or duration <= 0 or np.any(np.diff(time) <= 0):
        raise ValueError("A measured motion window needs three increasing timestamps")
    phase = (time-time[0])/duration
    grid = np.linspace(0., 1., phase_points)
    com = np.asarray(signals["com_pos_w"][first:last+1], dtype=float)
    foot = np.asarray(signals["feet_pos_w"][first:last+1, 0], dtype=float)
    rpy = np.asarray(signals["base_rpy_rad"][first:last+1], dtype=float)
    if any(x.shape != (len(time), 3) or not np.all(np.isfinite(x)) for x in (com, foot, rpy)):
        raise ValueError("Measured body and foot states must be finite XYZ triples")
    # Conversion precedes interpolation; wrapped Euler components are never
    # averaged or linearly interpolated.
    rotations = Rotation.from_euler("xyz", rpy)
    com_sample = np.column_stack([np.interp(grid, phase, com[:, j]) for j in range(3)])
    foot_sample = np.column_stack([np.interp(grid, phase, foot[:, j]) for j in range(3)])
    rotation_sample = Slerp(phase, rotations)(grid)
    features = relative_features(com_sample, rotation_sample, foot_sample,
        start_com_position=com[0], start_body_rotation=rotations[0], start_foot_position=foot[0])
    return features, duration


def _attach_provenance(model, records, split_manifest_path):
    manifest_bytes = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    model.metadata["training_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    if split_manifest_path is not None:
        manifest = Path(split_manifest_path).resolve()
        model.metadata["split_manifest"] = str(manifest)
        model.metadata["split_manifest_sha256"] = _sha256(manifest)
    model.metadata["demonstration_source"] = "Successful scripted-controller simulation trials; measured states"


def fit_runs(run_dirs, *, phase_points=41, split_manifest_path=None):
    """Fit measured lowering trajectories from successful demonstration folders.

    Evaluation/development folders are rejected, even if their simulator truth
    happens to be present. Labels come from ``known_height_m``, never from the
    evaluation truth dictionary. An initially incorrect estimate is allowed
    only for explicitly marked recovery demonstrations. The split manifest,
    when supplied, is recorded by hash; run IDs and hashes are always included.
    """
    run_dirs = _training_paths(run_dirs, phase_points)
    features, heights, durations, records = [], [], [], []
    for run in run_dirs:
        _, height, record, signals_path = _training_metadata(run)
        with np.load(signals_path, allow_pickle=False) as signals:
            first, last = _lowering_bounds(signals, run)
            trajectory, duration = _measured_window(signals, first, last, phase_points)
        features.append(trajectory)
        heights.append(height)
        durations.append(duration)
        record["measured_lowering_duration_s"] = duration
        records.append(record)
    model = PRIMPMotionModel.fit(np.asarray(features), heights, durations, training_records=records)
    _attach_provenance(model, records, split_manifest_path)
    model.metadata["segment"] = "First lower phase through first contact-confirmed reload sample"
    return model


def fit_recovery_runs(run_dirs, *, phase_points=41, split_manifest_path=None,
                      window_stride_s=.15, min_remaining_s=.12):
    """Fit current-state→reload motion/time windows after missing contact.

    Requires successful, explicitly marked recovery demonstrations. The current
    measured foot-bottom clearance to the offline ``known_height_m`` label is
    the context; strictly positive time until confirmed reload is the target.
    The current measured CoM, body rotation and foot position define each
    window's origins. Overlapping windows are not independent trials: metadata
    records both the number of source demonstrations and the larger window
    count, plus every window's source and time bounds.
    """
    run_dirs = _training_paths(run_dirs, phase_points)
    if not np.isfinite(window_stride_s) or window_stride_s <= 0:
        raise ValueError("window_stride_s must be finite and positive")
    if not np.isfinite(min_remaining_s) or min_remaining_s <= 0:
        raise ValueError("min_remaining_s must be finite and positive")
    features, clearances, remaining, records, windows = [], [], [], [], []
    for run in run_dirs:
        metadata, height, record, signals_path = _training_metadata(run, require_recovery=True)
        radius = float(metadata.get("foot_radius_m", np.nan))
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError(f"{run.name}: recovery training requires a positive measured-foot radius")
        with np.load(signals_path, allow_pickle=False) as signals:
            first, last = _lowering_bounds(signals, run)
            if "missing_contact" not in signals:
                raise ValueError(f"{run.name}: missing the missing-contact observation log")
            missing_rows = np.flatnonzero(signals["missing_contact"][first:last])+first
            if not len(missing_rows):
                raise ValueError(f"{run.name}: no missing-contact event before confirmed reload")
            first_missing = int(missing_rows[0])
            time = np.asarray(signals["control_time_s"], dtype=float)
            end_time = float(time[last])
            target_times = np.arange(time[first_missing], end_time-min_remaining_s+1e-12, window_stride_s)
            starts = np.unique(np.searchsorted(time[first:last+1], target_times)+first)
            count = 0
            for start in starts:
                start = int(start)
                if start < first_missing or last-start < 2 or end_time-time[start] < min_remaining_s-1e-12:
                    continue
                trajectory, duration = _measured_window(signals, start, last, phase_points)
                measured_bottom = float(signals["feet_pos_w"][start, 0, 2])-radius
                clearance = measured_bottom-height
                if not np.isfinite(clearance):
                    raise ValueError(f"{run.name}: nonfinite measured clearance")
                features.append(trajectory)
                clearances.append(clearance)
                remaining.append(duration)
                windows.append(dict(run_id=run.name, start_sample=start, reload_sample=last,
                    start_time_s=float(time[start]), reload_time_s=end_time,
                    measured_foot_bottom_m=measured_bottom, known_height_m=height,
                    clearance_to_known_surface_m=clearance, remaining_duration_s=duration))
                count += 1
            if not count:
                raise ValueError(f"{run.name}: no recovery window has enough positive remaining duration")
            record.update(first_missing_sample=first_missing, first_missing_time_s=float(time[first_missing]),
                          confirmed_reload_sample=last, recovery_windows=count)
        records.append(record)
    model = RecoveryMotionModel.fit(np.asarray(features), clearances, remaining, training_records=records)
    _attach_provenance(model, records, split_manifest_path)
    model.metadata.update(training_demonstrations=len(records), training_windows=len(windows),
        window_records=windows, window_stride_s=float(window_stride_s), min_remaining_s=float(min_remaining_s),
        segment="Measured states from missing-contact event onward through first contact-confirmed reload",
        window_dependence="Overlapping windows from the same demonstration are correlated; independent trial count is training_demonstrations")
    return model
