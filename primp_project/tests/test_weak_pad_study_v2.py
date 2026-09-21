"""Matched-protocol provenance must not retry or hide adverse outcomes."""
import json
from pathlib import Path
import pytest
from primp_project.experiments import weak_pad_study_v2 as study


def cases():
    return [dict(case_id='new_layout',family='geometry',condition_role='held_out',
        parameters=dict(failure_threshold_n=25.,scenario='geometry',initial_probe_force_n=20.,
                        sensor_config={'force_bias_n':.2},initial_state={'body_offset_xy_m':[.005,0.]}),
        expected_outcomes={s:['SUCCESS','SAFE_STOP','RECOVERED_STOP'] for s in study.STRATEGIES})]


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(study,'source_fingerprint',lambda:dict(sha256='frozen',files={}))
    inventory=study.development_inventory
    monkeypatch.setattr(study,'development_inventory',lambda directory=study.DEFAULT_DEVELOPMENT_DIR:
        [] if Path(directory)==study.DEFAULT_DEVELOPMENT_DIR else inventory(directory))


def runner(counter,*,outcome='SAFE_STOP',wrong_seed=False,optimizer_id='common'):
    def run(**kwargs):
        counter.append(kwargs)
        run=Path(kwargs['output_group'])/'weak_pad_test';run.mkdir(parents=True)
        public={k:v for k,v in kwargs.items() if k not in ('failure_threshold_n','output_group','headless')}
        metadata=dict(experiment='weak_pad',protocol_version=2,strategy=kwargs['strategy'],role=kwargs['role'],
            seed=kwargs['seed']+int(wrong_seed),trial_parameters=public,
            movement_optimizer_id=optimizer_id,movement_optimizer_settings={'lateral_freedom':.08},
            evaluation={'failure_threshold_n':kwargs['failure_threshold_n']})
        summary=dict(outcome=outcome,physical_success=outcome=='SUCCESS',metrics={})
        (run/'metadata.json').write_text(json.dumps(metadata));(run/'signals.npz').write_bytes(b'unchanged signals')
        (run/'weak_pad_summary.json').write_text(json.dumps(summary))
        return run,summary
    return run


def test_declared_cases_are_paired_and_numerics_are_not_chosen_by_module():
    with pytest.raises(ValueError,match='explicitly'):study.protocol(None)
    p=study.protocol(cases(),seeds=(17,29))
    assert len(p['trials'])==6
    assert {t['condition_role'] for t in p['trials']}=={'held_out'}
    assert all(t['parameters']==p['trials'][0]['parameters'] for t in p['trials'])


def test_completed_safe_stops_resume_without_rerun_or_success_credit(tmp_path,frozen):
    counter=[]
    first=study.run_study(tmp_path,cases=cases(),workers=1,runner=runner(counter))
    second=study.run_study(tmp_path,workers=1,runner=runner(counter))
    assert len(counter)==3 and first==second
    assert second['physical_successes']==0 and second['expected_outcomes_met']==3
    assert study.verify_study(tmp_path)['trials']==3


def test_wrong_seed_and_failed_attempt_stay_visible_without_retry(tmp_path,frozen):
    counter=[]
    report=study.run_study(tmp_path,cases=cases(),workers=1,runner=runner(counter,outcome='SUCCESS',wrong_seed=True))
    assert report['complete'] and report['physical_successes']==0
    assert all(row['status']=='error' for row in report['trials'])
    study.run_study(tmp_path,workers=1,runner=runner(counter))
    assert len(counter)==3


def test_verify_never_creates_manifest_or_launches_pending_cells(tmp_path,frozen):
    with pytest.raises(FileNotFoundError):study.verify_study(tmp_path/'missing')
    assert not (tmp_path/'missing').exists()
    _,path=study.ensure_manifest(tmp_path,cases());study.freeze(tmp_path,path)
    study._write(tmp_path/'study_state.json',dict(manifest_sha256=study._sha(path),trials={}))
    with pytest.raises(ValueError,match='Incomplete'):study.verify_study(tmp_path)


def test_tampered_raw_hash_blocks_resume_and_report(tmp_path,frozen):
    result=study.run_study(tmp_path,cases=cases(),workers=1,runner=runner([]))
    (Path(result['trials'][0]['run_dir'])/'signals.npz').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='Canonical'):study.verify_study(tmp_path)
    with pytest.raises(ValueError,match='Canonical'):study.run_study(tmp_path,workers=1,runner=runner([]))


def test_movement_optimizer_cannot_differ_between_matched_variants(tmp_path,frozen):
    counter=[]
    def varied(**kwargs):return runner(counter,optimizer_id=kwargs['strategy'])(**kwargs)
    with pytest.raises(ValueError,match='movement optimizer'):study.run_study(tmp_path,cases=cases(),workers=1,runner=varied)


def test_changed_condition_cannot_reuse_existing_manifest(tmp_path,frozen):
    study.ensure_manifest(tmp_path,cases())
    changed=cases();changed[0]['parameters']['sensor_config']['force_bias_n']=.4
    with pytest.raises(ValueError,match='Protocol changed'):study.ensure_manifest(tmp_path,changed)


def test_unsafe_and_recovered_outcomes_never_count_as_success(tmp_path,frozen):
    counter=[]
    def different(**kwargs):
        outcome={'fixed_probe':'SAFE_STOP','adaptive_force_fixed_posture':'UNSAFE','adaptive_probe':'RECOVERED_STOP'}[kwargs['strategy']]
        return runner(counter,outcome=outcome)(**kwargs)
    result=study.run_study(tmp_path,cases=cases(),workers=1,runner=different)
    assert result['physical_successes']==0 and result['expected_outcomes_met']==2
    assert result['by_strategy']['adaptive_probe']['outcomes']['RECOVERED_STOP']==1
    assert result['by_strategy']['adaptive_force_fixed_posture']['outcomes']['UNSAFE']==1


def test_new_seed_or_label_does_not_turn_development_condition_into_holdout(tmp_path,frozen):
    development=tmp_path/'development';run=development/'weak_pad_old';run.mkdir(parents=True)
    parameters=study._canonical_parameters(cases()[0]['parameters'])
    threshold=parameters.pop('failure_threshold_n')
    parameters.update(strategy='adaptive_probe',seed=99,role='development',scenario='earlier_label')
    (run/'metadata.json').write_text(json.dumps(dict(protocol_version=2,role='development',
        trial_parameters=parameters,evaluation={'failure_load_n':threshold})))
    (run/'signals.npz').write_bytes(b'earlier physical data')
    with pytest.raises(ValueError,match='already appeared'):
        study.ensure_manifest(tmp_path/'study',cases(),seeds=(17,),development_dir=development)
    changed=cases();changed[0]['condition_role']='development'
    manifest,_=study.ensure_manifest(tmp_path/'study',changed,development_dir=development)
    assert len(manifest['development_inventory'])==1
    assert manifest['development_inventory'][0]['signals_sha256']==study._sha(run/'signals.npz')
