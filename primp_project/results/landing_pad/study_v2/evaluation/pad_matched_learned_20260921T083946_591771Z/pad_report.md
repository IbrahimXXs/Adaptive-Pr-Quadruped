# Adjustable landing pad — PASS

Planner: **matched_learned**. Role: **evaluation**. Height condition: **higher**.

| Metric | Value |
|---|---:|
| sample_count | 15320 |
| duration_s | 30.639999999993897 |
| mpc_updates | 3066 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 12.023320420140049 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| fallback_active_time_s | 0.16199999999991022 |
| fallback_commanded_foot_descent_m | 0.0003711965559153596 |
| fallback_commanded_com_travel_m | 0.00015318419151735965 |
| fallback_active_plan_count | 24 |
| minimum_unsupported_remaining_time_s | 0.45420466797546855 |
| minimum_raw_model_remaining_time_s | 0.18099034979709777 |
| learned_prior_active_plan_count | 63 |
| learned_prior_active_plan_fraction | 0.7241379310344828 |
| missing_contact_planning_updates | 0 |
| recovery_planning_updates | 0 |
| minimum_raw_recovery_remaining_time_s | None |
| lowering_initial_measured_foot_bottom_m | 0.030120701914579384 |
| lowering_initial_measured_com_w | [-0.06686759488012525, -0.04708388796836721, 0.2578266871907798] |
| success | True |
| completion_time_s | 30.639999999993897 |
| lowering_to_touchdown_s | 2.909999999998387 |
| lowering_to_completion_s | 12.93599999999283 |
| first_target_touchdown_time_s | 20.613999999999454 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -1.0900000000016128 |
| observed_contact_timing | early |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.4509503763838847 |
| normal_impulse_first_100ms_ns | 0.13634406042318106 |
| maximum_roll_pitch_change_during_landing_deg | 0.5200160233205194 |
| maximum_com_reference_error_during_landing_m | 0.015085555223487432 |
| maximum_body_rotation_during_landing_deg | 0.917697357390728 |
| height_belief_final_error_m | 0.0002522927596645217 |
| height_belief_error_at_contact_confirmation_m | 0.0006214383183377791 |
| planner_update_count | 87 |
| planner_mean_compute_time_s | 0.008673930919469748 |
| planner_maximum_compute_time_s | 0.021422452000479097 |
| reference_projection_count | 0.0 |
| planner_fallback_count | 24.0 |
| learned_conditioning_updates | 47.0 |
| learned_duration_min_s | None |
| learned_duration_max_s | None |
| predictive_optimization_failures | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15320, "last_time_s": 30.639999999993897} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3066, "recorded_updates": 3066, "extra_support_change_updates": 2, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3066} |
| nlp_status | PASS | {"2": 2766} |
| selected_force_cap | PASS | 3.835499845837431e-11 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005511261045572493 |
| cycle_1_support_slip | PASS | 0.007417109670416241 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.23399999999911, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.2833462724362548, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 24.435999999997335, "minimum_normal_force_n_by_leg": {"FL": 11.718049528245759, "FR": 37.21287397911631, "RL": 40.13998043778266, "RR": 60.04093956909273}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.045321560992114, "FR": 34.20555897248554, "RL": 40.10955802278549, "RR": 41.182235955002085}} |
| pad_reference_limit_configuration | PASS | {"max_foot_speed_m_s": 0.015, "search_speed_m_s": 0.005, "max_com_speed_m_s": 0.008, "max_body_displacement_m": 0.012, "target_xy_tolerance_m": 0.005, "max_orientation_deviation_rad": 0.03490658503988659, "max_orientation_rate_rad_s": 0.02} |
| pad_finite_planner_signals | PASS | null |
| pad_commanded_foot_speed | PASS | {"maximum_m_s": 0.011646358269519732, "limit_m_s": 0.015} |
| pad_commanded_com_speed | PASS | {"maximum_m_s": 0.008000000000112287, "limit_m_s": 0.008} |
| pad_monotone_lowering | PASS | {"maximum_upward_speed_m_s": 0.0} |
| pad_commanded_body_displacement | PASS | {"maximum_m": 0.0012018405241576713, "limit_m": 0.012} |
| pad_commanded_target_xy | PASS | {"maximum_coordinate_error_m": 0.0010694791497675715, "limit_m": 0.005} |
| pad_commanded_orientation | PASS | {"maximum_deviation_rad": 0.0006049678682657787, "maximum_rate_rad_s": 0.003971301299402784} |
| pad_contact_reference_freeze | PASS | {"maximum_foot_speed_m_s": 0.0, "maximum_com_speed_m_s": 0.0} |
| pad_planner_update_cadence | PASS | {"frequency_hz": 20.0, "period_steps": 25, "missing_updates": 0, "unexpected_updates": 0} |
| pad_commanded_recovery_speed | PASS | {"checked_intervals": 0, "maximum_m_s": null, "limit_m_s": 0.005} |
| pad_adaptation_signals | PASS | [] |
| pad_adaptation_alignment | PASS | null |
| pad_positive_remaining_duration | PASS | {"planner_remaining_time_s": 0.45420466797546855, "optimized_remaining_time_s": 0.45420466797546855, "feasible_remaining_time_s": 0.45420466797546855, "model_remaining_time_s": 0.18099034979709777, "raw_model_remaining_time_s": 0.18099034979709777} |
| pad_current_state_replanning | PASS | null |
| pad_fallback_prior_exclusion | PASS | null |
| pad_prior_execution | PASS | true |
| pad_fallback_work_accounting | PASS | {"active_time_s": 0.16199999999991022, "foot_descent_m": 0.0003711965559153596, "com_travel_m": 0.00015318419151735965} |
| pad_noncontact_ablation_configuration | PASS | false |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": 0.0017943354656429593, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": 0.005848866824042377, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.72938041473641, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.045321560992114, "maximum_xy_target_error_m": 0.0026852448879946095, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00015113317595762295 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.23399999999911} |
| pad_target_reload_loading | PASS | 11.718049528245759 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 87, "maximum_fallback_count": 24.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
