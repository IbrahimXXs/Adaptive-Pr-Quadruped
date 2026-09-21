# Task-derived testing against one calibrated fixed force

The previous capacity sweep showed that reducing an excessive test can avoid
damage. It used one movement demand, so a smaller constant test could have
explained that result. This experiment varies the required movement and
compares the existing task-derived test with **one fixed force selected only
from development trials**.

All 24 formal trials are complete. Task-derived testing completes **10/12
movements and damages 2/12 pads**, versus **6/12 completions and 6/12 damaged
pads** for the selected fixed force. Every damaged trial recovers; four matched
cases complete intact where the constant test damages the pad. See the
[full results, remaining failures, and timing comparison](results/task_probe.md)
and the [paired replay](../results/weak_pad/task_probe/media/README.md).

Both policies retain the same conventional body/load optimizer, allowed
probing-posture changes, controller, observations, certificate, and recovery
behavior. The fixed policy may change posture to realize its selected force;
it cannot choose a different force for a different task. Neither policy receives
the hidden pad capacity. The existing V2 and 32-trial probe-efficiency source
and results remain preserved.

## A capable fixed-force policy

Development uses the existing B geometry, a 62 N pad, seed 101, and two
forward-movement demands: **34 mm and 45 mm**. Three candidate additional test
commands, **50.57, 52.5, and 53 N**, each run both tasks. The selected scalar is
the smallest command whose two native trials complete their movements without
pad damage. All six attempts are retained, including safe stops or failures.

Development selected **52.5 N**. At 34 mm, all three candidates completed;
at 45 mm, 50.57 N stopped safely, while 52.5 N and 53 N completed. No development
pad was damaged. The
[frozen selection](../results/weak_pad/task_probe/validation/fixed_force_selection.json)
retains the rule and every candidate record. An
[independent raw audit](../results/weak_pad/task_probe/validation/development_selection_raw_audit.json)
reconstructs the same choice from measured task progress and fresh load proof.

The fixed force is therefore selected across a wider task range than the later
evaluation. It is not calibrated only to the easiest or nominal task. The
selection, source, and formal cases are frozen before evaluation; formal
outcomes cannot change the chosen scalar.

This is the lowest successful force among the three declared candidates, not
a global optimization over every possible constant. A different candidate grid
or a selection objective that accepts development-task failures could choose a
different tradeoff.

The common initial 12 N probe remains. Additional testing still requires a
fresh stable measured hold before future loading is authorized. A fixed-force
policy may stop if its single permitted additional test cannot establish a
feasible continuation; it must not silently substitute another force.

## Vary the task while keeping the support geometry fixed

Evaluation uses **36, 40, and 44 mm** commanded forward progress, with FR as the
next lifted leg. These demands interpolate between the two development tasks.
The same B geometry, initial state, and sensing model are used throughout.

The [independent analytic design](../results/weak_pad/task_probe/validation/analytic_task_design.json)
reconstructs force equilibrium from the preserved measured stance. These are
planning predictions, not new physical results:

| Forward demand | Minimum future FL load | Predicted task-derived additional command |
| --- | ---: | ---: |
| 36 mm | 39.077 N | 49.078 N |
| 40 mm | 40.559 N | 50.560 N |
| 44 mm | 42.042 N | 52.043 N |

Small sensing and settling differences can change the live numbers. The task
policy recomputes the minimum over the shared future body/load feasible set
using the observed stance and initial probing origin. Its unchanged formula is:

```text
required measured plateau = minimum future load + 1 N sensing + 8 N tracking + 0.001 N tolerance
additional command = required measured plateau + 0.8 N sensor-error bound + 0.2 N empirical undershoot allowance
```

The original certificate still subtracts the same 1 N and 8 N reserves from
actual measured evidence. An allocated or requested command is never a
certificate. The 0.2 N command allowance and 8 N tracking reserve remain
empirical, without a guarantee for other configurations.

All evaluation tasks retain the original minimum physical-progress and next-leg
lift checks. The new study additionally requires terminal actual progress to
reach at least the declared forward goal minus **1 mm**, together with at least **one second**
of simultaneous task-specific progress, measured FR lift, and certified support.
Thus a nominal 44 mm task cannot count as complete merely by satisfying the old
30 mm gate.

## Bounded evaluation

The 24 declared cells comprise three task demands, two shared hidden capacities
of **51.5 N and 55 N**, two policies, and new sensing seeds **311 and 1201**.
The strong pad checks whether both policies execute the different tasks. The
weaker pad tests the tradeoff between sufficient evidence and testing damage.
Unknown strength remains evaluator-only; it does not determine either command.

The physical task/capacity combinations and seeds are new. The geometry is
known, and the 40 mm demand is a nominal-task control rather than an unseen
movement demand. These are engineering cases, not independent samples of a
terrain population.

Report completed useful movements, pad damage, controlled recovery, safe stops,
and invalid or unsafe outcomes separately. Compare probing time only with its
outcome visible: failed tests terminate probing early, which is not faster
successful testing. Forward progress uses the **first** probing position for
both policies; a later test does not reset the task origin.

This experiment tests the practical value of conditioning the test amplitude
on the next task against a calibrated constant. It does not establish globally
optimal testing, exact strength estimation, hardware safety, or algorithmic
novelty. Both policies use conventional optimization, without PRIMP.

## Reproduce the frozen comparison

The [development protocol](../results/weak_pad/task_probe/validation/development_protocol.json)
lists all six candidate/task cells and the selection rule. The
[evaluation cases](../results/weak_pad/task_probe/validation/evaluation_cases.json)
use the resulting 52.5 N scalar in every task and both policies' metadata.
Reproduce evaluation in a fresh folder using that recorded development choice:

```bash
conda activate quadruped-pympc
python -m primp_project.task_probe.study all \
  --cases-json primp_project/results/weak_pad/task_probe/validation/evaluation_cases.json \
  --selection-json primp_project/results/weak_pad/task_probe/validation/fixed_force_selection.json \
  --seeds 311 1201 --workers 2 \
  --study-dir primp_project/results/weak_pad/task_probe_reproduction
```

Separate `prepare`, `evaluate`, `report`, and `verify` stages are available.
The manifest embeds the immutable development selection and evidence hashes.
Selection verification requires exactly one retained trial for every declared
candidate/task cell; it cannot choose only favorable attempts or use formal
evaluation outcomes to revise the scalar.

The additional [raw audit](../results/weak_pad/task_probe/validation/audit_execution.py)
independently recomputes the force-equilibrium lower bounds, native development
selection, actual per-task progress, certificate evidence, physical pad damage,
and recovery. It does not launch simulation or change canonical recordings.

Large raw recordings remain in the project folder. The
[large-file audit](../results/weak_pad/task_probe/validation/large_files_audit.json)
verifies that files above 99 MB are ignored by exact path, without deleting data
or ignoring entire result folders.
