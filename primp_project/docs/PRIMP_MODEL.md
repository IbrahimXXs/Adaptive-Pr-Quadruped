# PRIMP-based coordinated landing model

The learned planner models the **measured lowering motion of the body and front-left foot, together with its duration**. PyMPC remains responsible for dynamics and torque control. The existing contact-gated sequence still shifts the body, unloads, lifts, holds, confirms landing, and restores support. Those preparatory and support-transition phases are not learned in this first version.

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

`fit_runs()` accepts only folders whose metadata identifies a completed `landing_pad` **demonstration** and whose `pad_summary.json` passes. It requires contact-confirmed reload. Evaluation and development trials are rejected, including evaluation trials containing simulator terrain truth.

The segment begins at the first `lower` sample and ends at the first confirmed `reload` sample. The model uses measured CoM, body orientation, and foot position. All other raw phases remain in the recordings but do not enter this model. Translation is resampled in normalized time; orientation is resampled with SO(3) interpolation. The positive duration is measured from logged control timestamps. Only the offline `known_height_m` training label supplies terrain height; the evaluator's truth dictionary is never read by the fitter.

Demonstrations are successful **scripted-controller simulation trials**. They are neither human demonstrations nor evidence of optimal motions. Learned relationships inherit the behavior supplied by that controller. A dataset with almost no demonstrated body adjustment cannot teach a useful large body adjustment.

The saved model consists of numeric `model.npz` and `model.json`. Provenance includes training run IDs, hashes of raw signals, metadata and acceptance summaries, an aggregate training-manifest hash, optional external split-manifest hash, feature conventions, observed height/duration ranges, and regularization settings. Loading verifies the model-file hash.

## Online conditioning

The model receives a height **belief** and a continuity waypoint from the previously accepted feasible reference. Its online API has no simulator, scene, pad object, or actual-height input. Contact and missing contact update the shared sensor-only belief upstream. Measured body/foot state also feeds the common controller and feasibility projection.

The execution adapter conditions on the preceding feasible body/foot reference at the current motion phase. It removes the shared virtual contact-compression offset before constructing model features. This keeps a few millimetres of physical tracking lag from being misinterpreted as a higher landing surface when conditioning an already advanced trajectory phase. The model API can also condition measured waypoints for offline inspection; that capability is distinct from the adapter's causal reference-continuity waypoint.

`condition()` starts from the saved prior on every call. This prevents repeated application of an unchanged belief from producing artificial confidence. It returns only the suffix beginning at the current phase index, so the caller cannot execute a rewritten past. Duration is predicted jointly and remains positive through the exponential map. The planner and shared feasibility layer decide how to allocate that remaining time and enforce reach, speed, body, support, and contact-transfer limits.

Height uncertainty enters the conditioning observation covariance. Optional desired or measured waypoints use the same conditional-Gaussian machinery. The predicted full duration is available even when no desired duration is supplied. A duration observation is optional for offline inspection; evaluation uses the learned duration prediction.

## API

```python
from primp_project.learning import fit_runs, PRIMPMotionModel

model = fit_runs(demonstration_directories, phase_points=41,
                 split_manifest_path=split_manifest)
model.save(model_directory)
model = PRIMPMotionModel.load(model_directory)
motion = model.condition(height_mean=belief.mean, height_std=belief.std,
                         current_phase=phase, current_features=accepted_reference_features)
features, derivative_by_phase, second_derivative_by_phase = motion.sample(phase)
```

The nine returned features use the same lowering-start anchors as training. Body orientation is reconstructed by composing the start rotation with the predicted exponential rotation. Interpolation uses a cubic spline with zero endpoint derivatives. Phase derivatives must be divided by the execution duration (and its square) to produce SI velocity and acceleration. The planner applies its common feasibility filter before these references reach PyMPC.

`PRIMPMotionModel.fit(features, heights_m, durations_s)` also supports already aligned arrays of shape `[demonstrations, phase_points, 9]` for numerical tests and offline research. This lower-level API does not validate recording roles; experiment training uses `fit_runs()`.

## Verification and limits

`tests/test_primp_model.py` checks positive covariance, the conditional Markov precision structure, body/foot/orientation/timing adaptation, uncertain waypoints, causal suffixes, rotation wrapping, uncertainty reduction, repeat conditioning, serialization integrity, and rejection of failed/evaluation training recordings.

This is an initial locally Gaussian model for small height changes. It does not implement multimodal skill selection, automatic discovery of support phases, learned touchdown detection, or a claim of superiority over the reactive and predictive alternatives. Held-out simulation results and their shared sensing/execution conditions determine what can be claimed about task performance.
