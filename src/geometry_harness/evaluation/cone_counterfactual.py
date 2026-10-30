"""A zero-inference, post-hoc cone counterfactual for a failed Korgis Bottle.

The original frozen stage (1/2 technical native scenes when independently
validated) remains immutable. Verifies every source artifact and the original
Blender baseline before an independently labelled, opt-in cone replay.
No generated Python is executed; only the audited JSON builder can run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from geometry_harness.cli import blender_binary, sha256, source_sha, ShowcaseError
from geometry_harness.evaluation.local_staged_blender import (
    _read, _verified_source, StagedBlenderError,
)
from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.local_smoke import _build_and_reopen, _write, LocalSmokeError
from geometry_harness.providers.local import DEFAULT_MODEL
from geometry_harness.benchmark_smoke import EXPECTED_REV
from geometry_harness.strategies.bpy_subset import (
    compile_bpy_subset, UnsafeGeneratedCode,
)

EXPERIMENT = "G1_QWEN_BOTTLE_OPT_IN_CONE_POST_HOC_V1"
TARGET = "Bottle_seed0"
ORIGINAL_PASS = "CoffeeTable_seed0"
SOURCE_REL = f"tasks/{TARGET}/model-generated.py"


class CounterfactualError(ValueError):
    pass


def _preflight(stage: Path, baseline: Path) -> tuple[dict, bytes]:
    report_file = stage / "local-benchmark.json"
    report = _read(report_file)
    baseline_report = _read(baseline / "local-blender-validation.json")
    rows = report.get("result_rows")
    observed_tasks = report.get("task_ids")
    if (report.get("phase") != "GENERATION_ONLY_REQUIRES_LATER_BLENDER"
            or report.get("model") != DEFAULT_MODEL
            or report.get("dataset_revision") != EXPECTED_REV
            or report.get("runtime") != "korgis_loopback_only"
            or observed_tasks != [ORIGINAL_PASS, TARGET]
            or not isinstance(rows, list) or len(rows) != 2
            or [r.get("task_id") for r in rows] != observed_tasks
            or report.get("safe_source_pass") != 1
            or report.get("new_model_calls") != 2):
        raise CounterfactualError("Expected frozen two-task Korgis baseline unavailable")
    if (rows[0].get("safe_source") != "PASS"
            or rows[1].get("safe_source") != "FAIL"
            or rows[1].get("provider_status") != "COMPLETED"
            or rows[1].get("error_class") != "UnsafeGeneratedCode"):
        raise CounterfactualError("Bottle source not the original AST rejection")
    if (baseline_report.get("stage_report_sha256") != sha256(report_file)
            or baseline_report.get("runtime") != "NO_KORGIS_REQUESTS_BLENDER_ONLY"
            or baseline_report.get("model_calls") != 0
            or baseline_report.get("model") != DEFAULT_MODEL
            or baseline_report.get("attempted") != 2
            or baseline_report.get("native_pass") != 1):
        raise CounterfactualError("Baseline Blender validation does not match stage")
    checked = baseline_report.get("per_instance")
    if (not isinstance(checked, list) or len(checked) != 2
            or checked[0].get("task_id") != ORIGINAL_PASS
            or checked[0].get("native_scene") != "PASS"
            or checked[1].get("task_id") != TARGET
            or checked[1].get("native_scene") != "UNKNOWN"):
        raise CounterfactualError("Original Blender baseline is not 1/2")
    for row in rows:
        # This revalidates the source SHA+byte inventory for *both* tasks,
        # including the failing source whose parser status remains FAIL.
        _verified_source(stage, row)
    raw = stage / SOURCE_REL
    if raw.is_symlink() or not raw.is_file() or not raw.resolve().is_relative_to(stage):
        raise CounterfactualError("Bottle source not a regular staged file")
    data = raw.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise CounterfactualError("Invalid UTF-8 Bottle source") from None
    try:
        compile_bpy_subset(text, normalize_names=True)
    except UnsafeGeneratedCode as exc:
        if str(exc) != "Unsupported Blender operation":
            raise CounterfactualError("Original rejection differs: not the cone operation") from exc
    else:
        raise CounterfactualError("The original parser unexpectedly accepts Bottle")
    return report, data


def run(stage: Path, baseline: Path, output: Path, *, binary: str | None = None) -> dict:
    stage, baseline, output = (
        p.expanduser().resolve() for p in (stage, baseline, output)
    )
    if (output.exists() or output.is_relative_to(stage)
            or output.is_relative_to(baseline) or stage == baseline):
        raise CounterfactualError("New isolated output required, source/baseline immutable")
    report, raw = _preflight(stage, baseline)
    parsed = compile_bpy_subset(raw.decode("utf-8"), normalize_names=True, allow_cone=True)
    if not any(x["kind"] == "cone" for x in parsed["objects"]):
        raise CounterfactualError("Expected at least one explicitly permitted cone")
    blender = binary or blender_binary()
    if not blender:
        raise CounterfactualError("Blender missing; cannot score derived native scene")
    output.mkdir(parents=True, mode=0o700)
    task_dir = output / "tasks" / TARGET
    task_dir.mkdir(parents=True)
    (task_dir / "model-generated.py").write_bytes(raw)
    (task_dir / "model-generated.py").chmod(0o600)
    _write(task_dir / "scene-spec.json", parsed)

    status = "FAIL"
    error_type = None
    try:
        _build_and_reopen(blender, task_dir)
        status = "PASS"
    except (ShowcaseError, LocalSmokeError, ValueError, OSError) as exc:
        error_type = type(exc).__name__

    artifacts = []
    for p in sorted(task_dir.rglob("*")):
        if p.is_file() and not p.is_symlink():
            artifacts.append({
                "path": str(p.relative_to(output)), "sha256": sha256(p),
                "bytes": p.stat().st_size,
            })
    result = {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "status": "COUNTERFACTUAL_NATIVE_PASS" if status == "PASS" else "COUNTERFACTUAL_NATIVE_FAIL",
        "baseline_original_native_pass": 1,
        "baseline_original_attempted": 2,
        "baseline_bottle_safe_source": "FAIL",
        "baseline_bottle_native_scene": "UNKNOWN",
        "counterfactual_task": TARGET,
        "counterfactual_safe_source": "PASS",
        "counterfactual_native_scene": status,
        "counterfactual_error_class": error_type,
        "post_hoc_combined_native_pass": 2 if status == "PASS" else 1,
        "post_hoc_denominator": 2,
        "post_hoc_not_original_model_success": True,
        "new_model_calls": 0,
        "api_cost_usd": "0",
        "source_sha": source_sha(),
        "model": DEFAULT_MODEL,
        "dataset_revision": EXPECTED_REV,
        "source_stage_report_sha256": sha256(stage / "local-benchmark.json"),
        "source_blender_baseline_sha256": sha256(baseline / "local-blender-validation.json"),
        "source_model_output_sha256": sha256(stage / SOURCE_REL),
        "replayed_model_output_sha256": sha256(task_dir / "model-generated.py"),
        "cone_count": sum(x["kind"] == "cone" for x in parsed["objects"]),
        "generated_mesh_objects": len(parsed["objects"]),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "shape_similarity": "UNKNOWN_REFERENCE_SCORER_NOT_EXECUTED",
        "semantic_fidelity": "UNKNOWN_NOT_JUDGED",
        "warning": (
            "This is a post-hoc opt-in geometry vocabulary expansion. "
            "Original Qwen technical 1/2 remains unchanged. Native PASS validates "
            "reopen and dimensions, NOT geometric or prompt similarity."
        ),
    }
    _write(output / "cone-counterfactual.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.stage, args.baseline, args.out)
    except (CounterfactualError, StagedBlenderError, UnsafeGeneratedCode,
            ValueError, OSError, TypeError, KeyError, ShowcaseError) as exc:
        print(f"Post-hoc cone replay refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        key: result[key] for key in (
            "status", "baseline_original_native_pass", "post_hoc_combined_native_pass",
            "post_hoc_denominator", "cone_count", "generated_mesh_objects",
            "new_model_calls", "counterfactual_error_class",
        )
    }, indent=2))
    return 0 if result["counterfactual_native_scene"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
