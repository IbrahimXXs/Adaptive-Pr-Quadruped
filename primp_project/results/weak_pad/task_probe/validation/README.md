# Validation for task-derived versus calibrated fixed-force testing

The development tournament selects one constant before the formal comparison.
All task and capacity changes are then evaluated with that same scalar and the
unchanged task-derived planner. Raw recordings are retained in the neighboring
`trials/` and `task_probe_development/` groups.

| Evidence | Purpose |
| --- | --- |
| [development_protocol.json](development_protocol.json) | Predeclares the three fixed-force candidates and both development tasks |
| [fixed_force_selection.json](fixed_force_selection.json) | Records the selected 52.5 N scalar, selection rule, every native candidate outcome, and immutable evidence hashes |
| [development_selection_raw_audit.json](development_selection_raw_audit.json) | Independently reselects 52.5 N from measured task completion and pad survival in all six candidate trials |
| [analytic_task_design.json](analytic_task_design.json) | Independent equilibrium LP predictions for the chosen task range; explicitly not a physical trial |
| [evaluation_cases.json](evaluation_cases.json) | Six task/capacity combinations, each paired across policies and two seeds |
| [independent_execution_audit.json](independent_execution_audit.json) | Checks raw physical outcomes, task-specific progress, measured certificates, recovery, force targets, one fixed scalar, and matched prefixes |
| [frozen_task_behavior_equivalence.json](frozen_task_behavior_equivalence.json) | Checks that the reused task-derived policy retains its previous nominal development behavior |
| [final_tests.json](final_tests.json) | Exact combined regression command, result, and log hash |
| [task_probe_analyzer_mutations.json](task_probe_analyzer_mutations.json) | Nine deliberate task, proof, force, reserve, and damage falsifications are rejected without changing raw evidence |
| [frozen_comparison_verification.json](frozen_comparison_verification.json) | Reproduces all 24 old and new analyzer results, checks matched inputs and one fixed scalar, and verifies preserved evidence and policy/capacity prefixes |
| [catalog_validation.json](catalog_validation.json) | Confirms all new formal and development records are indexed with outcomes and report links |
| [large_files_audit.json](large_files_audit.json) | Confirms large recordings remain present and are excluded from Git using exact file paths |

The formal declaration is `../split_manifest.json`; execution source hashes are
in `../execution_freeze.json`. The manifest embeds the completed fixed-force
selection. A partial raw audit is not a completed experiment: check both its
`complete` flag and the expected/completed trial counts.

The new raw audit reuses the original independent V2 geometry and certificate
helpers, rather than calling the execution planner or production analyzer. It
also verifies actual progress for each particular task, with the common 1 mm
tolerance, during measured next-leg lift and certified support. It independently
checks that the minimum qualifying development candidate is the scalar applied
across all formal tasks.

```bash
conda activate quadruped-pympc
python primp_project/results/weak_pad/task_probe/validation/audit_task_design.py
python primp_project/results/weak_pad/task_probe/validation/audit_execution.py
```

The [matched replay wrapper](render_matched_replay.py) restores recorded robot
and pad states using the preserved renderer. It executes no control or physics
step. Its preselected pair is the 36 mm task, 51.5 N pad, and seed 311:

```bash
MUJOCO_GL=egl python primp_project/results/weak_pad/task_probe/validation/render_matched_replay.py
```

Videos, previews, hashes, and complete decode checks are grouped in
[`../media/`](../media/README.md). Simulator strength is displayed only as
evaluation information. The first probing position remains the task origin.
