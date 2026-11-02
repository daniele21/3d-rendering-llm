"""Transactional, authorized 2D architectural door move with independent CAD reopen.

No model Python / arbitrary DXF code. Only typed deltas against a SHA-verified
source revision may produce a NEW, annotated DXF. Any failure leaves the
source unchanged and a rollback copy, never a partial accepted output.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from .dxf_revision import export_verified_plan_dxf, import_verified_plan_dxf
from .geometry_math import opening_on_wall
from .schema import PlanReject, plan_sha256, validate_plan

MAX_MOVE_MM = 1000
PATCH_KEYS = frozenset({
    "schema_version","operation_id","operation_type","target_id",
    "expected_plan_sha256","expected_offset_mm","delta_mm",
})
ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


class CADPatchReject(PlanReject):
    pass


def _stable_id(value):
    return (type(value) is str and 1<=len(value)<=48 and
            value[0].isalpha() and all(c in ID_CHARS for c in value))


def preflight_move_door(plan: dict, patch: dict) -> tuple[dict, dict]:
    """Validate an all-or-nothing edit, return candidate and change evidence.

    Wall geometry is unchanged, door width+host unchanged. Reject a move
    on locked/unknown/load-bearing wall as not independently authorized.
    """
    original=validate_plan(plan)
    if type(patch) is not dict or set(patch)!=PATCH_KEYS:
        raise CADPatchReject("Patch must have exact allowlisted fields")
    if (type(patch["schema_version"]) is not int or patch["schema_version"]!=1
            or patch["operation_type"]!="move_door"
            or not _stable_id(patch["operation_id"])
            or not _stable_id(patch["target_id"])):
        raise CADPatchReject("Invalid operation or stable entity ID")
    expected=plan_sha256(original)
    if patch["expected_plan_sha256"]!=expected:
        raise CADPatchReject("Stale source revision hash")
    delta=patch["delta_mm"]
    if type(delta) is not int or not 1<=abs(delta)<=MAX_MOVE_MM:
        raise CADPatchReject("Door delta must be nonzero integer +/-1000 mm")
    if type(patch["expected_offset_mm"]) is not int:
        raise CADPatchReject("Expected old position must be exact integer mm")
    matches=[o for o in original["openings"] if o["id"]==patch["target_id"]]
    if len(matches)!=1 or matches[0]["kind"]!="door":
        raise CADPatchReject("Target door not found")
    door=matches[0]
    if door["locked"]:
        raise CADPatchReject("Door is locked, no authorized mutation")
    if door["offset_mm"]!=patch["expected_offset_mm"]:
        raise CADPatchReject("Door location precondition mismatch")
    hosts=[w for w in original["walls"] if w["id"]==door["host_wall_id"]]
    if len(hosts)!=1:
        raise CADPatchReject("Host wall missing")
    host=hosts[0]
    if host["locked"] or host["structural_status"]!="non_load_bearing":
        raise CADPatchReject("Host wall locked or structural status not approved")
    new_offset=door["offset_mm"]+delta
    if type(new_offset) is not int or new_offset<0 or new_offset>30_000:
        raise CADPatchReject("New door offset outside bounded range")
    position=opening_on_wall(host["start_mm"],host["end_mm"],
                             offset_mm=new_offset,width_mm=door["width_mm"])
    if position["status"]!="PASS":
        raise CADPatchReject("Door would extend beyond wall")
    for other in original["openings"]:
        if other["id"]==door["id"] or other["host_wall_id"]!=door["host_wall_id"]:
            continue
        left,right=new_offset,new_offset+door["width_mm"]
        a,b=other["offset_mm"],other["offset_mm"]+other["width_mm"]
        if max(a,left)<min(b,right):
            raise CADPatchReject("Door would overlap another opening")
    next_plan=deepcopy(original)
    next_door=next(o for o in next_plan["openings"] if o["id"]==door["id"])
    next_door["offset_mm"]=new_offset
    # Deterministic revision identifier without self-referential plan hash.
    key=f"{expected}|{patch['operation_id']}|{door['id']}|{new_offset}"
    next_plan["revision_id"]="rev_"+hashlib.sha256(key.encode("utf8")).hexdigest()[:16]
    next_plan=validate_plan(next_plan)
    if (next_plan["source_sha256"]!=original["source_sha256"]
            or next_plan["walls"]!=original["walls"]
            or any(x!=y for x,y in zip(next_plan["openings"], original["openings"])
                   if x["id"]!=door["id"])):
        raise CADPatchReject("Unauthorized non-target mutation")
    evidence={
        "operation_id":patch["operation_id"],"target_id":door["id"],
        "operation_type":"move_door","old_offset_mm":door["offset_mm"],
        "new_offset_mm":new_offset,"delta_mm":delta,
        "source_plan_sha256":expected,
        "candidate_plan_sha256":plan_sha256(next_plan),
        "other_walls_unchanged":True,"other_openings_unchanged":True,
        "geometry_gate":position,
    }
    return next_plan,evidence


def _write_json(path: Path, data: dict):
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n",encoding="utf8")
    path.chmod(0o600)


def run_move_door(source_path: Path, patch: dict, out: Path) -> dict:
    supplied=Path(source_path).expanduser()
    if supplied.is_symlink():
        raise CADPatchReject("Symlinked input plan is not authorized")
    source_path=supplied.resolve()
    out=Path(out).expanduser().resolve()
    if out.exists() or not source_path.is_file():
        raise CADPatchReject("Original regular plan required and fresh output directory")
    if out==source_path.parent or out.is_relative_to(source_path.parent) and out.name==source_path.name:
        raise CADPatchReject("Output cannot alias original source file")
    original_bytes=source_path.read_bytes()
    if len(original_bytes)>2_000_000:
        raise CADPatchReject("Source plan exceeds maximum 2MB")
    original_file_sha=hashlib.sha256(original_bytes).hexdigest()
    original=validate_plan(json.loads(original_bytes))
    candidate, evidence=preflight_move_door(original,patch)
    out.mkdir(parents=True,mode=0o700)
    _write_json(out/"original-plan.json",original)
    _write_json(out/"rollback-plan.json",original)
    # Writing the candidate is not accepting it. Only a newly reopened
    # annotated DXF may become the final accepted revision.
    _write_json(out/"candidate-plan.json",candidate)
    accepted=False
    failure=None
    export=None
    try:
        export=export_verified_plan_dxf(candidate,out/"candidate.dxf")
        independent=import_verified_plan_dxf(out/"candidate.dxf")
        if independent!=candidate or plan_sha256(independent)!=evidence["candidate_plan_sha256"]:
            raise CADPatchReject("Independent readback disagrees with candidate")
        if hashlib.sha256(source_path.read_bytes()).hexdigest()!=original_file_sha:
            raise CADPatchReject("Original source changed during transaction")
        _write_json(out/"accepted-plan.json",candidate)
        accepted=True
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failure=type(exc).__name__
    if hashlib.sha256(source_path.read_bytes()).hexdigest()!=original_file_sha:
        accepted=False
        failure="SourceCorruptedDuringTransaction"
        (out/"accepted-plan.json").unlink(missing_ok=True)
    report={
        "schema_version":1,
        "status":"ACCEPTED" if accepted else "ROLLED_BACK",
        "operation_id":patch["operation_id"],
        "source_revision_sha256":evidence["source_plan_sha256"],
        "accepted_revision_sha256":evidence["candidate_plan_sha256"] if accepted else None,
        "rollback_revision_sha256":plan_sha256(original),
        "source_file_sha256":original_file_sha,
        "source_unchanged":hashlib.sha256(source_path.read_bytes()).hexdigest()==original_file_sha,
        "non_targets_unchanged":evidence["other_walls_unchanged"] and evidence["other_openings_unchanged"],
        "new_model_calls":0,
        "tool":"ezdxf",
        "failure_class":failure,
        "dxf_export":export,
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "artifact_hashes":[],
    }
    _write_json(out/"operation.json",evidence)
    for file in sorted(out.iterdir()):
        if file.is_file() and file.name!="transaction-manifest.json":
            report["artifact_hashes"].append({
                "path":file.name,
                "sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                "bytes":file.stat().st_size,
            })
    _write_json(out/"transaction-manifest.json",report)
    return report


def main(argv=None) -> int:
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",required=True,type=Path)
    p.add_argument("--patch",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        patch=json.loads(a.patch.read_text(encoding="utf8"))
        result=run_move_door(a.plan,patch,a.out)
    except (OSError,ValueError,TypeError) as exc:
        print(json.dumps({"status":"REJECTED_BEFORE_TRANSACTION",
                          "reason":type(exc).__name__}))
        return 2
    print(json.dumps({k:result[k] for k in (
        "status","operation_id","source_unchanged",
        "non_targets_unchanged","new_model_calls")},sort_keys=True))
    return 0 if result["status"]=="ACCEPTED" else 1


if __name__=="__main__":
    raise SystemExit(main())
