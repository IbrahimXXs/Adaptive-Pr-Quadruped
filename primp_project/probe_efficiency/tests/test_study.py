"""Retain every paired attempt and the original frozen V2 study."""
import json
from pathlib import Path
import pytest
from primp_project.probe_efficiency import study


def cases():
    return [dict(case_id='capacity51',family='capacity_sweep',condition_role='held_out',
        parameters=dict(failure_threshold_n=51.,sensor_config={'force_bias_n':-.2,'force_noise_n':.6}),
        expected_outcomes={policy:['SUCCESS','SAFE_STOP','RECOVERED_STOP'] for policy in study.POLICIES})]


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(study,'source_fingerprint',lambda:dict(sha256='frozen',files={}))
    monkeypatch.setattr(study,'verify_legacy_baseline',lambda:dict(verified=True,trials=48))
    inventory=study.development_inventory
    monkeypatch.setattr(study,'development_inventory',lambda directory=study.DEFAULT_DEVELOPMENT_DIR:
        [] if Path(directory)==study.DEFAULT_DEVELOPMENT_DIR else inventory(directory))
    monkeypatch.setattr(study,'_plot_comparison',lambda *args:None)


def runner(counter, *, wrong_policy=False, optimizer_id='common'):
    def run(**kwargs):
        counter.append(kwargs)
        directory=Path(kwargs['output_group'])/'weak_pad_fake';directory.mkdir(parents=True)
        public={k:v for k,v in kwargs.items() if k not in ('failure_threshold_n','output_group','headless')}
        public['strategy']='adaptive_probe'
        metadata=dict(experiment='weak_pad',protocol_version=2,strategy='adaptive_probe',study_name='probe_efficiency',
            probe_policy='unknown' if wrong_policy else kwargs['probe_policy'],role=kwargs['role'],seed=kwargs['seed'],
            trial_parameters=public,movement_optimizer_id=optimizer_id,movement_optimizer_settings={'freedom':.08},
            evaluation={'failure_threshold_n':kwargs['failure_threshold_n']})
        summary=dict(outcome='SAFE_STOP',physical_success=False,metrics={})
        (directory/'metadata.json').write_text(json.dumps(metadata));(directory/'signals.npz').write_bytes(b'raw')
        for name in ('weak_pad_summary.json','probe_efficiency_summary.json'):
            (directory/name).write_text(json.dumps(summary))
        return directory,summary
    return run


def test_every_capacity_has_two_policies_identical_parameters_and_seeds():
    protocol=study.protocol(cases(),seeds=(211,907))
    assert len(protocol['trials'])==4
    assert all(row['parameters']==protocol['trials'][0]['parameters'] for row in protocol['trials'])
    assert {row['probe_policy'] for row in protocol['trials']}==set(study.POLICIES)
    unpaired=cases();unpaired[0]['probe_policies']=['minimum_sufficient']
    with pytest.raises(ValueError,match='both policies'):study.protocol(unpaired)


def test_resume_never_reruns_completed_stops(tmp_path,frozen):
    counter=[]
    a=study.run_study(tmp_path,cases=cases(),seeds=(211,),workers=1,runner=runner(counter))
    b=study.run_study(tmp_path,workers=1,runner=runner(counter))
    assert len(counter)==2 and a==b and a['physical_successes']==0
    assert study.verify_study(tmp_path)['legacy_baseline']['verified']


def test_failed_identity_stays_in_denominator_and_is_not_retried(tmp_path,frozen):
    counter=[]
    report=study.run_study(tmp_path,cases=cases(),seeds=(211,),workers=1,runner=runner(counter,wrong_policy=True))
    assert report['expected_trials']==2 and report['physical_successes']==0
    assert all(row['status']=='error' for row in report['trials'])
    study.run_study(tmp_path,workers=1,runner=runner(counter));assert len(counter)==2


@pytest.mark.parametrize('filename',['signals.npz','metadata.json','weak_pad_summary.json','probe_efficiency_summary.json'])
def test_either_summary_and_raw_data_are_immutable(tmp_path,frozen,filename):
    report=study.run_study(tmp_path,cases=cases(),seeds=(211,),workers=1,runner=runner([]))
    path=Path(report['trials'][0]['run_dir'])/filename
    if filename=='signals.npz':path.write_bytes(b'altered')
    else:
        values=json.loads(path.read_text());values['tampered']=True;path.write_text(json.dumps(values))
    with pytest.raises(ValueError,match='Canonical'):study.verify_study(tmp_path)


def test_optimizer_changes_are_rejected(tmp_path,frozen):
    def changed(**kwargs):return runner([],optimizer_id=kwargs['probe_policy'])(**kwargs)
    with pytest.raises(ValueError,match='movement optimizer'):
        study.run_study(tmp_path,cases=cases(),seeds=(211,),workers=1,runner=changed)


def test_heldout_label_requires_new_physical_condition_not_new_noise_seed(tmp_path,frozen):
    root=tmp_path/'development';directory=root/'old';directory.mkdir(parents=True)
    public=study._canonical_parameters(cases()[0]['parameters']);threshold=public.pop('failure_threshold_n')
    public.update(strategy='adaptive_probe',probe_policy='maximum_feasible',seed=17,role='development',scenario='otherlabel')
    (directory/'metadata.json').write_text(json.dumps(dict(protocol_version=2,role='development',
        trial_parameters=public,evaluation={'failure_threshold_n':threshold})))
    (directory/'signals.npz').write_bytes(b'old')
    with pytest.raises(ValueError,match='already appeared'):
        study.ensure_manifest(tmp_path/'formal',cases(),seeds=(907,),development_dir=root)


def test_verify_does_not_create_or_execute_pending_study(tmp_path,frozen):
    with pytest.raises(FileNotFoundError):study.verify_study(tmp_path/'missing')
    assert not (tmp_path/'missing').exists()


def test_original_v2_source_and_results_still_match_snapshot():
    result=study.verify_legacy_baseline()
    assert result['verified'] and result['trials']==48 and result['canonical_files']==147
