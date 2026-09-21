"""Controller transitions cannot hide a transient contact/site violation."""
import numpy as np
import pytest
from primp_project.control.weak_pad import WeakPadWrapper
from primp_project.planning.load_capacity import DemonstratedLoadCertificate, CertificateConfig


def wrapper():
    w=WeakPadWrapper.__new__(WeakPadWrapper)
    w.certificate_estimator=DemonstratedLoadCertificate(CertificateConfig(
        dwell_s=.5,measurement_margin_n=1.,tracking_margin_n=8.))
    w.origin=0.;w.phase='probe_hold'
    for t in np.arange(0,.502,.002):w._monitor_certificate(t,np.array([.28,.14,.02]),np.zeros(3),True,22.)
    assert w.certificate_valid
    return w


@pytest.mark.parametrize('phase',['probe_release','reprobe_posture','probe_ramp','progress_shift','safe_stop'])
@pytest.mark.parametrize('violation',['contact','vertical','horizontal'])
def test_transition_invalidity_is_latched_even_after_return(phase,violation):
    w=wrapper();w.phase=phase
    p=np.array([.28,.14,.02]);q=p.copy()
    if violation=='vertical':q[2]-=.003
    if violation=='horizontal':q[0]+=.011
    assert w._monitor_certificate(.504,q,np.zeros(3),violation!='contact',22.)
    for t in np.arange(.506,1.1,.002):
        w._monitor_certificate(t,p,np.zeros(3),True,40.)
    assert not w.certificate_valid
    w.phase='probe_hold'
    for t in np.arange(1.1,1.8,.002):w._monitor_certificate(t,p,np.zeros(3),True,40.)
    assert not w.certificate_valid
    assert w.certificate_force_n==0.


def test_transition_monitor_cannot_upgrade_certificate_or_bridge_hold_evidence():
    w=wrapper();w.phase='probe_release'
    for t in np.arange(.504,1.2,.002):w._monitor_certificate(t,np.array([.28,.14,.02]),np.zeros(3),True,40.)
    assert w.certificate_force_n==21.
    w.phase='probe_hold'
    for t in np.arange(1.2,1.698,.002):w._monitor_certificate(t,np.array([.28,.14,.02]),np.zeros(3),True,40.)
    assert w.certificate_force_n==21.
    w._monitor_certificate(1.7,np.array([.28,.14,.02]),np.zeros(3),True,40.)
    assert w.certificate_force_n==39.
