"""Policy-efficiency claims cannot replace frozen physical success checks."""
import numpy as np
import pytest
from dataclasses import asdict
from primp_project.planning.load_capacity import CapacityPlanningConfig
from primp_project.probe_efficiency.analysis import evaluate_probe_efficiency, compare_baseline_traces
from primp_project.probe_efficiency.study import paired_results
from primp_project.tests.test_weak_pad_v2_analysis import evidence_v2, recovery_evidence


def evidence(recovery=False, policy='minimum_sufficient'):
    m,d=(recovery_evidence() if recovery else evidence_v2())
    m.update(study_name='probe_efficiency',probe_policy=policy,tracking_reserve_n=8.,
             sensor_force_error_bound_n=0.,trial_parameters={'probe_undershoot_allowance_n':.2,
                'measurement_reserve_n':1.,'tracking_reserve_n':8.},
             model_mass_kg=420./9.81,gravity_m_s2=9.81,
             movement_optimizer_settings=asdict(CapacityPlanningConfig(forward_progress_m=.04,next_lift_leg=2)))
    n=len(d['control_time_s'])
    for name in ('actual_pad_normal_force_n', 'force_before_deformation_n'):
        d[name][d[name]==22.]=24.
    d['contact_normal_force'][d['contact_normal_force'][:,0]==22.,0]=24.
    d['sensor_pad_normal_force_n'][0]=24.
    d['sensor_pad_normal_force_n'][1:]=d['contact_normal_force'][:-1,0]
    d['certificate_force_n'][d['certificate_force_n']>0.]=23.
    d['tracking_reserve_n'][:]=8.
    d.update(additional_probe_count=np.ones(n,dtype=int),actual_pad_displacement_m=d['pad_sink_displacement_m'].copy(),
        probe_origin_com_w=np.tile(d['com_pos_w'][0],(n,1)),
        minimum_future_load_n=np.full(n,14.),minimum_sufficient_probe_load_n=np.full(n,23.001),
        target_tolerance_n=np.full(n,.001),probe_target_load_n=np.full(n,23.201 if policy=='minimum_sufficient' else 40.))
    d['selected_probe_request_n']=d['probe_target_load_n'].copy()
    m['capacity_decision_history']=[dict(action='PROBE',minimum_future_load_n=14.,
        achievable_probe_load_n=float(d['probe_target_load_n'][0]),requested_probe_load_n=float(d['selected_probe_request_n'][0]))]
    d['achieved_probe_command_n'][:]=d['probe_target_load_n']
    probe=np.isin(d['phase'],('probe_hold','probe_ramp'))
    d['applied_pad_force_cap_n'][probe]=d['probe_target_load_n'][probe]+.2
    d['grf_desired_w'][probe,0,2]=d['probe_target_load_n'][probe]-.2
    return m,d


def test_frozen_physical_validation_is_preserved_under_new_target_audit():
    m,d=evidence();r=evaluate_probe_efficiency(m,d)
    assert r['outcome']=='SUCCESS' and r['physical_success']
    assert r['probe_efficiency_integrity_passed']
    assert r['metrics']['minimum_sufficient_test_target_n']==pytest.approx(23.001)
    assert r['metrics']['pad_damaged'] is False
    d['certificate_monitor_update'][80]=False
    rejected=evaluate_probe_efficiency(m,d)
    assert not rejected['physical_success']
    assert not rejected['criteria']['continuous_certificate_monitor']['passed']


@pytest.mark.parametrize('violation',['reduced_reserve','max_probe','nonfinite','missing',
    'larger_command','larger_cap','larger_mpc_force','changed_tracking_metadata','changed_sensor_bound',
    'invented_task_load','false_displacement','changed_request','all_reserves_weakened','invented_target_and_decision'])
def test_fabricated_minimum_probe_targets_cannot_pass(violation):
    m,d=evidence()
    if violation=='reduced_reserve':d['minimum_sufficient_probe_load_n'][:]-=1.
    elif violation=='max_probe':d['probe_target_load_n'][:]=40.
    elif violation=='nonfinite':d['probe_target_load_n'][3]=np.nan
    elif violation=='larger_command':d['achieved_probe_command_n'][:]+=3.
    elif violation=='larger_cap':d['applied_pad_force_cap_n'][30]+=3.
    elif violation=='larger_mpc_force':d['grf_desired_w'][30,0,2]+=3.
    elif violation=='changed_tracking_metadata':m['tracking_reserve_n']=5.
    elif violation=='changed_sensor_bound':m['sensor_force_error_bound_n']=.5
    elif violation=='invented_task_load':
        for name in ('minimum_future_load_n','minimum_sufficient_probe_load_n','probe_target_load_n'):d[name]-=5.
    elif violation=='false_displacement':d['actual_pad_displacement_m'][:]=.06
    elif violation=='changed_request':d['selected_probe_request_n']+=10.
    elif violation=='all_reserves_weakened':
        m['tracking_reserve_n']=m['trial_parameters']['tracking_reserve_n']=6.
        d['tracking_reserve_n'][:]=6.
        d['minimum_sufficient_probe_load_n']-=2.;d['probe_target_load_n']-=2.
    elif violation=='invented_target_and_decision':
        for name in ('minimum_future_load_n','minimum_sufficient_probe_load_n','probe_target_load_n',
                     'selected_probe_request_n','achieved_probe_command_n'):d[name]+=5.
        for name in ('minimum_future_load_n','achievable_probe_load_n','requested_probe_load_n'):
            m['capacity_decision_history'][0][name]+=5.
    else:del d['minimum_future_load_n']
    r=evaluate_probe_efficiency(m,d)
    assert r['outcome']=='INVALID' and not r['physical_success'] and not r['passed']


def test_recovered_damage_stays_damage_and_never_becomes_completion():
    r=evaluate_probe_efficiency(*evidence(recovery=True))
    assert r['outcome']=='RECOVERED_STOP'
    assert r['metrics']['pad_damaged'] and r['metrics']['pad_failure_during_probe']
    assert not r['physical_success']
    assert r['metrics']['recovery_time_s']>0.
    assert r['metrics']['maximum_pad_displacement_m']==pytest.approx(.06)


def test_launch_surface_force_is_excluded_from_probe_peak_and_elapsed_is_separate():
    m,d=evidence();d['phase'][:10]='stand';d['actual_pad_normal_force_n'][:10]=0.
    d['contact_normal_force'][:10,0]=100.
    r=evaluate_probe_efficiency(m,d)
    assert r['metrics']['maximum_actual_probe_force_n']==24.
    assert r['metrics']['probe_time_s']==pytest.approx(.9)
    assert r['metrics']['deliberate_probe_time_s']==pytest.approx(.9)
    assert r['metrics']['total_trial_time_s']==pytest.approx(4.)


def rows(minimum_outcome='SUCCESS', minimum_damage=False, maximum_damage=True):
    return [dict(case_id='c',seed=211,probe_policy=policy,status='completed',outcome=outcome,
        physical_success=outcome=='SUCCESS',metrics=dict(pad_damaged=damage,hidden_capacity_n=51.,
        probe_time_s=time,maximum_actual_probe_force_n=force,total_trial_time_s=time+30))
        for policy,outcome,damage,time,force in [
            ('maximum_feasible','RECOVERED_STOP',maximum_damage,15.,52.),
            ('minimum_sufficient',minimum_outcome,minimum_damage,21.,51.)]]


def test_preventable_damage_needs_observed_paired_undamaged_task_completion():
    assert paired_results(rows())[0]['avoidable_damage_demonstrated']
    for outcome,damage in [('SAFE_STOP',False),('RECOVERED_STOP',True),('SUCCESS',True)]:
        assert not paired_results(rows(outcome,damage))[0]['avoidable_damage_demonstrated']
    assert not paired_results(rows(maximum_damage=False))[0]['avoidable_damage_demonstrated']
    broken=rows();broken[0]['status']='error'
    assert not paired_results(broken)[0]['avoidable_damage_demonstrated']


def test_baseline_equivalence_checks_commands_and_physics_not_host_timing(tmp_path):
    original=tmp_path/'original';extension=tmp_path/'extension';original.mkdir();extension.mkdir()
    a=dict(qpos=np.array([[1.,2.],[3.,4.]]),phase=np.array(['stand','probe']),
           mpc_update=np.array([True,False]),solver_time_s=np.ones(2),wall_time_s=np.arange(2))
    np.savez(original/'signals.npz',**a)
    a['solver_time_s']*=2.;a['wall_time_s']+=20
    np.savez(extension/'signals.npz',**a,new_target=np.ones(2))
    assert compare_baseline_traces(original,extension)['verified']
    a['qpos'][0,0]+=.001;np.savez(extension/'signals.npz',**a)
    r=compare_baseline_traces(original,extension)
    assert not r['verified'] and r['mismatches'][0]['channel']=='qpos'
