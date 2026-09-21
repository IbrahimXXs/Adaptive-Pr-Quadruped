"""Continuous monitor and physical recovery must survive adversarial logs."""
import copy
import numpy as np
import pytest
from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2
from primp_project.tests.test_weak_pad_analysis import evidence


def evidence_v2():
    m,d=evidence()
    m.update(protocol_version=2,strategy='adaptive_probe',sensor_config={},
             recovery_hold_s=2.,recovery_lift_height_m=.020,recovery_max_unload_delay_s=3.)
    n=len(d['control_time_s'])
    d['phase']=d['phase'].astype('U40')
    d.update(certificate_monitor_update=np.arange(n)>=60,
        certificate_observation_phase=d['phase'].copy(),
        certificate_revision=(np.arange(n)>=60).astype(int),
        certificate_invalidation_reason=np.full(n,'',dtype='U40'),
        sensor_observation_time_s=d['control_time_s'].copy(),
        recovery_triggered=np.zeros(n,bool),recovered_stop_declared=np.zeros(n,bool),
        recovery_trigger_reason=np.full(n,'',dtype='U40'),recovery_start_time_s=np.full(n,-1.),
        recovery_foot_anchor_w=np.tile([.2,.15,.02],(n,1)))
    d['sensor_pad_normal_force_n'][1:]=d['contact_normal_force'][:-1,0]
    d['sensor_pad_foot_pos_w'][1:]=d['feet_pos_w'][:-1,0]
    d['sensor_contact_measured'][1:]=d['contact_measured'][:-1]
    return m,d


def recovery_evidence():
    m,d=evidence_v2();n=len(d['control_time_s'])
    d['phase'][:123]='probe_ramp';d['phase'][10:100]='probe_hold'
    d['phase'][123:140]='recovery_unload';d['phase'][140:180]='recovery_lift';d['phase'][180:]='recovery_hold'
    d['com_pos_w'][:]=[-.08,-.06,.3]
    d['feet_pos_w'][:,2,2]=.02;d['feet_desired_w'][:,2,2]=.02
    d['contact_measured'][:]=True;d['sensor_contact_measured'][:]=True;d['contact_planned'][:]=True
    d['contact_normal_force'][:]=[22.,60.,60.,60.]
    d['actual_pad_normal_force_n'][:]=22.;d['force_before_deformation_n'][:]=22.
    d['actual_pad_normal_force_n'][120:123]=30.;d['force_before_deformation_n'][120:123]=30.
    d['actual_pad_normal_force_n'][123:]=0.;d['force_before_deformation_n'][123:]=0.
    d['contact_normal_force'][123:,0]=0.;d['contact_measured'][123:,0]=False
    d['sensor_contact_measured'][123:,0]=False;d['contact_planned'][123:,0]=False
    d['sensor_pad_normal_force_n'][:]=d['actual_pad_normal_force_n']
    d['pad_contact'][123:]=False
    d['pad_failed'][121:]=True
    t=d['control_time_s'];d['pad_sink_displacement_m'][121:]=np.minimum(.06,.1*(t[121:]-t[121]))
    d['certificate_force_n'][123:]=0.;d['certificate_valid'][123:]=False
    d['certificate_invalidation_reason'][123:]='lost_contact'
    d['certificate_revision'][123:]=2
    d['recovery_triggered'][123:]=True;d['recovery_start_time_s'][123:]=t[123]
    d['recovery_trigger_reason'][123:]='observed_sink'
    d['recovered_stop_declared'][380:]=True
    d['task_complete_declared'][:]=False;d['safe_stop_declared'][:]=False;d['future_plan_active'][:]=False
    d['grf_desired_w'][123:,0,2]=0.;d['planned_pad_force_n'][123:]=0.
    d['applied_pad_force_cap_n'][123:]=0.
    d['feet_pos_w'][180:,0,2]+=.025;d['feet_desired_w'][180:,0,2]+=.025
    d['sensor_pad_foot_pos_w'][:]=d['feet_pos_w'][:,0]
    d['contact_normal_force'][120:123,0]=30.
    d['sensor_pad_normal_force_n'][1:]=d['contact_normal_force'][:-1,0]
    d['sensor_pad_foot_pos_w'][1:]=d['feet_pos_w'][:-1,0]
    d['sensor_contact_measured'][1:]=d['contact_measured'][:-1]
    return m,d


def test_v2_success_requires_continuous_certificate_monitor():
    m,d=evidence_v2()
    assert evaluate_weak_pad_v2(m,d)['outcome']=='SUCCESS'
    d['certificate_monitor_update'][80]=False
    r=evaluate_weak_pad_v2(m,d)
    assert not r['physical_success']
    assert not r['criteria']['continuous_certificate_monitor']['passed']


def test_certificate_created_at_phase_transition_uses_observation_phase():
    m,d=evidence_v2()
    d['phase'][60]='probe_release'
    assert d['certificate_observation_phase'][60]=='probe_hold'
    assert evaluate_weak_pad_v2(m,d)['outcome']=='SUCCESS'


@pytest.mark.parametrize('phase',['probe_release','reprobe_posture','probe_ramp'])
def test_transient_loss_between_probe_and_movement_is_latched_even_if_contact_returns(phase):
    m,d=evidence_v2();d['phase'][80:90]=phase
    d['sensor_contact_measured'][85,0]=False
    d['certificate_valid'][85]=False
    r=evaluate_weak_pad_v2(m,d)
    assert not r['criteria']['continuous_certificate_monitor']['passed']
    assert not r['physical_success']


def test_transient_motion_cannot_be_hidden_by_returning_to_tested_foothold():
    m,d=evidence_v2();d['sensor_pad_foot_pos_w'][80,0]+=.012
    d['certificate_valid'][80]=False
    r=evaluate_weak_pad_v2(m,d)
    assert not r['criteria']['continuous_certificate_monitor']['passed']


def test_physically_aligned_temporary_contact_loss_cannot_restore_old_certificate():
    m,d=evidence_v2();d['phase'][80:90]='probe_release'
    d['certificate_observation_phase'][80:90]='probe_release'
    d['contact_measured'][84,0]=False;d['contact_normal_force'][84,0]=0.
    d['pad_contact'][84]=False;d['actual_pad_normal_force_n'][84]=0.
    d['force_before_deformation_n'][84]=0.
    d['sensor_contact_measured'][85,0]=False;d['sensor_pad_normal_force_n'][85]=0.
    d['certificate_valid'][85]=False;d['certificate_invalidation_reason'][85]='lost_contact'
    r=evaluate_weak_pad_v2(m,d)
    assert r['criteria']['realized_sensor_error_bounds']['passed']
    assert r['criteria']['actual_dwell_certificate']['passed']
    assert all(c['passed'] for c in r['criteria'].values() if c['category']=='integrity')
    assert not r['criteria']['continuous_certificate_monitor']['passed']
    assert not r['physical_success']


def test_sensing_error_must_fit_declared_measurement_reserve():
    m,d=evidence_v2();m['sensor_config']={'force_bias_n':.8,'force_noise_n':.4}
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']=='INVALID'
    assert not r['criteria']['sensor_reserve_covers_declared_error']['passed']


def test_actual_probe_failure_can_end_in_controlled_recovery_but_never_task_success():
    r=evaluate_weak_pad_v2(*recovery_evidence())
    assert r['outcome']=='RECOVERED_STOP'
    assert r['controlled_recovery_passed']
    assert not r['passed'] and not r['physical_success'] and not r['physical_safety_passed']
    assert r['metrics']['recovery_stable_hold_s']>=2.


@pytest.mark.parametrize('violation',['only_commanded_lift','no_commanded_lift','short_hold','final_support_loss','task_success_claim','failure_during_movement','kept_loading','no_trigger'])
def test_recovery_requires_physical_unloading_lift_and_terminal_tripod(violation):
    m,d=recovery_evidence()
    if violation=='only_commanded_lift':d['feet_pos_w'][180:,0,2]=.02
    elif violation=='no_commanded_lift':d['feet_desired_w'][180:,0,2]=.02
    elif violation=='short_hold':d['feet_pos_w'][180:250,0,2]=.02
    elif violation=='final_support_loss':d['contact_measured'][-1,1]=False
    elif violation=='task_success_claim':d['task_complete_declared'][-1]=True
    elif violation=='failure_during_movement':d['phase'][121]='progress_shift';d['future_plan_active'][121]=True
    elif violation=='kept_loading':d['actual_pad_normal_force_n'][123:]=5.
    else:d['recovery_triggered'][:]=False
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']!='RECOVERED_STOP'
    assert not r['physical_success']


def test_a_safe_stop_cannot_hide_future_loading_above_its_certificate():
    m,d=evidence_v2()
    d['phase'][100:]='safe_stop'
    d['safe_stop_declared'][100:]=True
    d['task_complete_declared'][:]=False
    d['contact_measured'][:,2]=True;d['sensor_contact_measured'][:,2]=True
    d['contact_normal_force'][:,2]=60.
    d['actual_pad_normal_force_n'][130]=22.
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']!='SAFE_STOP'
    assert not r['criteria']['future_certified_or_unloaded']['passed']


def test_later_recovery_does_not_excuse_a_fabricated_earlier_certificate():
    m,d=recovery_evidence();d['certificate_force_n'][60:123]=40.
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']=='INVALID'
    assert not r['criteria']['certificate_evidence_sound']['passed']


def test_controlled_abort_without_actual_pad_failure_is_a_safe_stop():
    m,d=recovery_evidence()
    d['actual_pad_normal_force_n'][120:123]=22.;d['force_before_deformation_n'][120:123]=22.
    d['pad_failed'][:]=False;d['pad_sink_displacement_m'][:]=0.
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']=='SAFE_STOP'
    assert not r['controlled_recovery_passed']
    assert not r['physical_success']


def test_declared_sensing_error_is_checked_against_aligned_physical_truth():
    m,d=evidence_v2();m['sensor_config']={'force_bias_n':.3,'force_noise_n':.1,'position_noise_m':.0002}
    d['sensor_pad_normal_force_n']+=.3
    d['sensor_pad_foot_pos_w'][:,0]+=.00015
    assert evaluate_weak_pad_v2(m,d)['criteria']['realized_sensor_error_bounds']['passed']
    d['sensor_pad_normal_force_n'][200]+=.101
    r=evaluate_weak_pad_v2(m,d)
    assert not r['criteria']['realized_sensor_error_bounds']['passed']
    assert not r['physical_success']


@pytest.mark.parametrize('field',['oversized_position_error','undeclared_delay'])
def test_sensor_metadata_cannot_exceed_supported_error_and_delay_limits(field):
    m,d=evidence_v2()
    if field=='oversized_position_error':m['sensor_config']['position_noise_m']=.1
    else:m['sensor_delay_s']=.04
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']=='INVALID'
    assert not r['criteria']['supported_sensor_configuration']['passed']


def test_recovered_stop_cannot_keep_commanding_support_on_the_failed_pad():
    m,d=recovery_evidence()
    d['applied_pad_force_cap_n'][180:]=30.;d['planned_pad_force_n'][180:]=30.
    d['grf_desired_w'][180:,0,2]=30.
    r=evaluate_weak_pad_v2(m,d)
    assert r['criteria']['controlled_probe_failure_recovery']['passed']
    assert not r['criteria']['recovery_commands_unloaded']['passed']
    assert r['outcome']!='RECOVERED_STOP'


def test_recovery_phase_flags_cannot_hide_an_aligned_original_support_loss():
    m,d=recovery_evidence()
    d['phase'][130:132]='stand'
    d['contact_measured'][130,1]=False;d['contact_normal_force'][130,1]=0.
    d['sensor_contact_measured'][131,1]=False
    r=evaluate_weak_pad_v2(m,d)
    assert r['criteria']['realized_sensor_error_bounds']['passed']
    assert not r['criteria']['recovery_state_coverage']['passed']
    assert not r['criteria']['probe_and_recovery_tripod']['passed']
    assert r['outcome']=='INVALID'


def test_positive_small_certificate_allows_only_zero_command_unloaded_stop():
    m,d=evidence_v2()
    d['phase'][100:]='safe_stop';d['certificate_observation_phase'][100:]='safe_stop'
    d['com_pos_w'][:]=[-.08,-.06,.3]
    d['feet_pos_w'][:,2,2]=.02;d['contact_measured'][:,2]=True
    d['contact_normal_force'][:,2]=60.;d['contact_planned'][:,2]=True
    d['contact_normal_force'][:100,0]=4.;d['contact_normal_force'][100:,0]=.5
    d['actual_pad_normal_force_n'][:]=d['contact_normal_force'][:,0]
    d['force_before_deformation_n'][:]=d['actual_pad_normal_force_n']
    d['sensor_pad_normal_force_n'][0]=4.
    d['sensor_pad_normal_force_n'][1:]=d['contact_normal_force'][:-1,0]
    d['sensor_contact_measured'][1:]=d['contact_measured'][:-1]
    d['certificate_force_n'][60:]=3.
    d['safe_stop_declared'][100:]=True;d['task_complete_declared'][:]=False
    d['planned_pad_force_n'][100:]=0.;d['applied_pad_force_cap_n'][100:]=0.
    d['grf_desired_w'][100:,0,2]=0.
    r=evaluate_weak_pad_v2(m,d)
    assert r['outcome']=='SAFE_STOP'
    assert r['criteria']['actual_dwell_certificate']['passed']
    assert r['criteria']['future_certified_or_unloaded']['passed']


def test_final_and_concurrent_progress_do_not_count_larger_probe_repositioning():
    m,d=evidence_v2()
    d['com_pos_w'][70:90,0]+=.07
    r=evaluate_weak_pad_v2(m,d)
    assert r['metrics']['maximum_probe_com_displacement_m']==pytest.approx(.07)
    assert r['metrics']['final_forward_com_motion_m']==pytest.approx(.04)
    assert r['metrics']['simultaneous_progress_min_forward_m']==pytest.approx(.04)
    assert r['metrics']['simultaneous_progress_max_forward_m']==pytest.approx(.04)


def test_tracking_gaps_are_separated_between_deliberate_probe_and_execution():
    m,d=evidence_v2()
    d['actual_pad_normal_force_n'][110]=20.
    r=evaluate_weak_pad_v2(m,d)
    groups=r['metrics']['tracking_gap_by_phase_group']
    assert groups['future_execution']['maximum_actual_minus_cap_n']==pytest.approx(5.)
    assert groups['future_execution']['maximum_actual_minus_command_n']==pytest.approx(6.)
    assert groups['deliberate_probe']['maximum_actual_minus_cap_n']==pytest.approx(-2.)
    assert groups['recovery']['samples']==0
