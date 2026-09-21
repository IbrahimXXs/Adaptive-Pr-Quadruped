"""Reproduce learned-reference attribution from the frozen pilot recordings.

Run from the repository conda environment. Writes only learned_execution_audit.json
beside this script; verifies canonical recording and model hashes before analysis.
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from primp_project.learning import PRIMPMotionModel

root=Path(__file__).resolve().parent.parent
out=Path(__file__).resolve().parent/'learned_execution_audit.json'
model=PRIMPMotionModel.load(root/'model')
audits=[];pending=[]
def number(x):return float(x)
def vector(x):return np.asarray(x).astype(float).tolist()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for group in (root,root/'held_out_heights'):
 if not (group/'split_manifest.json').exists():continue
 manifest=json.loads((group/'split_manifest.json').read_text())
 state=json.loads((group/'study_state.json').read_text())
 for spec in manifest['evaluations']:
  if spec['planner']!='learned':continue
  entry=state['trials'].get(spec['trial_id'],{})
  if entry.get('status')!='completed' or not entry.get('run_dir'):
   pending.append({'trial_id':spec['trial_id'],'status':entry.get('status','not_run')});continue
  run=Path(entry['run_dir'])
  if not run.exists():
   run=(group/'recordings'/run.name) if group.name=='held_out_heights' else (root.parent/'evaluation'/run.name)
  metadata=json.loads((run/'metadata.json').read_text())
  summary=json.loads((run/'pad_summary.json').read_text())
  for name,key in [('signals.npz','signals_sha256'),('metadata.json','metadata_sha256'),('pad_summary.json','summary_sha256')]:
   if entry.get(key) and entry[key]!=sha(run/name):raise ValueError(f'Changed recorded artifact: {run.name}/{name}')
  if metadata['model_hashes_sha256']['model.npz']!=sha(root/'model/model.npz'):raise ValueError('Recorded model differs')
  with np.load(run/'signals.npz',allow_pickle=False) as archive:d={name:archive[name] for name in archive.files}
  phase=d['phase'].astype(str);lower=np.flatnonzero(phase=='lower');reload=np.flatnonzero(phase=='reload')
  if not len(lower) or not len(reload):continue
  first,last=int(lower[0]),int(reload[0]);start=float(d['control_time_s'][first])
  landing=(np.arange(len(phase))>=first)&(np.arange(len(phase))<last)
  updates=np.flatnonzero(landing&d['planner_update'].astype(bool))
  missing=np.flatnonzero(landing&d['missing_contact'].astype(bool))
  fallback_delta=np.diff(d['planner_fallback_count'],prepend=0)
  fallback=np.flatnonzero(landing&(fallback_delta>0))
  condition_delta=np.diff(d['planner_conditioning_count'],prepend=0)
  conditions=np.flatnonzero(landing&(condition_delta>0))
  pre=updates[d['planner_fallback_count'][updates]==0]
  body0=d['planner_com_target_w'][first].copy();foot0=d['planner_foot_target_w'][first].copy()
  radius=float(metadata['foot_radius_m'])
  initial=model.condition(float(d['belief_mean_m'][first]),float(d['belief_std_m'][first]),
             current_phase=0.,current_features=np.zeros(9),state_std=np.array([.0005]*3+[.0002]*3+[.0005]*3))
  def snapshot(i):
   if i is None:return None
   i=int(i)
   return dict(time_after_lower_start_s=number(d['control_time_s'][i]-start),
      belief_mean_m=number(d['belief_mean_m'][i]),belief_std_m=number(d['belief_std_m'][i]),
      learned_phase=number(d['learned_phase'][i]),learned_duration_s=number(d['learned_duration_s'][i]),
      reported_remaining_time_s=number(d['planner_remaining_time_s'][i]),
      proposed_body_z_change_m=number(d['planner_proposed_com_w'][i,2]-body0[2]),
      executed_body_z_change_m=number(d['planner_com_target_w'][i,2]-body0[2]),
      proposed_foot_bottom_m=number(d['planner_proposed_foot_w'][i,2]-radius),
      executed_foot_bottom_m=number(d['planner_foot_target_w'][i,2]-radius),
      measured_foot_bottom_m=number(d['foot_bottom_z_w'][i]),
      conditioning_count=int(d['planner_conditioning_count'][i]),fallback_count=int(d['planner_fallback_count'][i]))
  differences=[]
  for i in pre:
   feature,_,_=initial.sample(float(d['learned_phase'][i]))
   u=float(np.clip((d['learned_phase'][i]-.7)/.3,0.,1.))
   preload=metadata['contact_compression_m']*(10*u**3-15*u**4+6*u**5)
   frozen_body=body0+feature[:3]
   frozen_foot=foot0+feature[6:9];frozen_foot[2]-=preload
   differences.append([d['planner_proposed_com_w'][i,2]-frozen_body[2],
                       d['planner_proposed_foot_w'][i,2]-frozen_foot[2],
                       d['learned_duration_s'][i]-initial.duration_s])
  differences=np.array(differences)
  def effect(column):
   return {'minimum':number(differences[:,column].min()),'maximum':number(differences[:,column].max()),
           'maximum_absolute':number(np.abs(differences[:,column]).max())} if len(differences) else None
  first_missing=int(missing[0]) if len(missing) else None
  first_fallback=int(fallback[0]) if len(fallback) else None
  timing=dict(initial_model_duration_s=initial.duration_s,
     learned_duration_range_s=[number(d['learned_duration_s'][updates].min()),number(d['learned_duration_s'][updates].max())],
     measured_lowering_to_touchdown_s=summary['metrics']['lowering_to_touchdown_s'],
     measured_lowering_to_confirmed_reload_s=number(d['control_time_s'][last]-start),
     fallback_updates=int(np.sum(fallback_delta[fallback])) if len(fallback) else 0,
     fallback_nominal_update_horizon_sum_s=number(np.sum(fallback_delta[fallback])/metadata['planner_frequency_hz']) if len(fallback) else 0.,
     first_fallback_to_confirmed_reload_s=number(d['control_time_s'][last]-d['control_time_s'][first_fallback]) if first_fallback is not None else 0.,
     active_fallback_descent_command_time_s=number(np.count_nonzero(landing & (np.arange(len(phase))>=first_fallback) & (d['desired_foot_vel_w'][:,2] < -1e-10))*metadata['dt_s']) if first_fallback is not None else 0.,
     remaining_time_during_fallback_s=sorted(set(vector(d['planner_remaining_time_s'][fallback]))) if len(fallback) else [])
  footprint={}
  if first_missing is not None:
   split=first_fallback if first_fallback is not None and first_fallback>=first_missing else last
   footprint['executed_foot_descent_after_missing_before_fallback_m']=number(d['planner_foot_target_w'][first_missing,2]-d['planner_foot_target_w'][split,2])
   footprint['executed_body_z_change_after_missing_before_fallback_m']=number(d['planner_com_target_w'][split,2]-d['planner_com_target_w'][first_missing,2])
  if first_fallback is not None:
   footprint['executed_foot_descent_during_fallback_m']=number(d['planner_foot_target_w'][first_fallback,2]-d['planner_foot_target_w'][last,2])
   footprint['executed_body_z_change_during_fallback_m']=number(d['planner_com_target_w'][last,2]-d['planner_com_target_w'][first_fallback,2])
  audit=dict(trial_id=spec['trial_id'],study=manifest['study'],run_id=run.name,run_directory=str(run),
     passed=bool(summary['passed']),actual_height_m=spec['actual_height_m'],sensor_profile=spec['sensor_profile'],
     signals_sha256=sha(run/'signals.npz'),source_sha256=entry['source_sha256'],
     initial=snapshot(first),first_missing_contact=snapshot(first_missing),first_fallback=snapshot(first_fallback),
     confirmed_reload=snapshot(last),conditioning_events=[snapshot(i) for i in conditions],timing=timing,
     proposed_body_z_change_range_during_lowering_m=[number((d['planner_proposed_com_w'][updates,2]-body0[2]).min()),number((d['planner_proposed_com_w'][updates,2]-body0[2]).max())],
     executed_body_z_change_range_during_lowering_m=[number((d['planner_com_target_w'][landing,2]-body0[2]).min()),number((d['planner_com_target_w'][landing,2]-body0[2]).max())],
     subsequent_conditioning_effect_before_fallback_at_matched_phase=dict(
        proposed_body_z_difference_m=effect(0),proposed_foot_z_difference_m=effect(1),predicted_duration_difference_s=effect(2)),
     motion_partition=footprint,reference_projection_count=int(np.max(d['reference_projection_count'])))
  audits.append(audit)
report=dict(generated_at=datetime.now(timezone.utc).isoformat(),completed_learned_trials=len(audits),pending_learned_trials=pending,
  model_sha256=sha(root/'model/model.npz'),trials=audits,
  conventions=dict(
   scope='Only completed formal learned trials are audited; development trials are excluded. Raw recordings/model remain unchanged.',
   proposed='Unfiltered 20Hz planner proposals, including shared virtual contact preload and any counted fallback.',
   executed='The actual accepted/interpolated 500Hz body and foot command logged by the executor, not measured tracking state or a separately logged endpoint.',
   model_effect='Before any fallback, compare each proposal against the initial conditioned distribution evaluated at the SAME learned phase, with identical shared preload. Differences isolate later belief/reference conditioning from normal trajectory progress.',
   timing='Learned duration is a distribution prediction, not observed completion time. Planner remaining time reaches zero at model phase1; subsequent bounded recovery time is not included in that prediction.',
   fallback_time='Count times50ms sums nominal planning horizons, NOT elapsed time: contact-freeze/resume can trigger extra updates. Actual first-fallback-to-confirmed-reload span and accumulated active downward-command samples are reported separately.',
   attribution='This observational audit cannot causally prove a learned-planner advantage. Model-driven references, servo preload, feedback tracking, feasibility limits and fallback all affect final success.'))
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
for a in audits:
 e=a['subsequent_conditioning_effect_before_fallback_at_matched_phase']
 print(a['trial_id'],'body effect m',e['proposed_body_z_difference_m'],'foot effect m',e['proposed_foot_z_difference_m'],
       'duration effect s',e['predicted_duration_difference_s'],'fallback',a['timing']['fallback_updates'],
       'missing',a['first_missing_contact'],'partition',a['motion_partition'])
print('Wrote',out,'completed',len(audits),'pending',len(pending))
