"""Matched optimization, measured-state recovery, and controlled ablations."""

from dataclasses import replace
import numpy as np
import pytest

from primp_project.learning import PRIMPMotionModel
from primp_project.learning.recovery import RecoveryMotionModel
from primp_project.planning import GroundHeightBelief, MotionReference
from primp_project.planning.matched import MatchedPlanner, VARIANTS
from primp_project.tests.test_pad_planning import context, observation


@pytest.fixture
def models():
    heights = np.linspace(-.012, .012, 7)
    phase = np.linspace(0., 1., 15)
    features = np.zeros((7, len(phase), 9))
    for i, h in enumerate(heights):
        features[i, :, 0] = .1*h*phase
        features[i, :, 2] = .3*h*phase
        features[i, :, 4] = .5*h*phase
        features[i, :, 8] = (h-.03)*phase
    nominal = PRIMPMotionModel.fit(features, heights, 4.-30*heights)
    clearance = np.linspace(.0001, .02, 7)
    windows = np.zeros_like(features)
    for i, height in enumerate(clearance):
        windows[i, :, 2] = -.25*height*phase
        windows[i, :, 4] = .3*height*phase
        windows[i, :, 8] = -height*phase
    recovery = RecoveryMotionModel.fit(windows, clearance, .2+clearance/.005)
    return nominal, recovery


def test_noncontact_ablation_preserves_missing_event_and_contact_updates():
    belief = GroundHeightBelief(context(), noncontact_updates=False)
    initial = belief.probability.copy()
    belief.update(observation(5., bottom=-.006))
    np.testing.assert_array_equal(belief.probability, initial)
    assert belief.missing_contact
    assert belief.last_event == 'missing_contact_no_update'
    belief.update(observation(5.1, bottom=-.006, contact=True, force=2.))
    assert belief.contact_observed and not belief.missing_contact
    assert belief.mean < -.005


@pytest.mark.parametrize('variant', VARIANTS)
def test_every_variant_uses_same_optimization_freedoms_and_limits(models, variant):
    c = context()
    planner = MatchedPlanner(c, *models, variant=variant)
    belief = GroundHeightBelief(c)
    ref = planner.plan(observation(), belief)
    assert planner.last_optimization['success'], planner.last_optimization
    assert planner.last_optimization['variables'] == 46
    assert planner.last_optimization['horizon'] == 5
    assert planner.last_optimization['constraint_violation'] < 1e-5
    assert np.linalg.norm(ref.foot_position-c.start_foot_position) <= c.max_foot_speed*c.planning_dt+1e-8
    assert np.linalg.norm(ref.com_position-c.start_com_position) <= c.max_com_speed*c.planning_dt+1e-8
    assert np.all(np.abs(ref.body_rpy-c.start_body_rpy) <= .02*c.planning_dt+1e-8)
    assert ref.remaining_time_s > 0.


@pytest.mark.parametrize('variant', VARIANTS)
def test_recovery_time_is_positive_from_current_measurement_after_nominal_clock_expires(models, variant):
    c = context()
    planner = MatchedPlanner(c, *models, variant=variant)
    measured = observation(20., bottom=-.006)
    belief = GroundHeightBelief(c, noncontact_updates=variant != 'no_noncontact_updates').update(measured)
    accepted = MotionReference(c.start_com_position, np.zeros(3), c.start_body_rpy,
        measured.foot_position-[0., 0., .004], np.zeros(3), np.zeros(3), 1.)
    planner.accept_reference(accepted, preload_m=.004)
    reference = planner.plan(measured, belief)
    assert planner.recovery_active
    assert reference.remaining_time_s >= .15
    assert planner.model_remaining_time_s > 0.
    assert planner.optimized_remaining_time_s > 0.
    np.testing.assert_array_equal(planner.planning_anchor_foot_w, measured.foot_position)
    np.testing.assert_array_equal(planner.planning_anchor_com_w, measured.com_position)
    assert np.linalg.norm(reference.foot_velocity) <= c.search_speed+1e-7
    assert reference.foot_position[2] <= accepted.foot_position[2]+1e-9


def test_conditional_correlation_ablation_preserves_marginals_and_positive_covariance(models):
    c = context()
    full = MatchedPlanner(c, *models, variant='learned')
    ablated = MatchedPlanner(c, *models, variant='no_body_foot_correlation')
    obs, belief = observation(), GroundHeightBelief(c)
    (_, covariance, _), _ = full._learned_prior(obs, belief, 0., 4.)
    (_, changed, _), _ = ablated._learned_prior(obs, belief, 0., 4.)
    body = np.array([9*i+j for i in range(5) for j in range(6)])
    foot = np.array([9*i+j for i in range(5) for j in range(6, 9)])
    np.testing.assert_allclose(changed[np.ix_(body, body)], covariance[np.ix_(body, body)])
    np.testing.assert_allclose(changed[np.ix_(foot, foot)], covariance[np.ix_(foot, foot)])
    np.testing.assert_allclose(changed[-1], covariance[-1])
    conditional_cross = changed[np.ix_(body, foot)]-np.outer(changed[body, -1], changed[-1, foot])/changed[-1, -1]
    np.testing.assert_allclose(conditional_cross, 0., atol=1e-15)
    assert np.linalg.eigvalsh(changed).min() >= -1e-12

    # The common numerical/waypoint floors include log time, so verify the
    # covariance actually inverted by the optimizer, not only the raw model.
    full.plan(obs, belief)
    ablated.plan(obs, belief)
    covariance, changed = full.last_prior_covariance, ablated.last_prior_covariance
    np.testing.assert_allclose(changed[np.ix_(body, body)], covariance[np.ix_(body, body)])
    np.testing.assert_allclose(changed[np.ix_(foot, foot)], covariance[np.ix_(foot, foot)])
    np.testing.assert_allclose(changed[-1], covariance[-1])
    conditional_cross = changed[np.ix_(body, foot)]-np.outer(changed[body, -1], changed[-1, foot])/changed[-1, -1]
    np.testing.assert_allclose(conditional_cross, 0., atol=1e-13)
    assert np.linalg.eigvalsh(changed).min() > 0.


def test_unsupported_prior_is_actually_disabled_and_fallback_is_explicit(models):
    c = context()
    planner = MatchedPlanner(c, *models, variant='learned')
    belief = GroundHeightBelief(c)
    belief.probability[:] = 0.
    belief.probability[-1] = 1.
    result = planner.plan(observation(), belief)
    assert planner.fallback_active and planner.fallback_reason == 'prior_out_of_support'
    assert not planner.model_features_active
    assert not planner.last_optimization['learned_prior_active']
    assert planner.fallback_count == planner.fallback_events == 1
    assert planner.fallback_displacement_m == pytest.approx(np.linalg.norm(result.foot_position-c.start_foot_position))
    planner.accept_reference(result)
    ordinary = GroundHeightBelief(c)
    planner.plan(observation(.2), ordinary)
    assert not planner.fallback_active and planner.fallback_reason == ''


def test_missing_recovery_model_does_not_masquerade_as_learned_recovery(models):
    c = context()
    planner = MatchedPlanner(c, model=models[0], variant='learned')
    obs = observation(5., bottom=-.003)
    belief = GroundHeightBelief(c).update(obs)
    planner.plan(obs, belief)
    assert planner.fallback_reason == 'recovery_prior_unavailable'
    assert planner.fallback_active and not planner.model_features_active


def test_failed_learned_optimization_records_only_the_executed_fallback(models, monkeypatch):
    import primp_project.planning.matched as implementation

    original = implementation.minimize

    def fail_after_attempt(*args, **kwargs):
        result = original(*args, **kwargs)
        result.success = False
        result.message = 'Forced optimization failure'
        return result

    monkeypatch.setattr(implementation, 'minimize', fail_after_attempt)
    c = context()
    planner = MatchedPlanner(c, *models, variant='learned')
    reference = planner.plan(observation(), GroundHeightBelief(c))
    assert planner.last_optimization['learned_prior_attempted']
    assert not planner.last_optimization['learned_prior_active']
    assert not planner.model_features_active
    assert planner.fallback_active and planner.fallback_reason == 'optimizer_failure'
    assert planner.optimization_failures == planner.fallback_count == 1
    np.testing.assert_array_equal(reference.com_position, c.start_com_position)
    np.testing.assert_array_equal(reference.body_rpy, c.start_body_rpy)
    np.testing.assert_allclose(reference.foot_position,
        c.start_foot_position-[0., 0., c.max_foot_speed*c.planning_dt])

    # A later successful solve must restore prior attribution rather than
    # permanently inheriting the failure state.
    monkeypatch.setattr(implementation, 'minimize', original)
    planner.accept_reference(reference)
    planner.plan(observation(.05), GroundHeightBelief(c))
    assert planner.model_features_active
    assert planner.last_optimization['learned_prior_active']
    assert not planner.fallback_active and planner.fallback_reason == ''


def test_exhausted_belief_target_uses_identical_conventional_search_for_both_planners(models):
    c = context()
    belief = GroundHeightBelief(c)
    foot = c.start_foot_position.copy()
    foot[2] = belief.quantile(.25)+c.foot_radius-c.contact_compression_m-.0002
    accepted = MotionReference(c.start_com_position, np.zeros(3), c.start_body_rpy,
        foot, np.zeros(3), np.zeros(3), 1.)
    obs = observation(4., bottom=foot[2]-c.foot_radius+.004)
    learned = MatchedPlanner(c, *models, variant='learned')
    conventional = MatchedPlanner(c, *models, variant='predictive')
    references = []
    for planner in (learned, conventional):
        planner.accept_reference(accepted, preload_m=.004)
        references.append(planner.plan(obs, belief))
        assert planner.last_optimization['success']
        assert planner.fallback_reason == 'bounded_search_beyond_belief_target'
        assert planner.fallback_active and not planner.model_features_active
        assert not planner.last_optimization['learned_prior_active']
    np.testing.assert_allclose(references[0].com_position, references[1].com_position)
    np.testing.assert_allclose(references[0].body_rpy, references[1].body_rpy)
    np.testing.assert_allclose(references[0].foot_position, references[1].foot_position)
    assert references[0].remaining_time_s == pytest.approx(references[1].remaining_time_s)


def test_terrain_posterior_is_identical_before_and_after_all_variant_plans(models):
    c, obs = context(), observation(4., bottom=-.001)
    belief = GroundHeightBelief(c).update(obs)
    original = belief.probability.copy()
    for variant in VARIANTS:
        planner = MatchedPlanner(c, *models, variant=variant)
        planner.plan(obs, belief)
        np.testing.assert_array_equal(belief.probability, original)


def test_recovery_stays_latched_through_weak_contact_before_support_confirmation(models):
    c = context()
    planner = MatchedPlanner(c, *models, variant='learned')
    belief = GroundHeightBelief(c).update(observation(5., bottom=-.003))
    first = planner.plan(observation(5., bottom=-.003), belief)
    planner.accept_reference(first)
    weak_contact = observation(5.1, bottom=-.003, contact=True, force=.6)
    belief.update(weak_contact)
    assert not belief.missing_contact
    planner.plan(weak_contact, belief)
    assert planner.recovery_active
    assert planner.raw_model_remaining_time_s > 0.


def test_timing_ablation_keeps_learned_motion_and_only_removes_learned_timing_terms(models):
    c, obs = context(), observation()
    belief = GroundHeightBelief(c)
    full = MatchedPlanner(c, *models, variant='learned')
    ablated = MatchedPlanner(c, *models, variant='no_timing_adaptation')
    (mean, covariance, _), _ = full._learned_prior(obs, belief, 0., 3.1)
    (mean_without_time, changed, log_time), _ = ablated._learned_prior(obs, belief, 0., 3.1)
    np.testing.assert_allclose(mean_without_time, mean)
    np.testing.assert_allclose(changed[:-1, :-1], covariance[:-1, :-1])
    np.testing.assert_array_equal(changed[:-1, -1], np.zeros(len(changed)-1))
    assert log_time == pytest.approx(np.log(3.1))


@pytest.mark.parametrize('variant', ['predictive', 'learned', 'no_body_foot_correlation', 'no_timing_adaptation'])
def test_optimizer_objective_and_speed_constraint_gradients_match_numerical_differences(models, monkeypatch, variant):
    import primp_project.planning.matched as implementation

    original = implementation.minimize
    checked = []

    def verify_and_solve(function, initial, **kwargs):
        point = initial.copy()+.017*np.sin(np.arange(len(initial))+.7)
        point[-1] = initial[-1]+.03
        h = 1e-6
        numerical = np.empty_like(point)
        speed = kwargs['constraints'][1]
        numerical_speed = np.empty((len(speed['fun'](point)), len(point)))
        for index in range(len(point)):
            delta = np.zeros_like(point)
            delta[index] = h
            numerical[index] = (function(point+delta)[0]-function(point-delta)[0])/(2*h)
            numerical_speed[:, index] = (speed['fun'](point+delta)-speed['fun'](point-delta))/(2*h)
        np.testing.assert_allclose(function(point)[1], numerical, rtol=2e-5, atol=2e-6)
        np.testing.assert_allclose(speed['jac'](point), numerical_speed, rtol=2e-5, atol=2e-6)
        checked.append(True)
        return original(function, initial, **kwargs)

    monkeypatch.setattr(implementation, 'minimize', verify_and_solve)
    c = context()
    planner = MatchedPlanner(c, *models, variant=variant)
    planner.plan(observation(), GroundHeightBelief(c))
    assert checked == [True]
    assert planner.last_optimization['success']
