"""Independently audit a real six-task evidence bundle and build a failure-inclusive gallery.

Not an official 3DCodeBench image/Chamfer/Uni3D/judge scorer. The executable
pass is measured from independently opened Blender scene evidence only;
reference similarity is UNKNOWN unless an externally reviewed scorer runs.
This script never reads hidden reference factories or calls any AI model.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from geometry_harness.costs.ledger import reconcile, load_events

from geometry_harness.cli import png_dimensions


class EvidenceError(ValueError):
    pass


EXPECTED_DATASET = "b70b4ee54b93fab76596da5809f3e71c617fa5c2"
EXPECTED_IDS = ("CoffeeTable_seed0", "ArmChair_seed0", "Bottle_seed0",
                "AquariumTank_seed0", "Balloon_seed0", "BrainCoral_seed0")


def _read_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise EvidenceError("Required audit metadata missing or linked")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise EvidenceError("Invalid JSON audit evidence") from None


def _file(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel:
        raise EvidenceError("Invalid evidence path")
    path = root / rel
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise EvidenceError("Missing evidence or symlink traversal")
    return path


def audit(root: Path) -> dict:
    root = root.resolve()
    report = _read_json(root / "benchmark.json")
    bundle = _read_json(root / "bundle-manifest.json")
    cost = _read_json(root / "cost-summary.json")
    if report.get("dataset_revision") != EXPECTED_DATASET or report.get("model") != "gpt-6-luna":
        raise EvidenceError("Unexpected benchmark revision or model")
    if tuple(report.get("smoke_ids", ())) != EXPECTED_IDS:
        raise EvidenceError("Exact benchmark six-task cohort changed")
    if (bundle.get("source_sha") != report.get("source_sha")
            or bundle.get("dataset_revision") != EXPECTED_DATASET
            or bundle.get("model") != "gpt-6-luna"):
        raise EvidenceError("Bundle identity mismatch")
    files = bundle.get("files")
    if not isinstance(files, list) or not files:
        raise EvidenceError("Missing file inventory")
    seen = set()
    for item in files:
        rel = item.get("path")
        if rel in seen:
            raise EvidenceError("Duplicate artifact inventory path")
        seen.add(rel)
        content = _file(root, rel).read_bytes()
        if hashlib.sha256(content).hexdigest() != item.get("sha256") or len(content) != item.get("bytes"):
            raise EvidenceError("SHA/length mismatch: artifact corrupted")
    if not {"benchmark.json", "cost-summary.json", "costs/events.jsonl"}.issubset(seen):
        raise EvidenceError("Incomplete per-call cost or benchmark audit files")
    expected = set(EXPECTED_IDS)
    per_task = report.get("task_results")
    if not isinstance(per_task, list) or set(x.get("task_id") for x in per_task) != expected or len(per_task) != 6:
        raise EvidenceError("Missing/duplicate task outcome; denominator must remain six")
    if cost.get("recorded_calls") != 6 or cost.get("grand_total_status") != "COMPLETE":
        raise EvidenceError("Cannot claim full priced six-task dataset audit")
    try:
        recalculated = reconcile(load_events(_file(root, "costs/events.jsonl")))
    except (ValueError, KeyError, TypeError):
        raise EvidenceError("Raw cost ledger cannot be independently reconciled") from None
    if (recalculated.get("grand_total_status") != "COMPLETE"
            or recalculated["recorded_calls"] != 6
            or recalculated["priced_subtotal_usd"] != cost["priced_subtotal_usd"]):
        raise EvidenceError("Saved summary differs from original per-call ledger")
    if cost.get("priced_subtotal_usd") != report.get("model_estimated_usd"):
        raise EvidenceError("Model cost mismatch")
    outcomes = []
    for tid in EXPECTED_IDS:
        task = next(x for x in per_task if x["task_id"] == tid)
        result = _read_json(_file(root, f"tasks/{tid}/result.json"))
        if result.get("task_id") != tid or result.get("native_scene") != task.get("native_scene"):
            raise EvidenceError("Task outcome differs between manifest and task result")
        state = result["native_scene"]
        if state not in ("PASS", "FAIL", "UNKNOWN"):
            raise EvidenceError("Unrecognized scene result")
        image = None
        if state == "PASS":
            for rel in (f"tasks/{tid}/scene.blend",
                        f"tasks/{tid}/preview.png",
                        f"tasks/{tid}/geometry.json"):
                if rel not in seen:
                    raise EvidenceError("Claimed native PASS without hashed real scene")
                _file(root, rel)
            scene = _file(root, f"tasks/{tid}/scene.blend")
            if not scene.read_bytes().startswith(b"BLENDER"):
                raise EvidenceError("Claimed native scene is not Blender")
            geometry = _read_json(_file(root, f"tasks/{tid}/geometry.json"))
            if geometry.get("passed") is not True or not geometry.get("mesh_objects"):
                raise EvidenceError("No independent positive Blender reopen evidence")
            width,height = png_dimensions(_file(root, f"tasks/{tid}/preview.png"))
            if width <= 0 or height <= 0:
                raise EvidenceError("Invalid real preview")
            image = f"tasks/{tid}/preview.png"
        outcomes.append({
            "task_id": tid, "native_scene": state, "preview_path": image,
            "prompt_fidelity": "UNKNOWN", "official_similarity": "UNKNOWN",
            "provider_outcome": result.get("provider_outcome"),
            "cost_usd_estimate": result.get("usd_estimate"),
            "error_class": result.get("error_class"),
        })
    pass_count = sum(x["native_scene"] == "PASS" for x in outcomes)
    failed = sum(x["native_scene"] == "FAIL" for x in outcomes)
    unknown = sum(x["native_scene"] == "UNKNOWN" for x in outcomes)
    if pass_count != report.get("scene_passes"):
        raise EvidenceError("Native-scene pass count inconsistent with original report")
    return {
        "schema_version": 1, "dataset_revision": EXPECTED_DATASET,
        "model": "gpt-6-luna", "source_sha": report["source_sha"],
        "original_run_status": report["status"],
        "audit_status": "EVIDENCE_VERIFIED_NOT_UPSTREAM_SCORED",
        "task_count": 6, "native_pass": pass_count,
        "native_fail": failed, "native_unknown": unknown,
        "native_pass_rate": pass_count / 6,
        "cost_status": "COMPLETE", "model_estimated_usd": cost["priced_subtotal_usd"],
        "shape_score": None, "visual_score": None, "upstream_scorer": "NOT_RUN",
        "notes": "Only native scene/geometry evidence verified; FAILED original CI is not rewritten. Comparison to official 3DCodeBench is not valid yet.",
        "tasks": outcomes,
    }


def gallery(data: dict):
    esc = lambda x: html.escape(str(x), quote=True)
    sections = []
    for item in data["tasks"]:
        if item["preview_path"]:
            img = '<img loading="lazy" width="320" src="' + esc(item["preview_path"]) + '" alt="' + esc(item["task_id"]) + ' preview">'
        else:
            img = "<p>No validated native scene / preview</p>"
        sections.append("<section><h2>" + esc(item["task_id"]) + "</h2>" + img +
                        "<p>Native scene: " + esc(item["native_scene"]) +
                        " · visual fidelity: UNKNOWN · shape similarity: UNKNOWN</p></section>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Geometry six-task evidence gallery</title>"
            "<style>body{font:16px system-ui;margin:2em auto;max-width:1100px}"
            "section{display:inline-block;vertical-align:top;width:45%;padding:1%;border:1px solid #aaa;margin:.5%}"
            "img{max-width:100%;height:auto}</style><h1>Six-task evidence — "
            + esc(data["model"]) + "</h1><p>Native passes " +
            str(data["native_pass"]) + "/6. Official shape and visual quality UNKNOWN."
            " Historical CI and cost evidence preserved without model reruns.</p>" +
            "".join(sections) + "</html>")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    if a.out.exists():
        p.error("Refusing to overwrite an existing audit")
    result = audit(a.root)
    a.out.mkdir(parents=True)
    (a.out / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    for item in result["tasks"]:
        if item["preview_path"]:
            src = _file(a.root.resolve(), item["preview_path"])
            dest = a.out / item["preview_path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    (a.out / "index.html").write_text(gallery(result))
    print(json.dumps({key: result[key] for key in
                      ("audit_status","native_pass","native_fail","native_unknown",
                       "model_estimated_usd", "upstream_scorer")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
