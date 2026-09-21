# Matched motion-distribution study (V2)

V2 investigates the limitation found in the [preserved V1 pilot](results/landing_pad.md):
the learned trajectory could finish before a lower surface was reached, leaving
additional descent and time to the common fallback. V2 adds measured recovery
demonstrations and a separate distribution of remaining body–foot motion and
time. It compares five variants of one predictive reference optimizer.

The completed study passes **60/60 reserved evaluations**, **12/12 per variant**,
with **317 tests** and an independent raw-signal audit. The
[results page](results/landing_pad_v2.md) and
[full comparison](../results/landing_pad/study_v2/comparison/comparison.md)
report all conditions and paired differences. Raw learned recovery time stays
positive before clipping, but every complete learned trial still uses some
fallback. Removing learned timing makes all twelve matched cases faster, so
an overall learned coordination/timing advantage remains unproven.

The separate landing pad, three fixed support surfaces, Go2 model, PyMPC
execution controller, contact gates, and reference limits remain the same
[physical experiment](landing_pad.md#physical-experiment). All new V2 records,
models, development attempts, and reports live in
`results/landing_pad/study_v2/`. V1 records and models are retained unchanged.

The [recorded V2 learned replay](../results/landing_pad/study_v2/validation/learned_lower_raised_replay.mp4)
and [preview](../results/landing_pad/study_v2/validation/learned_lower_raised_replay.png)
show the formal −6 mm, seed-29, raised-clearance trial. The 32.7-second video
renders measured states at 20 fps, with no controller rerun. Its
[provenance](../results/landing_pad/study_v2/validation/learned_lower_raised_replay.json)
binds the replay to the original signals.

## Training and reserved evaluation

| Group | Conditions | Independent recordings |
| --- | --- | ---: |
| Inherited nominal demonstrations | Preserved successful V1 steps: known −10, 0, +10 mm heights × 3, 4, 5 s nominal duration | 9 |
| New recovery demonstrations | Actual −4, −8, −12 mm, initial estimate 0 mm × 3, 4, 5 s; reactive controller, clean sensing, nominal initial clearance | 9 |
| Formal evaluation | Five matched variants × actual −6/+6 mm × noise seeds 17/29/43 × nominal/raised initial clearance | 60 |

All nine new demonstrations passed. The nominal motion model is fitted to
all **18** demonstration recordings. The recovery model uses only the **nine**
new recovery recordings. Its **102 overlapping windows** are correlated
training segments, not 102 independent demonstrations. Both fitters require
successful demonstration metadata and preserved acceptance/raw-data hashes;
formal evaluation recordings are excluded from fitting.

Every evaluation starts from a zero height estimate and a four-second nominal
lowering duration. The sensor profile supplies 40 ms delayed observations with
bounded ±0.5 mm position and ±0.3 N force noise. Nominal and raised conditions
request 30 and 35 mm held-foot clearance respectively; actual measured initial
foot and CoM states are recorded as well. The ±6 mm heights and raised clearance
are reserved from fitting and live development. Development uses other heights
and nominal clearance. Three seeds provide repeated sensing conditions, while
the two clearances test a controlled change in the initial movement state.

The immutable [split manifest](../results/landing_pad/study_v2/split_manifest.json)
was written before evaluation. The separate
[V1 training inventory](../results/landing_pad/study_v2/v1_training_manifest.json)
captures the inherited files. A [read-only integrity audit](../results/landing_pad/study_v2/validation/v1_integrity.json)
confirms that all nine V1 demonstrations, all 24 V1 evaluations, and the
original model retain their saved hashes.

## What each variant changes

All five variants optimize body XYZ, body orientation, foot XYZ, and positive
remaining duration with the same horizon, physical limits, contact policy,
support projection, sensing, and PyMPC controller. The common optimizer also
has the same deterministic motion objectives. The learned variants add the
conditioned joint motion/time distribution as a quadratic prior.

| CLI planner | Difference from the complete learned variant |
| --- | --- |
| `matched_predictive` | Omits the learned motion/time prior while retaining the same optimizer and feasible execution |
| `matched_learned` | Uses the complete conditioned motion/time prior and recovery distribution |
| `matched_no_body_foot_correlation` | Removes direct body–foot covariance conditional on log-duration, preserving the individual marginals and timing-mediated correlation |
| `matched_no_timing_adaptation` | Removes learned motion/time cross-covariance and substitutes the common baseline timing prior; feasible duration optimization remains active |
| `matched_no_noncontact_updates` | Disables negative-contact updates to the terrain belief; contact observations, event detection, recovery limits, and the other learned terms remain active |

The covariance ablation removes a defined statistical dependence. It does not
freeze body motion or disconnect the body controller. The timing ablation
removes learned timing information, not the safety requirement to retain enough
feasible time. The noncontact ablation changes terrain inference, not the
contact gate that prevents unsupported weight transfer.

## Terrain belief, motion conditioning, and recovery

Simulator truth remains evaluator-only. The adaptation module receives the
initial estimate and permitted sensor observations; it never receives the true
pad height. The shared estimator supplies a discrete terrain posterior `q(h)`.
V2 conditions the learned distribution separately at each height and integrates
the resulting motion distributions with **exactly those posterior weights**.
It does not apply the training-height prior a second time. Between-height
variation contributes to the full body/foot/time covariance.

Nominal motion uses the previous accepted feasible reference as a continuity
waypoint, with shared virtual contact compression removed. The nominal phase
uses measured geometric progress. After missing contact, recovery is anchored
at the current measured body and foot state. Each training recovery window
predicts the movement and physical time from its measured starting state to
contact-confirmed reload. Consequently, additional recovery does not multiply
a total duration by an exhausted nominal phase.

The planner records raw model remaining time, optimizer remaining time, and
the feasible remaining time supplied to execution separately. It also records
whether the learned prior is active and why common fallback is invoked.
Feasibility floors and the shared descent bound still affect the executed
duration; a positive feasible time alone does not establish learned timing
accuracy or a learned performance advantage.

The [model guide](PRIMP_MODEL.md) describes the PRIMP-derived construction,
fixed-posterior mixture, measured recovery origins, and APIs. The saved
[model diagnostics](../results/landing_pad/study_v2/validation/model_diagnostics.json)
and [plot](../results/landing_pad/study_v2/validation/model_diagnostics.png)
show that a supplied +7 mm posterior mean stays at +7 mm under V2 conditioning.
The legacy observation-style interface instead shrinks that example to +2.286 mm.
Explicit component integration agrees with the V2 full covariance to about
`1e-16`. Recovery-window timing has an **in-sample** MAE of 0.232 s and RMSE of
0.408 s. These correlated-window diagnostics verify fitting and arithmetic;
they are not held-out timing accuracy or closed-loop improvement results.

## Evaluation and attribution

Each declared cell receives one attempt. Failed trials, infrastructure errors,
and interrupted attempts remain visible; resuming does not silently retry or
replace them. Source and both model artifacts are frozen before evaluation,
checked before submission and after completion, and attested by each worker.
The report checks recording hashes, trial/condition association, model digests,
source attestations, and shared controller settings.

The comparison pairs identical true height, sensing seed, and initial condition.
It compares complete learned against matched predictive, and each of the three
ablations against complete learned: **12 pairs per contrast, 48 total**. The
sign convention is `method − reference`. Success outcomes include every planned
cell. Metric differences require both paired trials to pass; reports provide
the corresponding sample counts rather than hiding failed pairs.

Primary execution outcomes are completion, first-100-ms peak normal force and
impulse, body roll/pitch disturbance, and lowering-to-completion time. Additional
diagnostics make the learned and fallback contributions visible:

- Fallback active time integrates recorded applied-reference intervals.
  Fallback foot descent and CoM travel integrate actual changes in the applied
  commands during those intervals. The preceding sample owns an interval;
  frozen/non-landing intervals add no fallback work. Invocation counts are
  separate and are not converted into duration by dividing by 20 Hz.
- Positive remaining-time fractions use unsupported planning updates, with
  separate summaries after missing contact. Raw model, optimized, and feasible
  timings remain distinguishable.
- Remaining-time MAE compares the proposed duration with the measured interval
  to confirmed reload, including the confirmation dwell. This is an execution
  calibration diagnostic under feedback, not a prospective timing guarantee.
- Actual measured lower-entry foot/CoM states accompany the nominal/raised
  labels. This exposes the realized initial-condition difference.

The validation retains the earlier measured reload/final-foot-loading and
100 Hz MPC checks, plus applied reference bounds and 20 Hz planning cadence.
V2 independently reconstructs fallback work and requires positive remaining
time before feasibility clipping while the foot is unsupported. It also checks
current measured planning anchors, actual learned-prior execution, and absence
of that prior during common fallback. An
[in-memory corruption audit](../results/landing_pad/study_v2/validation/falsification.json)
rejects seven violations of those requirements without modifying recorded data.
Comparisons remain descriptive simulation
evidence; three seeds and one repeat per height/seed/clearance cell do not
establish general superiority or hardware robustness.

The [execution audit](../results/landing_pad/study_v2/validation/execution_audit.json)
finds zero reference-optimizer/MPC QP failures and exact simulated cadence.
Measured planner wall time has 11.65 ms p95 and 61.89 ms maximum; 15 of 6,588
updates exceed 50 ms under four concurrent workers. This is not a hard
real-time wall-clock guarantee. The separate
[learned timing audit](../results/landing_pad/study_v2/validation/learned_execution_audit.json)
reports recovery forecast error, larger nominal timing errors, extrapolated
posterior mass, and actual fallback contribution without treating positive
remaining time alone as calibrated prediction.

## Reproduce without replacing preserved results

Run from the repository root in the existing project environment. A fresh
directory records a new study and captures the preserved V1 training inputs:

```bash
conda activate quadruped-pympc
python -m primp_project pad-study-v2 all --workers 4 --study-dir primp_project/results/landing_pad/reproduction_v2
```

The available stages are `declare`, `demo`, `train`, `freeze`, `evaluate`, and
`all`. `demo` runs serially; `--workers 4` controls evaluation only. Omit the
option for serial evaluation. Parallel native workers use separate acados
generated-code directories while the parent process owns the study journal.
Parallel evaluation is headless. Preserve interrupted/failed evidence and use
a new study directory when changing frozen code or models.

For deliberate development before freezing, run `declare`, `demo`, and `train`,
then test only unreserved conditions using `pad` and the two new model paths.
Finish all controller/model changes before `freeze` and `evaluate`. Source
changes are not accepted as a resume of an already frozen evaluation.

```text
study_v2/
├── split_manifest.json          # Reserved conditions and pairing
├── v1_training_manifest.json    # Read-only inherited V1 file hashes
├── study_state.json             # Attempts, acceptance, source/model attestations
├── execution_freeze.json        # Frozen evaluation source and both models
├── demonstrations/              # Nine new recovery recordings
├── development/                 # Smoke checks and any failed engineering attempts
├── evaluation/                  # All formal attempts, including failures
├── model/                       # Nominal model fitted from 18 demonstrations
├── recovery_model/              # Recovery model from nine demonstrations
├── comparison/                  # Trial and paired CSV/JSON, report, plot
└── validation/                  # Independent audits, diagnostics, test evidence
```
