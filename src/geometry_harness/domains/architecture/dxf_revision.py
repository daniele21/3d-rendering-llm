"""Audited, round-trippable *explicitly annotated* architectural DXF revision v1.

Only bounded LINE entities in a small 2D plan, with trusted XDATA identifying
semantically measured walls and hosted doors/windows. This is NOT a general
DXF importer or a converter for unannotated real-world CAD.
Uses pinned optional ezdxf (MIT), not a home-made DXF writer.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import tempfile

from .schema import PlanReject, validate_plan, plan_sha256

APPID = "GEOMETRY_HARNESS_PLAN_V1"
MAX_BYTES = 2_000_000
LAYERS = {"wall": "A-WALL", "door": "A-DOOR", "window": "A-WINDOW"}
FINGERPRINT = "ARCHITECTURE_PLAN_XDATA_V1"


class DXFRevisionError(PlanReject):
    pass


def _library():
    try:
        import ezdxf
    except ImportError:
        raise DXFRevisionError("Pinned optional ezdxf==1.4.5 is required") from None
    return ezdxf


def _meta(revision: str, source: str, kind: str, stable_id: str,
          fields: list[tuple[int, object]]) -> list:
    return [(1000, FINGERPRINT), (1000, revision), (1000, source),
            (1000, kind), (1000, stable_id), *fields]


def _tags(entity) -> list:
    try:
        return [(x.code, x.value) for x in entity.get_xdata(APPID)]
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        raise DXFRevisionError("Entity has missing or malformed trusted XDATA") from exc


def _strict_tags(tags: list, *, kind: str) -> tuple[str, str, str, dict]:
    allowed = {
        "wall": [1000,1000,1000,1000,1000,1070,1070,1000],
        "door": [1000,1000,1000,1000,1000,1000,1070,1070,1070],
        "window": [1000,1000,1000,1000,1000,1000,1070,1070,1070],
    }[kind]
    if [t[0] for t in tags] != allowed or tags[0][1] != FINGERPRINT or tags[3][1] != kind:
        raise DXFRevisionError("Untrusted or ambiguous entity XDATA")
    _, revision, source, _, ident = (t[1] for t in tags[:5])
    if kind == "wall":
        obj = {"id": ident, "thickness_mm":tags[5][1],
               "locked": _read_bool(tags[6][1]),"structural_status":tags[7][1]}
    else:
        obj = {"id": ident, "kind": kind,"host_wall_id":tags[5][1],
               "offset_mm":tags[6][1],"width_mm":tags[7][1],
               "locked":_read_bool(tags[8][1])}
    return revision, source, ident, obj


def _read_bool(value: object) -> bool:
    if type(value) is not int or value not in (0, 1):
        raise DXFRevisionError("Invalid DXF XDATA boolean")
    return bool(value)


def _point_xy(point, *, label: str) -> list[int]:
    if not all(math.isfinite(float(v)) for v in (point[0], point[1], point[2])):
        raise DXFRevisionError(f"{label}: nonfinite geometry")
    if abs(float(point[2])) > 0.00001:
        raise DXFRevisionError(f"{label}: nonplanar geometry")
    result=[]
    for value in (point[0],point[1]):
        mm=round(value)
        if abs(value-mm)>0.001 or abs(value)>1_000_000:
            raise DXFRevisionError(f"{label}: not at exact integer-mm coordinate")
        result.append(int(mm))
    return result


def _opening_points(opening: dict, wall: dict) -> tuple[tuple[float,float],tuple[float,float]]:
    (x0,y0),(x1,y1) = wall["start_mm"], wall["end_mm"]
    dx,dy = x1-x0,y1-y0
    distance=math.hypot(dx,dy)
    offset=opening["offset_mm"]
    width=opening["width_mm"]
    return ((x0+dx*offset/distance, y0+dy*offset/distance),
            (x0+dx*(offset+width)/distance, y0+dy*(offset+width)/distance))


def _near(actual, expected: tuple[float,float], *, label: str) -> None:
    if (not all(math.isfinite(float(actual[i])) for i in (0, 1, 2))
            or abs(float(actual[2]))>0.00001
            or abs(actual[0]-expected[0])>0.01
            or abs(actual[1]-expected[1])>0.01):
        raise DXFRevisionError(f"{label}: DXF geometry differs from measured semantic opening")


def _read_doc(path: Path):
    ezdxf=_library()
    path=Path(path).expanduser()
    if (path.is_symlink() or not path.is_file()
            or not 1<=path.stat().st_size<=MAX_BYTES):
        raise DXFRevisionError("Invalid or oversized source DXF")
    try:
        doc=ezdxf.readfile(str(path))
    except (OSError, ValueError, ezdxf.DXFError) as exc:
        raise DXFRevisionError(f"Unparseable DXF: {type(exc).__name__}") from None
    if doc.header.get("$INSUNITS") != 4:
        raise DXFRevisionError("Annotated DXF must declare exact millimeter units")
    if APPID not in doc.appids:
        raise DXFRevisionError("Missing semantic XDATA application identifier")
    entities=list(doc.modelspace())
    if not 1<=len(entities)<=384:
        raise DXFRevisionError("Unsupported DXF entity count")
    return entities


def import_verified_plan_dxf(path: Path) -> dict:
    """Independent read: require exact backed geometry and all semantic tags."""
    entities=_read_doc(path)
    walls,openings=[],[]
    revision=source=None
    observed=[]
    for entity in entities:
        if entity.dxftype()!="LINE":
            raise DXFRevisionError("Only annotated 2D LINE entities supported")
        kind={v:k for k,v in LAYERS.items()}.get(entity.dxf.layer)
        if kind is None:
            raise DXFRevisionError("Unmapped CAD layer")
        tags=_tags(entity)
        vrev,vsrc,ident,obj=_strict_tags(tags,kind=kind)
        if revision is None:
            revision,source=vrev,vsrc
        elif revision!=vrev or source!=vsrc:
            raise DXFRevisionError("Mixed revision or source provenance")
        if kind=="wall":
            obj["start_mm"]=_point_xy(entity.dxf.start,label="wall.start")
            obj["end_mm"]=_point_xy(entity.dxf.end,label="wall.end")
            walls.append(obj)
        else:
            observed.append((entity.dxf.start,entity.dxf.end,obj))
            openings.append(obj)
    candidate = validate_plan({
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":revision,"source_sha256":source,
        "walls":walls,"openings":openings,
    })
    wall_by_id={w["id"]:w for w in candidate["walls"]}
    for actual_start,actual_end,opening in observed:
        exp_start,exp_end=_opening_points(opening,wall_by_id[opening["host_wall_id"]])
        _near(actual_start,exp_start,label=f"{opening['id']} start")
        _near(actual_end,exp_end,label=f"{opening['id']} end")
    return candidate


def export_verified_plan_dxf(plan: dict, path: Path) -> dict:
    """Create a NEW editable DXF and independently reopen; no overwrites."""
    source=validate_plan(plan)
    path=Path(path).expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise DXFRevisionError("Refuse to overwrite existing DXF")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise DXFRevisionError("A trusted existing output parent is required")
    ezdxf=_library()
    doc=ezdxf.new("R2010")
    doc.header["$INSUNITS"]=4
    doc.appids.new(APPID)
    for layer in LAYERS.values():
        if layer not in doc.layers:
            doc.layers.new(layer)
    model=doc.modelspace()
    revision,provenance=source["revision_id"],source["source_sha256"]
    for wall in source["walls"]:
        line=model.add_line((*wall["start_mm"],0),(*wall["end_mm"],0),
                            dxfattribs={"layer":LAYERS["wall"]})
        line.set_xdata(APPID,_meta(revision,provenance,"wall",wall["id"],[
            (1070,wall["thickness_mm"]),(1070,int(wall["locked"])),
            (1000,wall["structural_status"]),
        ]))
    wall_by_id={w["id"]:w for w in source["walls"]}
    for op in source["openings"]:
        start,end=_opening_points(op,wall_by_id[op["host_wall_id"]])
        line=model.add_line((*start,0),(*end,0),
                            dxfattribs={"layer":LAYERS[op["kind"]]})
        line.set_xdata(APPID,_meta(revision,provenance,op["kind"],op["id"],[
            (1000,op["host_wall_id"]),(1070,op["offset_mm"]),
            (1070,op["width_mm"]),(1070,int(op["locked"])),
        ]))
    fd,name=tempfile.mkstemp(prefix=".architecture-",suffix=".dxf",dir=path.parent)
    os.close(fd)
    temporary=Path(name)
    try:
        doc.saveas(temporary)
        if temporary.stat().st_size>MAX_BYTES:
            raise DXFRevisionError("Encoded DXF exceeds bounded source size")
        replay=import_verified_plan_dxf(temporary)
        if replay!=source or plan_sha256(replay)!=plan_sha256(source):
            raise DXFRevisionError("Independent DXF semantic reopen differs")
        if path.exists() or path.is_symlink():
            raise DXFRevisionError("Concurrent output collision")
        temporary.chmod(0o600)
        os.link(temporary,path)  # exclusive create, never replace existing file
        result={
            "status":"DXF_ROUNDTRIP_PASS",
            "format":"DXF_R2010_ANNOTATED_V1",
            "entity_count":len(source["walls"])+len(source["openings"]),
            "source_plan_sha256":plan_sha256(source),
            "readback_plan_sha256":plan_sha256(replay),
            "export_dxf_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes":path.stat().st_size,
            "output_path":str(path),
            "model_calls":0,
            "third_party_library":"ezdxf",
        }
        return result
    finally:
        temporary.unlink(missing_ok=True)
