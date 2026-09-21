# Adjustable landing pad — PASS

Planner: **learned**. Role: **development**. Height condition: **higher**.

| Metric | Value |
|---|---:|
| sample_count | 15314 |
| duration_s | 30.627999999993904 |
| mpc_updates | 3064 |
| maximum_abs_roll_pitch_deg | 0.43570502247900955 |
| maximum_abs_actuator_torque_nm | 11.991575281765618 |
| final_complete_duration_s | 2.004 |
| maximum_logged_vs_independent_margin_difference_m | 0.0 |
| success | True |
| completion_time_s | 30.627999999993904 |
| lowering_to_touchdown_s | 3.0559999999983063 |
| lowering_to_completion_s | 12.923999999992837 |
| first_target_touchdown_time_s | 20.759999999999373 |
| nominal_touchdown_deadline_s | 21.704000000001066 |
| touchdown_minus_nominal_deadline_s | -0.9440000000016937 |
| observed_contact_timing | early |
| missing_contact_observed | False |
| first_missing_contact_time_s | None |
| missing_contact_before_physical_touchdown | False |
| recovery_to_touchdown_s | 0.0 |
| peak_normal_force_first_100ms_n | 1.4246945533827398 |
| normal_impulse_first_100ms_ns | 0.13510525966337697 |
| maximum_roll_pitch_change_during_landing_deg | 0.5366723614691494 |
| maximum_com_reference_error_during_landing_m | 0.015027134142779274 |
| maximum_body_rotation_during_landing_deg | 1.0371429363730655 |
| height_belief_final_error_m | 0.00024861062966993926 |
| height_belief_error_at_contact_confirmation_m | 0.0006908365204920143 |
| planner_update_count | 80 |
| planner_mean_compute_time_s | 0.00045705958743837984 |
| planner_maximum_compute_time_s | 0.0007275349998963065 |
| reference_projection_count | 17.0 |
| planner_fallback_count | 8.0 |
| learned_conditioning_updates | 4.0 |
| learned_duration_min_s | 2.1511958014702057 |
| learned_duration_max_s | 4.104066037928759 |
| predictive_optimization_failures | 0.0 |

| Check | Result | Observed |
|---|---|---|
| completed | PASS | {"status": "completed", "completed_cycles": 1} |
| cycle_labels | PASS | [1] |
| sample_clock | PASS | {"rows": 15314, "last_time_s": 30.627999999993904} |
| control_alignment | PASS | 1.1084883011491797e-15 |
| mpc_update_cadence | PASS | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 3064, "recorded_updates": 3064, "extra_support_change_updates": 1, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | [] |
| no_termination | PASS | 0 |
| no_numerical_warnings | PASS | 0.0 |
| no_torque_saturation | PASS | 0 |
| qp_success | PASS | {"0": 3064} |
| nlp_status | PASS | {"2": 2764} |
| selected_force_cap | PASS | 4.6139545059103655e-11 |
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
| cycle_1_support_slip | PASS | 0.007417109670416241 |
| cycle_1_lift_entry_guard | PASS | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07142988585428, "physical_support_margin_m": 0.06906348433927874, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | {"time_s": 21.221999999999117, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.006944029596781, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | {"reload_dwell_s": 0.2, "first_recenter_time_s": 24.423999999997342, "minimum_normal_force_n_by_leg": {"FL": 11.813501504127673, "FR": 37.27174459995972, "RL": 40.06189415131482, "RR": 59.96250462913148}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | 2.004 |
| final_four_foot_loading | PASS | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 32.07378082117061, "FR": 34.20065187411889, "RL": 40.14281188074963, "RR": 41.129688574013514}} |
| pad_configuration | PASS | {"experiment": "landing_pad", "cycles": 1, "max_search_depth_m": 0.02, "contact_compression_m": 0.004} |
| pad_fixed_support_surfaces | PASS | [0.0, 0.0, 0.0, 0.0] |
| pad_truth_separation_schema | PASS | [] |
| pad_bounded_descent | PASS | {"minimum_commanded_bottom_m": 0.0060393675282356535, "minimum_allowed_bottom_m": -0.024} |
| pad_physical_reach | PASS | {"minimum_actual_bottom_m": 0.009847403287572824, "minimum_allowed_bottom_m": -0.04} |
| pad_foot_bottom_consistency | PASS | 0.0 |
| pad_target_force_consistency | PASS | {"maximum_target_force_n": 32.77136946310154, "maximum_target_minus_total_normal_n": 0.0} |
| pad_final_target_loading | PASS | {"minimum_normal_force_n": 32.07378082117061, "maximum_xy_target_error_m": 0.002865520462804291, "missing_target_contact_samples": 0} |
| pad_final_height_consistency | PASS | 0.00015259671242717592 |
| pad_target_contact_before_reload | PASS | {"required_samples": 49, "first_reload_time_s": 21.221999999999117} |
| pad_target_reload_loading | PASS | 11.813501504127673 |
| pad_belief_bounds | PASS | null |
| pad_sensor_causality | PASS | {"maximum_future_lead_s": 0.0} |
| pad_planner_execution | PASS | {"updates": 80, "maximum_fallback_count": 8.0} |

- **impact:** Simulated target-pad normal reaction over exactly 100 ms after first physical target contact; impulse is the rectangle-rule integral, including static load.
- **body_disturbance:** Roll/pitch change from lowering entry and CoM tracking error are reported separately from intentionally commanded body motion.
- **timing:** Physical contact time uses post-step evaluation contacts. Nominal deadline is lowering entry plus requested nominal duration; approximately planned means within 0.25 s. This descriptive label is not an acceptance criterion.
- **height_truth:** Actual height is used only by the simulator and this evaluator. Schema checks do not prove absence of arbitrary numeric information leaks; planner API tests and code review complement them.
- **completion:** All inherited controlled-step criteria and additional pad checks must pass. No relative planner superiority is assumed.

![Landing-pad evidence](pad_overview.png)

Full requirements and metrics: `pad_summary.json`. Core execution checks: `step_report.md`. Measurements: `signals.npz`; simulator-only truth: `metadata.json` → `evaluation`.
