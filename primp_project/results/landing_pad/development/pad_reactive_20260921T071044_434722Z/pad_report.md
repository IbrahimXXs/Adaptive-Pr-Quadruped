# Adjustable landing pad — FAIL

Planner: **reactive**. Role: **development**. Height condition: **approximately_correct**.

| Metric | Value |
|---|---:|
| sample_count | 15646 |
| duration_s | 31.291999999993536 |
| mpc_updates | 3132 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.980353548010312 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | False |
| completion_time_s | 31.291999999993536 |
| lowering_to_touchdown_s | 3.8859999999978463 |
| lowering_to_completion_s | 13.58799999999247 |
| first_target_touchdown_time_s | 21.589999999998913 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -0.11400000000215371 |
| observed_contact_timing | approximately_planned |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.5096711900047448 |
| normal_impulse_first_100ms_ns | 0.13884360833722417 |
| maximum_roll_pitch_change_during_landing_deg | 0.4964863940800049 |
| maximum_com_reference_error_during_landing_m | 0.015049767536312118 |
| maximum_body_rotation_during_landing_deg | 0.9432841664230134 |
| height_belief_final_error_m | 0.00023395628204757855 |
| height_belief_error_at_contact_confirmation_m | 0.0005779469566957771 |
| planner_update_count | 82 |
| planner_mean_compute_time_s | 0.00014286758532096693 |
| planner_maximum_compute_time_s | 0.000225957999646198 |
| reference_projection_count | 4.0 |
| planner_fallback_count | 0.0 |
| learned_conditioning_updates | None |
| learned_duration_min_s | None |
| learned_duration_max_s | None |
| predictive_optimization_failures | None |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15646, "last_time_s": 31.291999999993536} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3132, "recorded_updates": 3132, "extra_support_change_updates": 2, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3132} |
| nlp_status | PASS | {"2": 2832} |
| selected_force_cap | PASS | 4.109437688710737e-12 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005982972096287127 |
| cycle_1_support_slip | PASS | 0.007443042641190415 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.88599999999875, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0115619195413643, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 25.087999999996974, "minimum_normal_force_n_by_leg": {"FL": 11.679764533029747, "FR": 37.17555580030436, "RL": 40.158472001807105, "RR": 60.09692746540927}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.005890679337014, "FR": 34.20466675973395, "RL": 40.065508833959505, "RR": 41.24145483403749}} |
| pad_reference_limit_configuration | PASS | {"max_foot_speed_m_s": 0.015, "search_speed_m_s": 0.005, "max_com_speed_m_s": 0.008, "max_body_displacement_m": 0.012, "target_xy_tolerance_m": 0.005, "max_orientation_deviation_rad": 0.03490658503988659, "max_orientation_rate_rad_s": 0.02} |
| pad_finite_planner_signals | PASS | null |
| pad_commanded_foot_speed | FAIL | {"maximum_m_s": 0.016843686041861896, "limit_m_s": 0.015} |
| pad_commanded_com_speed | FAIL | {"maximum_m_s": 0.01600000000001118, "limit_m_s": 0.008} |
| pad_monotone_lowering | PASS | {"maximum_upward_speed_m_s": 0.0} |
| pad_commanded_body_displacement | PASS | {"maximum_m": 0.001549892822458987, "limit_m": 0.012} |
| pad_commanded_target_xy | PASS | {"maximum_coordinate_error_m": 0.0, "limit_m": 0.005} |
| pad_commanded_orientation | PASS | {"maximum_deviation_rad": 0.0, "maximum_rate_rad_s": 0.0} |
| pad_contact_reference_freeze | PASS | {"maximum_foot_speed_m_s": 0.0, "maximum_com_speed_m_s": 0.0} |
| pad_planner_update_cadence | FAIL | {"frequency_hz": 20.0, "period_steps": 25, "missing_updates": 2, "unexpected_updates": 0} |
| pad_commanded_recovery_speed | PASS | {"checked_intervals": 0, "maximum_m_s": null, "limit_m_s": 0.005} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": -0.004656903755632595, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": -0.0001492823704683996, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.67746384413376, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.005890679337014, "maximum_xy_target_error_m": 0.0023914425165192372, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.0001492823704683996 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.88599999999875} |
| pad_target_reload_loading | PASS | 11.679764533029747 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 82, "maximum_fallback_count": 0.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
