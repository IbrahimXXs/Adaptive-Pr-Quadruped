# Frozen comparison verification

Verified all 32 predeclared trials without changing their recorded evidence.

- Every saved V2 evaluation result was reproduced exactly from raw signals. Every original physical, certificate and recovery criterion is unchanged in the focused summary.
- All 16 policy pairs use identical public inputs, initial geometry and movement optimizer settings.
- Across 28 comparisons with the 56 N reference, all 103 non-host/non-overload-timer signal channels matched exactly before the earliest physical failure. This checks that hidden capacity did not influence execution before observable pad failure.
- The original 48-trial V2 study still matches all 147 canonical file hashes and its original execution-source fingerprint.
- The result catalog labels all 32 formal runs and two excluded development runs by probe policy, preserving historical annotations and distinguishing recovery from completion.

| Policy | Completed undamaged | Pad damaged, then recovered | Other outcomes |
| --- | --- | --- | --- |
| Maximum feasible | 4 / 16 | 12 / 16 | 0 |
| Minimum sufficient | 8 / 16 | 8 / 16 | 0 |

The four additional completions occur at capacities 52 N and 53 N, with both seeds. These provide direct paired evidence of damage avoided while completing the intended movement. Both policies still damaged and recovered on capacities 48.5–51 N.

Among the four pairs where both completed undamaged, the minimum policy took 0.048–0.048 s longer in the full probing sequence. Both retained 12.004 s of active ramp/hold time. Lower force did not improve probing time in this controller.

[Machine-readable checks](frozen_comparison_verification.json) · [Catalog verification](catalog_validation.json) · [Independent physical audit](independent_execution_audit.json) · [Exact baseline behavior check](baseline_behavior_equivalence.json)
