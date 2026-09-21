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
from .weak_pad_study import _now, _sha, _write, source_fingerprint as base_fingerprint

STRATEGIES=('fixed_probe','adaptive_force_fixed_posture','adaptive_probe')
OUTCOMES=('SUCCESS','SAFE_STOP','RECOVERED_STOP','UNSAFE','INCOMPLETE','INVALID')
DEFAULT_STUDY_DIR=RESULTS_ROOT/'weak_pad'/'study_v2'
DEFAULT_DEVELOPMENT_DIR=RESULTS_ROOT/'weak_pad'/'development_v2'


def _canonical_parameters(parameters):
    """Resolve the runner's defaults before hashing or comparing conditions."""
    from .weak_pad_v2 import run_trial
    signature=inspect.signature(run_trial)
    unknown=set(parameters)-set(signature.parameters)
    if unknown:raise ValueError(f'Unknown runner parameters: {sorted(unknown)}')
    values={key:item.default for key,item in signature.parameters.items()
            if key not in ('strategy','seed','role','headless','output_group')}
    values.update(parameters)
    for key in ('planning_config','initial_state','sensor_config'):
        values[key]=values[key] or {}
    return json.loads(json.dumps(values,allow_nan=False))


def _condition_signature(public,threshold):
    """A new label, policy or seed does not make a new physical condition."""
    from primp_project.planning.load_capacity import CapacityPlanningConfig
    from dataclasses import asdict
    parameters=_canonical_parameters({key:value for key,value in public.items()
        if key not in ('strategy','seed','role','headless','output_group')})
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
    files=base_fingerprint()['files']
    paths=[PROJECT_ROOT/'experiments'/'weak_pad_v2.py',PROJECT_ROOT/'analysis'/'weak_pad_v2.py',
           PROJECT_ROOT/'analysis'/'weak_pad.py',PROJECT_ROOT/'analysis'/'step.py']
    for path in paths:
        if not path.exists():raise ValueError(f'Missing V2 execution/analysis source: {path}')
        files[str(path.relative_to(REPOSITORY_ROOT))]=_sha(path)
    return dict(sha256=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest(),files=files)


def protocol(cases, *, seeds=(17,)):
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
        if any(key in parameters for key in ('strategy','seed','role','output_group','headless')):
            raise ValueError('Case parameters cannot override comparison identity')
        threshold=parameters.get('failure_threshold_n')
        if not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or threshold<=0:
            raise ValueError('A finite positive evaluator-only threshold is required')
        # Round-trip validation rejects nonserializable and nonfinite nested values.
        parameters=_canonical_parameters(parameters)
        strategies=case.get('strategies',list(STRATEGIES))
        if not strategies or len(set(strategies))!=len(strategies) or any(s not in STRATEGIES for s in strategies):
            raise ValueError('Declare distinct recognized matched strategies')
        expected=case.get('expected_outcomes',{})
        for strategy in strategies:
            allowed=expected.get(strategy)
            if not isinstance(allowed,list) or not allowed or any(v not in OUTCOMES for v in allowed):
                raise ValueError('Predeclare expected outcomes for every strategy; do not infer them after results')
            for seed in seeds:
                trials.append(dict(trial_id=f'{case_id}_{strategy}_seed{seed}',case_id=case_id,
                    family=case.get('family','unspecified'),condition_role=case['condition_role'],
                    strategy=strategy,seed=int(seed),role='evaluation',parameters=parameters,
                    expected_outcomes=allowed))
    return dict(version=2,experiment='weak_pad',cases=cases,seeds=list(seeds),trials=trials,
        policy=dict(attempts='One attempt per cell, including failures and interrupted attempts; no silent reruns',
            comparison='Every strategy uses the same movement optimizer, movement freedoms, feasibility limits and force allocation; only probing adaptation differs',
            success='Only actual body-and-foot progress is SUCCESS; SAFE_STOP and RECOVERED_STOP do not count as task completion',
            truth='Hidden pad strength is evaluator-only; sensing, geometry and error bounds are public',
            interpretation='Predeclared engineering cases and declared seeds, not a statistical population or independent samples within each trace',
            holdout='Held-out labels describe condition selection before evaluation; development conditions remain labeled separately'))


def ensure_manifest(directory, cases=None, seeds=(17,), *, development_dir=DEFAULT_DEVELOPMENT_DIR):
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
            raise ValueError('A held-out condition already appeared in development; strategy, scenario label and seed do not establish novelty')
    directory.mkdir(parents=True,exist_ok=True)
    _write(path,dict(expected,created_at=_now(),development_inventory=inventory))
    return json.loads(path.read_text()),path


def freeze(directory,path):
    expected=dict(version=2,manifest_sha256=_sha(path),source=source_fingerprint())
    target=Path(directory)/'execution_freeze.json'
    if target.exists():
        saved=json.loads(target.read_text())
        if {key:saved.get(key) for key in expected}!=expected:raise ValueError('Frozen V2 source or protocol changed')
        return saved
    _write(target,dict(expected,frozen_at=_now()))
    return json.loads(target.read_text())


def _kwargs(spec):
    return dict(spec['parameters'],strategy=spec['strategy'],seed=spec['seed'],role='evaluation')


def _validate_record(run_dir,spec,entry=None):
    run=Path(run_dir);metadata=json.loads((run/'metadata.json').read_text());summary=json.loads((run/'weak_pad_summary.json').read_text())
    if metadata.get('experiment')!='weak_pad' or metadata.get('protocol_version')!=2:
        raise ValueError('Wrong experiment protocol')
    for key in ('strategy','seed','role'):
        if metadata.get(key)!=_kwargs(spec)[key]:raise ValueError(f'Trial identity mismatch: {key}')
    declared=metadata.get('trial_parameters')
    public={key:value for key,value in _kwargs(spec).items() if key!='failure_threshold_n'}
    if declared!=public:raise ValueError('Recorded public trial parameters differ from the predeclared cell')
    actual_threshold=metadata.get('evaluation',{}).get('failure_threshold_n',metadata.get('evaluation',{}).get('failure_load_n'))
    if actual_threshold!=spec['parameters']['failure_threshold_n']:raise ValueError('Evaluator-only capacity differs')
    if not metadata.get('movement_optimizer_id'):raise ValueError('Movement optimizer identity is missing')
    if summary.get('physical_success') is not (summary.get('outcome')=='SUCCESS'):
        raise ValueError('Stops and recovery cannot count as physical success')
    if entry:
        for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','weak_pad_summary.json')):
            if entry.get(key)!=_sha(run/name):raise ValueError(f'Canonical trial changed: {name}')
    return metadata,summary


def _worker(spec,directory,frozen,headless):
    os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
    group=Path(directory)/'trials'/spec['trial_id'];result={}
    try:
        if source_fingerprint()!=frozen['source']:raise ValueError('Source changed before trial')
        from .weak_pad_v2 import run_trial
        run,_=run_trial(**_kwargs(spec),headless=headless,output_group=group)
        result['run_dir']=str(run)
        if source_fingerprint()!=frozen['source']:raise ValueError('Source changed during trial')
    except BaseException as error:
        result.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
        candidates=sorted(group.glob('weak_pad_*')) if group.exists() else []
        if candidates:result['run_dir']=str(candidates[-1])
    return result


def write_comparison(directory,manifest,state):
    directory=Path(directory);rows=[];identities={}
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'],{});summary={}
        if entry.get('status')=='completed':
            metadata,summary=_validate_record(entry['run_dir'],spec,entry)
            identity=(metadata['movement_optimizer_id'],json.dumps(metadata.get('movement_optimizer_settings',{}),sort_keys=True))
            if spec['case_id'] in identities and identities[spec['case_id']]!=identity:
                raise ValueError('Compared strategies changed the movement optimizer or its constraints')
            identities[spec['case_id']]=identity
        rows.append(dict(trial_id=spec['trial_id'],case_id=spec['case_id'],strategy=spec['strategy'],seed=spec['seed'],
            family=spec['family'],condition_role=spec['condition_role'],status=entry.get('status','not_run'),run_dir=entry.get('run_dir'),
            outcome=summary.get('outcome','NO_RESULT'),physical_success=bool(summary.get('physical_success',False)),
            expected_outcome_met=summary.get('outcome') in spec['expected_outcomes'],metrics=summary.get('metrics',{}),error=entry.get('error')))
    result=dict(version=2,complete=all(row['status'] in ('completed','error') for row in rows),expected_trials=len(rows),
        expected_outcomes_met=sum(row['expected_outcome_met'] for row in rows),physical_successes=sum(row['physical_success'] for row in rows),
        trials=rows,paired_optimizer_verified=all(row['status']=='completed' for row in rows),policy=manifest['policy'])
    result['by_strategy']={s:dict(trials=sum(r['strategy']==s for r in rows),
        outcomes={outcome:sum(r['strategy']==s and r['outcome']==outcome for r in rows) for outcome in OUTCOMES},
        no_result=sum(r['strategy']==s and r['outcome']=='NO_RESULT' for r in rows)) for s in STRATEGIES}
    _write(directory/'comparison'/'comparison.json',result)
    columns=('trial_id','condition_role','outcome','physical_success','expected_outcome_met','maximum_certified_force_n',
             'maximum_actual_future_pad_force_n','maximum_forward_com_motion_m','maximum_next_foot_clearance_m',
             'final_forward_com_motion_m','simultaneous_progress_min_forward_m','simultaneous_progress_max_forward_m',
             'simultaneous_progress_hold_s','probe_time_s','additional_probe_count','recovery_unload_delay_s','recovery_stable_hold_s')
    with (directory/'comparison'/'trials.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in rows:
            values=dict(row,**row['metrics']);writer.writerow({key:values.get(key) for key in columns})
    lines=['# Matched weak-pad V2 study','',f"Physical task completions: {result['physical_successes']}/{len(rows)}. Predeclared outcomes matched: {result['expected_outcomes_met']}/{len(rows)}.",'',
        'Every strategy has the same movement optimization freedoms. SAFE_STOP and RECOVERED_STOP remain separate from successful movement.','',
        '| Case / seed | Strategy | Condition | Outcome | Probe s | Extra probes | Recovery hold s |','| --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        m=row['metrics'];lines.append(f"| {row['case_id']} / {row['seed']} | {row['strategy']} | {row['condition_role']} | {row['outcome']} | {m.get('probe_time_s','—')} | {m.get('additional_probe_count','—')} | {m.get('recovery_stable_hold_s','—')} |")
    lines+=['','| Case / strategy / seed | Certified N | Actual future peak N | Final forward mm | Foot lift mm | Simultaneous hold s |',
            '| --- | --- | --- | --- | --- | --- |']
    def number(value,scale=1.):return '—' if value is None else f'{scale*value:.3f}'
    for row in rows:
        m=row['metrics'];lines.append(f"| {row['case_id']} / {row['strategy']} / {row['seed']} | {number(m.get('maximum_certified_force_n'))} | {number(m.get('maximum_actual_future_pad_force_n'))} | {number(m.get('final_forward_com_motion_m'),1000)} | {number(m.get('maximum_next_foot_clearance_m'),1000)} | {number(m.get('simultaneous_progress_hold_s'))} |")
    lines+=['',manifest['policy']['interpretation'], '',manifest['policy']['holdout']]
    (directory/'comparison'/'report.md').write_text('\n'.join(lines)+'\n')
    if result['complete']:_plot_comparison(directory/'comparison'/'comparison.png',rows)
    return result


def _plot_comparison(path,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    order=[]
    for row in rows:
        key=(row['case_id'],row['seed'])
        if key not in order:order.append(key)
    colors={'SUCCESS':'#238b45','SAFE_STOP':'#f1b14b','RECOVERED_STOP':'#4b91c2',
            'UNSAFE':'#bd3039','INVALID':'#a352a3','INCOMPLETE':'#888888','NO_RESULT':'#c9c9c9'}
    short={'SUCCESS':'SUCCESS','SAFE_STOP':'STOP','RECOVERED_STOP':'RECOVERED',
           'UNSAFE':'UNSAFE','INVALID':'INVALID','INCOMPLETE':'INCOMPLETE','NO_RESULT':'NO RESULT'}
    fig,axes=plt.subplots(1,2,figsize=(12,max(4.,.45*len(order)+2.)),constrained_layout=True)
    for row in rows:
        y=order.index((row['case_id'],row['seed']));x=STRATEGIES.index(row['strategy'])
        axes[0].scatter(x,y,s=1200,marker='s',c=colors[row['outcome']],alpha=.9)
        axes[0].text(x,y,short[row['outcome']],ha='center',va='center',fontsize=7,color='black')
        probe=row['metrics'].get('probe_time_s')
        if probe is not None:axes[1].scatter(probe,y+(x-1)*.16,marker=('o','s','^')[x],
            c=('#414141','#527fbb','#8b4e99')[x],s=35)
    axes[0].set_xticks(range(3),['Fixed probe','Force adaptation\nfixed posture','Force + posture\nadaptation'],fontsize=9)
    axes[0].set_yticks(range(len(order)),[f'{case} / seed {seed}' for case,seed in order],fontsize=8)
    axes[0].set_xlim(-.6,2.6);axes[0].set_title('Observed outcome; only green completes the task')
    axes[1].set_yticks(range(len(order)),[]);axes[1].set_xlabel('Recorded probe time (s)')
    axes[1].set_title('Same movement optimizer; different probing policies')
    for x,label in enumerate(('Fixed probe','Force only','Force + posture')):
        axes[1].scatter([],[],marker=('o','s','^')[x],c=('#414141','#527fbb','#8b4e99')[x],label=label)
    axes[1].legend(fontsize=8)
    for ax in axes:ax.set_ylim(len(order)-.5,-.5);ax.grid(alpha=.15)
    fig.suptitle('Matched weak-pad V2 engineering study')
    fig.savefig(path,dpi=170);plt.close(fig)


def run_study(study_dir=DEFAULT_STUDY_DIR,*,cases=None,seeds=(17,),workers=2,headless=True,runner=None):
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
        _write(state_path,state);print(f"WEAK_PAD_V2 {spec['trial_id']}",flush=True)
    def finish(spec,result):
        entry=state['trials'][spec['trial_id']];entry.update(finished_at=_now(),**result)
        entry['status']='error' if result.get('error') else 'completed'
        if entry['status']=='completed':
            try:
                _,summary=_validate_record(entry['run_dir'],spec)
                entry['outcome']=summary['outcome']
                for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','weak_pad_summary.json')):
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
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'])
        if not entry or entry.get('status') not in ('completed','error'):raise ValueError('Incomplete study; verification never launches missing cells')
        if entry.get('source_sha256')!=frozen['source']['sha256']:raise ValueError('Attempt source differs')
        if entry['status']=='completed':_validate_record(entry['run_dir'],spec,entry)
    return dict(verified=True,trials=len(manifest['trials']),source_sha256=frozen['source']['sha256'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','evaluate','all','report','verify'))
    parser.add_argument('--study-dir',type=Path,default=DEFAULT_STUDY_DIR)
    parser.add_argument('--cases-json',type=Path)
    parser.add_argument('--seeds',type=int,nargs='+',default=[17]);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args(argv)
    cases=json.loads(args.cases_json.read_text()) if args.cases_json else None
    if args.stage=='verify':print(json.dumps(verify_study(args.study_dir),indent=2));return 0
    if args.stage=='prepare':
        manifest,path=ensure_manifest(args.study_dir,cases,args.seeds);freeze(args.study_dir,path)
        print(f'Predeclared {len(manifest["trials"])} V2 trials: {path}');return 0
    if args.stage=='report':
        manifest=json.loads((args.study_dir/'split_manifest.json').read_text())
        result=write_comparison(args.study_dir,manifest,json.loads((args.study_dir/'study_state.json').read_text()))
    else:result=run_study(args.study_dir,cases=cases,seeds=args.seeds,workers=args.workers)
    print(json.dumps({key:result[key] for key in ('complete','expected_trials','expected_outcomes_met','physical_successes')},indent=2))
    return 0 if result['complete'] and result['expected_outcomes_met']==result['expected_trials'] else 1

if __name__=='__main__':raise SystemExit(main())
