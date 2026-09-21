"""Matched execution phases, unchanged baseline construction and attribution."""
from types import ModuleType, SimpleNamespace
import sys

import numpy as np
import pytest

from primp_project.control.weak_pad_v2 import WeakPadV2Wrapper
from primp_project.planning.load_capacity import CapacityDecision, CapacityPlanningConfig
from primp_project.probe_efficiency.control import MinimumSufficientWrapper
from primp_project.probe_efficiency.recording import ProbeEfficiencyRecorder


def public_parameters(policy):
    return dict(strategy='adaptive_probe', probe_policy=policy, scenario='test',
        initial_probe_force_n=12., requested_probe_force_n=60., maximum_probe_force_n=60.,
        measurement_reserve_n=1., tracking_reserve_n=8., planning_config={},
        probe_offset_xy_m=[0., 0.], initial_state={}, sensor_config={'force_bias_n': -.6,
        'force_noise_n': .2, 'position_noise_m': 0.}, target_tolerance_n=.001,
        probe_undershoot_allowance_n=.2, seed=123, role='development')


def fake_state(cls):
    wrapper = cls.__new__(cls)
    wrapper.capacity_config = CapacityPlanningConfig()
    wrapper.strategy = 'adaptive_probe'
    wrapper.certificate_estimator = SimpleNamespace(certificate=object())
    wrapper.anchors = np.zeros((4, 3))
    wrapper.weight = 150.
    wrapper.probe_origin_com = np.array([0., 0., .28])
    wrapper.additional_probe_count = 0
    wrapper.origin = 2.
    wrapper.decision_history = []
    wrapper.future_plan_active = True
    wrapper.com_target = np.array([.01, -.02, .28])
    wrapper.target_tolerance_n = .001
    wrapper.sensor_force_error_bound_n = .8
    wrapper.probe_undershoot_allowance_n = .2
    wrapper.enter = lambda phase, time: setattr(wrapper, 'entered', (phase, time))
    return wrapper


@pytest.mark.parametrize('action,phase', [
    ('EXECUTE', 'progress_shift'), ('PROBE', 'reprobe_posture'), ('SAFE_STOP', 'safe_stop'),
])
def test_identical_decision_takes_identical_frozen_phase_transition(monkeypatch, action, phase):
    import primp_project.planning.load_capacity as frozen_planning
    import primp_project.probe_efficiency.control as new_control

    decision = CapacityDecision(action, 'injected matched decision',
        np.array([.04, -.06, .28]), np.array([10., 60., 0., 80.]),
        np.array([11., 150., 0., 150.]), next_lift_leg=2, next_lift_height_m=.03,
        next_hold_s=1., certified_load_n=19., usable_force_cap_n=11.,
        nominal_required_load_n=30., chosen_future_load_n=10.,
        requested_probe_load_n=20., achievable_probe_load_n=20.,
        maximum_achievable_probe_load_n=35.)
    calls = []

    def select(*args, **kwargs):
        calls.append((args, kwargs))
        return decision

    planner = SimpleNamespace(decide=select, last_probe_target=None)
    monkeypatch.setattr(frozen_planning, 'MatchedCapacityPlanner', lambda *a, **k: planner)
    monkeypatch.setattr(new_control, 'MinimumSufficientCapacityPlanner', lambda *a, **k: planner)
    baseline, new = fake_state(WeakPadV2Wrapper), fake_state(MinimumSufficientWrapper)
    baseline._choose_movement(7.)
    new._choose_movement(7.)
    assert baseline.entered == new.entered == (phase, 7.)
    for field in ('required_pad_force_n', 'movement_feasible', 'strategy_state',
                  'additional_probe_count', 'future_plan_active'):
        assert getattr(new, field) == getattr(baseline, field)
    for field in ('progress_target', 'reprobe_target', 'reprobe_start',
                  'maximum_achievable_probe_force_n'):
        assert hasattr(new, field) == hasattr(baseline, field)
        if hasattr(new, field):
            np.testing.assert_equal(getattr(new, field), getattr(baseline, field))
    baseline_log = baseline.decision_history[0]
    new_log = dict(new.decision_history[0])
    assert new_log.pop('minimum_probe_target') is None
    for name in baseline_log:
        np.testing.assert_equal(new_log[name], baseline_log[name])
    assert all(call[1]['allow_additional_probe'] for call in calls)


def test_inherited_execution_monitoring_and_recovery_are_the_frozen_methods():
    for method in ('enter', '_configure_capacity_planner', '_monitor_certificate',
                   '_start_recovery', '_handle_certificate_invalidation',
                   'update_phase', 'references', 'compute_actions'):
        assert getattr(MinimumSufficientWrapper, method) is getattr(WeakPadV2Wrapper, method)


def test_recorder_explicitly_names_policy_without_changing_optimizer_or_reserves(tmp_path):
    records = [ProbeEfficiencyRecorder(tmp_path/policy,
        trial_parameters=public_parameters(policy), rendered=False)
        for policy in ('maximum_feasible', 'minimum_sufficient')]
    a, b = (record.metadata for record in records)
    for key in ('protocol_version', 'experiment', 'strategy', 'movement_optimizer_id',
                'movement_optimizer_settings', 'movement_optimizer_config_sha256',
                'sensor_force_reserve_n', 'tracking_reserve_n', 'sensor_force_error_bound_n',
                'required_forward_progress_m', 'required_next_leg_lift_m',
                'required_progress_hold_s'):
        assert a[key] == b[key]
    assert a['protocol_version'] == 2
    assert a['strategy'] == b['strategy'] == 'adaptive_probe'
    assert a['probe_policy'] == 'maximum_feasible'
    assert b['probe_policy'] == 'minimum_sufficient'
    assert a['sensor_force_reserve_n'] == 1. and a['tracking_reserve_n'] == 8.
    assert a['sensor_force_error_bound_n'] == pytest.approx(.8)
    assert 'evaluation' not in a['trial_parameters']
    assert 'failure_threshold_n' not in a['trial_parameters']


@pytest.mark.parametrize('policy,expected_class', [
    ('maximum_feasible', WeakPadV2Wrapper), ('minimum_sufficient', MinimumSufficientWrapper),
])
def test_runner_uses_exact_frozen_baseline_class_and_hides_capacity_from_controller(
        monkeypatch, tmp_path, policy, expected_class):
    from primp_project.probe_efficiency import analysis, recording, runner
    from quadruped_pympc import config as cfg

    monkeypatch.setattr(cfg, 'robot', 'go2')
    monkeypatch.setitem(cfg.mpc_params, 'type', 'nominal')
    monkeypatch.setitem(cfg.simulation_params, 'gait', 'full_stance')
    monkeypatch.setattr(runner, 'PROJECT_ROOT', tmp_path/'project')
    captured = {}

    def constructor(instance, env, **kwargs):
        captured.update(controller_type=type(instance), controller_args=kwargs, env=env)

    monkeypatch.setattr(WeakPadV2Wrapper, '__init__', constructor)
    monkeypatch.setattr(MinimumSufficientWrapper, '__init__', constructor)

    class Recorder:
        def __init__(self, run_dir, *, trial_parameters, rendered):
            self.metadata = {}
            captured['public'] = trial_parameters

        def save(self, status, error):
            captured['saved'] = (status, error)

    def simulate(**kwargs):
        captured['simulation'] = kwargs
        kwargs['controller_factory'](object(), inherited_parameter='preserved')
        kwargs['experiment_recorder'].metadata['experiment_complete'] = True

    simulation = ModuleType('simulation.simulation')
    simulation.run_simulation = simulate
    monkeypatch.setitem(sys.modules, 'simulation.simulation', simulation)
    monkeypatch.setattr(recording, 'ProbeEfficiencyRecorder', Recorder)
    monkeypatch.setattr(analysis, 'analyze_probe_efficiency', lambda p: {'outcome': 'SAFE_STOP'})
    path, summary = runner.run_trial(probe_policy=policy, failure_threshold_n=42.5,
                                     output_group=tmp_path/'results')
    assert captured['controller_type'] is expected_class
    assert captured['saved'] == ('completed', None)
    assert summary['outcome'] == 'SAFE_STOP' and path.exists()
    args = captured['controller_args']
    assert args['strategy'] == 'adaptive_probe'
    assert args['inherited_parameter'] == 'preserved'
    assert 'failure_threshold_n' not in args
    assert 'failure_threshold_n' not in captured['public']
    assert captured['simulation']['environment_factory'].args[0].failure_load_n == 42.5
    if policy == 'maximum_feasible':
        assert 'target_tolerance_n' not in args and 'probe_undershoot_allowance_n' not in args
    else:
        assert args['target_tolerance_n'] == .001
        assert args['probe_undershoot_allowance_n'] == .2
