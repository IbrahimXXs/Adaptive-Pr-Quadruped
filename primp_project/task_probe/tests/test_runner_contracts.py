"""Policy construction, common execution settings and distinct force channels."""
from dataclasses import asdict
from types import ModuleType, SimpleNamespace
import sys

import numpy as np
import pytest

from primp_project.planning.load_capacity import CapacityDecision
from primp_project.probe_efficiency.control import MinimumSufficientWrapper
from primp_project.recording.weak_pad_v2 import WeakPadV2Recorder
from primp_project.task_probe.control import FixedForceWrapper
from primp_project.task_probe.recording import TaskProbeRecorder


def public_parameters(policy):
    return dict(strategy='adaptive_probe', probe_policy=policy, scenario='contract',
        fixed_probe_force_n=48., initial_probe_force_n=12., requested_probe_force_n=60.,
        maximum_probe_force_n=60., measurement_reserve_n=1., tracking_reserve_n=8.,
        planning_config={'forward_progress_m': .037, 'next_lift_leg': 1,
            'minimum_support_force_n': 12., 'probe_posture_adjustment_m': .1},
        probe_offset_xy_m=[-.04, 0.], initial_state={},
        sensor_config={'force_bias_n': -.6, 'force_noise_n': .2, 'position_noise_m': .0001},
        target_tolerance_n=.001, probe_undershoot_allowance_n=.2, seed=31, role='development')


@pytest.fixture
def runner_harness(monkeypatch, tmp_path):
    from primp_project.task_probe import analysis, recording, runner
    from quadruped_pympc import config as cfg
    captured = []
    active = {}
    monkeypatch.setattr(cfg, 'robot', 'go2')
    monkeypatch.setitem(cfg.mpc_params, 'type', 'nominal')
    monkeypatch.setitem(cfg.simulation_params, 'gait', 'full_stance')
    monkeypatch.setattr(runner, 'PROJECT_ROOT', tmp_path/'project')
    monkeypatch.setenv('PYMPC_ACADOS_EXPORT_DIR', str(tmp_path/'previous_build'))

    def constructor(instance, env, **kwargs):
        active.update(controller_type=type(instance), controller_args=kwargs)

    monkeypatch.setattr(FixedForceWrapper, '__init__', constructor)
    monkeypatch.setattr(MinimumSufficientWrapper, '__init__', constructor)

    class Recorder:
        def __init__(self, run_dir, *, trial_parameters, rendered):
            self.metadata = {}
            active.update(public=trial_parameters, rendered=rendered)

        def save(self, status, error):
            active['saved'] = (status, error)

    def simulate(**kwargs):
        active['simulation'] = kwargs
        kwargs['controller_factory'](object(), inherited_parameter='preserved')
        kwargs['experiment_recorder'].metadata['experiment_complete'] = True
        captured.append(dict(active))

    simulation = ModuleType('simulation.simulation')
    simulation.run_simulation = simulate
    monkeypatch.setitem(sys.modules, 'simulation.simulation', simulation)
    monkeypatch.setattr(recording, 'TaskProbeRecorder', Recorder)
    monkeypatch.setattr(analysis, 'analyze_task_probe', lambda p: {'outcome': 'SAFE_STOP'})
    return runner, captured, active


def test_runner_uses_exact_classes_and_identical_common_execution_settings(runner_harness, tmp_path):
    import os
    runner, captured, active = runner_harness
    for policy in ('fixed_force', 'task_sufficient'):
        parameters = public_parameters(policy)
        parameters.pop('strategy')
        run, result = runner.run_trial(**parameters, failure_threshold_n=47.5,
            headless=True, output_group=tmp_path/'runs')
        assert run.exists() and result['outcome'] == 'SAFE_STOP'
        assert active['saved'] == ('completed', None)
        assert os.environ['PYMPC_ACADOS_EXPORT_DIR'] == str(tmp_path/'previous_build')
    fixed, task = captured
    assert fixed['controller_type'] is FixedForceWrapper
    assert task['controller_type'] is MinimumSufficientWrapper
    fixed_args, task_args = dict(fixed['controller_args']), dict(task['controller_args'])
    assert fixed_args.pop('fixed_probe_force_n') == 48.
    assert task_args.pop('target_tolerance_n') == .001
    assert fixed_args == task_args
    assert fixed_args['measurement_reserve_n'] == 1. and fixed_args['tracking_reserve_n'] == 8.
    assert fixed_args['planning_config'] == public_parameters('fixed_force')['planning_config']
    assert fixed_args['inherited_parameter'] == 'preserved'
    for record in captured:
        assert 'failure_threshold_n' not in record['controller_args']
        assert 'failure_threshold_n' not in record['public']
        assert record['simulation']['environment_factory'].args[0].failure_load_n == 47.5
        assert record['simulation']['lock_zero_velocity']
        assert record['simulation']['stop_on_termination']
        assert np.all(np.asarray(record['simulation']['ref_base_lin_vel']) == 0.)
        assert np.all(np.asarray(record['simulation']['ref_base_ang_vel']) == 0.)
    for key in ('num_episodes', 'num_seconds_per_episode', 'ref_base_lin_vel',
                'ref_base_ang_vel', 'friction_coeff', 'base_vel_command_type', 'seed',
                'render', 'lock_zero_velocity', 'stop_on_termination'):
        assert fixed['simulation'][key] == task['simulation'][key]


@pytest.mark.parametrize('changed', [
    {'measurement_reserve_n': .9}, {'tracking_reserve_n': 7.9},
])
def test_runner_rejects_weakened_shared_reserves_before_simulating(runner_harness, tmp_path, changed):
    runner, captured, _ = runner_harness
    with pytest.raises(ValueError, match='frozen 1 N sensing and 8 N tracking'):
        runner.run_trial(**changed, output_group=tmp_path/'runs')
    assert not captured


def test_recorder_preserves_matched_optimizer_digest_and_physical_criteria(tmp_path):
    records = [TaskProbeRecorder(tmp_path/policy,
        trial_parameters=public_parameters(policy), rendered=False)
        for policy in ('fixed_force', 'task_sufficient')]
    fixed, task = [record.metadata for record in records]
    for key in ('protocol_version', 'experiment', 'strategy', 'movement_optimizer_id',
                'movement_optimizer_settings', 'movement_optimizer_config_sha256',
                'sensor_force_reserve_n', 'tracking_reserve_n', 'sensor_force_error_bound_n',
                'required_forward_progress_m', 'required_next_leg_lift_m',
                'required_progress_hold_s', 'fixed_probe_force_n'):
        assert fixed[key] == task[key]
    assert fixed['fixed_probe_force_n'] == 48.
    assert fixed['sensor_force_reserve_n'] == 1. and fixed['tracking_reserve_n'] == 8.
    assert fixed['movement_optimizer_settings']['forward_progress_m'] == .037
    assert fixed['probe_policy'] == 'fixed_force' and task['probe_policy'] == 'task_sufficient'
    assert fixed['study_name'] == task['study_name'] == 'task_probe'


@pytest.mark.parametrize('policy', ['fixed_force', 'task_sufficient'])
def test_recorder_keeps_selected_command_separate_from_request_budget_and_measured_force(
        monkeypatch, tmp_path, policy):
    recorder = TaskProbeRecorder(tmp_path, trial_parameters=public_parameters(policy), rendered=False)
    selected = 48. if policy == 'fixed_force' else 46.001
    prior_probe = CapacityDecision('PROBE', 'test', np.array([0., 0., .28]),
        np.array([selected, 30., 40., 150.-selected-70.]), np.full(4, 150.),
        next_lift_leg=1, next_lift_height_m=.03, next_hold_s=1.,
        certified_load_n=11., usable_force_cap_n=3., nominal_required_load_n=40.,
        chosen_future_load_n=0., requested_probe_load_n=selected,
        achievable_probe_load_n=selected, minimum_future_load_n=36.)
    final_decision = CapacityDecision('EXECUTE', 'actual proof obtained', np.array([.04, -.02, .28]),
        np.array([37., 0., 60., 53.]), np.array([38., 0., 150., 150.]),
        next_lift_leg=1, next_lift_height_m=.03, next_hold_s=1.,
        certified_load_n=46., usable_force_cap_n=38., nominal_required_load_n=40.,
        chosen_future_load_n=37., minimum_future_load_n=36.)
    wrapper = SimpleNamespace(decision=final_decision,
        decision_history=[asdict(prior_probe), asdict(final_decision)],
        sensor_force_error_bound_n=.8, tracking_reserve_n=8.)

    def record_frozen_observations(self, env, wrapper, *args, **kwargs):
        self.rows['actual_pad_normal_force_n'].append(np.array(45.6))
        self.rows['sensor_pad_normal_force_n'].append(np.array(45.0))
        self.rows['achieved_probe_command_n'].append(np.array(selected))
        self.rows['requested_probe_force_n'].append(np.array(60.))

    monkeypatch.setattr(WeakPadV2Recorder, 'record_step', record_frozen_observations)
    recorder.record_step(object(), wrapper)
    rows = recorder.rows
    assert rows['actual_pad_normal_force_n'][-1] == 45.6
    assert rows['sensor_pad_normal_force_n'][-1] == 45.0
    assert rows['requested_probe_force_n'][-1] == 60.
    assert rows['probe_target_load_n'][-1] == selected
    assert rows['selected_probe_request_n'][-1] == selected
    assert rows['achieved_probe_command_n'][-1] == selected
    assert rows['minimum_sufficient_probe_load_n'][-1] == pytest.approx(45.001)
    assert rows['probe_execution_allowance_n'][-1] == (0. if policy == 'fixed_force' else 1.)


def test_recorder_does_not_invent_a_selected_probe_from_the_global_request(monkeypatch, tmp_path):
    recorder = TaskProbeRecorder(tmp_path, trial_parameters=public_parameters('fixed_force'), rendered=False)
    wrapper = SimpleNamespace(decision=None, decision_history=[], sensor_force_error_bound_n=.8,
                              tracking_reserve_n=8.)
    monkeypatch.setattr(WeakPadV2Recorder, 'record_step', lambda *a, **k: None)
    recorder.record_step(object(), wrapper)
    for key in ('minimum_future_load_n', 'minimum_sufficient_probe_load_n',
                'probe_target_load_n', 'selected_probe_request_n'):
        assert recorder.rows[key][-1] == 0.


def test_source_archive_contains_the_unchanged_task_policy_dependencies(monkeypatch, tmp_path):
    from primp_project import PROJECT_ROOT
    recorder = TaskProbeRecorder(tmp_path, trial_parameters=public_parameters('task_sufficient'), rendered=False)
    monkeypatch.setattr(WeakPadV2Recorder, 'start', lambda *a, **k: None)
    recorder.start(object(), object())
    for relative in ('probe_efficiency/control.py', 'probe_efficiency/planner.py',
                     'task_probe/control.py', 'task_probe/planner.py'):
        assert (tmp_path/'source'/relative).read_bytes() == (PROJECT_ROOT/relative).read_bytes()
