"""Re-score a separate 5/6 Luna counterfactual using pinned original references.

Requires private operator-held original, independently measured native ablation,
and pre-scored baseline GLBs. Runs only audited Blender exporter and pinned
external scorer; never executes generated source or calls a model. The original
2/6 run and its shape stage are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

from geometry_harness.cli import blender_binary, png_dimensions
from geometry_harness.evaluation.benchmark_evidence import audit, EXPECTED_IDS
from geometry_harness.evaluation.rejection_postmortem import TASK_IDS, inspect
from geometry_harness.evaluation.upstream_shape_adapter import (
    EXPORT, MODEL, UPSTREAM_COMMIT, ShapeGateError, score,
)
from geometry_harness.g1 import _safe_run
from geometry_harness.strategies.bpy_subset import compile_bpy_subset


ORIGINAL_VALID = ("CoffeeTable_seed0", "Balloon_seed0")
EXPERIMENT = "luna_name_only_five_scene_counterfactual_v1"


def _read(path: Path, root: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ShapeGateError("Missing or unsafe private evidence file")
    return json.loads(path.read_text(encoding="utf-8"))


def _file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ShapeGateError("Invalid artifact path")
    target = root / relative
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
        raise ShapeGateError("Missing or linked private artifact")
    return target


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_file(root: Path, meta: dict) -> Path:
    path = _file(root, meta["path"])
    if _sha(path) != meta["sha256"] or path.stat().st_size != meta["bytes"]:
        raise ShapeGateError("Artifact SHA/size mismatch")
    return path


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _preflight(original: Path, baseline: Path, derived: Path):
    historical = audit(original)
    if historical["native_pass"] != 2 or historical["original_run_status"] != "INCOMPLETE":
        raise ShapeGateError("Unexpected historical baseline, must remain 2/6 INCOMPLETE")
    base = _read(baseline / "scorer-staging.json", baseline)
    provenance = _read(baseline / "shape-scorer-provenance.json", baseline)
    if (base.get("model") != MODEL or base.get("upstream_commit") != UPSTREAM_COMMIT
            or base.get("source_sha") != historical["source_sha"]
            or base.get("source_cost_estimated_usd") != historical["model_estimated_usd"]
            or base.get("dataset_revision") != historical["dataset_revision"]
            or base.get("native_pass") != 2
            or base.get("expected_tasks") != list(EXPECTED_IDS)
            or provenance.get("scorer_status") != "UPSTREAM_SHAPE_CHAMFER_EXECUTED"
            or provenance.get("n_scored") != 2
            or provenance.get("upstream_commit") != UPSTREAM_COMMIT
            or provenance.get("dataset_revision") != historical["dataset_revision"]):
        raise ShapeGateError("Original pinned shape stage does not match audited baseline")
    by_task = {x["task_id"]: x for x in base["tasks"]}
    if set(by_task) != set(EXPECTED_IDS) or len(base["tasks"]) != 6:
        raise ShapeGateError("Original six-task shape stage incomplete")
    original_files = {}
    for task in ORIGINAL_VALID:
        rec = by_task[task]
        if rec.get("native_scene") != "PASS" or not isinstance(rec.get("generated_glb"), dict):
            raise ShapeGateError("Historical native PASS GLB missing")
        expected = f"results/text_to_3D/{MODEL}/{task}/glb/{task}.glb"
        if rec["generated_glb"].get("path") != expected:
            raise ShapeGateError("Unrecognized original GLB path")
        path = _verify_file(baseline, rec["generated_glb"])
        if path.read_bytes()[:4] != b"glTF":
            raise ShapeGateError("Original GLB header invalid")
        original_files[task] = path
    old_metrics = _read(baseline / "results" / "text_to_3D" / MODEL /
                        "_metrics" / "shape_chamfer.json", baseline)
    if old_metrics.get("n_instances") != 6 or old_metrics.get("n_ok") != 2:
        raise ShapeGateError("Original scorer metric denominator changed")
    report = _read(derived / "native-name-ablation.json", derived)
    if (report.get("experiment") != "luna_original_name_only_native_ablation"
            or report.get("historical_native_scene_pass") != 2
            or report.get("derived_native_pass") != 3
            or report.get("counterfactual_native_scene_pass_total") != 5
            or report.get("counterfactual_denominator") != 6
            or report.get("historical_run_status") != historical["original_run_status"]
            or report.get("historical_model_cost_usd_estimate") != historical["model_estimated_usd"]
            or report.get("new_model_calls") != 0
            or report.get("original_run_reclassified") is not False):
        raise ShapeGateError("Derived native provenance is not the audited 3/3 ablation")
    rows = report.get("result_rows")
    if not isinstance(rows, list) or len(rows) != 3 or {x.get("task_id") for x in rows} != set(TASK_IDS):
        raise ShapeGateError("Expected exactly three named derived native scenes")
    derived_files = {}
    for record in rows:
        task = record["task_id"]
        if (record.get("native_scene") != "PASS" or record.get("native_scene_checks") != "PASS"
                or record.get("safe_compiler") != "PASS" or record.get("model_calls") != 0):
            raise ShapeGateError("Derived task has not independently passed native checks")
        entries = record.get("artifacts")
        if not isinstance(entries, list):
            raise ShapeGateError("Missing derived artifact hashes")
        seen = {}
        for item in entries:
            if item["path"] in seen:
                raise ShapeGateError("Duplicate derived file record")
            seen[item["path"]] = _verify_file(derived, item)
        folder = f"tasks/{task}"
        required = {f"{folder}/safe-scene-spec.json", f"{folder}/reopened-geometry.json",
                    f"{folder}/native/scene.blend", f"{folder}/native/preview.png"}
        if not required.issubset(seen):
            raise ShapeGateError("Derived native scene missing audited files")
        scene = seen[f"{folder}/native/scene.blend"]
        if scene.read_bytes()[:7] != b"BLENDER":
            raise ShapeGateError("Derived Blender scene header invalid")
        png_dimensions(seen[f"{folder}/native/preview.png"])
        measured = _read(seen[f"{folder}/reopened-geometry.json"], derived)
        spec = _read(seen[f"{folder}/safe-scene-spec.json"], derived)
        raw = _file(original, f"tasks/{task}/model-generated.py")
        if record.get("original_model_sha256") != _sha(raw):
            raise ShapeGateError("Derived scene original model hash mismatch")
        finding, candidate = inspect(raw.read_text(encoding="utf-8"))
        if (finding.get("name_ablation_status") != "COMPILER_PASS_AFTER_NAME_ABLATION"
                or candidate is None or record.get("name_only_candidate_sha256") !=
                hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                or spec != compile_bpy_subset(candidate)):
            raise ShapeGateError("Derived scene is not a deterministic name-only transform")
        names = [obj["name"] for obj in spec["objects"]]
        if (measured.get("passed") is not True or
                {x["name"] for x in measured.get("mesh_objects", [])} != set(names) or
                len(measured["mesh_objects"]) != len(names)):
            raise ShapeGateError("Derived reopened Blender geometry not verified")
        derived_files[task] = (scene, names)
    return historical, provenance, old_metrics, original_files, derived_files


def _paired_metrics(metrics: dict, original_metrics: dict) -> bool:
    old = {x["instance"]: x for x in original_metrics["per_instance"]}
    new = {x["instance"]: x for x in metrics["per_instance"]}
    if set(new) != set(EXPECTED_IDS) or set(old) != set(EXPECTED_IDS):
        return False
    for task in ORIGINAL_VALID:
        if old[task].get("status") != "OK" or new[task].get("status") != "OK":
            return False
        for field in ("cd", "cd_yawmin"):
            a, b = old[task].get(field), new[task].get(field)
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                return False
            if not math.isfinite(a) or not math.isfinite(b) or not math.isclose(a, b, abs_tol=1e-6, rel_tol=0):
                return False
    return (all(new[t].get("status") == "OK" for t in TASK_IDS)
            and new["BrainCoral_seed0"].get("status") != "OK"
            and metrics.get("n_instances") == 6 and metrics.get("n_ok") == 5)


def run(original: Path, baseline: Path, derived: Path, output: Path, *,
        upstream: Path | None = None, refs: Path | None = None,
        binary: str | None = None) -> dict:
    original, baseline, derived, output = (x.expanduser().resolve() for x in (original, baseline, derived, output))
    if output.exists():
        raise ShapeGateError("New evidence directory required: never overwrite originals")
    if (upstream is None) != (refs is None):
        raise ShapeGateError("Pinned scorer and scorer-private references must be provided together")
    historical, provenance, old_metrics, originals, converted = _preflight(original, baseline, derived)
    executable = binary or blender_binary()
    if not executable:
        raise ShapeGateError("Real Blender required for the three trusted GLB exports")
    base = output / "results" / "text_to_3D" / MODEL
    output.mkdir(parents=True, mode=0o700)
    rows = []
    for task in EXPECTED_IDS:
        target = base / task
        target.mkdir(parents=True)
        row = {"task_id": task, "native_scene": "FAIL",
               "generated_glb": None, "shape_status": "UNKNOWN_NOT_SHAPE_SCORED",
               "source_cohort": "original" if task in ORIGINAL_VALID else
                                "name_only_derived" if task in TASK_IDS else "original_unrecovered"}
        if task in originals or task in converted:
            glb = target / "glb" / f"{task}.glb"
            glb.parent.mkdir()
            if task in originals:
                shutil.copyfile(originals[task], glb)
            else:
                scene, names = converted[task]
                expected = target / "expected.json"
                _write(expected, {"object_ids": names})
                _safe_run([executable, "-b", str(scene), "--disable-autoexec",
                           "--python-exit-code", "14", "--python", str(EXPORT),
                           "--", "--out", str(glb), "--expected", str(expected)],
                          target / "export.log", limit=120)
            if not glb.is_file() or glb.read_bytes()[:4] != b"glTF":
                raise ShapeGateError("Audited Blender exporter did not produce a valid GLB")
            row["native_scene"] = "PASS"
            row["generated_glb"] = {"path": str(glb.relative_to(output)),
                                    "sha256": _sha(glb), "bytes": glb.stat().st_size}
            row["shape_status"] = "READY_FOR_ISOLATED_REFERENCE_SCORER"
        rows.append(row)
    staging = {"schema_version": 1, "experiment": EXPERIMENT, "model": MODEL,
               "upstream_commit": UPSTREAM_COMMIT,
               "source_sha": historical["source_sha"],
               "dataset_revision": historical["dataset_revision"],
               "original_run_status": historical["original_run_status"],
               "original_native_pass": 2, "native_pass": 5,
               "source_cost_estimated_usd": historical["model_estimated_usd"],
               "expected_tasks": list(EXPECTED_IDS), "tasks": rows,
               "scoring_status": "NOT_RUN",
               "quality_status": "UNKNOWN_NOT_SHAPE_SCORED",
               "comparability": "COUNTERFACTUAL_NONCOMPARABLE_TO_OFFICIAL_3DCODEBENCH",
               "model_calls": 0, "new_api_cost_estimate_usd": "0"}
    _write(output / "scorer-staging.json", staging)
    if upstream is None:
        return staging
    score(output, upstream, refs)
    latest = _read(output / "shape-scorer-provenance.json", output)
    metric_path = base / "_metrics" / "shape_chamfer.json"
    metrics = _read(metric_path, output)
    consistent = _paired_metrics(metrics, old_metrics)
    references_match = (
        latest.get("reference_glb_sha256") == provenance.get("reference_glb_sha256")
        and latest.get("upstream_shape_scorer_sha256") == provenance.get("upstream_shape_scorer_sha256")
        and latest.get("upstream_commit") == provenance.get("upstream_commit"))
    outcome = {"schema_version": 1, "experiment": EXPERIMENT,
               "original_native_pass": 2, "counterfactual_native_pass": 5,
               "model_calls": 0, "new_api_cost_estimate_usd": "0",
               "original_run_reclassified": False,
               "scorer_same_references_and_revision": references_match,
               "original_pair_score_reproducible": consistent,
               "shape_status": "SCORED_PINNED_COUNTERFACTUAL" if consistent and references_match
                               else "UNKNOWN_UNPAIRED_OR_PROVENANCE_MISMATCH",
               "n_scored": metrics.get("n_ok") if consistent and references_match else None,
               "conditional_cd": metrics.get("cd", {}).get("conditional_mean") if consistent and references_match else None,
               "penalized_cd": metrics.get("cd", {}).get("penalized_mean") if consistent and references_match else None,
               "per_instance": metrics.get("per_instance") if consistent and references_match else None,
               "semantic_quality": "UNKNOWN_NOT_SEMANTICALLY_JUDGED",
               "warning": "Counterfactual restricted AST/Blender 5.2; CD is not an official 3DCodeBench quality score."}
    _write(output / "counterfactual-shape-results.json", outcome)
    if not consistent or not references_match:
        raise ShapeGateError("Scorer finished but paired baseline or frozen references do not match: no shape claim")
    return outcome


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--baseline-stage", type=Path, required=True)
    p.add_argument("--derived", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--upstream", type=Path)
    p.add_argument("--refs", type=Path)
    a = p.parse_args(argv)
    try:
        result = run(a.original, a.baseline_stage, a.derived, a.out,
                     upstream=a.upstream, refs=a.refs)
    except (ShapeGateError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Counterfactual shape scoring rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
