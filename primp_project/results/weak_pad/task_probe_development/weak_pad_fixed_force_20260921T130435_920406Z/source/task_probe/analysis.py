"""Task-derived versus fixed-force probing with unchanged V2 physical checks.

Simulator capacity is evaluator-only. A surviving pad is not called task-capable
because its capacity exceeds a requested force: paired physical completion is
the evidence used when reporting avoidable damage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from primp_project.analysis.step import _safe
from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2, PROBE_PHASES, RECOVERY_PHASES, MOVEMENT_PHASES
from primp_project.analysis.weak_pad import plot_overview, _longest

POLICIES = ('fixed_force', 'task_sufficient')
EXTRA_SIGNALS = ('minimum_future_load_n', 'minimum_sufficient_probe_load_n',
                 'target_tolerance_n', 'probe_target_load_n', 'selected_probe_request_n')
FROZEN_MEASUREMENT_RESERVE_N = 1.
FROZEN_TRACKING_RESERVE_N = 8.


def _duration(time, mask, dt):
    """Count recorded fixed-rate control intervals, including their final tick."""
    return float(np.count_nonzero(mask) * dt)


def evaluate_task_probe(metadata, data):
    """Preserve every V2 criterion; audit added policy telemetry separately."""
    result = evaluate_weak_pad_v2(metadata, data)
    result['baseline_validator'] = 'primp_project.analysis.weak_pad_v2.evaluate_weak_pad_v2'
    result['baseline_outcome'] = result['outcome']
    result['study_name'] = 'task_probe'
    result['probe_policy'] = metadata.get('probe_policy')
    added = {}

    def check(name, passed, requirement, observed=None):
        added[name] = dict(passed=bool(passed), category='integrity', requirement=requirement,
                           observed=_safe(observed))

    check('task_probe_identity', metadata.get('study_name') == 'task_probe'
          and metadata.get('probe_policy') in POLICIES and metadata.get('strategy') == 'adaptive_probe',
          'The selected probe policy retains the frozen adaptive_probe controller and shared movement optimizer')
    missing = [name for name in EXTRA_SIGNALS if name not in data]
    check('probe_target_telemetry', not missing,
          'Record minimum task load, sufficient test target, tolerance and selected probe target', missing)
    if not len(data.get('control_time_s', [])):
        result['task_probe_criteria'] = added
        result['outcome'] = 'INVALID'
        result['physical_success'] = False
        result['passed'] = False
        return _safe(result)

    t = np.asarray(data['control_time_s'])
    phase = np.asarray(data['phase']).astype(str)
    dt = float(metadata.get('dt_s', np.median(np.diff(t))))
    probe = np.isin(phase, PROBE_PHASES)
    deliberate = np.isin(phase, ('probe_ramp', 'probe_hold'))
    extra_probe = np.asarray(data['additional_probe_count']) > 0
    stronger = extra_probe & probe
    physical = np.asarray(data['actual_pad_normal_force_n'])
    commanded = np.asarray(data['achieved_probe_command_n'])
    measured = np.asarray(data['sensor_pad_normal_force_n'])
    failed = np.asarray(data['pad_failed'], dtype=bool)
    displacement = np.asarray(data['actual_pad_displacement_m'])
    recovery = np.isin(phase, RECOVERY_PHASES)
    failed_rows = np.flatnonzero(failed)
    probe_rows = np.flatnonzero(probe)
    first_failure = int(failed_rows[0]) if len(failed_rows) else None
    reserve = float(metadata['sensor_force_reserve_n']) + float(metadata['tracking_reserve_n'])
    public = metadata.get('trial_parameters', {})
    undershoot = float(public.get('probe_undershoot_allowance_n', .2))
    sensor_error = float(metadata.get('sensor_force_error_bound_n', 0.))
    sensing = metadata.get('sensor_config', {})
    declared_sensor_error = abs(float(sensing.get('force_bias_n', 0.)))+float(sensing.get('force_noise_n', 0.))
    check('reserve_and_sensor_configuration_consistent',
          metadata['sensor_force_reserve_n'] == FROZEN_MEASUREMENT_RESERVE_N
          and metadata['tracking_reserve_n'] == FROZEN_TRACKING_RESERVE_N
          and public.get('measurement_reserve_n') == metadata['sensor_force_reserve_n']
          and public.get('tracking_reserve_n') == metadata['tracking_reserve_n']
          and np.all(np.asarray(data['tracking_reserve_n']) == metadata['tracking_reserve_n'])
          and np.isclose(sensor_error, declared_sensor_error, atol=1e-12, rtol=0.),
          'The frozen 1 N sensing and 8 N tracking reserves match public parameters, metadata and every control tick; command sensing allowance equals declared bounded sensor error')
    check('pad_displacement_channels_agree',
          np.array_equal(displacement, np.asarray(data['pad_sink_displacement_m'])),
          'Reported target-pad displacement equals the deformation trace audited by the unchanged physical failure validator')
    metrics = dict(
        requested_task_progress_m=float(metadata.get('movement_optimizer_settings', {}).get('forward_progress_m', 0.)),
        fixed_probe_force_n=float(public.get('fixed_probe_force_n', 0.)),
        pad_damaged=bool(np.any(failed)),
        maximum_pad_displacement_m=float(np.max(displacement)),
        pad_failure_time_s=float(t[first_failure]) if first_failure is not None else None,
        pad_failure_phase=str(phase[first_failure]) if first_failure is not None else None,
        pad_failure_during_probe=bool(probe[first_failure]) if first_failure is not None else False,
        probe_time_s=_duration(t, probe, dt),
        deliberate_probe_time_s=_duration(t, deliberate, dt),
        additional_probe_time_s=_duration(t, stronger, dt),
        recovery_time_s=_duration(t, recovery, dt),
        total_trial_time_s=float(t[-1]-t[0]+dt),
        probe_start_time_s=float(t[probe_rows[0]]) if len(probe_rows) else None,
        probe_end_time_s=float(t[probe_rows[-1]]+dt) if len(probe_rows) else None,
        maximum_actual_probe_force_n=float(np.max(physical[probe])) if np.any(probe) else None,
        maximum_measured_probe_force_n=float(np.max(measured[probe])) if np.any(probe) else None,
        maximum_commanded_probe_force_n=float(np.max(commanded[deliberate])) if np.any(deliberate) else None,
        maximum_actual_additional_probe_force_n=float(np.max(physical[stronger])) if np.any(stronger) else None,
        probe_force_impulse_ns=float(np.sum(physical[probe])*dt),
        total_sensing_tracking_reserve_n=reserve,
        declared_probe_undershoot_allowance_n=undershoot,
        declared_command_sensor_error_bound_n=sensor_error,
        applied_probe_undershoot_allowance_n=undershoot if metadata.get('probe_policy') == 'task_sufficient' else 0.,
        applied_command_sensor_error_allowance_n=sensor_error if metadata.get('probe_policy') == 'task_sufficient' else 0.,
        hidden_capacity_n=float(metadata['evaluation'].get('failure_threshold_n', metadata['evaluation'].get('failure_load_n'))),
    )
    if not missing:
        minimum = np.asarray(data['minimum_future_load_n'])
        sufficient = np.asarray(data['minimum_sufficient_probe_load_n'])
        tolerance = np.asarray(data['target_tolerance_n'])
        target = np.asarray(data['probe_target_load_n'])
        requested = np.asarray(data['selected_probe_request_n'])
        valid_shape = all(value.shape == t.shape for value in (minimum, sufficient, tolerance, target, requested))
        finite = valid_shape and all(np.all(np.isfinite(value)) for value in (minimum, sufficient, tolerance, target, requested))
        check('finite_probe_target_telemetry', finite,
              'All per-tick target telemetry has finite values and exactly matches the control clock')
        if finite:
            # The planner has no task target before its first post-test decision.
            selected = sufficient > 0.
            math_ok = np.all(minimum[selected] >= 0.) and np.all(tolerance[selected] > 0.)
            math_ok &= np.allclose(sufficient[selected], minimum[selected]+reserve+tolerance[selected], atol=1e-8, rtol=0.)
            check('sufficient_target_preserves_reserves', math_ok,
                  'Sufficient target equals the shared minimum future load plus unchanged sensing/tracking reserves and positive numerical tolerance')
            active = extra_probe & deliberate
            check('selected_target_matches_executed_command',
                  np.allclose(commanded[active], target[active], atol=1e-8, rtol=0.),
                  'Every additional test actually selects its recorded target amplitude; logging a gentler target while commanding more is invalid')
            probe_decisions = [item for item in metadata.get('capacity_decision_history', []) if item.get('action') == 'PROBE']
            decision_consistent = True
            for index in np.unique(np.asarray(data['additional_probe_count'])[active]):
                decision_index = int(index)-1
                if index != int(index) or decision_index < 0 or decision_index >= len(probe_decisions):
                    decision_consistent = False
                    continue
                decision = probe_decisions[decision_index]
                chosen = active & (np.asarray(data['additional_probe_count']) == index)
                decision_consistent &= (
                    np.allclose(minimum[chosen], decision.get('minimum_future_load_n', np.nan), atol=1e-8, rtol=0.)
                    and np.allclose(target[chosen], decision.get('achievable_probe_load_n', np.nan), atol=1e-8, rtol=0.)
                    and np.allclose(requested[chosen], decision.get('requested_probe_load_n', np.nan), atol=1e-8, rtol=0.))
            check('selected_target_matches_planner_decision', decision_consistent,
                  'Additional-probe index, minimum future load, request and selected amplitude match the logged planner decision')
            if np.any(selected):
                try:
                    # Recompute from recorded geometry using the frozen shared
                    # feasible set. A self-consistent invented target/decision
                    # must not redefine what the movement actually requires.
                    from primp_project.planning.load_capacity import CapacityPlanningConfig, MatchedCapacityPlanner
                    config = CapacityPlanningConfig(**metadata['movement_optimizer_settings'])
                    first_test = int(np.flatnonzero(deliberate)[0])
                    anchors = np.asarray(data['feet_desired_w'])[first_test]
                    origin = np.asarray(data['probe_origin_com_w'])[first_test]
                    weight = float(metadata['model_mass_kg'])*float(metadata['gravity_m_s2'])
                    allocation = MatchedCapacityPlanner('adaptive_probe', config).minimum_future_allocation(
                        anchors, weight, origin, np.full(4, weight))
                    computed_minimum = float(allocation.forces_n[config.weak_leg])
                    recomputed = allocation.feasible and np.allclose(minimum[selected], computed_minimum, atol=1e-7, rtol=0.)
                    observed = computed_minimum
                except (KeyError, TypeError, ValueError, IndexError) as error:
                    recomputed, observed = False, f'{type(error).__name__}: {error}'
                check('task_minimum_recomputed_from_geometry', recomputed,
                      'The task load lower bound is recomputed from initial probing geometry and the unchanged shared movement constraints', observed)
            check('probe_mpc_bounds_match_target',
                  np.all(np.asarray(data['applied_pad_force_cap_n'])[active] <= target[active]+.2+1e-8)
                  and np.all(np.asarray(data['grf_desired_w'])[active, 0, 2]
                             <= np.asarray(data['applied_pad_force_cap_n'])[active]+float(metadata.get('force_tolerance_n', .5))),
                  'Additional-test MPC caps retain the frozen target + 0.2 N bound, and force commands obey the installed cap and declared solver tolerance')
            if metadata.get('probe_policy') == 'task_sufficient':
                check('minimum_policy_targets_sufficient_load', np.any(selected) or not np.any(extra_probe),
                      'Every additional minimum-policy probe declares its task-derived target')
                check('minimum_policy_does_not_select_maximum', undershoot >= 0. and sensor_error >= 0.
                      and np.allclose(target[active], sufficient[active]+sensor_error+undershoot, atol=1e-6, rtol=0.),
                      'The selected command is the measured sufficient target plus declared sensing error and probe undershoot allowance, not the achievable maximum')
            if metadata.get('probe_policy') == 'fixed_force':
                fixed = float(public.get('fixed_probe_force_n', 0.))
                check('fixed_policy_uses_declared_constant', fixed > 0. and np.isfinite(fixed)
                      and metadata.get('fixed_probe_force_n') == fixed
                      and np.allclose(target[active], fixed, atol=1e-8, rtol=0.)
                      and np.allclose(requested[active], fixed, atol=1e-8, rtol=0.),
                      'The fixed policy requests and applies its one declared constant; task load cannot silently tune that command')
            values = np.flatnonzero(selected)
            metrics.update(
                minimum_future_load_n=float(minimum[values[0]]) if len(values) else None,
                minimum_sufficient_test_target_n=float(sufficient[values[0]]) if len(values) else None,
                selected_additional_probe_target_n=float(np.max(target[extra_probe & deliberate])) if np.any(extra_probe & deliberate) else None,
                extra_command_over_sufficient_n=float(np.max(commanded[extra_probe & deliberate]-sufficient[extra_probe & deliberate])) if np.any(extra_probe & deliberate) else None,
                capacity_above_sufficient_target_n=float(metrics['hidden_capacity_n']-sufficient[values[0]]) if len(values) else None,
            )
    if result['physical_success']:
        final = t >= t[-1]-.1
        settings = metadata['movement_optimizer_settings']
        progress = np.asarray(data['com_pos_w'])[:, 0]-np.asarray(data['probe_origin_com_w'])[:, 0]
        required = float(settings['forward_progress_m'])-.001
        next_leg = int(metadata['next_leg_index'])
        others = [leg for leg in range(4) if leg != next_leg]
        contacts = np.asarray(data['contact_measured'], bool)
        normal = np.asarray(data['contact_normal_force'])
        lift = np.asarray(data['feet_pos_w'])[:, next_leg, 2]-np.asarray(data['next_lift_anchor_w'])[:, 2]
        simultaneous = (np.isin(phase, MOVEMENT_PHASES) & (progress >= required-1e-8)
            & (lift >= float(metadata.get('required_next_leg_lift_m', .02))-1e-8)
            & ~contacts[:, next_leg] & ~np.asarray(data['contact_planned'], bool)[:, next_leg]
            & np.all(contacts[:, others] & (normal[:, others] >= 2.), axis=1)
            & np.asarray(data['certificate_valid'], bool) & ~failed)
        hold, _ = _longest(t, simultaneous, dt)
        check('task_specific_goal_attained', np.all(progress[final] >= required-1e-8)
              and hold >= float(settings['next_hold_s'])-1e-8,
              'A completed trial reaches its declared forward goal within 1 mm at termination and sustains that progress with measured next-leg clearance and certified support for the requested hold',
              dict(required_forward_progress_m=required, terminal_minimum_progress_m=float(np.min(progress[final])),
                   simultaneous_task_hold_s=hold))
        metrics.update(task_specific_simultaneous_hold_s=hold,
            task_specific_terminal_minimum_progress_m=float(np.min(progress[final])),task_progress_tolerance_m=.001)
    result['metrics'].update(metrics)
    result['task_probe_criteria'] = added
    result['task_probe_integrity_passed'] = all(item['passed'] for item in added.values())
    if not result['task_probe_integrity_passed']:
        result['outcome'] = 'INVALID'
        result['physical_success'] = False
        result['passed'] = False
    result['conventions'].update(
        probe_time='Recorded control intervals in probe_ramp, probe_hold, probe_release and reprobe_posture; recovery time is separate.',
        pad_damage='Actual simulator failure latch and displacement; never inferred from commanded foot force.',
        sufficient_test='The measured target retains the sensing/tracking reserves. The command additionally covers bounded sensing error and a declared empirical probe undershoot allowance; only the audited measured dwell certificate authorizes future loading.',
        task_capable='Damage avoided requires a matched physical completion with an undamaged pad.',
        fixed_policy='One force selected on the predeclared development tasks, then held constant across every evaluation task and capacity.',
        task_policy='The unchanged task-sufficient planner recomputes its probe target from each task-required load.')
    return _safe(result)


def analyze_task_probe(run_dir):
    run = Path(run_dir)
    metadata = json.loads((run/'metadata.json').read_text())
    with np.load(run/'signals.npz', allow_pickle=False) as archive:
        data = {key:archive[key] for key in archive.files}
    # Save unchanged baseline analysis alongside the focused extension.
    baseline = evaluate_weak_pad_v2(metadata, data)
    baseline['run_id'] = run.name
    (run/'weak_pad_summary.json').write_text(json.dumps(baseline, indent=2, allow_nan=False)+'\n')
    result = evaluate_task_probe(metadata, data)
    result['run_id'] = run.name
    (run/'task_probe_summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    lines = [f"# Task-load probing: {result['outcome']}", '',
             f"Policy: {result['probe_policy']}. Physical task completion: {result['physical_success']}.", '',
             'V2 physical, certificate and recovery checks are unchanged. Pad damage and controlled recovery remain separate from completion.', '',
             '| Check | Passed | Requirement |', '| --- | --- | --- |']
    for name, item in {**result['criteria'], **result['task_probe_criteria']}.items():
        lines.append(f"| {name} | {item['passed']} | {item['requirement']} |")
    (run/'task_probe_report.md').write_text('\n'.join(lines)+'\n')
    plot_overview(metadata, data, baseline, run/'weak_pad_overview.png')
    return result


def compare_baseline_traces(original_run_dir, extension_run_dir):
    """Audit unchanged physical/command traces for a paired baseline replay.

    Wall-clock and measured solver runtimes depend on host scheduling. Every
    other original per-tick channel must match, including MPC timing/status,
    qpos/qvel, sensor observations, applied force, certificate and phase.
    """
    ignored = {'wall_time_s', 'solver_time_s'}
    with np.load(Path(original_run_dir)/'signals.npz', allow_pickle=False) as original:
        with np.load(Path(extension_run_dir)/'signals.npz', allow_pickle=False) as extension:
            missing = sorted(set(original.files)-set(extension.files))
            mismatches = []
            for name in sorted(set(original.files)&set(extension.files)-ignored):
                a, b = original[name], extension[name]
                equal = np.array_equal(a, b, equal_nan=True) if a.dtype.kind in 'fc' else np.array_equal(a, b)
                if not equal:
                    delta = float(np.max(np.abs(a-b))) if a.shape == b.shape and a.dtype.kind in 'fc' else None
                    mismatches.append(dict(channel=name, original_shape=list(a.shape), extension_shape=list(b.shape), max_abs_difference=delta))
            return dict(verified=not missing and not mismatches,
                original_run_dir=str(Path(original_run_dir).resolve()),
                extension_run_dir=str(Path(extension_run_dir).resolve()),
                compared_channels=len(set(original.files)&set(extension.files)-ignored),
                ignored_host_runtime_channels=sorted(ignored), missing=missing, mismatches=mismatches)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(analyze_task_probe(args.run_dir), indent=2))


if __name__ == '__main__':
    main()
