"""Compare probe targets while retaining the frozen V2 execution controller."""
import argparse
from datetime import datetime, timezone
from functools import partial
import json
import math
import os
from pathlib import Path
import traceback

from primp_project import PROJECT_ROOT, RESULTS_ROOT

POLICIES = ('maximum_feasible', 'minimum_sufficient')


def run_trial(*, probe_policy='minimum_sufficient', failure_threshold_n=62.,
              scenario='probe_efficiency', initial_probe_force_n=12.,
              requested_probe_force_n=60., maximum_probe_force_n=60.,
              measurement_reserve_n=1., tracking_reserve_n=8., planning_config=None,
              probe_offset_xy_m=(0., 0.), initial_state=None, sensor_config=None,
              target_tolerance_n=.001, probe_undershoot_allowance_n=.2, seed=17,
              headless=True, output_group=None, role='development'):
    from quadruped_pympc import config as cfg
    from simulation.simulation import run_simulation
    from primp_project.environment.weak_pad import WeakPadSpec, WeakPadInitialState, make_weak_pad_env
    from primp_project.control.weak_pad_v2 import WeakPadV2Wrapper
    from .control import MinimumSufficientWrapper
    from .recording import ProbeEfficiencyRecorder
    from .analysis import analyze_probe_efficiency

    if probe_policy not in POLICIES or role not in ('development', 'evaluation'):
        raise ValueError('Unknown probe policy or trial role')
    positive = (failure_threshold_n, initial_probe_force_n, requested_probe_force_n,
        maximum_probe_force_n, measurement_reserve_n, tracking_reserve_n, target_tolerance_n)
    if not all(math.isfinite(x) and x > 0 for x in positive):
        raise ValueError('Force bounds, reserves and numerical tolerance must be positive')
    if measurement_reserve_n != 1. or tracking_reserve_n != 8.:
        raise ValueError('This focused comparison retains the frozen 1 N sensing and 8 N tracking reserves')
    if target_tolerance_n > .01:
        raise ValueError('The numerical targeting tolerance must not exceed 0.01 N')
    if not math.isfinite(probe_undershoot_allowance_n) or probe_undershoot_allowance_n < 0:
        raise ValueError('Probe undershoot allowance must be finite and nonnegative')
    if cfg.robot != 'go2' or cfg.mpc_params['type'] != 'nominal' or cfg.simulation_params['gait'] != 'full_stance':
        raise ValueError('This experiment requires the frozen Go2 nominal full_stance controller')
    if (planning_config or {}).get('weak_leg', 0) != 0:
        raise ValueError('The frozen stepping controller tests the front-left foot')
    initial_state = dict(initial_state or {})
    initial = WeakPadInitialState(**initial_state)
    public = dict(strategy='adaptive_probe', probe_policy=probe_policy, scenario=scenario,
        initial_probe_force_n=initial_probe_force_n, requested_probe_force_n=requested_probe_force_n,
        maximum_probe_force_n=maximum_probe_force_n, measurement_reserve_n=measurement_reserve_n,
        tracking_reserve_n=tracking_reserve_n, planning_config=planning_config or {},
        probe_offset_xy_m=list(probe_offset_xy_m), initial_state=initial_state,
        sensor_config=sensor_config or {}, target_tolerance_n=target_tolerance_n,
        probe_undershoot_allowance_n=probe_undershoot_allowance_n, seed=seed, role=role)
    group = Path(output_group) if output_group else RESULTS_ROOT/'weak_pad'/'probe_efficiency_development'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run_dir = group/f'weak_pad_{probe_policy}_{stamp}'
    run_dir.mkdir(parents=True, exist_ok=False)
    recorder = ProbeEfficiencyRecorder(run_dir, trial_parameters=public, rendered=not headless)
    print(f'Recording in {run_dir}', flush=True)
    previous = os.environ.get('PYMPC_ACADOS_EXPORT_DIR')
    build = PROJECT_ROOT/'artifacts'/'cache'/'acados'/f'probe_efficiency_worker_{os.getpid()}'
    build.mkdir(parents=True, exist_ok=True)
    os.environ['PYMPC_ACADOS_EXPORT_DIR'] = str(build)
    controller_args = dict(strategy='adaptive_probe', initial_probe_force_n=initial_probe_force_n,
        requested_probe_force_n=requested_probe_force_n, maximum_probe_force_n=maximum_probe_force_n,
        measurement_reserve_n=measurement_reserve_n, tracking_reserve_n=tracking_reserve_n,
        planning_config=planning_config, probe_offset_xy_m=probe_offset_xy_m,
        sensor_config=sensor_config, seed=seed)
    controller = WeakPadV2Wrapper
    if probe_policy == 'minimum_sufficient':
        controller = MinimumSufficientWrapper
        controller_args.update(target_tolerance_n=target_tolerance_n,
            probe_undershoot_allowance_n=probe_undershoot_allowance_n)
    error = None
    try:
        run_simulation(qpympc_cfg=cfg, num_episodes=1, num_seconds_per_episode=110,
            ref_base_lin_vel=(0., 0.), ref_base_ang_vel=(0., 0.), friction_coeff=(.8, .8),
            base_vel_command_type='human', seed=seed, render=not headless,
            experiment_recorder=recorder, lock_zero_velocity=True, stop_on_termination=True,
            environment_factory=partial(make_weak_pad_env, WeakPadSpec(failure_load_n=failure_threshold_n),
                run_dir/'scene', initial_state=initial),
            controller_factory=lambda env, **kw: controller(env, **controller_args, **kw))
        if not recorder.metadata.get('experiment_complete', False):
            raise RuntimeError('No controlled terminal state reached')
    except (Exception, KeyboardInterrupt) as exc:
        error = f'{type(exc).__name__}: {exc}'
        (run_dir/'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        if previous is None:
            os.environ.pop('PYMPC_ACADOS_EXPORT_DIR', None)
        else:
            os.environ['PYMPC_ACADOS_EXPORT_DIR'] = previous
        recorder.save('completed' if error is None else 'failed', error)
    summary = analyze_probe_efficiency(run_dir)
    (group/'LATEST.txt').write_text(run_dir.name+'\n')
    print(f"{summary['outcome']}: {run_dir}", flush=True)
    return run_dir, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parameters', type=Path, required=True)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--output-group', type=Path)
    args = parser.parse_args(argv)
    parameters = json.loads(args.parameters.read_text())
    _, result = run_trial(**parameters, headless=args.headless, output_group=args.output_group)
    return 0 if result['outcome'] in ('SUCCESS', 'SAFE_STOP', 'RECOVERED_STOP') else 1


if __name__ == '__main__':
    raise SystemExit(main())
