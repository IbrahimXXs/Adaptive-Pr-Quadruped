#!/usr/bin/env python3
"""Run repeated contact-gated front-left steps on known flat ground."""

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
import traceback

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT.parent))

from quadruped_pympc import config as cfg
from simulation.simulation import run_simulation
from primp_project.controlled_step import ControlledStepWrapper
from primp_project.step_recorder import StepRecorder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--hold-seconds', type=float, default=6.)
    parser.add_argument('--friction', type=float, default=.8)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
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
    run_dir = PROJECT / 'runs' / f'step_{stamp}'
    run_dir.mkdir(parents=True)
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
    from primp_project.analyze_step import analyze_step
    passed = analyze_step(run_dir)['passed'] if recorder.rows else False
    (PROJECT / 'runs' / 'LATEST_STEP.txt').write_text(run_dir.name+'\n')
    print(f"\n{'PASS' if passed and error is None else 'FAIL'}: {run_dir}", flush=True)
    return 0 if passed and error is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
