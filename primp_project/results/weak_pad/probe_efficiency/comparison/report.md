# How much probing is necessary?

Both policies use the frozen V2 controller and physical evaluation. The new policy changes the additional test target; movement freedoms and sensing/tracking reserves are identical.

Physical completions: 12/32. Paired examples of damage avoided with physical completion: 4.

| Policy | Trials | Completed | Pad damaged | Recovered after damage | Safe stop | Other outcomes |
| --- | --- | --- | --- | --- | --- | --- |
| maximum_feasible | 16 | 4 | 12 | 12 | 0 | 0 |
| minimum_sufficient | 16 | 8 | 8 | 8 | 0 | 0 |

| Capacity N / seed | Policy | Outcome | Damaged | Test command N | Actual test peak N | Probe s | Recovery s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 48.500 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 48.635 | 16.188 | 5.104 |
| 48.500 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 48.640 | 16.188 | 5.104 |
| 48.500 / 211 | minimum_sufficient | RECOVERED_STOP | True | 50.569 | 48.561 | 16.420 | 5.104 |
| 48.500 / 907 | minimum_sufficient | RECOVERED_STOP | True | 50.562 | 48.574 | 16.422 | 5.104 |
| 49.500 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 49.634 | 16.258 | 5.104 |
| 49.500 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 49.621 | 16.256 | 5.104 |
| 49.500 / 211 | minimum_sufficient | RECOVERED_STOP | True | 50.569 | 49.520 | 16.580 | 5.104 |
| 49.500 / 907 | minimum_sufficient | RECOVERED_STOP | True | 50.562 | 49.529 | 16.582 | 5.104 |
| 50.500 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 50.620 | 16.334 | 5.104 |
| 50.500 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 50.573 | 16.334 | 5.104 |
| 50.500 / 211 | minimum_sufficient | RECOVERED_STOP | True | 50.569 | 50.549 | 16.922 | 5.104 |
| 50.500 / 907 | minimum_sufficient | RECOVERED_STOP | True | 50.562 | 50.545 | 16.924 | 5.104 |
| 51.000 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 51.083 | 16.382 | 5.104 |
| 51.000 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 51.086 | 16.382 | 5.104 |
| 51.000 / 211 | minimum_sufficient | RECOVERED_STOP | True | 50.569 | 51.008 | 17.072 | 5.104 |
| 51.000 / 907 | minimum_sufficient | RECOVERED_STOP | True | 50.562 | 51.011 | 17.084 | 5.104 |
| 52.000 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 52.021 | 16.532 | 5.104 |
| 52.000 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 52.029 | 16.534 | 5.104 |
| 52.000 / 211 | minimum_sufficient | SUCCESS | False | 50.569 | 51.057 | 21.506 | 0.000 |
| 52.000 / 907 | minimum_sufficient | SUCCESS | False | 50.562 | 51.047 | 21.506 | 0.000 |
| 53.000 / 211 | maximum_feasible | RECOVERED_STOP | True | 53.137 | 53.058 | 16.848 | 5.104 |
| 53.000 / 907 | maximum_feasible | RECOVERED_STOP | True | 53.127 | 53.053 | 16.850 | 5.104 |
| 53.000 / 211 | minimum_sufficient | SUCCESS | False | 50.569 | 51.057 | 21.506 | 0.000 |
| 53.000 / 907 | minimum_sufficient | SUCCESS | False | 50.562 | 51.047 | 21.506 | 0.000 |
| 54.000 / 211 | maximum_feasible | SUCCESS | False | 53.137 | 53.716 | 21.458 | 0.000 |
| 54.000 / 907 | maximum_feasible | SUCCESS | False | 53.127 | 53.703 | 21.458 | 0.000 |
| 54.000 / 211 | minimum_sufficient | SUCCESS | False | 50.569 | 51.057 | 21.506 | 0.000 |
| 54.000 / 907 | minimum_sufficient | SUCCESS | False | 50.562 | 51.047 | 21.506 | 0.000 |
| 56.000 / 211 | maximum_feasible | SUCCESS | False | 53.137 | 53.716 | 21.458 | 0.000 |
| 56.000 / 907 | maximum_feasible | SUCCESS | False | 53.127 | 53.703 | 21.458 | 0.000 |
| 56.000 / 211 | minimum_sufficient | SUCCESS | False | 50.569 | 51.057 | 21.506 | 0.000 |
| 56.000 / 907 | minimum_sufficient | SUCCESS | False | 50.562 | 51.047 | 21.506 | 0.000 |

Among the 4 pairs where both policies completed undamaged, the minimum-policy change in probing time ranged from 0.048 to 0.048 s. All-trial times also include tests interrupted by pad failure; shorter failed tests are not efficiency gains.

The four previous failures remain below the relaxed task load and are not claimed preventable by this experiment

A paired maximum-policy pad failure is called avoidable here only when the minimum policy completes the same movement undamaged

Requested force, actual target-pad force and measured dwell proof remain distinct. The empirical 8 N tracking reserve has not been established as a universal bound.

Predeclared engineering cases and declared seeds, not a statistical population or independent samples within each trace

Held-out labels describe condition selection before evaluation; development conditions remain labeled separately
