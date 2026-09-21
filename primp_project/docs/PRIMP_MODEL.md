# PRIMP-based coordinated landing model

The learned planner models the **measured lowering motion of the body and front-left foot, together with its duration**. V2 adds a separate model of **remaining recovery motion and positive time to confirmed reload from the current measured state**. PyMPC remains responsible for dynamics and torque control. The contact-gated sequence still shifts the body, unloads, lifts, holds, confirms landing, and restores support. Preparatory and support-transition phases remain scripted.

## Relationship to published PRIMP

[Ruan et al., PRIMP](https://arxiv.org/abs/2305.15761) learns relative-pose distributions between adjacent trajectory samples, combines them into a joint Gaussian in local Lie-algebra coordinates, and conditions that distribution on uncertain via poses. Its inverse covariance has adjacent block structure (equation 9); Gaussian conditioning adapts the full motion (equation 13). The paper also describes a Pose Change Group formulation separating rotation and translation. The authors' [official Python implementation](https://github.com/ChirikjianLab/primp-python) was inspected as a reference.

Our implementation retains relative-motion covariance, local SO(3) rotation coordinates, the Gaussian Markov trajectory, and uncertain waypoint conditioning. It is an independent implementation of these ingredients, **not** a ProMP basis-function model and not an unmodified copy of the authors' package. We replace GORA with event-aligned normalized lowering time. We extend the state with a second coordinated translation and add learned height/duration contexts. The published manipulation benchmarks and performance claims do not establish performance for this quadruped extension.

## State and probability model

Each demonstration is represented by 41 samples by default. A sample contains nine channels:

| Channels | Quantity | Coordinates |
| --- | --- | --- |
| 0–2 | Physical whole-robot center of mass | Metres relative to lowering-start CoM |
| 3–5 | Body rotation | SO(3) logarithm relative to lowering-start orientation |
| 6–8 | Front-left foot center | Metres relative to lowering-start foot center |

The group is `R³(CoM) × SO(3)(body) × R³(foot)`. Rotation means solve the local intrinsic mean equation; rotation differences use group composition and logarithms. Wrapped Euler components are never averaged. Translation remains expressed in the common world-aligned frame. This is a product-group extension, not the coupled translational part of an SE(3) twist.

Two global context variables hold the pad-top height relative to the fixed support surfaces, and the logarithm of lowering duration. The local generative model is:

```text
c ~ Gaussian(context_mean, context_covariance)
x[0] = B[0] (c - context_mean) + epsilon[0]
x[i] = A[i] x[i-1] + B[i] (c - context_mean) + epsilon[i]
```

`A[i]` transports the local rotation coordinates; its translational blocks are identity. The full 9×9 covariance of each relative-motion residual retains body/foot correlations. `B[i]` is learned from demonstration contexts. Conditioning on the contexts leaves an adjacent-block precision matrix; marginalizing them adds correlations across the motion. The implementation builds the covariance recursively and uses Cholesky solves for conditioning. It does not replace the learned body or timing relationship with a manually selected height multiplier during model fitting or inference.

Small positive covariance floors account for sparse data and prevent singular matrices. Their default standard deviations are 20 micrometres for translations and 0.2 milliradians for rotations. These are numerical modeling choices, not calibrated sensor-noise estimates. The initial implementation assumes small body rotations around the demonstrated motions.

## Training data and separation from evaluation

`fit_runs()` accepts only folders whose metadata identifies a completed `landing_pad` **demonstration** and whose `pad_summary.json` passes. It requires contact-confirmed reload. Evaluation and development trials are rejected, including evaluation trials containing simulator terrain truth. An initial estimate that differs from the offline known height is accepted only when metadata explicitly marks `recovery_demonstration: true`.

The segment begins at the first `lower` sample and ends at the first confirmed `reload` sample. The model uses measured CoM, body orientation, and foot position. All other raw phases remain in the recordings but do not enter this model. Translation is resampled in normalized time; orientation is resampled with SO(3) interpolation. The positive duration is measured from logged control timestamps. Only the offline `known_height_m` training label supplies terrain height; the evaluator's truth dictionary is never read by the fitter.

Demonstrations are successful **scripted-controller simulation trials**. They are neither human demonstrations nor evidence of optimal motions. Learned relationships inherit the behavior supplied by that controller. A dataset with almost no demonstrated body adjustment cannot teach a useful large body adjustment.

The nominal model consists of numeric `model.npz` and `model.json`; recovery uses separate `recovery.npz` and `recovery.json`. Provenance includes training run IDs, hashes of raw signals, metadata and acceptance summaries, an aggregate training-manifest hash, optional external split-manifest hash, feature conventions, observed context/duration ranges, and regularization settings. Loading verifies the model-file hash. V1 artifacts are preserved; V2 fits new artifacts rather than overwriting the earlier results.

## Fixed-posterior conditioning in V2

The model receives the sensor estimator's discrete height posterior **q(h)**. Its online API has no simulator, scene, pad object, or actual-height input. Contact and missing contact update the shared sensor-only belief upstream. Measured body/foot state also feeds the controller, feasible reference generation, and recovery model's measured origins.

`condition_belief(heights, probabilities, ...)` conditions the learned joint Gaussian on **each exact height** and optional continuity waypoints, then integrates these motion conditionals with the supplied posterior weights. It never multiplies q by the training height prior or by the likelihood of a continuity waypoint. A waypoint can change the motion conditional at a given height; it cannot change that height's supplied probability. For latent motion and log-duration vector z, the computation is:

```text
p_execution(z) = sum_j q_j p_model(z | h = h_j, waypoint observations)
mean = sum_j q_j mean_j
covariance = sum_j q_j [covariance_j + (mean_j - mean)(mean_j - mean)^T]
```

The second term in the covariance is essential: uncertain terrain contributes uncertainty and cross-correlation across body position, foot position, orientation, and log-duration. The output retains the full joint covariance of the returned 9D phase samples followed by log-duration. The exact-height conditional mean is affine in height and its covariance is height independent, so the full 241-point belief can be integrated with one covariance solve. There is no Gaussian replacement or terrain-prior reweighting of the input q. Positive duration expectation and variance use all supplied mixture weights and component log-normal moments, not simply the exponential of an averaged log-duration.

Rotation means and covariance use a shared local SO(3) tangent chart. Integrating these local coordinates and mapping the mean back through the exponential is a small-rotation PRIMP approximation; it is not an exact distribution on arbitrary dispersed rotations. The returned covariance is expressed in those local tangent coordinates, not globally in Euler-angle coordinates.

The nominal execution adapter supplies the preceding feasible reference as a continuity waypoint. It removes the shared virtual contact-compression offset before constructing model features. Its phase comes from measured geometric progress. This separates measured tracking lag from command continuity. Optional endpoint conditioning imposes `foot_dz = h + offset` separately in each height component, with an explicit tracking tolerance; it does not treat the desired endpoint as new terrain evidence. The API returns only the requested future suffix.

`unsupported_probability` reports how much supplied height mass lies outside the observed training range. Extrapolation is still computed and is not silently described as demonstrated behavior. The matched execution planner decides whether enough demonstrated support remains, records fallback use, and applies the same body, foot, timing and contact constraints as its conventional alternative.

### Legacy V1 measurement interface

`condition(height_mean, height_std, ...)` remains unchanged for reproduction of V1. It interprets height uncertainty as **Gaussian observation noise** and combines that observation with the training-height prior. It therefore **must not receive an already computed terrain posterior** in V2. Starting each call from the saved model avoids accumulating repeated calls, but does not fix the inappropriate prior reweighting when a posterior is passed as an observation. The new `condition_belief` interface fixes that distinction. Legacy duration is a log-normal median; the mixture API reports the expected duration.

## Recovery motion and remaining time

`fit_recovery_runs()` accepts only successful demonstrations explicitly marked `recovery_demonstration: true` with a logged missing-contact event before confirmed reload. Each window begins at a measured state at or after that event and ends at the first contact-confirmed reload. Defaults sample starting states every 0.15 seconds and retain windows with at least 0.12 seconds remaining and three samples. The context and time labels are:

```text
clearance = measured_FL_foot_bottom_at_window_start - offline_known_height
remaining_duration = confirmed_reload_timestamp - window_start_timestamp
```

The features use each window's measured CoM, body rotation, and foot position as their origins. Contact force and desired references are not substituted for measured trajectories. The model learns the joint remaining body/foot motion and logarithm of positive remaining time. This time includes the observed approach and contact-confirmation interval; it is not just time to first physical touch.

Online, `RecoveryMotionModel.condition_belief(..., current_foot_bottom_m=...)` transforms each terrain component into its current measured clearance and applies the same fixed-weight integration. Returned motions begin at phase zero relative to the **current measured origins**. The duration is physical remaining time, not a previously predicted total duration multiplied by an exhausted global phase. The model contains no hand-written depth/speed timing law. Command continuity and feasibility remain responsibilities of the shared execution optimizer.

Recovery windows overlap and are correlated. Metadata records both the number of source demonstrations and the larger number of windows; windows are not additional independent trials. Each window records its source, measured start, clearance, confirmed endpoint, and duration. Unsupported probability for this model refers to its **clearance** range. V2's training protocol uses the preserved nine V1 demonstrations plus nine new recovery demonstrations for nominal motion, and only the nine new recovery demonstrations for recovery windows.

## API

```python
from primp_project.learning import (
    fit_runs, fit_recovery_runs, PRIMPMotionModel, RecoveryMotionModel,
)

model = fit_runs(demonstration_directories, phase_points=41,
                 split_manifest_path=split_manifest)
model.save(model_directory)
model = PRIMPMotionModel.load(model_directory)
motion = model.condition_belief(
    heights=belief.heights, probabilities=belief.probability,
    current_phase=phase, current_features=accepted_reference_features,
)
features, derivative_by_phase, second_derivative_by_phase = motion.sample(phase)

recovery = fit_recovery_runs(recovery_demonstration_directories,
                            split_manifest_path=split_manifest)
recovery.save(recovery_directory)
recovery = RecoveryMotionModel.load(recovery_directory)
remaining = recovery.condition_belief(
    heights=belief.heights, probabilities=belief.probability,
    current_foot_bottom_m=measured_foot_bottom,
)
# remaining.features are relative to the current measured CoM/body/foot pose.
# remaining.duration_s is positive remaining physical time to confirmed reload.
```

Nominal features use the lowering-start anchors; recovery features use the current measured anchors. Heights and measured foot bottom must use the same fixed-support height datum. Body orientation is reconstructed by composing the anchor rotation with the predicted exponential rotation. Interpolation uses a cubic spline with zero endpoint derivatives. Phase derivatives must be divided by the modeled segment duration (and its square) to produce SI velocity and acceleration. The matched planner optimizes a feasible suffix using the full motion/time covariance before its references reach PyMPC.

`PRIMPMotionModel.fit(features, heights_m, durations_s)` also supports already aligned arrays of shape `[demonstrations, phase_points, 9]` for numerical tests and offline research. This lower-level API does not validate recording roles; experiment training uses `fit_runs()`.

## Verification and limits

[Legacy model tests](../tests/test_primp_model.py) check positive covariance, the conditional Markov precision structure, body/foot/orientation/timing adaptation, uncertain waypoints, causal suffixes, rotation wrapping, serialization integrity, and rejection of failed/evaluation training recordings. [Posterior tests](../tests/test_belief_conditioning.py) check preservation of q without shrinkage toward training heights, an independent exact-height Gaussian solve, full law-of-total covariance under arbitrary mixtures, nonlinear duration moments, endpoint conditioning, and a sparse 241-point belief. [Recovery tests](../tests/test_recovery_learning.py) check current-clearance-dependent positive remaining time, measured-state extraction, event timestamps, separate artifact hashes, overlapping-window provenance, and rejection of unmarked, failed, evaluation, or non-recovery recordings.

The fitted V2 artifacts have reproducible [model diagnostics](../results/landing_pad/study_v2/validation/model_diagnostics.json) and a [standalone figure](../results/landing_pad/study_v2/validation/model_diagnostics.png). The [execution audit](../results/landing_pad/study_v2/validation/learned_execution_audit.json) and its [timing figure](../results/landing_pad/study_v2/validation/learned_execution_audit.png) distinguish the unclipped learned time, optimizer-selected feasible horizon, realized time to confirmed reload, and fallback intervals. These quantities are not interchangeable. Both audits preserve the canonical model and recording hashes; their reproduction scripts sit beside the outputs.

This is an initial locally Gaussian model for small height changes. It does not implement multimodal skill selection, automatic discovery of support phases, learned touchdown detection, or a claim of superiority over the reactive and predictive alternatives. Held-out simulation results and their shared sensing/execution conditions determine what can be claimed about task performance.
