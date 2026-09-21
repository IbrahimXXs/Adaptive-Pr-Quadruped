"""Run matched probing policies with continuous certification and real recovery."""
import argparse
from datetime import datetime,timezone
from functools import partial
import json
import math
import os
from pathlib import Path
import traceback
from primp_project import PROJECT_ROOT,RESULTS_ROOT


def run_trial(*,strategy='adaptive_probe',failure_threshold_n=25.,scenario='nominal',
              initial_probe_force_n=22.,requested_probe_force_n=60.,maximum_probe_force_n=60.,
              measurement_reserve_n=1.,tracking_reserve_n=8.,planning_config=None,
              probe_offset_xy_m=(0.,0.),initial_state=None,sensor_config=None,seed=17,
              headless=True,output_group=None,role='development'):
    from quadruped_pympc import config as cfg
    from simulation.simulation import run_simulation
    from primp_project.environment.weak_pad import WeakPadSpec,WeakPadInitialState,make_weak_pad_env
    from primp_project.control.weak_pad_v2 import WeakPadV2Wrapper,STRATEGIES
    from primp_project.recording.weak_pad_v2 import WeakPadV2Recorder
    from primp_project.analysis.weak_pad_v2 import analyze_weak_pad_v2
    if strategy not in STRATEGIES or role not in ('development','evaluation'):raise ValueError('Unknown V2 strategy/role')
    values=(failure_threshold_n,initial_probe_force_n,requested_probe_force_n,maximum_probe_force_n,
        measurement_reserve_n,tracking_reserve_n)
    if not all(math.isfinite(x) and x>0 for x in values):raise ValueError('Forces and reserves must be positive and finite')
    if cfg.robot!='go2' or cfg.mpc_params['type']!='nominal' or cfg.simulation_params['gait']!='full_stance':
        raise ValueError('V2 requires Go2 nominal full_stance')
    initial_state={} if initial_state is None else dict(initial_state)
    initial=WeakPadInitialState(**initial_state)
    public=dict(strategy=strategy,scenario=scenario,initial_probe_force_n=initial_probe_force_n,
        requested_probe_force_n=requested_probe_force_n,maximum_probe_force_n=maximum_probe_force_n,
        measurement_reserve_n=measurement_reserve_n,tracking_reserve_n=tracking_reserve_n,
        planning_config=planning_config or {},probe_offset_xy_m=list(probe_offset_xy_m),
        initial_state=initial_state,sensor_config=sensor_config or {},seed=seed,role=role)
    group=Path(output_group) if output_group else RESULTS_ROOT/'weak_pad'/'development_v2'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run_dir=group/f'weak_pad_{strategy}_{stamp}';run_dir.mkdir(parents=True,exist_ok=False)
    recorder=WeakPadV2Recorder(run_dir,trial_parameters=public,rendered=not headless)
    print(f'Recording in {run_dir}',flush=True)
    previous=os.environ.get('PYMPC_ACADOS_EXPORT_DIR')
    build=PROJECT_ROOT/'artifacts'/'cache'/'acados'/f'weak_v2_worker_{os.getpid()}'
    build.mkdir(parents=True,exist_ok=True);os.environ['PYMPC_ACADOS_EXPORT_DIR']=str(build)
    error=None
    try:
        run_simulation(qpympc_cfg=cfg,num_episodes=1,num_seconds_per_episode=110,
            ref_base_lin_vel=(0.,0.),ref_base_ang_vel=(0.,0.),friction_coeff=(.8,.8),
            base_vel_command_type='human',seed=seed,render=not headless,
            experiment_recorder=recorder,lock_zero_velocity=True,stop_on_termination=True,
            environment_factory=partial(make_weak_pad_env,WeakPadSpec(failure_load_n=failure_threshold_n),
                run_dir/'scene',initial_state=initial),
            controller_factory=lambda env,**kw:WeakPadV2Wrapper(env,strategy=strategy,
                initial_probe_force_n=initial_probe_force_n,requested_probe_force_n=requested_probe_force_n,
                maximum_probe_force_n=maximum_probe_force_n,measurement_reserve_n=measurement_reserve_n,
                tracking_reserve_n=tracking_reserve_n,planning_config=planning_config,
                probe_offset_xy_m=probe_offset_xy_m,sensor_config=sensor_config,seed=seed,**kw))
        if not recorder.metadata.get('experiment_complete',False):raise RuntimeError('No controlled terminal state reached')
    except (Exception,KeyboardInterrupt) as exc:
        error=f'{type(exc).__name__}: {exc}';(run_dir/'error.txt').write_text(traceback.format_exc());traceback.print_exc()
    finally:
        if previous is None:os.environ.pop('PYMPC_ACADOS_EXPORT_DIR',None)
        else:os.environ['PYMPC_ACADOS_EXPORT_DIR']=previous
        recorder.save('completed' if error is None else 'failed',error)
    summary=analyze_weak_pad_v2(run_dir)
    (group/'LATEST.txt').write_text(run_dir.name+'\n')
    print(f"{summary['outcome']}: {run_dir}",flush=True)
    return run_dir,summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parameters',type=Path,help='Public trial options plus evaluator-only failure_threshold_n')
    p.add_argument('--strategy',choices=('fixed_probe','adaptive_force_fixed_posture','adaptive_probe'),default='adaptive_probe')
    p.add_argument('--failure-threshold',type=float,default=25.)
    p.add_argument('--headless',action='store_true');p.add_argument('--output-group',type=Path)
    a=p.parse_args(argv)
    kw=json.loads(a.parameters.read_text()) if a.parameters else dict(strategy=a.strategy,failure_threshold_n=a.failure_threshold)
    _,summary=run_trial(**kw,headless=a.headless,output_group=a.output_group)
    return 0 if summary.get('outcome') in ('SUCCESS','SAFE_STOP','RECOVERED_STOP') else 1

if __name__=='__main__':raise SystemExit(main())
