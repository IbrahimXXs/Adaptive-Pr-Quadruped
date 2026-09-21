"""Predeclared weak-pad comparisons with immutable attempts and distinct outcomes."""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import math
import os
from pathlib import Path
import re
import shutil
import traceback

from primp_project import PROJECT_ROOT, REPOSITORY_ROOT, RESULTS_ROOT

DEFAULT_STUDY_DIR = RESULTS_ROOT/'weak_pad'/'study'
DEFAULT_CASES = (
    dict(case_id='capacity25_probe20', failure_threshold_n=25., probe_command_limit_n=20., strategies=['unaware','conservative','adaptive']),
    dict(case_id='capacity25_probe22', failure_threshold_n=25., probe_command_limit_n=22., strategies=['unaware','conservative','adaptive']),
    dict(case_id='capacity27_probe24', failure_threshold_n=27., probe_command_limit_n=24., strategies=['unaware','conservative','adaptive']),
    dict(case_id='capacity35_probe12', failure_threshold_n=35., probe_command_limit_n=12., strategies=['conservative','adaptive']),
)
EXPECTED = {'unaware':'PROBLEM_COLLAPSE','conservative':'SAFE_STOP','adaptive':'SUCCESS'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def source_fingerprint():
    """Freeze execution code separately from independent posthoc analysis."""
    paths=[]
    for folder in ('control','environment','recording','planning'):
        paths.extend((PROJECT_ROOT/folder).glob('*.py'))
    paths.extend([PROJECT_ROOT/'experiments'/'weak_pad.py', REPOSITORY_ROOT/'simulation'/'simulation.py',
                  REPOSITORY_ROOT/'quadruped_pympc'/'config.py',
                  REPOSITORY_ROOT/'quadruped_pympc'/'controllers'/'gradient'/'nominal'/'centroidal_nmpc_nominal.py'])
    files={str(path.relative_to(REPOSITORY_ROOT)):_sha(path) for path in sorted(set(paths)) if path.name!='catalog.py'}
    digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(sha256=digest, files=files)


def protocol(cases=None, *, seeds=(17,), requested_probe_force_n=45., measurement_reserve_n=1., tracking_reserve_n=8.):
    cases=list(DEFAULT_CASES if cases is None else cases)
    if not cases or len({case['case_id'] for case in cases})!=len(cases):
        raise ValueError('Study cases require distinct nonempty case IDs')
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError('Seeds must be nonempty and unique')
    if any(isinstance(seed,bool) or int(seed)!=seed or not 0<=seed<2**32 for seed in seeds):
        raise ValueError('Seeds must be nonnegative 32-bit integers')
    if any(not math.isfinite(value) or value<=0 for value in (requested_probe_force_n,measurement_reserve_n,tracking_reserve_n)):
        raise ValueError('Shared force requests and reserves must be finite and positive')
    trials=[]
    for case in cases:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',str(case['case_id'])):
            raise ValueError('Case IDs must be safe simple names')
        if any(not math.isfinite(float(case[key])) or float(case[key])<=0 for key in ('failure_threshold_n','probe_command_limit_n')):
            raise ValueError('Pad thresholds and probe commands must be finite and positive')
        if not case['strategies'] or len(set(case['strategies']))!=len(case['strategies']) or any(s not in EXPECTED for s in case['strategies']):
            raise ValueError('Each case must declare distinct recognized strategies')
        for seed in seeds:
            for strategy in case['strategies']:
                trials.append(dict(trial_id=f"{case['case_id']}_{strategy}_seed{seed}",case_id=case['case_id'],
                    strategy=strategy, failure_threshold_n=float(case['failure_threshold_n']),
                    probe_command_limit_n=float(case['probe_command_limit_n']),seed=int(seed),
                    requested_probe_force_n=float(requested_probe_force_n),measurement_reserve_n=float(measurement_reserve_n),
                    tracking_reserve_n=float(tracking_reserve_n),role='evaluation',expected_outcome=EXPECTED[strategy]))
    return dict(version=1,experiment='weak_pad',cases=cases,seeds=list(seeds),trials=trials,
        policy=dict(attempts='One recorded attempt per declared cell; failed/interrupted attempts remain visible and are never silently replaced',
            comparison='Same physical pad and controller per paired case; declared strategy and force-allocation changes only',
            awareness='Unaware retains original contact-confirmation/reload behavior; it does not perform a capacity probe',
            success='Only >=30 mm simultaneous body advance and >=20 mm actual next-foot lift sustained >=1 s with certified loading is physical SUCCESS',
            expected_outcomes='PROBLEM_COLLAPSE and SAFE_STOP can validate their hypotheses but are not successful task completion',
            truth_boundary='Failure threshold is simulator/evaluator input only; capacity planning uses measured load evidence',
            interpretation='Small deterministic engineering comparison with explicit development-selected conditions; no statistical generalization claim'))


def ensure_manifest(study_dir=DEFAULT_STUDY_DIR, *, cases=None, seeds=(17,)):
    directory=Path(study_dir).resolve();directory.mkdir(parents=True,exist_ok=True)
    path=directory/'split_manifest.json'
    expected=protocol(cases,seeds=seeds)
    if path.exists():
        saved=json.loads(path.read_text())
        if {key:saved.get(key) for key in expected}!=expected:
            raise ValueError('Study protocol changed; preserve this study and choose a new directory')
    else:
        _write(path,dict(expected,created_at=_now()))
    return json.loads(path.read_text()),path


def freeze_execution(directory, manifest_path):
    directory=Path(directory)
    expected=dict(version=1,manifest_sha256=_sha(manifest_path),executor=source_fingerprint())
    path=directory/'execution_freeze.json'
    if path.exists():
        saved=json.loads(path.read_text())
        if {key:saved.get(key) for key in expected}!=expected:
            raise ValueError('Executor or manifest changed after study freeze')
        return saved
    _write(path,dict(expected,frozen_at=_now(),initial_analyzer_sha256=_sha(PROJECT_ROOT/'analysis'/'weak_pad.py')))
    return json.loads(path.read_text())


def _validate_record(run_dir,spec,entry=None):
    directory=Path(run_dir)
    metadata=json.loads((directory/'metadata.json').read_text())
    summary=json.loads((directory/'weak_pad_summary.json').read_text())
    if metadata.get('experiment')!='weak_pad' or metadata.get('role')!='evaluation' or metadata.get('strategy')!=spec['strategy']:
        raise ValueError('Trial identity differs from the predeclared cell')
    if metadata.get('seed')!=spec['seed']:raise ValueError('Trial seed differs from the predeclared cell')
    for key in ('requested_probe_force_n','probe_command_limit_n','tracking_reserve_n'):
        if abs(float(metadata[key])-spec[key])>1e-12:raise ValueError(f'Trial parameter differs: {key}')
    if abs(float(metadata['sensor_force_reserve_n'])-spec['measurement_reserve_n'])>1e-12:
        raise ValueError('Sensor-force reserve differs')
    threshold=metadata['evaluation'].get('failure_threshold_n',metadata['evaluation'].get('failure_load_n'))
    if abs(float(threshold)-spec['failure_threshold_n'])>1e-12:raise ValueError('Simulator threshold differs')
    if summary.get('physical_success') is not (summary.get('outcome')=='SUCCESS'):
        raise ValueError('Summary falsely counts a stop/collapse as physical success')
    if summary.get('expected_outcome_met') is not (summary.get('outcome')==spec['expected_outcome']):
        raise ValueError('Expected-outcome label is inconsistent')
    if entry:
        for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','weak_pad_summary.json')):
            if entry.get(key)!=_sha(directory/name):raise ValueError(f'Canonical trial changed: {name}')
    return summary


def _worker(spec, directory, frozen, headless):
    os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
    directory=Path(directory);group=directory/'trials'/spec['trial_id']
    output={}
    try:
        if source_fingerprint()!=frozen['executor']:raise ValueError('Executor changed before native trial')
        from primp_project.experiments.weak_pad import run_trial
        kwargs={key:value for key,value in spec.items() if key not in ('trial_id','case_id','expected_outcome')}
        run_dir,summary=run_trial(**kwargs,headless=headless,output_group=group)
        output.update(run_dir=str(run_dir),summary=summary)
        if source_fingerprint()!=frozen['executor']:raise ValueError('Executor changed during native trial')
        output['executor_sha256']=frozen['executor']['sha256']
    except BaseException as error:
        output['error']=f'{type(error).__name__}: {error}'
        output['traceback']=traceback.format_exc()
        candidates=sorted(group.glob('weak_pad_*')) if group.exists() else []
        if candidates:output['run_dir']=str(candidates[-1])
    return output


def write_comparison(directory, manifest, state):
    directory=Path(directory);rows=[]
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'],{})
        summary={}
        if entry.get('run_dir') and (Path(entry['run_dir'])/'weak_pad_summary.json').exists():
            if entry.get('status')=='completed':summary=_validate_record(entry['run_dir'],spec,entry)
        rows.append(dict(parameters=spec,status=entry.get('status','not_run'),run_dir=entry.get('run_dir'),
            error=entry.get('error'),outcome=summary.get('outcome','NO_RESULT'),
            expected_outcome_met=bool(summary.get('expected_outcome_met',False)),
            physical_success=bool(summary.get('physical_success',False)),metrics=summary.get('metrics',{})))
    by_strategy={strategy:dict(trials=sum(row['parameters']['strategy']==strategy for row in rows),
        expected_outcomes_met=sum(row['expected_outcome_met'] for row in rows if row['parameters']['strategy']==strategy),
        physical_successes=sum(row['physical_success'] for row in rows if row['parameters']['strategy']==strategy)) for strategy in EXPECTED}
    report=dict(version=1,complete=all(row['status'] in ('completed','error') for row in rows),
        expected_trials=len(rows),expected_outcomes_met=sum(row['expected_outcome_met'] for row in rows),
        physical_successes=sum(row['physical_success'] for row in rows),by_strategy=by_strategy,trials=rows,
        interpretation=manifest['policy']['interpretation'])
    _write(directory/'comparison'/'comparison.json',report)
    text=['# Weak-pad comparison','',f"Expected outcomes validated: {report['expected_outcomes_met']}/{len(rows)}. Physical task completions: {report['physical_successes']}/{len(rows)}.",
        '', 'Collapsing under an unverified transfer and conservatively stopping are separate outcomes, not successful movement.', '',
        '| Case | Strategy | Outcome | Expected outcome met | Physical success | Certified N | Peak future N | Forward mm | Lift mm | Hold s |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    def fmt(value, scale=1.):return '—' if value is None else f'{value*scale:.3f}'
    for row in rows:
        m=row['metrics'];spec=row['parameters']
        text.append(f"| {spec['case_id']} | {spec['strategy']} | {row['outcome']} | {row['expected_outcome_met']} | {row['physical_success']} | {fmt(m.get('maximum_certified_force_n'))} | {fmt(m.get('maximum_actual_future_pad_force_n'))} | {fmt(m.get('maximum_forward_com_motion_m'),1000)} | {fmt(m.get('maximum_next_foot_clearance_m'),1000)} | {fmt(m.get('simultaneous_progress_hold_s'))} |")
    text+=['',manifest['policy']['interpretation']]
    (directory/'comparison'/'report.md').write_text('\n'.join(text)+'\n')
    with (directory/'comparison'/'trials.csv').open('w',newline='') as stream:
        fields=['case_id','strategy','failure_threshold_n','probe_command_limit_n','seed','outcome','expected_outcome_met','physical_success',
                'maximum_certified_force_n','maximum_actual_future_pad_force_n','maximum_forward_com_motion_m','maximum_next_foot_clearance_m','simultaneous_progress_hold_s','maximum_pad_sink_m']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            merged=dict(row['parameters'],**row['metrics'],outcome=row['outcome'],expected_outcome_met=row['expected_outcome_met'],physical_success=row['physical_success'])
            writer.writerow({name:merged.get(name) for name in fields})
    if rows and all(row['status'] in ('completed','error') for row in rows):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        figure,axes=plt.subplots(1,3,figsize=(15,6),constrained_layout=True)
        labels=[f"{row['parameters']['case_id']}\n{row['parameters']['strategy']}" for row in rows]
        y=np.arange(len(rows));colors={'SUCCESS':'tab:green','SAFE_STOP':'tab:orange','PROBLEM_COLLAPSE':'tab:red'}
        axes[0].scatter([1]*len(rows),y,c=[colors.get(row['outcome'],'gray') for row in rows],s=70)
        for i,row in enumerate(rows):axes[0].text(1.03,i,row['outcome'],va='center',fontsize=8)
        axes[0].set_yticks(y,labels,fontsize=7);axes[0].set_xticks([]);axes[0].set_xlim(.96,1.35);axes[0].set_title('Distinct observed outcomes')
        for i,row in enumerate(rows):
            m=row['metrics'];truth=row['parameters']['failure_threshold_n']
            axes[1].scatter(truth,i,color='tab:red',marker='|',s=100)
            if m.get('maximum_actual_future_pad_force_n') is not None:axes[1].scatter(m['maximum_actual_future_pad_force_n'],i,color='black',s=25)
            if m.get('maximum_certified_force_n') is not None:axes[1].scatter(m['maximum_certified_force_n'],i,color='tab:blue',marker='x',s=40)
            if m.get('maximum_forward_com_motion_m') is not None:axes[2].scatter(1000*m['maximum_forward_com_motion_m'],i,color='tab:purple',s=25)
            if m.get('maximum_next_foot_clearance_m') is not None:axes[2].scatter(1000*m['maximum_next_foot_clearance_m'],i,color='tab:cyan',marker='x',s=40)
        axes[1].set(xlabel='Force (N)',title='Black: actual future peak\nBlue ×: certified; red |: hidden threshold')
        axes[2].axvline(30,color='tab:purple',linestyle='--',alpha=.5);axes[2].axvline(20,color='tab:cyan',linestyle='--',alpha=.5)
        axes[2].set(xlabel='Measured displacement (mm)',title='Purple: forward body progress\nCyan ×: next-foot clearance')
        for ax in axes:ax.invert_yaxis();ax.grid(alpha=.15)
        for ax in axes[1:]:ax.set_yticks(y,[])
        figure.suptitle('Weak-pad study: an expected collapse or safe stop is not task completion')
        figure.savefig(directory/'comparison'/'comparison.png',dpi=165);plt.close(figure)
    return report


def run_study(study_dir=DEFAULT_STUDY_DIR, *, cases=None, seeds=(17,), workers=2, headless=True, runner=None):
    directory=Path(study_dir).resolve()
    manifest,path=ensure_manifest(directory,cases=cases,seeds=seeds)
    frozen=freeze_execution(directory,path)
    state_path=directory/'study_state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else dict(version=1,manifest_sha256=_sha(path),trials={})
    if state['manifest_sha256']!=_sha(path):raise ValueError('Study state references a different manifest')
    pending=[]
    for spec in manifest['trials']:
        old=state['trials'].get(spec['trial_id'])
        if old:
            if old.get('status')=='running':raise ValueError('Interrupted attempt remains preserved; use a new study after review')
            if old.get('executor_sha256')!=frozen['executor']['sha256']:raise ValueError('Recorded attempt used different execution source')
            if old.get('status')=='completed':_validate_record(old['run_dir'],spec,old)
            continue
        pending.append(spec)
    def reserve(spec):
        state['trials'][spec['trial_id']]=dict(parameters=spec,status='running',started_at=_now(),executor_sha256=frozen['executor']['sha256'])
        _write(state_path,state)
        print(f"WEAK_PAD {spec['trial_id']}",flush=True)
    def finish(spec,result):
        entry=state['trials'][spec['trial_id']]
        entry.update(finished_at=_now(),status='error' if result.get('error') else 'completed')
        if result.get('run_dir'):entry['run_dir']=result['run_dir']
        if result.get('error'):entry.update(error=result['error'],traceback=result.get('traceback'))
        else:
            try:
                summary=_validate_record(result['run_dir'],spec)
                entry.update(outcome=summary['outcome'],expected_outcome_met=summary['expected_outcome_met'],physical_success=summary['physical_success'])
                for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','weak_pad_summary.json')):
                    entry[key]=_sha(Path(result['run_dir'])/name)
                entry['analyzer_sha256']=summary.get('analyzer_sha256')
            except Exception as error:entry.update(status='error',error=f'{type(error).__name__}: {error}')
        _write(state_path,state);write_comparison(directory,manifest,state)
        print(f"{entry['status']}: {spec['trial_id']} → {entry.get('outcome',entry.get('error'))}",flush=True)
    if runner is not None:
        if workers!=1:raise ValueError('Injected test runners require serial execution')
        for spec in pending:
            reserve(spec)
            try:
                kwargs={key:value for key,value in spec.items() if key not in ('trial_id','case_id','expected_outcome')}
                run_dir,summary=runner(**kwargs,headless=headless,output_group=directory/'trials'/spec['trial_id'])
                result=dict(run_dir=str(run_dir),summary=summary)
            except Exception as error:result=dict(error=f'{type(error).__name__}: {error}')
            finish(spec,result)
    elif pending:
        if workers not in (1,2,3):raise ValueError('Use one to three native workers')
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as executor:
            active={};queue=iter(pending)
            while True:
                while len(active)<workers:
                    spec=next(queue,None)
                    if spec is None:break
                    reserve(spec)
                    active[executor.submit(_worker,spec,str(directory),frozen,headless)]=spec
                if not active:break
                done,_=wait(active,return_when=FIRST_COMPLETED)
                for future in done:
                    spec=active.pop(future)
                    try:result=future.result()
                    except BaseException as error:result=dict(error=f'{type(error).__name__}: {error}')
                    finish(spec,result)
    if source_fingerprint()!=frozen['executor']:raise ValueError('Executor differs after study')
    return write_comparison(directory,manifest,state)


def verify_study(study_dir=DEFAULT_STUDY_DIR):
    """Read-only verification; never creates a manifest or launches missing cells."""
    directory=Path(study_dir).resolve()
    manifest_path=directory/'split_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    state=json.loads((directory/'study_state.json').read_text())
    frozen=json.loads((directory/'execution_freeze.json').read_text())
    if frozen['manifest_sha256']!=_sha(manifest_path) or state['manifest_sha256']!=_sha(manifest_path):
        raise ValueError('Manifest provenance differs')
    if source_fingerprint()!=frozen['executor']:raise ValueError('Executor differs from the frozen study')
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'])
        if not entry or entry.get('status') not in ('completed','error'):
            raise ValueError('Study is incomplete; verification does not launch trials')
        if entry.get('executor_sha256')!=frozen['executor']['sha256']:
            raise ValueError('Recorded executor hash differs')
        if entry['status']=='completed':_validate_record(entry['run_dir'],spec,entry)
    return dict(verified=True,trials=len(manifest['trials']),executor_sha256=frozen['executor']['sha256'])


def reanalyze_study(study_dir=DEFAULT_STUDY_DIR):
    """Archive original summaries, then apply one explicit final analyzer version.

    Raw signals, metadata, executor snapshots and the execution freeze stay
    unchanged. Existing summary hashes remain in each entry's analysis_history.
    """
    directory=Path(study_dir).resolve()
    verify_study(directory)
    from primp_project.analysis.weak_pad import analyze_weak_pad, ANALYZER_SOURCE_SHA256
    manifest=json.loads((directory/'split_manifest.json').read_text())
    state=json.loads((directory/'study_state.json').read_text())
    source=PROJECT_ROOT/'analysis'/'weak_pad.py'
    if _sha(source)!=ANALYZER_SOURCE_SHA256:raise ValueError('Loaded analyzer differs from its source file')
    archive=directory/'validation'/'analysis_versions'/ANALYZER_SOURCE_SHA256
    archive.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,archive/'weak_pad.py')
    for spec in manifest['trials']:
        entry=state['trials'][spec['trial_id']]
        if entry['status']!='completed':continue
        run=Path(entry['run_dir']);summary_path=run/'weak_pad_summary.json'
        old=json.loads(summary_path.read_text())
        if old.get('analyzer_sha256')==ANALYZER_SOURCE_SHA256:continue
        old_hash=_sha(summary_path)
        preserved=directory/'validation'/'original_analysis'/spec['trial_id']/old_hash
        preserved.mkdir(parents=True,exist_ok=True)
        for name in ('weak_pad_summary.json','weak_pad_report.md','weak_pad_overview.png'):
            if (run/name).exists():shutil.copy2(run/name,preserved/name)
        immutable={name:_sha(run/name) for name in ('signals.npz','metadata.json')}
        summary=analyze_weak_pad(run)
        if immutable!={name:_sha(run/name) for name in immutable}:raise RuntimeError('Posthoc analysis changed raw evidence')
        entry.setdefault('analysis_history',[]).append(dict(summary_sha256=old_hash,
            recorded_analyzer_sha256=old.get('analyzer_sha256'),state_analyzer_sha256=entry.get('analyzer_sha256'),
            archived_at=_now(),archive=str(preserved),old_outcome=old.get('outcome')))
        entry.update(summary_sha256=_sha(summary_path),analyzer_sha256=ANALYZER_SOURCE_SHA256,
            outcome=summary['outcome'],expected_outcome_met=summary['expected_outcome_met'],physical_success=summary['physical_success'])
        _write(directory/'study_state.json',state)
    state['final_analysis']=dict(analyzer_sha256=ANALYZER_SOURCE_SHA256,source_archive=str(archive/'weak_pad.py'),reviewed_at=_now())
    _write(directory/'study_state.json',state)
    report=write_comparison(directory,manifest,state)
    verify_study(directory)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','evaluate','all','report','verify','reanalyze'),default='all',nargs='?')
    parser.add_argument('--study-dir',type=Path,default=DEFAULT_STUDY_DIR)
    parser.add_argument('--cases-json',type=Path,help='Optional explicit list of case/strategy sets')
    parser.add_argument('--seeds',type=int,nargs='+',default=[17])
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--human',action='store_true')
    args=parser.parse_args(argv)
    cases=json.loads(args.cases_json.read_text()) if args.cases_json else None
    if args.stage=='verify':
        print(json.dumps(verify_study(args.study_dir),indent=2));return 0
    if args.stage=='reanalyze':
        result=reanalyze_study(args.study_dir)
        print(json.dumps({key:result[key] for key in ('complete','expected_trials','expected_outcomes_met','physical_successes')},indent=2))
        return 0 if result['expected_outcomes_met']==result['expected_trials'] else 1
    if args.stage=='prepare':
        manifest,path=ensure_manifest(args.study_dir,cases=cases,seeds=args.seeds);freeze_execution(args.study_dir,path)
        print(f"Predeclared {len(manifest['trials'])} trials: {path}");return 0
    if args.stage=='report':
        manifest,path=ensure_manifest(args.study_dir,cases=cases,seeds=args.seeds)
        result=write_comparison(args.study_dir,manifest,json.loads((args.study_dir/'study_state.json').read_text()))
    else:
        result=run_study(args.study_dir,cases=cases,seeds=args.seeds,workers=args.workers,headless=not args.human)
    print(json.dumps({key:result[key] for key in ('complete','expected_trials','expected_outcomes_met','physical_successes','by_strategy')},indent=2))
    return 0 if result['complete'] and result['expected_outcomes_met']==result['expected_trials'] else 1


if __name__=='__main__':raise SystemExit(main())
