# Probe-efficiency validation evidence

The formal raw recordings, metadata, baseline summaries, and focused summaries
remain in `../trials/`. The manifest and execution freeze bind each declared
cell to one attempt. These independent audits read those records without
rewriting them or executing control.

| Evidence | What it checks |
| --- | --- |
| [reference_corridor.json](reference_corridor.json) | Reconstructs the required future load and old probe amplitude from preserved V2 geometry and signals; distinguishes the four old failures from the new capacity corridor |
| [baseline_behavior_equivalence.json](baseline_behavior_equivalence.json) | New maximum-policy development replay matches the historical B/62 N/seed101 trajectory exactly across 98 shared signals, excluding wall and solver time |
| [independent_execution_audit.json](independent_execution_audit.json) | Independent force-equilibrium LP, measured certificate history, physical failure threshold/dwell, tripod recovery, useful movement, paired policy prefixes, and actual-versus-commanded force |
| [frozen_comparison_verification.json](frozen_comparison_verification.json) | Frozen source and old-record preservation, unchanged V2 physical evaluation, matched parameters, and additional comparison integrity checks |
| [final_tests.json](final_tests.json) | Exact regression command, result, and log hash |
| [study_cases_proposed.json](study_cases_proposed.json) | Explicit eight-capacity protocol input; the immutable formal declaration is `../split_manifest.json` |

The raw audit reports partial completion while collection is in progress. Its
`verified` flag alone does not establish that all declared cells have finished;
also check `complete` and the expected/completed counts. Safe stopping and
controlled recovery never count as completed movement.

Reproduce the read-only calculations with the project environment:

```bash
conda activate quadruped-pympc
python primp_project/results/weak_pad/probe_efficiency/validation/audit_reference_corridor.py
python primp_project/results/weak_pad/probe_efficiency/validation/audit_baseline_behavior.py
python primp_project/results/weak_pad/probe_efficiency/validation/audit_execution.py
```

The reference and raw audits reuse the preserved independent V2 audit helpers,
whose equilibrium LP is separate from the execution planner. A source hash
records each helper. Hidden capacity appears only in evaluation of physical
failure, never in the independently reconstructed task-load bound.

The [matched replay wrapper](render_matched_replay.py) uses the preserved V2
renderer with additional policy and load annotations. It restores recorded
robot and pad states and uses `mj_forward`; it does not call `mj_step` or run a
controller. The preselected pair is 52 N capacity, seed 211:

```bash
MUJOCO_GL=egl python primp_project/results/weak_pad/probe_efficiency/validation/render_matched_replay.py
```

Videos, previews, complete decode checks, and provenance are grouped in
[`../media/`](../media/README.md). Diagnostic output from testing the overlay is
kept under the project `artifacts/validation/probe_efficiency/` folder.
