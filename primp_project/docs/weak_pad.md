# Testing a foothold before relying on it

This experiment extends the controlled front-foot landing task to a surface
whose normal-load capacity is unknown to the controller. The robot must do
more than make contact: after testing the foothold, it must advance its body
and lift a different leg, or explicitly stop when the next movement is not
supported by the evidence.

The native comparison is complete: four adaptive trials execute the next
movement, four conservative trials stop safely, and three unaware trials show
pad collapse after successful light contact. All 11 expected outcomes are
validated; only four are physical movement successes. See the
[measured results and replays](results/weak_pad.md). Development failures remain
recorded. The completed height-adaptation studies and their model/data
provenance remain separate and unchanged.

The declared study stores 11 attempts in [`results/weak_pad/study/`](../results/weak_pad/study/):
three strategies at (hidden failure threshold, initial probe command) pairs
(25 N,20 N), (25 N,22 N), and (27 N,24 N), plus conservative/adaptive at
(35 N,12 N) to exercise the stronger-probe decision. The initial probe command
is irrelevant to the unaware controller, which performs no added test. All
cells use seed 17, a 45 N high-level probe request, a 1 N measurement reserve,
and an 8 N tracking reserve. This is a controlled feasibility demonstration,
not a many-seed generalization study.

## Physical task and outcomes

The front-left foot lands on a separate pad while the other three feet remain
on fixed surfaces. The initial problem demonstration uses the existing light
contact gate: at least 2 N for 0.1 s, followed by ordinary weight transfer.
It intentionally has no added load probe; its purpose is to show that successful
touchdown alone does not establish sufficient support for subsequent loading.

The conservative and adaptive strategies then add the same initial gradual
load test and hold. They consider a movement requiring at least **30 mm of actual
forward CoM displacement**, at least **20 mm of actual rear-left foot lift**,
and at least **one second with both conditions satisfied**. The executor
commands additional clearance/progress to allow for tracking error.

| Strategy | Behavior | Meaning of its outcome |
| --- | --- | --- |
| Unaware transfer | Confirms light contact, then transfers weight with the original controller and no added probe | `PROBLEM_COLLAPSE` records the failure mechanism; it is not task success |
| Conservative baseline | Checks a fixed nominal next body motion against demonstrated capacity | `SAFE_STOP` is a valid conservative decision, not completed movement |
| Capacity-aware planner | Uses the same initial test as the conservative baseline, then optimizes body position and support-force allocation within the demonstrated limit | `SUCCESS` requires the physical forward-motion/second-leg-lift checkpoint and all safety checks |

The planner can also request another achievable probe or reject the movement.
A `PROBE` proposal does not authorize the next leg lift. New capacity must first
be demonstrated by a fresh measured plateau. These planner capabilities are
separate from which branches have been exercised in a native recorded trial.

## What a load certificate proves

`planning/load_capacity.py` receives immutable measurements: contact, actual
normal load, foot position and velocity, and optionally an independently
measured surface position. It receives no simulator failure threshold, failure
flag, pad deformation truth, environment object, requested force, or MPC force
cap.

A qualifying plateau contains contiguous measurements over the configured
dwell, with stable contact, small foot/surface motion, low foot speed, and a
small force range. The default executor uses a 0.5 s dwell and a 1 N force
measurement reserve. A short impact spike or a large command that the robot
does not actually apply cannot increase the certificate.

For measured normal forces over a valid window, the two separate quantities are

```text
certified_load = minimum measured force − measurement reserve
future MPC cap = max(0, certified_load − tracking reserve)
```

The first quantity is a demonstrated lower bound on supported load. It is not
the unknown breaking force. The second leaves room for differences between
requested and actual loading; native development determined that a 6 N
reserve was insufficient in one transition, so the current executor uses 8 N.
Actual future load is independently checked against the demonstrated bound.

During ordinary execution, monitoring may invalidate a certificate but cannot
raise it. Lost contact, more than 2.5 mm of vertical motion, or leaving the
configured 10 mm horizontal region invalidates the assessment until explicit
reassessment. Horizontal rolling is permitted only under the stated assumption
that strength is uniform within that local region. The evidence plateau still
requires at most 1 mm of measured foot motion; these are different checks for
different purposes.

## Feasible testing and next-motion planning

The planner uses measured foot anchors, robot weight, declared force bounds,
and optional calibrated force/torque inequalities. Its vertical-force model
enforces

```text
Σ F_i = weight
Σ x_i F_i = weight × CoM_x
Σ y_i F_i = weight × CoM_y
```

A linear program computes the maximum test force achievable at the chosen
body posture while retaining the original three supports. The allocated test
is the minimum of the requested load, that maximum minus a robustness reserve,
and the configured probing ceiling. All three values are reported separately.
The current executor also limits the initial exploratory command to 22 N,
even when the raw posture LP permits more. Consequently the 45 N high-level
request, the raw geometric maximum, the selected 22 N command, and the actual
measured load are different quantities. The reduction from 45 N to 22 N is
partly an exploration choice, not solely a balance constraint. A later stronger
test uses its separately computed feasible posture and bounded allocation.
The body must remain inside the original support triangle with a margin during
testing, so the untouched feet remain available if the new foothold yields.

For the next movement, the conservative baseline retains a fixed nominal body
target. The adaptive planner solves a constrained quadratic program over CoM
XY and four normal forces. The rear-left force is zero for its planned lift,
the front-left cap is bounded by the certificate, and remaining supports must
provide weight and moment balance within the body-position and support-margin
bounds. PyMPC tracks the revised references and contact schedule.

An illustrative calculation—not a native trial result—shows why body posture
matters. With 150 N weight and anchors FL=(0.29,0.15), FR=(0.20,−0.15),
RL=(−0.20,0.15), RR=(−0.20,−0.15) m, a probe CoM at (−0.0667,−0.05) m permits:

| Next target while RL is lifted | Required front-left load |
| --- | ---: |
| Nominal CoM (−0.0367,−0.07) m | 40 N |
| Adapted CoM (−0.0367,−0.11) m | 20 N |

Both advance by 30 mm. The adapted target has a 40 mm minimum support margin.
At the original fixed probe posture, however, the maximum achievable FL force
is approximately 36.73 N when each original support retains at least 5 N. A
45 N request cannot be treated as an achieved 45 N test.

## Simulator model and information boundary

The simulator pad has a hidden constant normal-load threshold. A sustained
overload triggers prescribed irreversible downward motion. Collision and
rendering geometry follow the same saved displacement. This is a controlled
failure fixture, not a structural material simulation.

Its assumptions are deliberately limited: strength is time invariant and
uniform within the tested local region; there is no fatigue, damage
accumulation, shear failure, stochastic strength, or rate dependence. A load
certificate does not establish safety when those assumptions fail. Terrain
strength/deformation truth is kept in evaluation records and is excluded from
the planning interface. The robot's mass and inertia are unchanged.

## Commands and recorded evidence

Run from the repository root in the existing environment:

```bash
conda activate quadruped-pympc
python -m primp_project weak-pad --help
python -m primp_project weak-pad --strategy adaptive --failure-threshold 35 --headless
python -m primp_project results
```

The declared comparison runs with two isolated native workers:

```bash
python -m primp_project weak-pad-study all --workers 2
```

Use a fresh study folder for a new reproduction rather than replacing the
recorded attempts. Its immutable split manifest and execution freeze, trial
journal, and `comparison/report.md` remain alongside the raw records.

`--failure-threshold` configures only the simulator/evaluator. The controller
receives the same allowed measurements regardless of that value. Standalone
trials default to the development group; formal comparisons require a declared
study and preserved attempts rather than repeated selection of passing runs.

Each `results/weak_pad/` recording keeps raw signals, metadata, source snapshots,
the scene, `weak_pad_summary.json`, `weak_pad_report.md`, and
`weak_pad_overview.png`. The catalog separates expected outcomes from physical
success and never replaces the weak-pad checks with a generic step report.
The independent analyzer checks measured evidence windows, future applied MPC
caps and actual pad loads, controller solves, the support schedule, meaningful
forward progress, second-leg clearance, and their sustained overlap. Replay
uses recorded robot states and recorded pad motion; it does not rerun planning.

The task currently uses an explicit measured-load model and constrained
planner. Adding a learned motion or strength distribution is a later question;
this experiment first establishes whether the controller can demonstrate and
respect a useful support limit.
