# Matched probing policies: 48 held-out evaluations

The frozen evaluation completed all **48 declared trials**: **20 movements,
24 safe stops, and 4 controlled recoveries after actual pad failure**. All
predeclared outcomes occurred, with no `UNSAFE`, `INCOMPLETE`, or `INVALID`
classification. Only the 20 completed movements count as physical success.

Compared with force adaptation at the fixed test pose, allowing a changed pose
enabled **four additional movements**, but also caused **four pad failures
followed by recovery**. Both fixed-pose policies stopped without damaging those
four pads. This establishes a conditional feasibility benefit and a probing
cost/risk tradeoff, not unqualified dominance.

[Formal representative replays](../../results/weak_pad/study_v2/media/README.md)
show the force-adaptive fixed-pose baseline and adaptive-policy movement in the
same 66 N condition and sensing seed, plus recovery on a separate 34 N pad.
The recovery clip is a different capacity condition, not the matched baseline
comparison.

## Held-out outcomes and probing cost

Each policy ran the same eight conditions with sensing seeds 101 and 509.
The future body/load optimizer, movement limits, reserves, and maximum 60 N
probe budget were identical within each condition.

| Policy | Movement successes | Safe stops | Failed probe followed by recovery | Extra tests | Mean time in probing phases |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed initial test | 4/16 | 12/16 | 0/16 | 0 | 8.206 s |
| Adaptive force, fixed test pose | 6/16 | 10/16 | 0/16 | 2 | 9.769 s |
| Adaptive force and test pose | 10/16 | 2/16 | 4/16 | 10 | 14.841 s |

Probing time includes ramp, hold, release, and testing-posture changes. It is
averaged over every declared condition, including stops and failed probes.
The four recoveries each added 5.104 s of recovery phases. Completion time and
all per-trial metrics are retained in the
[comparison report](../../results/weak_pad/study_v2/comparison/report.md),
[JSON](../../results/weak_pad/study_v2/comparison/comparison.json), and
[CSV](../../results/weak_pad/study_v2/comparison/trials.csv).

Both seeds produced the following outcomes in each condition:

| Held-out condition and hidden capacity | Fixed test | Adaptive force, fixed pose | Adaptive test pose |
| --- | --- | --- | --- |
| RL layout A, 38 N | SUCCESS | SUCCESS | SUCCESS |
| RL layout B, 32 N | SUCCESS | SUCCESS | SUCCESS |
| RL requiring another test, 56 N | SAFE_STOP | SUCCESS | SUCCESS |
| FR necessary-pose layout A, 66 N | SAFE_STOP | SAFE_STOP | SUCCESS |
| Same FR layout A, 34 N | SAFE_STOP | SAFE_STOP | RECOVERED_STOP |
| FR necessary-pose layout B, 62 N | SAFE_STOP | SAFE_STOP | SUCCESS |
| Same FR layout B, 29 N | SAFE_STOP | SAFE_STOP | RECOVERED_STOP |
| FR task not provable by allowed safe tests, 80 N | SAFE_STOP | SAFE_STOP | SAFE_STOP |

The last condition has a strong pad but insufficient achievable testing
evidence under the declared constraints. It does not mean the underlying
movement is physically impossible. In the RL additional-test case, both
adaptive policies use the same sufficient fixed-pose test and complete without
an unnecessary posture change.

## Necessity checked on the formal recordings

An [independent LP audit](../../results/weak_pad/study_v2/validation/necessity_audit.json)
reconstructs the bounds from every formal FR recording, using both the allowed
noisy sensor snapshot and independently recorded prior physics. It calls no
planner helpers. All 30 FR records pass; all ten case/seed groups have identical
initial snapshots and movement settings across the three policies.

For the four successful adaptive FR trials, the physical-geometry bounds are:

| Quantity | Layout A, two seeds | Layout B, two seeds |
| --- | ---: | ---: |
| Ideal fixed-pose maximum, with all original-support force floors removed | 24.806–24.807 N | 26.096–26.106 N |
| Minimum future FL force, relaxed to 30 mm progress | 35.451–35.452 N | 36.859–36.870 N |
| Minimum future FL force, commanded 40 mm progress | 39.127–39.128 N | 40.566–40.577 N |
| Measured future certificate | 52.044–52.066 N | 51.615–51.633 N |
| Maximum actual future pad force | 39.556–39.579 N | 40.901–40.938 N |

The relaxed calculation retains the full original upper-forward and lateral
freedoms. Even the ideal fixed-pose maximum remains more than 10 N below the
relaxed task requirement. Terminal actual progress across these four trials
was 39.883–40.019 mm, with FR clearance of 29.210–29.673 mm.

This necessity applies to the prescribed FR lift, forward-progress task, and
shared quasistatic constraints. Selecting another next leg, changing the task,
or using a dynamic gait is outside the comparison.

## What changed from V1

All three policies now use exactly the same body/load quadratic program and
movement constraints. The earlier adaptive body/load planner is the shared
foundation, including the baseline's ability to shift laterally and redistribute
load. The comparison concerns additional testing: no extra test, stronger force
at the fixed pose, or stronger force with a changed pose. The latter first uses
a sufficient fixed-pose test when one is available.

This is an engineering comparison of conventional planners and measured-load
certificates. It does not use PRIMP, establish a new learning method, or by
itself demonstrate research novelty. The [V1 recordings and results](weak_pad.md)
and all prior height-adaptation evidence remain separate.

## Native posture-necessity case

The robot first moves FL to the pad and performs the same nominal 12 N initial
test. Its later task is at least 30 mm of actual forward CoM progress from that
first test origin, a different front leg (FR) at least 20 mm clear of its fixed
support, and at least one second satisfying both conditions. Every policy has
the same 60 N probe budget, body/load optimizer, movement bounds, and reserves.

| Policy | Observed development outcome | Extra test |
| --- | --- | --- |
| `fixed_probe` | `SAFE_STOP` | None |
| `adaptive_force_fixed_posture` | `SAFE_STOP` | No useful fixed-pose test exists |
| `adaptive_probe` | `SUCCESS` | Changed test posture, new measured plateau, then movement |

The independent audit uses the **recorded, settled anchors and measured initial
test CoM**, rather than nominal scene coordinates:

| Geometric or measured quantity | Value |
| --- | ---: |
| Maximum fixed-pose FL test with 8 N original-support floors | 19.838 N |
| Ideal fixed-pose maximum after removing those floors | 25.994 N |
| Minimum FL load over all allowed future body/load allocations | 40.181 N |
| Minimum if commanded progress is relaxed to the physical 30 mm requirement | 36.544 N |
| Allocated moved-pose test after the 2 N probing reserve | 52.803 N |
| New certificate from the actual stable load, after the 1 N sensing reserve | 52.080 N |
| Future MPC cap after the 8 N tracking reserve | 44.080 N |
| Maximum actual future pad load | 40.563 N |

Even the ideal fixed-pose maximum is below the relaxed physical task's minimum.
This rules out the earlier explanation that another larger force request at
the original pose would have sufficed. Both policies may optimize the same
future body position and force allocation.

The necessity claim applies to this prescribed FR lift and forward-progress
task under the shared quasistatic constraints. It does not establish necessity
for every possible gait: selecting another next leg, changing the goal, or
using a dynamic maneuver lies outside this comparison.

During terminal progress, actual forward displacement was 39.86–39.98 mm and
FR clearance was 29.23–29.67 mm. The simultaneous progress condition lasted
3.124 s; maximum roll/pitch was 1.064 degrees. The body advanced farther during
testing and then returned toward the task target, so the trace's 91 mm maximum
forward displacement is not the final movement distance. Progress uses the
original test origin throughout.

Evidence:

- [Adaptive native recording](../../results/weak_pad/development_v2/weak_pad_adaptive_probe_20260921T110509_467417Z/weak_pad_report.md)
- [Fixed-policy stop](../../results/weak_pad/development_v2/weak_pad_fixed_probe_20260921T110625_114013Z/weak_pad_report.md)
- [Force-adaptive fixed-pose stop](../../results/weak_pad/development_v2/weak_pad_adaptive_force_fixed_posture_20260921T110710_629660Z/weak_pad_report.md)
- [Independent necessity audit](../../results/weak_pad/study_v2/validation/development/necessary_posture_dev02_audit.json)

## Failure, recovery, and retained development attempts

A stronger probe on a weaker pad caused actual pad failure. The controller
detected permitted sensor evidence, unloaded and lifted FL, and held the
original tripod. The [recorded recovery](../../results/weak_pad/development_v2/weak_pad_adaptive_probe_20260921T110600_073353Z/weak_pad_report.md)
has 35.60 mm of measured recovery lift, 3.324 s of stable recovered support,
and a 5.104 s recovery interval. Its outcome is `RECOVERED_STOP`, not movement
success. A separate initial-probe failure also recovered without first issuing
a capacity certificate.

The [first necessity development attempt](../../results/weak_pad/development_v2/weak_pad_adaptive_probe_20260921T110015_033589Z/weak_pad_report.md)
stopped safely. Its initial analytic margin was too small once the body settled
and feet rolled. The subsequent development configuration uses measured settled
anchors, a more rearward initial test reference, an 8 N support-force floor,
and a 120 mm allowed testing-posture adjustment. The earlier attempt remains
visible and is not replaced by the successful one.

The capable fixed-policy baseline also
[completed the original nominal RL-lift condition](../../results/weak_pad/development_v2/weak_pad_fixed_probe_20260921T105743_948963Z/weak_pad_report.md):
41.995 mm actual forward progress, 29.048 mm clearance, and 2.980 s simultaneous
hold. Its body/load adaptation is therefore operational, rather than disabled
to manufacture a testing advantage.

## Evaluation protocol and validation

Eight conditions, all three policies, and two new sensing seeds produce
48 declared cells. Conditions vary initial body position, support layout,
next lifted leg, initial test strength, unknown pad capacity, and bounded
sensing errors. The conditions include cases where all policies should
complete, cases requiring another fixed-pose test, two layouts requiring a
changed test posture, weak-pad failures during that test, and a case where no
allowed safe test can establish enough evidence for the task.

Selection used static geometry and LP calculations only, without running the
held-out controller or physics conditions. The
[manifest](../../results/weak_pad/study_v2/split_manifest.json) and
[source freeze](../../results/weak_pad/study_v2/execution_freeze.json) preceded
execution. Force sensing used a declared bias of +0.6 or −0.6 N plus bounded
±0.2 N noise; foot-position noise was bounded by ±0.1 mm per component. The
1 N sensing reserve covers that force-error bound. Contact observations and
the existing MPC state channels remained ideal.

Every attempt remains in the journal. The
[independent raw audit](../../results/weak_pad/study_v2/validation/independent_execution_audit.json)
verifies all 48 records, the frozen source, continuous certificate validity,
actual physical outcomes, and matched initial testing prefixes. It also checks
actual loading against the old certificate during posture changes before the
deliberate stronger ramp. The
[final test suite](../../results/weak_pad/study_v2/validation/final_tests.json)
passed **487 tests**. Validation does not turn a stop or recovery into completed
movement.

## The empirical 8 N reserve

The raw audit separates actual load minus the installed MPC cap from actual
load minus the requested MPC ground-reaction force. The former is the operative
cap-reserve gap. Maxima across all 48 trials were:

| Phase group | Actual minus installed cap | Actual minus requested GRF |
| --- | ---: | ---: |
| Certified movement and safe stopping | 1.582 N | 1.582 N |
| Certified probe release and posture changes | 6.547 N | 7.603 N |
| Deliberate probe ramps and holds | 3.432 N | 3.433 N |
| Controlled recovery | 0 N | 0 N |

The execution and transition groups require a valid certificate. Deliberate
testing and recovery are separate; standing and initial light contact are
excluded from reserve inference. No evaluated configuration exceeded the
declared 8 N cap reserve in these groups. Per-configuration extrema and counts,
including failed probes, are recorded in the raw audit and
[force-tracking plot](../../results/weak_pad/study_v2/validation/force_tracking_gaps.png).
Actual future load stayed at least 6.418 N below its certificate. During the
testing-posture change, before the deliberate stronger ramp, actual loading
stayed at least 1.453 N below the still-current older certificate.

## Interpretation limits

The 8 N tracking reserve remains empirical. The observed extrema do not prove
a bound for new geometry, sensing, motion speed, or hardware. Changing the
testing pose improved completion in selected conditions while increasing test
duration and damaging four pads that fixed-pose stopping preserved.

The pad is a prescribed threshold-and-sinking simulator fixture, not a
structural material model. Certificates assume locally uniform, time-invariant
normal-load capacity. Two seeds per condition and a finite set of geometries
cannot establish population failure rates, broad robustness, or hardware
safety. The [V2 guide](../weak_pad_v2.md) documents sensing, validity monitoring,
the information boundary, and reproduction commands.
