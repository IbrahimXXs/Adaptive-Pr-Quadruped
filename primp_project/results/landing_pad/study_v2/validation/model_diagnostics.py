"""Reproduce descriptive V2 model checks without fitting or editing artifacts.

Run from any directory with the quadruped-pympc environment. The two model
artifacts and their source demonstrations are read-only. Errors reported here
are in-sample descriptive errors over correlated recovery windows, not held-out
performance and not an inflated count of independent demonstrations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from primp_project.learning import PRIMPMotionModel, RecoveryMotionModel


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_vector(model, prediction):
    start = prediction.start_index
    values = prediction.features-model.mean_features[start:]
    values[:, 3:6] = (Rotation.from_rotvec(model.mean_features[start:, 3:6]).inv()
                     * Rotation.from_rotvec(prediction.features[:, 3:6])).as_rotvec()
    return np.r_[values.ravel(), prediction.log_duration_mean]


def mixture_check(model, heights, weights, *, measured_bottom=None):
    weights = np.asarray(weights, dtype=float)
    weights /= weights.sum()
    kwargs = {} if measured_bottom is None else {"current_foot_bottom_m": measured_bottom}
    mixture = model.condition_belief(heights, weights, **kwargs)
    inner = model if measured_bottom is None else model.motion_model
    components = [model.condition_belief([h], [1.], **kwargs) for h in heights]
    means = np.stack([local_vector(inner, component) for component in components])
    average = weights@means
    covariance = sum(w*(component.joint_covariance+np.outer(mean-average, mean-average))
                     for w, component, mean in zip(weights, components, means))
    expected_time = sum(w*component.duration_s for w, component in zip(weights, components))
    expected_second_time = sum(w*(component.duration_s**2+component.duration_std_s**2)
                              for w, component in zip(weights, components))
    report = dict(
        supplied_heights_m=list(map(float, heights)), supplied_weights=weights.tolist(),
        returned_heights_m=mixture.mixture_heights.tolist(), returned_weights=mixture.mixture_weights.tolist(),
        supplied_mean_m=float(weights@heights), returned_mean_m=float(mixture.mixture_weights@mixture.mixture_heights),
        maximum_weight_error=float(np.max(np.abs(mixture.mixture_weights-weights))),
        maximum_mean_error=float(np.max(np.abs(local_vector(inner, mixture)-average))),
        maximum_covariance_error=float(np.max(np.abs(mixture.joint_covariance-covariance))),
        relative_covariance_error=float(np.linalg.norm(mixture.joint_covariance-covariance)/np.linalg.norm(covariance)),
        duration_expectation_error_s=float(abs(mixture.duration_s-expected_time)),
        duration_variance_error_s2=float(abs(mixture.duration_std_s**2-(expected_second_time-expected_time**2))),
        positive_duration_mean_s=mixture.duration_s, positive_duration_std_s=mixture.duration_std_s,
        log_duration_mean=mixture.log_duration_mean, log_duration_variance=mixture.log_duration_variance,
        joint_covariance_minimum_eigenvalue=float(np.linalg.eigvalsh(mixture.joint_covariance).min()),
        unsupported_probability=mixture.unsupported_probability,
        endpoint_body_z_m=float(mixture.features[-1, 2]), endpoint_foot_z_m=float(mixture.features[-1, 8]),
        body_z_foot_z_covariance_m2=float(mixture.joint_covariance[-8, -2]),
        foot_z_log_time_covariance_m=float(mixture.joint_covariance[-2, -1]),
    )
    if measured_bottom is not None:
        report["current_measured_foot_bottom_m"] = measured_bottom
    return report, mixture


def error_stats(actual, predicted):
    error = np.asarray(predicted)-np.asarray(actual)
    return dict(window_count=len(error), mean_error_s=float(error.mean()),
                mean_absolute_error_s=float(np.abs(error).mean()),
                median_absolute_error_s=float(np.median(np.abs(error))),
                root_mean_square_error_s=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error_s=float(np.abs(error).max()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    directory = args.study_dir.resolve()
    output = directory/"validation"
    output.mkdir(parents=True, exist_ok=True)
    paths = [directory/folder/name for folder, names in
             (("model", ("model.npz", "model.json")), ("recovery_model", ("recovery.npz", "recovery.json"))) for name in names]
    hashes_before = {str(path.relative_to(directory)): sha(path) for path in paths}
    nominal = PRIMPMotionModel.load(directory/"model")
    recovery = RecoveryMotionModel.load(directory/"recovery_model")
    for model in (nominal, recovery):
        for record in model.metadata["training_records"]:
            source = Path(record["run_directory"])
            for key, filename in (("signals_sha256", "signals.npz"), ("metadata_sha256", "metadata.json"), ("summary_sha256", "pad_summary.json")):
                if sha(source/filename) != record[key]:
                    raise ValueError(f"Training provenance no longer matches: {source/filename}")
    nominal_check, _ = mixture_check(nominal, np.array([-.01, 0., .01]), [.1, .1, .8])
    qmean = nominal_check["supplied_mean_m"]
    qvariance = np.array(nominal_check["supplied_weights"])@((np.array(nominal_check["supplied_heights_m"])-qmean)**2)
    train_variance = nominal.covariance[-2, -2]
    legacy_posterior_mean = (train_variance*qmean+qvariance*nominal.context_mean[0])/(train_variance+qvariance)
    nominal_check.update(training_height_mean_m=float(nominal.context_mean[0]),
        legacy_gaussian_measurement_reweighted_mean_m=float(legacy_posterior_mean),
        legacy_prior_pull_m=float(legacy_posterior_mean-qmean),
        interpretation="All supplied heights are within nominal training support. New interface preserves q; legacy number shows the unwanted prior reweighting if q were treated as a measurement.")
    recovery_check, recovery_mixture = mixture_check(recovery, np.array([-.012, -.006, -.001]), [.15, .55, .30], measured_bottom=0.)
    windows = recovery.metadata["window_records"]
    clearance = np.array([row["clearance_to_known_surface_m"] for row in windows])
    actual_time = np.array([row["remaining_duration_s"] for row in windows])
    predicted_time = np.array([recovery.condition_belief([0.], [1.], current_foot_bottom_m=c).duration_s for c in clearance])
    runs = sorted({row["run_id"] for row in windows})
    per_run = {}
    for run in runs:
        select = np.array([row["run_id"] == run for row in windows])
        per_run[run] = error_stats(actual_time[select], predicted_time[select])
    lower, upper = recovery.metadata["training_clearance_range_m"]
    gaps = np.linspace(lower, upper, 100)
    predictions = [recovery.condition_belief([0.], [1.], current_foot_bottom_m=gap) for gap in gaps]
    times = np.array([p.duration_s for p in predictions])
    stds = np.array([p.duration_std_s for p in predictions])
    conditioned = [dict(clearance_m=float(gap), remaining_duration_s=p.duration_s, duration_std_s=p.duration_std_s,
                        log_duration_mean=p.log_duration_mean, log_duration_std=float(np.sqrt(p.log_duration_variance)),
                        remaining_body_z_m=float(p.features[-1, 2]), remaining_foot_z_m=float(p.features[-1, 8]),
                        remaining_body_pitch_tangent_rad=float(p.features[-1, 4]), unsupported_probability=p.unsupported_probability)
                   for gap, p in zip(gaps, predictions)]
    terrain_grid = np.linspace(-.02, .004, 241)
    belief_centers = np.linspace(-.014, -.001, 45)
    belief_curves = {}
    for sigma in (.0003, .002):
        rows = []
        for center in belief_centers:
            weights = np.exp(-.5*((terrain_grid-center)/sigma)**2)
            p = recovery.condition_belief(terrain_grid, weights, current_foot_bottom_m=0.)
            rows.append(dict(supplied_center_m=float(center), posterior_mean_m=float(p.mixture_heights@p.mixture_weights),
                             duration_s=p.duration_s, duration_std_s=p.duration_std_s, unsupported_probability=p.unsupported_probability))
        belief_curves[str(sigma)] = rows
    report = dict(version=2, model_artifact_hashes=hashes_before,
        provenance=dict(nominal_source_demonstrations=nominal.metadata["training_demonstrations"],
            recovery_source_demonstrations=recovery.metadata["training_demonstrations"], recovery_correlated_windows=len(windows),
            training_clearance_range_m=[lower, upper], measured_remaining_duration_range_s=recovery.metadata["remaining_duration_range_s"],
            training_manifest_sha256=nominal.metadata["training_manifest_sha256"],
            recovery_training_manifest_sha256=recovery.metadata["training_manifest_sha256"]),
        nominal_posterior_preservation=nominal_check, recovery_posterior_preservation=recovery_check,
        in_sample_recovery_time_errors=dict(interpretation="Descriptive fit errors over correlated training windows; no held-out or independent-window inference.",
            pooled_windows=error_stats(actual_time, predicted_time), per_source_demonstration=per_run),
        conditioned_recovery=conditioned, fixed_measured_bottom_zero_belief_sweep=belief_curves,
        limitations=["The single Gaussian context implies a log-linear expected-time trend, not a calibrated nonlinear gap/time law.",
            "Height/clearance range support does not imply predicted durations remain inside the observed time range.",
            "SO3 moments use a common local tangent chart appropriate to the demonstrated small rotations.",
            "These are model diagnostics, not evidence that learned execution improves task success, impact, disturbance or time."])
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.8), constrained_layout=True)
    ax = axes[0, 0]
    ax.scatter(clearance*1000, actual_time, s=10, alpha=.4, color="gray",
               label=f"{len(windows)} windows / {len(runs)} source trials")
    ax.plot(gaps*1000, times, label="Learned expected remaining time", color="tab:blue")
    ax.fill_between(gaps*1000, np.maximum(0, times-stds), times+stds, alpha=.18, color="tab:blue", label="±1 duration SD")
    ax.set(xlabel="Current measured clearance (mm)", ylabel="Remaining physical time (s)", title="Recovery timing vs measured state")
    ax.legend(fontsize=7)
    ax = axes[0, 1]
    for sigma, rows in belief_curves.items():
        ax.plot([r["posterior_mean_m"]*1000 for r in rows], [r["duration_s"] for r in rows], label=f"Belief SD {float(sigma)*1000:g} mm")
    ax.axvspan(-upper*1000, -lower*1000, color="gray", alpha=.1, label="Demonstrated clearance interval")
    ax.set(xlabel="Supplied terrain posterior mean (mm)", ylabel="Expected remaining time (s)", title="Fixed measured foot bottom = 0")
    ax.legend(fontsize=7)
    ax = axes[0, 2]
    supplied = np.array(nominal_check["supplied_heights_m"])*1000
    ax.bar(supplied-.3, nominal_check["supplied_weights"], width=.6, label="Supplied q(h)")
    ax.bar(supplied+.3, nominal_check["returned_weights"], width=.6, label="Retained mixture q(h)")
    ax.axvline(qmean*1000, color="black", label="Fixed posterior mean")
    ax.axvline(legacy_posterior_mean*1000, color="tab:red", linestyle="--", label="Legacy prior-reweighted mean")
    ax.set(xlabel="Terrain height (mm)", ylabel="Probability mass", title="Posterior weights are preserved")
    ax.legend(fontsize=7)
    ax = axes[1, 0]
    ax.plot(gaps*1000, [p.features[-1, 2]*1000 for p in predictions], label="Body CoM Z")
    ax.plot(gaps*1000, [p.features[-1, 8]*1000 for p in predictions], label="Front foot Z")
    ax.set(xlabel="Current measured clearance (mm)", ylabel="Remaining displacement (mm)", title="Coordinated remaining body and foot motion")
    ax.legend(fontsize=8)
    ax = axes[1, 1]
    for index in (5, 40, 85):
        p = predictions[index]
        ax.plot(p.phase, p.features[:, 8]*1000, label=f"Foot, gap {gaps[index]*1000:.1f} mm")
        ax.plot(p.phase, p.features[:, 2]*1000, linestyle="--", color=ax.lines[-1].get_color())
    ax.set(xlabel="Normalized remaining phase", ylabel="Relative height (mm)", title="Remaining motion (dashed: body CoM)")
    ax.legend(fontsize=7)
    ax = axes[1, 2]
    indices = np.array([-8, -2, -1])
    c = recovery_mixture.joint_covariance[np.ix_(indices, indices)]
    correlation = c/np.sqrt(np.outer(np.diag(c), np.diag(c)))
    artist = ax.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
    labels = ["Final body Z", "Final foot Z", "Log remaining time"]
    ax.set_xticks(range(3), labels, rotation=15)
    ax.set_yticks(range(3), labels)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{correlation[i,j]:.2f}", ha="center", va="center")
    ax.set_title("Mixture retains body/foot/time covariance")
    fig.colorbar(artist, ax=ax, shrink=.8)
    fig.suptitle("V2 model diagnostics — training-window fit, not held-out performance", fontsize=13)
    image_path = output/"model_diagnostics.png"
    fig.savefig(image_path, dpi=170)
    plt.close(fig)
    hashes_after = {str(path.relative_to(directory)): sha(path) for path in paths}
    if hashes_before != hashes_after:
        raise RuntimeError("Model artifacts changed while diagnostics ran")
    report["model_hashes_unchanged"] = True
    report["reproduction_script_sha256"] = sha(__file__)
    (output/"model_diagnostics.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(dict(source_demonstrations=report["provenance"],
                         nominal_mixture=nominal_check, recovery_mixture=recovery_check,
                         training_window_errors=report["in_sample_recovery_time_errors"]["pooled_windows"],
                         figure=str(image_path)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
