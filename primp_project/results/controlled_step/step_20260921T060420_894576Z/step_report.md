# Controlled FL foot step — PASS

Completed 3 of 3 requested cycles. Each commanded lift is 30 mm with a 6 s hold. Recorded 96.064 s at 0.002 s per interval.

Predeclared engineering limits for this controlled flat-ground simulation; not a stability proof.

| Check | Result | Requirement | Observed |
|---|---|---|---|
| completed | PASS | Completed status and exactly 3 completed cycles | {"status": "completed", "completed_cycles": 3} |
| cycle_labels | PASS | Every requested cycle appears in chronological order | [1, 2, 3] |
| sample_clock | PASS | Continuous end-of-interval sampling with no reset or time gap | {"rows": 48032, "last_time_s": 96.06399999995752} |
| control_alignment | PASS | Control timestamp equals interval endpoint minus dt | 4.661201979949681e-15 |
| mpc_update_cadence | PASS | MPC updates match the configured fixed-step cadence, initialization, and immediate support changes; no missing or unexplained solves | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 9612, "recorded_updates": 9612, "extra_support_change_updates": 5, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | All recorded numerical signals finite | [] |
| no_termination | PASS | No termination or truncation | 0 |
| no_numerical_warnings | PASS | No MuJoCo numerical warnings | 0.0 |
| no_torque_saturation | PASS | No actuator command clipping | 0 |
| qp_success | PASS | Every MPC update has QP status 0 | {"0": 9612} |
| nlp_status | PASS | Post-settling MPC NLP status is 0 or 2 | {"2": 9312} |
| selected_force_cap | PASS | Desired selected-foot vertical force <= configured cap + 1 N at MPC updates | -0.0 |
| body_tilt | PASS | Maximum absolute roll or pitch < 8 degrees | 0.43570502247899173 |
| cycle_1_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter"] |
| cycle_1_hold_duration | PASS | Continuous hold >= 6 s with at most one sample of boundary tolerance | 6.0 |
| cycle_1_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_1_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.02700854672413193 |
| cycle_1_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06994197732410058, "logged_minimum_m": 0.06994197732410058} |
| cycle_1_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_1_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.004985735215494025 |
| cycle_1_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007316698490805778 |
| cycle_1_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.071429885855316, "physical_support_margin_m": 0.06906348433927881, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 23.945999999997607, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0130787428228207, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 27.147999999995832, "minimum_normal_force_n_by_leg": {"FL": 14.501490881881255, "FR": 37.14989029289026, "RL": 37.46094524930647, "RR": 60.00266236449143}, "missing_measured_or_planned_contacts": 0} |
| cycle_2_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter"] |
| cycle_2_hold_duration | PASS | Continuous hold >= 6 s with at most one sample of boundary tolerance | 6.0 |
| cycle_2_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_2_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_2_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_2_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.027028369447133646 |
| cycle_2_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06999570871154674, "logged_minimum_m": 0.06999570871154674} |
| cycle_2_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_2_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.004993454214993358 |
| cycle_2_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007243810920246616 |
| cycle_2_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 41.84800000000518, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.09140275503288, "physical_support_margin_m": 0.06909540564430118, "selected_force_cap_n": 0.0} |
| cycle_2_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.1, "reload_duration_s": 3.2, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_2_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 55.296000000021614, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.10000000000012221, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0125553214100353, "independent_debounce_passed": true} |
| cycle_2_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 58.496000000025525, "minimum_normal_force_n_by_leg": {"FL": 14.267009203074274, "FR": 37.259686194204576, "RL": 37.53361706485126, "RR": 60.05429254750891}, "missing_measured_or_planned_contacts": 0} |
| cycle_3_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_3_hold_duration | PASS | Continuous hold >= 6 s with at most one sample of boundary tolerance | 6.0 |
| cycle_3_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_3_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_3_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_3_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.02705248806342482 |
| cycle_3_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06998110282726806, "logged_minimum_m": 0.06998110282726806} |
| cycle_3_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_3_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.004988880668642828 |
| cycle_3_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007254619596012194 |
| cycle_3_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 73.2000000000108, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.07387134048878, "physical_support_margin_m": 0.06906844650605415, "selected_force_cap_n": 0.0} |
| cycle_3_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.102, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_3_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 86.65799999997944, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999976694, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0094602904710297, "independent_debounce_passed": true} |
| cycle_3_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 89.85999999997198, "minimum_normal_force_n_by_leg": {"FL": 14.068328966749748, "FR": 37.36692737390988, "RL": 37.60219998679417, "RR": 60.076601812467565}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | Final complete phase lasts >= 1 s with all four feet in measured and planned contact | 2.004 |
| final_four_foot_loading | PASS | Every foot remains loaded above 5 N throughout the final complete phase (at least 1 s), with measured and planned contact | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 35.54421823658176, "FR": 37.50974991695896, "RL": 36.17022253131601, "RR": 38.40301806436808}} |

| Cycle | Hold (s) | Min clearance (mm) | Min support margin (mm) | Max hold error (mm) | Max support drift (mm) |
|---|---:|---:|---:|---:|---:|
| 1 | 6.000 | 27.009 | 69.942 | 3.362 | 7.317 |
| 2 | 6.000 | 27.028 | 69.996 | 3.360 | 7.244 |
| 3 | 6.000 | 27.052 | 69.981 | 3.356 | 7.255 |

Phase durations and landing-force peaks for every cycle are in `step_summary.json`. Fixed anchors and the physical CoM support triangle provide evidence independent of the requested foot trajectory.

- **phase duration:** Sample count × dt; row labels describe the preceding control interval.
- **clearance:** Selected foot geometry-center height above recorded fixed pre-lift center; not absolute floor distance.
- **support margin:** Independently recomputed from physical CoM and the other three measured foot centers in world XY.
- **support displacement:** Foot geometry-center displacement from fixed per-cycle shift anchors includes rolling and contact compliance; it is not a measurement of pure tangential slip.
- **landing debounce:** Pre-reload sampled selected-foot contacts must remain active with normal force >= 2 N; one boundary sample is allowed for control-start versus observation-end alignment.
- **restored loading:** Each foot must exceed 5 N over the last 0.2 s of reload plus the first recenter sample, and throughout final standing; contact flags alone do not establish loading.
- **mpc cadence:** Periodic interval is round(1/(configured frequency × physics dt)), matching the controller. Initialization and support changes force solves; a support-change solve does not reset the periodic grid.
- **force cap:** Bounds the MPC desired vertical force at MPC updates, not the measured contact reaction.
- **force ramp duration:** The 3 s minimum for unload/reload is a declared check of this milestone's fixed controller schedule, not a universal dynamics requirement.
- **landing impact:** Peak simulated normal contact reaction in first 100 ms after contact; not a hardware impact measurement.
- **nlp status:** Status 2 denotes the configured SQP iteration limit; underlying QP status must remain zero.

![Controlled step overview](step_overview.png)

Raw observations: `signals.npz`. Configuration/provenance: `metadata.json`.
