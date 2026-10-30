"""Private, no-egress Ollama vs Luna six-task smoke using frozen public prompts.

This is an experimental run, not official 3DCodeBench. Never executes
model-authored Python. Runs the same restricted AST and trusted Blender
builder as the Luna branch, with no model keys and no cloud fallback.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

from geometry_harness.benchmark_smoke import CONTRACT, EXPECTED_REV
from geometry_harness.cli import ShowcaseError, blender_binary, png_dimensions, sha256, source_sha
from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.providers.compatible import ProviderError
from geometry_harness.providers.local import (
    DEFAULT_MODEL, LocalProviderError, OllamaLocalCodeProvider,
)
from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode

PUBLIC_NAMES = ("prompt_description.txt", "prompt_instruction.txt")


class LocalSmokeError(ValueError):
    pass


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _load_prompts(public_root: Path, suite_path: Path,
                  task_ids: tuple[str, ...]) -> dict[str, str]:
    if public_root.is_symlink() or not public_root.is_dir():
        raise LocalSmokeError("Public prompt root missing or linked")
    if suite_path.is_symlink() or not suite_path.is_file():
        raise LocalSmokeError("Frozen six-task suite missing or linked")
    suite_bytes = suite_path.read_bytes()
    if len(suite_bytes) > 3_000_000:
        raise LocalSmokeError("Oversized frozen suite")
    suite = json.loads(suite_bytes)
    if (suite.get("benchmark") != "3DCodeBench"
            or suite.get("schema_version") != 1
            or suite.get("dataset_revision") != EXPECTED_REV
            or suite.get("reference_access") != "scorer_only"
            or suite.get("tiers", {}).get("smoke") != list(EXPECTED_IDS)):
        raise LocalSmokeError("Unexpected frozen original six-task suite")
    manifest_path = public_root / "staging-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise LocalSmokeError("Missing public generator prompt manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("task_ids") != list(EXPECTED_IDS)
            or manifest.get("dataset_revision") != EXPECTED_REV
            or manifest.get("source_suite_sha256") != hashlib.sha256(suite_bytes).hexdigest()
            or manifest.get("reference_access") != "NONE_in_generator_workspace"):
        raise LocalSmokeError("Private prompt staging not pinned to frozen suite")
    inventory = {x["task_id"]: x for x in suite["tasks"]}
    if len(inventory) != len(suite["tasks"]):
        raise LocalSmokeError("Duplicate task inventory")
    prompts = {}
    for task in task_ids:
        if task not in inventory:
            raise LocalSmokeError("Unknown local smoke task")
        folder = public_root / task
        if folder.is_symlink() or not folder.is_dir() or not folder.resolve().is_relative_to(public_root.resolve()):
            raise LocalSmokeError("Unsafe public prompt folder")
        values = []
        for name, hash_field in zip(PUBLIC_NAMES,
                                    ("prompt_description_sha256", "prompt_instruction_sha256")):
            path = folder / name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(public_root.resolve()):
                raise LocalSmokeError("Unsafe public task prompt file")
            content = path.read_bytes()
            if not 0 < len(content) <= 128 * 1024 or b"\x00" in content:
                raise LocalSmokeError("Invalid prompt bytes")
            if hashlib.sha256(content).hexdigest() != inventory[task][hash_field]:
                raise LocalSmokeError("Public prompt hash mismatch")
            values.append(content.decode("utf-8"))
        prompt = (CONTRACT + "\n\nOBJECT DESCRIPTION:\n" + values[0]
                  + "\n\nOBJECT INSTRUCTIONS:\n" + values[1])
        if len(prompt) > 12000:
            raise LocalSmokeError("Combined public task prompt exceeds bound")
        prompts[task] = prompt
    return prompts


def run(output: Path, public_root: Path, suite: Path, *,
        task_ids: tuple[str, ...] = EXPECTED_IDS,
        provider: OllamaLocalCodeProvider | None = None) -> dict:
    output, public_root, suite = (x.expanduser().resolve()
                                  for x in (output, public_root, suite))
    if output.exists():
        raise LocalSmokeError("New immutable output required; no overwrites")
    if not task_ids or len(set(task_ids)) != len(task_ids) or any(x not in EXPECTED_IDS for x in task_ids):
        raise LocalSmokeError("Choose unique frozen six-task IDs")
    # Validate all requested inputs and all prompt hashes before any request.
    prompts = _load_prompts(public_root, suite, task_ids)
    binary = blender_binary()
    if not binary:
        raise LocalSmokeError("Blender required for local model benchmark")
    engine = provider or OllamaLocalCodeProvider()
    output.mkdir(parents=True, mode=0o700)
    rows = []
    for task in task_ids:
        folder = output / "tasks" / task
        folder.mkdir(parents=True)
        record = {
            "task_id": task,
            "model": engine.model,
            "provider_status": "NOT_RUN",
            "safe_source": "UNKNOWN",
            "native_scene": "UNKNOWN",
            "semantic_quality": "UNKNOWN_NOT_VISUALLY_REVIEWED",
            "error_class": None, "model_calls": 0,
            "input_tokens": None, "output_tokens": None,
            "llm_elapsed_seconds": None,
            "telemetry": None,
            "normalized_mesh_names": None,
            "files": [],
        }
        started = time.monotonic()
        try:
            record["model_calls"] = 1
            response = engine.generate(prompts[task])
            record["llm_elapsed_seconds"] = round(time.monotonic() - started, 4)
            record["provider_status"] = "COMPLETED"
            record["input_tokens"] = response.input_tokens
            record["output_tokens"] = response.output_tokens
            if getattr(engine, "last_telemetry", None) is not None:
                record["telemetry"] = asdict(engine.last_telemetry)
            code_file = folder / "model-generated.py"
            code_file.write_text(response.code, encoding="utf-8")
            code_file.chmod(0o600)
            spec = compile_bpy_subset(response.code, normalize_names=True)
            record["safe_source"] = "PASS"
            record["normalized_mesh_names"] = spec["name_normalization"]["changes"]
            _write(folder / "scene-spec.json", spec)
            _safe_run([
                binary, "-b", "--factory-startup", "--disable-autoexec",
                "--python-exit-code", "14", "--python", str(BUILDER),
                "--", "--spec", str(folder / "scene-spec.json"), "--out", str(folder),
            ], folder / "build.log", limit=180)
            _safe_run([
                binary, "-b", str(folder / "scene.blend"), "--disable-autoexec",
                "--python-exit-code", "14", "--python", str(INSPECT),
                "--", "--spec", str(folder / "scene-spec.json"),
                "--output", str(folder / "geometry.json"),
            ], folder / "inspect.log", limit=180)
            geometry = json.loads((folder / "geometry.json").read_text(encoding="utf-8"))
            if geometry.get("passed") is not True:
                raise LocalSmokeError("Independent native Blender geometry failed")
            png_dimensions(folder / "preview.png")
            record["native_scene"] = "PASS"
        except (LocalProviderError, ProviderError, UnsafeGeneratedCode,
                LocalSmokeError, ShowcaseError, ValueError, TypeError, OSError) as exc:
            record["error_class"] = type(exc).__name__
            if record["provider_status"] == "NOT_RUN":
                record["provider_status"] = "FAILED"
            elif record["safe_source"] == "UNKNOWN":
                record["safe_source"] = "FAIL"
            else:
                record["native_scene"] = "FAIL"
        finally:
            record["llm_elapsed_seconds"] = (
                record["llm_elapsed_seconds"]
                if record["llm_elapsed_seconds"] is not None
                else round(time.monotonic() - started, 4)
            )
        for item in sorted(folder.rglob("*")):
            if item.is_file() and not item.is_symlink():
                record["files"].append({
                    "path": str(item.relative_to(output)),
                    "sha256": sha256(item), "bytes": item.stat().st_size,
                })
        _write(folder / "result.json", record)
        rows.append(record)
    summary = {
        "schema_version": 1, "experiment": "G1_LOCAL_QWEN_VS_LUNA_RESTRICTED_SMOKE",
        "source_sha": source_sha(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": "ollama_loopback_only",
        "model": engine.model,
        "model_params": {
            "context_tokens": engine.context_tokens,
            "max_output_tokens": engine.max_output_tokens,
            "temperature": engine.temperature, "seed": engine.seed,
            "keep_alive": 0,
        },
        "platform": platform.platform(), "dataset_revision": EXPECTED_REV,
        "task_ids": list(task_ids), "attempted": len(rows),
        "native_pass": sum(x["native_scene"] == "PASS" for x in rows),
        "safe_source_pass": sum(x["safe_source"] == "PASS" for x in rows),
        "new_model_calls": sum(x["model_calls"] for x in rows),
        "api_cost_usd": "0", "hardware_electricity_cost": "UNKNOWN",
        "official_benchmark_score": None,
        "semantic_quality": "UNKNOWN_NOT_VISUALLY_REVIEWED",
        "comparison": "COMPATIBLE_PROMPTS_AND_SAFE_COMPILER_BUT_SEPARATE_LOCAL_EXPERIMENT",
        "result_rows": rows,
    }
    _write(output / "local-benchmark.json", summary)
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public-root", type=Path, required=True)
    p.add_argument("--suite", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--task", action="append", choices=EXPECTED_IDS,
                   help="Repeat to select 1-6 tasks; default is all six")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--num-ctx", type=int, default=8192)
    p.add_argument("--num-predict", type=int, default=4096)
    args = p.parse_args(argv)
    try:
        tasks = tuple(args.task) if args.task else EXPECTED_IDS
        provider = OllamaLocalCodeProvider(
            model=args.model, context_tokens=args.num_ctx,
            max_output_tokens=args.num_predict,
        )
        report = run(args.out, args.public_root, args.suite,
                     task_ids=tasks, provider=provider)
    except (LocalSmokeError, LocalProviderError, ValueError, OSError) as exc:
        print(f"Local smoke rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        key: report[key]
        for key in ("model", "task_ids", "attempted", "native_pass",
                    "safe_source_pass", "new_model_calls", "api_cost_usd")
    }, indent=2))
    return 0 if report["native_pass"] == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
