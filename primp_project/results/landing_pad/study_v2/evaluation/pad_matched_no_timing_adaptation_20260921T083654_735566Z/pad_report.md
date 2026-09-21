# Adjustable landing pad — PASS

Planner: **matched_no_timing_adaptation**. Role: **evaluation**. Height condition: **lower**.

| Metric | Value |
|---|---:|
| sample_count | 16164 |
| duration_s | 32.327999999993544 |
| mpc_updates | 3234 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.989453437903107 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| fallback_active_time_s | 0.4019999999997772 |
| fallback_commanded_foot_descent_m | 0.0005035570180023496 |
| fallback_commanded_com_travel_m | 0.00022777709990535927 |
| fallback_active_plan_count | 37 |
| minimum_unsupported_remaining_time_s | 0.8053989513742609 |
| minimum_raw_model_remaining_time_s | 0.2962471102944678 |
| learned_prior_active_plan_count | 91 |
| learned_prior_active_plan_fraction | 0.7109375 |
| missing_contact_planning_updates | 24 |
| recovery_planning_updates | 62 |
| minimum_raw_recovery_remaining_time_s | 0.2962471102944678 |
| lowering_initial_measured_foot_bottom_m | 0.030165003966676436 |
| lowering_initial_measured_com_w | [-0.06750015063978843, -0.04761579852235616, 0.2585508634092852] |
| success | True |
| completion_time_s | 32.327999999993544 |
| lowering_to_touchdown_s | 4.459999999997528 |
| lowering_to_completion_s | 14.623999999992478 |
| first_target_touchdown_time_s | 22.163999999998595 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | 0.45999999999752816 |
| observed_contact_timing | late |
| missing_contact_observed | True |
| first_missing_contact_time_s | 21.00199999999924 |
| missing_contact_before_physical_touchdown | True |
| recovery_to_touchdown_s | 1.161999999999356 |
| peak_normal_force_first_100ms_n | 1.046197922163195 |
| normal_impulse_first_100ms_ns | 0.0923232597172145 |
| maximum_roll_pitch_change_during_landing_deg | 0.4714441317996478 |
| maximum_com_reference_error_during_landing_m | 0.015080572917778288 |
| maximum_body_rotation_during_landing_deg | 0.950887655838549 |
| height_belief_final_error_m | 0.0002574748829958151 |
| height_belief_error_at_contact_confirmation_m | 0.000637630924084376 |
| planner_update_count | 128 |
| planner_mean_compute_time_s | 0.008904287077982076 |
| planner_maximum_compute_time_s | 0.05225244699977338 |
| reference_projection_count | 0.0 |
| planner_fallback_count | 37.0 |
| learned_conditioning_updates | 112.0 |
| learned_duration_min_s | None |
| learned_duration_max_s | None |
| predictive_optimization_failures | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 16164, "last_time_s": 32.327999999993544} |
| control_alignment | PASS | 2.444225377651321e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3234, "recorded_updates": 3234, "extra_support_change_updates": 1, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3234} |
| nlp_status | PASS | {"2": 2934} |
| selected_force_cap | PASS | 2.502432928128431e-11 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005427570084065536 |
| cycle_1_support_slip | PASS | 0.007538991118200639 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 22.921999999998175, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.31578748303147, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 26.1239999999964, "minimum_normal_force_n_by_leg": {"FL": 11.6469981064135, "FR": 37.02309166447437, "RL": 40.19210130758366, "RR": 60.25595701337364}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.19440341597343, "FR": 34.169917125056564, "RL": 40.020436061578614, "RR": 41.124965773580406}} |
| pad_reference_limit_configuration | PASS | {"max_foot_speed_m_s": 0.015, "search_speed_m_s": 0.005, "max_com_speed_m_s": 0.008, "max_body_displacement_m": 0.012, "target_xy_tolerance_m": 0.005, "max_orientation_deviation_rad": 0.03490658503988659, "max_orientation_rate_rad_s": 0.02} |
| pad_finite_planner_signals | PASS | null |
| pad_commanded_foot_speed | PASS | {"maximum_m_s": 0.011825517582987593, "limit_m_s": 0.015} |
| pad_commanded_com_speed | PASS | {"maximum_m_s": 0.0015534673330270105, "limit_m_s": 0.008} |
| pad_monotone_lowering | PASS | {"maximum_upward_speed_m_s": 0.0} |
| pad_commanded_body_displacement | PASS | {"maximum_m": 0.0013488973184958009, "limit_m": 0.012} |
| pad_commanded_target_xy | PASS | {"maximum_coordinate_error_m": 0.0022069551533723253, "limit_m": 0.005} |
| pad_commanded_orientation | PASS | {"maximum_deviation_rad": 0.004245457382107811, "maximum_rate_rad_s": 0.0073401057616340115} |
| pad_contact_reference_freeze | PASS | {"maximum_foot_speed_m_s": 0.0, "maximum_com_speed_m_s": 0.0} |
| pad_planner_update_cadence | PASS | {"frequency_hz": 20.0, "period_steps": 25, "missing_updates": 0, "unexpected_updates": 0} |
| pad_commanded_recovery_speed | PASS | {"checked_intervals": 550, "maximum_m_s": 0.004260276060952058, "limit_m_s": 0.005} |
| pad_adaptation_signals | PASS | [] |
| pad_adaptation_alignment | PASS | null |
| pad_positive_remaining_duration | PASS | {"planner_remaining_time_s": 0.8053989513742609, "optimized_remaining_time_s": 0.8053989513742609, "feasible_remaining_time_s": 0.8053989513742609, "model_remaining_time_s": 0.2962471102944678, "raw_model_remaining_time_s": 0.2962471102944678} |
| pad_current_state_replanning | PASS | null |
| pad_fallback_prior_exclusion | PASS | null |
| pad_prior_execution | PASS | true |
| pad_fallback_work_accounting | PASS | {"active_time_s": 0.4019999999997772, "foot_descent_m": 0.0005035570180023496, "com_travel_m": 0.00022777709990535927} |
| pad_noncontact_ablation_configuration | PASS | false |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": -0.008815820179228443, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": -0.006155187787214043, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.844382860064854, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.19440341597343, "maximum_xy_target_error_m": 0.0027731072330687973, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.0001551877872140433 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 22.921999999998175} |
| pad_target_reload_loading | PASS | 11.6469981064135 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 128, "maximum_fallback_count": 37.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
