# Weak-pad V2 validation evidence

`development/analyzer_review_before.json` preserves the independent review findings. `development/analyzer_review_after.json` and `development/falsify_analyzer.py` verify that the clean native recordings retain their outcomes and all 11 corrupted variants are rejected. These checks do not change the canonical recordings.

`final_development_readonly_audit.json` records all seven development outcomes using the final analyzer, including the earlier safe-stop development attempt. It separates final movement progress from larger probe excursions and splits force-tracking gaps by phase.

`study_cases_proposed.json` is the reviewed eight-condition input used to prepare the 48-cell protocol with seeds 101 and 509. The authoritative execution declaration is the adjacent study's `split_manifest.json`; its development inventory records the previously used conditions and raw hashes. `focused_tests.json` records the 65 focused regression checks before freezing.

Earlier distinct copies of the development review are retained with an `_earlier` suffix. The final formal raw audit is `independent_execution_audit.json`, reproduced by `audit_execution.py`; `force_tracking_gaps.png` plots per-trial maxima. `necessity_audit.json` and `audit_necessity.py` independently check the geometric load limits.
