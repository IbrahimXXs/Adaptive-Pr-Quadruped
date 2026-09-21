# Standing baseline

This experiment records **two seconds of settling followed by 30 seconds of
four-foot standing** on flat ground. It establishes the measurements and
baseline behavior for the [ground-height adaptation project](../README.md).
The existing Go2 robot and nominal acados MPC settings are retained.

## Run

From the repository root:

```bash
conda activate quadruped-pympc
python -m primp_project standing
```

The viewer opens and the experiment ends automatically. For unattended runs:

```bash
python -m primp_project standing --headless
```

The runner checks that `simulation_params` contains `gait='full_stance'`,
`scene='flat'`, and `mode='human'`. It enforces zero linear and angular velocity
commands on **every** control step, including if arrow keys are pressed.
Mouse disturbances can still affect the robot and its validation results.
Ground friction is fixed at 0.8; the seed defaults to 0. It stops on a fall or
other termination instead of silently resetting and continuing the recording.

For short debugging runs use `--seconds 1 --settle-seconds 2`. These are not
the full 30-second baseline. Durations must be multiples of the 0.002 s step.

## Files in each recording

Each full baseline invocation creates a new
`primp_project/results/standing/standing_<UTC timestamp>/` directory.
Short runs requested with `--seconds` below 30 go into `results/archive/`
and update that archive's latest pointer.
`results/standing/LATEST.txt` identifies the most recent run;
`results/standing/CANONICAL.txt` identifies the selected baseline recording.
Paths in these pointer files are relative to their containing directory.
Previous runs are preserved and listed in the [results catalog](../results/README.md).

| File | Contents |
| --- | --- |
| `signals.npz` | All signals as named NumPy arrays, including raw model state |
| `samples.csv` | The same measurements as flat columns, one row per physics interval |
| `contact_events.csv` | Observed contact onset/loss, leg, phase, and force at detection |
| `metadata.json` | Settings, versions, source revision, units, frames, and clock conventions |
| `source_changes.patch` | Local simulator/configuration changes at recording time |
| `source/` | Source snapshot for new recordings, preserving package paths |
| `summary.json` | Numerical metrics, explicit pass criteria, and overall result |
| `REPORT.md` | Human-readable results |
| `overview.png` | Body motion, foot motion, forces, and support plots |
| `error.txt` | Exception details, if a run failed or was interrupted |

All experiment artifacts stay in `primp_project/`. Diagnostic logs and caches
under `artifacts/` are ignored by Git. Integration outside this folder is limited to
the existing robot configuration and simulation recorder/controller hooks.

## What is measured

The logging rate is **500 Hz**; the MPC updates at **100 Hz**. The default run
contains 16,000 integration intervals: 1,000 settling and 15,000 standing.
Each sample is the **end** of an interval, so time runs from 0.002 to 32.000 s.
The standing samples cover `(2, 32]` s. `control_time_s` identifies the start
of the interval for the held reference and command. Raw MuJoCo and wall clocks
are also saved. The reset's internal physics step is excluded from experiment
time; its resulting initial state is retained in metadata.

Leg order is always **FL, FR, RL, RR** (front-left, front-right, rear-left,
rear-right). Position is in metres, forces in newtons, torques in Nm, and
rotation/phase timing in radians/seconds as named. Positions, linear velocities,
and contact forces use world XYZ; angular velocity uses the base frame.
Orientation is saved both as scalar-first quaternion and XYZ roll/pitch/yaw.

Actual foot positions are the foot **geometry centers**, not the terrain
surface/contact points. The logger records the actual instantaneous foot target
from the whole-body controller separately from the planner's touchdown target.
During stance, the controller's foot target follows recent measured foot
positions. Therefore a small desired-minus-actual error does not prove the
feet stayed fixed: the report also measures drift from fixed anchors at the
start of the standing phase.

Measured support means an active simulator constraint between the exact foot
geometry and static world geometry. Planned support is copied independently
from the controller. Contact forces are summed **on the foot**, with the sign
corrected for either MuJoCo geometry order. Planned MPC forces are recorded
separately. These are simulator measurements, not hardware force-sensor data.

MuJoCo leaves some geometry/contact arrays stale after stepping. The recorder
copies `MjData` and refreshes the copy with `mj_forward`, aligning actual body,
feet, contacts, and forces at the post-step timestamp without changing the live
controller state. Forces therefore describe the instantaneous post-step
reaction under the held control; they are not integrated landing impulses.
The physical CoM uses mass-weighted body inertial positions. It is distinct
from the CoM estimate used internally by the unchanged controller.

`phase` and `phase_time_s` distinguish settling and standing. Raw gait phase
and per-leg swing time are retained, but full-stance gait phase is a constant
offset rather than a progressing step cycle. Planned support is not inferred
from that phase. Solver results are counted only on `mpc_update` rows; other
rows hold the previous result. Acados status 2 is expected with the existing
one-iteration SQP setting and is allowed only with successful QP solves.

## Validation

The report checks exact duration and continuous clocks, finite data, zero
commands, four planned supports, no reset/termination/numerical warnings, and
successful QP solves. During the standing window all four measured contacts
must remain active. Chosen engineering limits are 5 degrees roll/pitch,
2 cm horizontal body drift, 2 cm height range, 0.03 m/s RMS linear speed,
0.05 rad/s RMS angular speed, and 1 cm maximum foot drift from fixed anchors.
These are explicit baseline acceptance criteria, not general robot safety
limits. Startup/contact settling remains in the logs and is reported separately.

The completed 30-second baseline is recorded in the
[standing results](results/standing.md).

To inspect data interactively:

```python
from pathlib import Path
import numpy as np

root = Path('primp_project/results/standing')
run = root / (root / 'LATEST.txt').read_text().strip()
with np.load(run / 'signals.npz', allow_pickle=False) as log:
    print(log['time_s'].shape)
    print(log['contact_measured'][-1])
    print(log['contact_planned'][-1])
```

The separate [controlled-step experiment](controlled_step.md) builds on these
measurements with sustained three-leg support and a contact-confirmed landing.
The standing baseline remains available for regression checks.

To regenerate a standing report:

```bash
python -m primp_project analyze-standing primp_project/results/standing/standing_<timestamp>
```

Focused recording/analysis tests can be run with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest primp_project/tests -q -o cache_dir=primp_project/artifacts/cache/pytest --basetemp=primp_project/artifacts/test_tmp
```

Plugin autoload is disabled only for this test command because the installed
ROS pytest plugin uses an older pytest hook API.
