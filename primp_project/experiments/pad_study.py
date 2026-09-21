"""Collect known-height demonstrations and run a predeclared landing-pad pilot."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from primp_project import PROJECT_ROOT, REPOSITORY_ROOT, RESULTS_ROOT


DEFAULT_STUDY_DIR = RESULTS_ROOT / "landing_pad" / "study"
PLANNERS = ("reactive", "predictive", "learned")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")
    temporary.replace(path)


def protocol():
    """Return fixed cells before looking at any evaluation outcome."""
    demonstrations = []
    for height in (-.01, 0., .01):
        for duration in (3., 4., 5.):
            demonstrations.append(dict(
                trial_id=f"demo_h{int(round(height*1000)):+03d}mm_t{duration:g}s",
                actual_height_m=height, initial_estimate_m=height,
                planner="reactive", role="demonstration", lower_duration_s=duration,
                sensor_profile="clean", seed=17))
    evaluations = []
    for sensor in ("clean", "noisy_delayed"):
        for height in (-.005, 0., .005):
            for planner in PLANNERS:
                evaluations.append(dict(
                    trial_id=f"eval_{planner}_h{int(round(height*1000)):+03d}mm_{sensor}",
                    actual_height_m=height, initial_estimate_m=0., planner=planner,
                    role="evaluation", lower_duration_s=4., sensor_profile=sensor, seed=17))
    return dict(version=1, study="adjustable_landing_pad_pilot", demonstrations=demonstrations,
                evaluations=evaluations, evaluation_policy=dict(
                    repetitions_per_cell=1, seed=17,
                    held_out_heights_m=[-.005, .005], calibration_height_m=0.,
                    held_out_sensor_profile="noisy_delayed",
                    shared="Initial estimate, sensing settings, execution controller, contact gates and feasibility limits",
                    conclusions="Descriptive simulation pilot; no statistical superiority claim"))


def ensure_manifest(study_dir):
    study_dir = Path(study_dir)
    study_dir.mkdir(parents=True, exist_ok=True)
    path = study_dir/"split_manifest.json"
    expected = protocol()
    if path.exists():
        saved = json.loads(path.read_text())
        if {key: saved.get(key) for key in expected} != expected:
            raise ValueError("Existing split manifest differs from this protocol; choose a new study directory")
    else:
        _write_json(path, dict(expected, created_at=_now()))
    return json.loads(path.read_text()), path


def held_out_protocol(primary_manifest_sha256, model_sha256):
    """A separate untouched-height supplement; the original 18 cells are fixed."""
    cells = []
    for height in (-.0075, .0075):
        for planner in PLANNERS:
            cells.append(dict(trial_id=f"heldout_{planner}_h{height*1000:+.1f}mm_clean",
                              actual_height_m=height, initial_estimate_m=0., planner=planner,
                              role="evaluation", lower_duration_s=4., sensor_profile="clean", seed=17))
    return dict(version=1, study="adjustable_landing_pad_held_out_heights", demonstrations=[], evaluations=cells,
                inherits=dict(primary_split_manifest_sha256=primary_manifest_sha256,
                              fitted_model_sha256=model_sha256, fitted_model_relative_path="../model/model.npz"),
                evaluation_policy=dict(repetitions_per_cell=1, seed=17,
                    held_out_heights_m=[-.0075, .0075], sensor_profiles=["clean"],
                    height_reservation="Neither height used in demonstration fitting or live engineering development before declaration",
                    model_policy="Reuse the original nine-demonstration model; no refitting",
                    execution_policy="Same source fingerprint and controller as the completed paired eighteen-cell pilot",
                    conclusions="Descriptive supplementary simulation pilot; no statistical superiority claim"))


def ensure_held_out_manifest(study_dir=DEFAULT_STUDY_DIR):
    """Predeclare six held-out cells and bind them to the existing fitted model."""
    study_dir = Path(study_dir).resolve()
    _, primary_manifest = ensure_manifest(study_dir)
    primary_state = _load_state(study_dir, primary_manifest)
    model_record = primary_state.get("model")
    model_path = study_dir/"model"/"model.npz"
    if not model_record or not model_path.exists() or model_record["model_sha256"] != _sha(model_path):
        raise ValueError("The original nine-demonstration model is required before declaring held-out heights")
    directory = study_dir/"held_out_heights"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/"split_manifest.json"
    expected = held_out_protocol(_sha(primary_manifest), _sha(model_path))
    if path.exists():
        saved = json.loads(path.read_text())
        if {key: saved.get(key) for key in expected} != expected:
            raise ValueError("Held-out manifest or inherited model differs; preserve this evaluation and create a separate study")
    else:
        _write_json(path, dict(expected, created_at=_now()))
    state = _load_state(directory, path)
    if state.get("model") is None:
        state["model"] = dict(model_record)
        state["primary_study_directory"] = str(study_dir)
        _write_json(directory/"study_state.json", state)
    return json.loads(path.read_text()), path


def source_fingerprint(scope="evaluation"):
    """Identify experiment-affecting code so a resume cannot hide code changes."""
    paths = []
    for directory in ("control", "planning", "learning", "environment", "recording"):
        if scope == "demonstration" and directory == "learning":
            continue
        paths.extend((PROJECT_ROOT/directory).glob("*.py"))
    paths.extend(PROJECT_ROOT/name for name in ("experiments/pad.py", "analysis/pad.py", "analysis/step.py"))
    paths.extend(REPOSITORY_ROOT/name for name in ("simulation/simulation.py", "quadruped_pympc/config.py"))
    h = hashlib.sha256()
    for path in sorted(set(paths)):
        if path.exists() and path.name != "catalog.py":
            source = path.read_bytes()
            if scope == "demonstration" and path == PROJECT_ROOT/"planning"/"baselines.py":
                # Development of the unused learned adapter does not invalidate
                # already measured reactive demonstrations.
                tree = ast.parse(source)
                tree.body = [node for node in tree.body if not
                             (isinstance(node, ast.ClassDef) and node.name == "LearnedMotionPlanner")]
                source = ast.dump(tree, include_attributes=False).encode()
            h.update(str(path.relative_to(REPOSITORY_ROOT)).encode()+b"\0"+source+b"\0")
    return h.hexdigest()


def _load_state(study_dir, manifest_path):
    path = study_dir/"study_state.json"
    digest = _sha(manifest_path)
    if path.exists():
        state = json.loads(path.read_text())
        if state.get("split_manifest_sha256") != digest:
            raise ValueError("Split manifest changed after study state was created")
        return state
    return dict(version=1, split_manifest_sha256=digest, created_at=_now(), trials={}, model=None)


def _validate_record(run_dir, spec, entry=None):
    """Verify association and acceptance from disk, rather than trusting the journal."""
    run_dir = Path(run_dir)
    metadata_path, summary_path = run_dir/"metadata.json", run_dir/"pad_summary.json"
    metadata = json.loads(metadata_path.read_text())
    summary = json.loads(summary_path.read_text())
    observed_sensor = metadata.get("sensor_profile")
    if isinstance(observed_sensor, dict):
        observed_sensor = observed_sensor.get("name")
    pairs = {
        "role": (metadata.get("role"), spec["role"]),
        "planner": (metadata.get("planner"), spec["planner"]),
        "sensor_profile": (observed_sensor, spec["sensor_profile"]),
        "seed": (metadata.get("seed"), spec["seed"]),
        "initial_height_estimate_m": (metadata.get("initial_height_estimate_m"), spec["initial_estimate_m"]),
        "nominal_lower_duration_s": (metadata.get("nominal_lower_duration_s"), spec["lower_duration_s"]),
        "actual_pad_height_m": (metadata.get("evaluation", {}).get("actual_pad_height_m"), spec["actual_height_m"]),
    }
    mismatch = {name: pair for name, pair in pairs.items() if pair[0] != pair[1]}
    if metadata.get("experiment") != "landing_pad" or mismatch:
        raise ValueError(f"{run_dir.name}: recording does not match declared cell: {mismatch}")
    if summary.get("passed") is True and metadata.get("status") != "completed":
        raise ValueError(f"{run_dir.name}: acceptance claims success for an incomplete recording")
    if entry:
        for key, path in (("signals_sha256", run_dir/"signals.npz"),
                          ("metadata_sha256", metadata_path), ("summary_sha256", summary_path)):
            if entry.get(key) is not None and (not path.exists() or entry[key] != _sha(path)):
                raise ValueError(f"{run_dir.name}: saved {key} changed after the trial")
    return summary


def _run_cell(spec, *, study_dir, state, runner, headless, code_hash, model_path=None, output_group=None):
    trial_id = spec["trial_id"]
    state_path = study_dir/"study_state.json"
    old = state["trials"].get(trial_id)
    model_hash = _sha(Path(model_path)/"model.npz") if model_path is not None else None
    if old is not None:
        if old.get("source_sha256") != code_hash or old.get("model_sha256") != model_hash:
            raise ValueError(f"{trial_id}: code/model differs from the recorded attempt; use a new study directory")
        if old.get("status") == "running":
            raise ValueError(f"{trial_id}: interrupted attempt needs review; its journal and partial recordings are preserved")
        if old.get("run_dir") and old.get("status") != "error":
            summary = _validate_record(old["run_dir"], spec, old)
            if bool(summary.get("passed")) != bool(old.get("passed")):
                raise ValueError(f"{trial_id}: acceptance changed after the attempt")
        print(f"Resume {trial_id}: {'PASS' if old.get('passed') else 'FAIL'}", flush=True)
        return old
    entry = dict(trial_id=trial_id, status="running", passed=False, started_at=_now(),
                 source_sha256=code_hash, model_sha256=model_hash, parameters=dict(spec))
    state["trials"][trial_id] = entry
    _write_json(state_path, state)
    print(f"Run {trial_id}", flush=True)
    kwargs = {key: value for key, value in spec.items() if key != "trial_id"}
    kwargs.update(headless=headless, model_path=model_path,
                  output_group=Path(output_group) if output_group is not None else
                  study_dir.parent/("demonstrations" if spec["role"] == "demonstration" else "evaluation"))
    try:
        run_dir, returned_summary = runner(**kwargs)
        run_dir = Path(run_dir).resolve()
        # Store the result directory even if verification fails, so that failed
        # attempts remain findable and cannot disappear from the comparison.
        entry["run_dir"] = str(run_dir)
        summary = _validate_record(run_dir, spec)
        if bool(returned_summary.get("passed")) != bool(summary.get("passed")):
            raise ValueError("Runner acceptance differs from the saved acceptance summary")
        entry.update(status="completed", passed=summary.get("passed") is True,
                     signals_sha256=_sha(run_dir/"signals.npz") if (run_dir/"signals.npz").exists() else None,
                     metadata_sha256=_sha(run_dir/"metadata.json"), summary_sha256=_sha(run_dir/"pad_summary.json"))
    except Exception as exc:
        entry.update(status="error", passed=False, error=f"{type(exc).__name__}: {exc}")
    finally:
        entry["finished_at"] = _now()
        state["updated_at"] = _now()
        _write_json(state_path, state)
    return entry


def run_held_out_heights(*, study_dir=DEFAULT_STUDY_DIR, headless=True, trial_runner=None):
    """Run six untouched-height cells with the unchanged paired-pilot model/code."""
    study_dir = Path(study_dir).resolve()
    manifest, manifest_path = ensure_held_out_manifest(study_dir)
    directory = manifest_path.parent
    state = _load_state(directory, manifest_path)
    primary_manifest = json.loads((study_dir/"split_manifest.json").read_text())
    primary_state = _load_state(study_dir, study_dir/"split_manifest.json")
    primary_attempts = [primary_state["trials"].get(spec["trial_id"], {})
                        for spec in primary_manifest["evaluations"]]
    if any(not entry or entry.get("status") == "running" for entry in primary_attempts):
        raise ValueError("Complete the eighteen declared paired-pilot attempts before supplementary held-out evaluation")
    code_hash = source_fingerprint()
    if {entry.get("source_sha256") for entry in primary_attempts} != {code_hash}:
        raise ValueError("Held-out evaluation must keep the paired pilot's source/controller unchanged")
    model_path = study_dir/"model"/"model.npz"
    model_hash = _sha(model_path)
    if model_hash != manifest["inherits"]["fitted_model_sha256"]:
        raise ValueError("The inherited fitted model changed after held-out declaration")
    from primp_project.learning import PRIMPMotionModel
    PRIMPMotionModel.load(model_path)
    if trial_runner is None:
        from primp_project.experiments.pad import run_trial
        trial_runner = run_trial
    for spec in manifest["evaluations"]:
        _run_cell(spec, study_dir=directory, state=state, runner=trial_runner, headless=headless,
                  code_hash=code_hash, model_path=study_dir/"model" if spec["planner"] == "learned" else None,
                  output_group=directory/"recordings")
    # Reporting must never mutate/refit the original model, including its hash.
    if _sha(model_path) != model_hash:
        raise ValueError("Fitted model was unexpectedly modified during held-out evaluation")
    from primp_project.analysis.comparison import write_comparison
    write_comparison(directory)
    return state


def run_study(stage, *, study_dir=DEFAULT_STUDY_DIR, headless=True, trial_runner=None):
    """Run demo/train/evaluate/all; failures are retained and never cherry-picked."""
    if stage == "heldout":
        return run_held_out_heights(study_dir=study_dir, headless=headless, trial_runner=trial_runner)
    if stage not in ("demo", "train", "evaluate", "all"):
        raise ValueError("Study stage must be demo, train, evaluate, all or heldout")
    study_dir = Path(study_dir).resolve()
    manifest, manifest_path = ensure_manifest(study_dir)
    state = _load_state(study_dir, manifest_path)
    code_hash = source_fingerprint()
    demo_code_hash = source_fingerprint("demonstration")
    if trial_runner is None and stage in ("demo", "evaluate", "all"):
        from primp_project.experiments.pad import run_trial
        trial_runner = run_trial
    if stage in ("demo", "all"):
        for spec in manifest["demonstrations"]:
            entry = _run_cell(spec, study_dir=study_dir, state=state, runner=trial_runner,
                              headless=headless, code_hash=demo_code_hash)
            if not entry["passed"]:
                raise RuntimeError(f"Demonstration {spec['trial_id']} failed; training stopped. See {study_dir/'study_state.json'}")
    if stage in ("train", "all"):
        from primp_project.learning import fit_runs
        runs = []
        for spec in manifest["demonstrations"]:
            entry = state["trials"].get(spec["trial_id"])
            if not entry or not entry.get("passed") or not entry.get("run_dir"):
                raise ValueError("All nine accepted demonstrations are required before training")
            if not _validate_record(entry["run_dir"], spec, entry).get("passed"):
                raise ValueError(f"{spec['trial_id']}: demonstration no longer passes")
            runs.append(entry["run_dir"])
        # An `all` resume keeps its existing model; explicit retraining is
        # forbidden once evaluation has begun.
        evaluated = any(spec["trial_id"] in state["trials"] for spec in manifest["evaluations"])
        model_path = study_dir/"model"/"model.npz"
        saved_model = state.get("model")
        preserve = stage == "all" and saved_model is not None
        if preserve:
            if (not model_path.exists() or saved_model["model_sha256"] != _sha(model_path)
                    or saved_model["training_run_ids"] != [Path(run).name for run in runs]):
                raise ValueError("Existing model does not match this study's saved training set")
        else:
            if evaluated:
                raise ValueError("Evaluation has begun; preserve its model and use a new study directory for retraining")
            model = fit_runs(runs, split_manifest_path=manifest_path)
            model_path = model.save(study_dir/"model")
            state["model"] = dict(path=str(model_path), model_sha256=_sha(model_path),
                                  trained_at=_now(), training_run_ids=[Path(run).name for run in runs],
                                  split_manifest_sha256=_sha(manifest_path))
            _write_json(study_dir/"study_state.json", state)
    if stage in ("evaluate", "all"):
        model_path = study_dir/"model"/"model.npz"
        model_record = state.get("model")
        if not model_record or not model_path.exists() or model_record["model_sha256"] != _sha(model_path):
            raise ValueError("Train and preserve the study model before evaluating the three planners")
        from primp_project.learning import PRIMPMotionModel
        PRIMPMotionModel.load(model_path)  # Check numeric model + provenance integrity.
        for spec in manifest["evaluations"]:
            _run_cell(spec, study_dir=study_dir, state=state, runner=trial_runner,
                      headless=headless, code_hash=code_hash,
                      model_path=study_dir/"model" if spec["planner"] == "learned" else None)
        from primp_project.analysis.comparison import write_comparison
        write_comparison(study_dir)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project pad-study", description=__doc__)
    parser.add_argument("stage", choices=("demo", "train", "evaluate", "all", "heldout"))
    parser.add_argument("--study-dir", type=Path, default=DEFAULT_STUDY_DIR)
    parser.add_argument("--render", action="store_true", help="Open the simulator viewer for each sequential trial")
    args = parser.parse_args(argv)
    try:
        state = run_study(args.stage, study_dir=args.study_dir, headless=not args.render)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"Study stopped: {exc}\n")
    trials = list(state["trials"].values())
    print(f"Study: {args.study_dir.resolve()}\nAccepted recordings: {sum(t.get('passed', False) for t in trials)}/{len(trials)}", flush=True)
    if args.stage in ("evaluate", "all", "heldout"):
        cells = (ensure_held_out_manifest(args.study_dir)[0] if args.stage == "heldout" else protocol())["evaluations"]
        return 0 if all(state["trials"].get(c["trial_id"], {}).get("passed") for c in cells) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
