# Adjustable landing pad — FAIL

Planner: **reactive**. Role: **development**. Height condition: **lower**.

| Metric | Value |
|---|---:|
| sample_count | 14853 |
| duration_s | 29.705999999994415 |
| mpc_updates | 2972 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.18830884802005 |
| final_complete_duration_s | 0.0 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | False |
| completion_time_s | 29.705999999994415 |
| lowering_to_touchdown_s | None |
| lowering_to_completion_s | 12.001999999993348 |
| first_target_touchdown_time_s | None |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | None |
| observed_contact_timing | no_touchdown |
| missing_contact_observed | True |
| first_missing_contact_time_s | 21.64799999999888 |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | None |
| normal_impulse_first_100ms_ns | None |
| maximum_roll_pitch_change_during_landing_deg | 0.164440758974277 |
| maximum_com_reference_error_during_landing_m | 0.001793156948883833 |
| maximum_body_rotation_during_landing_deg | 0.22754868804491962 |
| height_belief_final_error_m | 0.005000214470989632 |
| height_belief_error_at_contact_confirmation_m | None |
| planner_update_count | 241 |
| planner_mean_compute_time_s | 0.00014365620757480918 |
| planner_maximum_compute_time_s | 0.00017225499868800398 |
| reference_projection_count | 0.0 |
| planner_fallback_count | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | FAIL | {"status": "failed", "completed_cycles": 0} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 14853, "last_time_s": 29.705999999994415} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 2972, "recorded_updates": 2972, "extra_support_change_updates": 1, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 2972} |
| nlp_status | PASS | {"2": 2672} |
| selected_force_cap | PASS | -0.0 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | FAIL | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005427570084065536 |
| cycle_1_support_slip | PASS | 0.0077395303792842105 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | FAIL | {"unload_duration_s": 3.1, "reload_duration_s": 0.0, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": null} |
| cycle_1_reload_gate | FAIL | null |
| cycle_1_reload_loading | FAIL | null |
| final_four_foot_stance | FAIL | 0.0 |
| final_four_foot_loading | FAIL | {"duration_s": 0.0, "minimum_normal_force_n_by_leg": {"FL": null, "FR": null, "RL": null, "RR": null}} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": -0.024, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": -0.02395619612693258, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 0.0, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | FAIL | {"minimum_normal_force_n": null, "maximum_xy_target_error_m": null, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | FAIL | null |
| pad_target_contact_before_reload | FAIL | {"required_samples": 49, "first_reload_time_s": null} |
| pad_target_reload_loading | FAIL | null |
| pad_belief_bounds | FAIL | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 241, "maximum_fallback_count": 0.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
