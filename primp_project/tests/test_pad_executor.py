"""Contact-gate and interpolation checks without constructing native solvers."""

from types import SimpleNamespace

import numpy as np
import pytest

from primp_project.control.landing_pad import LandingPadWrapper
from primp_project.planning import SensorObservation, SensorProfile, SensorStream
from primp_project.tests.test_controlled_step import sequence_in_phase


def executor():
    wrapper = LandingPadWrapper.__new__(LandingPadWrapper)
    wrapper.__dict__.update(sequence_in_phase('hold').__dict__)
    wrapper.env = SimpleNamespace(
        mjData=SimpleNamespace(subtree_linvel=np.zeros((1, 3))),
        base_ori_euler_xyz=np.zeros(3),
        feet_vel=lambda **kwargs: SimpleNamespace(FL=np.zeros(3)),
    )
    wrapper.sensor_stream = SensorStream(SensorProfile())
    wrapper.target_xy = wrapper.foot_anchor[:2]+[.09, 0.]
    wrapper.foot_radius = .02
    wrapper.initial_estimate = 0.
    wrapper.planner_name = 'reactive'
    wrapper.lower_duration = wrapper.remaining_time = 4.
    wrapper.body_orientation_ref = np.zeros(3)
    wrapper.com_target = wrapper.tripod_target.copy()
    wrapper.com_velocity = np.zeros(3)
    wrapper.foot_target = np.r_[wrapper.target_xy, .05]
    wrapper.foot_velocity = wrapper.foot_acceleration = np.zeros(3)
    wrapper.sensor_observation = SensorObservation(
        0., wrapper.com_target, np.zeros(3), np.zeros(3), wrapper.foot_target,
        np.zeros(3), [False, True, True, True], [0., 50., 50., 50.], wrapper.anchors[1:])
    wrapper.belief = wrapper.planner = wrapper.context = wrapper.projector = None
    wrapper.landing_frozen = False
    wrapper.enter('lower', 0.)
    return wrapper


def observe(wrapper, t, contact=False, force=0., support_force=50.):
    feet = wrapper.anchors.copy()
    feet[0] = wrapper.foot_target
    wrapper.update_phase(t, feet, wrapper.tripod_target,
                         np.array([contact, True, True, True]),
                         np.array([force, support_force, 50., 50.]), np.zeros(3))


def test_landing_reload_requires_continuous_loaded_contact_and_resets_on_dropout():
    wrapper = executor()
    observe(wrapper, 1., True, 1.99)
    assert wrapper.phase == 'lower'
    assert not wrapper.landing_frozen
    observe(wrapper, 1.1, True, 2.)
    assert wrapper.phase == 'confirm' and wrapper.landing_frozen
    observe(wrapper, 1.19, True, 2.)
    assert wrapper.phase == 'confirm'
    observe(wrapper, 1.195, False, 0.)
    assert wrapper.contact_dwell_since is None
    observe(wrapper, 1.2, True, 2.)
    observe(wrapper, 1.299, True, 2.)
    assert wrapper.phase == 'confirm'
    observe(wrapper, 1.3, True, 2.)
    assert wrapper.phase == 'reload'
    assert wrapper.contact_confirmed


def test_no_contact_keeps_three_leg_schedule_and_rejects_unbounded_wait():
    wrapper = executor()
    observe(wrapper, 4.1)
    wrapper.references(4.1)
    assert wrapper.phase == 'confirm'
    np.testing.assert_array_equal(wrapper.planned, [0, 1, 1, 1])
    assert wrapper.force_cap == 0.
    assert not wrapper.contact_confirmed
    with pytest.raises(RuntimeError, match='bounded descent/time'):
        observe(wrapper, 12.001)
    assert wrapper.phase == 'confirm'


def test_support_loss_aborts_before_changing_landing_schedule():
    wrapper = executor()
    with pytest.raises(RuntimeError, match='Three-leg support lost'):
        observe(wrapper, 1., support_force=4.99)
    assert not wrapper.contact_confirmed


def test_contact_confirmation_after_deadline_cannot_transfer_weight():
    wrapper = executor()
    observe(wrapper, 11.95, True, 3.)
    with pytest.raises(RuntimeError, match='bounded descent/time'):
        observe(wrapper, 12.051, True, 3.)
    assert wrapper.phase == 'confirm'
    assert not wrapper.contact_confirmed


def test_freeze_and_resume_reference_is_continuous_after_transient_contact():
    wrapper = executor()
    wrapper.references(0.)
    wrapper.references(.02)
    frozen_foot = wrapper.foot_target.copy()
    frozen_com = wrapper.com_target.copy()
    # Interrupt the first 50 ms segment before it reaches its endpoint.
    observe(wrapper, .02, True, 2.1)
    wrapper.references(.02)
    np.testing.assert_array_equal(wrapper.foot_velocity, np.zeros(3))
    observe(wrapper, .1, False, 0.)
    wrapper.references(.1)
    np.testing.assert_allclose(wrapper.foot_target, frozen_foot, atol=1e-14)
    np.testing.assert_allclose(wrapper.com_target, frozen_com, atol=1e-14)
    wrapper.references(.102)
    assert np.linalg.norm(wrapper.foot_target-frozen_foot) <= wrapper.context.max_foot_speed*.002+1e-12


def test_nominal_interpolation_respects_shared_speed_bound_between_ticks():
    wrapper = executor()
    previous = wrapper.foot_target.copy()
    for i in range(101):
        t = i*.002
        observe(wrapper, t)
        wrapper.references(t)
        assert np.linalg.norm(wrapper.foot_target-previous) <= wrapper.context.max_foot_speed*.002+1e-12
        previous = wrapper.foot_target.copy()
