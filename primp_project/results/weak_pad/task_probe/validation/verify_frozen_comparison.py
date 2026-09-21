"""Verify frozen validation semantics and capacity-blind execution prefixes.

Reads raw traces only. This audit complements the separate physical LP and
certificate audit; it never rewrites metadata, raw evidence or trial summaries.
"""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2
from primp_project.task_probe.analysis import evaluate_task_probe
from primp_project.task_probe.study import verify_study, verify_legacy_baseline, paired_results, verify_selection

STUDY = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(a, b):
    return np.array_equal(a, b, equal_nan=True) if a.dtype.kind in 'fc' else np.array_equal(a, b)


def prefix_pair(reference, compared):
    """Only evaluator overload timers may differ before physical failure."""
    ignored = {'wall_time_s', 'solver_time_s', 'overload_elapsed_s'}
    with np.load(reference/'signals.npz', allow_pickle=False) as a:
        with np.load(compared/'signals.npz', allow_pickle=False) as b:
            stop = min(len(a['control_time_s']), len(b['control_time_s']))
            for z in (a, b):
                failed = np.flatnonzero(z['pad_failed'])
                if len(failed):
                    stop = min(stop, int(failed[0]))
            shared = sorted(set(a.files) & set(b.files) - ignored)
            mismatch = [key for key in shared if not equal(a[key][:stop], b[key][:stop])]
            return dict(verified=not mismatch and stop > 0,
                reference_run_id=reference.name, compared_run_id=compared.name,
                compared_samples=stop, compared_channels=len(shared),
                prefix_duration_s=float(a['control_time_s'][stop-1]-a['control_time_s'][0]+.002) if stop else 0.,
                ignored_host_and_evaluator_channels=sorted(ignored), mismatches=mismatch)


def policy_prefix(a_dir,b_dir,channels):
    with np.load(a_dir/'signals.npz',allow_pickle=False) as a:
        with np.load(b_dir/'signals.npz',allow_pickle=False) as b:
            stop=min(len(a['control_time_s']),len(b['control_time_s']))
            for archive in (a,b):
                decision=np.flatnonzero(archive['additional_probe_count']>0)
                if len(decision):stop=min(stop,int(decision[0]))
            mismatches=[key for key in channels if not equal(a[key][:stop],b[key][:stop])]
            return dict(verified=stop>0 and not mismatches,fixed_run_id=a_dir.name,task_run_id=b_dir.name,
                compared_channels=len(channels),compared_samples=stop,
                prefix_duration_s=float(a['control_time_s'][stop-1]-a['control_time_s'][0]+.002),mismatches=mismatches)


def verify(directory=STUDY):
    directory=Path(directory)
    frozen=verify_study(directory)
    manifest=json.loads((directory/'split_manifest.json').read_text())
    state=json.loads((directory/'study_state.json').read_text())
    comparison=json.loads((directory/'comparison/comparison.json').read_text())
    if any(entry.get('status') != 'completed' for entry in state['trials'].values()):
        raise ValueError('All predeclared attempts must have recorded results before this full audit')
    rows=[];groups=defaultdict(list);matching=defaultdict(dict);policy_runs=defaultdict(dict);checks=[]
    selection=verify_selection(manifest['fixed_force_selection'])
    chosen_force=manifest['fixed_force_selection']['selected_force_n']
    selection_record=manifest['fixed_force_selection']
    development_protocol=json.loads(Path(selection_record['protocol_path']).read_text())
    declared=datetime.fromisoformat(development_protocol['declared_at'])
    selected_at=datetime.fromisoformat(selection_record['selected_at'])
    manifest_at=datetime.fromisoformat(manifest['created_at'])
    development_start_times=[datetime.fromisoformat(json.loads((Path(row['run_dir'])/'metadata.json').read_text())['created_utc'])
        for row in selection_record['candidate_trials']]
    evaluation_start_times=[]
    for spec in manifest['trials']:
        entry=state['trials'][spec['trial_id']];run=Path(entry['run_dir'])
        m=json.loads((run/'metadata.json').read_text())
        evaluation_start_times.append(datetime.fromisoformat(m['created_utc']))
        saved_base=json.loads((run/'weak_pad_summary.json').read_text())
        focused=json.loads((run/'task_probe_summary.json').read_text())
        before={name:sha(run/name) for name in ('metadata.json','signals.npz','weak_pad_summary.json','task_probe_summary.json')}
        with np.load(run/'signals.npz', allow_pickle=False) as archive:
            d={key:archive[key] for key in archive.files}
        base=evaluate_weak_pad_v2(m,d);base['run_id']=run.name
        rerun_focused=evaluate_task_probe(m,d);rerun_focused['run_id']=run.name
        phase=d['phase'].astype(str);dt=float(m['dt_s']);metrics=focused['metrics']
        probe=np.isin(phase,('probe_ramp','probe_hold','probe_release','reprobe_posture'))
        deliberate=np.isin(phase,('probe_ramp','probe_hold'))
        recovery=np.isin(phase,('recovery_unload','recovery_lift','recovery_hold'))
        check=dict(trial_id=spec['trial_id'],
            exact_original_evaluator_result=base==saved_base,
            exact_frozen_task_evaluator_result=rerun_focused==focused,
            every_original_criterion_unchanged=base['criteria']==focused['criteria'],
            original_outcome_unchanged=base['outcome']==focused['outcome'],
            original_completion_semantics=base['physical_success']==focused['physical_success'] and base['passed']==focused['passed'],
            all_new_integrity_checks=all(c['passed'] for c in focused['task_probe_criteria'].values()),
            actual_pad_damage=metrics['pad_damaged']==bool(np.any(d['pad_failed'])),
            exact_probe_time=metrics['probe_time_s']==float(np.count_nonzero(probe)*dt),
            exact_deliberate_probe_time=metrics['deliberate_probe_time_s']==float(np.count_nonzero(deliberate)*dt),
            exact_recovery_time=metrics['recovery_time_s']==float(np.count_nonzero(recovery)*dt),
            distinct_command_and_physical_force=metrics['maximum_actual_probe_force_n']==float(np.max(d['actual_pad_normal_force_n'][probe])),
            one_development_selected_fixed_scalar=(m['trial_parameters']['fixed_probe_force_n']==chosen_force
                and m['fixed_probe_force_n']==chosen_force and spec['parameters']['fixed_probe_force_n']==chosen_force),
            declared_task_goal=(metrics['requested_task_progress_m']==spec['parameters']['planning_config']['forward_progress_m']),
            task_specific_success_gate=(not focused['physical_success'] or
                focused['task_probe_criteria']['task_specific_goal_attained']['passed']),
            raw_and_summaries_unchanged=before=={name:sha(run/name) for name in before})
        check['verified']=all(v for k,v in check.items() if k!='trial_id')
        checks.append(check)
        public={key:value for key,value in m['trial_parameters'].items() if key!='probe_policy'}
        matching[(spec['case_id'],spec['seed'])][spec['probe_policy']]=dict(public=public,
            optimizer=m['movement_optimizer_settings'],optimizer_id=m['movement_optimizer_id'],
            initial_state=m['initial_state'],model_mass_kg=m['model_mass_kg'],gravity_m_s2=m['gravity_m_s2'])
        policy_runs[(spec['case_id'],spec['seed'])][spec['probe_policy']]=run
        groups[(spec['task_id'],spec['probe_policy'],spec['seed'])].append((spec['parameters']['failure_threshold_n'],run))
        rows.append(dict(case_id=spec['case_id'],seed=spec['seed'],probe_policy=spec['probe_policy'],
            status='completed',outcome=focused['outcome'],physical_success=focused['physical_success'],metrics=metrics))
    matched=[dict(case_id=case,seed=seed,verified=pair['fixed_force']==pair['task_sufficient'])
             for (case,seed),pair in matching.items()]
    prefixes=[]
    for (task_id,policy,seed),runs in groups.items():
        ordered=sorted(runs,key=lambda x:x[0]);reference=ordered[-1][1]
        for capacity,run in ordered[:-1]:
            prefixes.append(dict(task_id=task_id,probe_policy=policy,seed=seed,hidden_capacity_n=capacity,**prefix_pair(reference,run)))
    pairs=paired_results(rows)
    pairs_unchanged=pairs==comparison['paired_results']
    original_state=json.loads(Path('primp_project/results/weak_pad/study_v2/study_state.json').read_text())
    original_run=Path(next(iter(original_state['trials'].values()))['run_dir'])
    with np.load(original_run/'signals.npz',allow_pickle=False) as archive:
        channels=sorted(set(archive.files)-{'wall_time_s','solver_time_s'})
    policy_prefixes=[dict(case_id=case,seed=seed,**policy_prefix(pair['fixed_force'],pair['task_sufficient'],channels))
        for (case,seed),pair in policy_runs.items()]
    chronology=dict(verified=declared<min(development_start_times) and max(development_start_times)<selected_at<manifest_at<min(evaluation_start_times),
        candidate_grid_declared_at=declared.isoformat(),fixed_scalar_selected_at=selected_at.isoformat(),
        evaluation_manifest_created_at=manifest_at.isoformat(),first_evaluation_started_at=min(evaluation_start_times).isoformat())
    result=dict(verified=frozen['verified'] and selection['verified'] and
        all(row['verified'] for row in checks+matched+prefixes+policy_prefixes) and pairs_unchanged and chronology['verified'],
        frozen_study=frozen,original_evaluator_source_sha256=sha(Path('primp_project/analysis/weak_pad_v2.py')),
        audited_trials=len(checks),audit_source_sha256=sha(Path(__file__)),
        original_evaluation_checks_preserved=checks,matched_policy_geometry_and_parameters=matched,
        across_capacity_prefix_checks=prefixes,paired_comparison_matches_raw_results=pairs_unchanged,
        across_policy_prefix_checks=policy_prefixes,frozen_development_selection=selection,
        development_selection_precedes_evaluation=chronology,
        physical_outcomes=dict(Counter(row['outcome'] for row in rows)),
        paired_damage_prevented_with_task_completion=sum(row['avoidable_damage_demonstrated'] for row in pairs),
        canonical_evidence_modified=False,legacy_baseline_after_audit=verify_legacy_baseline())
    target=directory/'validation/frozen_comparison_verification.json'
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    result=verify()
    print(json.dumps({key:result[key] for key in ('verified','audited_trials','paired_damage_prevented_with_task_completion','physical_outcomes')},indent=2))
    if not result['verified']:raise SystemExit(1)
