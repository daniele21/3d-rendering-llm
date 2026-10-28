"""Six task, explicitly paid, Luna-only *internal* 3DCodeBench smoke.

Source: pinned public prompt texts. Reference factories never enter this process.
This is NOT the upstream image/Chamfer/VLM scorer. Native executable scene rate
is objective, prompt fidelity and ground-truth similarity are UNKNOWN.

Model-generated Python is NEVER executed: strict AST literal subset -> vetted
scene spec -> repository-owned Blender builder and separate inspector.
Every provider call, including rejected outputs, enters an append-only cost ledger.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

from geometry_harness.cli import blender_binary, png_dimensions, sha256, source_sha, ShowcaseError
from geometry_harness.costs.ledger import default_ledger_path, load_events, reconcile
from geometry_harness.costs.pricing import RATE_CARD
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.providers.compatible import OpenAICompatibleCodeProvider, ProviderError
from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode

MODEL = "gpt-6-luna"  # Published API identifier; 6.1-luna is not documented.
EXPECTED_REV = "b70b4ee54b93fab76596da5809f3e71c617fa5c2"
MAX_CALLS = 6
MAX_OUTPUT_TOKENS = 2048
MAX_MODEL_USD = Decimal("0.05")
CONTRACT = (
    "Write Blender 5 bpy Python for the public description/instructions below. "
    "This experimental runner can ONLY safely interpret straight-line literal "
    "bpy.ops.mesh.primitive_cube_add(size=..., location=(x,y,z)), "
    "bpy.ops.mesh.primitive_cylinder_add(radius=...,depth=...,vertices=...,location=(x,y,z)) "
    "and bpy.ops.mesh.primitive_uv_sphere_add(radius=...,segments=...,ring_count=...,location=(x,y,z)). "
    "After each primitive use 'obj = bpy.context.object', 'obj.name = \"partname\"', "
    "and optional literal obj.dimensions/location/scale = (x,y,z). "
    "No loops, helper variables, functions, computed expressions, other imports, "
    "materials or external assets. Max 48 uniquely named objects. "
    "Return only Python code. If the target is too complex, provide the best "
    "approximation you can express in the allowed primitives. "
    "Do not claim to have rendered anything."
)


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cost(root: Path):
    ledger = root / "costs" / "events.jsonl"
    if not ledger.is_file():
        return None
    report = reconcile(load_events(ledger))
    _write(root / "cost-summary.json", report)
    return report


def conservative_max_usd(prompt: str) -> Decimal:
    # Upper bound by UTF-8 bytes + generous system/protocol token overhead,
    # not a model-averaged "4 chars/token" assumption. Also bound output.
    upper_input = len(prompt.encode("utf-8")) + 8192
    input_rate, read_rate, write_30m, write_12h, output_rate = RATE_CARD[MODEL]["short"]
    # Upper-bound the most expensive possible input class, not only uncached.
    input_rate = max(map(Decimal, (input_rate, read_rate, write_30m, write_12h)))
    return (Decimal(upper_input) * input_rate +
            Decimal(MAX_OUTPUT_TOKENS) * Decimal(output_rate)) / Decimal(1_000_000)


def run(output: Path, public_root: Path, suite: Path) -> dict:
    output, public_root, suite = output.resolve(), public_root.resolve(), suite.resolve()
    if output.exists():
        raise ShowcaseError("Benchmark output directory already exists")
    if not public_root.is_dir() or not suite.is_file():
        raise ShowcaseError("Pinned public prompt folder and suite are required")
    benchmark = json.loads(suite.read_text(encoding="utf-8"))
    if benchmark.get("dataset_revision") != EXPECTED_REV or benchmark.get("reference_access") != "scorer_only":
        raise ShowcaseError("Wrong dataset or unsafe reference-access contract")
    ids = benchmark.get("tiers", {}).get("smoke")
    if not isinstance(ids, list) or len(ids) != MAX_CALLS or len(set(ids)) != MAX_CALLS:
        raise ShowcaseError("Expected exactly six frozen public task IDs")
    staged_manifest = json.loads((public_root / "staging-manifest.json").read_text())
    if staged_manifest.get("task_ids") != ids or staged_manifest.get("dataset_revision") != EXPECTED_REV:
        raise ShowcaseError("Public prompts do not match the pinned smoke suite")
    if os.environ.get("GEOMETRY_ALLOW_REMOTE_INFERENCE") != "1" or os.environ.get("GEOMETRY_CLOUD_MODEL") != MODEL:
        raise ShowcaseError("Paid six-task benchmark requires explicit Luna-only opt-in")
    ledger = default_ledger_path()
    if not ledger.is_relative_to(output) or ledger.name != "events.jsonl":
        raise ShowcaseError("Benchmark ledger must be inside the immutable evidence folder")
    if not os.environ.get("GEOMETRY_CLOUD_API_KEY"):
        raise ShowcaseError("Missing key in restricted experiment environment")
    outdir = output / "tasks"
    outdir.mkdir(parents=True)
    (output / "costs").mkdir()
    binary = blender_binary()
    if not binary:
        raise ShowcaseError("Blender not available")
    provider = OpenAICompatibleCodeProvider(
        endpoint="https://api.openai.com/v1/chat/completions",
        model=MODEL, api_key=os.environ["GEOMETRY_CLOUD_API_KEY"],
        timeout=60, max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    total_model_usd = Decimal("0")
    records = []
    aborted_reason = None
    started = time.monotonic()
    for task_id in ids:
        folder = public_root / task_id
        task_out = outdir / task_id
        task_out.mkdir()
        record = {"task_id": task_id, "model": MODEL, "call_id": None,
                  "provider_outcome": "NOT_RUN", "safe_source": "UNKNOWN",
                  "native_scene": "UNKNOWN", "prompt_fidelity": "UNKNOWN",
                  "official_3dcodebench_score": None, "usd_estimate": None,
                  "error_class": None, "files": []}
        records.append(record)
        try:
            prompt_paths = [folder / name for name in ("prompt_description.txt", "prompt_instruction.txt")]
            public = []
            for p in prompt_paths:
                if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(public_root):
                    raise ShowcaseError("Unsafe public prompt")
                raw = p.read_bytes()
                if len(raw) > 128 * 1024:
                    raise ShowcaseError("Public prompt too large")
                public.append(raw.decode("utf-8"))
            prompt = CONTRACT + "\n\nOBJECT DESCRIPTION:\n" + public[0] + \
                     "\n\nOBJECT INSTRUCTIONS:\n" + public[1]
            if not 1 <= len(prompt) <= 12000:
                raise ShowcaseError("Public prompt exceeds provider limit")
            bound = conservative_max_usd(prompt)
            if total_model_usd + bound > MAX_MODEL_USD:
                raise ShowcaseError("Conservative USD model call bound exceeded; no request sent")
            os.environ["GEOMETRY_BENCHMARK_TASK_ID"] = task_id
            # Exactly one request per task. Never retry failed, refused or unpriced calls.
            try:
                output_code = provider.generate(prompt)
            finally:
                os.environ.pop("GEOMETRY_BENCHMARK_TASK_ID", None)
            record["call_id"] = output_code.call_id
            record["provider_outcome"] = "COMPLETED"
            record["usd_estimate"] = output_code.cost_usd
            if output_code.pricing is None or output_code.pricing.get("status") != "PRICED":
                raise ShowcaseError("No verified usage/pricing for provider call")
            if output_code.pricing.get("model") != MODEL:
                aborted_reason = "UnexpectedProviderModel"
                raise ShowcaseError("Unexpected returned model; no silent substitution")
            total_model_usd += Decimal(output_code.cost_usd)
            code_path = task_out / "model-generated.py"
            code_path.write_text(output_code.code, encoding="utf-8")
            plan = compile_bpy_subset(output_code.code)
            record["safe_source"] = "PASS"
            _write(task_out / "scene-spec.json", plan)
            _safe_run([binary, "-b", "--factory-startup", "--python-exit-code", "14",
                       "--python", str(BUILDER), "--", "--spec", str(task_out/"scene-spec.json"),
                       "--out", str(task_out)], task_out / "build.txt", limit=70)
            _safe_run([binary, "-b", str(task_out/"scene.blend"), "--python-exit-code", "14",
                       "--python", str(INSPECT), "--", "--spec", str(task_out/"scene-spec.json"),
                       "--output", str(task_out/"geometry.json")],
                      task_out / "inspect.txt", limit=70)
            geometry = json.loads((task_out/"geometry.json").read_text())
            if not geometry.get("passed"):
                raise ShowcaseError("Independent Blender geometry check rejected scene")
            width, height = png_dimensions(task_out / "preview.png")
            if width <= 0 or height <= 0:
                raise ShowcaseError("Missing rendered preview dimensions")
            record["native_scene"] = "PASS"
        except (ProviderError, UnsafeGeneratedCode, ShowcaseError, OSError,
                ValueError, UnicodeError) as exc:
            record["error_class"] = type(exc).__name__
            if record["provider_outcome"] != "COMPLETED":
                record["provider_outcome"] = "FAIL_OR_NOT_RUN"
                # A transport failure can have been billed with missing usage;
                # stop before the next request and retain UNKNOWN in ledger.
                aborted_reason = type(exc).__name__
            elif record["safe_source"] == "UNKNOWN":
                record["safe_source"] = "FAIL"
            elif record["native_scene"] == "UNKNOWN":
                record["native_scene"] = "FAIL"
        for path in task_out.rglob("*"):
            if path.is_file() and not path.is_symlink():
                record["files"].append({
                    "path": str(path.relative_to(output)), "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                })
        _write(task_out / "result.json", record)
        if aborted_reason:
            break
    cost = _cost(output)
    if cost is None or cost.get("grand_total_status") != "COMPLETE":
        aborted_reason = aborted_reason or "UnknownBilling"
    if cost and Decimal(cost["priced_subtotal_usd"]) > MAX_MODEL_USD:
        aborted_reason = "ActualModelSpendExceeded"
    scene_success = sum(1 for r in records if r["native_scene"] == "PASS")
    metric = {
        "schema_version": 1, "benchmark": "3DCodeBench",
        "track": "internal_restricted_safe_literal_bpy",
        "dataset_revision": EXPECTED_REV, "smoke_ids": ids,
        "attempted": len(records), "requested": len(ids),
        "scene_passes": scene_success,
        "scene_pass_rate": str(Decimal(scene_success) / len(records)) if records else None,
        "upstream_similarity_score": None,
        "quality_status": "UNKNOWN_NO_UPSTREAM_SCORER",
        "model": MODEL,
        "model_call_limit": MAX_CALLS,
        "model_calls_recorded": cost["recorded_calls"] if cost else 0,
        "model_usd_upper_budget": str(MAX_MODEL_USD),
        "model_estimated_usd": cost["priced_subtotal_usd"] if cost else None,
        "cost_reconciliation": cost["grand_total_status"] if cost else "UNKNOWN",
        # A failed/refused/generated-invalid last task is a benchmark FAIL,
        # not a missing test, PROVIDED all six calls are accounted and priced.
        # Still reject unknown billing, model mismatch and overspend.
        "status": "COMPLETE_INTERNAL_SMOKE" if (
            len(records) == MAX_CALLS and cost is not None
            and cost["recorded_calls"] == MAX_CALLS
            and cost["grand_total_status"] == "COMPLETE"
            and Decimal(cost["priced_subtotal_usd"]) <= MAX_MODEL_USD
            and aborted_reason not in {"UnexpectedProviderModel", "ActualModelSpendExceeded"}
        ) else "INCOMPLETE",
        "task_failures": sum(1 for r in records if r["native_scene"] != "PASS"),
        "aborted_reason": aborted_reason,
        "duration_seconds": round(time.monotonic() - started, 4),
        "source_sha": source_sha(), "platform": platform.platform(),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "task_results": [
            {k: v for k, v in r.items() if k not in {"files"}}
            for r in records
        ],
        "warning": "No official 3DCodeBench image/shape/judge metric; do not compare to upstream leaderboard.",
    }
    _write(output / "benchmark.json", metric)
    files = []
    for path in output.rglob("*"):
        if path.is_file() and path.name != "bundle-manifest.json":
            files.append({"path": str(path.relative_to(output)), "sha256": sha256(path),
                          "bytes": path.stat().st_size})
    _write(output / "bundle-manifest.json", {
        "schema_version": 1, "model": MODEL, "stage": "G1-benchmark-smoke",
        "source_sha": source_sha(), "dataset_revision": EXPECTED_REV,
        "benchmark_status": metric["status"], "file_count": len(files), "files": files,
    })
    print(json.dumps({k: metric[k] for k in ("status", "attempted", "scene_passes",
                                             "model_calls_recorded", "model_estimated_usd",
                                             "cost_reconciliation", "quality_status",
                                             "task_failures", "aborted_reason")}))
    return metric


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--public-root", type=Path, required=True)
    p.add_argument("--suite", type=Path, required=True)
    a = p.parse_args()
    result = run(a.output, a.public_root, a.suite)
    return 0 if result["status"] == "COMPLETE_INTERNAL_SMOKE" else 1


if __name__ == "__main__":
    sys.exit(main())
