"""Checks for motion continuity, tripod geometry, and measured-contact gates."""

from itertools import permutations
from types import SimpleNamespace

import numpy as np
import pytest

from primp_project.controlled_step import ControlledStepWrapper, smooth_motion, support_margin


def test_quintic_motion_has_stationary_endpoints_and_consistent_derivatives():
    start = np.array([0.2, -0.1, 0.02])
    end = np.array([0.17, -0.07, 0.05])
    duration = 2.0
    for t, position in ((-1.0, start), (0.0, start), (duration, end), (duration + 1, end)):
        actual, velocity, acceleration = smooth_motion(start, end, t, duration)
        np.testing.assert_allclose(actual, position, atol=1e-14)
        np.testing.assert_allclose(velocity, 0, atol=1e-14)
        np.testing.assert_allclose(acceleration, 0, atol=1e-14)

    # Compare derivatives against nearby commanded positions, rather than
    # repeating the interpolation polynomial in the test.
    t, h = 0.73, 1e-5
    before = smooth_motion(start, end, t - h, duration)
    current = smooth_motion(start, end, t, duration)
    after = smooth_motion(start, end, t + h, duration)
    np.testing.assert_allclose(current[1], (after[0] - before[0]) / (2*h), atol=1e-10)
    np.testing.assert_allclose(current[2], (after[1] - before[1]) / (2*h), atol=1e-10)


def test_tripod_margin_is_signed_and_independent_of_foot_order():
    triangle = np.array([[0.0, 0.0, 0.02], [2.0, 0.0, 0.02], [0.0, 2.0, 0.02]])
    for order in permutations(range(3)):
        feet = triangle[list(order)]
        assert support_margin([0.5, 0.5, 0.3], feet) == pytest.approx(0.5)
        assert support_margin([1.0, 1.0, 0.3], feet) == pytest.approx(0.0, abs=1e-14)
        assert support_margin([1.2, 1.2, 0.3], feet) == pytest.approx(-0.4 / np.sqrt(2))


def sequence_in_phase(phase):
    """Build just the state machine, avoiding native solver construction."""
    sequence = ControlledStepWrapper.__new__(ControlledStepWrapper)
    sequence.phase = phase
    sequence.phase_start = sequence.origin = 0.0
    sequence.cycles = sequence.cycle = 1
    sequence.completed_cycles = 0
    sequence.experiment_complete = False
    sequence.events = []
    sequence.guard_since = None
    sequence.contact_confirmed = False
    sequence.landing_dwell = 0.0
    sequence.contact_dwell_since = None
    sequence.hold_seconds = 6.0
    sequence.lift_height = 0.03
    sequence.weight = 150.0
    sequence.unload_initial_cap = 37.5
    sequence.anchors = np.array([
        [0.2, 0.15, 0.02], [0.2, -0.15, 0.02],
        [-0.2, 0.15, 0.02], [-0.2, -0.15, 0.02],
    ])
    sequence.center_target = np.array([0.0, 0.0, 0.28])
    sequence.tripod_target = np.array([-0.2/3, -0.05, 0.28])
    sequence.foot_anchor = sequence.anchors[0].copy()
    sequence.foot_target = sequence.foot_anchor.copy()
    sequence.confirm_start = sequence.foot_anchor.copy()
    sequence.nmpc_GRFs = SimpleNamespace(FL=np.array([0.0, 0.0, 37.5]))
    return sequence


def observe(sequence, t, front_contact, front_normal):
    sequence.update_phase(
        t, sequence.anchors.copy(), sequence.tripod_target.copy(),
        np.array([front_contact, True, True, True]),
        np.array([front_normal, 50.0, 50.0, 50.0]), np.zeros(3),
    )


@pytest.mark.parametrize("front_contact,front_normal", [(False, 0.0), (False, 10.0), (True, 1.9)])
def test_reload_requires_loaded_measured_contact_and_times_out_without_it(front_contact, front_normal):
    sequence = sequence_in_phase("confirm")
    for t in (0.0, 0.5, 1.0, 1.9):
        observe(sequence, t, front_contact, front_normal)
        sequence.references(t)
        assert sequence.phase == "confirm"
        assert not sequence.contact_confirmed
        assert sequence.planned[0] == 0
        assert sequence.force_cap == 0.0
    with pytest.raises(RuntimeError, match="No confirmed touchdown"):
        observe(sequence, 2.1, front_contact, front_normal)
    assert not any(event["to"] == "reload" for event in sequence.events)


def test_contact_debounce_restarts_after_interrupted_contact():
    sequence = sequence_in_phase("confirm")
    observe(sequence, 0.00, True, 3.0)
    observe(sequence, 0.06, True, 3.0)
    assert sequence.phase == "confirm"
    observe(sequence, 0.08, False, 0.0)
    assert sequence.contact_dwell_since is None
    assert sequence.landing_dwell == 0.0
    observe(sequence, 0.13, True, 3.0)
    observe(sequence, 0.20, True, 3.0)
    assert sequence.phase == "confirm"
    assert not sequence.contact_confirmed
    observe(sequence, 0.235, True, 3.0)
    assert sequence.phase == "reload"
    assert sequence.contact_confirmed
    assert sequence.landing_dwell == pytest.approx(0.105)
    assert [event["to"] for event in sequence.events] == ["reload"]


def test_touchdown_during_lowering_starts_confirmation_before_reload():
    sequence = sequence_in_phase("lower")
    observe(sequence, 1.0, True, 3.0)
    assert sequence.phase == "confirm"
    assert not sequence.contact_confirmed
    observe(sequence, 1.05, True, 3.0)
    assert sequence.phase == "confirm"
    observe(sequence, 1.10, True, 3.0)
    assert sequence.phase == "reload"
    assert [event["to"] for event in sequence.events] == ["confirm", "reload"]


def test_early_touchdown_preserves_the_last_commanded_foot_position():
    sequence = sequence_in_phase("lower")
    sequence.references(1.5)
    target_before_contact = sequence.foot_target.copy()
    observe(sequence, 1.5, True, 3.0)
    sequence.references(1.5)
    assert sequence.phase == "confirm"
    np.testing.assert_array_equal(sequence.foot_target, target_before_contact)


@pytest.mark.parametrize("phase", ["lift", "hold", "lower", "confirm"])
def test_airborne_and_unconfirmed_landing_keep_binary_three_foot_support(phase):
    sequence = sequence_in_phase(phase)
    for t in (0.0, 0.1, 1.5, 4.0, 6.0):
        sequence.references(t)
        np.testing.assert_array_equal(sequence.planned, [0, 1, 1, 1])
        assert set(np.unique(sequence.planned)) <= {0, 1}
        assert sequence.force_cap == 0.0
        if phase == "hold":
            np.testing.assert_allclose(sequence.foot_target, sequence.foot_anchor + [0, 0, 0.03])
            np.testing.assert_array_equal(sequence.foot_velocity, np.zeros(3))
            np.testing.assert_array_equal(sequence.foot_acceleration, np.zeros(3))


def test_unloading_changes_load_limit_without_fractional_contact_masks():
    sequence = sequence_in_phase("unload")
    caps = []
    for t in np.linspace(0, 3, 31):
        sequence.references(float(t))
        np.testing.assert_array_equal(sequence.planned, [1, 1, 1, 1])
        caps.append(sequence.force_cap)
    assert caps[0] == pytest.approx(sequence.unload_initial_cap)
    assert caps[-1] == pytest.approx(0.0)
    assert np.all(np.diff(caps) <= 1e-12)
