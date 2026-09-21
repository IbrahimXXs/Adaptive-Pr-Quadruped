# Matched testing-policy replay

Preselected condition: **52 N hidden capacity, seed 211**. Capacity is shown only as evaluation truth.

[Watch the synchronized comparison](capacity52p0_paired_seed211.mp4) · [Preview](capacity52p0_paired_seed211.png)

| Policy | Recorded outcome | Individual replay |
| --- | --- | --- |
| Maximum Feasible Test | RECOVERED_STOP | [Video](capacity52p0_maximum_feasible_seed211.mp4) |
| Minimum Sufficient Test | SUCCESS | [Video](capacity52p0_minimum_sufficient_seed211.mp4) |

The videos restore recorded robot states and pad displacement. They do not rerun physics or control.
Both panels start at the same recorded simulation time. A shorter completed trial remains on its final frame with an explicit label.
The preview combines representative outcome frames; their separately labeled timestamps can differ.

Overlays distinguish the selected probe command, sufficient measured plateau, actual target-pad force, certificate, and installed MPC cap.
Body progress is measured from the first probing position; stronger probing does not reset the task origin.

Only completed forward motion together with lifting the next leg counts as task completion. Recovery from a failed pad remains a damaged, incomplete task.

[Full sweep results](../../../../docs/results/probe_efficiency.md) · [Replay provenance and complete decode checks](index.json)
