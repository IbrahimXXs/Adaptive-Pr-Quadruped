# Matched testing-policy replay

Preselected condition: **36 mm forward task, 51.5 N hidden capacity, seed 311**. Capacity is shown only as evaluation truth.

[Watch the synchronized comparison](progress36_capacity51p5_paired_seed311.mp4) · [Preview](progress36_capacity51p5_paired_seed311.png)

| Policy | Recorded outcome | Individual replay |
| --- | --- | --- |
| Fixed Test Selected On Development | RECOVERED_STOP | [Video](progress36_capacity51p5_fixed_force_seed311.mp4) |
| Task-Derived Sufficient Test | SUCCESS | [Video](progress36_capacity51p5_task_sufficient_seed311.mp4) |

The videos restore recorded robot states and pad displacement. They do not rerun physics or control.
Both panels start at the same recorded simulation time. A shorter completed trial remains on its final frame with an explicit label.
The preview combines representative outcome frames; their separately labeled timestamps can differ.

Overlays distinguish the selected probe command, sufficient measured plateau, actual target-pad force, certificate, and installed MPC cap.
Body progress is measured from the first probing position; stronger probing does not reset the task origin.

Only completed forward motion together with lifting the next leg counts as task completion. Recovery from a failed pad remains a damaged, incomplete task.

The fixed command was selected on both 34 mm and 45 mm development tasks and remains one constant throughout evaluation.

[Full comparison results](../../../../docs/results/task_probe.md) · [Replay provenance and complete decode checks](index.json)
