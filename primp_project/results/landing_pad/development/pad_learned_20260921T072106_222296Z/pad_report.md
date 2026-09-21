# Adjustable landing pad — PASS

Planner: **learned**. Role: **development**. Height condition: **higher**.

| Metric | Value |
|---|---:|
| sample_count | 15700 |
| duration_s | 31.399999999993476 |
| mpc_updates | 3142 |
| maximum_abs_roll_pitch_deg | 0.5480502023497626 |
| maximum_abs_actuator_torque_nm | 11.978659985570133 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | True |
| completion_time_s | 31.399999999993476 |
| lowering_to_touchdown_s | 3.3859999999981234 |
| lowering_to_completion_s | 13.69599999999241 |
| first_target_touchdown_time_s | 21.08999999999919 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -0.6140000000018766 |
| observed_contact_timing | early |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.1792965916005986 |
| normal_impulse_first_100ms_ns | 0.10634006444967636 |
| maximum_roll_pitch_change_during_landing_deg | 0.5142677846334018 |
| maximum_com_reference_error_during_landing_m | 0.015182301931818501 |
| maximum_body_rotation_during_landing_deg | 0.9596890609870049 |
| height_belief_final_error_m | 0.00028826909538259664 |
| height_belief_error_at_contact_confirmation_m | 0.0007583067585899082 |
| planner_update_count | 86 |
| planner_mean_compute_time_s | 0.0004650037441489647 |
| planner_maximum_compute_time_s | 0.0007930850006232504 |
| reference_projection_count | 15.0 |
| planner_fallback_count | 5.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15700, "last_time_s": 31.399999999993476} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3142, "recorded_updates": 3142, "extra_support_change_updates": 2, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3142} |
| nlp_status | PASS | {"2": 2842} |
| selected_force_cap | PASS | 1.0256432603830506e-11 |
| body_tilt | PASS | 0.5480502023497626 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005743553135885866 |
| cycle_1_support_slip | PASS | 0.007417109670416241 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.99399999999869, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0033056771931466, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 25.195999999996914, "minimum_normal_force_n_by_leg": {"FL": 11.633331448058772, "FR": 37.36038701398685, "RL": 39.95800502273673, "RR": 60.156991844980624}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.06246768378744, "FR": 34.18695091716512, "RL": 40.19873088137254, "RR": 41.11609532189993}} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": 0.0055009801831134054, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": 0.009847461601877307, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.769644831256485, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.06246768378744, "maximum_xy_target_error_m": 0.00277340609604847, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00015253839812269347 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.99399999999869} |
| pad_target_reload_loading | PASS | 11.633331448058772 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 86, "maximum_fallback_count": 5.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
