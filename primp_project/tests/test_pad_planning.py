"""Sensor isolation, censored contact inference, and feasible landing planning."""

from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from primp_project.planning.observations import (
    LandingContext, MotionReference, SensorObservation, SensorProfile, SensorStream,
)
from primp_project.planning.belief import GroundHeightBelief
from primp_project.planning.baselines import (
    ConventionalPredictivePlanner, FeasibilityProjector, LearnedMotionPlanner,
    ReactivePlanner, support_halfspaces,
)


ANCHORS = np.array([[.2, -.15, .02], [-.2, .15, .02], [-.2, -.15, .02]])


def context(**kwargs):
    return LandingContext(0., .02, 0., np.array([.29, .15, .05]),
                          np.array([-.2/3, -.05, .28]), np.array([.29, .15]), **kwargs)


def observation(t=0., bottom=.03, contact=False, force=0.):
    return SensorObservation(t, [-.2/3, -.05, .28], [0, 0, 0], [0, 0, 0],
                             [.29, .15, bottom+.02], [0, 0, -.005],
                             [contact, True, True, True], [force, 50, 50, 50], ANCHORS)


def test_sensor_contract_copies_input_and_is_immutable_without_simulator_fields():
    raw = np.array([.29, .15, .05])
    obs = replace(observation(), foot_position=raw)
    raw[:] = 999
    assert obs.foot_position[0] == pytest.approx(.29)
    with pytest.raises(ValueError):
        obs.foot_position[0] = 7
    with pytest.raises(ValueError):
        obs.foot_position.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        obs.environment = object()
    with pytest.raises(TypeError):
        replace(obs, actual_pad_height=.01)


def test_sensor_stream_bounded_noise_and_explicit_delay_are_repeatable():
    profile = SensorProfile("held_out", .0005, .3, .04, seed=17)
    streams = SensorStream(profile), SensorStream(profile)
    histories = []
    for stream in streams:
        sequence = [stream.observe(observation(i*.01, bottom=.03-i*.0001)) for i in range(20)]
        histories.append(sequence)
    for left, right in zip(*histories):
        np.testing.assert_array_equal(left.foot_position, right.foot_position)
        assert left.measurement_time_s <= left.time_s
        original = observation(left.measurement_time_s, bottom=.03-round(left.measurement_time_s/.01)*.0001)
        assert np.max(np.abs(left.foot_position-original.foot_position)) <= .0005+1e-12
        assert np.max(np.abs(left.normal_forces-original.normal_forces)) <= .3+1e-12
    assert histories[0][-1].time_s-histories[0][-1].measurement_time_s == pytest.approx(.04)


def test_missing_contact_censors_height_without_access_to_actual_height():
    belief = GroundHeightBelief(context())
    initial_mean = belief.mean
    for i, bottom in enumerate(np.linspace(.03, -.006, 50)):
        belief.update(observation(i*.05, bottom=bottom))
    assert belief.missing_contact
    assert belief.mean < initial_mean-.005
    assert belief.quantile(.95) < -.004
    probability = belief.probability.copy()
    for i in range(50, 70):
        belief.update(observation(i*.05, bottom=-.006))
    np.testing.assert_array_equal(probability, belief.probability)


def test_early_loaded_contact_updates_height_upwards_and_duplicate_is_ignored():
    belief = GroundHeightBelief(context())
    sample = observation(.5, bottom=.006, contact=True, force=2.)
    belief.update(sample)
    assert belief.mean > .005
    assert belief.std < .0011
    assert belief.contact_observed
    probability = belief.probability.copy()
    belief.update(sample)
    np.testing.assert_array_equal(probability, belief.probability)


@pytest.mark.parametrize("planner_type", [ReactivePlanner, ConventionalPredictivePlanner])
def test_evaluation_truth_cannot_change_a_plan_when_observations_are_identical(planner_type):
    # These evaluation labels intentionally disagree; no planner interface takes
    # either value. Keeping observations equal must keep reference outputs equal.
    outputs = []
    for evaluation_only_height in (-.01, .01):
        c = context()
        obs = observation()
        posterior = GroundHeightBelief(c).update(obs)
        planner = planner_type(c)
        outputs.append(planner.plan(obs, posterior))
    for field in ("com_position", "foot_position", "foot_velocity"):
        np.testing.assert_array_equal(getattr(outputs[0], field), getattr(outputs[1], field))
    assert outputs[0].remaining_time_s == outputs[1].remaining_time_s


def test_reactive_missing_contact_changes_body_foot_and_remaining_time():
    c = context()
    initial_belief = GroundHeightBelief(c)
    missing_belief = GroundHeightBelief(c)
    missing = observation(4., bottom=-.006)
    missing_belief.update(missing)
    nominal = ReactivePlanner(c).plan(observation(), initial_belief)
    adapted = ReactivePlanner(c).plan(missing, missing_belief)
    assert adapted.com_position[2] < nominal.com_position[2]
    assert abs(adapted.foot_velocity[2]) <= c.search_speed+1e-12
    assert adapted.remaining_time_s > nominal.remaining_time_s


def test_predictive_planner_solves_real_constrained_multistep_optimization():
    c = context()
    planner = ConventionalPredictivePlanner(c)
    belief = GroundHeightBelief(c)
    obs = observation()
    first = planner.plan(obs, belief)
    assert planner.optimization_successes == 1
    assert planner.optimization_failures == 0
    assert planner.last_optimization["horizon"] == 8
    assert planner.last_optimization["constraint_violation"] < 1e-7
    assert first.foot_position[2] < c.start_foot_position[2]
    normals, offsets = support_halfspaces(obs.support_anchors, c.support_margin)
    assert np.min(normals@first.com_position[:2]-offsets) >= -1e-8
    missing = observation(4., -.006)
    belief.update(missing)
    revised = planner.plan(missing, belief)
    assert planner.optimization_successes == 2
    assert revised.com_position[2] < first.com_position[2]
    assert abs(revised.foot_velocity[2]) <= c.search_speed+1e-8


def test_shared_projector_bounds_descent_reach_and_three_foot_support():
    c = context()
    projector = FeasibilityProjector(c)
    malicious = MotionReference([10, 10, -10], [99, 99, 99], [1, 1, 1],
                                [.29, .15, -10], [0, 0, -99], [0, 0, -99], 1.)
    obs = observation(5., bottom=-.001)
    normals, offsets = support_halfspaces(ANCHORS, c.support_margin)
    for _ in range(350):
        projected = projector.project(malicious, obs)
        assert projected.foot_position[2] >= c.minimum_foot_z-1e-10
        assert np.linalg.norm(projected.foot_velocity) <= c.search_speed+1e-10
        assert np.min(normals@projected.com_position[:2]-offsets) >= -1e-8
        assert np.max(np.abs(projected.com_position-c.start_com_position)) <= c.max_body_displacement+1e-10
    assert projector.clipped_references == 350


def test_no_contact_search_cannot_descend_beyond_shared_reach_bound():
    c = context()
    planner = ReactivePlanner(c)
    belief = GroundHeightBelief(c)
    for i in range(500):
        obs = observation(i*.05, bottom=-.01)
        belief.update(obs)
        result = planner.plan(obs, belief)
    assert result.foot_position[2] == pytest.approx(c.minimum_foot_z)


def test_geometry_contact_without_loading_is_not_false_missing_contact():
    belief = GroundHeightBelief(context())
    prior = belief.probability.copy()
    belief.update(observation(4., -.002, contact=True, force=.1))
    assert not belief.missing_contact
    assert belief.last_event == "contact_pending_load"
    np.testing.assert_array_equal(prior, belief.probability)


def test_learned_adaptor_uses_demonstrated_body_foot_and_timing_relationships():
    from primp_project.learning.primp import PRIMPMotionModel

    heights = np.array([-.01, -.005, 0., .005, .01])
    durations = 4.-70*heights
    phases = np.linspace(0., 1., 21)
    demonstrations = []
    for height in heights:
        movement = np.zeros((len(phases), 9))
        movement[:, 0] = .2*height*phases
        movement[:, 2] = .3*height*phases
        movement[:, 4] = height*phases
        movement[:, 8] = (height-.03)*phases
        demonstrations.append(movement)
    model = PRIMPMotionModel.fit(demonstrations, heights, durations)
    references = []
    planners = []
    for target_height in (-.005, .005):
        c = context()
        belief = GroundHeightBelief(c)
        belief.probability = np.exp(-.5*((belief.heights-target_height)/.0003)**2)
        belief.probability /= belief.probability.sum()
        planner = LearnedMotionPlanner(c, model)
        planner.phase = .4
        sensed = replace(observation(1.6),
                         com_position=c.start_com_position+np.array([.2*target_height, 0., .3*target_height])*.4,
                         body_rpy=np.array([0., target_height*.4, 0.]),
                         foot_position=c.start_foot_position+np.array([0., 0., (target_height-.03)*.4]))
        planner.accept_reference(MotionReference(sensed.com_position, np.zeros(3), sensed.body_rpy,
            sensed.foot_position, np.zeros(3), np.zeros(3), 2.4), preload_m=0.)
        references.append(planner.plan(sensed, belief))
        planners.append(planner)
    lower, higher = references
    assert lower.com_position[2] < higher.com_position[2]
    assert lower.foot_position[2] < higher.foot_position[2]
    assert planners[0].duration_s > planners[1].duration_s
    assert lower.remaining_time_s > higher.remaining_time_s
    assert all(planner.fallback_count == 0 for planner in planners)


def test_learned_phase_advances_without_reanchoring_unchanged_belief_each_tick():
    from primp_project.learning.primp import PRIMPMotionModel

    heights = np.array([-.005, 0., .005])
    phases = np.linspace(0., 1., 21)
    features = np.zeros((3, len(phases), 9))
    for i, height in enumerate(heights):
        features[i, :, 8] = (height-.03)*phases
    model = PRIMPMotionModel.fit(features, heights, [4., 4., 4.])
    c = context()
    planner = LearnedMotionPlanner(c, model)
    belief = GroundHeightBelief(c)
    for i in range(20):
        result = planner.plan(observation(i*.05), belief)
    assert planner.conditioning_updates == 1
    assert planner.phase > .2
    assert result.foot_position[2] < c.start_foot_position[2]-.006


def test_learned_adaptor_conditions_accepted_reference_and_removes_servo_preload():
    from types import SimpleNamespace

    class RecordingModel:
        def __init__(self):
            self.calls = []

        def condition(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(duration_s=4., sample=lambda phase: (np.zeros(9), np.zeros(9), np.zeros(9)))

    c = context()
    model = RecordingModel()
    planner = LearnedMotionPlanner(c, model)
    obs = replace(observation(), foot_position=c.start_foot_position+[.0005, -.0005, .0005])
    belief = GroundHeightBelief(c)
    planner.plan(obs, belief)
    np.testing.assert_array_equal(model.calls[0]['state_std'], [.0005]*3+[.0002]*3+[.0005]*3)
    np.testing.assert_array_equal(model.calls[0]['current_features'], np.zeros(9))
    accepted = MotionReference(c.start_com_position+[.001, 0., 0.], np.zeros(3), [.0, .001, 0.],
                               c.start_foot_position+[0., 0., -.015], np.zeros(3), np.zeros(3), 2.)
    planner.accept_reference(accepted, preload_m=.003)
    belief.update(observation(.2, bottom=-.005))
    planner.plan(replace(obs, time_s=.2), belief)
    expected = [.001, 0., 0., 0., .001, 0., 0., 0., -.012]
    np.testing.assert_allclose(model.calls[1]['current_features'], expected, atol=1e-12)


def test_reference_conditioning_does_not_mistake_tracking_lag_for_a_higher_landing():
    from primp_project.learning import PRIMPMotionModel

    heights = np.array([-.005, 0., .005])
    phase = np.linspace(0., 1., 21)
    demonstrations = np.zeros((3, len(phase), 9))
    for index, height in enumerate(heights):
        demonstrations[index, :, 8] = (height-.03)*phase
    model = PRIMPMotionModel.fit(demonstrations, heights, [4., 4., 4.])
    c = context()
    belief = GroundHeightBelief(c)
    planner = LearnedMotionPlanner(c, model)
    planner.phase = .5
    accepted = MotionReference(c.start_com_position, np.zeros(3), np.zeros(3),
        c.start_foot_position+[0., 0., -.015], np.zeros(3), np.zeros(3), 2.)
    planner.accept_reference(accepted, preload_m=0.)
    # Real demonstrations/execution show roughly 4 mm of descent tracking lag.
    # That lag must not become an upward correction of the learned touchdown.
    lagged = replace(observation(2.), foot_position=accepted.foot_position+[0., 0., .004])
    planner.plan(lagged, belief)
    wrong_phase_measurement = np.r_[np.zeros(6), lagged.foot_position-c.start_foot_position]
    incorrect = model.condition(belief.mean, belief.std, current_phase=.5,
        current_features=wrong_phase_measurement, state_std=np.array([.0005]*3+[.0002]*3+[.0005]*3))
    assert incorrect.features[-1, 8]-planner.last_prediction.features[-1, 8] > .004
    assert planner.last_prediction.features[-1, 8] == pytest.approx(-.03, abs=.0005)


def test_common_lowering_projector_cannot_retract_a_lightly_touching_foot():
    c = context()
    projector = FeasibilityProjector(c)
    prior = projector.previous
    proposed = replace(prior, foot_position=prior.foot_position+[0., 0., .001])
    projected = projector.project(proposed, observation(contact=True, force=.6))
    assert projected.foot_position[2] == prior.foot_position[2]
    assert projected.foot_velocity[2] == 0.
