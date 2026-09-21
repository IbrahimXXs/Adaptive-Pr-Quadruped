"""Run blind capacity testing and certified load transfer onto one weak pad."""
import argparse
from datetime import datetime, timezone
from functools import partial
import json
import os
from pathlib import Path
import traceback
from primp_project import PROJECT_ROOT, RESULTS_ROOT

STRATEGIES=('unaware','conservative','adaptive')


def run_trial(*, strategy='adaptive', failure_threshold_n=35., requested_probe_force_n=45.,
              probe_command_limit_n=22., measurement_reserve_n=1., tracking_reserve_n=8.,
              seed=17, headless=True, output_group=None, role='development'):
    import math
    from quadruped_pympc import config as cfg
    from simulation.simulation import run_simulation
    from primp_project.environment.weak_pad import WeakPadSpec, make_weak_pad_env
    from primp_project.control.weak_pad import WeakPadWrapper
    from primp_project.recording.weak_pad import WeakPadRecorder
    if strategy not in STRATEGIES or role not in ('development','evaluation'):
        raise ValueError('Unknown weak-pad strategy or role')
    if not all(math.isfinite(v) and v>0 for v in (failure_threshold_n,requested_probe_force_n,
            probe_command_limit_n,measurement_reserve_n,tracking_reserve_n)):
        raise ValueError('Loads and force reserves must be finite and positive')
    if cfg.robot!='go2' or cfg.mpc_params['type']!='nominal' or cfg.simulation_params['gait']!='full_stance':
        raise ValueError('Weak-pad executor requires Go2 nominal full_stance')
    group=Path(output_group) if output_group else RESULTS_ROOT/'weak_pad'/role
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run_dir=group/f'weak_pad_{strategy}_{stamp}'
    run_dir.mkdir(parents=True,exist_ok=False)
    recorder=WeakPadRecorder(run_dir,strategy=strategy,requested_probe_force_n=requested_probe_force_n,
        probe_command_limit_n=probe_command_limit_n,measurement_reserve_n=measurement_reserve_n,
        tracking_reserve_n=tracking_reserve_n,seed=seed,rendered=not headless,role=role)
    print(f'Recording in {run_dir}',flush=True)
    previous=os.environ.get('PYMPC_ACADOS_EXPORT_DIR')
    build=PROJECT_ROOT/'artifacts'/'cache'/'acados'/f'weak_pad_worker_{os.getpid()}'
    build.mkdir(parents=True,exist_ok=True)
    os.environ['PYMPC_ACADOS_EXPORT_DIR']=str(build)
    error=None
    try:
        run_simulation(qpympc_cfg=cfg,num_episodes=1,num_seconds_per_episode=90,
            ref_base_lin_vel=(0.,0.),ref_base_ang_vel=(0.,0.),friction_coeff=(.8,.8),
            base_vel_command_type='human',seed=seed,render=not headless,
            experiment_recorder=recorder,lock_zero_velocity=True,stop_on_termination=True,
            environment_factory=partial(make_weak_pad_env,
                WeakPadSpec(failure_load_n=failure_threshold_n),run_dir/'scene'),
            controller_factory=lambda env,**kw:WeakPadWrapper(env,strategy=strategy,
                requested_probe_force_n=requested_probe_force_n,probe_command_limit_n=probe_command_limit_n,
                measurement_reserve_n=measurement_reserve_n,tracking_reserve_n=tracking_reserve_n,**kw))
        if not recorder.metadata.get('experiment_complete',False):
            raise RuntimeError('Trial ended without a controlled terminal state')
    except (Exception,KeyboardInterrupt) as exc:
        error=f'{type(exc).__name__}: {exc}'
        (run_dir/'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        if previous is None:os.environ.pop('PYMPC_ACADOS_EXPORT_DIR',None)
        else:os.environ['PYMPC_ACADOS_EXPORT_DIR']=previous
        recorder.save('completed' if error is None else 'failed',error)
    try:
        from primp_project.analysis.weak_pad import analyze_weak_pad
        summary=analyze_weak_pad(run_dir)
    except ImportError:
        summary={'passed':False,'expected_outcome_met':False,'error':error,'analysis':'pending'}
        (run_dir/'weak_pad_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (group/'LATEST.txt').write_text(run_dir.name+'\n')
    print(f"{summary.get('outcome','INCOMPLETE')}: {run_dir}",flush=True)
    return run_dir,summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--strategy',choices=STRATEGIES,default='adaptive')
    p.add_argument('--failure-threshold',type=float,default=35.,help='Simulator-only overload threshold, N')
    p.add_argument('--requested-probe-force',type=float,default=45.)
    p.add_argument('--probe-command-limit',type=float,default=22.)
    p.add_argument('--measurement-reserve',type=float,default=1.)
    p.add_argument('--tracking-reserve',type=float,default=8.)
    p.add_argument('--seed',type=int,default=17)
    p.add_argument('--headless',action='store_true')
    p.add_argument('--role',choices=('development','evaluation'),default='development')
    p.add_argument('--output-group',type=Path)
    a=p.parse_args(argv)
    _,s=run_trial(strategy=a.strategy,failure_threshold_n=a.failure_threshold,
        requested_probe_force_n=a.requested_probe_force,probe_command_limit_n=a.probe_command_limit,
        measurement_reserve_n=a.measurement_reserve,tracking_reserve_n=a.tracking_reserve,
        seed=a.seed,headless=a.headless,role=a.role,output_group=a.output_group)
    return 0 if s.get('expected_outcome_met',False) else 1

if __name__=='__main__':raise SystemExit(main())
