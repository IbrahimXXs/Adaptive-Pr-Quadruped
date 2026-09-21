"""A separate, predeclared study of matched predictive motion priors and ablations.

V1 recordings and models are read-only training provenance. New recovery
demonstrations, fitted models, failures, and evaluation records live in V2.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import hashlib
import json
import multiprocessing
import os
from pathlib import Path

from primp_project import PROJECT_ROOT, REPOSITORY_ROOT, RESULTS_ROOT
from .pad_study import _now, _sha, _write_json, _validate_record as _validate_v1_record


DEFAULT_STUDY_DIR = RESULTS_ROOT / "landing_pad" / "study_v2"
DEFAULT_V1_STUDY_DIR = RESULTS_ROOT / "landing_pad" / "study"
PLANNERS = (
    "matched_predictive", "matched_learned", "matched_no_body_foot_correlation",
    "matched_no_timing_adaptation", "matched_no_noncontact_updates",
)
MODEL_DIRS = ("model", "recovery_model")
MODEL_FILES = {"model": ("model.npz", "model.json"),
               "recovery_model": ("recovery.npz", "recovery.json")}


def protocol():
    demonstrations = [dict(
        trial_id=f"recovery_h{height*1000:+g}mm_t{duration:g}s",
        actual_height_m=height, initial_estimate_m=0., planner="reactive",
        role="demonstration", recovery_demonstration=True,
        lower_duration_s=duration, sensor_profile="clean", seed=17,
        initial_condition="nominal")
        for height in (-.004, -.008, -.012) for duration in (3., 4., 5.)]
    evaluations = [dict(
        trial_id=f"eval_{planner}_h{height*1000:+g}mm_seed{seed}_{initial}",
        actual_height_m=height, initial_estimate_m=0., planner=planner,
        role="evaluation", recovery_demonstration=False,
        lower_duration_s=4., sensor_profile="noisy_delayed", seed=seed,
        initial_condition=initial)
        for height in (-.006, .006) for seed in (17, 29, 43)
        for initial in ("nominal", "raised") for planner in PLANNERS]
    return dict(
        version=2, study="matched_landing_motion_distribution_v2",
        demonstrations=demonstrations, evaluations=evaluations,
        training_policy={
            "preserved_v1_demonstrations": 9, "new_recovery_demonstrations": 9,
            "motion_training": "All 18 accepted demonstrations; immutable V1 labels and measured trajectories",
            "recovery_training": "The nine new missing-contact recovery demonstrations only",
            "evaluation_data_excluded": True,
        },
        evaluation_policy={
            "paired_keys": ["actual_height_m", "seed", "initial_condition"],
            "seeds": [17, 29, 43], "sensor_profile": "noisy_delayed",
            "held_out_heights_m": [-.006, .006],
            "initial_conditions": {"nominal": "30 mm held foot clearance", "raised": "35 mm held foot clearance"},
            "matched": "Same predictive execution framework, sensing, estimator inputs, contact gates, limits, and model files; declared prior/conditioning ablations only",
            "reservation": "Evaluation heights and raised initial clearance are withheld from fitting and live development",
            "failure_policy": "One recorded attempt per cell; no silent retry, replacement, or success-only denominator",
            "conclusions": "Paired descriptive simulation study; no automatic statistical superiority claim",
        })


def _capture_v1_sources(v1_study_dir):
    """Verify canonical V1 records, without reanalyzing or rewriting anything."""
    v1_study_dir = Path(v1_study_dir).resolve()
    manifest_path, state_path = v1_study_dir/"split_manifest.json", v1_study_dir/"study_state.json"
    manifest, state = json.loads(manifest_path.read_text()), json.loads(state_path.read_text())
    if state.get("split_manifest_sha256") != _sha(manifest_path):
        raise ValueError("V1 manifest does not match its preserved state")
    specs = manifest.get("demonstrations", [])
    if len(specs) != 9:
        raise ValueError("Exactly nine preserved V1 demonstrations are required")
    records = []
    for spec in specs:
        entry = state.get("trials", {}).get(spec["trial_id"], {})
        if entry.get("status") != "completed" or not entry.get("passed") or not entry.get("run_dir"):
            raise ValueError("Every inherited V1 demonstration must have completed successfully")
        directory = Path(entry["run_dir"]).resolve()
        if _validate_v1_record(directory, spec, entry).get("passed") is not True:
            raise ValueError(f"V1 training record {directory.name} does not pass")
        hashes = {key: _sha(directory/name) for key, name in (
            ("signals_sha256", "signals.npz"), ("metadata_sha256", "metadata.json"),
            ("summary_sha256", "pad_summary.json"))}
        records.append(dict(trial_id=spec["trial_id"], run_id=directory.name,
                            run_dir=str(directory), parameters=spec, **hashes))
    return dict(version=1, source_study_directory=str(v1_study_dir),
                source_manifest_sha256=_sha(manifest_path),
                source_state_sha256_at_capture=_sha(state_path), records=records)


def validate_v1_sources(inventory):
    """Validate only captured training files; later V1 reporting is irrelevant."""
    records = inventory.get("records", [])
    if len(records) != 9 or len({record["run_dir"] for record in records}) != 9:
        raise ValueError("V1 training inventory must contain nine distinct recordings")
    for record in records:
        directory = Path(record["run_dir"])
        summary = _validate_v1_record(directory, record["parameters"], record)
        if summary.get("passed") is not True:
            raise ValueError(f"Preserved V1 demonstration {directory.name} failed")
    return [Path(record["run_dir"]) for record in records]


def ensure_manifest(study_dir=DEFAULT_STUDY_DIR, *, v1_study_dir=DEFAULT_V1_STUDY_DIR):
    directory = Path(study_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    inventory_path = directory/"v1_training_manifest.json"
    if not inventory_path.exists():
        _write_json(inventory_path, _capture_v1_sources(v1_study_dir))
    inventory = json.loads(inventory_path.read_text())
    validate_v1_sources(inventory)
    expected = dict(protocol(), v1_training_manifest_sha256=_sha(inventory_path))
    path = directory/"split_manifest.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if {key: saved.get(key) for key in expected} != expected:
            raise ValueError("V2 manifest differs from the reserved protocol; use a fresh study directory")
    else:
        _write_json(path, dict(expected, created_at=_now()))
    return json.loads(path.read_text()), path


def _load_state(directory, manifest_path):
    path = directory/"study_state.json"
    if path.exists():
        state = json.loads(path.read_text())
        if state.get("split_manifest_sha256") != _sha(manifest_path):
            raise ValueError("V2 split manifest changed after bookkeeping began")
        return state
    return dict(version=2, created_at=_now(), split_manifest_sha256=_sha(manifest_path),
                trials={}, models=None)


def source_fingerprint(scope="evaluation"):
    """Exclude unrelated tools; bind execution, fitting, validation, and protocol."""
    paths = []
    if scope == "demonstration":
        names = ("control/controlled_step.py", "control/landing_pad.py",
                 "planning/observations.py", "planning/belief.py", "planning/baselines.py",
                 "environment/landing_pad.py", "recording/standing.py", "recording/step.py", "recording/pad.py")
        paths.extend(PROJECT_ROOT/name for name in names)
    else:
        for name in ("control", "planning", "learning", "environment", "recording"):
            paths.extend((PROJECT_ROOT/name).glob("*.py"))
        paths.extend(PROJECT_ROOT/name for name in ("experiments/pad_study_v2.py", "analysis/comparison_v2.py"))
    paths.extend(PROJECT_ROOT/name for name in ("experiments/pad.py", "analysis/pad.py", "analysis/step.py", "analysis/adaptation.py"))
    paths.extend(REPOSITORY_ROOT/name for name in ("simulation/simulation.py", "quadruped_pympc/config.py"))
    paths.append(REPOSITORY_ROOT/"quadruped_pympc/controllers/gradient/nominal/centroidal_nmpc_nominal.py")
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        if not path.is_file() or path.name == "catalog.py":
            continue
        content = path.read_bytes()
        if scope == "demonstration" and path.name == "baselines.py":
            tree = ast.parse(content)
            tree.body = [node for node in tree.body if not isinstance(node, ast.ClassDef)
                         or node.name not in ("LearnedMotionPlanner", "ConventionalPredictivePlanner")]
            content = ast.dump(tree, include_attributes=False).encode()
        digest.update(str(path.relative_to(REPOSITORY_ROOT)).encode()+b"\0"+content+b"\0")
    return digest.hexdigest()


def validate_record(run_dir, spec, entry=None):
    summary = _validate_v1_record(run_dir, spec, entry)
    metadata = json.loads((Path(run_dir)/"metadata.json").read_text())
    expected = {name: spec[name] for name in ("initial_condition", "recovery_demonstration")}
    expected["requested_lift_height_m"] = .035 if spec["initial_condition"] == "raised" else .03
    mismatch = {name: [metadata.get(name), value] for name, value in expected.items()
                if metadata.get(name) != value}
    if mismatch:
        raise ValueError(f"{Path(run_dir).name}: V2 initial/recovery condition mismatch: {mismatch}")
    return summary


def model_artifacts(directory):
    files = {}
    for name in MODEL_DIRS:
        folder = Path(directory)/name
        paths = [folder/filename for filename in MODEL_FILES[name]]
        if not all(path.is_file() for path in paths):
            raise ValueError("Train and preserve both V2 motion and recovery models before evaluation")
        for path in paths:
            files[path.relative_to(directory).as_posix()] = _sha(path)
    return files


def _verify_models(directory, state):
    saved = state.get("models")
    if not saved or saved.get("files") != model_artifacts(directory):
        raise ValueError("V2 fitted model files changed or have not been trained")
    return saved["files"]


def freeze_execution(study_dir=DEFAULT_STUDY_DIR):
    directory = Path(study_dir).resolve()
    manifest, path = ensure_manifest(directory)
    state = _load_state(directory, path)
    files = _verify_models(directory, state)
    frozen = dict(version=2, split_manifest_sha256=_sha(path),
                  v1_training_manifest_sha256=manifest["v1_training_manifest_sha256"],
                  source_sha256=source_fingerprint(), model_files=files)
    freeze_path = directory/"execution_freeze.json"
    if freeze_path.exists():
        saved = json.loads(freeze_path.read_text())
        if {key: saved.get(key) for key in frozen} != frozen:
            raise ValueError("V2 source/model changed after execution freeze; preserve this study and start a new one")
        return saved
    if any(spec["trial_id"] in state["trials"] for spec in manifest["evaluations"]):
        raise ValueError("Cannot create a new freeze after evaluation attempts exist")
    _write_json(freeze_path, dict(frozen, frozen_at=_now()))
    return json.loads(freeze_path.read_text())


def _run_cell(spec, *, directory, state, runner, headless, code_hash, frozen=None):
    trial_id = spec["trial_id"]
    old = state["trials"].get(trial_id)
    models = frozen["model_files"] if frozen else None
    if old:
        if old.get("source_sha256") != code_hash or old.get("model_files") != models:
            raise ValueError(f"{trial_id}: source/model differs from recorded attempt")
        if old.get("status") == "running":
            raise ValueError(f"{trial_id}: interrupted attempt remains preserved; review before using a fresh study")
        if old.get("run_dir"):
            summary = validate_record(old["run_dir"], spec, old)
            if bool(summary.get("passed")) != bool(old.get("passed")):
                raise ValueError(f"{trial_id}: saved acceptance changed")
        return old
    entry = dict(trial_id=trial_id, parameters=dict(spec), status="running", passed=False,
                 started_at=_now(), source_sha256=code_hash, model_files=models)
    state["trials"][trial_id] = entry
    _write_json(directory/"study_state.json", state)
    kwargs = {key: value for key, value in spec.items() if key != "trial_id"}
    kwargs.update(headless=headless,
                  output_group=directory/("demonstrations" if spec["role"] == "demonstration" else "evaluation"),
                  model_path=directory/"model" if frozen else None,
                  recovery_model_path=directory/"recovery_model" if frozen else None)
    print(f"V2 {trial_id}", flush=True)
    try:
        run_dir, returned = runner(**kwargs)
        run_dir = Path(run_dir).resolve()
        entry["run_dir"] = str(run_dir)
        summary = validate_record(run_dir, spec)
        if bool(returned.get("passed")) != bool(summary.get("passed")):
            raise ValueError("Returned and saved acceptance disagree")
        entry.update(status="completed", passed=summary.get("passed") is True,
                     signals_sha256=_sha(run_dir/"signals.npz"), metadata_sha256=_sha(run_dir/"metadata.json"),
                     summary_sha256=_sha(run_dir/"pad_summary.json"))
        if frozen:
            actual_source = source_fingerprint()
            if actual_source != frozen["source_sha256"] or model_artifacts(directory) != frozen["model_files"]:
                raise ValueError("Source/model changed during serial evaluation")
            entry["actual_source_sha256"] = actual_source
    except Exception as exc:
        entry.update(status="error", passed=False, error=f"{type(exc).__name__}: {exc}")
    finally:
        entry["finished_at"] = _now()
        state["updated_at"] = _now()
        _write_json(directory/"study_state.json", state)
    return entry


def _evaluation_worker(kwargs, expected_source, expected_models, directory):
    """Spawn-safe native worker; only its trial runner writes the trial folder."""
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    output = {}
    try:
        before = source_fingerprint()
        output["actual_source_before_sha256"] = before
        if before != expected_source or model_artifacts(directory) != expected_models:
            raise ValueError("Worker source/model differs before execution")
        from primp_project.experiments.pad import run_trial
        run_dir, summary = run_trial(**kwargs)
        output.update(run_dir=str(Path(run_dir).resolve()), returned_summary=summary)
        after = source_fingerprint()
        output["actual_source_after_sha256"] = after
        if after != expected_source or model_artifacts(directory) != expected_models:
            raise ValueError("Worker source/model changed during execution")
    except Exception as exc:
        output["worker_error"] = f"{type(exc).__name__}: {exc}"
    return output


def _parallel_evaluate(manifest, directory, state, frozen, *, workers, headless):
    """Reserve and validate in the parent; preserve every attempt on interruption."""
    queue = []
    for spec in manifest["evaluations"]:
        old = state["trials"].get(spec["trial_id"])
        if old:
            if old.get("source_sha256") != frozen["source_sha256"] or old.get("model_files") != frozen["model_files"]:
                raise ValueError("Parallel resume source/model differs from recorded attempt")
            if old.get("status") == "running":
                raise ValueError(f"{spec['trial_id']}: interrupted attempt remains preserved; no automatic rerun")
            if old.get("run_dir"):
                summary = validate_record(old["run_dir"], spec, old)
                if bool(summary.get("passed")) != bool(old.get("passed")):
                    raise ValueError("Parallel resume acceptance changed")
        else:
            queue.append(spec)
    pending = {}
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as executor:
        while queue or pending:
            while queue and len(pending) < workers:
                freeze_execution(directory)
                spec = queue.pop(0)
                trial_id = spec["trial_id"]
                entry = dict(trial_id=trial_id, parameters=dict(spec), status="running", passed=False,
                             started_at=_now(), source_sha256=frozen["source_sha256"],
                             model_files=frozen["model_files"], execution="spawned_worker")
                state["trials"][trial_id] = entry
                _write_json(directory/"study_state.json", state)
                kwargs = {key: value for key, value in spec.items() if key != "trial_id"}
                kwargs.update(headless=headless, output_group=directory/"evaluation",
                              model_path=directory/"model", recovery_model_path=directory/"recovery_model")
                print(f"V2 submit {trial_id}", flush=True)
                future = executor.submit(_evaluation_worker, kwargs, frozen["source_sha256"], frozen["model_files"], directory)
                pending[future] = (spec, entry)
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                spec, entry = pending.pop(future)
                try:
                    freeze_execution(directory)
                    output = future.result()
                    if output.get("run_dir"):
                        entry["run_dir"] = output["run_dir"]
                    if output.get("worker_error"):
                        raise ValueError(output["worker_error"])
                    if (output.get("actual_source_before_sha256") != frozen["source_sha256"]
                            or output.get("actual_source_after_sha256") != frozen["source_sha256"]):
                        raise ValueError("Worker did not attest the frozen source before and after execution")
                    run = Path(output["run_dir"])
                    summary = validate_record(run, spec)
                    if bool(output["returned_summary"].get("passed")) != bool(summary.get("passed")):
                        raise ValueError("Worker acceptance differs from saved summary")
                    entry.update(status="completed", passed=summary.get("passed") is True,
                                 actual_source_sha256=output["actual_source_after_sha256"],
                                 signals_sha256=_sha(run/"signals.npz"), metadata_sha256=_sha(run/"metadata.json"),
                                 summary_sha256=_sha(run/"pad_summary.json"))
                except Exception as exc:
                    entry.update(status="error", passed=False, error=f"{type(exc).__name__}: {exc}")
                finally:
                    entry["finished_at"] = _now()
                    state["updated_at"] = _now()
                    _write_json(directory/"study_state.json", state)
                print(f"V2 {'PASS' if entry['passed'] else 'FAIL'} {spec['trial_id']}", flush=True)
    freeze_execution(directory)


def _fit_models(directory, manifest, state, *, model_fitter=None):
    if any(spec["trial_id"] in state["trials"] for spec in manifest["evaluations"]):
        raise ValueError("Evaluation has begun; V2 models cannot be refitted")
    old_runs = validate_v1_sources(json.loads((directory/"v1_training_manifest.json").read_text()))
    recovery_runs = []
    for spec in manifest["demonstrations"]:
        entry = state["trials"].get(spec["trial_id"], {})
        if not entry.get("passed") or not entry.get("run_dir"):
            raise ValueError("All nine accepted recovery demonstrations are required before training")
        if validate_record(entry["run_dir"], spec, entry).get("passed") is not True:
            raise ValueError("A recovery training recording no longer passes")
        recovery_runs.append(Path(entry["run_dir"]))
    if model_fitter is None:
        from primp_project.learning import fit_runs, fit_recovery_runs
        motion = fit_runs(old_runs+recovery_runs, split_manifest_path=directory/"split_manifest.json")
        motion.save(directory/"model")
        recovery = fit_recovery_runs(recovery_runs, split_manifest_path=directory/"split_manifest.json")
        recovery.save(directory/"recovery_model")
    else:
        model_fitter(old_runs, recovery_runs, directory)
    state["models"] = dict(trained_at=_now(), files=model_artifacts(directory),
                           motion_training_run_ids=[path.name for path in old_runs+recovery_runs],
                           recovery_training_run_ids=[path.name for path in recovery_runs])
    _write_json(directory/"study_state.json", state)


def run_study(stage, *, study_dir=DEFAULT_STUDY_DIR, v1_study_dir=DEFAULT_V1_STUDY_DIR,
              headless=True, trial_runner=None, model_fitter=None, workers=1):
    if stage not in ("declare", "demo", "train", "freeze", "evaluate", "all"):
        raise ValueError("Unknown V2 study stage")
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 4:
        raise ValueError("V2 workers must be an integer from one to four")
    if workers > 1 and (not headless or trial_runner is not None):
        raise ValueError("Parallel evaluation requires headless native workers; custom runners use workers=1")
    directory = Path(study_dir).resolve()
    manifest, manifest_path = ensure_manifest(directory, v1_study_dir=v1_study_dir)
    state = _load_state(directory, manifest_path)
    _write_json(directory/"study_state.json", state)
    if stage == "declare":
        return state
    if trial_runner is None and stage in ("demo", "evaluate", "all"):
        from primp_project.experiments.pad import run_trial
        trial_runner = run_trial
    if stage in ("demo", "all"):
        code_hash = source_fingerprint("demonstration")
        for spec in manifest["demonstrations"]:
            entry = _run_cell(spec, directory=directory, state=state, runner=trial_runner,
                              headless=headless, code_hash=code_hash)
            if not entry["passed"]:
                raise RuntimeError(f"Recovery demonstration {spec['trial_id']} failed; training stopped and attempt preserved")
    if stage in ("train", "all"):
        if stage == "all" and state.get("models"):
            _verify_models(directory, state)
        else:
            _fit_models(directory, manifest, state, model_fitter=model_fitter)
    if stage in ("freeze", "evaluate", "all"):
        frozen = freeze_execution(directory)
    if stage in ("evaluate", "all"):
        if workers > 1:
            _parallel_evaluate(manifest, directory, state, frozen, workers=workers, headless=headless)
        else:
            for spec in manifest["evaluations"]:
                # Fail before the next trial if code/model changed during a long run.
                current = freeze_execution(directory)
                _run_cell(spec, directory=directory, state=state, runner=trial_runner,
                          headless=headless, code_hash=current["source_sha256"], frozen=frozen)
        freeze_execution(directory)
        from primp_project.analysis.comparison_v2 import write_comparison
        write_comparison(directory)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project pad-study-v2", description=__doc__)
    parser.add_argument("stage", choices=("declare", "demo", "train", "freeze", "evaluate", "all"))
    parser.add_argument("--study-dir", type=Path, default=DEFAULT_STUDY_DIR)
    parser.add_argument("--v1-study-dir", type=Path, default=DEFAULT_V1_STUDY_DIR)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="One to four isolated native evaluation processes; default one")
    args = parser.parse_args(argv)
    try:
        state = run_study(args.stage, study_dir=args.study_dir, v1_study_dir=args.v1_study_dir,
                          headless=not args.render, workers=args.workers)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"V2 study stopped: {exc}\n")
    if args.stage in ("evaluate", "all"):
        return 0 if all(state["trials"].get(cell["trial_id"], {}).get("passed")
                        for cell in protocol()["evaluations"]) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
