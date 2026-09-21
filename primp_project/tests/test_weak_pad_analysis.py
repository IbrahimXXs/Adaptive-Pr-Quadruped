"""Falsify requested-force certificates, cap-only safety and empty progress claims."""
import numpy as np
import pytest
from primp_project.analysis.weak_pad import evaluate_weak_pad


def evidence(strategy='adaptive'):
    n,dt=400,.01
    time=np.arange(n)*dt
    feet=np.tile(np.array([[.2,.15,.02],[.2,-.15,.02],[-.2,.15,.02],[-.2,-.15,.02]]),(n,1,1))
    com=np.tile([-.08,-.06,.3],(n,1))
    future=np.arange(n)>=100
    phase=np.where(future,'safe_stop' if strategy=='conservative' else 'execute','probe_hold')
    contacts=np.ones((n,4),bool); normal=np.tile([22.,60.,60.,60.],(n,1)); normal[future,0]=14.
    planned=contacts.copy()
    if strategy=='adaptive':
        com[future,0]+=.04
        feet[150:350,2,2]+=.025
        contacts[150:350,2]=False;normal[150:350,2]=0;planned[150:350,2]=False
    force=normal[:,0].copy()
    cert=np.where(np.arange(n)>=60,21.,0.)
    d=dict(time_s=time+dt,control_time_s=time,step=np.arange(1,n+1),phase=phase,
        com_pos_w=com,base_rpy_rad=np.zeros((n,3)),feet_pos_w=feet,feet_desired_w=feet.copy(),
        contact_measured=contacts,contact_normal_force=normal,contact_planned=planned,
        grf_desired_w=np.zeros((n,4,3)),mpc_update=np.ones(n,bool),mpc_status=np.full(n,2),qp_status=np.zeros(n),
        requested_probe_force_n=np.full(n,45.),achieved_probe_command_n=np.full(n,22.),
        sensor_pad_normal_force_n=force.copy(),actual_pad_normal_force_n=force.copy(),pad_contact=np.ones(n,bool),
        certificate_force_n=cert,certificate_valid=cert>0,certificate_update=np.arange(n)==60,
        probe_evidence_start_time_s=np.where(cert>0,.1,-1.),probe_evidence_end_time_s=np.where(cert>0,.6,-1.),
        planned_pad_force_n=np.where(future,14.,22.),applied_pad_force_cap_n=np.where(future,15.,24.),
        required_pad_force_n=np.full(n,30.),tracking_reserve_n=np.full(n,6.),commanded_next_leg_lift_m=np.full(n,.025),
        strategy_state=np.where(future,'SAFE_STOP' if strategy=='conservative' else 'EXECUTE','PROBE'),
        safe_stop_declared=future.copy() if strategy=='conservative' else np.zeros(n,bool),
        task_complete_declared=(np.arange(n)>380) if strategy=='adaptive' else np.zeros(n,bool),
        future_plan_active=future,pad_sink_displacement_m=np.zeros(n),pad_failed=np.zeros(n,bool),
        force_before_deformation_n=force.copy(),sensor_pad_foot_pos_w=feet[:,0].copy(),
        sensor_pad_foot_vel_w=np.zeros((n,3)),sensor_contact_measured=contacts.copy())
    d['grf_desired_w'][:,0,2]=d['planned_pad_force_n']
    m=dict(experiment='weak_pad',strategy=strategy,status='completed',experiment_complete=True,role='evaluation',dt_s=dt,
        legs=['FL','FR','RL','RR'],selected_leg='FL',next_leg='RL',probe_dwell_s=.5,
        sensor_force_reserve_n=1.,max_probe_motion_m=.001,force_tolerance_n=.5,
        simulation_params=dict(mpc_frequency=100.),evaluation=dict(failure_threshold_n=25.,overload_dwell_s=.02,sink_speed_m_s=.1,sink_depth_m=.06))
    return m,d


def test_meaningful_adaptive_success_and_safe_stop_have_distinct_outcomes():
    for strategy,outcome,success in [('adaptive','SUCCESS',True),('conservative','SAFE_STOP',False)]:
        result=evaluate_weak_pad(*evidence(strategy))
        assert result['outcome']==outcome
        assert result['expected_outcome_met']
        assert result['physical_success'] is success
        assert result['passed'] is success
        assert result['metrics']['maximum_forward_com_motion_m'] == pytest.approx(.04 if success else 0.)


def test_original_unaware_controller_collapse_is_demonstrated_but_never_success():
    m,d=evidence('unaware')
    d['phase'][:100]='confirm';d['phase'][100:]='reload'
    d['future_plan_active'][:]=False
    d['certificate_force_n'][:]=0;d['certificate_valid'][:]=False
    d['certificate_update'][:]=False
    d['force_before_deformation_n'][120:]=30.
    d['actual_pad_normal_force_n'][120:]=30.
    d['pad_failed'][121:]=True
    d['pad_sink_displacement_m'][121:]=np.minimum(.06,.1*(d['control_time_s'][121:]-d['control_time_s'][121]))
    result=evaluate_weak_pad(m,d)
    assert result['outcome']=='PROBLEM_COLLAPSE'
    assert result['expected_outcome_met']
    assert not result['physical_success'] and not result['passed']
    assert not result['physical_safety_passed']


@pytest.mark.parametrize('violation',['request_as_proof','brief_spike','short_dwell','future_evidence','foot_motion','foot_speed','lost_contact'])
def test_certificate_requires_actual_full_stable_causal_dwell(violation):
    m,d=evidence()
    if violation=='request_as_proof':d['certificate_force_n'][60:]=44.
    elif violation=='brief_spike':d['sensor_pad_normal_force_n'][59]=40.;d['certificate_force_n'][60:]=39.
    elif violation=='short_dwell':d['probe_evidence_start_time_s'][60:]=.5
    elif violation=='future_evidence':d['probe_evidence_end_time_s'][60:]=.8
    elif violation=='foot_motion':d['sensor_pad_foot_pos_w'][40:60,0]+=.01
    elif violation=='foot_speed':d['sensor_pad_foot_vel_w'][40,2]=.02
    else:d['sensor_contact_measured'][40,0]=False
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['actual_dwell_certificate']['passed']
    assert not result['physical_success']


def test_an_actual_capacity_overrun_is_not_excused_by_solver_tolerance_or_valid_mpc_cap():
    m,d=evidence()
    d['actual_pad_normal_force_n'][120]=21.435
    result=evaluate_weak_pad(m,d)
    assert result['criteria']['planned_force_with_reserve']['passed']
    assert not result['criteria']['actual_future_loading']['passed']
    assert not result['physical_success']


def test_installed_cap_cannot_consume_declared_tracking_reserve():
    m,d=evidence()
    d['applied_pad_force_cap_n'][120]=15.1
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['planned_force_with_reserve']['passed']


@pytest.mark.parametrize('violation',['only_commanded_lift','too_short','no_forward','unsupported_other_leg','still_planned_support'])
def test_success_needs_concurrent_measured_body_and_foot_progress(violation):
    m,d=evidence()
    if violation=='only_commanded_lift':d['feet_pos_w'][:,2,2]=.02
    elif violation=='too_short':d['feet_pos_w'][210:350,2,2]=.02
    elif violation=='no_forward':d['com_pos_w'][:,0]=-.08
    elif violation=='unsupported_other_leg':d['contact_measured'][150:350,1]=False
    else:d['contact_planned'][150:350,2]=True
    result=evaluate_weak_pad(m,d)
    assert not result['physical_success']


def test_stale_certificate_cannot_follow_a_lost_or_moved_foothold():
    m,d=evidence()
    d['sensor_pad_foot_pos_w'][120:,0]+=.011
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['certificate_site_guard']['passed']
    assert not result['physical_success']


def test_declared_failure_without_physical_overload_cannot_pass_problem_demo():
    m,d=evidence('unaware')
    d['pad_failed'][121:]=True
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['physical_failure_model']['passed']
    assert result['outcome']=='INVALID'


def test_missing_mpc_updates_and_leaked_strength_are_rejected():
    m,d=evidence()
    d['mpc_update'][150]=False;m['failure_threshold_n']=25.
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['mpc_update_cadence']['passed']
    assert not result['criteria']['strength_truth_boundary']['passed']
    assert not result['expected_outcome_met']


def test_one_sample_short_of_declared_probe_dwell_is_not_sufficient():
    m,d=evidence()
    d['probe_evidence_start_time_s'][60:]=.11
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['actual_dwell_certificate']['passed']


def test_probe_ramp_support_is_checked_outside_the_final_evidence_window():
    m,d=evidence()
    d['contact_measured'][5,1]=False
    result=evaluate_weak_pad(m,d)
    assert result['criteria']['actual_dwell_certificate']['passed']
    assert not result['criteria']['probe_tripod_support']['passed']
    assert not result['physical_success']


def test_capacity_cannot_increase_during_continuous_future_execution():
    m,d=evidence()
    d['certificate_force_n'][60:120]=20.
    d['applied_pad_force_cap_n'][100:120]=14.
    result=evaluate_weak_pad(m,d)
    assert result['criteria']['actual_dwell_certificate']['passed']
    assert not result['criteria']['future_certificate_no_growth']['passed']
    assert not result['physical_success']


def test_historical_progress_does_not_hide_a_missing_terminal_support():
    m,d=evidence()
    d['contact_measured'][-20:,1]=False
    d['contact_normal_force'][-20:,1]=0.
    result=evaluate_weak_pad(m,d)
    assert result['criteria']['meaningful_progress']['passed']
    assert not result['criteria']['terminal_support']['passed']
    assert not result['physical_success']


@pytest.mark.parametrize('field',['metadata','final_flag'])
def test_historical_completion_flag_cannot_replace_final_completion(field):
    m,d=evidence()
    if field=='metadata':m['experiment_complete']=False
    else:d['task_complete_declared'][-20:]=False
    assert not evaluate_weak_pad(m,d)['physical_success']


def test_one_false_future_flag_cannot_mask_an_actual_overload():
    m,d=evidence()
    d['future_plan_active'][370]=False
    d['actual_pad_normal_force_n'][370]=22.
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['future_loading_coverage']['passed']
    assert not result['criteria']['actual_future_loading']['passed']
    assert not result['physical_success']


def test_hidden_capacity_in_nested_planner_input_list_is_rejected():
    m,d=evidence()
    m['planner_inputs']=[{'failure_load_n':35.}]
    result=evaluate_weak_pad(m,d)
    assert not result['criteria']['strength_truth_boundary']['passed']
    assert not result['physical_success']


def test_plot_uses_actual_target_pad_force_and_probe_origin_not_launch_stance():
    from primp_project.analysis.weak_pad import overview_series
    m,d=evidence()
    d['phase'][:20]='stand'
    d['sensor_pad_normal_force_n'][:20]=45.
    d['actual_pad_normal_force_n'][:20]=0.
    d['com_pos_w'][:20,0]+=.07
    d['feet_pos_w'][:20,2,2]+=.003
    values=overview_series(m,d)
    assert np.all(values['target_pad_force_n'][:20]==0.)
    assert values['origin_sample']==20
    assert values['forward_progress_m'][20]==0.
    assert values['next_foot_clearance_m'][20]==0.
    assert values['forward_progress_m'][100]==pytest.approx(.04)
    assert values['next_foot_clearance_m'][150]==pytest.approx(.025)
