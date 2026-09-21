"""Probe-dose comparison layered over the unmodified V2 physical validator.

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
from primp_project.analysis.weak_pad_v2 import evaluate_weak_pad_v2, PROBE_PHASES, RECOVERY_PHASES
from primp_project.analysis.weak_pad import plot_overview

POLICIES = ('maximum_feasible', 'minimum_sufficient')
EXTRA_SIGNALS = ('minimum_future_load_n', 'minimum_sufficient_probe_load_n',
                 'target_tolerance_n', 'probe_target_load_n')


def _duration(time, mask, dt):
    """Count recorded fixed-rate control intervals, including their final tick."""
    return float(np.count_nonzero(mask) * dt)


def evaluate_probe_efficiency(metadata, data):
    """Preserve every V2 criterion; audit added policy telemetry separately."""
    result = evaluate_weak_pad_v2(metadata, data)
    result['baseline_validator'] = 'primp_project.analysis.weak_pad_v2.evaluate_weak_pad_v2'
    result['baseline_outcome'] = result['outcome']
    result['study_name'] = 'probe_efficiency'
    result['probe_policy'] = metadata.get('probe_policy')
    added = {}

    def check(name, passed, requirement, observed=None):
        added[name] = dict(passed=bool(passed), category='integrity', requirement=requirement,
                           observed=_safe(observed))

    check('probe_efficiency_identity', metadata.get('study_name') == 'probe_efficiency'
          and metadata.get('probe_policy') in POLICIES and metadata.get('strategy') == 'adaptive_probe',
          'Probe dose changes while the frozen adaptive_probe controller and shared movement optimizer remain the foundation')
    missing = [name for name in EXTRA_SIGNALS if name not in data]
    check('probe_target_telemetry', not missing,
          'Record minimum task load, sufficient test target, tolerance and selected probe target', missing)
    if not len(data.get('control_time_s', [])):
        result['probe_efficiency_criteria'] = added
        result['outcome'] = 'INVALID'
        result['physical_success'] = False
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
    metrics = dict(
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
        probe_undershoot_allowance_n=undershoot,
        command_sensor_error_allowance_n=sensor_error,
        hidden_capacity_n=float(metadata['evaluation'].get('failure_threshold_n', metadata['evaluation'].get('failure_load_n'))),
    )
    if not missing:
        minimum = np.asarray(data['minimum_future_load_n'])
        sufficient = np.asarray(data['minimum_sufficient_probe_load_n'])
        tolerance = np.asarray(data['target_tolerance_n'])
        target = np.asarray(data['probe_target_load_n'])
        valid_shape = all(value.shape == t.shape for value in (minimum, sufficient, tolerance, target))
        finite = valid_shape and all(np.all(np.isfinite(value)) for value in (minimum, sufficient, tolerance, target))
        check('finite_probe_target_telemetry', finite,
              'All per-tick target telemetry has finite values and exactly matches the control clock')
        if finite:
            # The planner has no task target before its first post-test decision.
            selected = extra_probe & (sufficient > 0.)
            math_ok = np.all(minimum[selected] >= 0.) and np.all(tolerance[selected] > 0.)
            math_ok &= np.allclose(sufficient[selected], minimum[selected]+reserve+tolerance[selected], atol=1e-8, rtol=0.)
            check('sufficient_target_preserves_reserves', math_ok,
                  'Sufficient target equals the shared minimum future load plus unchanged sensing/tracking reserves and positive numerical tolerance')
            if metadata.get('probe_policy') == 'minimum_sufficient':
                active = extra_probe & deliberate
                check('minimum_policy_targets_sufficient_load', np.any(selected) or not np.any(extra_probe),
                      'Every additional minimum-policy probe declares its task-derived target')
                check('minimum_policy_does_not_select_maximum', undershoot >= 0. and sensor_error >= 0.
                      and np.allclose(target[active], sufficient[active]+sensor_error+undershoot, atol=1e-6, rtol=0.),
                      'The selected command is the measured sufficient target plus declared sensing error and probe undershoot allowance, not the achievable maximum')
            values = np.flatnonzero(selected)
            metrics.update(
                minimum_future_load_n=float(minimum[values[0]]) if len(values) else None,
                minimum_sufficient_test_target_n=float(sufficient[values[0]]) if len(values) else None,
                selected_additional_probe_target_n=float(np.max(target[extra_probe & deliberate])) if np.any(extra_probe & deliberate) else None,
                extra_command_over_sufficient_n=float(np.max(commanded[extra_probe & deliberate]-sufficient[extra_probe & deliberate])) if np.any(extra_probe & deliberate) else None,
                capacity_above_sufficient_target_n=float(metrics['hidden_capacity_n']-sufficient[values[0]]) if len(values) else None,
            )
    result['metrics'].update(metrics)
    result['probe_efficiency_criteria'] = added
    result['probe_efficiency_integrity_passed'] = all(item['passed'] for item in added.values())
    if not result['probe_efficiency_integrity_passed']:
        result['outcome'] = 'INVALID'
        result['physical_success'] = False
    result['conventions'].update(
        probe_time='Recorded control intervals in probe_ramp, probe_hold, probe_release and reprobe_posture; recovery time is separate.',
        pad_damage='Actual simulator failure latch and displacement; never inferred from commanded foot force.',
        sufficient_test='The measured target retains the sensing/tracking reserves. The command additionally covers bounded sensing error and a declared empirical probe undershoot allowance; only the audited measured dwell certificate authorizes future loading.',
        task_capable='Avoidable damage is claimed only when the matched gentler-policy trial physically completes with an undamaged pad.',
        prior_failures='This sweep does not relabel the four earlier failures as preventable; their pads were below the task-required load.')
    return _safe(result)


def analyze_probe_efficiency(run_dir):
    run = Path(run_dir)
    metadata = json.loads((run/'metadata.json').read_text())
    with np.load(run/'signals.npz', allow_pickle=False) as archive:
        data = {key:archive[key] for key in archive.files}
    # Save unchanged baseline analysis alongside the focused extension.
    baseline = evaluate_weak_pad_v2(metadata, data)
    baseline['run_id'] = run.name
    (run/'weak_pad_summary.json').write_text(json.dumps(baseline, indent=2, allow_nan=False)+'\n')
    result = evaluate_probe_efficiency(metadata, data)
    result['run_id'] = run.name
    (run/'probe_efficiency_summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    lines = [f"# Probe efficiency: {result['outcome']}", '',
             f"Policy: {result['probe_policy']}. Physical task completion: {result['physical_success']}.", '',
             'V2 physical, certificate and recovery checks are unchanged. Pad damage and controlled recovery remain separate from completion.', '',
             '| Check | Passed | Requirement |', '| --- | --- | --- |']
    for name, item in {**result['criteria'], **result['probe_efficiency_criteria']}.items():
        lines.append(f"| {name} | {item['passed']} | {item['requirement']} |")
    (run/'probe_efficiency_report.md').write_text('\n'.join(lines)+'\n')
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
    print(json.dumps(analyze_probe_efficiency(args.run_dir), indent=2))


if __name__ == '__main__':
    main()
