# Matched movement planning and adaptive foothold testing

The current experiment asks whether changing a load test can establish enough
evidence for a useful next movement. Every compared policy uses the same sensor
interface, certificate estimator, and optimizer for body position and leg
loads. Given identical evidence, their future movement plans are identical.
The comparison changes which additional tests a policy may perform.

The [48-trial held-out evaluation](results/weak_pad_v2.md) is complete. Fixed,
force-only, and pose-adaptive testing complete 4, 6, and 10 of their 16 tasks,
respectively. The additional four movements over force-only adaptation come
with four actual pad failures followed by controlled recovery; fixed-pose
policies stop without damaging those pads. Stops and recovery are separate
from completed movement.

The earlier [11-trial experiment](results/weak_pad.md) established contact,
measured load testing, subsequent movement, and conservative stopping. Its
fixed-motion baseline had fewer movement freedoms. V2 makes that experiment's
adaptive body/load quadratic program the shared control foundation and a
capable baseline. This is conventional constrained planning; no PRIMP model is
used in this comparison, and implementation alone does not establish research
novelty.

## What is matched

All policies use `MatchedCapacityPlanner` and its inherited `_future(adapt=True)`
optimizer. Given the same certificate, anchors, initial task origin, force
bounds, and settings, their next body target and support-force allocation are
identical. Regression tests check this directly, including a case where the
baseline must shift laterally to make the next movement possible.

| Policy | Initial test | Additional testing | Next movement |
| --- | --- | --- | --- |
| `fixed_probe` | Predeclared load test at the initial test pose | None | Shared body/load optimizer |
| `adaptive_force_fixed_posture` | Same initial test | May increase the test force, keeping the initial test pose | Shared body/load optimizer |
| `adaptive_probe` | Same initial test | May change test force and body pose | Shared body/load optimizer |

The adaptive policy first checks whether a stronger fixed-pose test suffices.
It uses posture freedom only when that test cannot establish enough load;
extra freedom does not automatically cause a larger test or body excursion.

The maximum requested force, sensor observations, force reserves, controller,
movement bounds, and support margins are matched within each case. A low
initial exploratory force is a declared policy choice, distinct from the
maximum available test budget. The force-only policy tests whether any
advantage requires a changed pose rather than simply another, stronger test.

The task requires at least 30 mm of actual forward CoM movement from the
**initial** test origin, at least 20 mm of actual lift of the declared next leg,
and at least one second satisfying both conditions. Commands include tracking
allowance. A later test does not reset the origin: the body may move forward
during testing and return toward the final task target before lifting the next
leg. Reported trajectories must be interpreted using that fixed origin.

## Why a changed test pose can be necessary

The planner enforces vertical equilibrium and horizontal moment balance:

```text
sum(F_i) = weight
sum(x_i F_i) = weight * CoM_x
sum(y_i F_i) = weight * CoM_y
```

It computes both the minimum weak-foot force over the entire allowed future
movement and the maximum force attainable in the initial test pose. These are
optimization bounds, not measured load certificates.

A development geometry moves the front launch feet 35 mm rearward and the rear
feet 35 mm forward, with small lateral offsets. The selected FL foot then lands
90 mm ahead of its launch point. The body reference for initial testing is
50 mm behind the centroid of the original FR/RL/RR supports; the next lifted
foot is FR. Planning uses the actual measured test origin and settled anchors.
An independent audit of the successful native development run gives:

| Quantity | Normal force |
| --- | ---: |
| Maximum fixed-pose test with the declared 8 N support floors | 19.838 N |
| Maximum fixed-pose test even after removing all support floors | 25.994 N |
| Minimum future FL force for the shared 40 mm commanded movement | 40.181 N |
| Maximum test after an allowed change of body pose | 54.803 N |
| Allocated test after the 2 N probing reserve | 52.803 N |
| Actual measured certificate after the 1 N sensing reserve | 52.080 N |
| Installed future cap after the 8 N tracking reserve | 44.080 N |

With FR lifted, FL is the only support ahead of the rear feet. Lateral body
adjustment cannot remove the forward moment that FL must support; the LP
accounts for the actual settled anchors. Even relaxing progress to the required
physical 30 mm leaves a minimum of 36.544 N, above the ideal fixed-pose maximum
of 25.994 N. The
necessity does not depend on an artificially low force-request ceiling, a
fixed future body pose, or the support-force floors.

This necessity is specific to the prescribed FR lift, forward-progress task,
and shared quasistatic feasibility constraints. Choosing a different next leg,
changing the task, or using other dynamic gaits is not evaluated. It is not a
claim that every physically possible continuation requires a changed test.

The native adaptive trial completed: terminal forward progress was
39.86–39.98 mm, FR clearance was 29.23–29.67 mm, and peak future pad load was
40.563 N. Both matched baselines stopped safely in the same condition. This is
a development result, separate from the frozen held-out evaluation. An earlier
development attempt also stopped because its narrower static feasibility
margin did not survive settling. Both attempts remain recorded. See the
[V2 results](results/weak_pad_v2.md) and the
[independent native necessity audit](../results/weak_pad/study_v2/validation/development/necessary_posture_dev02_audit.json).

## Evidence and continuous validity

The certificate is computed only from allowed measurements over a complete,
contiguous, stable probe plateau. Neither requested force, allocated force,
MPC force cap, geometric maximum, nor a hidden simulator strength becomes proof:

```text
certified load = minimum measured force during the valid dwell - sensing reserve
future MPC cap = max(0, certified load - tracking reserve)
```

A positive certificate with a zero usable cap remains valid evidence of weak
support. It may inform another test or a stop, but does not authorize the next
movement.

The estimator keeps checking contact and tested-location validity during
release, posture changes, decisions, movement, and stopping. Ordinary movement
cannot increase the certificate. Lost contact or excessive tested-foot motion
invalidates it; returning to the old position does not restore it. An explicit
new assessment requires a fresh full measured dwell. The independent analyzer
reconstructs these events from the sensor trace, rather than trusting a
certificate value recorded at movement entry.

The local surface is assumed to have constant, spatially uniform normal-load
strength within the declared tested region. The monitor allows up to 10 mm of
horizontal rolling and 2.5 mm of vertical motion; the evidence plateau has the
stricter 1 mm motion limit. These assumptions do not establish a material model
for fatigue, fracture, shear, or changing support strength.

The 8 N tracking reserve is an empirical development choice. It must be checked
against the actual force minus the corresponding executed MPC force cap in
each evaluated configuration and transition. Report reserve exceedances and
actual loads above the certificate as failures; do not infer a universal
overshoot guarantee from a finite number of trials. Bounded sensor errors are
declared separately and must fit inside the sensing reserve.

## Stops, failed probes, and completion

A proposed stronger test is allowed to explore an unproven load while the
original three supports remain available. It does not authorize lifting the
next support leg. If the pad yields during probing, a sensor-triggered recovery
must unload and lift FL, retain the original tripod, and reach a sustained
measured terminal hold. A software exception or a caught failure flag is not
evidence of recovery.

| Outcome | Physical meaning |
| --- | --- |
| `SUCCESS` | The required forward movement and next-leg lift complete while respecting the certificate |
| `SAFE_STOP` | The movement is declined; the original tripod remains stable and any uncertified target is unloaded |
| `RECOVERED_STOP` | The pad actually fails during testing, followed by validated physical unloading, lift, and stable tripod hold |
| `UNSAFE`, `INCOMPLETE`, `INVALID` | A physical, completion, or evidence requirement failed |

Only `SUCCESS` counts as completed movement. Safe stopping and controlled
recovery are reported separately, along with test duration, number of tests,
test force, posture changes, and recovery cost. Stronger probing can fail or
cost more even when its eventual motion optimizer is identical to a baseline.
In particular, an adaptive test can damage a pad that a fixed-pose policy
would leave intact by stopping. Controlled recovery limits the robot's loss of
support; it does not undo the pad failure or establish overall dominance.

## Reproduction and preservation

Run from the repository root in the existing environment:

```bash
conda activate quadruped-pympc
python -m primp_project weak-pad-v2 --help
python -m primp_project weak-pad-study-v2 --help
```

Standalone trials use an explicit parameter JSON and default to
`results/weak_pad/development_v2/`. Formal evaluation freezes the case manifest
and source, records development conditions, and executes each declared cell
once. A new label or random seed does not turn a previously tested physical
condition into a held-out condition. All failed and interrupted attempts remain
visible. Use a fresh study directory for reproduction.

V1 raw recordings and their original results remain under
`results/weak_pad/study/`. V2 has separate recordings, manifests, comparisons,
and validation artifacts. The earlier PRIMP height-adaptation experiments also
remain separate; they do not supply the planner used here.
