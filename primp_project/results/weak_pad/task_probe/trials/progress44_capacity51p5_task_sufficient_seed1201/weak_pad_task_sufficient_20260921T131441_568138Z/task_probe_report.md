# Task-load probing: RECOVERED_STOP

Policy: task_sufficient. Physical task completion: False.

V2 physical, certificate and recovery checks are unchanged. Pad damage and controlled recovery remain separate from completion.

| Check | Passed | Requirement |
| --- | --- | --- |
| finite_data | True | All recorded numeric evidence is finite |
| sensor_evidence_channels | True | Capacity-aware trials record aligned foot velocity as well as measured force/position |
| configuration | True | Declared experiment, timing, finite force reserves and bounded movement checks |
| completed_recording | True | Recording ends through the experiment's declared controlled completion/stop path |
| future_loading_coverage | True | Known movement/stop phases determine future loading coverage; a logged flag cannot hide an interval |
| sample_clock | True | Continuous physics timestamps and aligned control/measurement intervals |
| mpc_update_cadence | True | Every periodic/support-change solve occurs; extra solves must install a changed force cap |
| solver_success | True | MPC NLP status is 0 or the existing controller's accepted status 2; every QP status is zero |
| strength_truth_boundary | True | Hidden pad capacity occurs only in evaluator metadata |
| physical_failure_model | True | Latched failure and subsequent deformation follow actual overload dwell, not commanded loading |
| probe_observed | True | A probe phase is physically recorded |
| probe_tripod_support | False | The original three legs remain measured supports throughout probe ramp, dwell, release and any probe-posture change |
| actual_dwell_certificate | True | Every capacity certificate is bounded by sustained actual achieved loading and measured-force reserve, with original three supports stable |
| certificate_changes_logged | True | A valid certificate has strictly positive tested capacity |
| future_declared | False | A future plan or conservative stop is reached |
| future_valid_certificate | False | Every future loading interval has a valid measured-evidence certificate |
| future_certificate_no_growth | True | Monitoring during continuous future execution may invalidate but cannot increase a capacity certificate |
| planned_force_with_reserve | False | Every planned/installed MPC load respects certificate minus declared tracking reserve |
| actual_future_loading | False | Actual future target loading stays below tested capacity throughout, independently of the MPC cap |
| pad_survives | False | No weak-pad failure occurs |
| body_stable | True | Measured roll and pitch stay within the declared stability limit |
| certificate_site_guard | True | A valid future certificate retains sensed contact within the declared uniform 10 mm horizontal / 2.5 mm vertical test region |
| meaningful_progress | False | Measured CoM advances >=30 mm while another foot is actually >=20 mm airborne for >=1 s, with three other measured supports |
| airborne_contact_schedule | True | A physically lifted foot is not still scheduled as a support |
| terminal_support | False | Every planned support remains physically loaded throughout the final half-second, with at least three stable supports |
| conservative_stop | False | An infeasible untested movement causes a sustained safe stop on the original three legs without claiming task completion |
| requested_force_is_not_achieved | True | At least 1 N of requested probe loading remains unachieved and cannot be certified |
| collapse_after_light_touch | False | Confirmed light contact is followed by actual weight-transfer overload and >=2 mm physical pad collapse; the unaware baseline intentionally has no capacity probe |
| configuration_v2 | True | V2 declares one recognized strategy and the selected FL target |
| recovery_state_coverage | True | Recovery is one contiguous unload→lift→hold sequence through termination; a changed phase label cannot hide a support-loss interval |
| supported_sensor_configuration | True | Declared sensing uses bounded force noise, at most 0.2 mm componentwise position noise and zero delay |
| sensor_reserve_covers_declared_error | True | Measurement reserve covers the entire declared bounded force error |
| realized_sensor_error_bounds | True | Every recorded post-reset observation respects the declared bounded force/position errors and ideal contact channel |
| aligned_sensor_clock | True | V2 observations are synchronous with each control input; no unaccounted delayed samples |
| continuous_certificate_monitor | True | Every post-certificate tick checks contact/site validity, with irreversible invalidation until a fresh complete probe |
| certificate_evidence_sound | True | Any issued certificate has a complete independently verified physical evidence window, even if the trial later recovers |
| certificate_revision_finite | True | Certificate revision identifiers are nonnegative integers |
| probe_and_recovery_tripod | True | Original three supports remain measured and loaded through every probe and recovery transition |
| no_future_execution_after_failure | True | A failed pad never authorizes further weight-transfer movement |
| future_certified_or_unloaded | True | Every movement/stop interval respects certified actual and commanded loads, or leaves an uncertified target unloaded and unscheduled |
| recovery_commands_unloaded | True | Throughout recovery lift and hold the target is unscheduled, its installed force cap is zero, and its commanded support force is negligible |
| recovery_configuration | True | Recovery declares at least 20 mm lift, at least 2 s stable hold, and a bounded unload deadline |
| controlled_probe_failure_recovery | True | Failure occurs during a probe, followed by controlled FL unloading/lift and at least 2 s of terminal original-tripod support; no task completion claim |
| terminal_safe_stop | False | An intentional stop maintains the original tripod; any uncertified target is physically unloaded |
| task_probe_identity | True | The selected probe policy retains the frozen adaptive_probe controller and shared movement optimizer |
| probe_target_telemetry | True | Record minimum task load, sufficient test target, tolerance and selected probe target |
| reserve_and_sensor_configuration_consistent | True | The frozen 1 N sensing and 8 N tracking reserves match public parameters, metadata and every control tick; command sensing allowance equals declared bounded sensor error |
| pad_displacement_channels_agree | True | Reported target-pad displacement equals the deformation trace audited by the unchanged physical failure validator |
| finite_probe_target_telemetry | True | All per-tick target telemetry has finite values and exactly matches the control clock |
| sufficient_target_preserves_reserves | True | Sufficient target equals the shared minimum future load plus unchanged sensing/tracking reserves and positive numerical tolerance |
| selected_target_matches_executed_command | True | Every additional test actually selects its recorded target amplitude; logging a gentler target while commanding more is invalid |
| selected_target_matches_planner_decision | True | Additional-probe index, minimum future load, request and selected amplitude match the logged planner decision |
| task_minimum_recomputed_from_geometry | True | The task load lower bound is recomputed from initial probing geometry and the unchanged shared movement constraints |
| probe_mpc_bounds_match_target | True | Additional-test MPC caps retain the frozen target + 0.2 N bound, and force commands obey the installed cap and declared solver tolerance |
| minimum_policy_targets_sufficient_load | True | Every additional minimum-policy probe declares its task-derived target |
| minimum_policy_does_not_select_maximum | True | The selected command is the measured sufficient target plus declared sensing error and probe undershoot allowance, not the achievable maximum |
