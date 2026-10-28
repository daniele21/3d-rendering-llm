"""Single-object authorized translation with native Blender checkpoint and rollback.

The accepted source .blend is NEVER modified. All model-authored Python remains
data, not executable. Only our audited Blender builder and inspector are run.
Missing/failed invariants reject the candidate; original checkpoint survives.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone

from geometry_harness.cli import blender_binary, sha256, ShowcaseError
from geometry_harness.g1 import BUILDER, INSPECT, _safe_run
from geometry_harness.validation.issues import validate

class RepairError(ValueError):
    pass


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vec(value):
    if not isinstance(value, list) or len(value) != 3 or any(
        type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 30
        for x in value
    ):
        raise RepairError("Finite absolute metric coordinates [-30,30] required")
    return [float(v) for v in value]


def preflight(spec: dict, patch: dict, source_spec_sha: str, source_blend_sha: str) -> dict:
    allowed = {"schema_version", "operation_id", "operation_type", "target_id",
               "scene_spec_sha256", "scene_blend_sha256",
               "expected_location_m", "new_location_m"}
    if not isinstance(patch, dict) or set(patch) != allowed:
        raise RepairError("Unauthorized or missing typed operation properties")
    if patch["schema_version"] != 1 or patch["operation_type"] != "set_location":
        raise RepairError("Only bounded set_location v1 is implemented")
    if not isinstance(patch["operation_id"], str) or not patch["operation_id"].isidentifier():
        raise RepairError("Invalid operation_id")
    if patch["scene_spec_sha256"] != source_spec_sha or patch["scene_blend_sha256"] != source_blend_sha:
        raise RepairError("Stale or forged scene revision")
    if not isinstance(spec, dict) or spec.get("parser") != "safe_literal_bpy_cube_v1":
        raise RepairError("Unknown safe scene specification")
    parts = spec.get("objects")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 48:
        raise RepairError("Missing trusted scene objects")
    by_name = {p.get("name"): p for p in parts}
    if len(by_name) != len(parts):
        raise RepairError("Duplicate object identity")
    target = patch["target_id"]
    if not isinstance(target, str) or not target.isidentifier() or target not in by_name:
        raise RepairError("Missing or unauthorized target ID")
    old = _vec(patch["expected_location_m"])
    if any(abs(a-b) > 1e-5 for a,b in zip(old,_vec(by_name[target]["location"]))):
        raise RepairError("Optimistic location precondition does not match")
    new = _vec(patch["new_location_m"])
    if any(abs(a-b) > .5 for a,b in zip(old, new)):
        raise RepairError("Maximum scoped translation is 0.5 m per axis")
    if old == new:
        raise RepairError("No-op patch rejected")
    candidate = deepcopy(spec)
    next(p for p in candidate["objects"] if p["name"] == target)["location"] = new
    # We alter ONLY one location; all other fields and identities stay unchanged.
    for left,right in zip(parts,candidate["objects"]):
        if left["name"] != right["name"]:
            raise RepairError("Identity mutation")
        if left["name"] != target and left != right:
            raise RepairError("Non-target object was modified")
    return candidate


def execute(original_blend: Path, original_spec: Path, patch: dict,
            task_contract: dict, out: Path) -> dict:
    original_blend, original_spec, out = (
        original_blend.resolve(), original_spec.resolve(), out.resolve())
    if out.exists():
        raise RepairError("Refusing to overwrite or reuse an output directory")
    if not original_blend.is_file() or original_blend.is_symlink() or not original_spec.is_file() or original_spec.is_symlink():
        raise RepairError("Source scene and safe spec must be regular files")
    if not original_blend.read_bytes().startswith(b"BLENDER"):
        raise RepairError("Source is not a native Blender checkpoint")
    spec_sha, blend_sha = _hash(original_spec), _hash(original_blend)
    source_spec = json.loads(original_spec.read_text(encoding="utf-8"))
    candidate_spec = preflight(source_spec, patch, spec_sha, blend_sha)
    binary = blender_binary()
    if not binary:
        raise RepairError("Real Blender is required, no synthetic acceptance")
    out.mkdir(parents=True)
    artifacts = out / "candidate"
    artifacts.mkdir()
    logs = out / "logs"
    logs.mkdir()
    accepted = False
    failure = None
    original_observed = None
    candidate_observed = None
    before_report = None
    after_report = None
    source_checkpoint = out / "source-checkpoint.blend"
    shutil.copy2(original_blend, source_checkpoint)
    try:
        # Source must reopen and match the *original* spec before any mutation.
        _safe_run([binary, "-b", str(source_checkpoint),
                   "--disable-autoexec", "--python-exit-code", "14",
                   "--python", str(INSPECT), "--", "--spec", str(original_spec),
                   "--output", str(out / "original-geometry.json")],
                  logs / "original-reopen.txt", limit=90)
        original_observed = json.loads((out / "original-geometry.json").read_text())
        if not original_observed.get("passed"):
            raise RepairError("Source scene failed fresh-process consistency check")
        before_report = validate(original_observed, task_contract)
        if before_report["status"] == "UNKNOWN":
            raise RepairError("Original scene constraints unknown")
        (out / "candidate-spec.json").write_text(
            json.dumps(candidate_spec, indent=2) + "\n", encoding="utf-8")
        _safe_run([binary, "-b", "--factory-startup",
                   "--disable-autoexec", "--python-exit-code", "14",
                   "--python", str(BUILDER), "--",
                   "--spec", str(out / "candidate-spec.json"),
                   "--out", str(artifacts)], logs / "candidate-build.txt", limit=90)
        _safe_run([binary, "-b", str(artifacts / "scene.blend"),
                   "--disable-autoexec", "--python-exit-code", "14",
                   "--python", str(INSPECT), "--",
                   "--spec", str(out / "candidate-spec.json"),
                   "--output", str(out / "candidate-geometry.json")],
                  logs / "candidate-reopen.txt", limit=90)
        candidate_observed = json.loads((out / "candidate-geometry.json").read_text())
        if not candidate_observed.get("passed"):
            raise RepairError("Candidate failed fresh Blender geometry validation")
        old_by_id = {o["geometry_id"]: o for o in original_observed["mesh_objects"]}
        new_by_id = {o["geometry_id"]: o for o in candidate_observed["mesh_objects"]}
        if set(old_by_id) != set(new_by_id):
            raise RepairError("Object IDs were added or removed")
        for ident in old_by_id:
            if ident != patch["target_id"] and old_by_id[ident] != new_by_id[ident]:
                raise RepairError("Non-target native mesh changed")
        after_report = validate(candidate_observed, task_contract)
        if after_report["status"] != "PASS":
            raise RepairError("Candidate did not satisfy the declared task constraints")
        if _hash(original_blend) != blend_sha or _hash(original_spec) != spec_sha:
            raise RepairError("Source checkpoint was modified during the repair")
        # This happens only AFTER independent reopen/validation. Source remains immutable.
        shutil.copy2(artifacts / "scene.blend", out / "accepted.blend")
        accepted = True
    except (ShowcaseError, RepairError, ValueError, OSError, KeyError, TypeError) as exc:
        failure = type(exc).__name__
        # Explicit recoverable checkpoint, never reinterpret failed candidate as accepted.
    finally:
        shutil.copy2(source_checkpoint, out / "rollback.blend")
        if _hash(original_blend) != blend_sha or _hash(out / "rollback.blend") != blend_sha:
            accepted = False
            failure = "SourceRevisionCorrupted"
        report = {"schema_version": 1, "operation_id": patch["operation_id"],
                  "target_id": patch["target_id"], "operation_type": "set_location",
                  "source_spec_sha256": spec_sha, "source_blend_sha256": blend_sha,
                  "status": "ACCEPTED" if accepted else "ROLLED_BACK",
                  "model_calls": 0, "model_cost_usd": "0",
                  "before_status": before_report["status"] if before_report else "UNKNOWN",
                  "after_status": after_report["status"] if after_report else "UNKNOWN",
                  "source_checkpoint_unchanged": _hash(original_blend) == blend_sha,
                  "rollback_matches_source": _hash(out / "rollback.blend") == blend_sha,
                  "error_class": failure,
                  "files": []}
        (out / "operation.json").write_text(json.dumps(
            {"schema_version": 1, "operation_id": patch["operation_id"],
             "type": "set_location", "target_id": patch["target_id"],
             "source_blend_sha256": blend_sha, "old": patch["expected_location_m"],
             "new": patch["new_location_m"]}, indent=2) + "\n")
        for file in sorted(out.rglob("*")):
            if file.is_file() and file.name != "repair-manifest.json":
                report["files"].append({"path": str(file.relative_to(out)),
                                        "sha256": _hash(file), "bytes": file.stat().st_size})
        (out / "repair-manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    for name in ("--blend", "--spec", "--patch", "--contract", "--out"):
        p.add_argument(name, type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = execute(args.blend, args.spec,
                         json.loads(args.patch.read_text(encoding="utf-8")),
                         json.loads(args.contract.read_text(encoding="utf-8")),
                         args.out)
        print(json.dumps({key:report[key] for key in ("status", "target_id", "before_status", "after_status","model_calls")}))
        return 0 if report["status"] == "ACCEPTED" else 2
    except (OSError, ValueError, RepairError) as exc:
        p.exit(2, f"Scoped repair rejected: {type(exc).__name__}\n")


if __name__ == "__main__":
    raise SystemExit(main())
