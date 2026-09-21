# Matched landing-pad study: V2 results

V2 tests remaining-motion and timing adaptation with five variants of the same
predictive reference optimizer. It adds recovery demonstrations to address the
phase-exhaustion limitation in the [preserved V1 pilot](landing_pad.md).
The [experiment guide](../landing_pad_v2.md) defines the information boundary,
exact ablations, limits, reserved conditions, and reproduction commands.

**All 60 reserved evaluations passed**, with **12/12 per variant**, no comparison
consistency errors, and 60/60 independent raw-signal audit passes. Learned
recovery time remains positive before feasibility clipping, addressing V1's
expired-phase failure mode. The results **do not establish an overall learned
advantage**: the complete learned variant needs more common fallback than the
matched predictive baseline, and disabling learned timing shortens completion
in all 12 matched pairs.

## Recorded training and frozen protocol

All **nine new recovery demonstrations passed**. They use actual heights
−4, −8, and −12 mm with initially zero height estimates and nominal lowering
durations of 3, 4, and 5 seconds. Together with the nine preserved V1
demonstrations, they fit the V2 nominal motion model from **18 recordings**.
The separate recovery model uses the nine new recordings only, generating
**102 overlapping measured-state-to-reload windows**. These windows are
correlated training segments rather than independent trials.

The [reserved split](../../results/landing_pad/study_v2/split_manifest.json)
contains **60 evaluation cells**: five variants × actual −6/+6 mm heights ×
noise seeds 17/29/43 × nominal/raised initial foot clearance (30/35 mm).
Every evaluation uses an initial estimate of zero, a four-second nominal
lowering duration, 40 ms sensor delay, bounded ±0.5 mm position noise, and
bounded ±0.3 N force noise. The two heights and raised initial condition were
not executed during fitting or live development.

The [execution freeze](../../results/landing_pad/study_v2/execution_freeze.json)
binds source and both canonical model artifacts. The full suite passed
**317 tests** before evaluation; the
[test output](../../results/landing_pad/study_v2/validation/tests.txt) is retained.
Four independent native workers executed the formal trials while the parent
owned the journal. Every declared cell has one preserved completed attempt.
The [independent execution audit](../../results/landing_pad/study_v2/validation/execution_audit.json)
checks all 60 raw recordings, frozen source/model hashes, training provenance,
measured support and loading, reference bounds, planning cadence, and realized
initial conditions. Raised clearance is physically about **4.989 mm** higher at
lowering entry, confirming that the initial-condition labels describe a measured
change. Minimum true target-pad force during pre-reload confirmation is
**2.251 N**; minimum final standing load across all feet/trials is **31.959 N**.

## Matched comparison

The [full report](../../results/landing_pad/study_v2/comparison/comparison.md),
[JSON](../../results/landing_pad/study_v2/comparison/comparison.json),
[trial CSV](../../results/landing_pad/study_v2/comparison/comparison.csv), and
[plot](../../results/landing_pad/study_v2/comparison/comparison.png) contain all
60 trials. These are per-variant medians across 12 accepted trials:

| Variant | Success | First-100-ms peak force (N) | Roll/pitch disturbance (°) | Lowering to completion (s) | Applied fallback time (s) | Fallback descent (mm) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Matched predictive | 12/12 | 1.310 | 0.495 | 13.832 | 0.037 | 0.032 |
| Complete learned | 12/12 | 1.258 | 0.497 | 14.022 | 0.256 | 0.368 |
| No direct body–foot correlation | 12/12 | 1.271 | 0.495 | 13.979 | 0.259 | 0.427 |
| No learned timing adaptation | 12/12 | 1.273 | 0.496 | 13.722 | 0.270 | 0.363 |
| No noncontact belief updates | 12/12 | 1.183 | 0.500 | 14.316 | 1.237 | 2.474 |

Landing-force windows start at first physical touch, before full weight
transfer. The body metric is the maximum roll/pitch change during landing.
Fallback displacement is commanded foot descent attributed to the common
fallback, not physical work or total foot motion. All 12 complete learned
trials use some fallback; the learned prior is active on a median **76.1%** of
unsupported planning updates. The matched predictive baseline has six trials
with fallback foot motion.

The [paired differences](../../results/landing_pad/study_v2/comparison/paired_differences.csv)
use identical height, seed, and initial condition. All 12 pairs are available
for each contrast. These values are medians of individual paired differences,
which need not equal differences between the medians above:

| Method minus reference | Completion difference (s) | Peak-force difference (N) | Fallback-time difference (s) | Fallback-descent difference (mm) |
| --- | ---: | ---: | ---: | ---: |
| Complete learned − predictive | +0.104 | −0.052 | +0.204 | +0.296 |
| No body–foot correlation − complete learned | 0.000 | +0.003 | +0.010 | +0.020 |
| No learned timing − complete learned | −0.194 | −0.013 | −0.002 | −0.051 |
| No noncontact updates − complete learned | +0.350 | −0.130 | +0.989 | +2.117 |

The complete learned variant has a lower first-contact peak in seven of twelve
pairs, but is slower in eight, tied in two, and faster in two. Its small median
force reduction does not establish an overall benefit. The timing ablation is
faster in **all 12 pairs**, so these conditions provide no evidence that learned
timing improves completion time. Removing direct body–foot correlation produces
small changes without demonstrating a useful coordination advantage.

Removing noncontact belief updates increases fallback time and descent in
**all 12 pairs**. That comparison supports the contribution of negative-contact
evidence in this implementation, although completion-time effects are mixed
and the lower reaction force trades against more recovery. Three sensing seeds,
two heights, and two clearances are a small descriptive simulation study, not
a statistical or hardware superiority claim.

## Model diagnostics and scope of claims

The [diagnostic data](../../results/landing_pad/study_v2/validation/model_diagnostics.json)
and [plot](../../results/landing_pad/study_v2/validation/model_diagnostics.png)
verify fixed-posterior conditioning: a supplied +7 mm height mean remains at
+7 mm, whereas the legacy observation-style API shrinks that example to
+2.286 mm. Explicit integration of component distributions agrees with the
returned full motion/time covariance to approximately `1e-16`.

On its own correlated training windows, recovery remaining-time error is
**0.232 s MAE / 0.408 s RMSE**. This is an in-sample diagnostic. The formal
comparison separately measures closed-loop timing and task outcomes; fitting
these windows does not establish held-out timing accuracy or a learned advantage.

## What the learned timing actually contributes

The [learned execution audit](../../results/landing_pad/study_v2/validation/learned_execution_audit.json)
and [per-trial plot](../../results/landing_pad/study_v2/validation/learned_execution_audit.png)
cover all **48 learned/ablation trials**, including the **12 complete learned**
trials. All raw model remaining times stay positive while unsupported; none of
the 48 trials needs the 0.1-second model floor to make that prediction positive.
For complete learned, the minimum raw model remaining time is **0.161 s**.

In the six complete learned lower-pad trials, first missing contact increases
raw predicted remaining time by a median **0.992 s**. The first recovery
prediction has median **1.898 s**, compared with **1.858 s** of subsequently
realized time to confirmed reload. During actual recovery-prior use, the median
of six per-trial forecast MAEs is **0.141 s** (range **0.117–0.164 s**), based on
149 correlated planning updates. This is descriptive closed-loop forecasting
under continued replanning, not 149 independent observations or a calibrated
uncertainty guarantee.

That recovery calculation is active when at least 50% of supplied posterior
mass lies within the training-clearance range. **No active recovery update
reaches 99% supported mass**, so every such mixture includes some extrapolation.
Nominal-phase timing errors are larger: median per-trial MAE **0.882 s** for
the six lower-pad trials and **1.412 s** for the six higher-pad trials. Across
all active prior phases, the median of twelve per-trial raw forecast MAEs is
**0.982 s**. The applied feasible horizon is a distinct optimizer choice; its
median discrepancy during active recovery is **0.965 s**. It should not be
described as the same statistical prediction as raw learned duration.

Common fallback remains active in every complete learned trial: **0.350–0.460 s**
and **0.329–0.528 mm** of descent on lower pads; **0.100–0.162 s** and
**0.225–0.422 mm** on higher pads. V2 therefore implements positive learned
recovery timing and actual learned-prior execution, while the comparison still
finds no completion-time benefit from the learned timing term. Improving nominal
timing, increasing demonstrated recovery support, and understanding the joint
optimizer's timing tradeoffs remain research steps.

Fallback contribution is measured from applied reference intervals: active
time, downward foot displacement, and CoM travel. Invocation counts do not
substitute for those quantities. Raw model time is reported separately from
optimized/feasible timing, so a feasibility floor cannot be mistaken for a
learned prediction. The strict V2 validator also checks measured-state planning
anchors, actual use of the learned prior, and exclusion of that prior while
fallback is executing.

An [in-memory falsification audit](../../results/landing_pad/study_v2/validation/falsification.json)
started from an actual reserved learned recording and rejected all seven
deliberate corruptions: expired raw time hidden by a positive floor, expired
applied time, a stale measured anchor, fabricated fallback time or descent,
simultaneous prior/fallback credit, and a learned label without any actual
prior use. The [reproducer](../../results/landing_pad/study_v2/validation/falsify_adaptation.py)
does not change canonical measurements or reports.

## Computation and execution limits

The simulation executes the expected 20 Hz planner and 100 Hz MPC schedules,
including the declared contact transitions. There are **zero reference-optimizer
failures and zero MPC QP failures**. Across 6,588 planner updates, measured wall
time has **11.65 ms p95** and **61.89 ms maximum**. **15 updates exceed the 50 ms
planning period** under four concurrent native workers. Exact simulation cadence
therefore does not establish a hard real-time 20 Hz wall-clock guarantee.
The 190,107 recorded MPC solves have 1.285 ms p95 and 6.668 ms maximum.

## Preserved evidence and development failures

The [complete learned replay](../../results/landing_pad/study_v2/validation/learned_lower_raised_replay.mp4)
and [preview](../../results/landing_pad/study_v2/validation/learned_lower_raised_replay.png)
show the accepted formal −6 mm, seed-29, raised-clearance trial. It renders the
32.7-second measured trajectory at 20 fps, without rerunning the controller.
The [replay provenance](../../results/landing_pad/study_v2/validation/learned_lower_raised_replay.json)
records the source signal hash. It is viewable execution evidence for that
condition, not a comparative performance result.

The [V1 integrity audit](../../results/landing_pad/study_v2/validation/v1_integrity.json)
and its [reproducer](../../results/landing_pad/study_v2/validation/audit_v1_integrity.py)
confirm that all nine inherited demonstrations, all 24 V1 evaluations, the
V1 manifest/state, and the original model retain their preserved hashes.
The V2 [training inventory](../../results/landing_pad/study_v2/v1_training_manifest.json)
records exactly which inherited files entered fitting.

Eight V2 development attempts were retained before the freeze: seven pass and
one retains a **FAIL** label caused by an overly restrictive analyzer check.
That check required a posterior mean to lie between its 5th and 95th
percentiles, which is not guaranteed for a skewed distribution. The valid
posterior missed the bound by about 1.2 micrometres. The check was corrected to
verify ordered credible bounds and a mean within the estimator's height grid;
the same declared development condition then passed. No controller or terrain
estimator change was required, and the original failed report remains intact.
This was a validation false rejection, not a physical fall, and neither
development attempt is counted as a formal evaluation.

The refreshed [catalog](../../results/README.md) contains **131 recordings**,
including **77 V2 records**: nine training demonstrations, eight development
attempts, and 60 formal evaluations. All V2 records have purpose/condition
annotations; the one retained development failure remains explicit. The
[completion/resume record](../../results/landing_pad/study_v2/validation/runner_completion.json)
preserves the managed-session termination after all trials and reports had
been saved. A clean resume exited successfully with **zero native trial reruns**.
