# Adjustable landing pad — PASS

Planner: **learned**. Role: **development**. Height condition: **lower**.

| Metric | Value |
|---|---:|
| sample_count | 17354 |
| duration_s | 34.70799999999645 |
| mpc_updates | 3473 |
| maximum_abs_roll_pitch_deg | 0.5165037858965841 |
| maximum_abs_actuator_torque_nm | 11.961695940764377 |
| final_complete_duration_s | 2.0020000000000002 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | True |
| completion_time_s | 34.70799999999645 |
| lowering_to_touchdown_s | 7.297999999995955 |
| lowering_to_completion_s | 17.003999999995386 |
| first_target_touchdown_time_s | 25.00199999999702 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | 3.2979999999959553 |
| observed_contact_timing | late |
| missing_contact_observed | True |
| first_missing_contact_time_s | 23.103999999998074 |
| missing_contact_before_physical_touchdown | True |
| recovery_to_touchdown_s | 1.897999999998948 |
| peak_normal_force_first_100ms_n | 1.5242941904448026 |
| normal_impulse_first_100ms_ns | 0.1354064603893737 |
| maximum_roll_pitch_change_during_landing_deg | 0.4077714358322379 |
| maximum_com_reference_error_during_landing_m | 0.015182547316412854 |
| maximum_body_rotation_during_landing_deg | 0.8797512410993477 |
| height_belief_final_error_m | 0.00023865423598389522 |
| height_belief_error_at_contact_confirmation_m | 0.0006477604180733839 |
| planner_update_count | 151 |
| planner_mean_compute_time_s | 0.0004080960463747129 |
| planner_maximum_compute_time_s | 0.0007461149998562178 |
| reference_projection_count | 50.0 |
| planner_fallback_count | 67.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 17354, "last_time_s": 34.70799999999645} |
| control_alignment | PASS | 2.444225377651321e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3473, "recorded_updates": 3473, "extra_support_change_updates": 2, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3473} |
| nlp_status | PASS | {"2": 3173} |
| selected_force_cap | PASS | -0.0 |
| body_tilt | PASS | 0.5165037858965841 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005427570084065536 |
| cycle_1_support_slip | PASS | 0.007666796573113437 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 25.303999999996854, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0134681882940275, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 28.50599999999508, "minimum_normal_force_n_by_leg": {"FL": 11.422766942789162, "FR": 36.90315507587821, "RL": 40.28062172536606, "RR": 60.51129471035371}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.0020000000000002 |
| final_four_foot_loading | PASS | {"duration_s": 2.0020000000000002, "minimum_normal_force_n_by_leg": {"FL": 32.197529042893784, "FR": 34.1756517749566, "RL": 40.00093956733249, "RR": 41.12838154832479}} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": -0.013916137424450487, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": -0.010155223864246977, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.84539775182752, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.197529042893784, "maximum_xy_target_error_m": 0.0026549067833420577, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00015522386424697728 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 25.303999999996854} |
| pad_target_reload_loading | PASS | 11.422766942789162 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 151, "maximum_fallback_count": 67.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
