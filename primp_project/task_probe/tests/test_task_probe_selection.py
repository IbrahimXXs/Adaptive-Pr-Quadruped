"""One fixed scalar is selected on the complete declared development grid."""
import copy
import json
from pathlib import Path
import pytest
from primp_project.task_probe import study


def make_protocol(tmp_path):
    protocol=dict(version=1,candidate_forces_n=[50.57,52.5,53.],rule=study.SELECTION_RULE,
        tasks=[dict(task_id=task,parameters=dict(failure_threshold_n=62.,seed=101,
            planning_config={'forward_progress_m':progress})) for task,progress in [('easy',.034),('hard',.045)]])
    path=tmp_path/'protocol.json';path.write_text(json.dumps(protocol));return path,protocol


def make_run(tmp_path,task,force,*,outcome='SUCCESS',damaged=False,seed=101,role='development'):
    from primp_project.task_probe.runner import run_trial
    import inspect
    public={key:value.default for key,value in inspect.signature(run_trial).parameters.items()
        if key not in ('failure_threshold_n','output_group','headless')}
    public.update(strategy='adaptive_probe',probe_policy='fixed_force',fixed_probe_force_n=force,
        role=role,seed=seed,planning_config=task['parameters']['planning_config'],
        sensor_config={},initial_state={},probe_offset_xy_m=[0.,0.])
    directory=tmp_path/f"{task['task_id']}_{force}";directory.mkdir()
    metadata=dict(study_name='task_probe',role=role,probe_policy='fixed_force',fixed_probe_force_n=force,
        trial_parameters=public,evaluation={'failure_threshold_n':62.})
    summary=dict(outcome=outcome,physical_success=outcome=='SUCCESS',metrics={'pad_damaged':damaged})
    (directory/'metadata.json').write_text(json.dumps(metadata));(directory/'signals.npz').write_bytes(b'fixed raw evidence')
    (directory/'task_probe_summary.json').write_text(json.dumps(summary))
    return directory


def grid(tmp_path):
    path,p=make_protocol(tmp_path)
    runs=[make_run(tmp_path,task,force,outcome='SAFE_STOP' if task['task_id']=='hard' and force==50.57 else 'SUCCESS')
        for task in p['tasks'] for force in p['candidate_forces_n']]
    return path,p,runs


def test_selects_smallest_force_succeeding_on_every_declared_task(tmp_path):
    path,p,runs=grid(tmp_path);target=tmp_path/'selected.json'
    selected=study.select_fixed_force(path,runs,target)
    assert selected['selected_force_n']==52.5
    assert len(selected['candidate_trials'])==6
    assert study.verify_selection(selected)['verified']
    assert study.select_fixed_force(path,runs,target)==selected


@pytest.mark.parametrize('mutation',['omit_failure','duplicate','wrong_seed','evaluation_leak','alter_summary','alter_protocol'])
def test_selection_cannot_hide_cells_change_seed_or_use_evaluation_results(tmp_path,mutation):
    path,p,runs=grid(tmp_path)
    if mutation=='omit_failure':runs=runs[1:]
    elif mutation=='duplicate':runs[-1]=runs[0]
    elif mutation in ('wrong_seed','evaluation_leak'):
        file=runs[0]/'metadata.json';m=json.loads(file.read_text())
        if mutation=='wrong_seed':m['trial_parameters']['seed']=907
        else:m['role']=m['trial_parameters']['role']='evaluation'
        file.write_text(json.dumps(m))
    if mutation in ('alter_summary','alter_protocol'):
        selected=study.select_fixed_force(path,runs,tmp_path/'selected.json')
        changed=runs[0]/'task_probe_summary.json' if mutation=='alter_summary' else path
        values=json.loads(changed.read_text());values['tampered']=True;changed.write_text(json.dumps(values))
        with pytest.raises(ValueError):study.verify_selection(selected)
    else:
        with pytest.raises(ValueError):study.select_fixed_force(path,runs,tmp_path/'selected.json')


def cases():
    return [dict(case_id=f'goal{i}',task_id=f'goal{i}',family='progress',condition_role='held_out',
        parameters=dict(failure_threshold_n=55.,fixed_probe_force_n=52.5,planning_config={'forward_progress_m':goal}),
        expected_outcomes={policy:['SUCCESS','SAFE_STOP','RECOVERED_STOP'] for policy in study.POLICIES})
        for i,goal in enumerate((.036,.044))]


def test_fixed_force_cannot_be_retuned_per_task_or_selected_after_evaluation():
    p=study.protocol(cases(),seeds=(311,1201),selection={'selected_force_n':52.5})
    assert len(p['trials'])==8 and {r['parameters']['fixed_probe_force_n'] for r in p['trials']}=={52.5}
    changed=cases();changed[1]['parameters']['fixed_probe_force_n']=53.
    with pytest.raises(ValueError,match='constant'):study.protocol(changed)
    with pytest.raises(ValueError,match='differs'):study.protocol(cases(),selection={'selected_force_n':53.})


def test_evaluation_manifest_requires_verified_completed_development_selection(tmp_path):
    with pytest.raises(ValueError,match='completed development selection'):
        study.ensure_manifest(tmp_path/'formal',cases())
    path,p,runs=grid(tmp_path);selected=tmp_path/'selected.json';study.select_fixed_force(path,runs,selected)
    m,_=study.ensure_manifest(tmp_path/'formal',cases(),selection_path=selected,development_dir=tmp_path/'none')
    assert m['fixed_force_selection']['selected_force_n']==52.5
    assert len(m['fixed_force_selection']['candidate_trials'])==6


def test_predecessor_studies_and_every_canonical_record_are_unchanged():
    result=study.verify_legacy_baseline()
    assert result['verified'] and result['trials']==32 and result['canonical_files']==131
    assert result['original_v2']['trials']==48 and result['original_v2']['canonical_files']==147


def test_formal_runner_freezes_selection_retains_stops_and_never_retries(tmp_path,monkeypatch):
    path,p,runs=grid(tmp_path);selected=tmp_path/'selected.json';study.select_fixed_force(path,runs,selected)
    monkeypatch.setattr(study,'source_fingerprint',lambda:dict(sha256='frozen',files={}))
    monkeypatch.setattr(study,'_plot_comparison',lambda *args:None)
    calls=[]
    def runner(**kwargs):
        calls.append(kwargs);directory=Path(kwargs['output_group'])/'weak_pad_fake';directory.mkdir(parents=True)
        public={k:v for k,v in kwargs.items() if k not in ('failure_threshold_n','headless','output_group')}
        public['strategy']='adaptive_probe'
        metadata=dict(experiment='weak_pad',study_name='task_probe',protocol_version=2,strategy='adaptive_probe',
            probe_policy=kwargs['probe_policy'],seed=kwargs['seed'],role='evaluation',trial_parameters=public,
            movement_optimizer_id='same',movement_optimizer_settings={},evaluation={'failure_threshold_n':kwargs['failure_threshold_n']})
        summary=dict(outcome='SAFE_STOP',physical_success=False,metrics={})
        (directory/'metadata.json').write_text(json.dumps(metadata));(directory/'signals.npz').write_bytes(b'immutable')
        for name in ('task_probe_summary.json','weak_pad_summary.json'):(directory/name).write_text(json.dumps(summary))
        return directory,summary
    a=study.run_study(tmp_path/'formal',cases=cases(),seeds=(311,),selection_path=selected,runner=runner,workers=1)
    b=study.run_study(tmp_path/'formal',runner=runner,workers=1)
    assert a==b and len(calls)==4 and a['physical_successes']==0
    assert study.verify_study(tmp_path/'formal')['verified']
    assert a['fixed_force_selection']['selected_force_n']==52.5
    one=Path(a['trials'][0]['run_dir'])/'signals.npz';one.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='Canonical'):study.verify_study(tmp_path/'formal')
