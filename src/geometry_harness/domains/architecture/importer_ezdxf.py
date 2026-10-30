"""Optional ezdxf (MIT) wall-only reader into immutable bounded PlanScene.

Reuse mature DXF file parsing, not a second home-grown general DXF grammar.
Fail closed on unsupported model-space entities/layers, floating dimensions,
blocks, curves and ambiguous units. DOES NOT parse openings or infer rooms.
No executable CAD content, external references, or dynamic imports from DXF.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .schema import PlanReject, validate_plan

MAX_DXF_BYTES = 2_000_000
DXF_UNITS_MM = {4: 1.0, 5: 10.0, 6: 1000.0}
WALL_LAYERS = frozenset({"WALLS", "A-WALL"})
ALLOWED_TYPES = frozenset({"LINE", "LWPOLYLINE"})


class DXFAdapterReject(PlanReject):
    pass


def _mm(value, factor: float, name: str) -> int:
    try:
        v=float(value)
    except (ValueError,TypeError,OverflowError):
        raise DXFAdapterReject(f"{name}: invalid numeric coordinate") from None
    if not math.isfinite(v):
        raise DXFAdapterReject(f"{name}: nonfinite coordinate")
    mm = v * factor
    if not math.isfinite(mm) or abs(mm)>1_000_000:
        raise DXFAdapterReject(f"{name}: coordinate outside bounded 1km plan")
    nearest=round(mm)
    if abs(mm-nearest) > 0.01:
        raise DXFAdapterReject(f"{name}: source coordinate exceeds 0.01mm precision tolerance")
    return int(nearest)


def _wall_from_segment(start, end, factor, handle: str, index: int,
                       thickness_mm: int) -> dict:
    a=[_mm(start[0],factor,"x0"),_mm(start[1],factor,"y0")]
    b=[_mm(end[0],factor,"x1"),_mm(end[1],factor,"y1")]
    if (not isinstance(handle,str) or not handle or len(handle)>32
            or not all(c in "0123456789ABCDEFabcdef" for c in handle)):
        raise DXFAdapterReject("Invalid DXF handle for stable wall identity")
    return {
        "id": f"wall_{handle.upper()}_{index}",
        "start_mm": a,"end_mm":b,
        "thickness_mm":thickness_mm,
        "locked":True,
        "structural_status":"unknown"
    }


def _iter_entity_segments(e, factor: float):
    kind=e.dxftype()
    if kind=="LINE":
        start,end=e.dxf.start,e.dxf.end
        if abs(_mm(start[2],factor,"line.z0"))>0 or abs(_mm(end[2],factor,"line.z1"))>0:
            raise DXFAdapterReject("Unsupported nonplanar LINE")
        yield start,end
    elif kind=="LWPOLYLINE":
        if e.closed:
            raise DXFAdapterReject("Closed polyline not yet supported")
        if abs(_mm(e.dxf.elevation,factor,"polyline.elevation"))>0:
            raise DXFAdapterReject("Unsupported elevated polyline")
        points=list(e.get_points("xyseb"))
        if not 2<=len(points)<=64:
            raise DXFAdapterReject("Polyline vertex count out of bounds")
        if any(abs(float(p[2]))>1e-12 or abs(float(p[3]))>1e-12
               or abs(float(p[4]))>1e-12 for p in points):
            raise DXFAdapterReject("Curves/bulges/variable-width polylines unsupported")
        for left,right in zip(points,points[1:]):
            yield left,right
    else:
        raise DXFAdapterReject(f"Unsupported model-space entity: {kind}")


def import_dxf_walls(path: Path, *, wall_thickness_mm: int,
                     revision_id: str = "rev_001") -> dict:
    """Parse supported DXF via ezdxf; produce strict plan with UNKNOWN semantics.

    Requires explicit thickness, not inferred from CAD layer or model text.
    The existing stdlib `dxf_safe` importer is NOT modified or bypassed.
    """
    path=Path(path).expanduser()
    if (path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= MAX_DXF_BYTES):
        raise DXFAdapterReject("Missing, symlinked or oversized DXF input")
    if type(wall_thickness_mm) is not int or not 50<=wall_thickness_mm<=1000:
        raise DXFAdapterReject("Explicit thickness_mm 50..1000 is required")
    original=path.read_bytes()
    sha=hashlib.sha256(original).hexdigest()
    try:
        import ezdxf
    except ImportError:
        raise DXFAdapterReject(
            "Optional ezdxf unavailable: install pinned ezdxf==1.4.5 for this adapter"
        ) from None
    try:
        document=ezdxf.readfile(str(path))
        units=document.header.get("$INSUNITS")
    except (OSError, ValueError, TypeError, ezdxf.DXFError) as exc:
        raise DXFAdapterReject(f"Unparseable DXF: {type(exc).__name__}") from None
    if type(units) is not int or units not in DXF_UNITS_MM:
        raise DXFAdapterReject("Explicit DXF mm/cm/metre INSUNITS required")
    factor=DXF_UNITS_MM[units]
    entities=list(document.modelspace())
    if not 1 <= len(entities) <= 128:
        raise DXFAdapterReject("Require 1..128 bounded model-space entities")
    objects=[]
    for e in entities:
        if e.dxftype() not in ALLOWED_TYPES:
            raise DXFAdapterReject(f"Unsupported model-space entity {e.dxftype()}")
        if e.dxf.layer not in WALL_LAYERS:
            raise DXFAdapterReject(f"Unmapped layer {e.dxf.layer}")
        handle=e.dxf.handle
        for n,(start,end) in enumerate(_iter_entity_segments(e,factor),1):
            if len(objects)>=128:
                raise DXFAdapterReject("Too many parsed walls")
            objects.append(_wall_from_segment(
                start,end,factor,handle,n,wall_thickness_mm
            ))
    candidate={
        "schema_version":1,"units":"mm","coordinate_frame":"local_xy",
        "revision_id":revision_id, "source_sha256":sha,
        "walls":objects,"openings":[],
    }
    return validate_plan(candidate)
