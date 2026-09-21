# Minimum sufficient additional testing: 32-trial capacity sweep

Targeting a sufficient additional test completed **8/16 movements**, compared
with **4/16** for the frozen maximum-feasible policy. At **52 N and 53 N**, both
noise seeds completed the movement with an intact pad under the smaller test;
the larger test damaged the same pads and required recovery. These four matched
pairs demonstrate unnecessary testing damage in this prescribed task.

All 32 predeclared trials finished. Both policies use the same controller,
movement optimizer, body and load freedoms, sensor interface, certificate
reserves, phase durations, and recovery behavior. Only the target of the
additional test changes. The common initial 12 N test remains.

| Policy | Completed movement | Damaged pad | Controlled recovery | Safe stop / unsafe / invalid |
| --- | ---: | ---: | ---: | ---: |
| Frozen maximum-feasible test | 4/16 | 12/16 | 12/16 | 0 / 0 / 0 |
| Minimum sufficient test with declared allowances | 8/16 | 8/16 | 8/16 | 0 / 0 / 0 |

Damage and recovery are overlapping counts: every damaged pad required recovery,
and none of those trials completed the movement. Recovery does not undo pad
damage or count as task success.

The [full comparison](../../results/weak_pad/probe_efficiency/comparison/report.md),
[machine-readable results](../../results/weak_pad/probe_efficiency/comparison/comparison.json),
and [independent raw audit](../../results/weak_pad/probe_efficiency/validation/independent_execution_audit.json)
retain every declared outcome.

## Where the smaller test helped

Each cell below contains both seeds, **211 and 907**. All use the previously
developed B support geometry and FR next-leg lift. These are new capacities and
seeds, not an unseen geometry. The hidden capacity is available only to the
simulator and evaluator.

| Hidden capacity | Maximum-feasible policy | Minimum-sufficient policy |
| --- | --- | --- |
| 48.5 N | 2 damaged, recovered | 2 damaged, recovered |
| 49.5 N | 2 damaged, recovered | 2 damaged, recovered |
| 50.5 N | 2 damaged, recovered | 2 damaged, recovered |
| 51 N | 2 damaged, recovered | 2 damaged, recovered |
| 52 N | 2 damaged, recovered | 2 completed intact |
| 53 N | 2 damaged, recovered | 2 completed intact |
| 54 N | 2 completed intact | 2 completed intact |
| 56 N | 2 completed intact | 2 completed intact |

The robot does not receive this capacity table. The command comes from the
minimum load over the shared future body/load feasible set, using the measured
settled stance and first probing position:

```text
minimum future FL load:                40.561–40.568 N
required measured plateau:            minimum + 1 N sensing + 8 N tracking + 0.001 N tolerance
minimum-policy test command:           required plateau + 0.8 N sensor-error bound + 0.2 N undershoot allowance
```

The two allowances only choose a command. They do not create evidence or change
the certificate, which still requires a complete stable measured hold. The
0.2 N undershoot allowance was fixed from previous recordings before the sweep;
it is empirical. The [experiment guide](../probe_efficiency.md) gives the method
and reproduction commands.

| Quantity in intact completed trials | Maximum-feasible policy | Minimum-sufficient policy |
| --- | ---: | ---: |
| Selected additional test command | 53.127–53.137 N | 50.562–50.569 N |
| Physical probe peak | 53.703–53.716 N | 51.047–51.057 N |
| Measured certificate after the sensing reserve | 51.613–51.632 N | 48.988–48.997 N |
| Physical future movement peak | 40.898–40.920 N | 40.846–40.847 N |
| Terminal forward progress from first probe | 39.885 mm | 39.977–39.990 mm |
| Maximum FR clearance | 29.659 mm | 29.724–29.726 mm |
| Simultaneous useful-progress hold | 3.122 s | 3.122 s |

The 50.5 N and 51 N cases expose a remaining boundary. They exceed the nominal
required measured plateau of about 49.56 N, yet the smaller policy still damages
them. Its command includes the explicit 1 N targeting allowance, and physical
force rises approximately another 0.49 N above that command. A lower command
is not a physical force cap. This policy targets a sufficient additional test
under its declared allowances; it does not establish the globally smallest or
damage-free test.

## A visible paired example

At 52 N capacity and seed 211, the maximum policy commands 53.137 N. The pad
fails during the ramp at 38.558 s. The original three supports remain available,
the controller unloads and lifts FL, and it settles in a stable recovery stance.
It does not lift FR or complete the subsequent movement.

The minimum policy commands 50.569 N and reaches a physical probe peak of
51.057 N. Its fresh certificate is 48.988 N, leaving a 40.988 N MPC cap after
the unchanged 8 N reserve. The physical future load peaks at 40.847 N; the robot
finishes with approximately 40 mm forward progress and 30 mm FR clearance.

[Watch the synchronized comparison](../../results/weak_pad/probe_efficiency/media/capacity52p0_paired_seed211.mp4)
or inspect the [preview and replay guide](../../results/weak_pad/probe_efficiency/media/README.md).
The videos restore recorded states without rerunning control. They label actual
target-pad force, selected probe command, certificate, installed cap, and
progress from the first probing position. A shorter completed recording remains
on its final frame with an explicit label.

## Probing time and recovery

There is **no probing-time improvement** with the phase durations frozen. In the
four pairs where both policies complete intact, active ramp/hold time is
**12.004 s for both**. Total testing time, including testing-posture changes and
release, is **21.458 s** for the maximum policy and **21.506 s** for the minimum
policy: the smaller test takes **0.048 s longer**. Total trial completion is
0.022–0.098 s longer in those same pairs.

Trials that damage a pad stop the probing sequence early and then recover; their
shorter test time is not faster successful testing. All 20 damaged trials enter
controlled recovery, spending 5.104 s in recovery phases and establishing at
least 3.342 s of measured stable tripod support with FL unloaded and lifted.

Actual physical future loads remain below the installed MPC caps in these
trials. During probe release or posture transitions, actual force exceeds the
installed cap by up to **6.547 N**. The unchanged empirical **8 N reserve** covers
these recorded transitions; it remains unvalidated as a guarantee for other
configurations.

## Validation and limits

The [combined suite passes 549 tests](../../results/weak_pad/probe_efficiency/validation/final_tests.json).
The [independent audit](../../results/weak_pad/probe_efficiency/validation/independent_execution_audit.json)
verifies all 32 raw recordings and all 16 matched prefixes, reconstructing the
task-load LP separately from the execution planner. It checks physical failure
threshold and dwell, qualifying probe evidence, continuous certificate validity,
controller update cadence, actual loading, useful progress, and recovery.

The [preservation and comparison audit](../../results/weak_pad/probe_efficiency/validation/frozen_comparison_verification.json)
checks frozen source and the original 48-trial records, reevaluates every new
record with the unchanged V2 physical validator, and checks matched public
inputs. Across-capacity prefixes also verify that hidden strength does not
affect recorded control or physics before the first failure.
An additional [behavioral equivalence check](../../results/weak_pad/probe_efficiency/validation/baseline_behavior_equivalence.json)
finds the new maximum-policy development run identical to its old V2 counterpart
across 98 shared signals, excluding wall and solver times. Source, split,
recording, and replay hashes are retained with the evidence.

This is a focused deterministic failure-model experiment with one geometry,
two sensing seeds, bounded errors, and one prescribed continuation. Capacities
share identical behavior before failure for a given policy and seed; the 32
cells are not independent samples of a terrain population. The comparison
establishes a benefit of reducing an excessive additional test in these cases,
not optimal testing, hardware safety, or algorithmic novelty. Both planners use
conventional optimization, without PRIMP.

The four old V2 probe failures remain unchanged: their 29 N and 34 N pads are
below even the relaxed task's required load. The four newly avoided failures
here occur on different, stronger 52 N and 53 N pads. No claim is made that the
new policy would complete those old four tasks.
