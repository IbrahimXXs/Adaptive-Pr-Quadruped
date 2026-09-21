"""Read-only independent checks of frozen V2 evidence; rerunnable while collecting.

Run with the project conda Python. This utility never invokes a controller or
rewrites canonical summaries. Per-tick measurements are correlated observations,
not independent experimental replicates.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

MOVEMENT=('plan','execute','progress_shift','next_unload','next_lift','progress_hold','progress_complete')
PROBE=('probe_ramp','probe_hold','probe_release','reprobe_posture')
RECOVERY=('recovery_unload','recovery_lift','recovery_hold')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def longest(mask,dt):
    where=np.flatnonzero(mask)
    if not len(where):return 0.,[]
    pieces=np.split(where,np.flatnonzero(np.diff(where)!=1)+1)
    best=max(pieces,key=len)
    return len(best)*dt,best


def triangle_margin(com,feet):
    xy=feet[:,:,:2];point=com[:,:2]
    def cross(a,b):return a[:,0]*b[:,1]-a[:,1]*b[:,0]
    area=cross(xy[:,1]-xy[:,0],xy[:,2]-xy[:,0])
    values=[]
    for i in range(3):
        edge=xy[:,(i+1)%3]-xy[:,i]
        values.append(np.sign(area)*cross(edge,point-xy[:,i])/np.maximum(1e-12,np.linalg.norm(edge,axis=1)))
    return np.min(np.stack(values),axis=0)


def certificate_history(data,metadata):
    t=data['control_time_s'];valid=data['certificate_valid'].astype(bool)
    ends=data['probe_evidence_end_time_s'];starts=data['probe_evidence_start_time_s']
    feet=data['sensor_pad_foot_pos_w'];contacts=data['sensor_contact_measured'][:,0].astype(bool)
    anchor=None;invalid_since=None;last_end=-np.inf;last_force=0.;failures=[];proofs=0
    for i in range(len(t)):
        if anchor is not None and invalid_since is None:
            motion=feet[i]-anchor
            if not contacts[i] or np.linalg.norm(motion[:2])>.010+1e-8 or abs(motion[2])>.0025+1e-8:
                invalid_since=float(t[i])
        if i and valid[i-1] and not valid[i] and invalid_since is None:invalid_since=float(t[i])
        if not valid[i]:continue
        force=data['certificate_force_n'][i]
        new=anchor is None or ends[i]>last_end+1e-8 or force>last_force+1e-8 or i and not valid[i-1]
        if invalid_since is not None:
            if not new or starts[i]<invalid_since-1e-8:
                failures.append('stale_invalidated_certificate');break
            invalid_since=None
        if new:
            rows=np.flatnonzero((t>=starts[i]-1e-8)&(t<=ends[i]+1e-8));proofs+=1
            passed=(len(rows)>=2 and ends[i]<=t[i]+1e-8 and t[rows[-1]]-t[rows[0]]>=metadata['probe_dwell_s']-1e-8
                and np.all(contacts[rows]) and np.all(np.isin(data['phase'][rows],PROBE))
                and data['certificate_observation_phase'][i]=='probe_hold'
                and np.ptp(data['sensor_pad_normal_force_n'][rows])<=1.5+1e-8
                and force<=np.min(data['sensor_pad_normal_force_n'][rows])-metadata['sensor_force_reserve_n']+1e-6
                and force<=np.min(data['actual_pad_normal_force_n'][rows])+1e-6
                and np.max(np.linalg.norm(feet[rows]-feet[rows[0]],axis=1))<=metadata['max_probe_motion_m']+1e-8
                and np.max(np.linalg.norm(data['sensor_pad_foot_vel_w'][rows],axis=1))<=.005+1e-8)
            if not passed:failures.append('certificate_without_full_actual_evidence');break
            anchor=feet[rows[-1]].copy();last_end=float(ends[i]);last_force=float(force)
    return dict(verified=not failures,failed_checks=failures,proof_windows_checked=proofs)


def audit_trial(spec,entry,frozen):
    run=Path(entry['run_dir']);metadata=json.loads((run/'metadata.json').read_text())
    summary=json.loads((run/'weak_pad_summary.json').read_text())
    with np.load(run/'signals.npz',allow_pickle=False) as archive:d={key:archive[key] for key in archive.files}
    failures=[]
    def check(name,condition):
        if not condition:failures.append(name)
    for key,name in (('signals_sha256','signals.npz'),('metadata_sha256','metadata.json'),('summary_sha256','weak_pad_summary.json')):
        check('immutable_'+name,entry.get(key)==sha(run/name))
    check('frozen_execution',entry.get('source_sha256')==frozen['source']['sha256'])
    expected={**spec['parameters'],'strategy':spec['strategy'],'seed':spec['seed'],'role':'evaluation'}
    threshold=expected.pop('failure_threshold_n')
    check('public_parameters',metadata.get('trial_parameters')==expected)
    check('hidden_capacity',metadata['evaluation']['failure_load_n']==threshold)
    check('no_hidden_capacity_in_public_input','failure_threshold_n' not in metadata['trial_parameters'])
    t=d['control_time_s'];dt=float(metadata['dt_s']);n=len(t);phase=d['phase'].astype(str)
    check('physical_clock',np.allclose(np.diff(t),dt,atol=1e-8,rtol=0))
    check('sensor_clock',np.allclose(d['sensor_observation_time_s'],t,atol=1e-8,rtol=0))
    mpc_period=round(1/(float(metadata['simulation_params']['mpc_frequency'])*dt))
    check('periodic_mpc_updates',np.all(d['mpc_update'][::mpc_period]))
    changed=np.r_[False,np.any(d['contact_planned'][1:]!=d['contact_planned'][:-1],axis=1)]
    check('support_change_mpc_updates',np.all(d['mpc_update'][changed]))
    check('qp_success',not np.any(d['qp_status'][d['mpc_update'].astype(bool)]))
    check('nlp_status',np.all(np.isin(d['mpc_status'][d['mpc_update'].astype(bool)],[0,2])))
    contacts=d['contact_measured'].astype(bool);normal=d['contact_normal_force'];valid=d['certificate_valid'].astype(bool)
    certificate=d['certificate_force_n'];actual=d['actual_pad_normal_force_n'];cap=d['applied_pad_force_cap_n']
    force_command=d['grf_desired_w'][:,0,2];reserve=d['tracking_reserve_n']
    sensor=metadata['sensor_config'];bias=sensor.get('force_bias_n',0.);noise=sensor.get('force_noise_n',0.)
    measured=d['sensor_pad_normal_force_n'][1:];truth=normal[:-1,0]
    check('actual_force_sensor_bounds',np.all(measured>=np.maximum(0.,truth+bias-noise)-1e-8)
          and np.all(measured<=np.maximum(0.,truth+bias+noise)+1e-8))
    position_error=d['sensor_pad_foot_pos_w'][1:]-d['feet_pos_w'][:-1,0]
    check('actual_position_sensor_bounds',np.max(np.abs(position_error))<=sensor.get('position_noise_m',0.)+1e-8)
    check('ideal_contact_sensor',np.array_equal(d['sensor_contact_measured'][1:].astype(bool),contacts[:-1]))
    check('measurement_reserve',abs(bias)+noise<=metadata['sensor_force_reserve_n']+1e-8)
    first_valid=np.flatnonzero(valid)
    if len(first_valid):check('continuous_monitor',np.all(d['certificate_monitor_update'][first_valid[0]:]))
    certificate_audit=certificate_history(d,metadata)
    check('continuous_certificate_history',certificate_audit['verified'])
    # Physical failure has a strict force threshold and contiguous overload dwell.
    overloaded=d['force_before_deformation_n']>threshold
    pieces=np.split(np.flatnonzero(overloaded),np.flatnonzero(np.diff(np.flatnonzero(overloaded))!=1)+1)
    needed=int(np.ceil(metadata['evaluation']['overload_dwell_s']/dt-1e-10))
    triggering=[part for part in pieces if len(part)>=needed]
    failure_index=int(triggering[0][needed-1]) if triggering else None
    expected_failed=np.zeros(n,bool)
    expected_sink=np.zeros(n)
    if failure_index is not None:
        expected_failed[failure_index:]=True
        expected_sink[failure_index:]=np.minimum(metadata['evaluation']['sink_depth_m'],
            metadata['evaluation']['sink_speed_m_s']*(t[failure_index:]-t[failure_index]))
    check('actual_overload_causes_failure',np.array_equal(d['pad_failed'].astype(bool),expected_failed))
    check('physical_collapse_motion',np.allclose(d['pad_sink_displacement_m'],expected_sink,atol=1e-8,rtol=0))
    probe=np.isin(phase,PROBE);movement=np.isin(phase,MOVEMENT);stop=phase=='safe_stop'
    recovery_rows=np.flatnonzero(d['recovery_triggered'].astype(bool)|np.isin(phase,RECOVERY))
    recovery=np.zeros(n,bool)
    if len(recovery_rows):recovery[recovery_rows[0]:]=True
    tilt=np.rad2deg(np.max(np.abs(d['base_rpy_rad'][:,:2]),axis=1))
    original_tripod=np.all(contacts[:,1:]&(normal[:,1:]>=5.),axis=1)&(triangle_margin(d['com_pos_w'],d['feet_pos_w'][:,1:])>=.005)&(tilt<=8.)
    check('whole_probe_and_recovery_tripod',np.all(original_tripod[probe|recovery]))
    check('no_execution_after_failure',not np.any(movement & expected_failed))
    certified_future=(movement|stop)&valid
    check('actual_future_below_certificate',np.all(actual[certified_future]<=certificate[certified_future]+1e-6))
    usable=certificate-reserve
    supported=certified_future&(usable>0)
    check('installed_caps_keep_reserve',np.all(cap[supported]<=usable[supported]+1e-6))
    check('desired_force_respects_cap',np.all(force_command[supported]<=cap[supported]+metadata['force_tolerance_n']))
    posture=phase=='reprobe_posture'
    check('posture_retains_certificate',np.all(valid[posture]))
    check('posture_actual_load_below_existing_proof',np.all(actual[posture]<=certificate[posture]+1e-6))
    check('posture_installed_cap_keeps_reserve',np.all(cap[posture]<=usable[posture]+1e-6))
    check('posture_gap_within_reserve',np.all(actual[posture]-cap[posture]<=reserve[posture]+1e-6))
    groups=dict(future_execution=certified_future,probe_transition=np.isin(phase,('probe_release','reprobe_posture'))&valid,
                deliberate_probe=np.isin(phase,('probe_ramp','probe_hold')),recovery=recovery)
    gaps={}
    for name,mask in groups.items():
        a=actual[mask]-cap[mask];b=actual[mask]-force_command[mask]
        gaps[name]=dict(samples=int(np.count_nonzero(mask)),maximum_actual_minus_cap_n=float(np.max(a)) if np.any(mask) else None,
            maximum_actual_minus_command_n=float(np.max(b)) if np.any(mask) else None,
            samples_above_declared_tracking_reserve=int(np.count_nonzero(a>reserve[mask]+1e-6)))
    start=np.flatnonzero(probe)[0]
    direction=np.asarray(metadata.get('progression_axis',[1.,0.,0.]))
    advance=(d['com_pos_w']-d['com_pos_w'][start])@direction
    leg=list(metadata['legs']).index(metadata['next_leg']);others=[i for i in range(4) if i!=leg]
    clearance=d['feet_pos_w'][:,leg,2]-d['feet_pos_w'][start,leg,2]
    progress=(movement&(advance>=.03-1e-6)&(clearance>=.02-1e-6)&~contacts[:,leg]
        &np.all(contacts[:,others]&(normal[:,others]>=2.),axis=1)&~expected_failed&valid)
    progress_hold,progress_indexes=longest(progress,dt)
    final=t>=t[-1]-.5+dt-1e-8
    if summary['outcome']=='SUCCESS':
        check('actual_simultaneous_progress',progress_hold>=1.-1e-8)
        check('terminal_task_flag',bool(d['task_complete_declared'][-1]))
        check('terminal_forward_progress',np.all(advance[final]>=.03-1e-6))
        check('terminal_planned_supports',np.all(~d['contact_planned'][final].astype(bool)|(contacts[final]&(normal[final]>=2.))))
        check('pad_never_failed',failure_index is None)
    recovery_hold=0.
    if summary['outcome']=='RECOVERED_STOP':
        check('failure_during_probe',failure_index is not None and probe[failure_index])
        check('recovery_present',len(recovery_rows)>0)
        if len(recovery_rows):
            first=recovery_rows[0];anchor=d['feet_pos_w'][first,0,2]
            recovery_clearance=float(metadata.get('recovery_minimum_foot_clearance_m',.020))
            check('declared_recovery_clearance',recovery_clearance>=.020)
            ranks=np.array([RECOVERY.index(p) if p in RECOVERY else -1 for p in phase[first:]])
            check('contiguous_recovery_states',np.all(ranks>=0) and ranks[0]==0 and ranks[-1]==2 and np.all(np.diff(ranks)>=0))
            airborne=np.isin(phase,('recovery_lift','recovery_hold'))
            check('recovery_zero_support_command',np.all(cap[airborne]<=1e-6)
                and np.all(force_command[airborne]<=metadata['force_tolerance_n']) and not np.any(d['contact_planned'][airborne,0]))
            recovered=(recovery&original_tripod&~contacts[:,0]&(normal[:,0]<2.)&(actual<=2.)
                &(d['feet_pos_w'][:,0,2]-anchor>=recovery_clearance-1e-6)
                &(d['feet_desired_w'][:,0,2]-anchor>=recovery_clearance-1e-6))
            recovery_hold,_=longest(recovered,dt)
            tail=t>=t[-1]-2.+dt-1e-8
            check('two_second_actual_recovery_hold',np.all(recovered[tail]) and np.count_nonzero(tail)*dt>=2.-1e-8)
        check('recovery_terminal_flag',bool(d['recovered_stop_declared'][-1]) and not np.any(d['task_complete_declared']))
    if summary['outcome']=='SAFE_STOP':
        check('stop_original_tripod',np.all(original_tripod[final]))
        check('stop_not_success',not np.any(d['task_complete_declared']) and failure_index is None)
    return dict(trial_id=spec['trial_id'],strategy=spec['strategy'],case_id=spec['case_id'],seed=spec['seed'],
        outcome=summary['outcome'],verified=not failures,failed_checks=failures,run_dir=str(run),
        final_forward_progress_m=float(advance[-1]),simultaneous_progress_hold_s=progress_hold,
        simultaneous_progress_min_forward_m=float(np.min(advance[progress_indexes])) if len(progress_indexes) else None,
        simultaneous_progress_max_forward_m=float(np.max(advance[progress_indexes])) if len(progress_indexes) else None,
        recovery_stable_hold_s=recovery_hold,tracking_gap_by_phase_group=gaps,
        certificate_history=certificate_audit,
        reprobe_posture_loading=dict(samples=int(np.count_nonzero(posture)),
            maximum_actual_minus_certificate_n=float(np.max(actual[posture]-certificate[posture])) if np.any(posture) else None,
            maximum_cap_plus_reserve_minus_certificate_n=float(np.max(cap[posture]+reserve[posture]-certificate[posture])) if np.any(posture) else None,
            maximum_actual_minus_cap_n=float(np.max(actual[posture]-cap[posture])) if np.any(posture) else None,
            actual_load_exceedance_samples=int(np.count_nonzero(actual[posture]>certificate[posture]+1e-6))),
        maximum_actual_future_pad_force_n=float(np.max(actual[certified_future])) if np.any(certified_future) else None,
        maximum_certified_force_n=float(np.max(certificate[valid])) if np.any(valid) else None,
        minimum_actual_future_certificate_slack_n=float(np.min(certificate[certified_future]-actual[certified_future])) if np.any(certified_future) else None)


def compare_common_prefix(manifest,state):
    fields=('com_pos_w','base_rpy_rad','feet_pos_w','contact_measured','contact_normal_force',
        'feet_desired_w','grf_desired_w','sensor_pad_normal_force_n','sensor_pad_foot_pos_w',
        'sensor_contact_measured','certificate_force_n','certificate_valid','probe_evidence_start_time_s',
        'probe_evidence_end_time_s')
    groups={}
    for spec in manifest['trials']:groups.setdefault((spec['case_id'],spec['seed']),[]).append(spec)
    output=[]
    for (case,seed),specs in groups.items():
        if not all(state['trials'].get(s['trial_id'],{}).get('status')=='completed' for s in specs):continue
        loaded=[];deadlines=[]
        for spec in specs:
            run=Path(state['trials'][spec['trial_id']]['run_dir'])
            metadata=json.loads((run/'metadata.json').read_text())
            history=metadata.get('capacity_decision_history',[])
            if not history:break
            deadlines.append(float(history[0]['time_s']))
            with np.load(run/'signals.npz',allow_pickle=False) as z:loaded.append({k:z[k] for k in ('control_time_s',)+fields})
        if len(loaded)!=len(specs):
            output.append(dict(case_id=case,seed=seed,verified=False,reason='No initial planning decision recorded'));continue
        end=min(deadlines);counts=[int(np.count_nonzero(d['control_time_s']<end-1e-8)) for d in loaded]
        differences={};same_counts=len(set(counts))==1
        if same_counts:
            for field in fields:
                baseline=loaded[0][field][:counts[0]].astype(float)
                differences[field]=max(float(np.max(np.abs(d[field][:counts[0]].astype(float)-baseline))) for d in loaded[1:]) if len(loaded)>1 else 0.
        verified=same_counts and counts[0]>0 and all(value<=1e-8 for value in differences.values())
        output.append(dict(case_id=case,seed=seed,verified=verified,common_prefix_samples=counts[0],
            ends_before_first_decision_time_s=end,first_decision_times_s=deadlines,maximum_absolute_differences=differences))
    return output


def summarize_tracking(rows):
    summary={}
    for strategy in sorted({row['strategy'] for row in rows}):
        summary[strategy]={}
        for phase in ('future_execution','probe_transition','deliberate_probe','recovery'):
            available=[row['tracking_gap_by_phase_group'][phase] for row in rows
                       if row['strategy']==strategy and row['tracking_gap_by_phase_group'][phase]['samples']]
            summary[strategy][phase]=dict(trials_with_samples=len(available),
                maximum_actual_minus_cap_n=max((r['maximum_actual_minus_cap_n'] for r in available),default=None),
                maximum_actual_minus_command_n=max((r['maximum_actual_minus_command_n'] for r in available),default=None),
                trials_exceeding_declared_cap_reserve=sum(r['samples_above_declared_tracking_reserve']>0 for r in available))
    return summary


def plot_tracking(path,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    phases=('future_execution','probe_transition','deliberate_probe','recovery')
    strategies=('fixed_probe','adaptive_force_fixed_posture','adaptive_probe')
    colors=('#444444','#4779ad','#9251a2')
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for axis,metric,title in zip(axes,('maximum_actual_minus_cap_n','maximum_actual_minus_command_n'),
        ('Actual target load − installed cap','Actual target load − desired GRF')):
        for i,strategy in enumerate(strategies):
            values=[row for row in rows if row['strategy']==strategy]
            for j,phase in enumerate(phases):
                group=[row['tracking_gap_by_phase_group'][phase][metric] for row in values
                       if row['tracking_gap_by_phase_group'][phase]['samples']]
                offset=np.linspace(-.045,.045,len(group)) if len(group)>1 else np.zeros(len(group))
                axis.scatter(j+(i-1)*.18+offset,group,c=colors[i],s=23,alpha=.8)
            axis.scatter([],[],c=colors[i],label=strategy.replace('_',' '),s=23)
        axis.axhline(0,color='gray',linewidth=.6)
        if metric.endswith('cap_n'):axis.axhline(8.,color='#bc3030',linestyle='--',label='Declared 8 N tracking reserve')
        axis.set_xticks(range(4),['Certified\nexecution','Certified probe\ntransitions','Deliberate\nprobe','Recovery'])
        axis.set_ylabel('Per-trial maximum gap (N)');axis.set_title(title);axis.grid(alpha=.15)
        axis.legend(fontsize=7,loc='best')
    fig.suptitle('Each point is one trial and phase group; initial stance and light contact excluded')
    fig.savefig(path,dpi=170);plt.close(fig)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-dir',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args(argv)
    study=args.study_dir.resolve();manifest=json.loads((study/'split_manifest.json').read_text())
    state=json.loads((study/'study_state.json').read_text());frozen=json.loads((study/'execution_freeze.json').read_text())
    root=next(parent for parent in study.parents if (parent/'quadruped_pympc').is_dir())
    source_ok=all(sha(root/name)==expected for name,expected in frozen['source']['files'].items())
    forbidden={'weak_pad_evaluation','failure_threshold_n','failure_load_n','true_capacity_n','actual_capacity_n'}
    source_leaks=[]
    for name in frozen['source']['files']:
        if not name.startswith(('primp_project/control/','primp_project/planning/')):continue
        for node in ast.walk(ast.parse((root/name).read_text())):
            if isinstance(node,ast.Attribute) and node.attr in forbidden or isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in forbidden:
                source_leaks.append(dict(path=name,line=node.lineno))
    rows=[];pending=[];errors=[]
    for spec in manifest['trials']:
        entry=state['trials'].get(spec['trial_id'],{})
        if entry.get('status')=='completed':rows.append(audit_trial(spec,entry,frozen))
        elif entry.get('status')=='error':errors.append(dict(trial_id=spec['trial_id'],error=entry.get('error')))
        else:pending.append(spec['trial_id'])
    prefixes=compare_common_prefix(manifest,state)
    result=dict(version=1,created_at=datetime.now(timezone.utc).isoformat(),study_complete=not pending,
        declared_trials=len(manifest['trials']),completed_trials=len(rows),pending_trials=pending,execution_errors=errors,
        source_sha256=frozen['source']['sha256'],frozen_source_unchanged=source_ok,
        controller_planner_hidden_truth_references=source_leaks,all_completed_trials_verified=source_ok and not source_leaks and all(r['verified'] for r in rows) and all(p['verified'] for p in prefixes),
        matched_initial_test_prefixes=prefixes,
        tracking_gaps_by_strategy=summarize_tracking(rows),
        related_evidence=dict(independent_geometry_necessity='necessity_audit.json',
            geometry_reproducer='audit_necessity.py',analyzer_mutation_review='development/analyzer_review_after.json',
            mutation_reproducer='development/falsify_analyzer.py',prefreeze_tests='prefreeze_tests.txt'),
        observed_outcomes=dict(Counter(row['outcome'] for row in rows)),trials=rows,
        conventions=dict(reserve='Actual target-pad load minus installed MPC cap is the operative cap reserve gap; actual minus GRF is separate force tracking.',
            phase_groups='Execution/safe_stop and probe_transition buckets require a valid certificate. Deliberate probe and recovery have separate buckets. Stand/light-contact excluded.',
            statistics='Per-run extrema and durations; correlated control ticks are not independent experimental trials.'))
    out=study/'validation'/'independent_execution_audit.json';out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    if result['study_complete'] and rows:plot_tracking(study/'validation'/'force_tracking_gaps.png',rows)
    print(json.dumps({key:result[key] for key in ('study_complete','completed_trials','all_completed_trials_verified','observed_outcomes')},indent=2))
    return 0 if result['all_completed_trials_verified'] else 1

if __name__=='__main__':raise SystemExit(main())
