"""Label only new probe-efficiency runs; preserve original recording evidence."""
from collections import Counter
import json
from pathlib import Path

from primp_project.recording.catalog import refresh_catalog
from primp_project.probe_efficiency.study import verify_study

STUDY=Path(__file__).resolve().parent.parent


def update(study=STUDY):
    study=Path(study).resolve();verify_study(study)
    root=study.parent.parent
    manifest=json.loads((study/'split_manifest.json').read_text())
    state=json.loads((study/'study_state.json').read_text())
    if any(entry.get('status')!='completed' for entry in state['trials'].values()):
        raise ValueError('Wait for all canonical recordings before the final catalog update')
    path=root/'annotations.json';annotations=json.loads(path.read_text())
    previous=dict(annotations);ids=set();outcomes={}
    for spec in manifest['trials']:
        run=Path(state['trials'][spec['trial_id']]['run_dir']);run_id=run.name;ids.add(run_id)
        result=json.loads((run/'probe_efficiency_summary.json').read_text());outcomes[run_id]=result['outcome']
        annotations[run_id]=dict(purpose=f"Probe efficiency: {spec['probe_policy']}; {spec['parameters']['failure_threshold_n']:g} N hidden capacity, seed {spec['seed']}",
            notes=[f"Frozen matched probe-dose evaluation. Probe policy: {spec['probe_policy']}. Focused validation outcome: {result['outcome']}; actual pad damage: {result['metrics']['pad_damaged']}.",
                f"The catalog status uses the unchanged V2 physical validator. [Focused report]({run.relative_to(root).as_posix()}/probe_efficiency_report.md) · [Target-integrity summary]({run.relative_to(root).as_posix()}/probe_efficiency_summary.json)."])
    development=root/'weak_pad/probe_efficiency_development'
    development_ids=set()
    for path_metadata in sorted(development.glob('*/metadata.json')):
        m=json.loads(path_metadata.read_text());run_id=path_metadata.parent.name;development_ids.add(run_id)
        annotations[run_id]=dict(purpose=f"Probe-efficiency development check: {m['probe_policy']}, seed {m['seed']}; excluded from the 32-trial sweep",
            notes=['Capacity 62 N development reference. The maximum-policy run reproduces all 98 shared physical/control channels of the frozen V2 baseline exactly.'])
    if any(annotations[key]!=value for key,value in previous.items() if key not in ids|development_ids):
        raise AssertionError('A historical run annotation changed')
    path.write_text(json.dumps(annotations,indent=2,ensure_ascii=False)+'\n')
    records=refresh_catalog(root)
    formal=[record for record in records if record['id'] in ids]
    checks=dict(all_formal_runs_listed=len(formal)==len(manifest['trials']),
        all_policies_explicit_in_purpose=all(any(policy in record['purpose'] for policy in ('maximum_feasible','minimum_sufficient')) for record in formal),
        catalog_and_focused_outcomes_agree=all(record['outcome']==outcomes[record['id']] for record in formal),
        recovery_distinct_from_completion=all(record['physical_success'] is False and record['status']=='RECOVERED_STOP'
            for record in formal if record['outcome']=='RECOVERED_STOP'),
        historical_annotations_preserved=True)
    result=dict(verified=all(checks.values()),checks=checks,total_catalog_recordings=len(records),
        formal_probe_efficiency_recordings=len(formal),development_probe_efficiency_recordings=len(development_ids),
        outcomes=dict(Counter(record['outcome'] for record in formal)),catalog_statuses=dict(Counter(record['status'] for record in formal)),
        recording_evidence_modified=False,post_catalog_study_verification=verify_study(study))
    (study/'validation/catalog_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=update();print(json.dumps(result,indent=2))
    if not result['verified']:raise SystemExit(1)
