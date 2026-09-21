# Does probe force need to follow task demand?

One fixed force selected on both development tasks is compared with the unchanged task-sufficient policy. Paired movement freedoms, controller and sensing/tracking reserves are identical. Each task must achieve its declared progress within 1 mm.

Physical completions: 16/24. Paired examples of damage avoided with physical completion: 4.

| Policy | Trials | Completed | Pad damaged | Recovered after damage | Safe stop | Other outcomes |
| --- | --- | --- | --- | --- | --- | --- |
| fixed_force | 12 | 6 | 6 | 6 | 0 | 0 |
| task_sufficient | 12 | 10 | 2 | 2 | 0 | 0 |

The development rule selected one constant: 52.500 N. It is unchanged across every evaluation task, capacity and seed.

| Task mm / capacity N / seed | Policy | Outcome | Damaged | Test command N | Actual test peak N | Probe s | Recovery s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36.000 / 51.500 / 311 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.515 | 16.572 | 5.104 |
| 36.000 / 51.500 / 1201 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.541 | 16.576 | 5.104 |
| 36.000 / 51.500 / 311 | task_sufficient | SUCCESS | False | 49.084 | 49.521 | 21.548 | 0.000 |
| 36.000 / 51.500 / 1201 | task_sufficient | SUCCESS | False | 49.075 | 49.512 | 21.546 | 0.000 |
| 36.000 / 55.000 / 311 | fixed_force | SUCCESS | False | 52.500 | 53.053 | 21.474 | 0.000 |
| 36.000 / 55.000 / 1201 | fixed_force | SUCCESS | False | 52.500 | 53.052 | 21.472 | 0.000 |
| 36.000 / 55.000 / 311 | task_sufficient | SUCCESS | False | 49.084 | 49.521 | 21.548 | 0.000 |
| 36.000 / 55.000 / 1201 | task_sufficient | SUCCESS | False | 49.075 | 49.512 | 21.546 | 0.000 |
| 40.000 / 51.500 / 311 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.515 | 16.572 | 5.104 |
| 40.000 / 51.500 / 1201 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.541 | 16.576 | 5.104 |
| 40.000 / 51.500 / 311 | task_sufficient | SUCCESS | False | 50.566 | 51.052 | 21.508 | 0.000 |
| 40.000 / 51.500 / 1201 | task_sufficient | SUCCESS | False | 50.557 | 51.042 | 21.506 | 0.000 |
| 40.000 / 55.000 / 311 | fixed_force | SUCCESS | False | 52.500 | 53.053 | 21.474 | 0.000 |
| 40.000 / 55.000 / 1201 | fixed_force | SUCCESS | False | 52.500 | 53.052 | 21.472 | 0.000 |
| 40.000 / 55.000 / 311 | task_sufficient | SUCCESS | False | 50.566 | 51.052 | 21.508 | 0.000 |
| 40.000 / 55.000 / 1201 | task_sufficient | SUCCESS | False | 50.557 | 51.042 | 21.506 | 0.000 |
| 44.000 / 51.500 / 311 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.515 | 16.572 | 5.104 |
| 44.000 / 51.500 / 1201 | fixed_force | RECOVERED_STOP | True | 52.500 | 51.541 | 16.576 | 5.104 |
| 44.000 / 51.500 / 311 | task_sufficient | RECOVERED_STOP | True | 52.049 | 51.575 | 16.816 | 5.104 |
| 44.000 / 51.500 / 1201 | task_sufficient | RECOVERED_STOP | True | 52.040 | 51.560 | 16.816 | 5.104 |
| 44.000 / 55.000 / 311 | fixed_force | SUCCESS | False | 52.500 | 53.053 | 21.474 | 0.000 |
| 44.000 / 55.000 / 1201 | fixed_force | SUCCESS | False | 52.500 | 53.052 | 21.472 | 0.000 |
| 44.000 / 55.000 / 311 | task_sufficient | SUCCESS | False | 52.049 | 52.586 | 21.480 | 0.000 |
| 44.000 / 55.000 / 1201 | task_sufficient | SUCCESS | False | 52.040 | 52.576 | 21.478 | 0.000 |

Among the 6 pairs where both policies completed undamaged, the task-sufficient policy change in probing time ranged from 0.006 to 0.074 s. All-trial times also include tests interrupted by pad failure; shorter failed tests are not efficiency gains.

The scalar fixed force is selected before evaluation and cannot change with task, hidden capacity or seed

A paired fixed-force pad failure is called avoidable here only when the task-sufficient policy completes the same movement undamaged

Requested force, actual target-pad force and measured dwell proof remain distinct. The empirical 8 N tracking reserve has not been established as a universal bound.

Predeclared engineering cases and declared seeds, not a statistical population or independent samples within each trace

Held-out labels describe condition selection before evaluation; development conditions remain labeled separately
