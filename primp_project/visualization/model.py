"""Inspect body/foot/timing coordination in a fitted landing-motion model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from primp_project import RESULTS_ROOT
from primp_project.learning import PRIMPMotionModel, relative_features


def _midpoint_timing_diagnostics(model, height_std_m):
    """In-sample state/timing covariance check; never an evaluation score."""
    result = []
    for record in model.metadata.get("training_records", []):
        path = Path(record["run_directory"])/"signals.npz"
        if not path.exists():
            result.append(dict(run_id=record["run_id"], unavailable="Training signal path is unavailable"))
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["signals_sha256"]:
            raise ValueError(f"Training signals changed after fitting: {record['run_id']}")
        with np.load(path, allow_pickle=False) as signals:
            first = np.flatnonzero(signals["phase"] == "lower")[0]
            last = np.flatnonzero(signals["phase"] == "reload")[0]
            middle = (first+last)//2
            observed = relative_features(
                signals["com_pos_w"][middle], Rotation.from_euler("xyz", signals["base_rpy_rad"][middle]),
                signals["feet_pos_w"][middle, 0], start_com_position=signals["com_pos_w"][first],
                start_body_rotation=Rotation.from_euler("xyz", signals["base_rpy_rad"][first]),
                start_foot_position=signals["feet_pos_w"][first, 0])
        prediction = model.condition(record["known_height_m"], height_std_m,
                                     current_phase=.5, current_features=observed)
        result.append(dict(run_id=record["run_id"], known_training_height_m=record["known_height_m"],
                           measured_duration_s=record["measured_lowering_duration_s"],
                           midpoint_state_conditioned_duration_s=prediction.duration_s))
    return result


def visualize_model(model_path, *, output_dir=None, height_std_m=.0005):
    """Plot conditioned mean motions with one-standard-deviation model bands.

    These are offline predictions from numerical height-belief queries, not new
    simulator trials and not validation of closed-loop performance.
    """
    model_path = Path(model_path).resolve()
    if model_path.is_dir():
        model_path = model_path/"model.npz"
    output_dir = Path(output_dir) if output_dir is not None else model_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    model = PRIMPMotionModel.load(model_path)
    heights = np.array([-.01, -.005, 0., .005, .01])
    predictions = [model.condition(float(height), height_std_m) for height in heights]
    features = np.stack([prediction.features for prediction in predictions])
    variance = np.stack([prediction.feature_variance for prediction in predictions])
    pitch = np.stack([Rotation.from_rotvec(f[:, 3:6]).as_euler("xyz")[:, 1] for f in features])
    durations = np.array([prediction.duration_s for prediction in predictions])
    log_variance = np.array([prediction.log_duration_variance for prediction in predictions])
    duration_low = durations*np.exp(-np.sqrt(log_variance))
    duration_high = durations*np.exp(np.sqrt(log_variance))
    diagnostics = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_file=str(model_path), model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        metadata_sha256=hashlib.sha256(model_path.with_suffix(".json").read_bytes()).hexdigest(),
        training_demonstrations=model.metadata["training_demonstrations"],
        training_records=model.metadata["training_records"],
        belief_standard_deviation_m=height_std_m,
        feature_names=model.metadata["feature_names"],
        maximum_com_z_separation_across_conditions_m=float(np.ptp(features[:, :, 2], axis=0).max()),
        maximum_foot_z_separation_across_conditions_m=float(np.ptp(features[:, :, 8], axis=0).max()),
        maximum_relative_pitch_separation_across_conditions_deg=float(np.rad2deg(np.ptp(pitch, axis=0)).max()),
        endpoint_com_z_height_slope_m_per_m=float(np.polyfit(heights, features[:, -1, 2], 1)[0]),
        endpoint_foot_z_height_slope_m_per_m=float(np.polyfit(heights, features[:, -1, 8], 1)[0]),
        duration_height_slope_s_per_m=float(np.polyfit(heights, durations, 1)[0]),
        duration_span_across_conditions_s=float(np.ptp(durations)),
        in_sample_midpoint_timing_conditions=_midpoint_timing_diagnostics(model, height_std_m),
        conditions=[dict(
            height_belief_mean_m=float(height), predicted_total_duration_s=float(prediction.duration_s),
            duration_one_sigma_interval_s=[float(low), float(high)],
            endpoint_com_displacement_m=prediction.features[-1, :3].tolist(),
            endpoint_foot_displacement_m=prediction.features[-1, 6:9].tolist(),
            endpoint_relative_body_pitch_deg=float(np.rad2deg(pitch[index, -1])),
            phase=prediction.phase.tolist(), features=prediction.features.tolist(),
            feature_variance=prediction.feature_variance.tolist())
            for index, (height, prediction, low, high) in enumerate(zip(heights, predictions, duration_low, duration_high))],
        conventions=dict(
            predictions="Offline conditional model outputs at lowering entry, anchored to zero relative body/foot state; no desired duration supplied.",
            positions="CoM and foot displacement from their measured lowering-start positions, in metres.",
            rotation="Pitch of the relative SO(3) body rotation; uncertainty uses the local pitch-axis tangent variance, valid for these small rotations.",
            uncertainty="One model standard deviation, not a calibrated confidence interval or empirical trial variability.",
            duration="Predicted total lower-start to first contact-confirmed reload duration, including confirmation dwell.",
            midpoint_diagnostic="Offline conditioning on measured midpoint states from the same training data, demonstrating state/timing covariance only; not a held-out accuracy test or online planner replay.",
            conclusion="Nonzero conditioned changes show learned numerical coordination. They do not establish feasibility, closed-loop benefit or superiority."))
    (output_dir/"conditioning_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, allow_nan=False)+"\n")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    colors = plt.get_cmap("coolwarm")(np.linspace(.05, .95, len(heights)))
    for index, (height, prediction, color) in enumerate(zip(heights, predictions, colors)):
        phase = prediction.phase
        label = f"Belief {height*1000:+.0f} mm"
        for axis, column, ylabel in ((axes[0, 0], 2, "CoM height change (mm)"),
                                    (axes[0, 1], 8, "Foot height change (mm)")):
            mean = features[index, :, column]*1000
            sigma = np.sqrt(variance[index, :, column])*1000
            axis.plot(phase, mean, label=label, color=color)
            axis.fill_between(phase, mean-sigma, mean+sigma, color=color, alpha=.12)
            axis.set(xlabel="Normalized lowering phase", ylabel=ylabel)
        mean_pitch = np.rad2deg(pitch[index])
        sigma_pitch = np.rad2deg(np.sqrt(variance[index, :, 4]))
        axes[1, 0].plot(phase, mean_pitch, label=label, color=color)
        axes[1, 0].fill_between(phase, mean_pitch-sigma_pitch, mean_pitch+sigma_pitch, color=color, alpha=.12)
    axes[0, 0].set_title("Learned body translation")
    axes[0, 1].set_title("Learned front-left foot translation")
    axes[0, 1].legend(fontsize=9)
    axes[1, 0].set(title="Learned relative body orientation", xlabel="Normalized lowering phase", ylabel="Relative body pitch (deg)")
    axes[1, 1].plot(heights*1000, durations, color="#3a536c", marker="o")
    axes[1, 1].fill_between(heights*1000, duration_low, duration_high, color="#3a536c", alpha=.15)
    axes[1, 1].set(title="Learned duration with no desired-time input", xlabel="Height belief mean (mm)", ylabel="Predicted total lowering duration (s)")
    for axis in axes.ravel():
        axis.grid(alpha=.2)
    fig.suptitle(f"PRIMP-based landing family · {model.metadata['training_demonstrations']} measured demonstrations\n"
                 f"Height belief σ = {height_std_m*1000:g} mm · bands = one model standard deviation")
    fig.savefig(output_dir/"conditioned_motions.png", dpi=180)
    plt.close(fig)
    return diagnostics


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project.visualization.model", description=__doc__)
    parser.add_argument("model", type=Path, nargs="?", default=RESULTS_ROOT/"landing_pad"/"study"/"model")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--height-std", type=float, default=.0005)
    args = parser.parse_args(argv)
    diagnostics = visualize_model(args.model, output_dir=args.output_dir, height_std_m=args.height_std)
    print(json.dumps({name: value for name, value in diagnostics.items()
                      if name.startswith(("maximum_", "endpoint_", "duration_"))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
