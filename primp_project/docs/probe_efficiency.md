# How much foothold testing is necessary?

This focused extension compares the preserved posture-adaptive policy with a
policy that requests only enough additional measured proof for the shared next
movement. A foothold may be strong enough for that movement and its force
reserves, yet fail during an unnecessarily large test. The experiment must
measure that possibility rather than assume that a smaller command is safer or
that a successful test is sufficient authorization.

The [completed 32-trial sweep](results/probe_efficiency.md) records 8/16 completed
movements with the sufficient target versus 4/16 with the larger test. Four new
matched pairs avoid pad damage while completing the task; eight minimum-policy
trials still damage the pad and recover. Testing time does not improve.

The [48-trial V2 study](results/weak_pad_v2.md) remains the historical baseline.
Its controller, certificate estimator, recovery behavior, movement optimizer,
timings, and acceptance checks are preserved. New source and recordings live in
separate probe-efficiency files and result folders. The comparison changes the
target of an additional test; both policies retain the same permitted body and
load redistribution, sensor observations, and subsequent task.

## The load being minimized

Let `F_min` be the minimum weak-foot force over the entire shared future
body/load feasible set. It is computed from the measured settled feet and
initial testing CoM. It is an optimization bound, not evidence that the surface
survives this force. The task still requires the declared next leg to lift while
the body makes forward progress from the first test origin.

The unchanged certificate uses a complete stable measured dwell:

```text
certificate = minimum measured force in the dwell - 1 N sensing reserve
future MPC cap = max(0, certificate - 8 N tracking reserve)
minimum sufficient measured plateau = F_min + 1 N + 8 N
```

Requested force, allocated force, measured force, and certified force are
different quantities. A command exactly equal to the required measured plateau
can underprove it because the foot undershoots the command or the sensor reads
low. Any added command-target allowance must be named and fixed independently
of the unchanged certificate reserves. Execution remains forbidden until the
actual measured certificate makes the shared future optimization feasible.
The 8 N tracking reserve remains empirical, not a general safety guarantee.

The new policy stops if no permitted test posture can realize its
sufficient target or if the actual completed test does not establish sufficient
proof. It must not silently fall back to maximum-force testing. Controlled
recovery remains available if a test damages the pad.

The implemented target adds the declared 0.8 N force-observation error bound,
a fixed 0.2 N empirical undershoot allowance, and 0.001 N numerical tolerance.
Thus the measured target is `F_min + 9 N + 0.001 N`, while the requested command
is another 1 N higher. The undershoot allowance is a targeting aid inferred
from the old records, not a verified tracking guarantee. Neither allowance is
substituted for fresh measured proof.

## Why the new capacity corridor matters

An [independent read-only audit](../results/weak_pad/probe_efficiency/validation/reference_corridor.json)
reconstructs the two successful front-leg task geometries from the recorded
settled stance. It uses the previous independent equilibrium LP rather than
calling the execution planner.

| Preserved geometry | Minimum future FL load | Sufficient measured plateau | Previous test command | Previous physical probe peak |
| --- | ---: | ---: | ---: | ---: |
| FR A, two seeds | 39.127–39.133 N | 48.127–48.133 N | 52.367–52.377 N | 52.968–52.980 N |
| FR B, two seeds | 40.559–40.584 N | 49.559–49.584 N | 53.120–53.135 N | 53.695–53.714 N |

These numbers identify a missing experimental region: capacities above the
sufficient test but below the larger physical test. They do not establish the
outcome of a smaller-force execution. In the old records, late-hold physical
force undershot the command by up to 0.150 N; the declared force sensing error
bound was 0.8 N. A separate 1 N command allowance is a plausible initial design
choice from these records. Its adequacy must be checked in new runs, especially
if the smaller target changes the selected probing posture.

The four previously failed pads had capacities of 34 N in A and 29 N in B. Even
relaxing the movement to 30 mm forward progress requires about 35.45 N and
36.85–36.88 N, respectively. Those pads are below the task requirement before
reserves. This extension makes no claim that gentler probing could complete
those four movements.

## Controlled comparison and outcomes

Choose capacities below, near, and above the sufficient target, through the old
larger test load. Keep each geometry, initial state, sensing sequence, shared
controller, and movement constraint identical within a policy pair. Hidden
capacity configures only the simulator and evaluation record; it must not enter
the planner or determine its test command. Declare the sweep and freeze the
method before formal execution, retaining all development and boundary failures.

Report these outcomes separately:

- Completed useful movement with an intact pad and a valid measured certificate.
- Pad damage, including damage during probing, independently of later recovery.
- Controlled recovery to the original supporting tripod.
- Safe stop without completion, and any unhandled or invalid outcome.

Record actual target-pad force rather than the selected foot's launch-surface
force. Report requested and achievable test commands, minimum future load,
measured certificate, physical force peak, and force-cap tracking error.
Measure testing time both as active ramp/hold time and elapsed time including
testing-posture changes and release. Common frozen phase durations may leave
testing time unchanged even when the load is smaller; damage-shortened failed
trials are not evidence of faster successful testing.

This is a test-efficiency comparison within the prescribed quasistatic task and
controller. It does not establish optimal testing, an exact strength estimate,
hardware performance, or a benefit of PRIMP.

## Focused sweep and reproduction

The [declared cases](../results/weak_pad/probe_efficiency/validation/study_cases_proposed.json)
use the existing B support geometry, FR as the next lifted leg, and hidden
capacities of **48.5, 49.5, 50.5, 51, 52, 53, 54, and 56 N**. Both policies run
with sensing seeds **211 and 907**, giving 32 cells. The force sensor has a
−0.6 N bias and bounded ±0.2 N noise; position observations have bounded
±0.1 mm noise. Capacity and seeds are new evaluation conditions. The geometry
and sensing model were already used in development, so this is not a new-layout
generalization study.

Use a fresh output directory to reproduce the comparison:

```bash
conda activate quadruped-pympc
python -m primp_project.probe_efficiency.study all \
  --cases-json primp_project/results/weak_pad/probe_efficiency/validation/study_cases_proposed.json \
  --seeds 211 907 --workers 2 \
  --study-dir primp_project/results/weak_pad/probe_efficiency_reproduction
```

Separate `prepare`, `evaluate`, `report`, and `verify` stages are available.
Preparation records the manifest and source hashes; execution retains every
attempt and checks the preserved V2 source and canonical records. `verify`
checks existing evidence without launching missing cells. The additional raw
audit is in
[validation/audit_execution.py](../results/weak_pad/probe_efficiency/validation/audit_execution.py).
