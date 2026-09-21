"""Run one controlled step onto a separate, adjustable landing pad."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
import json
from pathlib import Path
import traceback

from primp_project import RESULTS_ROOT

PLANNERS = ('reactive', 'predictive', 'learned', 'matched_predictive', 'matched_learned',
            'matched_no_body_foot_correlation', 'matched_no_timing_adaptation', 'matched_no_noncontact_updates')


def run_trial(*, actual_height_m, initial_estimate_m=0., planner='reactive', role='evaluation',
              lower_duration_s=4., sensor_profile='clean', seed=17, headless=True,
              model_path=None, output_group=None, recovery_model_path=None,
              recovery_demonstration=False, initial_condition='nominal'):
    from quadruped_pympc import config as cfg
    from simulation.simulation import run_simulation
    from primp_project.environment import LandingPadSpec, make_landing_pad_env
    from primp_project.planning import SENSOR_PROFILES
    from primp_project.control.landing_pad import LandingPadWrapper
    from primp_project.recording.pad import PadRecorder
    from primp_project.analysis.pad import analyze_pad
    import math
    if planner not in PLANNERS or role not in ('development', 'demonstration', 'evaluation'):
        raise ValueError('Unknown planner or trial role')
    if initial_condition not in ('nominal', 'raised'):
        raise ValueError('Unknown initial condition')
    if recovery_demonstration and role != 'demonstration':
        raise ValueError('Recovery training labels require demonstration role')
    if not all(math.isfinite(x) for x in (actual_height_m, initial_estimate_m, lower_duration_s)):
        raise ValueError('Trial heights and duration must be finite')
    if abs(actual_height_m) > .025 or abs(initial_estimate_m) > .015 or not 3 <= lower_duration_s <= 5:
        raise ValueError('Pilot supports actual heights within ±25mm, estimates ±15mm, and durations 3–5s')
    if role == 'demonstration' and not recovery_demonstration and abs(actual_height_m-initial_estimate_m) > 1e-12:
        raise ValueError('Demonstrations require an explicitly known landing height')
    if cfg.robot != 'go2' or cfg.mpc_params['type'] != 'nominal' or cfg.simulation_params['gait'] != 'full_stance':
        raise ValueError('Validated executor requires Go2, nominal MPC, full_stance')
    model = recovery_model = None
    if planner == 'learned' or (planner.startswith('matched_') and planner != 'matched_predictive'):
        from primp_project.learning import PRIMPMotionModel
        if model_path is None:
            raise ValueError('Learned planner requires --model')
        model = PRIMPMotionModel.load(Path(model_path))
        if planner.startswith('matched_'):
            from primp_project.learning.recovery import RecoveryMotionModel
            if recovery_model_path is None:
                raise ValueError('Matched learned planner requires --recovery-model')
            recovery_model = RecoveryMotionModel.load(Path(recovery_model_path))
    profile = replace(SENSOR_PROFILES[sensor_profile], seed=seed)
    group = Path(output_group) if output_group else RESULTS_ROOT/'landing_pad'/dict(development='development', demonstration='demonstrations', evaluation='evaluation')[role]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run_dir = group/f'pad_{planner}_{stamp}'
    run_dir.mkdir(parents=True, exist_ok=False)
    recorder = PadRecorder(run_dir, initial_estimate_m=initial_estimate_m, planner=planner, role=role,
        lower_duration_s=lower_duration_s, sensor_profile=profile, seed=seed, rendered=not headless,
        model_path=model_path, known_height_m=actual_height_m if role == 'demonstration' else None,
        recovery_model_path=recovery_model_path, recovery_demonstration=recovery_demonstration,
        initial_condition=initial_condition)
    print(f'Recording in {run_dir}', flush=True)
    error = None
    try:
        run_simulation(qpympc_cfg=cfg, num_episodes=1, num_seconds_per_episode=55,
            ref_base_lin_vel=(0.,0.), ref_base_ang_vel=(0.,0.), friction_coeff=(.8,.8),
            base_vel_command_type='human', seed=seed, render=not headless,
            experiment_recorder=recorder, lock_zero_velocity=True, stop_on_termination=True,
            environment_factory=partial(make_landing_pad_env, LandingPadSpec(true_height_m=actual_height_m), run_dir/'scene'),
            controller_factory=lambda env, **kw: LandingPadWrapper(env, initial_estimate_m=initial_estimate_m,
                planner_name=planner, lower_duration_s=lower_duration_s, sensor_profile=profile, model=model,
                recovery_model=recovery_model, initial_condition=initial_condition, **kw))
        if recorder.metadata['actual_completed_cycles'] != 1:
            raise RuntimeError('Trial ended before completing the step')
    except (Exception, KeyboardInterrupt) as exc:
        error = f'{type(exc).__name__}: {exc}'
        (run_dir/'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        recorder.save('completed' if error is None else 'failed', error)
    summary = analyze_pad(run_dir) if recorder.rows else {'passed':False, 'error':error}
    if not recorder.rows:
        (run_dir/'pad_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (group/'LATEST.txt').write_text(run_dir.name+'\n')
    print(f"{'PASS' if summary['passed'] and error is None else 'FAIL'}: {run_dir}", flush=True)
    return run_dir, summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m primp_project pad', description=__doc__)
    parser.add_argument('--actual-height', type=float, required=True, help='Simulator-only surface height in metres')
    parser.add_argument('--estimate', type=float, default=0., help='Initial height estimate in metres')
    parser.add_argument('--planner', choices=PLANNERS, default='reactive')
    parser.add_argument('--role', choices=('development','demonstration','evaluation'), default='evaluation')
    parser.add_argument('--lower-seconds', type=float, default=4.)
    parser.add_argument('--sensors', choices=('clean','noisy_delayed'), default='clean')
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--recovery-model', type=Path)
    parser.add_argument('--recovery-demonstration', action='store_true')
    parser.add_argument('--initial-condition', choices=('nominal', 'raised'), default='nominal')
    parser.add_argument('--output-group', type=Path)
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args(argv)
    _, summary = run_trial(actual_height_m=args.actual_height, initial_estimate_m=args.estimate,
        planner=args.planner, role=args.role, lower_duration_s=args.lower_seconds,
        sensor_profile=args.sensors, seed=args.seed, headless=args.headless, model_path=args.model,
        recovery_model_path=args.recovery_model, recovery_demonstration=args.recovery_demonstration,
        initial_condition=args.initial_condition, output_group=args.output_group)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
