# Weak-foothold results

The capacity-aware controller completed the meaningful next movement in **4/4
recorded cases**. The fixed-motion conservative baseline stopped safely in
**4/4**, and the original contact-confirmation/weight-transfer behavior produced
visible pad collapse in **3/3** problem demonstrations. All **11 predeclared
outcomes** were independently classified as expected; only the four completed
movements count as physical success.

This is a small deterministic engineering comparison with one seed and
development-selected conditions. It establishes the implemented behavior in
these simulator cases, not statistical generalization, a hardware guarantee,
or an advantage from a learned PRIMP strength model. The complete machine-
readable results and per-run evidence are in the
[comparison JSON](../../results/weak_pad/study/comparison/comparison.json) and
[comparison report](../../results/weak_pad/study/comparison/report.md).
The [independent raw-signal audit](../../results/weak_pad/study/validation/independent_audit.json)
also verifies all 11 outcomes and their preserved evidence.

## What was tested

The front-left foot contacts the separate load-limited pad; the other surfaces
remain fixed. Simulator failure thresholds are evaluation information and
never enter the planning API. The unaware demonstration uses the existing
2 N/0.1 s contact confirmation, then ordinary weight transfer without probing.
Conservative and adaptive controllers share the same initial measured load
test, sensing, force reserves, and execution controller.

| Hidden threshold | Initial probe command | Unaware | Conservative | Adaptive |
| ---: | ---: | --- | --- | --- |
| 25 N | 20 N | Pad collapse | Safe stop | Completed movement |
| 25 N | 22 N | Pad collapse | Safe stop | Completed movement |
| 27 N | 24 N | Pad collapse | Safe stop | Completed movement |
| 35 N | 12 N | Not scheduled | Safe stop | Stronger probe, then completed movement |

The probe setting is unused by the unaware controller, so its two 25 N trials
repeat the same physical condition. All trials use seed 17, a high-level probe
request of 45 N, a 1 N measurement reserve and an 8 N tracking reserve. The
[manifest](../../results/weak_pad/study/split_manifest.json),
[execution freeze](../../results/weak_pad/study/execution_freeze.json) and
[attempt journal](../../results/weak_pad/study/study_state.json) preserve the
declared cells, execution source, and one recorded attempt per cell.

## Measured adaptive movements

Success requires actual body advance of at least 30 mm and actual rear-left
foot clearance of at least 20 mm simultaneously for at least one second.
Every adaptive trial met those conditions without pad failure and while
keeping subsequent actual pad loading below its demonstrated bound.

| Threshold / initial command | Demonstrated load bound | Future MPC cap | Peak actual future pad force | Maximum forward CoM movement | Maximum RL clearance | Simultaneous qualifying hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 25 / 20 N | 19.407 N | 11.407 N | 17.676 N | 42.073 mm | 28.608 mm | 2.982 s |
| 25 / 22 N | 21.467 N | 13.467 N | 19.724 N | 41.995 mm | 29.048 mm | 2.980 s |
| 27 / 24 N | 23.526 N | 15.526 N | 21.524 N | 41.952 mm | 29.221 mm | 2.976 s |
| 35 / 12 N, after stronger probe | 30.191 N | 22.191 N | 27.522 N | 42.242 mm | 29.477 mm | 2.964 s |

Actual force can exceed the commanded MPC cap. The separate 8 N tracking
reserve is why the certification check compares actual future force with the
demonstrated bound, while planned/installed caps must remain at least 8 N below
that bound. Earlier development observed a 6.435 N command-to-actual gap; the
initial 6 N reserve was insufficient and that development record is retained.
The final controller also continuously checks the measured future load and
the validity of the tested foothold.

## Why the certificate and motion change matter

In the 25 N threshold / 22 N command case, the distinct quantities are:

| Quantity | Recorded value |
| --- | ---: |
| High-level requested test load | 45 N |
| Raw maximum at the original fixed probe posture | 36.089 N |
| Maximum after the probe robustness deduction | 34.089 N |
| Selected initial exploratory command | 22 N |
| Actual force across the probe hold | 22.176–22.632 N |
| Demonstrated bound from the qualifying 0.5 s minimum, minus sensing reserve | 21.467 N |
| Future MPC cap after tracking reserve | 13.467 N |
| Load required by the fixed nominal next movement | 38.744 N |

The 45 N request was neither achievable at that original posture nor actually
applied. The choice of 22 N additionally reflects a conservative exploration
limit; it is not explained solely by force balance. Certification uses the
measured plateau, never the request or its maximum transient sample.

The conservative baseline rejects its fixed nominal movement because the
required 38.744 N is above the usable certificate. The adaptive planner moves
the CoM laterally as it advances, selecting a quasi-static FL allocation of
13.467 N and unloading RL. The resulting physical movement satisfies the task
while the baseline remains on its original three strong supports for a verified
safe stop. Neither safe stopping nor surviving initial contact is counted as
movement completion.

## The stronger-probe branch

The 35 N threshold / 12 N initial command case initially establishes an
11.197 N demonstrated bound and a 3.197 N future cap. That is insufficient for
the constrained next movement. The conservative controller stops. The adaptive
controller records a `PROBE` decision, keeps the original tripod available,
changes its body posture and tests a 30 N allocation. A new measured 0.5 s
plateau raises the demonstrated bound to 30.191 N; only then does a separate
`EXECUTE` decision authorize the next-leg movement.

This run demonstrates fresh evidence before increased reliance on the foot.
It does **not** show that the posture change was necessary to reach the 30 N
test: the original pose's robust maximum already exceeded 30 N. Establishing a
causal benefit from that additional posture change requires another ablation.
The main demonstrated benefit here is changing the subsequent body/load plan
instead of rejecting the fixed nominal movement.

## Watch the recorded behavior

All three videos use the same 25 N threshold / 22 N configured initial-probe
case. They render saved robot states and saved pad displacement without
rerunning control.

| Behavior | Replay | Preview |
| --- | --- | --- |
| Light contact followed by pad collapse during ordinary transfer | [Video](../../results/weak_pad/study/trials/capacity25_probe22_unaware_seed17/weak_pad_unaware_20260921T100855_451535Z/media/weak_replay.mp4) | [Image](../../results/weak_pad/study/trials/capacity25_probe22_unaware_seed17/weak_pad_unaware_20260921T100855_451535Z/media/weak_replay.png) |
| Conservative safe stop after measured testing | [Video](../../results/weak_pad/study/trials/capacity25_probe22_conservative_seed17/weak_pad_conservative_20260921T100929_937092Z/media/weak_replay.mp4) | [Image](../../results/weak_pad/study/trials/capacity25_probe22_conservative_seed17/weak_pad_conservative_20260921T100929_937092Z/media/weak_replay.png) |
| Adapted forward movement and rear-left airborne hold | [Video](../../results/weak_pad/study/trials/capacity25_probe22_adaptive_seed17/weak_pad_adaptive_20260921T100942_173909Z/media/weak_replay.mp4) | [Image](../../results/weak_pad/study/trials/capacity25_probe22_adaptive_seed17/weak_pad_adaptive_20260921T100942_173909Z/media/weak_replay.png) |

The collapse replay shows 15.4 mm of pad descent while the robot remains
upright; pad failure is the demonstrated problem, not a claimed whole-robot
fall. [Replay validation](../../results/weak_pad/study/validation/replay_validation.json)
records raw/media hashes, decoded frame counts, and the inspected preview
states.

## Verification

All **405 project tests pass**. The final analyzer rejects the independently
constructed corrupted logs, including hidden future overload, missing probe
support, false completion, and lost final support. The separate raw-array
audit confirms all eleven outcomes, and read-only study verification confirms
the frozen executor and canonical recording hashes. See the
[verification record](../../results/weak_pad/study/validation/verification.json)
and [test output](../../results/weak_pad/study/validation/tests.log).

## Scope and reproduction

The simulator fixture has a time-invariant normal-load threshold and prescribed
irreversible sinking. Certification assumes uniform strength within the
configured 10 mm horizontal contact region. Vertical motion above 2.5 mm or
loss of the tested contact invalidates it. Fatigue, shear failure, damage
history and stochastic material strength are outside this experiment. No
learned PRIMP distribution was fitted to these weak-pad trials.

All earlier V1/V2 recordings and learned models remain separate. See the
[weak-pad guide](../weak_pad.md) for the sensing boundary, LP/QP equations,
commands, logging, and validation. Reproduce into a fresh folder:

```bash
conda activate quadruped-pympc
python -m primp_project weak-pad-study all --workers 2 --study-dir primp_project/results/weak_pad/reproduction
```
