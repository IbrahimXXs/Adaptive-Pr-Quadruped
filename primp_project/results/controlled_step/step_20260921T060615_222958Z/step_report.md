# Controlled FL foot step — PASS

Completed 3 of 3 requested cycles. Each commanded lift is 30 mm with a 10 s hold. Recorded 108.058 s at 0.002 s per interval.

Predeclared engineering limits for this controlled flat-ground simulation; not a stability proof.

| Check | Result | Requirement | Observed |
|---|---|---|---|
| completed | PASS | Completed status and exactly 3 completed cycles | {"status": "completed", "completed_cycles": 3} |
| cycle_labels | PASS | Every requested cycle appears in chronological order | [1, 2, 3] |
| sample_clock | PASS | Continuous end-of-interval sampling with no reset or time gap | {"rows": 54029, "last_time_s": 108.05799999992956} |
| control_alignment | PASS | Control timestamp equals interval endpoint minus dt | 4.661201979949681e-15 |
| mpc_update_cadence | PASS | MPC updates match the configured fixed-step cadence, initialization, and immediate support changes; no missing or unexplained solves | {"configured_frequency_hz": 100.0, "effective_periodic_frequency_hz": 100.0, "period_in_physics_steps": 5, "step_sequence_valid": true, "expected_updates": 10811, "recorded_updates": 10811, "extra_support_change_updates": 5, "missing_periodic_updates": 0, "missing_support_change_updates": 0, "unexpected_updates": 0} |
| finite_data | PASS | All recorded numerical signals finite | [] |
| no_termination | PASS | No termination or truncation | 0 |
| no_numerical_warnings | PASS | No MuJoCo numerical warnings | 0.0 |
| no_torque_saturation | PASS | No actuator command clipping | 0 |
| qp_success | PASS | Every MPC update has QP status 0 | {"0": 10811} |
| nlp_status | PASS | Post-settling MPC NLP status is 0 or 2 | {"2": 10511} |
| selected_force_cap | PASS | Desired selected-foot vertical force <= configured cap + 1 N at MPC updates | -0.0 |
| body_tilt | PASS | Maximum absolute roll or pitch < 8 degrees | 0.43726459673731705 |
| cycle_1_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter"] |
| cycle_1_hold_duration | PASS | Continuous hold >= 10 s with at most one sample of boundary tolerance | 10.0 |
| cycle_1_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_1_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_1_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.027011799850446203 |
| cycle_1_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06993833766220879, "logged_minimum_m": 0.06993833766220879} |
| cycle_1_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_1_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.00497965702083962 |
| cycle_1_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007319944126366913 |
| cycle_1_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 10.504000000000177, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.03243793220335, "physical_support_margin_m": 0.06899985575956571, "selected_force_cap_n": 0.0} |
| cycle_1_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_1_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 27.94399999999539, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999994458, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.018821933937694, "independent_debounce_passed": true} |
| cycle_1_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 31.145999999993617, "minimum_normal_force_n_by_leg": {"FL": 14.499220971113289, "FR": 37.144629129406006, "RL": 37.463901212952514, "RR": 60.007522199564335}, "missing_measured_or_planned_contacts": 0} |
| cycle_2_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter"] |
| cycle_2_hold_duration | PASS | Continuous hold >= 10 s with at most one sample of boundary tolerance | 10.0 |
| cycle_2_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_2_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_2_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_2_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.027031764344100262 |
| cycle_2_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06999130646126539, "logged_minimum_m": 0.06999130646126539} |
| cycle_2_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_2_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.00498636237665726 |
| cycle_2_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007245697058014407 |
| cycle_2_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 45.84400000001006, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.05780987379282, "physical_support_margin_m": 0.069034957472622, "selected_force_cap_n": 0.0} |
| cycle_2_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.1, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_2_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 63.28800000003138, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.10000000000012221, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.009579832266478, "independent_debounce_passed": true} |
| cycle_2_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 66.49000000002644, "minimum_normal_force_n_by_leg": {"FL": 14.263941958814188, "FR": 37.25377613021364, "RL": 37.53754689999559, "RR": 60.059404430503015}, "missing_measured_or_planned_contacts": 0} |
| cycle_3_phase_order | PASS | All stages occur once in stand→shift→unload→lift→hold→lower→confirm→reload→recenter order | ["stand", "shift", "unload", "lift", "hold", "lower", "confirm", "reload", "recenter", "complete"] |
| cycle_3_hold_duration | PASS | Continuous hold >= 10 s with at most one sample of boundary tolerance | 10.0 |
| cycle_3_hold_contact | PASS | Selected foot has neither contact nor planned support; other three have both for every hold sample | {"selected_measured_samples": 0, "selected_planned_samples": 0, "missing_support_measured_samples": 0, "missing_support_planned_samples": 0} |
| cycle_3_swing_schedule | PASS | Selected planned support remains off and the other three remain on throughout lift/hold/lower/confirm | {"selected_planned_samples": 0, "missing_support_planned_samples": 0} |
| cycle_3_support_contact_continuity | PASS | All three support feet retain measured contact throughout unload/lift/hold/lower/confirm/reload | 0 |
| cycle_3_hold_clearance | PASS | Selected foot remains >= 20 mm above its fixed pre-lift center height throughout hold | 0.02705617855951499 |
| cycle_3_support_margin | PASS | Physical CoM projection has >= 10 mm margin inside measured three-foot support triangle during hold | {"independent_minimum_m": 0.06997436191118078, "logged_minimum_m": 0.06997436191118078} |
| cycle_3_fixed_lift_reference | PASS | Immutable lift anchor and constant hold target 0.03 m above it, with zero desired velocity/acceleration | true |
| cycle_3_foot_tracking | PASS | Selected-foot 3D error < 12 mm during lift, hold, lower and confirm | 0.004984163976945179 |
| cycle_3_support_slip | PASS | All three support feet stay within 10 mm of their fixed positions at shift entry | 0.007256530327101321 |
| cycle_3_lift_entry_guard | PASS | Last unload sample before lift: selected normal < 3 N, each support > 5 N, physical margin >= 20 mm, selected cap <= 0.1 N | {"last_unload_time_s": 81.19599999999217, "selected_normal_force_n": 0.0, "minimum_support_normal_force_n": 45.04226556934135, "physical_support_margin_m": 0.06900946581704917, "selected_force_cap_n": 0.0} |
| cycle_3_force_cap_ramps | PASS | Unload and reload each last >= 3 s; held MPC force cap decreases monotonically on unload and increases on reload | {"unload_duration_s": 3.102, "reload_duration_s": 3.202, "maximum_unload_cap_increase_n": 0.0, "maximum_reload_cap_decrease_n": -0.0} |
| cycle_3_reload_gate | PASS | Reload follows confirm and recorded dwell >= 0.1 s; preceding contacts independently active at >= 2 N for that debounce minus at most one boundary sample | {"time_s": 98.65199999995149, "contact_confirmed": true, "measured_contact": true, "dwell_s": 0.09999999999976694, "independent_debounce_samples": 49, "independent_debounce_duration_s": 0.098, "independent_debounce_min_normal_force_n": 2.0156206082205728, "independent_debounce_passed": true} |
| cycle_3_reload_loading | PASS | All four feet have measured/planned contact and normal force > 5 N for the last 0.2 s of reload and first recenter sample | {"reload_dwell_s": 0.2, "first_recenter_time_s": 101.85399999994402, "minimum_normal_force_n_by_leg": {"FL": 14.065876376822803, "FR": 37.360223361028964, "RL": 37.607850045468, "RR": 60.080668814580896}, "missing_measured_or_planned_contacts": 0} |
| final_four_foot_stance | PASS | Final complete phase lasts >= 1 s with all four feet in measured and planned contact | 2.004 |
| final_four_foot_loading | PASS | Every foot remains loaded above 5 N throughout the final complete phase (at least 1 s), with measured and planned contact | {"duration_s": 2.004, "minimum_normal_force_n_by_leg": {"FL": 35.55974198766451, "FR": 37.504235830837295, "RL": 36.15373245626761, "RR": 38.40582353334699}} |

| Cycle | Hold (s) | Min clearance (mm) | Min support margin (mm) | Max hold error (mm) | Max support drift (mm) |
|---|---:|---:|---:|---:|---:|
| 1 | 10.000 | 27.012 | 69.938 | 3.359 | 7.320 |
| 2 | 10.000 | 27.032 | 69.991 | 3.358 | 7.246 |
| 3 | 10.000 | 27.056 | 69.974 | 3.353 | 7.257 |

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
