# Adjustable landing-pad results

Nine successful known-height demonstrations have been collected and fitted.
**All 24 evaluation trials passed**: **18/18 primary trials** and **6/6
supplementary reserved-height trials**. Each planner completed 6/6 primary
cases and 2/2 additional cases, with no source/model/settings consistency
errors. The initial simulation prototype and its evaluation are complete.
Individual reports are available through the
[recording catalog](../../results/README.md).

**Current learned-model limitation:** coordinated references change online, but
the lower-pad recovery still depends substantially on the shared bounded
fallback. The learned timing prediction does not account for that added
recovery time. Passing completion checks should not be interpreted as evidence
that the full learned body–foot–timing adaptation objective is already achieved.

## Experiment and evaluation groups

All planners use the same Go2 model, nominal acados controller, separate target
pad, contact-transfer gates, sensor interface, height belief, and feasible
reference limits. The target is 9 cm forward of FL; the other three supports
and the FL launch pad remain fixed at zero height. See the
[experiment guide](../landing_pad.md) for the execution sequence and limits.

| Group | Conditions | Planned trials | Current result |
| --- | --- | ---: | --- |
| Training demonstrations | Known heights −10, 0, +10 mm × nominal durations 3, 4, 5 s; clean sensing | 9 | **9 passed** and fitted |
| Primary comparison | Reactive/predictive/learned × heights −5, 0, +5 mm × clean/noisy-delayed sensing | 18 | **18 passed**, 6/6 per planner |
| Supplementary reserved heights | Same three planners × −7.5, +7.5 mm; clean sensing | 6 | **6 passed**, 2/2 per planner |
| Bounded-search guard | Reactive, actual −25 mm, initial estimate 0 mm | 1 development trial | Expected abort; retained **FAIL** |

All evaluation estimates start at zero and use a 4-second nominal lowering
duration. The noisy-delayed condition uses 40 ms delay, bounded ±0.5 mm position
noise, bounded ±0.3 N force noise, and seed 17. Each cell has one repetition.
The ±5 mm heights are withheld from model fitting but were used during
development. The supplementary ±7.5 mm heights are withheld from both fitting
and live development; their split is predeclared separately. The noisy-delayed
condition was also reserved from development.

## Demonstrated motion distribution

The fitted model learns measured lowering trajectories of physical CoM, body
rotation, and FL foot position, together with duration. The online adapter
conditions the distribution on height belief and the previous feasible
reference, removing its shared contact preload before forming the continuity
waypoint. Sensed motion still updates the belief, support projection, and
underlying tracking controller.

The [conditioned family plot](../../results/landing_pad/study/model/conditioned_motions.png)
and [numeric diagnostics](../../results/landing_pad/study/model/conditioning_diagnostics.json)
show the following offline variation across −10 to +10 mm conditioning heights:

| Diagnostic | Measured model response |
| --- | ---: |
| FL endpoint-height slope | 0.9965 mm/mm |
| Maximum CoM-Z separation | 4.945 mm |
| Maximum relative-pitch separation | 0.1006° |
| Height-only predicted-duration span | 0.002 s |

These measurements establish numerical body–foot coordination in the fitted
distribution. The height-only duration relationship is weak. The 3/4/5-second
examples provide timing covariance, but this evidence does not demonstrate a
useful deeper-ground → longer-time policy, improved performance, or held-out
prediction accuracy. The [model guide](../PRIMP_MODEL.md) documents the
PRIMP-derived construction and its quadruped extensions.

## Learned contribution and remaining timing limitation

The [independent execution audit](../../results/landing_pad/study/validation/learned_execution_audit.json)
examines recorded proposals, accepted/interpolated commands, model phase,
conditioning, and fallback use. In the clean −5 mm learned trial:

| Observation | Recorded evidence |
| --- | ---: |
| Learned phase when missing contact first appears | 0.926 |
| Maximum subsequent body-Z change versus initial distribution, at matched phase | 0.394 mm |
| Maximum subsequent foot-Z change versus initial distribution, at matched phase | 1.652 mm |
| Initial predicted total lowering duration | 4.104 s |
| Predicted duration range during execution | 3.915–4.149 s |
| Executed descent after bounded fallback starts | 4.389 mm |
| Fallback planning updates | 20, representing 1.0 s |
| Model-reported remaining time during fallback | 0 s |

The matched-phase comparison separates updated conditioning from ordinary
progress along the initial trajectory. It establishes a numerical learned
change to body, foot, and duration proposals. The additional descent and time
needed for completion nevertheless receive a major contribution from the
shared recovery rule. The model has not learned to predict positive additional
recovery time after its phase is exhausted. Its lower-pad success cannot by
itself establish either a learned timing benefit or superiority over the
capable alternatives.

Further work should collect recovery examples with demonstrated body/foot
coordination and measured remaining touchdown time, revise timing/phase
conditioning for continued descent, and evaluate the learned contribution
separately from common fallback and tracking feedback. Those changes are
future research; the frozen comparisons retain the implementation audited here.

## Formal comparison

The [primary comparison report](../../results/landing_pad/study/comparison/comparison.md)
and [machine-readable results](../../results/landing_pad/study/comparison/comparison.json)
cover every planned cell. The following values are medians across six trials
per planner, combining the three heights and two sensing profiles:

| Planner | Primary success | First-100-ms peak normal force (N) | Maximum roll/pitch change (°) | Lowering entry to completion (s) | Trials using fallback |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reactive | 6/6 | 1.479 | 0.496 | 13.613 | 0/6 |
| Predictive | 6/6 | 1.458 | 0.497 | 13.742 | 0/6 |
| Learned distribution | 6/6 | 1.744 | 0.489 | 13.620 | 4/6 |

First-100-ms median normal impulses are **0.136**, **0.133**, and **0.157 N·s**,
respectively. These landing-force windows begin at first physical contact,
before full weight transfer; they do not represent final standing forces.
The full report also includes CoM tracking error, per-condition timing,
computation, feasibility projections, and explicit fallback counts. A
[comparison plot](../../results/landing_pad/study/comparison/comparison.png)
shows the individual conditions.

All three methods completed these conditions. The learned planner shows no
clear advantage: its median landing reaction is higher, completion time is
similar, and its slightly lower attitude-change median is not evidence of a
statistically reliable benefit. Four learned trials used the shared fallback,
including both lower-pad sensing conditions. The pilot has one repeat per
condition and one noise seed, so these descriptive results establish only the
tested cases.

| Planner | Reserved-height success / 2 |
| --- | --- |
| Reactive | 2/2 |
| Predictive | 2/2 |
| Learned distribution | 2/2 |

The [reserved-height report](../../results/landing_pad/study/held_out_heights/comparison/comparison.md)
and [comparison data](../../results/landing_pad/study/held_out_heights/comparison/comparison.json)
confirm execution at the previously unused −7.5 and +7.5 mm heights. These six
trials use the exact same frozen source and trained model as the primary
comparison, with no refitting. The learned planner used bounded fallback in
both reserved-height trials. At −7.5 mm it adds **6.718 mm** of descent over
about **1.45 s** before confirmed reload, while model remaining time is zero.
At +7.5 mm, two fallback invocations add no net descent because contact holds
the foot. Invocation counts therefore do not by themselves measure recovery
motion. The learned timing limitation remains relevant.

## Replay and failure-bound evidence

The first formal lower-pad reactive trial passed the strengthened acceptance
checks. Watch its
[recorded replay](../../results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.mp4)
or [preview](../../results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.png).
The video renders saved physical states at 30 fps and labels true pad height
as evaluation information. It does not rerun control or planning.

The [−25 mm guard trial](../../results/landing_pad/development/pad_reactive_20260921T072409_356212Z/pad_report.md)
stopped with the commanded foot bottom bounded at −24 mm. FL remained
unsupported, all three support feet retained contact, and reload never began.
Maximum absolute roll/pitch was 0.436°. Its **FAIL** label is preserved because
the landing did not complete. This expected abort verifies the search bound
and contact gate and is excluded from planner success rates.

## Validation and provenance

The automated suite passed **220 tests** before the formal evaluation freeze;
the [test report](../../results/landing_pad/study/validation/tests.txt) and
[machine-readable check](../../results/landing_pad/study/validation/tests.json)
are preserved with the study.
Core checks include actual reload/final loading and expected 100 Hz MPC solves.
The current pad analyzer also reconstructs applied foot/CoM reference speeds,
bounded monotonic descent, orientation/position limits, frozen references at
contact, and the 20 Hz planner cadence, including pause/resume behavior.

The three earliest reactive development recordings completed their physical
movements but failed this later reference-transition validation. Their command
jumps and restart scheduling were corrected before demonstration collection.
They remain visible as **FAIL**, without being relabeled as physical falls or
counted toward formal success. Their original raw measurements remain intact.

All nine demonstrations pass the
[additional read-only reference audit](../../results/landing_pad/study/validation/landing_reference_audit.json).
Their original metadata, summary, and signal hashes are preserved for training
provenance. The [scene/blinding audit](../../results/landing_pad/study/validation/scene_blinding.json)
found identical initial states, sensor streams, beliefs, and planner references
across the three initial unknown-height cases until their first differing
physical contact. It also confirms unchanged fixed supports and separation of
actual height from planner inputs.

The scene audit is a dated snapshot captured before the earliest three
development reports were regenerated with stronger checks. Their raw-signal
and scene evidence remains unchanged; later derived reports are identified
separately. Training and formal-evaluation evidence remains bound to its saved
hashes. The expected abort also has a dedicated
[raw-signal check](../../results/landing_pad/study/validation/bounded_abort.json).

The preserved [final execution audit](../../results/landing_pad/study/validation/final_execution_audit.json)
independently checks all **24** raw recordings without invoking the analyzer or
rewriting trial evidence. It confirms consistent frozen source/model hashes,
preserved training hashes, contact support and loading, MPC/planner schedules,
and bounded reference execution. Across the nine noisy primary trials, true
target-pad force remained at least **2.269 N** during the **100 ms before
reload**. The minimum final standing load across all feet and all 24 trials
was **31.962 N**. The [audit script](../../results/landing_pad/study/validation/audit_execution.py)
and earlier [primary-only audit](../../results/landing_pad/study/validation/primary_execution_audit.json)
remain beside the final result for reproduction.

The completed 2026-09-21 catalog contains **54 recordings**, including **45
landing-pad recordings**: 12 development, nine demonstrations, and 24 formal
evaluations. Four development recordings retain **FAIL**: the three historical
reference-transition failures and the expected search-bound abort. All remain
separate from the 24/24 formal success count.

Demonstrations share one recorded source version; the learned execution adapter
was refined before formal evaluation, which uses a later frozen version. The
supplementary reserved-height comparison reuses that model and frozen controller.
Reproduce all stages in a fresh directory rather than resuming or overwriting
the historical study with changed code:

```bash
python -m primp_project pad-study all --study-dir primp_project/results/landing_pad/reproduction/study
python -m primp_project pad-study heldout --study-dir primp_project/results/landing_pad/reproduction/study
```
