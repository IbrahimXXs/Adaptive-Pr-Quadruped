# Weak-pad result: INVALID

Strategy: **unaware**. Expected outcome met: **False**. Physical movement success: **False**.

A survived probe establishes a tested load bound; a requested load or MPC cap alone does not establish capacity.

| Check | Result | Requirement |
| --- | --- | --- |
| finite_data | pass | All recorded numeric evidence is finite |
| configuration | pass | Declared experiment, timing, finite force reserves and bounded movement checks |
| completed_recording | pass | Recording ends through the experiment's controlled completion/stop path |
| sample_clock | pass | Continuous physics timestamps and aligned control/measurement intervals |
| mpc_update_cadence | pass | Every periodic/support-change solve occurs; extra solves must install a changed force cap |
| solver_success | not met | All recorded MPC and QP solves succeed |
| strength_truth_boundary | pass | Hidden pad capacity occurs only in evaluator metadata |
| physical_failure_model | pass | Latched failure and subsequent deformation follow actual overload dwell, not commanded loading |
| probe_observed | not met | A probe phase is physically recorded |
| actual_dwell_certificate | not met | Every capacity certificate is bounded by sustained actual achieved loading and measured-force reserve, with original three supports stable |
| certificate_changes_logged | pass | A valid certificate has strictly positive tested capacity |
| future_declared | not met | A future plan or conservative stop is reached |
| future_valid_certificate | not met | Every future loading interval has a valid measured-evidence certificate |
| planned_force_with_reserve | not met | Every planned/installed MPC load respects certificate minus declared tracking reserve |
| actual_future_loading | not met | Actual future target loading stays below tested capacity throughout, independently of the MPC cap |
| pad_survives | not met | No weak-pad failure occurs |
| body_stable | pass | Measured roll and pitch stay within the declared stability limit |
| meaningful_progress | not met | Measured CoM advances >=30 mm while another foot is actually >=20 mm airborne for >=1 s, with three other measured supports |
| airborne_contact_schedule | pass | A physically lifted foot is not still scheduled as a support |
| conservative_stop | not met | An infeasible untested movement causes a sustained safe stop on the original three legs without claiming task completion |
| requested_force_is_not_achieved | not met | At least 1 N of requested probe loading remains unachieved and cannot be certified |
| collapse_after_light_probe | not met | A survived actual probe is followed by actual future overload and >=2 mm physical pad collapse |
