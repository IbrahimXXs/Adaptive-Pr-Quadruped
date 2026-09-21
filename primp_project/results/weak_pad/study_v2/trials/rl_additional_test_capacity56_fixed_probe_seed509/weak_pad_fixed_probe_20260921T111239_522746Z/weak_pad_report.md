# Weak-pad V2: SAFE_STOP

Strategy: fixed_probe. Physical task success: False.

A controlled recovery and a safe stop are separate from task completion.

| Check | Result | Requirement |
| --- | --- | --- |
| finite_data | pass | All recorded numeric evidence is finite |
| sensor_evidence_channels | pass | Capacity-aware trials record aligned foot velocity as well as measured force/position |
| configuration | pass | Declared experiment, timing, finite force reserves and bounded movement checks |
| completed_recording | pass | Recording ends through the experiment's declared controlled completion/stop path |
| future_loading_coverage | pass | Known movement/stop phases determine future loading coverage; a logged flag cannot hide an interval |
| sample_clock | pass | Continuous physics timestamps and aligned control/measurement intervals |
| mpc_update_cadence | pass | Every periodic/support-change solve occurs; extra solves must install a changed force cap |
| solver_success | pass | MPC NLP status is 0 or the existing controller's accepted status 2; every QP status is zero |
| strength_truth_boundary | pass | Hidden pad capacity occurs only in evaluator metadata |
| physical_failure_model | pass | Latched failure and subsequent deformation follow actual overload dwell, not commanded loading |
| probe_observed | pass | A probe phase is physically recorded |
| probe_tripod_support | pass | The original three legs remain measured supports throughout probe ramp, dwell, release and any probe-posture change |
| actual_dwell_certificate | pass | Every capacity certificate is bounded by sustained actual achieved loading and measured-force reserve, with original three supports stable |
| certificate_changes_logged | pass | A valid certificate has strictly positive tested capacity |
| future_declared | pass | A future plan or conservative stop is reached |
| future_valid_certificate | pass | Every future loading interval has a valid measured-evidence certificate |
| future_certificate_no_growth | pass | Monitoring during continuous future execution may invalidate but cannot increase a capacity certificate |
| planned_force_with_reserve | pass | Every planned/installed MPC load respects certificate minus declared tracking reserve |
| actual_future_loading | pass | Actual future target loading stays below tested capacity throughout, independently of the MPC cap |
| pad_survives | pass | No weak-pad failure occurs |
| body_stable | pass | Measured roll and pitch stay within the declared stability limit |
| certificate_site_guard | pass | A valid future certificate retains sensed contact within the declared uniform 10 mm horizontal / 2.5 mm vertical test region |
| meaningful_progress | not met | Measured CoM advances >=30 mm while another foot is actually >=20 mm airborne for >=1 s, with three other measured supports |
| airborne_contact_schedule | pass | A physically lifted foot is not still scheduled as a support |
| terminal_support | pass | Every planned support remains physically loaded throughout the final half-second, with at least three stable supports |
| conservative_stop | pass | An infeasible untested movement causes a sustained safe stop on the original three legs without claiming task completion |
| requested_force_is_not_achieved | pass | At least 1 N of requested probe loading remains unachieved and cannot be certified |
| collapse_after_light_touch | not met | Confirmed light contact is followed by actual weight-transfer overload and >=2 mm physical pad collapse; the unaware baseline intentionally has no capacity probe |
| configuration_v2 | pass | V2 declares one recognized strategy and the selected FL target |
| recovery_state_coverage | pass | Recovery is one contiguous unload→lift→hold sequence through termination; a changed phase label cannot hide a support-loss interval |
| supported_sensor_configuration | pass | Declared sensing uses bounded force noise, at most 0.2 mm componentwise position noise and zero delay |
| sensor_reserve_covers_declared_error | pass | Measurement reserve covers the entire declared bounded force error |
| realized_sensor_error_bounds | pass | Every recorded post-reset observation respects the declared bounded force/position errors and ideal contact channel |
| aligned_sensor_clock | pass | V2 observations are synchronous with each control input; no unaccounted delayed samples |
| continuous_certificate_monitor | pass | Every post-certificate tick checks contact/site validity, with irreversible invalidation until a fresh complete probe |
| certificate_evidence_sound | pass | Any issued certificate has a complete independently verified physical evidence window, even if the trial later recovers |
| certificate_revision_finite | pass | Certificate revision identifiers are nonnegative integers |
| probe_and_recovery_tripod | pass | Original three supports remain measured and loaded through every probe and recovery transition |
| no_future_execution_after_failure | pass | A failed pad never authorizes further weight-transfer movement |
| future_certified_or_unloaded | pass | Every movement/stop interval respects certified actual and commanded loads, or leaves an uncertified target unloaded and unscheduled |
| recovery_commands_unloaded | pass | Throughout recovery lift and hold the target is unscheduled, its installed force cap is zero, and its commanded support force is negligible |
| recovery_configuration | pass | Recovery declares at least 20 mm lift, at least 2 s stable hold, and a bounded unload deadline |
| controlled_probe_failure_recovery | not met | Failure occurs during a probe, followed by controlled FL unloading/lift and at least 2 s of terminal original-tripod support; no task completion claim |
| terminal_safe_stop | pass | An intentional stop maintains the original tripod; any uncertified target is physically unloaded |
