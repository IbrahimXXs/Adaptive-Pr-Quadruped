#!/usr/bin/env python3
"""Record settling followed by 30 seconds of zero-command four-foot standing."""

import argparse
from datetime import datetime, timezone
import math
import traceback

from quadruped_pympc import config as cfg
from simulation.simulation import run_simulation
from primp_project import RESULTS_ROOT
from primp_project.recording.standing import StandingRecorder
from primp_project.recording.catalog import refresh_catalog
from primp_project.analysis.standing import analyze_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30.0, help="Standing duration after settling (default: 30 s).")
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--headless", action="store_true", help="Record without opening the viewer.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    for name, value in (("seconds", args.seconds), ("settle-seconds", args.settle_seconds)):
        if not math.isfinite(value) or value < 0 or (name == "seconds" and value == 0):
            parser.error(f"--{name} must be finite and {'positive' if name == 'seconds' else 'nonnegative'}")
        steps = value / cfg.simulation_params["dt"]
        if not math.isclose(steps, round(steps), abs_tol=1e-7):
            parser.error(f"--{name} must be a multiple of the simulation timestep")
    for key, expected in (("gait", "full_stance"), ("scene", "flat"), ("mode", "human")):
        if cfg.simulation_params[key] != expected:
            parser.error(f"Standing baseline requires simulation_params[{key!r}] = {expected!r}")
    if cfg.mpc_params["type"] != "nominal":
        parser.error("This baseline recorder currently validates the existing nominal acados controller.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    results_group = RESULTS_ROOT / ("archive" if args.seconds < 30 else "standing")
    run_dir = results_group / f"standing_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    recorder = StandingRecorder(run_dir, args.seconds, args.settle_seconds, args.seed, not args.headless)
    print(f"Recording in {run_dir}", flush=True)
    error = None
    try:
        run_simulation(
            qpympc_cfg=cfg, num_episodes=1,
            num_seconds_per_episode=args.seconds + args.settle_seconds,
            ref_base_lin_vel=(0.0, 0.0), ref_base_ang_vel=(0.0, 0.0),
            friction_coeff=(0.8, 0.8), base_vel_command_type=cfg.simulation_params["mode"],
            seed=args.seed, render=not args.headless, experiment_recorder=recorder,
            lock_zero_velocity=True, stop_on_termination=True,
        )
    except (Exception, KeyboardInterrupt) as exc:
        error = f"{type(exc).__name__}: {exc}"
        (run_dir / "error.txt").write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        recorder.save("completed" if error is None else "failed", error)
    if recorder.rows:
        summary = analyze_run(run_dir)
        passed = summary["passed"]
    else:
        passed = False
    (results_group / "LATEST.txt").write_text(run_dir.name + "\n")
    refresh_catalog()
    print(f"\n{'PASS' if passed and error is None else 'FAIL'}: {run_dir}", flush=True)
    return 0 if passed and error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
