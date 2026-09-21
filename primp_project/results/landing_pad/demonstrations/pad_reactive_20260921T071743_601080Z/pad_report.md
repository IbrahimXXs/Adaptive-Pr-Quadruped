# Adjustable landing pad — PASS

Planner: **reactive**. Role: **demonstration**. Height condition: **approximately_correct**.

| Metric | Value |
|---|---:|
| sample_count | 15649 |
| duration_s | 31.297999999993532 |
| mpc_updates | 3131 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.952389095429133 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | True |
| completion_time_s | 31.297999999993532 |
| lowering_to_touchdown_s | 3.8259999999978795 |
| lowering_to_completion_s | 13.593999999992466 |
| first_target_touchdown_time_s | 21.529999999998946 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -0.17400000000212046 |
| observed_contact_timing | approximately_planned |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.3473487158973243 |
| normal_impulse_first_100ms_ns | 0.12236405487353907 |
| maximum_roll_pitch_change_during_landing_deg | 0.5195626623921437 |
| maximum_com_reference_error_during_landing_m | 0.015189107454613188 |
| maximum_body_rotation_during_landing_deg | 1.0380529070378717 |
| height_belief_final_error_m | 0.00024115680830111633 |
| height_belief_error_at_contact_confirmation_m | 0.0006392148192867677 |
| planner_update_count | 83 |
| planner_mean_compute_time_s | 0.0001412071085570756 |
| planner_maximum_compute_time_s | 0.00016653499915264547 |
| reference_projection_count | 11.0 |
| planner_fallback_count | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15649, "last_time_s": 31.297999999993532} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3131, "recorded_updates": 3131, "extra_support_change_updates": 1, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3131} |
| nlp_status | PASS | {"2": 2831} |
| selected_force_cap | PASS | 3.5873747935059155e-11 |
| body_tilt | PASS | 0.43570502247900955 |
| cycle_1_phase_order | PASS | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_1_hold_duration | PASS | 5.0 |
| cycle_1_hold_contact | PASS | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | 0 |
| cycle_1_hold_clearance | PASS | 0.030134376927601916 |
| cycle_1_support_margin | PASS | {"independent_minimum_m": 0.06959821637692096, "logged_minimum_m": 0.06959821637692096} |
| cycle_1_fixed_lift_reference | PASS | true |
| cycle_1_foot_tracking | PASS | 0.005870536837413612 |
| cycle_1_support_slip | PASS | 0.007417109670416241 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.891999999998745, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0214917727326887, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 25.09399999999697, "minimum_normal_force_n_by_leg": {"FL": 11.806349503271338, "FR": 37.328600084236534, "RL": 40.059712712372985, "RR": 59.91273618333748}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 31.966439639072142, "FR": 34.184374836932534, "RL": 40.22813211897045, "RR": 41.213519410596014}} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": 0.00552625255832552, "minimum_allowed_bottom_m": -0.014} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": 0.009851458797123742, "minimum_allowed_bottom_m": -0.03} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.655911962755255, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 31.966439639072142, "maximum_xy_target_error_m": 0.0023881536170793772, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00014854120287625776 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.891999999998745} |
| pad_target_reload_loading | PASS | 11.806349503271338 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 83, "maximum_fallback_count": 0.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.75 s.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
