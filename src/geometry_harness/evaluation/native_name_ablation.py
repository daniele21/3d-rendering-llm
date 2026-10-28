"""Independent native Blender validation of three original name-only Luna candidates.

No paid inference; no execution of any model-generated Python. Re-audits original
six-task source bundle, independently recomputes the AST name-only transform
and uses only trusted Blender builder/inspector scripts. Derived evidence has
its own revision and NEVER overwrites the historical 2/6 benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from geometry_harness.cli import blender_binary, png_dimensions, ShowcaseError
from geometry_harness.evaluation.benchmark_evidence import audit
from geometry_harness.evaluation.rejection_postmortem import TASK_IDS, inspect
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.strategies.bpy_subset import compile_bpy_subset


class NativeAblationError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise NativeAblationError("Required private evidence missing or linked")
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run(bundle: Path, ablation: Path, output: Path) -> dict:
    bundle, ablation, output = (p.expanduser().resolve() for p in (bundle, ablation, output))
    if output.exists():
        raise NativeAblationError("New derived evidence path required; never overwrite")
    verified = audit(bundle)
    prior = _read(ablation / "postmortem.json")
    if (prior.get("source_model") != "gpt-6-luna"
            or prior.get("source_task_count") != 6
            or prior.get("source_native_pass") != 2
            or prior.get("source_run_status") != verified["original_run_status"]
            or prior.get("source_model_cost_usd_estimate") != verified["model_estimated_usd"]):
        raise NativeAblationError("Name ablation metadata does not match historical bundle")
    rows = prior.get("results")
    if not isinstance(rows, list) or [x.get("task_id") for x in rows] != list(TASK_IDS):
        raise NativeAblationError("Name-only ablation task identities altered")
    prepared = []
    # Full preflight before creating any new files or starting Blender.
    for row in rows:
        task = row["task_id"]
        original = bundle / "tasks" / task / "model-generated.py"
        candidate = ablation / f"{task}.alias-ablation.py"
        for target, root in ((original, bundle), (candidate, ablation)):
            if (target.is_symlink() or not target.is_file()
                    or not target.resolve().is_relative_to(root)):
                raise NativeAblationError("Untrusted original/candidate source path")
        if _sha(original) != row.get("original_source_sha256"):
            raise NativeAblationError("Original generated code changed")
        raw = original.read_text(encoding="utf-8")
        fresh, expected_source = inspect(raw)
        if (row.get("name_ablation_status") != "COMPILER_PASS_AFTER_NAME_ABLATION"
                or fresh["name_ablation_status"] != "COMPILER_PASS_AFTER_NAME_ABLATION"
                or expected_source is None
                or fresh["candidate_source_sha256"] != row.get("candidate_source_sha256")
                or candidate.read_text(encoding="utf-8") != expected_source
                or _sha(candidate) != row.get("candidate_source_sha256")):
            raise NativeAblationError("Candidate differs from deterministic name-only AST transformation")
        safe_spec = compile_bpy_subset(expected_source)
        prepared.append((task, safe_spec, _sha(original), _sha(candidate)))
    binary = blender_binary()
    if not binary:
        raise NativeAblationError("Real Blender required; no synthetic PASS")
    output.mkdir(parents=True, mode=0o700)
    results = []
    for task, spec, original_hash, candidate_hash in prepared:
        target = output / "tasks" / task
        target.mkdir(parents=True)
        artifacts = target / "native"
        artifacts.mkdir()
        record = {
            "task_id": task,
            "original_model_sha256": original_hash,
            "name_only_candidate_sha256": candidate_hash,
            "safe_compiler": "PASS",
            "native_scene": "UNKNOWN",
            "native_scene_checks": "NOT_RUN",
            "semantic_quality": "UNKNOWN_NOT_JUDGED",
            "shape_chamfer": None,
            "model_calls": 0, "new_model_token_cost_usd": "0",
            "error_class": None, "artifacts": [],
        }
        results.append(record)
        _write(target / "safe-scene-spec.json", spec)
        try:
            _safe_run([binary, "-b", "--factory-startup", "--disable-autoexec",
                       "--python-exit-code", "14", "--python", str(BUILDER),
                       "--", "--spec", str(target / "safe-scene-spec.json"),
                       "--out", str(artifacts)], target / "build.log", limit=120)
            scene = artifacts / "scene.blend"
            if not scene.is_file() or scene.read_bytes()[:7] != b"BLENDER":
                raise NativeAblationError("No valid Blender scene header")
            _safe_run([binary, "-b", str(scene), "--disable-autoexec",
                       "--python-exit-code", "14", "--python", str(INSPECT), "--",
                       "--spec", str(target / "safe-scene-spec.json"),
                       "--output", str(target / "reopened-geometry.json")],
                      target / "inspect.log", limit=120)
            measured = _read(target / "reopened-geometry.json")
            if not measured.get("passed") or len(measured.get("mesh_objects", [])) != len(spec["objects"]):
                raise NativeAblationError("Independent saved-scene re-open check failed")
            width, height = png_dimensions(artifacts / "preview.png")
            if width <= 0 or height <= 0:
                raise NativeAblationError("No verified preview dimensions")
            record["native_scene"] = "PASS"
            record["native_scene_checks"] = "PASS"
            record["mesh_count"] = len(spec["objects"])
            record["preview_dimensions_px"] = [width, height]
        except (ShowcaseError, NativeAblationError, OSError, ValueError, TypeError, KeyError) as exc:
            record["native_scene"] = "FAIL"
            record["native_scene_checks"] = "FAIL"
            record["error_class"] = type(exc).__name__
        # Enumerate only newly created native artifacts; do not copy any
        # original raw model Python, keys, scorer-private references or prompts.
        for file in sorted(target.rglob("*")):
            if file.is_file() and file.name != "result.json" and not file.is_symlink():
                record["artifacts"].append({"path": str(file.relative_to(output)),
                                            "sha256": _sha(file), "bytes": file.stat().st_size})
        _write(target / "result.json", record)
    derived_passes = sum(r["native_scene"] == "PASS" for r in results)
    report = {
        "schema_version": 1,
        "experiment": "luna_original_name_only_native_ablation",
        "historical_run_status": verified["original_run_status"],
        "historical_native_scene_pass": 2,
        "historical_task_count": 6,
        "historical_model_cost_usd_estimate": verified["model_estimated_usd"],
        "tested_derived_tasks": 3,
        "derived_native_pass": derived_passes,
        "derived_native_fail": 3 - derived_passes,
        "counterfactual_native_scene_pass_total": 2 + derived_passes,
        "counterfactual_denominator": 6,
        "quality_status": "UNKNOWN_NOT_SHAPE_SCORED",
        "original_run_reclassified": False,
        "new_model_calls": 0,
        "new_model_token_cost_usd": "0",
        "result_rows": results,
        "warning": "Counterfactual on historical generated code; not an original run or an upstream-comparable quality score.",
    }
    _write(output / "native-name-ablation.json", report)
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--ablation", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = run(args.bundle, args.ablation, args.out)
    except (NativeAblationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Native name ablation rejected: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in (
        "historical_native_scene_pass", "derived_native_pass",
        "derived_native_fail", "counterfactual_native_scene_pass_total",
        "counterfactual_denominator", "quality_status", "new_model_calls")}))
    return 0 if result["derived_native_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
