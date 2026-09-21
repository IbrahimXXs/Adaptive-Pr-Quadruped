"""A fixed command and a task-derived command have distinct auditable claims."""
import numpy as np
import pytest
from primp_project.task_probe.analysis import evaluate_task_probe
from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2
from primp_project.probe_efficiency.tests.test_probe_efficiency_analysis import evidence as previous_evidence


def evidence(policy='task_sufficient'):
    m,d=previous_evidence()
    m.update(study_name='task_probe',probe_policy=policy,fixed_probe_force_n=23.201,next_leg_index=2)
    m['trial_parameters'].update(probe_policy=policy,fixed_probe_force_n=23.201)
    d['next_lift_anchor_w']=np.tile(d['feet_pos_w'][0,2],(len(d['control_time_s']),1))
    return m,d


def test_unchanged_task_method_and_correct_fixed_force_both_pass_physics():
    for policy in ('fixed_force','task_sufficient'):
        m,d=evidence(policy);r=evaluate_task_probe(m,d)
        assert r['outcome']=='SUCCESS' and r['physical_success']
        assert r['task_probe_criteria']['task_specific_goal_attained']['passed']
        assert r['metrics']['task_specific_simultaneous_hold_s']>=1.


def test_fixed_policy_cannot_silently_use_a_task_specific_force():
    m,d=evidence('fixed_force');m['fixed_probe_force_n']=m['trial_parameters']['fixed_probe_force_n']=30.
    r=evaluate_task_probe(m,d)
    assert r['outcome']=='INVALID'
    assert not r['task_probe_criteria']['fixed_policy_uses_declared_constant']['passed']


@pytest.mark.parametrize('violation',['actual_progress','only_terminal_progress','insufficient_overlap'])
def test_original_thirty_mm_success_cannot_hide_missing_task_progress(violation):
    m,d=evidence();movement=np.isin(d['phase'],['execute'])
    if violation=='actual_progress':d['com_pos_w'][movement,0]=d['probe_origin_com_w'][movement,0]+.031
    elif violation=='only_terminal_progress':d['com_pos_w'][-3:,0]=d['probe_origin_com_w'][-3:,0]+.031
    else:d['com_pos_w'][170:350,0]=d['probe_origin_com_w'][170:350,0]+.031
    # A fabricated easier command target does not change the declared task.
    d['progress_target_w']=d['com_pos_w'].copy()
    assert evaluate_weak_pad_v2(m,d)['physical_success']
    r=evaluate_task_probe(m,d)
    assert not r['physical_success'] and not r['passed']
    assert not r['task_probe_criteria']['task_specific_goal_attained']['passed']


def test_task_sufficient_command_keeps_the_unchanged_target_arithmetic():
    m,d=evidence();d['probe_target_load_n']+=2.;d['achieved_probe_command_n']+=2.
    r=evaluate_task_probe(m,d)
    assert not r['task_probe_criteria']['minimum_policy_does_not_select_maximum']['passed']
    assert r['outcome']=='INVALID'
