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

We intend to learn coordinated movements from successful stepping examples
with a **PRIMP-inspired model**. During execution, contact and missing contact
will update the ground-height estimate, and the learned model will suggest a
revised movement. The current work builds and verifies the control and
recording foundation for that research.

## Current status and next milestones

| Milestone | Status | Evidence or intended outcome |
| --- | --- | --- |
| Stable four-foot standing | Complete | 30 seconds at zero commanded velocity, with synchronized body, foot, contact, force, support, and timing logs |
| Controlled front-left step on flat ground | Complete | Body shift, gradual unloading, 3 cm lift, 5–10 second airborne hold, slow lowering, contact confirmation, gradual reloading, and recentering |
| Repeat the controlled step | Complete for tested flat-ground conditions | Six successful cycles across two runs, with 6 and 10 second holds and friction coefficients 0.8 and 0.6 |
| Introduce a known ground-height mismatch | Planned | Test early or missing contact while preserving three-leg support; establish recovery limits and failure criteria |
| Estimate ground height from contact evidence | Planned | Use touchdown or continued absence of contact to revise the estimated surface height |
| Learn coordinated movement from demonstrations | Planned | Build a dataset and a PRIMP-inspired model of body trajectory, foot trajectory, and timing |
| Adapt and evaluate complete movements | Planned | Revise all three components during execution and compare against the scripted baseline |

The current step is a scripted, contact-gated primitive. Ground-height
estimation, learned movement generation, adaptation to unexpected terrain,
and hardware validation are still future work. Sustained three-leg support
is implemented explicitly; `full_stance` supplies the four-foot starting state.

See the [standing results](docs/results/standing.md) and
[controlled-step results](docs/results/controlled_step.md) for measurements,
acceptance checks, and links to the recorded evidence.

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

The experiment guides describe the full behavior, controller choices, signals,
and validation: [standing](docs/standing.md) and
[controlled step](docs/controlled_step.md).

## Project layout

All project-specific source, documentation, recordings, and working artifacts
live here. The upstream simulator and robot/controller packages remain at the
repository root.

```text
primp_project/
├── README.md              # Research goal, status, and entry points
├── __main__.py            # Unified command-line entry point
├── experiments/           # Standing and controlled-step runners
├── control/               # Coordinated step controller and phase logic
├── recording/             # Synchronized simulation and experiment logging
├── analysis/              # Independent acceptance checks and plots
├── tests/                 # Recording, controller, and analysis checks
├── docs/                  # Experiment guides and written result summaries
│   └── results/
├── results/               # Preserved recordings and searchable catalog
│   ├── standing/
│   ├── controlled_step/
│   └── archive/
└── artifacts/             # Diagnostic logs, caches, and temporary test files
```

## Recordings and results

The [results catalog](results/README.md) lists the retained runs and their
purpose. `results/catalog.json` provides the machine-readable index. Original
metadata is preserved; descriptive labels live in `results/annotations.json`.
Recordings are grouped by experiment; development and verification runs are
retained under `archive/`.
Each active experiment directory has a `LATEST.txt` pointer for the newest run
and a `CANONICAL.txt` pointer for the selected reference recording.

Each run keeps its measurements, metadata, reports, and plots together.
Signals include body pose, actual and desired foot positions, measured contacts
and forces, planned support, timestamps, and movement phase. Controlled-step
runs also record body references, foot trajectory derivatives, support margins,
force limits, phase transitions, and touchdown confirmation. Source snapshots
and provenance belong to the recording that produced them.

To regenerate a report for a particular run:

```bash
python -m primp_project analyze-standing primp_project/results/standing/standing_<timestamp>
python -m primp_project analyze-step primp_project/results/controlled_step/step_<timestamp>
```

## Checks

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest primp_project/tests -q -o cache_dir=primp_project/artifacts/cache/pytest --basetemp=primp_project/artifacts/test_tmp
```

Plugin autoload is disabled for this command because the installed ROS pytest
plugin uses an incompatible hook API. The experiment commands do not need it.
