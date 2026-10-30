"""Validate private Korgis-generated literal Blender scripts with Korgis stopped.

Reads a frozen output from `local_smoke --generate-only` after independently
checking its SHA manifest. No model/network requests are made. Never executes
model-generated Python: only the allowlisted AST and audited Blender builder.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

from geometry_harness.cli import blender_binary, sha256, source_sha, ShowcaseError
from geometry_harness.local_smoke import _build_and_reopen, _write
from geometry_harness.providers.local import DEFAULT_MODEL
from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode
from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.benchmark_smoke import EXPECTED_REV


class StagedBlenderError(ValueError):
    pass


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise StagedBlenderError("Missing immutable local stage")
    raw = path.read_bytes()
    if len(raw) > 3_000_000:
        raise StagedBlenderError("Oversized local stage")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise StagedBlenderError("Invalid local stage object")
    return obj


def _verified_source(stage: Path, row: dict) -> tuple[Path, Path] | None:
    task = row["task_id"]
    file_rows = row.get("files")
    if not isinstance(file_rows, list):
        raise StagedBlenderError("Missing SHA inventory")
    candidates = {}
    for item in file_rows:
        rel = item.get("path")
        if not isinstance(rel, str) or not rel.startswith(f"tasks/{task}/"):
            raise StagedBlenderError("Unsafe generated artifact path")
        path = (stage / rel)
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(stage)):
            raise StagedBlenderError("Missing or redirected generated artifact")
        if (path.stat().st_size != item.get("bytes")
                or sha256(path) != item.get("sha256")):
            raise StagedBlenderError("Generated artifact hash/bytes mismatch")
        candidates[rel] = path
    src = candidates.get(f"tasks/{task}/model-generated.py")
    spec = candidates.get(f"tasks/{task}/scene-spec.json")
    if row.get("provider_status") != "COMPLETED" or row.get("safe_source") != "PASS":
        if src is not None or spec is not None:
            # A failed compilation may legitimately preserve source; never
            # treat those partial files as validated.
            return None
        return None
    if not src or not spec:
        raise StagedBlenderError("Valid generated source/spec missing from SHA inventory")
    checked = compile_bpy_subset(src.read_text(encoding="utf-8"), normalize_names=True)
    if checked != _read(spec):
        raise StagedBlenderError("Stage AST-derived scene spec no longer matches generated code")
    return src, spec


def run(stage: Path, out: Path) -> dict:
    stage, out = stage.expanduser().resolve(), out.expanduser().resolve()
    if out.exists() or out == stage or out.is_relative_to(stage):
        raise StagedBlenderError("Use a new independent Blender output; never overwrite")
    report = _read(stage / "local-benchmark.json")
    if (report.get("phase") != "GENERATION_ONLY_REQUIRES_LATER_BLENDER"
            or report.get("dataset_revision") != EXPECTED_REV
            or report.get("model") != DEFAULT_MODEL
            or report.get("runtime") != "korgis_loopback_only"):
        raise StagedBlenderError("Stage is not the frozen local-only generation experiment")
    tasks = report.get("task_ids")
    rows = report.get("result_rows")
    if (not isinstance(tasks, list) or not isinstance(rows, list)
            or len(tasks) != len(rows) or len(tasks) == 0
            or len(set(tasks)) != len(tasks)
            or any(t not in EXPECTED_IDS for t in tasks)
            or [r.get("task_id") for r in rows] != tasks):
        raise StagedBlenderError("Stage has duplicated/missing/unfrozen task IDs")
    # Validate all provenance and sources *before* creating an output folder.
    trusted = {}
    for row in rows:
        trusted[row["task_id"]] = _verified_source(stage, row)
    binary = blender_binary()
    if not binary:
        raise StagedBlenderError("Blender executable is required")
    out.mkdir(parents=True, mode=0o700)
    results = []
    for task in tasks:
        record = {
            "task_id": task,
            "safe_source": "PASS" if trusted[task] else "FAIL_OR_UNKNOWN",
            "native_scene": "UNKNOWN" if trusted[task] is None else "FAIL",
            "error_class": None, "artifact_sha256": [],
        }
        if trusted[task] is not None:
            dst = out / "tasks" / task
            dst.mkdir(parents=True)
            src, spec = trusted[task]
            shutil.copyfile(src, dst / "model-generated.py")
            shutil.copyfile(spec, dst / "scene-spec.json")
            try:
                _build_and_reopen(binary, dst)
                record["native_scene"] = "PASS"
            except (OSError, ValueError, ShowcaseError) as exc:
                record["error_class"] = type(exc).__name__
            for path in sorted(dst.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    record["artifact_sha256"].append({
                        "path": str(path.relative_to(out)),
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                    })
        results.append(record)
    summary = {
        "schema_version": 1,
        "experiment": "G1_KORGIS_FROZEN_STAGED_BLENDER_VALIDATION",
        "source_sha": source_sha(),
        "stage_report_sha256": sha256(stage / "local-benchmark.json"),
        "stage_source_sha": report.get("source_sha"),
        "model": DEFAULT_MODEL,
        "runtime": "NO_KORGIS_REQUESTS_BLENDER_ONLY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "api_cost_usd": "0",
        "attempted": len(tasks),
        "native_pass": sum(x["native_scene"] == "PASS" for x in results),
        "per_instance": results,
        "semantic_quality": "UNKNOWN_NOT_VISUALLY_REVIEWED",
        "official_3dcodebench_score": None,
    }
    _write(out / "local-blender-validation.json", summary)
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        report = run(a.stage, a.out)
    except (StagedBlenderError, ShowcaseError, UnsafeGeneratedCode,
            ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Local Blender stage rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        k: report[k] for k in ("attempted","native_pass","model_calls","per_instance")
    }, indent=2))
    return 0 if report["native_pass"] == report["attempted"] else 1


if __name__ == "__main__":
    sys.exit(main())
