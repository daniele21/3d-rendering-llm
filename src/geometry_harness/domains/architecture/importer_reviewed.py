"""Supervised, lossless-in-scope ingest of *unannotated* straight-line DXF plans.

ezdxf parses real model-space LINE entities. Wall/opening meanings are NEVER
inferred from visual proximity or LLM guesses: operator supplies an explicit
source-SHA-bound host map for *every* opening. This adapter only reads a very
narrow LINE-layer subset, leaves all walls/openings locked, and labels the
result PENDING_HUMAN_CONFIRMATION. It does not mutate an arbitrary input DXF,
does not extract architectural compliance or certify structural safety.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .geometry_math import project_on_wall
from .importer_ezdxf import (
    DXFAdapterReject, _mm, _wall_from_segment, DXF_UNITS_MM, MAX_DXF_BYTES
)
from .schema import validate_plan

LAYERS={"A-WALL":"wall","WALLS":"wall","A-DOOR":"door","A-WINDOW":"window"}
OPEN_KINDS={"door","window"}


def _map_contract(source_hash: str, mapping: dict) -> dict:
    if (type(mapping) is not dict or set(mapping) !=
            {"schema_version","source_sha256","opening_hosts","review_ticket_id"}
            or type(mapping["schema_version"]) is not int or
            mapping["schema_version"]!=1 or
            mapping["source_sha256"]!=source_hash or
            type(mapping["review_ticket_id"]) is not str or
            not 1<=len(mapping["review_ticket_id"])<=64 or
            not all(c.isalnum() or c in "_-" for c in mapping["review_ticket_id"])):
        raise DXFAdapterReject("Invalid, stale or unreviewable DXF host-mapping contract")
    hosts=mapping["opening_hosts"]
    if (type(hosts) is not dict or len(hosts)>256 or
            any(type(k) is not str or not 1<=len(k)<=32
                or not all(ch in "0123456789ABCDEFabcdef" for ch in k)
                or type(v) is not str for k,v in hosts.items())):
        raise DXFAdapterReject("Invalid explicit opening hosts")
    return hosts


def import_supervised_line_plan(path: Path, mapping: dict,
                                *, thickness_mm: int) -> dict:
    """Return PlanScene plus review evidence, never permission to edit.

    The accepted geometry is a thin subset of unannotated CAD LINE drawings:
    door/window LINE segments must run along an explicit host wall and have
    endpoints within 1 mm. More complex symbols/blocks require independent
    recognition with a human-reviewed mapping; unsupported inputs reject.
    """
    path=Path(path).expanduser()
    if (path.is_symlink() or not path.is_file() or
            not 1<=path.stat().st_size<=MAX_DXF_BYTES):
        raise DXFAdapterReject("Missing, symlinked or oversized input DXF")
    if type(thickness_mm) is not int or not 50<=thickness_mm<=1000:
        raise DXFAdapterReject("Explicit bounded wall thickness required")
    source=path.read_bytes()
    source_sha=hashlib.sha256(source).hexdigest()
    host_map=_map_contract(source_sha,mapping)
    try:
        import ezdxf
    except ImportError:
        raise DXFAdapterReject("Pinned ezdxf==1.4.5 optional dependency required") from None
    try:
        doc=ezdxf.readfile(str(path))
    except (OSError,ValueError,ezdxf.DXFError) as exc:
        raise DXFAdapterReject(f"Unable to parse DXF: {type(exc).__name__}") from None
    units=doc.header.get("$INSUNITS")
    if type(units) is not int or units not in DXF_UNITS_MM:
        raise DXFAdapterReject("Source DXF requires explicit INSUNITS")
    factor=DXF_UNITS_MM[units]
    rows=list(doc.modelspace())
    if not 1<=len(rows)<=384:
        raise DXFAdapterReject("Unsupported modelspace entity count")
    if len(rows)>128+256:
        raise DXFAdapterReject("Source exceeds bounded semantic entity count")
    walls,opens=[],[]
    seen=set()
    for e in rows:
        if e.dxftype()!="LINE" or e.dxf.layer not in LAYERS:
            raise DXFAdapterReject("Unsupported entity/layer requires specialist review")
        handle=e.dxf.handle
        if (type(handle) is not str or not handle or len(handle)>32 or
                any(ch not in "0123456789ABCDEFabcdef" for ch in handle) or
                handle.upper() in seen):
            raise DXFAdapterReject("Missing or duplicate source LINE handle")
        seen.add(handle.upper())
        a=e.dxf.start;b=e.dxf.end
        if _mm(a[2],factor,"z0")!=0 or _mm(b[2],factor,"z1")!=0:
            raise DXFAdapterReject("Nonplanar DXF source")
        aa=[_mm(a[i],factor,"start") for i in (0,1)]
        bb=[_mm(b[i],factor,"end") for i in (0,1)]
        kind=LAYERS[e.dxf.layer]
        if kind=="wall":
            walls.append(_wall_from_segment(a,b,factor,handle,1,thickness_mm))
        else:
            opens.append((handle.upper(),kind,aa,bb))
    if not 1<=len(walls)<=128 or len(opens)>256:
        raise DXFAdapterReject("Unsupported wall/opening count")
    actual_handles={x[0] for x in opens}
    provided={k.upper() for k in host_map}
    if len(provided)!=len(host_map) or provided!=actual_handles:
        raise DXFAdapterReject("Each opening requires exactly one explicit host mapping")
    hosts={k.upper():v for k,v in host_map.items()}
    wall_lookup={w["id"]:w for w in walls}
    openings=[]
    for handle,kind,a,b in opens:
        host=hosts[handle]
        if host not in wall_lookup:
            raise DXFAdapterReject("Opening mapping references unknown source wall ID")
        w=wall_lookup[host]
        pa=project_on_wall(w["start_mm"],w["end_mm"],a,max_lateral_mm=1)
        pb=project_on_wall(w["start_mm"],w["end_mm"],b,max_lateral_mm=1)
        if pa["status"]!="PASS" or pb["status"]!="PASS":
            raise DXFAdapterReject("Opening LINE does not lie on reviewed host wall")
        first=pa["projected_offset_mm"]
        last=pb["projected_offset_mm"]
        offset=min(first,last);end=max(first,last)
        if abs(first-round(first))>0.01 or abs(last-round(last))>0.01:
            raise DXFAdapterReject("Ambiguous non-mm opening position")
        offset=int(round(offset));width=int(round(end))-offset
        if not 100<=width<=5000:
            raise DXFAdapterReject("Invalid opening extent/width")
        openings.append({
            "id":f"{kind}_{handle}","kind":kind,"host_wall_id":host,
            "offset_mm":offset,"width_mm":width,"locked":True,
        })
    scene=validate_plan({
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":"rev_001","source_sha256":source_sha,
        "walls":walls,"openings":openings,
    })
    return {
        "plan":scene,
        "mapping_status":"PENDING_HUMAN_CONFIRMATION",
        "review_ticket_id":mapping["review_ticket_id"],
        "source_sha256":source_sha,
        "source_dxf_not_modified":hashlib.sha256(path.read_bytes()).hexdigest()==source_sha,
        "wall_count":len(walls),"opening_count":len(openings),
        "authorizes_edit":False,
        "unmodeled_3d":"UNKNOWN",
        "source_format":"STRICT_UNANNOTATED_LINE_DXF",
        "model_calls":0,
    }
