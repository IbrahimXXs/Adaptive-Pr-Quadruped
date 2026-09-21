# Weak-pad comparison

Expected outcomes validated: 11/11. Physical task completions: 4/11.

Collapsing under an unverified transfer and conservatively stopping are separate outcomes, not successful movement.

| Case | Strategy | Outcome | Expected outcome met | Physical success | Certified N | Peak future N | Forward mm | Lift mm | Hold s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| capacity25_probe20 | unaware | PROBLEM_COLLAPSE | True | False | — | 28.791 | -13.983 | -1.895 | 0.000 |
| capacity25_probe20 | conservative | SAFE_STOP | True | False | 19.407 | 11.373 | 1.807 | 0.277 | 0.000 |
| capacity25_probe20 | adaptive | SUCCESS | True | True | 19.407 | 17.676 | 42.073 | 28.608 | 2.982 |
| capacity25_probe22 | unaware | PROBLEM_COLLAPSE | True | False | — | 28.791 | -13.983 | -1.895 | 0.000 |
| capacity25_probe22 | conservative | SAFE_STOP | True | False | 21.467 | 12.092 | 1.894 | 0.297 | 0.000 |
| capacity25_probe22 | adaptive | SUCCESS | True | True | 21.467 | 19.724 | 41.995 | 29.048 | 2.980 |
| capacity27_probe24 | unaware | PROBLEM_COLLAPSE | True | False | — | 31.420 | -9.116 | -1.895 | 0.000 |
| capacity27_probe24 | conservative | SAFE_STOP | True | False | 23.526 | 12.108 | 1.933 | 0.297 | 0.000 |
| capacity27_probe24 | adaptive | SUCCESS | True | True | 23.526 | 21.524 | 41.952 | 29.221 | 2.976 |
| capacity35_probe12 | conservative | SAFE_STOP | True | False | 11.197 | 3.117 | 1.161 | 0.015 | 0.000 |
| capacity35_probe12 | adaptive | SUCCESS | True | True | 30.191 | 27.522 | 42.242 | 29.477 | 2.964 |

Small deterministic engineering comparison with explicit development-selected conditions; no statistical generalization claim
