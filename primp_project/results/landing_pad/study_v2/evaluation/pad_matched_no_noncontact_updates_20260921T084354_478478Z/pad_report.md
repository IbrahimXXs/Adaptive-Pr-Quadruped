# Adjustable landing pad — PASS

Planner: **matched_no_noncontact_updates**. Role: **evaluation**. Height condition: **higher**.

| Metric | Value |
|---|---:|
| sample_count | 15234 |
| duration_s | 30.467999999993992 |
| mpc_updates | 3048 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 12.00514454247866 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| fallback_active_time_s | 0.15799999999991243 |
| fallback_commanded_foot_descent_m | 0.00034829714254460895 |
| fallback_commanded_com_travel_m | 0.00032786544779466104 |
| fallback_active_plan_count | 15 |
| minimum_unsupported_remaining_time_s | 0.7405278309202011 |
| minimum_raw_model_remaining_time_s | 0.16438304819955182 |
| learned_prior_active_plan_count | 60 |
| learned_prior_active_plan_fraction | 0.8 |
| missing_contact_planning_updates | 0 |
| recovery_planning_updates | 0 |
| minimum_raw_recovery_remaining_time_s | None |
| lowering_initial_measured_foot_bottom_m | 0.02947733749396559 |
| lowering_initial_measured_com_w | [-0.06705373234519525, -0.04732254047824126, 0.25823028514971236] |
| success | True |
| completion_time_s | 30.467999999993992 |
| lowering_to_touchdown_s | 2.911999999998386 |
| lowering_to_completion_s | 12.763999999992926 |
| first_target_touchdown_time_s | 20.615999999999453 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -1.088000000001614 |
| observed_contact_timing | early |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.6014880165796783 |
| normal_impulse_first_100ms_ns | 0.14704414976229635 |
| maximum_roll_pitch_change_during_landing_deg | 0.5233932393911652 |
| maximum_com_reference_error_during_landing_m | 0.01501269896153732 |
| maximum_body_rotation_during_landing_deg | 0.9343131040153093 |
| height_belief_final_error_m | 0.0002503457586710096 |
| height_belief_error_at_contact_confirmation_m | 0.0008339608512200475 |
| planner_update_count | 75 |
| planner_mean_compute_time_s | 0.00900042540008144 |
| planner_maximum_compute_time_s | 0.012257110000064131 |
| reference_projection_count | 0.0 |
| planner_fallback_count | 15.0 |
| learned_conditioning_updates | 42.0 |
| learned_duration_min_s | None |
| learned_duration_max_s | None |
| predictive_optimization_failures | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15234, "last_time_s": 30.467999999993992} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3048, "recorded_updates": 3048, "extra_support_change_updates": 1, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3048} |
| nlp_status | PASS | {"2": 2748} |
| selected_force_cap | PASS | 2.744747918473398e-11 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005823879441617856 |
| cycle_1_support_slip | PASS | 0.007444846557793335 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.061999999999205, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.3689334940587594, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 24.26399999999743, "minimum_normal_force_n_by_leg": {"FL": 11.664741136113555, "FR": 37.16195289051164, "RL": 40.194021439734115, "RR": 60.08912333842839}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.04342539273854, "FR": 34.22245062822743, "RL": 40.07629060226923, "RR": 41.18091848513165}} |
| pad_reference_limit_configuration | PASS | {"max_foot_speed_m_s": 0.015, "search_speed_m_s": 0.005, "max_com_speed_m_s": 0.008, "max_body_displacement_m": 0.012, "target_xy_tolerance_m": 0.005, "max_orientation_deviation_rad": 0.03490658503988659, "max_orientation_rate_rad_s": 0.02} |
| pad_finite_planner_signals | PASS | null |
| pad_commanded_foot_speed | PASS | {"maximum_m_s": 0.011510401518782212, "limit_m_s": 0.015} |
| pad_commanded_com_speed | PASS | {"maximum_m_s": 0.002768582015162225, "limit_m_s": 0.008} |
| pad_monotone_lowering | PASS | {"maximum_upward_speed_m_s": 0.0} |
| pad_commanded_body_displacement | PASS | {"maximum_m": 0.00023922558611906564, "limit_m": 0.012} |
| pad_commanded_target_xy | PASS | {"maximum_coordinate_error_m": 0.0010279341861046953, "limit_m": 0.005} |
| pad_commanded_orientation | PASS | {"maximum_deviation_rad": 0.0006003596663806817, "maximum_rate_rad_s": 0.0006489358344584749} |
| pad_contact_reference_freeze | PASS | {"maximum_foot_speed_m_s": 0.0, "maximum_com_speed_m_s": 0.0} |
| pad_planner_update_cadence | PASS | {"frequency_hz": 20.0, "period_steps": 25, "missing_updates": 0, "unexpected_updates": 0} |
| pad_commanded_recovery_speed | PASS | {"checked_intervals": 0, "maximum_m_s": null, "limit_m_s": 0.005} |
| pad_adaptation_signals | PASS | [] |
| pad_adaptation_alignment | PASS | null |
| pad_positive_remaining_duration | PASS | {"planner_remaining_time_s": 0.7405278309202011, "optimized_remaining_time_s": 0.7405278309202011, "feasible_remaining_time_s": 0.7405278309202011, "model_remaining_time_s": 0.16438304819955182, "raw_model_remaining_time_s": 0.16438304819955182} |
| pad_current_state_replanning | PASS | null |
| pad_fallback_prior_exclusion | PASS | null |
| pad_prior_execution | PASS | true |
| pad_fallback_work_accounting | PASS | {"active_time_s": 0.15799999999991243, "foot_descent_m": 0.00034829714254460895, "com_travel_m": 0.00032786544779466104} |
| pad_noncontact_ablation_configuration | PASS | true |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": 0.0015129487387073697, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": 0.00584877998359435, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.73207494445784, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.04342539273854, "maximum_xy_target_error_m": 0.002674835072677486, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00015122001640564993 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.061999999999205} |
| pad_target_reload_loading | PASS | 11.664741136113555 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 75, "maximum_fallback_count": 15.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
