"""Freeze/resume guards must preserve failures and keep verification read-only."""
import json
from pathlib import Path

import pytest

from primp_project.experiments import weak_pad_study as study


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'source_fingerprint',lambda:dict(sha256='fixed_executor',files={'executor.py':'fixed'}))
    cases=[dict(case_id='pair',failure_threshold_n=25.,probe_command_limit_n=22.,strategies=['conservative','adaptive'])]
    calls=[]
    def runner(**kw):
        calls.append(kw['strategy'])
        p=Path(kw['output_group'])/'recording';p.mkdir(parents=True)
        metadata=dict(experiment='weak_pad',role='evaluation',strategy=kw['strategy'],seed=kw['seed'],
            requested_probe_force_n=kw['requested_probe_force_n'],probe_command_limit_n=kw['probe_command_limit_n'],
            sensor_force_reserve_n=kw['measurement_reserve_n'],tracking_reserve_n=kw['tracking_reserve_n'],
            evaluation=dict(failure_threshold_n=kw['failure_threshold_n']))
        outcome=study.EXPECTED[kw['strategy']]
        result=dict(outcome=outcome,physical_success=outcome=='SUCCESS',expected_outcome_met=True,metrics={},analyzer_sha256='old_analyzer')
        (p/'metadata.json').write_text(json.dumps(metadata));(p/'signals.npz').write_bytes(b'immutable_signal_fixture')
        (p/'weak_pad_summary.json').write_text(json.dumps(result));(p/'weak_pad_report.md').write_text('Original report')
        return p,result
    return tmp_path/'study',cases,calls,runner


def test_completed_resume_never_reexecutes_and_stop_is_not_success(setup):
    p,cases,calls,runner=setup
    result=study.run_study(p,cases=cases,workers=1,runner=runner)
    assert result['expected_outcomes_met']==2 and result['physical_successes']==1
    study.run_study(p,cases=cases,workers=1,runner=runner)
    assert calls==['conservative','adaptive']
    assert study.verify_study(p)['verified']


def test_failed_physical_attempt_is_preserved_without_retry_or_denominator_change(setup):
    p,cases,calls,runner=setup
    def unsuccessful(**kw):
        run,result=runner(**kw)
        if kw['strategy']=='adaptive':
            result.update(outcome='UNSAFE',expected_outcome_met=False,physical_success=False)
            (run/'weak_pad_summary.json').write_text(json.dumps(result))
        return run,result
    result=study.run_study(p,cases=cases,workers=1,runner=unsuccessful)
    assert result['expected_trials']==2 and result['expected_outcomes_met']==1
    study.run_study(p,cases=cases,workers=1,runner=unsuccessful)
    assert len(calls)==2


def test_tampered_raw_record_rejected_before_resume(setup):
    p,cases,calls,runner=setup
    study.run_study(p,cases=cases,workers=1,runner=runner)
    state=json.loads((p/'study_state.json').read_text());run=Path(next(iter(state['trials'].values()))['run_dir'])
    (run/'signals.npz').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='Canonical trial changed'):study.verify_study(p)
    with pytest.raises(ValueError,match='Canonical trial changed'):study.run_study(p,cases=cases,workers=1,runner=runner)
    assert len(calls)==2


def test_verification_never_creates_or_runs_incomplete_studies(setup):
    p,cases,calls,runner=setup
    with pytest.raises(FileNotFoundError):study.verify_study(p)
    assert not p.exists()
    manifest,path=study.ensure_manifest(p,cases=cases);study.freeze_execution(p,path)
    study._write(p/'study_state.json',dict(manifest_sha256=study._sha(path),trials={}))
    before={str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()}
    with pytest.raises(ValueError,match='does not launch'):study.verify_study(p)
    assert before=={str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()}
    assert not calls


def test_interrupted_attempt_is_not_silently_restarted(setup):
    p,cases,calls,runner=setup
    manifest,path=study.ensure_manifest(p,cases=cases);frozen=study.freeze_execution(p,path)
    first=manifest['trials'][0]
    study._write(p/'study_state.json',dict(manifest_sha256=study._sha(path),trials={first['trial_id']:dict(status='running',executor_sha256=frozen['executor']['sha256'])}))
    with pytest.raises(ValueError,match='Interrupted'):study.run_study(p,cases=cases,workers=1,runner=runner)
    assert not calls


def test_wrong_recorded_seed_cannot_be_reported_as_success(setup):
    p,cases,calls,runner=setup
    def wrong_seed(**kw):
        run,result=runner(**kw);m=json.loads((run/'metadata.json').read_text());m['seed']=999
        (run/'metadata.json').write_text(json.dumps(m));return run,result
    result=study.run_study(p,cases=cases,workers=1,runner=wrong_seed)
    assert result['expected_outcomes_met']==0 and result['physical_successes']==0
    assert all(row['status']=='error' for row in result['trials'])


@pytest.mark.parametrize('change',[dict(case_id='../outside'),dict(failure_threshold_n=float('nan')),dict(probe_command_limit_n=0.)])
def test_case_ids_and_loads_are_validated(change):
    case=dict(case_id='case',failure_threshold_n=25.,probe_command_limit_n=22.,strategies=['adaptive']);case.update(change)
    with pytest.raises(ValueError):study.protocol([case])


def test_final_posthoc_review_archives_original_summaries_and_preserves_raw_hashes(setup,monkeypatch):
    from primp_project.analysis import weak_pad
    p,cases,calls,runner=setup
    study.run_study(p,cases=cases,workers=1,runner=runner)
    state=json.loads((p/'study_state.json').read_text())
    original={entry['run_dir']:(Path(entry['run_dir'])/'weak_pad_summary.json').read_bytes() for entry in state['trials'].values()}
    def reanalyze(run):
        result=json.loads((run/'weak_pad_summary.json').read_text());result['analyzer_sha256']=weak_pad.ANALYZER_SOURCE_SHA256
        (run/'weak_pad_summary.json').write_text(json.dumps(result));return result
    monkeypatch.setattr(weak_pad,'analyze_weak_pad',reanalyze)
    study.reanalyze_study(p)
    current=json.loads((p/'study_state.json').read_text())
    for entry in current['trials'].values():
        history=entry['analysis_history'];assert len(history)==1
        assert (Path(history[0]['archive'])/'weak_pad_summary.json').read_bytes()==original[entry['run_dir']]
        assert (Path(entry['run_dir'])/'signals.npz').read_bytes()==b'immutable_signal_fixture'
    study.reanalyze_study(p)
    assert len(calls)==2
    assert all(len(entry['analysis_history'])==1 for entry in json.loads((p/'study_state.json').read_text())['trials'].values())
