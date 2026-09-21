# Go2 foothold testing and movement within demonstrated load limits

Our current goal is to make a quadruped **test a foothold and choose a next
movement supported by that measured evidence**. A foot can make contact and
survive a light load while still failing during later weight transfer. The
robot must account for how much load its intended body motion and next leg
lift will place on the new support.

The latest experiment asks **how much additional testing is necessary** while
keeping the existing controller and evaluation frozen. Its 32-cell capacity
sweep compares the maximum-feasible test with a minimum sufficient test target,
including the same certificate reserves and explicit command allowances.
The smaller test completes **8/16 movements and damages 8/16 pads**, compared with
**4/16 completions and 12/16 damaged pads** for the baseline. All damage is followed by
controlled recovery. At 52 N and 53 N, four matched trials complete intact where
the larger test breaks the pad. Lower boundary capacities still fail under both
policies, and probing time does not improve.

Start with the [probe-efficiency results](docs/results/probe_efficiency.md),
[paired replay](results/weak_pad/probe_efficiency/media/README.md),
[experiment guide](docs/probe_efficiency.md), and
[independent audit](results/weak_pad/probe_efficiency/validation/independent_execution_audit.json).
All 32 predeclared outcomes were observed; the
[combined suite passes 549 tests](results/weak_pad/probe_efficiency/validation/final_tests.json).
The four newly avoided failures involve stronger pads and are distinct from
the four earlier V2 failures, which remain below the relaxed task load.

The preserved V2 comparison turns a measured load plateau into a conservative
certificate and gives **every policy the same body/load optimizer and movement
freedoms**. Policies differ only in whether further testing may change force
and testing pose. Task completion requires at least 30 mm forward CoM movement
and 20 mm lift of the declared next leg together for at least one second.

All **48 held-out trials** are complete. Fixed probing completes 4/16 movements,
force adaptation at the fixed test pose completes 6/16, and adaptation of force
and pose completes 10/16. The other outcomes are **24 safe stops and four
controlled recoveries after actual pad failure**. Adaptive probing enables four
additional movements versus the force-only baseline, but also damages four
pads that fixed-pose policies preserve by stopping. This is a conditional
feasibility benefit with additional probing cost and risk.

The [V2 results](docs/results/weak_pad_v2.md),
[matched replays](results/weak_pad/study_v2/media/README.md),
[independent raw audit](results/weak_pad/study_v2/validation/independent_execution_audit.json),
and [experiment guide](docs/weak_pad_v2.md) retain that earlier comparison.
All 48 predeclared outcomes were observed, with
[487 tests at its freeze](results/weak_pad/study_v2/validation/final_tests.json).

The preserved [11-case V1 study and replays](docs/results/weak_pad.md) contain
four completed movements, four conservative safe stops, and three unaware
collapses. Its ordinary body/load quadratic program is now the shared
foundation and capable baseline. This comparison uses no PRIMP model and
establishes no research novelty claim. Only completed movements count as
physical success; stops and controlled recovery remain separate outcomes.
The earlier height-adaptation and motion-learning work remains preserved below.

## Control and motion-learning foundation

The project uses the Go2 simulation and nominal acados controller in
[Quadruped-PyMPC](https://github.com/iit-DLSLab/Quadruped-PyMPC).

The initial research scenario coordinates **body motion, foot motion, and
timing** when the ground is higher or lower than expected. In a controlled
front-foot lowering movement, if the foot
reaches the expected surface height without contact, the robot should decide
how much farther to lower it, how to move its body while the other three feet
support it, and when to transfer weight. Early contact should also update its
estimate of the surface height.

The implementation includes a **PRIMP-based motion model** learned from
successful simulated steps. Contact and missing contact update a sensor-only
ground-height belief. V2 integrates the learned body–foot/time conditionals with
that posterior's fixed weights, without applying the training-height prior
again. Nominal motion uses the accepted feasible reference for continuity;
recovery predicts remaining motion and time from the current measured state.
The shared predictive optimizer enforces feasible references, and PyMPC tracks
them. Simulator terrain truth is reserved for recording and evaluation.
The initial learning target is the lowering movement; the surrounding body
shift, unloading, lift, hold, contact confirmation, and reload remain explicit
control phases. [Model details](docs/PRIMP_MODEL.md) distinguish the quadruped
extension from published PRIMP.

## Current milestone and established foundation

| Milestone | Status | Evidence or intended outcome |
| --- | --- | --- |
| Target only sufficient additional testing | Complete: 32 declared trials | Minimum targeting completes 8/16 versus 4/16 for the frozen baseline; four new matched pairs avoid damage, while eight minimum-policy trials still damage the pad and recover. No timing advantage |
| Compare testing policies with matched movement freedoms | Complete: 48 held-out trials | Fixed/force-only/adaptive probing complete 4/6/10 of 16 tasks each; 24 safe stops and 4 controlled recoveries remain separate. Independent settled-geometry necessity and raw audits pass |
| Plan beyond first contact on a weak foothold | Preserved V1: 11 declared cases | Four adapted movements, four conservative safe stops, three unaware collapses; its body/load optimizer becomes the V2 shared baseline |
| Stable four-foot standing | Complete | 30 seconds at zero commanded velocity, with synchronized body, foot, contact, force, support, and timing logs |
| Controlled front-left step on flat ground | Complete | Body shift, gradual unloading, 3 cm lift, 5–10 second airborne hold, slow lowering, contact confirmation, gradual reloading, and recentering |
| Repeat the controlled step | Complete for tested flat-ground conditions | Six successful cycles across two runs, with 6 and 10 second holds and friction coefficients 0.8 and 0.6 |
| Introduce a ground-height mismatch | V1 prototype evaluated | All 24 V1 planner/height/sensing cases passed; a separate −25 mm case aborts at the search bound |
| Estimate ground height from contact evidence | Implemented | Shared bounded posterior updated from contact and newly reached airborne depths; actual terrain height is reserved for simulation/evaluation |
| Learn coordinated movement from demonstrations | V2 model fitted from 18 passing trials | Preserved nine V1 demonstrations plus nine new recovery demonstrations at −4, −8, −12 mm with initially zero height estimates |
| Learn additional recovery motion/time | Implemented and evaluated in V2 | Nine recordings supply 102 correlated training windows. Learned remaining time stays positive before clipping in all 48 learned/ablation trials |
| Compare capable alternatives | V1 24/24; V2 60/60 passed | Five matched V2 variants each pass 12/12 reserved conditions. No overall learned advantage is established |
| Validate learned contribution | Explicit V2 checks and attribution | Positive unclipped remaining time, current measured planning anchors, actual learned-prior use, and independently integrated fallback time/displacement |

The original `step` command remains the repeatable flat-ground baseline.
`pad-study` preserves the V1 protocol; `pad-study-v2` runs the new study in its
own folder. Sustained three-leg support is implemented explicitly;
`full_stance` supplies the four-foot starting state.

V2 evaluates five matched variants at previously unused **−6/+6 mm** heights,
noise seeds **17/29/43**, and **30/35 mm** initial held-foot clearances. All
receive 40 ms delayed observations with bounded ±0.5 mm position and ±0.3 N
force noise. Both the evaluation heights and the raised clearance were reserved
from fitting and live development. The [V2 guide](docs/landing_pad_v2.md)
documents the frozen 60-cell protocol, exact ablations, and reproduction.
The source/models remained frozen; **317 tests passed**, all **60 evaluations
passed**, and the [independent audit](results/landing_pad/study_v2/validation/execution_audit.json)
confirms raw evidence and provenance. The
[V2 results](docs/results/landing_pad_v2.md) include the full paired comparison.
Complete learned is a median **0.104 s slower** than matched predictive in
paired completion time, and every complete learned trial uses some common
fallback. Disabling learned timing shortens completion in all 12 pairs
(median **0.194 s**). The implementation works under these conditions; a useful
learned coordination/timing advantage remains unproven.

See the [standing results](docs/results/standing.md),
[controlled-step results](docs/results/controlled_step.md),
[V1 landing-pad results](docs/results/landing_pad.md), and
[V2 matched-study results](docs/results/landing_pad_v2.md) for measurements,
acceptance checks, and links to the recorded evidence.

The [V2 diagnostics](results/landing_pad/study_v2/validation/model_diagnostics.json)
and [plot](results/landing_pad/study_v2/validation/model_diagnostics.png) verify
fixed-posterior conditioning and the recovery fit. Recovery timing MAE is
**0.232 s on its own correlated training windows**; that is not held-out
accuracy. The [learned execution audit](results/landing_pad/study_v2/validation/learned_execution_audit.json)
measures a **0.141 s median per-trial recovery forecast MAE** across six lower-pad
trials during active recovery-prior use. Nominal timing errors are larger and
the recovery mixtures include some extrapolated probability mass. This supports
the implemented recovery forecast without establishing broadly calibrated
timing or a comparative benefit.

The [V1 learned audit](results/landing_pad/study/validation/learned_execution_audit.json)
found zero model remaining time during about one second of shared lower-pad
recovery. V2 addresses that failure mode with current-state recovery windows;
the preserved V1 report retains its original results and limitations. A
[separate integrity audit](results/landing_pad/study_v2/validation/v1_integrity.json)
confirms that all nine V1 demonstrations, all 24 V1 evaluations, and the model
remain unchanged. Neither study establishes hardware performance.

Watch the [V2 learned lower-pad replay](results/landing_pad/study_v2/validation/learned_lower_raised_replay.mp4)
or inspect its [preview](results/landing_pad/study_v2/validation/learned_lower_raised_replay.png).
This passing formal trial uses −6 mm actual height, seed 29, and raised initial
clearance. The video renders stored physical states without rerunning control;
true pad height is labeled as evaluation information.

The three earliest reactive development recordings completed the physical
movement but now fail strengthened reference-speed/cadence checks. Their
reference-transition issues were corrected before demonstration collection.
All nine V1 training demonstrations pass the additional read-only audit; their
original files and training hashes remain unchanged. Historical failures stay
visible in the catalog and are excluded from formal success counts.

## Run an experiment

Run these commands from the repository root using the existing project
environment:

```bash
conda activate quadruped-pympc
python -m primp_project standing
python -m primp_project step
```

The standing experiment includes 2 seconds of settling and 30 seconds of
standing. The step experiment runs three consecutive cycles with 6-second
airborne holds. Both open the viewer and save a new recording automatically.
Use `--headless` for unattended runs, or inspect options with `--help`:

```bash
python -m primp_project step --headless --cycles 3 --hold-seconds 10
python -m primp_project step --help
python -m primp_project results
```

Run the three initial landing cases, with a zero-height initial estimate:

```bash
python -m primp_project pad --actual-height 0 --estimate 0 --planner reactive
python -m primp_project pad --actual-height 0.005 --estimate 0 --planner reactive
python -m primp_project pad --actual-height -0.005 --estimate 0 --planner reactive
```

`--actual-height` configures only the simulator and evaluation record. The
planner receives `--estimate`, nominal geometry, and allowed sensor observations.
Add `--headless` for unattended trials. Reproduce V2 collection, both fits, and
the 60-cell matched comparison in a fresh folder:

```bash
python -m primp_project pad-study-v2 all --workers 4 --study-dir primp_project/results/landing_pad/reproduction_v2
```

The [V2 guide](docs/landing_pad_v2.md) explains separate `declare`, `demo`,
`train`, `freeze`, and `evaluate` stages. Demonstrations run serially; evaluation
can use one to four headless native workers with separate acados build folders.
The parent process owns the journal, and each worker checks frozen source/model
hashes. Omit `--workers` for serial execution.

The original V1 protocol remains available separately:

```bash
python -m primp_project pad-study all --study-dir primp_project/results/landing_pad/reproduction/study
```

The V1 study defaults to headless execution and also supports separate `demo`,
`train`, and `evaluate` stages. Its [landing-pad guide](docs/landing_pad.md)
describes the split, bounds, sensing, metrics, and result files.
After the primary comparison, run `pad-study heldout` with the same study
directory for the supplementary ±7.5 mm comparison.
Use a fresh study directory for reproduction. The saved pilot preserves one
common demonstration source version and the later evaluation version; it must
not be silently resumed with changed code or overwritten.

The experiment guides describe the full behavior, controller choices, signals,
and validation: [standing](docs/standing.md) and
[controlled step](docs/controlled_step.md), [V1 landing pad](docs/landing_pad.md),
[V2 matched study](docs/landing_pad_v2.md),
the [matched weak-pad experiment](docs/weak_pad_v2.md),
the [probe-efficiency extension](docs/probe_efficiency.md),
and [learned model](docs/PRIMP_MODEL.md).

## Project layout

All project-specific source, documentation, recordings, and working artifacts
live here. The upstream simulator and robot/controller packages remain at the
repository root.

```text
primp_project/
├── README.md              # Research goal, status, and entry points
├── __main__.py            # Unified command-line entry point
├── experiments/           # Standing, step, landing-pad, and study runners
├── environment/           # Adjustable-height and load-limited pad environments
├── control/               # Shared step execution, support gates, MPC references
├── planning/              # Height belief, motion priors, measured-load planning
├── learning/              # PRIMP-based distribution, fitting, and conditioning
├── recording/             # Synchronized simulation and experiment logging
├── analysis/              # Independent acceptance checks and plots
├── visualization/         # Offline rendering of recorded physical states
├── probe_efficiency/      # Isolated test-target policy, runner, evaluation, tests
├── tests/                 # Recording, controller, and analysis checks
├── docs/                  # Experiment guides and written result summaries
│   └── results/
├── results/               # Preserved recordings and searchable catalog
│   ├── standing/
│   ├── controlled_step/
│   ├── landing_pad/        # Preserved V1 groups plus the separate study_v2/
│   ├── weak_pad/           # Separate load-testing development/evaluation evidence
│   └── archive/
└── artifacts/             # Diagnostic logs, caches, and temporary test files
```

## Recordings and results

The [results catalog](results/README.md) lists the retained runs and their
purpose. `results/catalog.json` provides the machine-readable index. Original
metadata is preserved; descriptive labels live in `results/annotations.json`.
Recordings are grouped by experiment; development and verification runs are
retained under `archive/`.
`LATEST.txt` points to the newest recording in an experiment or trial group;
`CANONICAL.txt`, where present, selects a reference recording. The catalog also
discovers nested landing-pad demonstration and evaluation groups. A pad trial
passes only when its pad-specific summary passes; a passing underlying step
summary does not replace those extra checks.
Weak-pad records use their own summary. `SAFE_STOP` and `PROBLEM_COLLAPSE` remain
explicit outcomes even when expected by the protocol; neither counts as a
successful physical movement. Only a validated `SUCCESS` receives `PASS`.

Each run keeps its measurements, metadata, reports, and plots together.
Signals include body pose, actual and desired foot positions, measured contacts
and forces, planned support, timestamps, and movement phase. Controlled-step
runs also record body references, foot trajectory derivatives, support margins,
force limits, phase transitions, and touchdown confirmation. Source snapshots
and provenance belong to the recording that produced them.
Landing-pad records additionally retain the sensor observations actually given
to the planner, the height belief, revised body/foot/timing references, planning
latency, feasibility projections, and fallback counts. V2 also logs unclipped
model, optimized, and feasible remaining times, current measured planning
anchors, learned-prior activity, and actual applied fallback time/displacement.
Evaluator-only fields
identify contact with the actual target pad and its true height. A study stores
its split manifest, run inventory, trained model provenance, and comparison
tables separately from raw trial measurements.

For a new or development recording, regenerate its report with the appropriate
analyzer. Frozen study summaries remain tied to their stored training/evaluation
hashes; independent audits are written beside them rather than replacing them.

```bash
python -m primp_project analyze-standing primp_project/results/standing/standing_<timestamp>
python -m primp_project analyze-step primp_project/results/controlled_step/step_<timestamp>
python -m primp_project analyze-pad primp_project/results/landing_pad/evaluation/pad_<planner>_<timestamp>
```

## Checks

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest primp_project/tests primp_project/probe_efficiency/tests -q -o cache_dir=primp_project/artifacts/cache/pytest --basetemp=primp_project/artifacts/test_tmp
```

Plugin autoload is disabled for this command because the installed ROS pytest
plugin uses an incompatible hook API. The experiment commands do not need it.
