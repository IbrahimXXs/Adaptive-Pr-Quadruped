# Weak-pad result: SUCCESS

Strategy: **adaptive**. Expected outcome met: **True**. Physical movement success: **True**.

A survived probe establishes a tested load bound; a requested load or MPC cap alone does not establish capacity.

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
| meaningful_progress | pass | Measured CoM advances >=30 mm while another foot is actually >=20 mm airborne for >=1 s, with three other measured supports |
| airborne_contact_schedule | pass | A physically lifted foot is not still scheduled as a support |
| terminal_support | pass | Every planned support remains physically loaded throughout the final half-second, with at least three stable supports |
| conservative_stop | not met | An infeasible untested movement causes a sustained safe stop on the original three legs without claiming task completion |
| requested_force_is_not_achieved | pass | At least 1 N of requested probe loading remains unachieved and cannot be certified |
| collapse_after_light_touch | not met | Confirmed light contact is followed by actual weight-transfer overload and >=2 mm physical pad collapse; the unaware baseline intentionally has no capacity probe |
