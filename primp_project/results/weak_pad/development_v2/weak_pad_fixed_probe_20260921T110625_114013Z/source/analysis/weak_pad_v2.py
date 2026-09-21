"""Independent continuous-certificate and controlled-recovery audit for V2.

Shared V1 kinematic, force, timestamp and MPC checks are reused. New checks
reconstruct certificate validity from every permitted sensor observation, rather
than trusting only the certificate value at movement entry. Simulator strength
is used exclusively to evaluate physical failure and recovery outcomes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from .step import _safe, _triangle_margin
from .weak_pad import evaluate_weak_pad, _longest, plot_overview

STRATEGIES = ('fixed_probe', 'adaptive_force_fixed_posture', 'adaptive_probe')
PROBE_PHASES = ('probe_ramp', 'probe_hold', 'probe_release', 'reprobe_posture')
MOVEMENT_PHASES = ('plan', 'execute', 'progress_shift', 'next_unload', 'next_lift', 'progress_hold', 'progress_complete')
RECOVERY_PHASES = ('recovery_unload', 'recovery_lift', 'recovery_hold')
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EXTRA_REQUIRED = ('certificate_monitor_update', 'certificate_revision', 'certificate_invalidation_reason',
    'certificate_observation_phase',
    'sensor_observation_time_s', 'recovery_triggered', 'recovered_stop_declared', 'recovery_trigger_reason',
    'recovery_start_time_s', 'recovery_foot_anchor_w')


def _continuous_certificate(metadata, data):
    """Independently latch invalidation, allowing restoration only by fresh proof.

    The guard uses the evidence endpoint as its anchor, matching the declared
    uniform local test region. Checking a whole trace catches a single lost
    contact or temporary departure even when the foot later returns.
    """
    t = np.asarray(data['control_time_s'])
    valid = np.asarray(data['certificate_valid'], bool)
    force = np.asarray(data['certificate_force_n'])
    measured_contact = np.asarray(data['sensor_contact_measured'], bool)[:, 0]
    foot = np.asarray(data['sensor_pad_foot_pos_w'])
    phase = np.asarray(data['certificate_observation_phase']).astype(str)
    starts = np.asarray(data['probe_evidence_start_time_s'])
    ends = np.asarray(data['probe_evidence_end_time_s'])
    observations = np.asarray(data['sensor_observation_time_s'])
    updates = np.asarray(data['certificate_monitor_update'], bool)
    failures, events = [], []
    ever_valid = False
    anchor = None
    invalidated_at = None
    previous_end = -np.inf
    previous_force = 0.
    for i in range(len(t)):
        if (ever_valid or valid[i]) and not updates[i]:
            failures.append(dict(sample=i, reason='monitor_not_updated'))
        # A certificate remains tied to its old anchor until a new entire test.
        if anchor is not None and invalidated_at is None:
            displacement = foot[i]-anchor
            reason = ('lost_contact' if not measured_contact[i] else
                'tested_foothold_moved' if np.linalg.norm(displacement[:2]) > .010+1e-8 or abs(displacement[2]) > .0025+1e-8 else None)
            if reason:
                invalidated_at = float(observations[i])
                events.append(dict(sample=i, time_s=float(t[i]), reason=reason))
                if not str(data['certificate_invalidation_reason'][i]):
                    failures.append(dict(sample=i, reason='invalidation_reason_missing'))
        if valid[i]:
            new_proof = (not ever_valid or ends[i] > previous_end+1e-8 or
                         force[i] > previous_force+1e-8 or (i > 0 and not valid[i-1]))
            if invalidated_at is not None:
                if not new_proof or starts[i] < invalidated_at-1e-8:
                    failures.append(dict(sample=i, reason='invalidated_certificate_reused'))
                else:
                    invalidated_at = None
            if new_proof:
                if phase[i] != 'probe_hold':
                    failures.append(dict(sample=i, reason='proof_created_outside_probe_hold'))
                if ever_valid and force[i] > previous_force+1e-8 and phase[i] != 'probe_hold':
                    failures.append(dict(sample=i, reason='ordinary_motion_increased_certificate'))
                j = int(np.searchsorted(observations, ends[i]+1e-8, side='right')-1)
                if j < 0 or j > i:
                    failures.append(dict(sample=i, reason='noncausal_evidence_anchor'))
                else:
                    anchor = foot[j].copy()
                previous_end, previous_force = float(ends[i]), float(force[i])
            if not measured_contact[i]:
                failures.append(dict(sample=i, reason='valid_without_sensed_contact'))
            ever_valid = True
    return dict(passed=not failures, violations=failures, invalidation_events=events,
                monitored_samples=int(np.count_nonzero(updates)))


def evaluate_weak_pad_v2(metadata, data):
    missing = sorted(set(EXTRA_REQUIRED)-data.keys())
    if missing:
        raise ValueError(f'Missing V2 evidence: {missing}')
    data = {key: np.asarray(value) for key,value in data.items()}
    n = len(data['control_time_s'])
    if any(data[key].ndim == 0 or len(data[key]) != n for key in EXTRA_REQUIRED):
        raise ValueError('V2 evidence channels must align with control samples')
    mapped = copy.deepcopy(metadata)
    mapped.update(experiment='weak_pad',strategy='adaptive')
    result = evaluate_weak_pad(mapped, data)
    checks = result['criteria']
    t = data['control_time_s']; dt = float(metadata['dt_s'])
    phase = data['phase'].astype(str)
    probe = np.isin(phase, PROBE_PHASES)
    recovery = np.isin(phase, RECOVERY_PHASES)
    movement = np.isin(phase, MOVEMENT_PHASES)
    stopped = phase == 'safe_stop'
    valid = data['certificate_valid'].astype(bool)
    actual = data['actual_pad_normal_force_n']
    failed = data['pad_failed'].astype(bool)
    contacts = data['contact_measured'].astype(bool)
    normal = data['contact_normal_force']
    legs = list(metadata.get('legs',['FL','FR','RL','RR']))
    selected = legs.index(metadata.get('selected_leg','FL'))
    supports = [i for i in range(4) if i != selected]
    tilt = np.rad2deg(np.max(np.abs(data['base_rpy_rad'][:,:2]),axis=1))
    max_tilt = float(metadata.get('maximum_abs_roll_pitch_deg',8.))
    support_margin = _triangle_margin(data['com_pos_w'],data['feet_pos_w'][:,supports])
    support_loaded = np.all(contacts[:,supports] & (normal[:,supports] >= 5.),axis=1)
    sensor_support_loaded = np.all(data['sensor_contact_measured'][:,supports].astype(bool),axis=1)
    original_tripod = support_loaded & sensor_support_loaded & (support_margin >= .005) & (tilt <= max_tilt)

    def check(name, passed, requirement, observed=None, category='integrity'):
        checks[name] = dict(passed=bool(passed),category=category,requirement=requirement,observed=_safe(observed))

    check('configuration_v2', metadata.get('experiment') == 'weak_pad' and metadata.get('protocol_version') == 2
          and metadata.get('strategy') in STRATEGIES and selected == 0,
          'V2 declares one recognized strategy and the selected FL target')
    sensor = metadata.get('sensor_config',{})
    sensor_values=np.array([sensor.get('force_bias_n',0.),sensor.get('force_noise_n',0.),
                           sensor.get('position_noise_m',0.),metadata.get('sensor_delay_s',0.)],dtype=float)
    check('supported_sensor_configuration',np.all(np.isfinite(sensor_values)) and sensor_values[1]>=0
          and 0<=sensor_values[2]<=.0002 and sensor_values[3]==0.,
          'Declared sensing uses bounded force noise, at most 0.2 mm componentwise position noise and zero delay')
    declared_error = abs(float(sensor.get('force_bias_n',0.)))+abs(float(sensor.get('force_noise_n',0.)))
    check('sensor_reserve_covers_declared_error', float(metadata.get('sensor_force_reserve_n',0.)) >= declared_error-1e-8,
          'Measurement reserve covers the entire declared bounded force error',declared_error)
    # Control observations precede each physics step. Except for the first
    # unrecorded reset state, the preceding row is independent physical truth
    # at exactly that observation time, including launch-surface foot contact.
    actual_observed_force=normal[:-1,selected]
    force_bias=float(sensor.get('force_bias_n',0.));force_noise=float(sensor.get('force_noise_n',0.))
    measured_force=data['sensor_pad_normal_force_n'][1:]
    lower_force=np.maximum(0.,actual_observed_force+force_bias-force_noise)
    upper_force=np.maximum(0.,actual_observed_force+force_bias+force_noise)
    position_error=data['sensor_pad_foot_pos_w'][1:]-data['feet_pos_w'][:-1,selected]
    check('realized_sensor_error_bounds', force_noise >= 0 and float(sensor.get('position_noise_m',0.)) >= 0
          and np.all(measured_force >= lower_force-1e-8) and np.all(measured_force <= upper_force+1e-8)
          and np.all(np.abs(position_error) <= float(sensor.get('position_noise_m',0.))+1e-8)
          and np.array_equal(data['sensor_contact_measured'][1:].astype(bool),contacts[:-1]),
          'Every recorded post-reset observation respects the declared bounded force/position errors and ideal contact channel',
          dict(audited_samples=n-1,maximum_force_error_n=float(np.max(np.abs(measured_force-actual_observed_force))),
               maximum_position_component_error_m=float(np.max(np.abs(position_error)))))
    observation_time = data['sensor_observation_time_s']
    check('aligned_sensor_clock', np.allclose(observation_time,t,atol=1e-8,rtol=0),
          'V2 observations are synchronous with each control input; no unaccounted delayed samples')
    monitor = _continuous_certificate(metadata,data)
    check('continuous_certificate_monitor', monitor['passed'],
          'Every post-certificate tick checks contact/site validity, with irreversible invalidation until a fresh complete probe',monitor,'safety')
    check('certificate_evidence_sound', not np.any(valid) or checks['actual_dwell_certificate']['passed'],
          'Any issued certificate has a complete independently verified physical evidence window, even if the trial later recovers')
    revisions = data['certificate_revision']
    check('certificate_revision_finite', np.all(revisions >= 0) and np.all(revisions == np.floor(revisions)),
          'Certificate revision identifiers are nonnegative integers')
    check('probe_and_recovery_tripod', np.any(probe) and np.all(original_tripod[probe | recovery]),
          'Original three supports remain measured and loaded through every probe and recovery transition',category='safety')
    check('no_future_execution_after_failure', not np.any(failed & movement),
          'A failed pad never authorizes further weight-transfer movement',category='safety')
    covered=movement | stopped
    certificate=data['certificate_force_n']
    cap=data['applied_pad_force_cap_n']
    permitted=certificate-data['tracking_reserve_n']
    solver_tolerance=float(metadata.get('force_tolerance_n',.1))
    certified_loading=(valid & (actual <= certificate+1e-6) & (cap <= permitted+1e-6)
        & (data['planned_pad_force_n'] <= permitted+solver_tolerance)
        & (data['grf_desired_w'][:,selected,2] <= cap+solver_tolerance))
    unloaded_stop=(stopped & ~valid & (actual <= 2.+1e-8) & (normal[:,selected] <= 2.+1e-8)
        & ~data['contact_planned'][:,selected].astype(bool) & (cap <= 1e-6)
        & (data['grf_desired_w'][:,selected,2] <= solver_tolerance))
    zero_usable_stop=(stopped & valid & (permitted <= 0.) & (cap <= 1e-6)
        & (actual <= np.minimum(2.,certificate)+1e-6) & (normal[:,selected] <= 2.+1e-8)
        & (data['planned_pad_force_n'] <= solver_tolerance)
        & (data['grf_desired_w'][:,selected,2] <= solver_tolerance))
    check('future_certified_or_unloaded', np.all((certified_loading | unloaded_stop | zero_usable_stop)[covered]),
          'Every movement/stop interval respects certified actual and commanded loads, or leaves an uncertified target unloaded and unscheduled',category='safety')
    if np.any(zero_usable_stop):
        check('planned_force_with_reserve',np.all((certified_loading | zero_usable_stop)[covered]),
              'A positive certificate below the tracking reserve allows only a zero-command, physically unloaded stop; loaded movement retains the full reserve',category='safety')
    recovery_airborne=np.isin(phase,('recovery_lift','recovery_hold'))
    check('recovery_commands_unloaded',np.all(cap[recovery_airborne]<=1e-6)
          and np.all(data['planned_pad_force_n'][recovery_airborne]<=solver_tolerance)
          and np.all(data['grf_desired_w'][recovery_airborne,selected,2]<=solver_tolerance)
          and not np.any(data['contact_planned'][recovery_airborne,selected]),
          'Throughout recovery lift and hold the target is unscheduled, its installed force cap is zero, and its commanded support force is negligible',category='safety')
    # This is a description, not an arbitrary requirement that every test miss
    # its requested load by at least one newton.
    checks['requested_force_is_not_achieved']['category']='description'

    failure_rows=np.flatnonzero(failed)
    first_failure=int(failure_rows[0]) if len(failure_rows) else None
    recovery_rows=np.flatnonzero(recovery)
    first_recovery=int(recovery_rows[0]) if len(recovery_rows) else None
    hold_required=float(metadata.get('recovery_minimum_tripod_hold_s',metadata.get('recovery_hold_s',2.)))
    lift_required=float(metadata.get('recovery_minimum_foot_clearance_m',metadata.get('recovery_lift_height_m',.020)))
    unload_limit=float(metadata.get('recovery_maximum_unload_delay_s',metadata.get('recovery_max_unload_delay_s',3.)))
    recovery_clock_valid=(hold_required >= 2. and lift_required >= .020 and 0 < unload_limit <= 5.)
    check('recovery_configuration',recovery_clock_valid,
          'Recovery declares at least 20 mm lift, at least 2 s stable hold, and a bounded unload deadline')
    failure_in_probe=first_failure is not None and bool(probe[first_failure])
    recovery_causal=(first_recovery is not None and np.any(data['recovery_triggered'][:first_recovery+1]))
    recovery_hold=0.; lift_peak=0.; unload_delay=None; terminal_recovered=False
    if first_recovery is not None:
        anchor=data['feet_pos_w'][first_recovery,selected].copy()
        sensed_anchor=data['recovery_foot_anchor_w'][first_recovery]
        lift=data['feet_pos_w'][:,selected,2]-anchor[2]
        commanded_lift=data['feet_desired_w'][:,selected,2]-anchor[2]
        unloaded=(actual <= 2.+1e-8) & ~contacts[:,selected] & (normal[:,selected] < 2.)
        recovered_sample=(recovery & original_tripod & unloaded & (lift >= lift_required-1e-6)
            & (commanded_lift >= lift_required-1e-6) & ~data['contact_planned'][:,selected].astype(bool))
        recovery_hold,_=_longest(t,recovered_sample,dt)
        lift_peak=float(np.max(lift[recovery]))
        unload_rows=np.flatnonzero(recovery & unloaded)
        if len(unload_rows):unload_delay=float(t[unload_rows[0]]-t[first_recovery])
        final=t >= t[-1]-hold_required+dt-1e-8
        terminal_recovered=(np.count_nonzero(final)*dt >= hold_required-1e-8
            and np.all(recovered_sample[final]) and np.all(np.linalg.norm(data['recovery_foot_anchor_w'][recovery]-sensed_anchor,axis=1)<1e-8))
    controlled_terminal=(recovery_causal and recovery_clock_valid and terminal_recovered
        and recovery_hold >= hold_required-1e-8 and unload_delay is not None and unload_delay <= unload_limit+1e-8
        and bool(data['recovered_stop_declared'][-1]) and not np.any(data['task_complete_declared'])
        and first_recovery is not None and not np.any(movement[first_recovery:]))
    controlled=controlled_terminal and failure_in_probe and not np.any(movement[first_failure:])
    check('controlled_probe_failure_recovery',controlled,
          'Failure occurs during a probe, followed by controlled FL unloading/lift and at least 2 s of terminal original-tripod support; no task completion claim',
          dict(failure_in_probe=failure_in_probe,recovery_causal=recovery_causal,unload_delay_s=unload_delay,
               actual_lift_m=lift_peak,stable_hold_s=recovery_hold),'recovery')
    # A safe stop can follow an insufficient certificate. If no certificate
    # remains, the target must be physically unloaded, not silently trusted.
    final=t >= t[-1]-.5+dt-1e-8
    stop_safe=bool(stopped[-1]) and np.all(original_tripod[final]) and not np.any(failed)
    stop_safe &= not np.any(data['task_complete_declared']) and bool(data['safe_stop_declared'][-1])
    stop_safe &= bool(np.all(valid[final] | (actual[final] <= 2.)))
    check('terminal_safe_stop',stop_safe,
          'An intentional stop maintains the original tripod; any uncertified target is physically unloaded','' ,'task')

    integrity=all(c['passed'] for c in checks.values() if c['category']=='integrity')
    evidence=all(c['passed'] for c in checks.values() if c['category']=='evidence')
    safety=all(c['passed'] for c in checks.values() if c['category']=='safety')
    physical_success=bool(result['physical_success'] and integrity and evidence and safety)
    recovery_safety_names=('body_stable','probe_and_recovery_tripod','no_future_execution_after_failure',
                           'continuous_certificate_monitor','future_certified_or_unloaded','recovery_commands_unloaded')
    recovery_safe=all(checks[name]['passed'] for name in recovery_safety_names)
    if not integrity:outcome='INVALID'
    elif physical_success:outcome='SUCCESS'
    elif controlled and recovery_safe:outcome='RECOVERED_STOP'
    elif (stop_safe or controlled_terminal and not np.any(failed)) and recovery_safe:outcome='SAFE_STOP'
    elif np.any(failed) or not recovery_safe:outcome='UNSAFE'
    else:outcome='INCOMPLETE'
    expected=metadata.get('expected_outcome')
    result.update(version=2,protocol_version=2,analyzer_sha256=SOURCE_SHA256,strategy=metadata.get('strategy'),
        outcome=outcome,physical_success=physical_success,passed=physical_success,
        controlled_recovery_passed=outcome=='RECOVERED_STOP',physical_safety_passed=bool(safety),
        expected_outcome=expected,expected_outcome_met=bool(expected is not None and outcome==expected))
    result['metrics'].update(probe_time_s=float(np.count_nonzero(probe)*dt),
        recovery_time_s=float(np.count_nonzero(recovery)*dt),recovery_unload_delay_s=unload_delay,
        recovery_lift_m=lift_peak,recovery_stable_hold_s=recovery_hold,
        certificate_invalidations=len(monitor['invalidation_events']),
        additional_probe_count=int(metadata.get('additional_probe_count',0)))
    result['conventions'].update(recovered_stop='A controlled recovery after actual probe failure; distinct from successful movement and from a pad that never failed',
        paired_comparison='Shared movement optimizer and constraints; only the permitted probing adaptation differs')
    return _safe(result)


def analyze_weak_pad_v2(run_dir):
    run=Path(run_dir)
    metadata=json.loads((run/'metadata.json').read_text())
    with np.load(run/'signals.npz',allow_pickle=False) as archive:data={key:archive[key] for key in archive.files}
    result=evaluate_weak_pad_v2(metadata,data);result['run_id']=run.name
    (run/'weak_pad_summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    lines=[f"# Weak-pad V2: {result['outcome']}",'',f"Strategy: {result['strategy']}. Physical task success: {result['physical_success']}.",'',
           'A controlled recovery and a safe stop are separate from task completion.','', '| Check | Result | Requirement |','| --- | --- | --- |']
    for name,check in result['criteria'].items():lines.append(f"| {name} | {'pass' if check['passed'] else 'not met'} | {check['requirement']} |")
    (run/'weak_pad_report.md').write_text('\n'.join(lines)+'\n')
    plot_overview(metadata,data,result,run/'weak_pad_overview.png')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run_dir',type=Path)
    args=parser.parse_args(argv);result=analyze_weak_pad_v2(args.run_dir)
    print(json.dumps({key:result[key] for key in ('outcome','physical_success','controlled_recovery_passed')}))
    return 0 if result['outcome'] in ('SUCCESS','SAFE_STOP','RECOVERED_STOP') else 1

if __name__=='__main__':raise SystemExit(main())
