# Adjustable landing pad and coordinated motion adaptation

This page describes the physical experiment and the preserved **V1 pilot**.
The separate [V2 matched-planner study](landing_pad_v2.md) adds measured recovery
demonstrations, fixed-posterior conditioning, and timing/covariance ablations.

The task is one front-left step onto a separate surface whose height can differ
from the robot's initial estimate. The robot shifts onto the other three legs,
unloads and lifts FL, moves it forward, holds it above the target, and lowers it.
Early contact or missing contact updates the terrain belief. Weight transfer
starts only after sustained measured loading confirms support.

The scene, sensor boundary, recovery rule, three planners, demonstration fitter,
and comparison pipeline are implemented. All nine known-height demonstrations
passed, including a later independent reference-bounds audit. The fitted model
is available; the primary 18-trial comparison and supplementary six-trial
reserved-height comparison use frozen code. **All 24 evaluation trials passed**:
18 primary trials and six reserved-height trials, giving each planner 6/6 and
2/2 successes respectively.
The [primary comparison](../results/landing_pad/study/comparison/comparison.md)
and [reserved-height comparison](../results/landing_pad/study/held_out_heights/comparison/comparison.md)
report no consistency errors. These results establish execution in the tested
conditions without establishing a learned-method advantage.

## Physical experiment

The four feet initially stand on four separate fixed pads with top height
`z = 0`. The three support pads remain fixed throughout every trial. The FL
launch pad also remains fixed. A fifth, independently adjustable pad sits
**9 cm forward** of the nominal FL starting position. The foot lifts **3 cm**,
translates to the target, and holds for **5 seconds** before lowering.

The landing pad has a 64 mm × 130 mm top. Its height is selected before the
trial and remains constant during execution. The global floor is at −120 mm,
so it cannot hide a target below zero. Project-owned MJCF and evaluation truth
are saved in the trial's `scene/` directory. Installed robot assets are read
without modification.

| Initial case | True target height | Initial estimate | Expected evidence |
| --- | ---: | ---: | --- |
| Correct estimate | 0 mm | 0 mm | Contact near the planned arrival |
| Higher pad | +5 mm | 0 mm | Contact before the planned arrival |
| Lower pad | −5 mm | 0 mm | No contact at the estimated height, then bounded recovery |

The recorded initial trials show touchdown **0.114 s before** the nominal
deadline at zero height, **0.708 s before** at +5 mm, and **0.808 s after** at
−5 mm. The lower-pad trial explicitly observed missing contact before landing.
Those three historical recordings completed the physical movement and passed
their original checks. The strengthened analyzer subsequently detected
reference-speed jumps and planner restart/cadence violations, so they now
retain **FAIL** results. These were reference-generation validation failures,
without physical falls. The transitions were fixed before collection of the
nine training demonstrations, which pass the new bounds audit.

The [formal lower-pad video](../results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.mp4)
and [preview](../results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.png)
show a later passing trial under the frozen implementation and strengthened
checks. They render measured states without executing the planner again. The
earlier development replay remains preserved with its historical recording.

The geometry adapter permits small heights within ±25 mm, while the pilot
collects demonstrations at −10, 0, and +10 mm. These limits define the simulator
experiment; they do not establish a hardware operating envelope.

## Information available during execution

The scene receives the actual target height. The evaluator records it in
`metadata.json` → `evaluation`, `evaluation.json`, and
`scene/evaluation_truth.json`. The planner has no environment, MuJoCo model,
pad object, evaluator contact identifier, or actual-height argument.

The planner receives an explicit immutable observation containing the measured
CoM position/velocity, body orientation, FL position/velocity, four contact
flags and normal forces, support anchors, and measurement/delivery timestamps.
Its context contains the initial height estimate, known foot radius and target
XY, starting references, and common motion limits. The executor uses physical
state for the existing MPC and independent support guards.

All three planners use the same bounded grid posterior. Loaded contact supplies
a noisy height observation based on foot-center height minus the **22 mm foot
radius**. An airborne foot supplies evidence that the surface is below its
underside. Newly reached depths update that evidence; holding at an unchanged
depth does not repeatedly count the same missing-contact observation. MuJoCo
contact margin and compliance mean the first contact flag is not an exact
geometric height measurement.

The `noisy_delayed` evaluation profile adds independent bounded uniform errors
of **±0.5 mm** to supplied CoM/foot positions and **±0.3 N** to normal forces,
then applies **40 ms** of observation delay. Contact flags travel through that
same delay. The pilot fixes the noise seed at **17**, so its paired comparisons
have matching sensing conditions; this is not a multi-seed robustness study.

## Shared execution and recovery limits

During lift, hold, lowering, and contact confirmation, the full MPC contact
horizon keeps FL unsupported and the other three feet supported. The same Go2
model, nominal acados MPC, Cartesian foot controller, and unload/reload ramps
serve every planner. The planner changes references rather than actuator
torques or the support-transfer gate.

The common feasibility layer enforces these bounds:

| Quantity | Limit |
| --- | ---: |
| Extra downward search below initial estimate | 20 mm |
| Additional contact-compression allowance | 4 mm |
| Foot speed before missing contact | 15 mm/s |
| Foot speed after reaching an expected but absent surface | 5 mm/s |
| CoM reference displacement from lowering entry | 12 mm per axis |
| CoM reference speed | 8 mm/s |
| CoM reference margin inside support triangle | 20 mm |
| Body orientation reference change | 2° per axis |
| Planning update rate | 20 Hz |
| Nominal MPC update rate | 100 Hz, plus immediate support transitions |
| Physics and recording rate | 500 Hz |

The minimum commanded foot-center height is
`initial_estimate − 0.020 + foot_radius − 0.004` metres. The actual search must
complete within the nominal lowering duration plus **8 seconds**. Contact must
remain loaded at the confirmation threshold for **0.1 seconds** before FL is
scheduled for support. Reload still requires sustained four-foot loading; the
final standing interval must keep every foot above **5 N**.

The reactive recovery continues slow descent while keeping three-leg support.
It adjusts the body toward a feasible support reference and recalculates the
remaining descent time. The predictive and learned planners use the same
search, feasibility, and contact gates. A bounded fallback is recorded explicitly
and can still complete safely; its use must be reported when interpreting a
planner's performance.

An additional **−25 mm** development trial with a zero estimate tested the
failure boundary. It reached the minimum commanded foot bottom of **−24 mm**,
kept all three support contacts, left FL unsupported, and aborted without
entering reload when support could not be confirmed. Maximum absolute body
roll/pitch was **0.436°**. The recording intentionally retains its **FAIL** label
because the step did not complete; this is evidence that the bounded-search
guard works, not a successful landing. See its
[abort report](../results/landing_pad/development/pad_reactive_20260921T072409_356212Z/pad_report.md).

## Planners and the learned movement model

| Planner | How the remaining references are produced |
| --- | --- |
| `reactive` | Contact-triggered bounded descent, body adjustment from terrain belief/support error, and remaining-time update |
| `predictive` | Receding-horizon optimization of body XYZ and foot height, with support, reach, speed, and smoothness constraints; remaining time follows its descent |
| `learned` | Condition a PRIMP-based body–foot motion distribution and duration on the terrain belief and previously accepted feasible reference |

The predictive reference planner is an alternative above the shared PyMPC
execution controller. It does not replace that controller. The learned method
also sends references through the common feasibility filter, which records
how often it changes a proposal.

The learned adapter uses the preceding accepted body/foot reference as a
continuity waypoint at the current motion phase. It removes the shared virtual
contact-compression offset before forming model features. This prevents a few
millimetres of physical tracking lag from being interpreted as a changed
landing height during phase-conditioned prediction. Physical observations
continue to update the height belief and feed support projection and the
existing tracking controller.

The learned segment runs from lowering entry to contact-confirmed reload.
Its nine channels are physical CoM translation, body rotation in local SO(3)
coordinates, and FL foot translation. Relative-motion covariance preserves
their correlations; height and logarithmic duration provide learned contexts.
Online conditioning produces a remaining suffix of the movement, including a
duration prediction. Preparatory phases and contact gates remain explicit.

The starting point is [Ruan et al., PRIMP](https://arxiv.org/abs/2305.15761).
Our independent quadruped extension uses a product state
`R³(CoM) × SO(3)(body) × R³(foot)` and event-aligned lowering time. The
[model guide](PRIMP_MODEL.md) documents the relationship to the published method,
the [authors' implementation](https://github.com/ChirikjianLab/primp-python),
the covariance construction, training provenance, and limitations.

Demonstrations come from the successful working reactive controller at known
heights. The model therefore learns the demonstrated coordination and timing;
the dataset is not a source of optimal trajectories. The fitter accepts only
completed, passing `demonstration` recordings and their offline known-height
labels. Evaluation and development runs cannot silently enter training.

All **nine** requested demonstrations passed and produced the saved model.
The [conditioned family](../results/landing_pad/study/model/conditioned_motions.png)
and [numeric diagnostics](../results/landing_pad/study/model/conditioning_diagnostics.json)
show these offline changes across conditioning heights from −10 to +10 mm:

| Model diagnostic | Observed |
| --- | ---: |
| FL endpoint-height response | 0.9965 mm per mm of conditioned height |
| Maximum CoM-Z trajectory separation | 4.945 mm |
| Maximum relative-pitch separation | 0.1006° |
| Height-only duration-prediction span | 0.002 s |

The fitted family contains measurable body–foot coordination. The duration
prediction is almost independent of height in these demonstrations. Although
the 3/4/5-second examples produce timing covariance, this dataset does **not**
establish a learned deeper-ground → longer-duration relationship or a useful
timing advantage. Conditioning training midpoint states also illustrates that
covariance, but it is an in-sample diagnostic. Closed-loop evaluation must
separately establish feasible execution and any comparative benefit.

The [online learned-execution audit](../results/landing_pad/study/validation/learned_execution_audit.json)
shows what actually contributes in the formal clean −5 mm trial. Missing
contact first appears at learned phase **0.926**. Before fallback, subsequent
conditioning changes proposed body Z by at most **0.394 mm** and foot Z by at
most **1.652 mm** relative to the original conditioned motion evaluated at the
same phase. The duration distribution changes too, from an initial **4.104 s**
to predictions spanning approximately **3.915–4.149 s**.

Once the learned phase reaches 1, the common fallback supplies a further
**4.389 mm** of executed descent over **20 planning updates**, about **1 second**.
The model's reported remaining time stays **zero** throughout that recovery.
The learned model therefore revises body/foot references and its duration
distribution, while the shared recovery rule makes a substantial contribution
to completing this lower-pad step. It does **not yet predict the added recovery
time**, and a completed trial is not evidence of a learned-method advantage.

The next research step is to collect recovery demonstrations that connect
additional descent with coordinated body movement and measured remaining
contact time, then adapt the learned phase/timing model to preserve positive
remaining time during that recovery. Comparisons should also isolate the
learned proposal's contribution from preload, tracking feedback, reference
projection, and shared fallback. The current frozen pilot evaluates the
implemented controller without silently adding those future changes.

## Pilot split and commands

Run from the repository root after activating the project environment:

```bash
conda activate quadruped-pympc
python -m primp_project pad --actual-height 0 --estimate 0 --planner reactive
python -m primp_project pad --actual-height 0.005 --estimate 0 --planner reactive
python -m primp_project pad --actual-height -0.005 --estimate 0 --planner reactive
```

Single trials show the viewer by default. Add `--headless` for unattended runs.
For a known-height demonstration, both heights must agree:

```bash
python -m primp_project pad --role demonstration --actual-height -0.01 --estimate -0.01 --lower-seconds 3 --planner reactive --headless
```

The study command performs collection, fitting, and evaluation in order:

```bash
python -m primp_project pad-study all --study-dir primp_project/results/landing_pad/reproduction/study
```

Its stages can also be run separately, using the same study directory:

```bash
python -m primp_project pad-study demo --study-dir primp_project/results/landing_pad/reproduction/study
python -m primp_project pad-study train --study-dir primp_project/results/landing_pad/reproduction/study
python -m primp_project pad-study evaluate --study-dir primp_project/results/landing_pad/reproduction/study
python -m primp_project pad-study heldout --study-dir primp_project/results/landing_pad/reproduction/study
```

The study defaults to headless execution; `--render` opens the viewer. The
predeclared pilot contains:

- **9 training demonstrations:** heights −10, 0, +10 mm crossed with nominal
  lowering durations 3, 4, 5 seconds, with correct initial estimates and clean
  sensing.
- **18 evaluation trials:** reactive, predictive, and learned planners crossed
  with target heights −5, 0, +5 mm and clean/noisy-delayed sensing, using a zero
  initial estimate and 4-second nominal lowering duration.
- **6 supplementary reserved-height trials:** the same three planners at
  −7.5 and +7.5 mm, clean sensing, zero initial estimate, 4-second nominal
  duration, and seed 17. These heights were unused during fitting or live
  development. The original fitted model and frozen primary-comparison code
  are reused without tuning between comparisons.

The ±5 mm heights are held out from model fitting but have been seen in the
reactive development trials above. They are not unseen development conditions.
Noisy-delayed observations are reserved from development for evaluation. Zero
height provides the shared reference case. The separately predeclared ±7.5 mm
comparison tests heights reserved from development as well as model fitting.
Nine demonstrations and one repeat per evaluation cell form an engineering
pilot; they cannot establish broad statistical superiority or behavior outside
the demonstrated range. Changing height, sensing, or code settings requires a
fresh study or an explicit new protocol, not silently mixing a resumed dataset.

The stored pilot's nine demonstrations share one source fingerprint and retain
their original measurement, metadata, and analysis hashes. The learned
execution adapter was refined after demonstration collection, then the code
was frozen for formal evaluation. Use the **fresh reproduction directory** in
the commands above to repeat all stages with the current implementation.
Attempting to resume the historical pilot with changed code is intentionally
rejected by provenance checks. Historical recordings remain preserved.

## Recorded evidence and evaluation

Each trial keeps raw signals, metadata, phase/contact events, source snapshots,
scene truth, and reports together. Planner inputs and beliefs are logged
separately from evaluator-only target-pad contact/force and foot-bottom height.
`pad_summary.json` retains every core controlled-step acceptance check and adds
independent checks for actual target-pad loading, bounded descent, surface
geometry, sensor timing, belief consistency, and the truth-field schema.

The evaluator reports successful completion, first-100-ms target-pad peak
normal force and integrated normal impulse, body attitude change, CoM reference
tracking error, completion/lowering/recovery times, terrain-belief error,
planning latency, feasibility projections, and fallback use. Body disturbance
and intentional reference motion are reported separately. These are simulated
quantities; the impulse includes sustained load during its 100 ms window.

Contact timing is compared with lowering entry plus the requested nominal
duration. The descriptive classes are **early**, **approximately planned**
(within ±0.25 seconds), and **late**. This label is not a pass/fail criterion.
Actual touchdown and missing-contact times remain available as numbers, so
late arrival cannot be mistaken for evidence that missing contact was observed.

The existing pilot result layout is shown below. The fresh reproduction
commands create the same structure inside `results/landing_pad/reproduction/`.

```text
results/landing_pad/
├── development/           # Preserved implementation/debug trials
├── demonstrations/        # Passing known-height steps and retained attempts
├── evaluation/            # Paired planner trials and retained attempts
└── study/
    ├── split_manifest.json
    ├── study_state.json
    ├── model/              # model.npz + model.json and training provenance
    ├── comparison/         # Primary comparison.json, .csv, .md, and .png
    └── held_out_heights/    # Separate split, state, recordings, and comparison
```

The catalog discovers nested trial groups and selects `pad_summary.json` for
landing-pad status. It never substitutes a passing underlying step summary
for absent or failed terrain-specific analysis. To reanalyze or inspect data:

```bash
python -m primp_project analyze-pad primp_project/results/landing_pad/evaluation/pad_<planner>_<timestamp>
python -m primp_project results
```

The study manifest and model hashes record which demonstrations produced the
model. Full per-trial reports remain the evidence for acceptance; an aggregate
comparison should always show failures, fallback use, and sensing conditions
alongside averages.

An independent [scene/blinding audit](../results/landing_pad/study/validation/scene_blinding.json)
also compares the three unknown-height development recordings. Their physical
states, sensor streams, height beliefs, and body/foot/timing references are
byte-identical for **20.994 seconds**, ending before the earliest target
contact. Only the target-height geometry differs. All nine demonstrations
share the same initial and pre-lowering physical states. The audit records raw
hashes, nominal-geometry hashes, planner API fields, and a source-level boundary
review; it is stronger evidence than checking labels alone, though it is not a
formal proof against arbitrary covert information channels.

The later [reference audit](../results/landing_pad/study/validation/landing_reference_audit.json)
checks applied reference differences and planner scheduling without altering
training records. All nine demonstrations pass; the three earliest development
recordings fail their historical transition violations. Formal runs use these
stronger acceptance checks directly. The [results page](results/landing_pad.md)
collects the final comparison status and keeps development and expected-abort
records separate from formal landing success counts.

The preserved [final execution audit](../results/landing_pad/study/validation/final_execution_audit.json)
independently reads the raw signals for all 24 trials. It confirms the frozen
source/model, training-file integrity, correct support transfer, and final
loading. Across noisy trials, the minimum true target-pad force over the
100 ms before reload was **2.269 N**; the minimum final standing load across
every foot and all evaluations was **31.962 N**. The
[audit script](../results/landing_pad/study/validation/audit_execution.py)
is retained with the results.
