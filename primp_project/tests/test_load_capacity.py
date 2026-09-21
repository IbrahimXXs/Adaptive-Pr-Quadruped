"""Certificates require achieved stable loads; next-leg motion obeys that proof."""
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from primp_project.planning.load_capacity import (
    CapacityPlanner, CapacityPlanningConfig, CertificateConfig,
    DemonstratedLoadCertificate, LoadObservation, solve_load_allocation,
)


ANCHORS = np.array([[.29, .15, .02], [.2, -.15, .02], [-.2, .15, .02], [-.2, -.15, .02]])
PROBE = np.array([-1/15, -.05, .28])
WEIGHT = 150.


def sample(t, force=25., contact=True, displacement=0., velocity=0., surface=None):
    return LoadObservation(t, force, contact, [.29, .15, .022+displacement], [0., 0., velocity], surface)


def demonstrated(force=27., config=CertificateConfig(dwell_s=.5, measurement_margin_n=1., tracking_margin_n=6.)):
    estimator = DemonstratedLoadCertificate(config)
    for i in range(61):
        estimator.update(sample(i*.01, force))
    return estimator


def assert_equilibrium(forces, com):
    np.testing.assert_allclose(np.r_[forces.sum(), ANCHORS[:, :2].T@forces], WEIGHT*np.r_[1., com[:2]], atol=1e-7)


def test_demonstration_uses_minimum_achieved_force_and_two_explicit_reserves():
    estimator = demonstrated(force=27.)
    cert = estimator.certificate
    assert cert.valid and cert.dwell_s >= .5
    assert cert.measured_min_force_n == pytest.approx(27.)
    assert cert.certified_load_n == pytest.approx(26.)
    assert cert.force_cap_n == pytest.approx(20.)
    assert cert.force_cap_n+cert.tracking_margin_n == pytest.approx(cert.certified_load_n)
    with pytest.raises(TypeError):
        replace(sample(1.), requested_force_n=45.)


def test_short_large_force_spike_cannot_create_or_raise_certificate():
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5))
    for i in range(45):
        estimator.update(sample(i*.01, 50.))
    assert not estimator.certificate.valid
    estimator = demonstrated(force=27.)
    original = estimator.certificate
    for i in range(61, 70):
        estimator.update(sample(i*.01, 100.))
    assert estimator.certificate == original


def test_an_extended_ramp_is_not_a_force_plateau():
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5))
    for i in range(101):
        estimator.update(sample(i*.01, 5.+i*.3))
    assert not estimator.certificate.valid


@pytest.mark.parametrize('kind', ['gap', 'contact', 'motion', 'velocity', 'surface'])
def test_discontinuous_or_moving_evidence_cannot_certify(kind):
    estimator = DemonstratedLoadCertificate(CertificateConfig(dwell_s=.5))
    for i in range(61):
        t = i*.01+(1. if kind == 'gap' and i >= 30 else 0.)
        obs = sample(t, contact=not (kind == 'contact' and i == 30),
            displacement=i*.0001 if kind == 'motion' else 0.,
            velocity=.01 if kind == 'velocity' else 0.,
            surface=[0., 0., i*.0001] if kind == 'surface' else None)
        estimator.update(obs)
    assert not estimator.certificate.valid


def test_lost_or_displaced_certified_foothold_invalidates_until_explicit_reassessment():
    estimator = demonstrated()
    estimator.update(sample(.7, displacement=-.003))
    assert not estimator.certificate.valid and estimator.certificate.force_cap_n == 0.
    assert estimator.certificate.invalidation_reason == 'tested_foothold_moved'
    for i in range(71, 160):
        estimator.update(sample(i*.01, 100., displacement=-.003))
    assert not estimator.certificate.valid
    estimator.reset()
    for i in range(61):
        estimator.update(sample(i*.01, 27.))
    assert estimator.certificate.valid
    estimator.update(sample(.7, contact=False))
    assert not estimator.certificate.valid and estimator.certificate.invalidation_reason == 'lost_contact'


def test_observations_are_immutable_and_have_no_scene_or_capacity_truth_fields():
    obs = sample(0.)
    with pytest.raises(ValueError):
        obs.foot_position_w.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        obs.actual_failure_threshold_n = 45.
    with pytest.raises(TypeError):
        replace(obs, actual_failure_threshold_n=45.)


def test_monitoring_cannot_raise_certificate_or_bridge_an_interrupted_probe_window():
    estimator = demonstrated()
    original = estimator.certificate
    for i in range(61, 161):
        estimator.update(sample(i*.01, 60.), allow_increase=False)
    assert estimator.certificate == original
    for i in range(161, 201):
        estimator.update(sample(i*.01, 60.))
    assert estimator.certificate == original
    for i in range(201, 222):
        estimator.update(sample(i*.01, 60.))
    assert estimator.certificate.certified_load_n > original.certified_load_n


@pytest.mark.parametrize('failure', ['contact', 'motion'])
def test_monitoring_invalidates_lost_or_displaced_tested_contact(failure):
    estimator = demonstrated()
    invalid = estimator.update(sample(.7, contact=failure != 'contact',
        displacement=-.003 if failure == 'motion' else 0.), allow_increase=False)
    assert not invalid.valid and invalid.force_cap_n == 0.


def test_declared_homogeneous_region_allows_small_horizontal_rolling_but_not_sinking():
    estimator = demonstrated()
    original = estimator.certificate
    rolled = replace(sample(.7), foot_position_w=sample(.7).foot_position_w+[.0074, 0., -.0005])
    assert estimator.update(rolled, allow_increase=False) == original
    outside = replace(sample(.8), foot_position_w=sample(.8).foot_position_w+[.0101, 0., 0.])
    assert not estimator.update(outside, allow_increase=False).valid
    estimator = demonstrated()
    sunk = replace(sample(.7), foot_position_w=sample(.7).foot_position_w+[.001, 0., -.0026])
    assert not estimator.update(sunk, allow_increase=False).valid


def test_probe_request_is_limited_by_actual_posture_feasibility_not_assumed_achieved():
    planner = CapacityPlanner(config=CapacityPlanningConfig(probe_force_ceiling_n=60.))
    plan, maximum = planner.probe_allocation(ANCHORS, WEIGHT, PROBE, 45., [150.]*4, allow_posture_change=False)
    assert plan.feasible
    assert maximum == pytest.approx(36.73469387755102)
    assert plan.forces_n[0] == pytest.approx(maximum-2.)
    assert plan.forces_n[0] < 45.
    assert plan.support_margin_m >= .02
    assert_equilibrium(plan.forces_n, plan.com_position_w)
    assert not DemonstratedLoadCertificate().certificate.valid


def test_configured_probe_ceiling_and_additional_torque_inequality_are_enforced():
    planner = CapacityPlanner(config=CapacityPlanningConfig(probe_force_ceiling_n=25.))
    plan, maximum = planner.probe_allocation(ANCHORS, WEIGHT, PROBE, 45., [150.]*4,
        extra_matrix=[[1., 0., 0., 0.]], extra_upper=[24.])
    assert plan.feasible and maximum == pytest.approx(24.)
    assert plan.forces_n[0] == pytest.approx(22.)
    assert_equilibrium(plan.forces_n, plan.com_position_w)


def test_same_twenty_newton_certificate_rejects_fixed_motion_but_allows_adapted_next_leg_lift():
    certificate = demonstrated(force=27.).certificate
    baseline = CapacityPlanner('baseline').decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4)
    adaptive = CapacityPlanner('adaptive').decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4)
    assert baseline.nominal_required_load_n == pytest.approx(40.)
    assert baseline.action == 'SAFE_STOP'
    assert adaptive.action == 'EXECUTE'
    assert adaptive.next_lift_leg == 2 and adaptive.next_lift_height_m >= .02 and adaptive.next_hold_s >= 1.
    assert adaptive.body_target_w[0]-PROBE[0] >= .03-1e-9
    assert adaptive.body_target_w[1] == pytest.approx(-.11, abs=1e-7)
    assert adaptive.chosen_future_load_n <= 20.+1e-8
    assert adaptive.mpc_force_caps_n[0] == pytest.approx(20.)
    assert adaptive.allocated_forces_n[2] == 0.
    assert adaptive.support_margin_m >= .01
    assert_equilibrium(adaptive.allocated_forces_n, adaptive.body_target_w)


def test_front_right_lift_cannot_be_made_feasible_by_lateral_posture_under_weak_cap():
    certificate = demonstrated(force=27.).certificate
    planner = CapacityPlanner(config=CapacityPlanningConfig(next_lift_leg=1))
    decision = planner.decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4, allow_additional_probe=False)
    assert decision.action == 'SAFE_STOP'


def test_stronger_probe_is_a_separate_request_and_does_not_authorize_uncertified_motion():
    certificate = demonstrated(force=12.).certificate
    planner = CapacityPlanner()
    decision = planner.decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4)
    assert decision.action == 'PROBE'
    assert decision.requested_probe_load_n == 45.
    assert decision.achievable_probe_load_n <= 30.
    assert decision.achievable_probe_load_n > certificate.certified_load_n
    assert decision.chosen_future_load_n == 0.
    assert certificate.force_cap_n == 5.
    assert_equilibrium(decision.allocated_forces_n, decision.body_target_w)
    no_probe = planner.decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4, allow_additional_probe=False)
    assert no_probe.action == 'SAFE_STOP'


def test_unachievable_stronger_probe_causes_safe_stop():
    certificate = demonstrated(force=12.).certificate
    planner = CapacityPlanner(config=CapacityPlanningConfig(probe_force_ceiling_n=8.))
    decision = planner.decide(certificate, ANCHORS, WEIGHT, PROBE, [150.]*4)
    assert decision.action == 'SAFE_STOP'


def test_force_lp_detects_insufficient_weight_support_and_honors_extra_constraints():
    bad = solve_load_allocation(ANCHORS, WEIGHT, PROBE, [0.]*4, [20.]*4)
    assert not bad.feasible
    limited = solve_load_allocation(ANCHORS, WEIGHT, PROBE, [0.]*4, [150.]*4,
        maximize_leg=0, extra_matrix=[[1., 0., 0., 0.]], extra_upper=[15.])
    assert limited.feasible and limited.forces_n[0] == pytest.approx(15.)
    assert_equilibrium(limited.forces_n, limited.com_position_w)
