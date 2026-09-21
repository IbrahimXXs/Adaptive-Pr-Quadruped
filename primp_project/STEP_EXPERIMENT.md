# Controlled front-left step

This experiment implements sustained three-leg support on known flat ground
using Go2 and the nominal acados MPC. All experiment logic and artifacts are
in `primp_project/`; the simulator has an optional controller factory and
observation refresh hook. Normal standing and upstream controller defaults
continue to use their existing path.

## Run

```bash
conda activate quadruped-pympc
python primp_project/run_step.py
```

The default opens the viewer, performs **three consecutive cycles without
resetting**, and stops after restoring four-foot standing. Each cycle takes
about 31 seconds, including a six-second airborne hold. Useful options:

```bash
python primp_project/run_step.py --headless --cycles 3
python primp_project/run_step.py --cycles 1 --hold-seconds 10
python primp_project/run_step.py --headless --cycles 3 --friction 0.6
```

Hold duration must be 5–10 seconds. Friction is constant within each run;
the default is 0.8. Keyboard velocity commands are held at zero: the scripted
body references move the body. Moving or disturbing the robot with the mouse
can cause a run to fail. The runner saves partial data and returns a nonzero
exit code when a control guard or report check fails.

## Sequence and guards

| Phase | Command and transition requirement |
| --- | --- |
| `stand` | At least 3 seconds on four feet; low speed for 0.2 s |
| `shift` | Smooth 4 s CoM movement to the other three feet's centroid; actual CoM must be at least 20 mm inside their triangle, all three contacts loaded above 5 N, and body speed below 0.02 m/s for 0.2 s |
| `unload` | Smooth 3 s reduction of FL MPC vertical-force limit to zero; blend Cartesian foot holding in; require measured FL load below 3 N and stable remaining supports for 0.1 s |
| `lift` | Remove FL from planned support and raise its immutable world target 30 mm over 2 s; require no FL contact and at least 25 mm measured rise for 0.2 s |
| `hold` | Maintain the same world foot target for the requested 5–10 s; continuously require three loaded supports, support margin above 20 mm, no FL contact, and at least 20 mm clearance |
| `lower` | Smooth descent toward the original anchor over 4 s, still planning only three supports |
| `confirm` | Allow a smooth search up to 5 mm below the original anchor over at most 2 s; active FL contact and at least 2 N normal force must persist for 0.1 s |
| `reload` | Only after confirmation, restore binary FL planned support; ramp its force allowance up and Cartesian correction out over 3 s; require four contacts loaded above 5 N |
| `recenter` | Smooth 4 s return of the body reference; require four contacts and low speed before another cycle |
| `complete` | Final 2 s of four-foot standing |

Durations are simulation seconds, not wall time. Contact gates can extend
phases within their explicit timeouts. A failed gate aborts instead of resetting
the robot or counting an incomplete movement as a successful cycle.
Trajectory segments use quintic interpolation; contact-triggered stops preserve
the commanded position but can reset desired velocity. Global continuity of
acceleration across contact events is not assumed.

## How the controller is coordinated

`controlled_step.py` subclasses the wrapper and supplies a nonperiodic reference
and torque path. It bypasses the periodic gait generator, periodic swing
trajectory, terrain estimator, and early-stance detector for this experiment.
Those modules assume recurring swing/stance and cannot directly represent the
long stationary airborne hold.

The Go2 model, MPC horizon, timestep, gains, and nominal optimization remain.
The following changes apply only to this experiment:

- Physical CoM position uses mass-weighted inertial body positions. Physical
  CoM velocity comes from MuJoCo subtree velocity; the modeled mass is the
  simulator's summed body mass. The usual Gym CoM estimate is biased relative
  to this quantity. Live derived observations are refreshed before controller
  reads; post-step logging still uses a separate refreshed copy.
- Horizontal position costs are enabled at 2000 in both directions; the
  default MPC gives them zero weight. A quintic body reference supplies
  position and velocity during shifts. Desired roll/pitch remain level; the
  lifted foot cannot corrupt a terrain-height estimate.
- FL contact parameters are **binary** throughout the entire horizon. They
  remain zero through lift, hold, lowering, and contact confirmation. No future
  touchdown is assumed. A support change triggers an immediate MPC solve.
- Gradual load transfer uses FL vertical-force inequality bounds at every
  input stage, not fractional contact flags. Zero vertical allowance also
  constrains horizontal force to zero through the friction inequalities.
- Joint bias compensation supports each leg's own weight. FL blends in the
  existing Cartesian PD and feedback-linearization law while unloading,
  follows explicit position/velocity/acceleration references while airborne,
  and blends it out during reloading. Passive-force compensation is applied once.
- The FL anchor is captured after standing and is fixed through touchdown.
  Its airborne target is never rebuilt from its moving measured position.
  Support-foot desired anchors are logged separately from actual positions.

Every MPC update reapplies experiment weights/bounds and checks QP status,
finite forces, and the force cap. NLP statuses 0 and 2 are accepted because
the retained configuration uses one SQP iteration. Failed-solver force
fallbacks are rejected. Optional DDP, RTI, gait adaptation, and extra constraint
variants are rejected by this runner rather than silently losing the caps.

## Logs and acceptance

Each invocation creates `runs/step_<UTC timestamp>/`; `runs/LATEST_STEP.txt`
points to the most recent. The 500 Hz `signals.npz` and `samples.csv` retain
all original body, foot, contact, force, planned support, torque, solver,
and timing measurements. Added signals include cycle and phase, physical CoM
reference, selected-foot anchor, desired foot velocity/acceleration, support
margin, last-solved force cap, contact-confirmation flag/dwell, and unload blend.
MPC samples normally occur at 100 Hz, with extra updates on support changes.

`phase_events.json` records transitions. `metadata.json` records controller
changes and completed cycles. `source/` snapshots the experiment implementation;
`source_changes.patch` records local simulator integration changes.
The independent analyzer writes `step_summary.json`, `step_report.md`, and
`step_overview.png` and checks every cycle. Limits are explicit experiment
acceptance thresholds, not a claim about general robot safety.

The checkpoint requires the full phase sequence, requested continuous airborne
hold, all three support contacts, an independently recomputed positive CoM
margin, bounded tracking/slip/tilt, contact-confirmed reloading, successful QPs,
no torque saturation or termination, and final four-foot standing. Initial
contact settling remains visible in the logs.

Repeated-run results and recording links are in [STEP_RESULTS.md](STEP_RESULTS.md).
To reanalyze a recording:

```bash
python primp_project/analyze_step.py primp_project/runs/step_<timestamp>
```

To run the focused recording, state-machine, and evidence-validation tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest primp_project -q -o cache_dir=primp_project/.pytest_cache --basetemp=primp_project/.pytest_tmp
```

The pytest environment variable avoids the installed ROS plugin's incompatible
hook API. It is not required to run experiments.

This is a scripted flat-ground stepping primitive. It does not yet estimate
unexpected terrain height, learn a PRIMP model, or validate hardware execution.
