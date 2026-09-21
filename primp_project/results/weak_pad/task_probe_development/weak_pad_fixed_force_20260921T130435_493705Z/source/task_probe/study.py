"""Frozen matched probing study with explicit conditions and retained attempts.

No numeric evaluation conditions are selected by this module. Supply a reviewed
case file after development, freeze it, then run each declared cell once.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import csv
import hashlib
import inspect
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import traceback

from primp_project import PROJECT_ROOT, REPOSITORY_ROOT, RESULTS_ROOT
from primp_project.experiments.weak_pad_study import _now, _sha, _write
from primp_project.probe_efficiency.study import source_fingerprint as legacy_fingerprint, verify_study as verify_predecessor

POLICIES=('fixed_force','task_sufficient')
OUTCOMES=('SUCCESS','SAFE_STOP','RECOVERED_STOP','UNSAFE','INCOMPLETE','INVALID')
DEFAULT_STUDY_DIR=RESULTS_ROOT/'weak_pad'/'task_probe'
DEFAULT_DEVELOPMENT_DIR=RESULTS_ROOT/'weak_pad'/'task_probe_development'
BASELINE_SNAPSHOT=DEFAULT_STUDY_DIR/'validation'/'frozen_predecessor_snapshot.json'


def _canonical_parameters(parameters):
    """Resolve the runner's defaults before hashing or comparing conditions."""
    from .runner import run_trial
    signature=inspect.signature(run_trial)
    unknown=set(parameters)-set(signature.parameters)
    if unknown:raise ValueError(f'Unknown runner parameters: {sorted(unknown)}')
    values={key:item.default for key,item in signature.parameters.items()
            if key not in ('probe_policy','seed','role','headless','output_group')}
    values.update(parameters)
    for key in ('planning_config','initial_state','sensor_config'):
        values[key]=values[key] or {}
    return json.loads(json.dumps(values,allow_nan=False))


def _condition_signature(public,threshold):
    """A new label, policy or seed does not make a new physical condition."""
    from primp_project.planning.load_capacity import CapacityPlanningConfig
    from dataclasses import asdict
    parameters=_canonical_parameters({key:value for key,value in public.items()
        if key not in ('probe_policy','strategy','seed','role','headless','output_group')})
    parameters['failure_threshold_n']=threshold
    parameters.pop('scenario',None)
    settings=dict(forward_progress_m=.04,next_lift_height_m=.03,next_hold_s=1.,
        maximum_probe_request_n=parameters['requested_probe_force_n'],requested_probe_load_n=parameters['requested_probe_force_n'],
        probe_force_ceiling_n=parameters['maximum_probe_force_n'])
    settings.update(parameters['planning_config'])
    parameters['planning_config']=asdict(CapacityPlanningConfig(**settings))
    parameters['initial_state']={
        **dict(body_offset_xy_m=[0.,0.],foot_offsets_xy_m=[[0.,0.]]*4),**parameters['initial_state']}
    parameters['sensor_config']={**dict(force_bias_n=0.,force_noise_n=0.,position_noise_m=0.),**parameters['sensor_config']}
    def numbers(value):
        if isinstance(value,dict):return {key:numbers(child) for key,child in value.items()}
        if isinstance(value,(tuple,list)):return [numbers(child) for child in value]
        return float(value) if isinstance(value,(int,float)) and not isinstance(value,bool) else value
    return hashlib.sha256(json.dumps(numbers(parameters),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def development_inventory(directory=DEFAULT_DEVELOPMENT_DIR):
    rows=[]
    for path in sorted(Path(directory).glob('*/metadata.json')):
        metadata=json.loads(path.read_text());signals=path.parent/'signals.npz'
        if metadata.get('protocol_version')!=2 or metadata.get('role')!='development' or not signals.exists():continue
        evaluation=metadata.get('evaluation',{})
        threshold=evaluation.get('failure_threshold_n',evaluation.get('failure_load_n'))
        rows.append(dict(run_id=path.parent.name,run_dir=str(path.parent.resolve()),metadata_sha256=_sha(path),
            signals_sha256=_sha(signals),condition_sha256=_condition_signature(metadata['trial_parameters'],threshold)))
    return rows


def source_fingerprint():
    """Extend the exact legacy source inventory without editing any legacy file."""
    files=dict(legacy_fingerprint()['files'])
    paths=list(Path(__file__).parent.glob('*.py'))+[BASELINE_SNAPSHOT]
    for path in paths:
        if not path.exists():raise ValueError(f'Missing task-load probing source: {path}')
        files[str(path.relative_to(REPOSITORY_ROOT))]=_sha(path)
    return dict(sha256=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest(),files=files)


def verify_legacy_baseline():
    """Check the saved 48-trial study and its source byte for byte."""
    snapshot=json.loads(BASELINE_SNAPSHOT.read_text())
    if legacy_fingerprint()!=snapshot['source_fingerprint']:
        raise ValueError('Frozen predecessor controller, environment or evaluation source changed')
    for name,digest in snapshot['canonical_files'].items():
        if _sha(REPOSITORY_ROOT/name)!=digest:
            raise ValueError(f'Predecessor canonical result changed: {name}')
    return dict(verified=True,trials=snapshot['prior_study_verify']['trials'],
        source_sha256=snapshot['source_fingerprint']['sha256'],canonical_files=len(snapshot['canonical_files']))


def verify_development_inventory(manifest):
    for row in manifest.get('development_inventory', []):
        directory=Path(row['run_dir'])
        for key,name in (('metadata_sha256','metadata.json'),('signals_sha256','signals.npz')):
            if _sha(directory/name)!=row[key]:
                raise ValueError(f'Development evidence changed after declaration: {directory/name}')
    return len(manifest.get('development_inventory', []))


def protocol(cases, *, seeds=(101,509)):
    if not cases:raise ValueError('Declare evaluation conditions explicitly; no automatic development-derived defaults')
    if not seeds or len(set(seeds))!=len(seeds) or any(isinstance(s,bool) or int(s)!=s or not 0<=s<2**32 for s in seeds):
        raise ValueError('Seeds must be distinct nonnegative 32-bit integers')
    ids=set();trials=[]
    for case in cases:
        case_id=case.get('case_id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',case_id) or case_id in ids:
            raise ValueError('Case IDs must be distinct safe simple names')
        ids.add(case_id)
        if case.get('condition_role') not in ('development','held_out'):
            raise ValueError('Each case declares whether its condition was used in development or held out')
        parameters=case.get('parameters',{})
        if any(key in parameters for key in ('probe_policy','strategy','seed','role','output_group','headless')):
            raise ValueError('Case parameters cannot override comparison identity')
        threshold=parameters.get('failure_threshold_n')
        if not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or threshold<=0:
            raise ValueError('A finite positive evaluator-only threshold is required')
        # Round-trip validation rejects nonserializable and nonfinite nested values.
        parameters=_canonical_parameters(parameters)
        if parameters['measurement_reserve_n']!=1. or parameters['tracking_reserve_n']!=8.:
            raise ValueError('The focused frozen-baseline comparison preserves the 1 N sensing and 8 N tracking reserves')
        probe_policies=case.get('probe_policies',list(POLICIES))
        if list(probe_policies)!=list(POLICIES):
            raise ValueError('Every capacity requires both policies in the fixed matched order')
        expected=case.get('expected_outcomes',{})
        for probe_policy in probe_policies:
            allowed=expected.get(probe_policy)
            if not isinstance(allowed,list) or not allowed or any(v not in OUTCOMES for v in allowed):
                raise ValueError('Predeclare expected outcomes for every probe_policy; do not infer them after results')
            for seed in seeds:
                trials.append(dict(trial_id=f'{case_id}_{probe_policy}_seed{seed}',case_id=case_id,
                    family=case.get('family','unspecified'),condition_role=case['condition_role'],
                    probe_policy=probe_policy,seed=int(seed),role='evaluation',parameters=parameters,
                    expected_outcomes=allowed))
    return dict(version=1,experiment='weak_pad',study_name='task_probe',cases=cases,seeds=list(seeds),trials=trials,
        policy=dict(attempts='One attempt per cell, including failures and interrupted attempts; no silent reruns',
            comparison='Both policies use the frozen V2 controller, movement optimizer, freedoms, constraints and reserves; the added policy targets a task-sufficient additional probe instead of the maximum feasible probe',
            success='Only actual body-and-foot progress is SUCCESS; SAFE_STOP and RECOVERED_STOP do not count as task completion',
            truth='Hidden pad strength is evaluator-only; sensing, geometry and error bounds are public',
            interpretation='Predeclared engineering cases and declared seeds, not a statistical population or independent samples within each trace',
            holdout='Held-out labels describe condition selection before evaluation; development conditions remain labeled separately',
            damage='Pad damage is the actual failure latch, including successfully recovered damage; recovery never counts as movement completion',
            avoidable_damage='A paired maximum-policy pad failure is called avoidable here only when the minimum policy completes the same movement undamaged',
            prior_failures='The four previous failures remain below the relaxed task load and are not claimed preventable by this experiment'))


def ensure_manifest(directory, cases=None, seeds=(101,509), *, development_dir=DEFAULT_DEVELOPMENT_DIR):
    directory=Path(directory);path=directory/'split_manifest.json'
    if path.exists():
        saved=json.loads(path.read_text())
        if cases is not None:
            expected=protocol(cases,seeds=seeds)
            if {key:saved.get(key) for key in expected}!=expected:raise ValueError('Protocol changed; choose a new study directory')
        return saved,path
    expected=protocol(cases,seeds=seeds)
    inventory=development_inventory(development_dir)
    used={row['condition_sha256'] for row in inventory}
    for spec in expected['trials']:
        if spec['condition_role']=='held_out' and _condition_signature(spec['parameters'],spec['parameters']['failure_threshold_n']) in used:
            raise ValueError('A held-out condition already appeared in development; probe_policy, scenario label and seed do not establish novelty')
    directory.mkdir(parents=True,exist_ok=True)
    _write(path,dict(expected,created_at=_now(),development_inventory=inventory))
    return json.loads(path.read_text()),path


def freeze(directory,path):
    verify_development_inventory(json.loads(Path(path).read_text()))
    expected=dict(version=1,manifest_sha256=_sha(path),source=source_fingerprint(),legacy_baseline=verify_legacy_baseline())
    target=Path(directory)/'execution_freeze.json'
    if target.exists():
        saved=json.loads(target.read_text())
        if {key:saved.get(key) for key in expected}!=expected:raise ValueError('Frozen task-load probing source or protocol changed')
        return saved
    _write(target,dict(expected,frozen_at=_now()))
    return json.loads(target.read_text())


def _kwargs(spec):
    return dict(spec['parameters'],probe_policy=spec['probe_policy'],seed=spec['seed'],role='evaluation')


def _validate_record(run_dir,spec,entry=None):
    run=Path(run_dir);metadata=json.loads((run/'metadata.json').read_text());summary=json.loads((run/'task_probe_summary.json').read_text())
    if metadata.get('experiment')!='weak_pad' or metadata.get('protocol_version')!=2 or metadata.get('study_name')!='task_probe' or metadata.get('strategy')!='adaptive_probe':
        raise ValueError('Wrong experiment protocol')
    for key in ('probe_policy','seed','role'):
        if metadata.get(key)!=_kwargs(spec)[key]:raise ValueError(f'Trial identity mismatch: {key}')
    declared=metadata.get('trial_parameters')
    public={key:value for key,value in _kwargs(spec).items() if key!='failure_threshold_n'}
    public['strategy']='adaptive_probe'
    if declared!=public:raise ValueError('Recorded public trial parameters differ from the predeclared cell')
    actual_threshold=metadata.get('evaluation',{}).get('failure_threshold_n',metadata.get('evaluation',{}).get('failure_load_n'))
    if actual_threshold!=spec['parameters']['failure_threshold_n']:raise ValueError('Evaluator-only capacity differs')
    if not metadata.get('movement_optimizer_id'):raise ValueError('Movement optimizer identity is missing')
    if summary.get('physical_success') is not (summary.get('outcome')=='SUCCESS'):
        raise ValueError('Stops and recovery cannot count as physical success')
    if entry:
        for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','task_probe_summary.json'),('baseline_summary_sha256','weak_pad_summary.json')):
            if entry.get(key)!=_sha(run/name):raise ValueError(f'Canonical trial changed: {name}')
    return metadata,summary


def _worker(spec,directory,frozen,headless):
    os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
    group=Path(directory)/'trials'/spec['trial_id'];result={}
    try:
        if source_fingerprint()!=frozen['source']:raise ValueError('Source changed before trial')
        from .runner import run_trial
        run,_=run_trial(**_kwargs(spec),headless=headless,output_group=group)
        result['run_dir']=str(run)
        if source_fingerprint()!=frozen['source']:raise ValueError('Source changed during trial')
    except BaseException as error:
        result.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
        candidates=sorted(group.glob('weak_pad_*')) if group.exists() else []
        if candidates:result['run_dir']=str(candidates[-1])
    return result


def paired_results(rows):
    """Preserve per-seed physical pairs; never infer damage prevention from capacity."""
    groups={}
    for row in rows:groups.setdefault((row['case_id'],row['seed']),{})[row['probe_policy']]=row
    result=[]
    for (case,seed),pair in groups.items():
        maximum=pair.get('fixed_force',{});minimum=pair.get('task_sufficient',{})
        ready=all(pair.get(policy,{}).get('status')=='completed' for policy in POLICIES)
        maxm=maximum.get('metrics',{});minm=minimum.get('metrics',{})
        undamaged_completion=minimum.get('physical_success',False) and minm.get('pad_damaged') is False
        def delta(key):
            a=maxm.get(key);b=minm.get(key)
            return b-a if ready and a is not None and b is not None else None
        result.append(dict(case_id=case,seed=seed,paired_records_complete=ready,
            hidden_capacity_n=maxm.get('hidden_capacity_n',minm.get('hidden_capacity_n')),
            maximum_outcome=maximum.get('outcome','NO_RESULT'),minimum_outcome=minimum.get('outcome','NO_RESULT'),
            maximum_pad_damaged=maxm.get('pad_damaged'),minimum_pad_damaged=minm.get('pad_damaged'),
            avoidable_damage_demonstrated=bool(ready and maxm.get('pad_damaged') and undamaged_completion),
            both_complete_undamaged=bool(ready and maximum.get('physical_success',False)
                and maxm.get('pad_damaged') is False and undamaged_completion),
            minimum_minus_maximum_probe_time_s=delta('probe_time_s'),
            minimum_minus_maximum_actual_probe_peak_n=delta('maximum_actual_probe_force_n'),
            minimum_minus_maximum_trial_time_s=delta('total_trial_time_s')))
    return result


def write_comparison(directory,manifest,state):
    directory=Path(directory);rows=[];identities={}
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'],{});summary={}
        if entry.get('status')=='completed':
            metadata,summary=_validate_record(entry['run_dir'],spec,entry)
            identity=(metadata['movement_optimizer_id'],json.dumps(metadata.get('movement_optimizer_settings',{}),sort_keys=True))
            if spec['case_id'] in identities and identities[spec['case_id']]!=identity:
                raise ValueError('Compared policies changed the movement optimizer or its constraints')
            identities[spec['case_id']]=identity
        rows.append(dict(trial_id=spec['trial_id'],case_id=spec['case_id'],probe_policy=spec['probe_policy'],seed=spec['seed'],
            family=spec['family'],condition_role=spec['condition_role'],status=entry.get('status','not_run'),run_dir=entry.get('run_dir'),
            outcome=summary.get('outcome','NO_RESULT'),physical_success=bool(summary.get('physical_success',False)),
            expected_outcome_met=summary.get('outcome') in spec['expected_outcomes'],metrics=summary.get('metrics',{}),error=entry.get('error')))
    pairs=paired_results(rows)
    result=dict(version=1,study_name='task_probe',complete=all(row['status'] in ('completed','error') for row in rows),expected_trials=len(rows),
        expected_outcomes_met=sum(row['expected_outcome_met'] for row in rows),physical_successes=sum(row['physical_success'] for row in rows),
        trials=rows,paired_optimizer_verified=all(row['status']=='completed' for row in rows),policy=manifest['policy'],
        paired_results=pairs,avoidable_damage_pairs=sum(row['avoidable_damage_demonstrated'] for row in pairs))
    result['by_probe_policy']={policy:dict(trials=sum(r['probe_policy']==policy for r in rows),
        outcomes={outcome:sum(r['probe_policy']==policy and r['outcome']==outcome for r in rows) for outcome in OUTCOMES},
        pad_damage=sum(r['probe_policy']==policy and r['metrics'].get('pad_damaged',False) for r in rows),
        undamaged_completions=sum(r['probe_policy']==policy and r['physical_success'] and not r['metrics'].get('pad_damaged',True) for r in rows),
        no_result=sum(r['probe_policy']==policy and r['outcome']=='NO_RESULT' for r in rows)) for policy in POLICIES}
    _write(directory/'comparison'/'comparison.json',result)
    columns=('trial_id','case_id','probe_policy','seed','condition_role','outcome','physical_success','pad_damaged',
        'hidden_capacity_n','minimum_future_load_n','minimum_sufficient_test_target_n','selected_additional_probe_target_n',
        'maximum_actual_probe_force_n','maximum_measured_probe_force_n','maximum_commanded_probe_force_n',
        'maximum_certified_force_n','maximum_actual_future_pad_force_n','probe_time_s','deliberate_probe_time_s',
        'additional_probe_time_s','recovery_time_s','total_trial_time_s','recovery_unload_delay_s','recovery_stable_hold_s',
        'maximum_pad_displacement_m','pad_failure_time_s','pad_failure_phase','final_forward_com_motion_m',
        'maximum_next_foot_clearance_m','simultaneous_progress_hold_s')
    with (directory/'comparison'/'trials.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in rows:
            values=dict(row,**row['metrics']);writer.writerow({key:values.get(key) for key in columns})
    if pairs:
        with (directory/'comparison'/'paired_differences.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    def number(value,scale=1.):return '—' if value is None else f'{scale*value:.3f}'
    lines=['# How much probing is necessary?', '',
        'Both policies use the frozen V2 controller and physical evaluation. The new policy changes the additional test target; movement freedoms and sensing/tracking reserves are identical.', '',
        f"Physical completions: {result['physical_successes']}/{len(rows)}. Paired examples of damage avoided with physical completion: {result['avoidable_damage_pairs']}.", '',
        '| Policy | Trials | Completed | Pad damaged | Recovered after damage | Safe stop | Other outcomes |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for policy,item in result['by_probe_policy'].items():
        outcomes=item['outcomes'];other=sum(outcomes[key] for key in ('UNSAFE','INCOMPLETE','INVALID'))+item['no_result']
        lines.append(f"| {policy} | {item['trials']} | {outcomes['SUCCESS']} | {item['pad_damage']} | {outcomes['RECOVERED_STOP']} | {outcomes['SAFE_STOP']} | {other} |")
    lines+=['', '| Capacity N / seed | Policy | Outcome | Damaged | Test command N | Actual test peak N | Probe s | Recovery s |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        m=row['metrics'];lines.append(f"| {number(m.get('hidden_capacity_n'))} / {row['seed']} | {row['probe_policy']} | {row['outcome']} | {m.get('pad_damaged','—')} | {number(m.get('selected_additional_probe_target_n'))} | {number(m.get('maximum_actual_probe_force_n'))} | {number(m.get('probe_time_s'))} | {number(m.get('recovery_time_s'))} |")
    matched=[pair for pair in pairs if pair['both_complete_undamaged']]
    if matched:
        deltas=[pair['minimum_minus_maximum_probe_time_s'] for pair in matched]
        lines+=['',f"Among the {len(matched)} pairs where both policies completed undamaged, the minimum-policy change in probing time ranged from {min(deltas):.3f} to {max(deltas):.3f} s. All-trial times also include tests interrupted by pad failure; shorter failed tests are not efficiency gains."]
    lines+=['',manifest['policy']['prior_failures'],'',manifest['policy']['avoidable_damage'],'',
        'Requested force, actual target-pad force and measured dwell proof remain distinct. The empirical 8 N tracking reserve has not been established as a universal bound.',
        '',manifest['policy']['interpretation'],'',manifest['policy']['holdout']]
    (directory/'comparison'/'report.md').write_text('\n'.join(lines)+'\n')
    if result['complete']:_plot_comparison(directory/'comparison'/'comparison.png',rows)
    return result


def _plot_comparison(path,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,3,figsize=(15,5.3),constrained_layout=True)
    colors={'fixed_force':'#995b34','task_sufficient':'#236c9c'}
    seeds=sorted({row['seed'] for row in rows})
    marks={'SUCCESS':'o','RECOVERED_STOP':'X','SAFE_STOP':'s','INVALID':'D','UNSAFE':'*','INCOMPLETE':'v','NO_RESULT':'v'}
    for row in rows:
        m=row['metrics'];capacity=m.get('hidden_capacity_n')
        if capacity is None:continue
        index=POLICIES.index(row['probe_policy']);offset=(index-.5)*.13+(seeds.index(row['seed'])-(len(seeds)-1)/2)*.025
        color=colors[row['probe_policy']]
        axes[0].scatter(capacity+offset,index,marker=marks[row['outcome']],c=color,s=68,
                        edgecolors='red' if m.get('pad_damaged') else color,linewidths=1.6)
        axes[1].scatter(capacity+offset,m.get('maximum_actual_probe_force_n'),marker=marks[row['outcome']],c=color,s=46)
        axes[2].scatter(capacity+offset,m.get('probe_time_s'),marker=marks[row['outcome']],c=color,s=46)
    capacities=[row['metrics'].get('hidden_capacity_n') for row in rows if row['metrics'].get('hidden_capacity_n') is not None]
    if capacities:
        axes[1].plot([min(capacities),max(capacities)],[min(capacities),max(capacities)],'k--',lw=1,label='Force equals capacity')
    axes[0].set_yticks([0,1],['Maximum feasible','Minimum sufficient']);axes[0].set_ylim(-.7,1.7)
    axes[0].set_title('Outcome: circle = completed, X = recovered\nRed edge = actual pad damage')
    axes[1].set_ylabel('Peak actual target-pad force during probing (N)');axes[1].set_title('Physical force, including test transitions')
    axes[2].set_ylabel('Probe phases (s)');axes[2].set_title('Interrupted failed probes can be shorter')
    for policy,color in colors.items():axes[1].scatter([],[],c=color,label=policy.replace('_',' '))
    axes[1].legend(fontsize=8)
    for ax in axes:ax.set_xlabel('Hidden pad capacity (N), evaluator only');ax.grid(alpha=.18)
    fig.suptitle('Frozen controller and reserves; paired capacity sweep')
    fig.savefig(path,dpi=170);plt.close(fig)


def run_study(study_dir=DEFAULT_STUDY_DIR,*,cases=None,seeds=(101,509),workers=2,headless=True,runner=None):
    if workers not in (1,2,3,4) or runner is not None and workers!=1:raise ValueError('Use one to four native workers, or one injected test runner')
    directory=Path(study_dir).resolve();manifest,path=ensure_manifest(directory,cases,seeds);frozen=freeze(directory,path)
    state_path=directory/'study_state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else dict(version=2,manifest_sha256=_sha(path),trials={})
    if state['manifest_sha256']!=_sha(path):raise ValueError('State manifest changed')
    pending=[]
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'])
        if entry:
            if entry.get('status')=='running':raise ValueError('Interrupted attempt retained; review it and start a new study')
            if entry.get('source_sha256')!=frozen['source']['sha256']:raise ValueError('Attempt source differs')
            if entry.get('status')=='completed':_validate_record(entry['run_dir'],spec,entry)
        else:pending.append(spec)
    def reserve(spec):
        state['trials'][spec['trial_id']]=dict(status='running',started_at=_now(),source_sha256=frozen['source']['sha256'])
        _write(state_path,state);print(f"TASK_PROBE {spec['trial_id']}",flush=True)
    def finish(spec,result):
        entry=state['trials'][spec['trial_id']];entry.update(finished_at=_now(),**result)
        entry['status']='error' if result.get('error') else 'completed'
        if entry['status']=='completed':
            try:
                _,summary=_validate_record(entry['run_dir'],spec)
                entry['outcome']=summary['outcome']
                for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','task_probe_summary.json'),('baseline_summary_sha256','weak_pad_summary.json')):
                    entry[key]=_sha(Path(entry['run_dir'])/name)
            except Exception as error:entry.update(status='error',error=f'{type(error).__name__}: {error}')
        _write(state_path,state);write_comparison(directory,manifest,state)
        print(f"{entry['status']}: {spec['trial_id']} -> {entry.get('outcome',entry.get('error'))}",flush=True)
    if runner is not None:
        for spec in pending:
            reserve(spec)
            try:
                run,_=runner(**_kwargs(spec),headless=headless,output_group=directory/'trials'/spec['trial_id'])
                result=dict(run_dir=str(run))
            except Exception as error:result=dict(error=f'{type(error).__name__}: {error}')
            finish(spec,result)
    elif pending:
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as pool:
            queue=iter(pending);active={}
            while True:
                while len(active)<workers:
                    spec=next(queue,None)
                    if spec is None:break
                    reserve(spec);active[pool.submit(_worker,spec,str(directory),frozen,headless)]=spec
                if not active:break
                done,_=wait(active,return_when=FIRST_COMPLETED)
                for future in done:
                    spec=active.pop(future)
                    try:result=future.result()
                    except BaseException as error:result=dict(error=f'{type(error).__name__}: {error}')
                    finish(spec,result)
    if source_fingerprint()!=frozen['source']:raise ValueError('Source changed during study')
    return write_comparison(directory,manifest,state)


def verify_study(study_dir=DEFAULT_STUDY_DIR):
    directory=Path(study_dir);path=directory/'split_manifest.json'
    manifest=json.loads(path.read_text());state=json.loads((directory/'study_state.json').read_text());frozen=json.loads((directory/'execution_freeze.json').read_text())
    if _sha(path)!=state['manifest_sha256'] or _sha(path)!=frozen['manifest_sha256']:raise ValueError('Manifest hash mismatch')
    if source_fingerprint()!=frozen['source']:raise ValueError('Frozen source differs')
    verify_development_inventory(manifest)
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'])
        if not entry or entry.get('status') not in ('completed','error'):raise ValueError('Incomplete study; verification never launches missing cells')
        if entry.get('source_sha256')!=frozen['source']['sha256']:raise ValueError('Attempt source differs')
        if entry['status']=='completed':_validate_record(entry['run_dir'],spec,entry)
    return dict(verified=True,trials=len(manifest['trials']),source_sha256=frozen['source']['sha256'],legacy_baseline=verify_legacy_baseline())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','evaluate','all','report','verify'))
    parser.add_argument('--study-dir',type=Path,default=DEFAULT_STUDY_DIR)
    parser.add_argument('--cases-json',type=Path)
    parser.add_argument('--seeds',type=int,nargs='+',default=[101,509]);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args(argv)
    cases=json.loads(args.cases_json.read_text()) if args.cases_json else None
    if args.stage=='verify':print(json.dumps(verify_study(args.study_dir),indent=2));return 0
    if args.stage=='prepare':
        manifest,path=ensure_manifest(args.study_dir,cases,args.seeds);freeze(args.study_dir,path)
        print(f'Predeclared {len(manifest["trials"])} task-load probing trials: {path}');return 0
    if args.stage=='report':
        manifest=json.loads((args.study_dir/'split_manifest.json').read_text())
        result=write_comparison(args.study_dir,manifest,json.loads((args.study_dir/'study_state.json').read_text()))
    else:result=run_study(args.study_dir,cases=cases,seeds=args.seeds,workers=args.workers)
    print(json.dumps({key:result[key] for key in ('complete','expected_trials','expected_outcomes_met','physical_successes')},indent=2))
    return 0 if result['complete'] and result['expected_outcomes_met']==result['expected_trials'] else 1

if __name__=='__main__':raise SystemExit(main())
