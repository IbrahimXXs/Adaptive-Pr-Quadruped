"""Independent raw-array checkpoint audit; run in the quadruped-pympc env."""
from pathlib import Path
import hashlib
import json
import numpy as np

STUDY = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def longest(mask, dt):
    ix=np.flatnonzero(mask)
    return 0. if not len(ix) else max(len(x) for x in np.split(ix,np.flatnonzero(np.diff(ix)>1)+1))*dt

def main():
    state=json.loads((STUDY/'study_state.json').read_text())
    manifest=json.loads((STUDY/'split_manifest.json').read_text())
    result=[]
    for spec in manifest['trials']:
        entry=state['trials'][spec['trial_id']]
        assert entry['status']=='completed',spec['trial_id']
        run=Path(entry['run_dir'])
        meta=json.loads((run/'metadata.json').read_text())
        summary=json.loads((run/'weak_pad_summary.json').read_text())
        with np.load(run/'signals.npz',allow_pickle=False) as bundle:
            d={key:bundle[key] for key in bundle.files}
        t=d['control_time_s'];dt=meta['dt_s'];phase=d['phase'];n=len(t)
        assert meta['status']=='completed' and meta['error'] is None
        assert meta['experiment_complete'] and bool(d['experiment_complete'][-1])
        assert np.allclose(np.diff(t),dt,rtol=0,atol=1e-8)
        assert np.array_equal(d['step'],np.arange(1,n+1))
        period=round(1/(meta['simulation_params']['mpc_frequency']*dt))
        expected=np.arange(n)%period==0
        expected[1:] |= np.any(d['contact_planned'][1:]!=d['contact_planned'][:-1],axis=1)
        assert np.array_equal(d['mpc_update'],expected)
        assert np.all(np.isin(d['mpc_status'][expected],[0,2]))
        assert np.all(d['qp_status'][expected]==0)
        assert np.rad2deg(np.max(np.abs(d['base_rpy_rad'][:,:2])))<8.
        actual=d['actual_pad_normal_force_n'];normal=d['contact_normal_force']
        row=dict(trial_id=spec['trial_id'],samples=n,duration_s=n*dt,
            signals_sha256=sha(run/'signals.npz'),metadata_sha256=sha(run/'metadata.json'),
            outcome=summary['outcome'],expected_outcome_met=summary['expected_outcome_met'],
            physical_success=summary['physical_success'])
        assert summary['outcome']==spec['expected_outcome']
        assert summary['physical_success']==(spec['strategy']=='adaptive')
        if spec['strategy']=='unaware':
            reload=np.flatnonzero(phase=='reload')[0]
            failure=np.flatnonzero(d['pad_failed'])[0]
            assert reload<failure and d['pad_sink_displacement_m'][-1]>=.002
            assert not np.any(d['certificate_valid'])
            assert longest((phase=='confirm') & (d['sensor_pad_normal_force_n']>=2.),dt)>=.1-1e-8
            over=d['force_before_deformation_n']>spec['failure_threshold_n']
            count=round(meta['evaluation']['overload_dwell_s']/dt)
            assert np.all(over[failure-count+1:failure+1])
            assert not d['pad_failed'][failure-1]
            assert np.all(d['contact_measured'][reload:,1:])
            assert np.min(normal[reload:,1:])>5.
            row.update(reload_start_s=float(t[reload]),failure_time_s=float(d['time_s'][failure]),
                maximum_sink_m=float(np.max(d['pad_sink_displacement_m'])),
                maximum_pad_force_n=float(np.max(actual)))
        else:
            expected_future=np.isin(phase,['progress_shift','next_unload','next_lift',
                'progress_hold','progress_complete','safe_stop'])
            future=d['future_plan_active'].astype(bool)
            assert np.array_equal(future,expected_future)
            assert np.any(future) and np.all(d['certificate_valid'][future])
            assert not np.any(d['pad_failed']) and np.max(d['pad_sink_displacement_m'])==0
            assert np.max(actual[future]-d['certificate_force_n'][future])<=1e-6
            assert np.max(d['applied_pad_force_cap_n'][future]+d['tracking_reserve_n'][future]-d['certificate_force_n'][future])<=1e-6
            probe=np.isin(phase,['probe_ramp','probe_hold','probe_release','reprobe_posture'])
            assert np.all(d['contact_measured'][probe,1:]) and np.min(normal[probe,1:])>5.
            updates=np.flatnonzero(d['certificate_valid'] & d['certificate_update'])
            assert len(updates)>0
            for i in updates:
                start,end=d['probe_evidence_start_time_s'][i],d['probe_evidence_end_time_s'][i]
                window=(t>=start-1e-8)&(t<=end+1e-8)
                assert end-start>=meta['probe_dwell_s']-1e-8 and end<=t[i]+1e-8
                assert np.all(phase[window]=='probe_hold')
                assert d['certificate_force_n'][i]<=np.min(d['sensor_pad_normal_force_n'][window])-meta['sensor_force_reserve_n']+1e-6
            row.update(final_certified_load_n=float(d['certificate_force_n'][-1]),
                final_mpc_cap_n=float(d['applied_pad_force_cap_n'][-1]),
                peak_future_actual_n=float(np.max(actual[future])),
                minimum_future_capacity_headroom_n=float(np.min(d['certificate_force_n'][future]-actual[future])),
                initial_request_n=float(d['requested_probe_force_n'][0]),
                additional_probe_count=int(meta['additional_probe_count']))
            if spec['strategy']=='conservative':
                assert d['safe_stop_declared'][-1] and not np.any(d['task_complete_declared'])
                tail=phase=='safe_stop'
                assert np.all(d['contact_measured'][tail,1:]) and np.min(normal[tail,1:])>5.
                assert longest(tail,dt)>=3.
            else:
                assert d['task_complete_declared'][-1]
                advance=d['com_pos_w'][:,0]-d['probe_origin_com_w'][:,0]
                lift=d['feet_pos_w'][:,2,2]-d['next_lift_anchor_w'][:,2]
                supported=np.all(d['contact_measured'][:,[0,1,3]] & (normal[:,[0,1,3]]>=2.),axis=1)
                success=future & (advance>=.03) & (lift>=.02) & ~d['contact_measured'][:,2] & supported
                assert longest(success,dt)>=1.
                assert np.all(success[phase=='progress_complete'])
                row.update(final_forward_m=float(advance[-1]),final_next_leg_clearance_m=float(lift[-1]),
                    simultaneous_progress_s=longest(success,dt),
                    raw_fixed_pose_probe_limit_n=float(d['maximum_achievable_probe_force_n'][np.flatnonzero(phase=='probe_ramp')[0]]))
        result.append(row)
    output=dict(passed=True,trial_count=len(result),audit_source_sha256=sha(Path(__file__)),trials=result)
    (STUDY/'validation'/'independent_audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(passed=True,trials=len(result),outcomes={name:sum(x['outcome']==name for x in result) for name in ['PROBLEM_COLLAPSE','SAFE_STOP','SUCCESS']}),indent=2))

if __name__=='__main__':main()
