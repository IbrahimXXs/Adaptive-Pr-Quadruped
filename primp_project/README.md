# Go2 ground-height adaptation with PRIMP-inspired motion learning

Our goal is to teach a quadruped to adjust its **body motion, foot motion, and
timing together** when the ground is higher or lower than expected. This
project uses the Go2 simulation and nominal acados controller in
[Quadruped-PyMPC](https://github.com/iit-DLSLab/Quadruped-PyMPC).

The first scenario is a controlled front-foot lowering movement. If the foot
reaches the expected surface height without contact, the robot should decide
how much farther to lower it, how to move its body while the other three feet
support it, and when to transfer weight. Early contact should also update its
estimate of the surface height.

The implementation now includes a **PRIMP-based motion model** that learns from
successful simulated steps. Contact and missing contact update a shared
ground-height belief; the learned planner conditions the remaining body–foot
motion and duration on that belief and the previously accepted feasible
reference. The continuity waypoint removes the common virtual preload before
model conditioning. Physical observations still drive the terrain belief,
support projection, and low-level controller. PyMPC tracks the revised references.
The initial learning target is the lowering movement; the surrounding body
shift, unloading, lift, hold, contact confirmation, and reload remain explicit
control phases. [Model details](docs/PRIMP_MODEL.md) distinguish the quadruped
extension from published PRIMP.

## Current status and next milestones

| Milestone | Status | Evidence or intended outcome |
| --- | --- | --- |
| Stable four-foot standing | Complete | 30 seconds at zero commanded velocity, with synchronized body, foot, contact, force, support, and timing logs |
| Controlled front-left step on flat ground | Complete | Body shift, gradual unloading, 3 cm lift, 5–10 second airborne hold, slow lowering, contact confirmation, gradual reloading, and recentering |
| Repeat the controlled step | Complete for tested flat-ground conditions | Six successful cycles across two runs, with 6 and 10 second holds and friction coefficients 0.8 and 0.6 |
| Introduce a ground-height mismatch | Prototype implemented and evaluated | All 24 planner/height/sensing cases passed; a separate −25 mm case aborts at the search bound |
| Estimate ground height from contact evidence | Implemented | Shared bounded posterior updated from contact and newly reached airborne depths; actual terrain height is reserved for simulation/evaluation |
| Learn coordinated movement from demonstrations | Nine passing demonstrations fitted | Known-height steps at −10, 0, +10 mm and 3, 4, 5 seconds; learned body–foot correlations and duration covariance |
| Compare capable alternatives | Complete for the pilot: 24/24 passed | Each planner passed 6/6 primary cases and 2/2 reserved-height cases with the same frozen model/controller; no learned advantage established |
| Learn additional recovery timing | Open research step | Learned conditioning revises the motion, but shared fallback handles extra descent after model phase ends and its remaining-time prediction reaches zero |

The original `step` command remains the repeatable flat-ground baseline. The
`pad` and `pad-study` commands introduce height uncertainty and learned motion.
The ±5 mm offsets are excluded from model fitting but were used in reactive
development trials. The noisy, delayed sensing condition is reserved from
development for evaluation. A supplementary six-trial comparison uses ±7.5 mm
heights reserved from both fitting and development. It is an initial simulation study; hardware behavior
and a performance advantage for the learned planner have not been established.
Sustained three-leg support is implemented explicitly; `full_stance` supplies
the four-foot starting state.

The [final raw-signal audit](results/landing_pad/study/validation/final_execution_audit.json)
independently verifies all 24 completed evaluations and preserved training
hashes. The primary and reserved-height comparisons report no consistency
errors. These results complete the initial simulation prototype and evaluation.

The initial engineering pipeline—adjustable terrain, sensor-based adaptation,
demonstration collection, model fitting, execution, and paired evaluation—is
implemented and evaluated. The complete learned body–foot–timing objective is
still open because the model does not yet account for the added recovery time.

See the [standing results](docs/results/standing.md),
[controlled-step results](docs/results/controlled_step.md), and
[landing-pad results](docs/results/landing_pad.md) for measurements,
acceptance checks, and links to the recorded evidence.

The [conditioned motion plot](results/landing_pad/study/model/conditioned_motions.png)
shows the fitted family. Across −10 to +10 mm conditioning heights, the FL
endpoint changes by **0.9965 mm per millimetre** of height, CoM-Z trajectories
separate by up to **4.945 mm**, and relative pitch by **0.1006°**. Height-only
duration predictions vary by only **2 ms**. The 3/4/5-second demonstrations
provide timing covariance, but they do not demonstrate that deeper ground
automatically causes a useful learned increase in duration. These are offline
model diagnostics; closed-loop benefit remains an evaluation question.

The [learned execution audit](results/landing_pad/study/validation/learned_execution_audit.json)
also identifies an active limitation: in the clean −5 mm trial, learned
conditioning changes body and foot references, but completion uses about
**1 second of shared bounded fallback** after model phase reaches its end.
The model reports zero remaining time during that recovery. Learning the
additional recovery time remains unfinished; successful execution alone does
not establish a learned-planner advantage.

Watch the [passing formal lower-pad replay](results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.mp4)
or inspect its [preview](results/landing_pad/evaluation/pad_reactive_20260921T073116_115745Z/replay.png).
It renders stored physical states without rerunning the controller.

The three earliest reactive development recordings completed the physical
movement but now fail strengthened reference-speed/cadence checks. Their
reference-transition issues were corrected before demonstration collection.
All nine training demonstrations pass the additional read-only audit; their
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
Add `--headless` for unattended trials. Collect demonstrations, fit the model,
and run the paired pilot with:

```bash
python -m primp_project pad-study all --study-dir primp_project/results/landing_pad/reproduction/study
```

The study defaults to headless execution and also supports separate `demo`,
`train`, and `evaluate` stages. Its [landing-pad guide](docs/landing_pad.md)
describes the split, bounds, sensing, metrics, and result files.
After the primary comparison, run `pad-study heldout` with the same study
directory for the supplementary ±7.5 mm comparison.
Use a fresh study directory for reproduction. The saved pilot preserves one
common demonstration source version and the later evaluation version; it must
not be silently resumed with changed code or overwritten.

The experiment guides describe the full behavior, controller choices, signals,
and validation: [standing](docs/standing.md) and
[controlled step](docs/controlled_step.md), [landing pad](docs/landing_pad.md),
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
├── environment/           # Independent adjustable-pad scene and environment
├── control/               # Shared step execution, support gates, MPC references
├── planning/              # Sensor boundary, height belief, and three planners
├── learning/              # PRIMP-based distribution, fitting, and conditioning
├── recording/             # Synchronized simulation and experiment logging
├── analysis/              # Independent acceptance checks and plots
├── visualization/         # Offline rendering of recorded physical states
├── tests/                 # Recording, controller, and analysis checks
├── docs/                  # Experiment guides and written result summaries
│   └── results/
├── results/               # Preserved recordings and searchable catalog
│   ├── standing/
│   ├── controlled_step/
│   ├── landing_pad/        # Demonstrations, evaluation, development, and study
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

Each run keeps its measurements, metadata, reports, and plots together.
Signals include body pose, actual and desired foot positions, measured contacts
and forces, planned support, timestamps, and movement phase. Controlled-step
runs also record body references, foot trajectory derivatives, support margins,
force limits, phase transitions, and touchdown confirmation. Source snapshots
and provenance belong to the recording that produced them.
Landing-pad records additionally retain the sensor observations actually given
to the planner, the height belief, revised body/foot/timing references, planning
latency, feasibility projections, and fallback counts. Evaluator-only fields
identify contact with the actual target pad and its true height. A study stores
its split manifest, run inventory, trained model provenance, and comparison
tables separately from raw trial measurements.

To regenerate a report for a particular run:

```bash
python -m primp_project analyze-standing primp_project/results/standing/standing_<timestamp>
python -m primp_project analyze-step primp_project/results/controlled_step/step_<timestamp>
python -m primp_project analyze-pad primp_project/results/landing_pad/evaluation/pad_<planner>_<timestamp>
```

## Checks

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest primp_project/tests -q -o cache_dir=primp_project/artifacts/cache/pytest --basetemp=primp_project/artifacts/test_tmp
```

Plugin autoload is disabled for this command because the installed ROS pytest
plugin uses an incompatible hook API. The experiment commands do not need it.
