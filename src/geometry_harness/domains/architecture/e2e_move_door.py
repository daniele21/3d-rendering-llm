"""Zero-inference synthetic Architecture W2 end-to-end DXF edit experiment.

Creates an explicitly annotated synthetic DXF with ezdxf, re-imports it,
proposes one authorized +300mm door move, writes a NEW DXF, and independently
checks the entire semantic scene and original source immutability. No Blender,
no model call, no partner data and no assumption of building-code compliance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .dxf_revision import export_verified_plan_dxf, import_verified_plan_dxf
from .edit_door import run_move_door
from .schema import plan_sha256, validate_plan

SOURCE_TEXT="SYNTHETIC_ARCH_W2_5000x4000_MM_NC_NO_PARTNER_DATA\n"


def _put_json(path: Path, value: dict):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n",encoding="utf8")


def run(out: Path) -> dict:
    out=Path(out).expanduser().resolve()
    if out.exists():
        raise ValueError("Fresh evidence root is mandatory")
    out.mkdir(parents=True, mode=0o700)
    source=out/"synthetic-source.txt"
    source.write_text(SOURCE_TEXT,encoding="utf8")
    source_digest=hashlib.sha256(source.read_bytes()).hexdigest()
    original={
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001","source_sha256":source_digest,
        "walls":[
            {"id":"wall_001","start_mm":[0,0],"end_mm":[5000,0],
             "thickness_mm":150,"locked":False,"structural_status":"non_load_bearing"},
            {"id":"wall_002","start_mm":[5000,0],"end_mm":[5000,4000],
             "thickness_mm":150,"locked":True,"structural_status":"unknown"},
            {"id":"wall_003","start_mm":[5000,4000],"end_mm":[0,4000],
             "thickness_mm":150,"locked":True,"structural_status":"unknown"},
            {"id":"wall_004","start_mm":[0,4000],"end_mm":[0,0],
             "thickness_mm":150,"locked":True,"structural_status":"unknown"},
        ],
        "openings":[
            {"id":"door_001","kind":"door","host_wall_id":"wall_001",
             "offset_mm":1200,"width_mm":900,"locked":False},
            {"id":"window_001","kind":"window","host_wall_id":"wall_002",
             "offset_mm":500,"width_mm":900,"locked":True},
        ],
    }
    original=validate_plan(original)
    original_plan=out/"original-plan.json"
    _put_json(original_plan,original)
    original_json_sha=hashlib.sha256(original_plan.read_bytes()).hexdigest()
    before_dxf=export_verified_plan_dxf(original,out/"before.dxf")
    if import_verified_plan_dxf(out/"before.dxf")!=original:
        raise ValueError("Original DXF independent reopen failed")
    patch={
        "schema_version":1,"operation_id":"move_door_300mm_01",
        "operation_type":"move_door","target_id":"door_001",
        "expected_plan_sha256":plan_sha256(original),
        "expected_offset_mm":1200,"delta_mm":300,
    }
    _put_json(out/"typed-patch.json",patch)
    transaction=run_move_door(original_plan,patch,out/"transaction")
    if transaction["status"]!="ACCEPTED":
        raise ValueError("Real 300 mm door move did not pass independent DXF readback")
    after=import_verified_plan_dxf(out/"transaction"/"candidate.dxf")
    if not (
        after["openings"][0]["offset_mm"]==1500 and
        after["walls"]==original["walls"] and
        after["openings"][1:]==original["openings"][1:] and
        after["openings"][0]["width_mm"]==900 and
        after["openings"][0]["host_wall_id"]=="wall_001" and
        after["source_sha256"]==source_digest and
        hashlib.sha256(original_plan.read_bytes()).hexdigest()==original_json_sha
    ):
        raise ValueError("Observed non-target mutation or lost source provenance")
    # Multiple disjoint roots and SHA inventory: no large evidence in Git.
    artifacts=[]
    for path in sorted(out.rglob("*")):
        if path.is_file():
            rel=str(path.relative_to(out))
            artifacts.append({
                "path":rel,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes":path.stat().st_size,
            })
    report={
        "schema_version":1,
        "experiment":"ARCHITECTURE_W2_SYNTHETIC_MOVE_DOOR_V1",
        "status":"PASS_EXACT_SYNTHETIC_DXF_MOVE_AND_ROLLBACK",
        "actual_dxf_roundtrip":True,
        "real_partner_dxf":False,
        "real_mac_run":None, # runner evidence is provided by actual CI, not claimed here
        "before_dxf_sha256":before_dxf["export_dxf_sha256"],
        "after_dxf_sha256":transaction["dxf_export"]["export_dxf_sha256"],
        "before_plan_sha256":plan_sha256(original),
        "after_plan_sha256":plan_sha256(after),
        "move_mm":300,
        "unrelated_walls_unchanged":True,
        "unrelated_openings_unchanged":True,
        "source_bytes_unchanged":True,
        "new_model_calls":0,
        "model_cost_usd":"0",
        "native_blender_executed":False,
        "normative_code_compliance":"UNKNOWN_NOT_CHECKED",
        "artifacts":artifacts,
    }
    _put_json(out/"e2e-manifest.json",report)
    return report


def main(argv=None)->int:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        result=run(a.out)
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(json.dumps({"status":"FAILED","error_class":type(exc).__name__}))
        return 2
    print(json.dumps({x:result[x] for x in (
        "experiment","status","move_mm","new_model_calls",
        "unrelated_walls_unchanged","unrelated_openings_unchanged"
    )}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
