# Adjustable landing pad — PASS

Planner: **matched_learned**. Role: **evaluation**. Height condition: **lower**.

| Metric | Value |
|---|---:|
| sample_count | 16292 |
| duration_s | 32.58399999999386 |
| mpc_updates | 3261 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.988255626585193 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| fallback_active_time_s | 0.349999999999806 |
| fallback_commanded_foot_descent_m | 0.00034854237197529114 |
| fallback_commanded_com_travel_m | 0.0001939248640433903 |
| fallback_active_plan_count | 31 |
| minimum_unsupported_remaining_time_s | 0.7826203824138782 |
| minimum_raw_model_remaining_time_s | 0.2891904630397396 |
| learned_prior_active_plan_count | 97 |
| learned_prior_active_plan_fraction | 0.7578125 |
| missing_contact_planning_updates | 23 |
| recovery_planning_updates | 57 |
| minimum_raw_recovery_remaining_time_s | 0.2891904630397396 |
| lowering_initial_measured_foot_bottom_m | 0.02947733749396559 |
| lowering_initial_measured_com_w | [-0.06705373234519525, -0.04732254047824126, 0.25823028514971236] |
| success | True |
| completion_time_s | 32.58399999999386 |
| lowering_to_touchdown_s | 4.6559999999974195 |
| lowering_to_completion_s | 14.87999999999279 |
| first_target_touchdown_time_s | 22.359999999998486 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | 0.6559999999974195 |
| observed_contact_timing | late |
| missing_contact_observed | True |
| first_missing_contact_time_s | 21.243999999999104 |
| missing_contact_before_physical_touchdown | True |
| recovery_to_touchdown_s | 1.1159999999993815 |
| peak_normal_force_first_100ms_n | 1.0118521372941913 |
| normal_impulse_first_100ms_ns | 0.09120195876058101 |
| maximum_roll_pitch_change_during_landing_deg | 0.4722213081203183 |
| maximum_com_reference_error_during_landing_m | 0.015077406877904223 |
| maximum_body_rotation_during_landing_deg | 0.9432138335756851 |
| height_belief_final_error_m | 0.0002558235506426596 |
| height_belief_error_at_contact_confirmation_m | 0.0007183282577870034 |
| planner_update_count | 128 |
| planner_mean_compute_time_s | 0.008688652890668891 |
| planner_maximum_compute_time_s | 0.01342962200033071 |
| reference_projection_count | 0.0 |
| planner_fallback_count | 31.0 |
| learned_conditioning_updates | 107.0 |
| learned_duration_min_s | None |
| learned_duration_max_s | None |
| predictive_optimization_failures | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 16292, "last_time_s": 32.58399999999386} |
| control_alignment | PASS | 2.444225377651321e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3261, "recorded_updates": 3261, "extra_support_change_updates": 2, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3261} |
| nlp_status | PASS | {"2": 2961} |
| selected_force_cap | PASS | 1.6741909134715845e-11 |
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
| cycle_1_support_slip | PASS | 0.0075551211645481665 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 23.177999999998033, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.3166584518414024, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 26.379999999996258, "minimum_normal_force_n_by_leg": {"FL": 11.622593287742616, "FR": 37.0342893208598, "RL": 40.18439105973603, "RR": 60.27746370120404}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.19195335892574, "FR": 34.177185113476426, "RL": 40.0120034385576, "RR": 41.12845856587582}} |
| pad_reference_limit_configuration | PASS | {"max_foot_speed_m_s": 0.015, "search_speed_m_s": 0.005, "max_com_speed_m_s": 0.008, "max_body_displacement_m": 0.012, "target_xy_tolerance_m": 0.005, "max_orientation_deviation_rad": 0.03490658503988659, "max_orientation_rate_rad_s": 0.02} |
| pad_finite_planner_signals | PASS | null |
| pad_commanded_foot_speed | PASS | {"maximum_m_s": 0.01151664163384948, "limit_m_s": 0.015} |
| pad_commanded_com_speed | PASS | {"maximum_m_s": 0.0013732458710462904, "limit_m_s": 0.008} |
| pad_monotone_lowering | PASS | {"maximum_upward_speed_m_s": 0.0} |
| pad_commanded_body_displacement | PASS | {"maximum_m": 0.0015203339628919177, "limit_m": 0.012} |
| pad_commanded_target_xy | PASS | {"maximum_coordinate_error_m": 0.0023325352460089044, "limit_m": 0.005} |
| pad_commanded_orientation | PASS | {"maximum_deviation_rad": 0.004446788789524742, "maximum_rate_rad_s": 0.007565752670906156} |
| pad_contact_reference_freeze | PASS | {"maximum_foot_speed_m_s": 0.0, "maximum_com_speed_m_s": 0.0} |
| pad_planner_update_cadence | PASS | {"frequency_hz": 20.0, "period_steps": 25, "missing_updates": 0, "unexpected_updates": 0} |
| pad_commanded_recovery_speed | PASS | {"checked_intervals": 575, "maximum_m_s": 0.00431980088833971, "limit_m_s": 0.005} |
| pad_adaptation_signals | PASS | [] |
| pad_adaptation_alignment | PASS | null |
| pad_positive_remaining_duration | PASS | {"planner_remaining_time_s": 0.7826203824138782, "optimized_remaining_time_s": 0.7826203824138782, "feasible_remaining_time_s": 0.7826203824138782, "model_remaining_time_s": 0.2891904630397396, "raw_model_remaining_time_s": 0.2891904630397396} |
| pad_current_state_replanning | PASS | null |
| pad_fallback_prior_exclusion | PASS | null |
| pad_prior_execution | PASS | true |
| pad_fallback_work_accounting | PASS | {"active_time_s": 0.349999999999806, "foot_descent_m": 0.00034854237197529114, "com_travel_m": 0.0001939248640433903} |
| pad_noncontact_ablation_configuration | PASS | false |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": -0.008879911436156308, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": -0.00615505023396614, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.840906852952145, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.19195335892574, "maximum_xy_target_error_m": 0.0027829859232564765, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.0001550502339661402 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 23.177999999998033} |
| pad_target_reload_loading | PASS | 11.622593287742616 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 128, "maximum_fallback_count": 31.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
