"""G1 vertical slice: generated Blender Python -> safe AST -> trusted bpy -> .blend.

No model-authored Python ever reaches Blender's Python interpreter. The audited
subset converter accepts only literal cube object creation and properties.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

from geometry_harness.cli import blender_binary, png_dimensions, sha256, source_sha, ShowcaseError
from geometry_harness.costs.ledger import default_ledger_path, load_events, reconcile
from geometry_harness.providers.compatible import OpenAICompatibleCodeProvider, ProviderError
from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode
from geometry_harness.telemetry.spans import TraceRecorder, write_summary
from geometry_harness.validation.issues import validate as validate_geometry


ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "blender" / "build_safe_scene.py"
INSPECT = ROOT / "blender" / "inspect_safe_scene.py"
RENDER_VIEWS = ROOT / "blender" / "render_validation_views.py"


def table_validation_contract() -> dict:
    """Independent stated table constraints, not model-chosen coordinates."""
    reqs = []
    for number in range(1, 5):
        name = f"leg_{number}"
        reqs.extend((
            {"id": f"floor_{number}", "type": "floor_contact",
             "object_id": name, "floor_z_m": 0.0, "tolerance_m": .05},
            {"id": f"support_{number}", "type": "vertical_contact",
             "support_id": name, "supported_id": "tabletop", "tolerance_m": .05},
        ))
    return {"schema_version": 1, "task_id": "internal_g1_table",
            "units": "m", "requirements": reqs}

PROMPT = """Create an editable wooden four-leg table in Blender 5 with exactly 5 mesh cubes.

Output ONLY literal Python bpy statements in this constrained form, repeated 5 times:
import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
obj = bpy.context.object
obj.name = "tabletop"
obj.dimensions = (2, 1, .08)

Create tabletop, leg_1, leg_2, leg_3 and leg_4 with distinct names, plausible
dimensions and positions. Legs must touch the floor and underside of tabletop.
Only those import, primitive_cube_add, name, dimensions, location and scale
statements are allowed. No variables in numeric expressions, loops, functions,
materials, cameras, filesystem operations, imports other than bpy or other bpy
ops. No explanation or markdown. Do not duplicate the example objects.
"""


def _safe_run(command: list[str], log_path: Path, limit: int = 90) -> float:
    """Run only *audited repo-owned* scripts in Blender without provider creds."""
    safe_env = {k: v for k, v in os.environ.items()
                if not (k.endswith(("_TOKEN", "_KEY", "_SECRET")) or
                        k.startswith(("GOOGLE_", "AWS_", "AZURE_")) or
                        k in ("GITHUB_TOKEN", "GH_TOKEN", "GEOMETRY_CLOUD_API_KEY"))}
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 env=safe_env, start_new_session=True)
        try:
            code = child.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise ShowcaseError("Trusted Blender builder exceeded time budget") from None
    if code:
        raise ShowcaseError(f"Trusted Blender builder failed with exit {code}")
    return round(time.monotonic() - start, 4)


def _table_semantics(parts: list[dict]) -> list[dict]:
    by_name = {p["name"]: p for p in parts}
    checks = []
    expected = {"tabletop", "leg_1", "leg_2", "leg_3", "leg_4"}
    checks.append({"name": "five_expected_named_parts",
                   "status": "PASS" if set(by_name) == expected else "FAIL"})
    if set(by_name) != expected:
        return checks
    top = by_name["tabletop"]
    bottom_top = top["location"][2] - top["dimensions"][2] / 2
    for number in range(1, 5):
        leg = by_name[f"leg_{number}"]
        floor = leg["location"][2] - leg["dimensions"][2] / 2
        contact = leg["location"][2] + leg["dimensions"][2] / 2
        inside = all(abs(leg["location"][ax] - top["location"][ax]) +
                     leg["dimensions"][ax] / 2 <= top["dimensions"][ax] / 2 + .025
                     for ax in (0, 1))
        ok = abs(floor) < .05 and abs(contact - bottom_top) < .05 and inside
        checks.append({"name": f"leg_{number}_contacts_floor_and_top",
                       "status": "PASS" if ok else "FAIL"})
    return checks


def _cost_summary(root: Path):
    ledger = root / "costs" / "events.jsonl"
    if not ledger.is_file():
        return None
    result = reconcile(load_events(ledger))
    (root / "cost-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def create_g1(root: Path, *, fixture_source: str | None = None) -> dict:
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ShowcaseError("G1 output path must be new and empty")
    root.mkdir(parents=True, exist_ok=True)
    artifacts = root / "artifacts"
    logs = root / "logs"
    artifacts.mkdir()
    logs.mkdir()
    tracer = TraceRecorder(root, source_sha=source_sha())
    started = time.monotonic()
    model_result = None
    status = "FAIL"
    errors: list[str] = []
    previous_span_id = None
    try:
        if fixture_source is None:
            cost_path = default_ledger_path()
            if not cost_path.is_relative_to(root):
                raise ShowcaseError("Live G1 cost ledger must be in the owned G1 artifact directory")
            with tracer.span("llm.generate") as span:
                model_result = OpenAICompatibleCodeProvider.from_env().generate(PROMPT)
                span.cost_call_id = model_result.call_id
            previous_span_id = span.span_id
            raw_source = model_result.code
        else:
            raw_source = fixture_source
        (artifacts / "model-generated.py").write_text(raw_source, encoding="utf-8")
        with tracer.span("code.compile", depends_on=(previous_span_id,) if previous_span_id else ()) as stage:
            parts = compile_bpy_subset(raw_source)
        previous_span_id = stage.span_id
        (artifacts / "scene-spec.json").write_text(json.dumps(parts, indent=2) + "\n")
        with tracer.span("geometry.validate", depends_on=(previous_span_id,)) as stage:
            checks = _table_semantics(parts["objects"])
            if any(x["status"] != "PASS" for x in checks):
                raise ShowcaseError("Generated geometry fails table part/contact specification")
        previous_span_id = stage.span_id
        binary = blender_binary()
        if not binary:
            raise ShowcaseError("Blender not installed on the target runner")
        with tracer.span("blender.build", depends_on=(previous_span_id,)) as stage:
            _safe_run([binary, "-b", "--factory-startup", "--python-exit-code", "14",
                       "--python", str(BUILDER), "--",
                       "--spec", str(artifacts / "scene-spec.json"),
                       "--out", str(artifacts)], logs / "build.txt")
        previous_span_id = stage.span_id
        if not (artifacts / "scene.blend").is_file():
            raise ShowcaseError("Trusted builder did not save native Blender scene")
        with tracer.span("scene.reopen", depends_on=(previous_span_id,)) as stage:
            _safe_run([binary, "-b", str(artifacts / "scene.blend"),
                       "--python-exit-code", "14", "--python", str(INSPECT), "--",
                       "--spec", str(artifacts / "scene-spec.json"),
                       "--output", str(artifacts / "geometry.json")], logs / "inspect.txt")
        previous_span_id = stage.span_id
        measured = json.loads((artifacts / "geometry.json").read_text())
        if not measured.get("passed"):
            raise ShowcaseError("Fresh-process geometric checks failed")
        # Evaluate the saved native scene against the *task* requirements
        # rather than only the dimensions proposed by the model itself.
        with tracer.span("geometry.validate", depends_on=(previous_span_id,)) as stage:
            geometry_report = validate_geometry(measured, table_validation_contract())
            (root / "geometry-issues.json").write_text(
                json.dumps(geometry_report, indent=2) + "\n", encoding="utf-8")
            if geometry_report["status"] != "PASS":
                raise ShowcaseError("Native scene fails independent floor/support constraints")
        previous_span_id = stage.span_id
        with tracer.span("blender.render_preview", depends_on=(previous_span_id,)) as stage:
            _safe_run([binary, "-b", str(artifacts / "scene.blend"),
                       "--python-exit-code", "14", "--python", str(RENDER_VIEWS),
                       "--", "--out", str(root / "views")], logs / "views.txt", limit=120)
        view_manifest = json.loads((root / "views" / "views-manifest.json").read_text())
        if {entry["view"] for entry in view_manifest["views"]} != {"front", "side", "top", "isometric"}:
            raise ShowcaseError("Four required Blender views not generated")
        width, height = png_dimensions(artifacts / "preview.png")
        checks += [{"name": "real_blender_reopen_geometry", "status": "PASS"},
                   {"name": "rendered_png_dimensions", "status": "PASS",
                    "detail": f"{width}x{height}"},
                   {"name": "generated_python_not_executed", "status": "PASS"},
                   {"name": "native_table_issues_pass", "status": "PASS"},
                   {"name": "four_real_validation_views", "status": "PASS"}]
        if fixture_source is None and (model_result is None or
                                       model_result.pricing is None or
                                       model_result.pricing.get("status") != "PRICED"):
            raise ShowcaseError("Actual model token pricing is incomplete")
        status = "PASS"
        shutil.copy2(artifacts / "preview.png", root / "contact-sheet.png")
        (root / "index.html").write_text(
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>G1 safe Blender showcase</title><h1>G1 — Blender geometry</h1>"
            "<p>Model source is parsed into audited literal geometry; never executed.</p>"
            "<img alt='Rendered model scene' src='artifacts/preview.png'>"
            "<p><a href='artifacts/scene.blend'>Native .blend</a> | "
            "<a href='artifacts/scene-spec.json'>Verified geometry data</a> | "
            "<a href='artifacts/model-generated.py'>Original model source</a></p>",
            encoding="utf-8"
        )
    except (ProviderError, UnsafeGeneratedCode, ShowcaseError, OSError, ValueError,
            json.JSONDecodeError) as exc:
        errors = [type(exc).__name__]  # sanitized failure class, no secrets or raw provider body
        checks = [{"name": "safe_g1_accepted", "status": "FAIL", "detail": errors[0]}]
    cost = _cost_summary(root)
    performance = write_summary(root)
    if fixture_source is None:
        if cost is None or cost.get("grand_total_status") != "COMPLETE":
            status = "FAIL"
            errors.append("IncompleteCostEvidence")
    (root / "assertions.json").write_text(json.dumps(checks, indent=2) + "\n")
    available = ("artifacts/model-generated.py", "artifacts/scene-spec.json",
                 "artifacts/scene.blend", "artifacts/preview.png",
                 "artifacts/geometry.json", "contact-sheet.png",
                 "index.html", "assertions.json", "costs/events.jsonl",
                 "cost-summary.json", "trace.jsonl", "performance-summary.json",
                 "geometry-issues.json", "views/views-manifest.json",
                 "views/front.png", "views/side.png", "views/top.png", "views/isometric.png",
                 "logs/build.txt", "logs/inspect.txt", "logs/views.txt")
    items = [{"path": name, "sha256": sha256(root / name),
              "bytes": (root / name).stat().st_size}
             for name in available if (root / name).is_file()]
    manifest = {"schema_version": 1, "milestone": "G1", "status": status,
                "evidence_type": "real_model_safe_literal_bpy_to_blender"
                if fixture_source is None else "trusted_fixture_safe_literal_bpy_to_blender",
                "model": model_result.model if model_result else "fixture_no_model",
                "model_calls": 1 if model_result else 0,
                "model_call_id": model_result.call_id if model_result else None,
                "source_sha": source_sha(),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "platform": platform.platform(),
                "duration_seconds": round(time.monotonic() - started, 4),
                "cost_usd_estimate": cost.get("priced_subtotal_usd") if cost else None,
                "cost_status": cost.get("grand_total_status") if cost else "NOT_APPLICABLE",
                "performance_status": performance["status"],
                "observed_span_wall_ms": performance["observed_wall_ms"],
                "checks": checks, "errors": errors, "artifacts": items}
    (root / "showcase-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if status != "PASS":
        raise ShowcaseError("G1 run failed; private bundle contains diagnostics and cost ledger")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="ci-artifacts/showcase/g1")
    parser.add_argument("--fixture", type=Path, help="Trusted repo fixture; no provider call")
    args = parser.parse_args(argv)
    try:
        fixture = args.fixture.read_text() if args.fixture else None
        result = create_g1(Path(args.output), fixture_source=fixture)
        print(json.dumps({"status": result["status"], "milestone": result["milestone"],
                          "evidence_type": result["evidence_type"],
                          "cost_estimate": result["cost_usd_estimate"]}))
        return 0
    except (OSError, ValueError, ShowcaseError) as exc:
        print(f"G1 FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
