#!/usr/bin/env python3
"""Run repeated contact-gated front-left steps on known flat ground."""

import argparse
from datetime import datetime, timezone
import math
import traceback

from quadruped_pympc import config as cfg
from simulation.simulation import run_simulation
from primp_project import RESULTS_ROOT
from primp_project.control.controlled_step import ControlledStepWrapper
from primp_project.recording.step import StepRecorder
from primp_project.recording.catalog import refresh_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project step", description=__doc__)
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--hold-seconds', type=float, default=6.)
    parser.add_argument('--friction', type=float, default=.8)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args(argv)
    if args.cycles < 1:
        parser.error('--cycles must be positive')
    if not math.isfinite(args.hold_seconds) or not 5 <= args.hold_seconds <= 10:
        parser.error('--hold-seconds must be between 5 and 10')
    if not math.isfinite(args.friction) or not .5 <= args.friction <= 1.2:
        parser.error('--friction must be between 0.5 and 1.2')
    if cfg.robot != 'go2' or cfg.mpc_params['type'] != 'nominal':
        parser.error('This experiment is validated for the current Go2 / nominal MPC setup')
    if cfg.simulation_params['gait'] != 'full_stance' or cfg.simulation_params['scene'] != 'flat':
        parser.error('This experiment requires full_stance and flat configuration')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    results_group = RESULTS_ROOT / 'controlled_step'
    run_dir = results_group / f'step_{stamp}'
    run_dir.mkdir(parents=True, exist_ok=False)
    recorder = StepRecorder(run_dir, args.cycles, args.hold_seconds, args.seed, not args.headless, args.friction)
    print(f'Recording in {run_dir}', flush=True)
    error = None
    try:
        run_simulation(qpympc_cfg=cfg, num_episodes=1,
                       num_seconds_per_episode=args.cycles*(50+args.hold_seconds)+3,
                       ref_base_lin_vel=(0., 0.), ref_base_ang_vel=(0., 0.),
                       friction_coeff=(args.friction, args.friction), base_vel_command_type='human',
                       seed=args.seed, render=not args.headless, experiment_recorder=recorder,
                       lock_zero_velocity=True, stop_on_termination=True,
                       controller_factory=lambda env, **kw: ControlledStepWrapper(
                           env, cycles=args.cycles, hold_seconds=args.hold_seconds, **kw))
        if recorder.metadata['actual_completed_cycles'] != args.cycles:
            raise RuntimeError('Experiment timed out before completing every cycle')
    except (Exception, KeyboardInterrupt) as exc:
        error = f'{type(exc).__name__}: {exc}'
        (run_dir / 'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        recorder.save('completed' if error is None else 'failed', error)
    from primp_project.analysis.step import analyze_step
    passed = analyze_step(run_dir)['passed'] if recorder.rows else False
    (results_group / 'LATEST.txt').write_text(run_dir.name+'\n')
    refresh_catalog()
    print(f"\n{'PASS' if passed and error is None else 'FAIL'}: {run_dir}", flush=True)
    return 0 if passed and error is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
