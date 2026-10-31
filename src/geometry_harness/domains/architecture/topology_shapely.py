"""Optional Shapely/GEOS topology *assessment* for bounded PlanScene v1.

Reuses Shapely (BSD-3) rather than implementing robust polygon predicates.
Reports uncertain junctions as UNKNOWN, not false acceptance or demolition
permission. Does not infer room polygons, compliance, structure or clearance
from wall centerlines. Always validate the authoritative PlanScene first.
"""
from __future__ import annotations

import math

from .schema import PlanReject, validate_plan

SHAPELY_VERSION = "2.1.2"
MAX_PAIRS = 8128  # <=128 walls
MIN_LINE_MM = 100
TOLERANCE_MM = 0.01


class TopologyReject(PlanReject):
    pass


def _shapely():
    try:
        import shapely
        from shapely.geometry import LineString
    except ImportError:
        raise TopologyReject("Pinned optional Shapely==2.1.2 unavailable") from None
    if shapely.__version__ != SHAPELY_VERSION:
        raise TopologyReject("Unsupported Shapely version; pin 2.1.2")
    return shapely, LineString


def assess_plan_topology(plan: dict) -> dict:
    """Typed evidence, not a silently accepted project.

    FAIL: duplicated/overlapping wall centerline beyond the exact endpoints.
    UNKNOWN: interior-crossing wall junctions can be intentional: human must
    classify them. PASS: measured geometry only, not building-code approval.
    """
    scene = validate_plan(plan)
    shapely,LineString = _shapely()
    walls = scene["walls"]
    lines = [(w["id"],LineString([w["start_mm"], w["end_mm"]])) for w in walls]
    issues=[]
    counts={"PASS":0,"FAIL":0,"UNKNOWN":0}
    for idx,(left_id,left) in enumerate(lines):
        if not left.is_valid or left.is_empty or left.length < MIN_LINE_MM:
            raise TopologyReject(f"Invalid measured wall: {left_id}")
        for right_id,right in lines[idx+1:]:
            if not left.intersects(right):
                continue
            intersection=left.intersection(right)
            if intersection.is_empty:
                continue
            if intersection.length>TOLERANCE_MM:
                code="COINCIDENT_WALL_CENTERLINES"
                status="FAIL"
            elif left.crosses(right):
                code="INTERIOR_WALL_INTERSECTION_REVIEW"
                status="UNKNOWN"
            elif left.touches(right):
                code="WALL_ENDPOINT_JUNCTION"
                status="PASS"
            else:
                # A T junction can be a valid load-bearing/partition
                # connection. We know geometry, not engineering intent.
                code="WALL_T_JUNCTION_REVIEW"
                status="UNKNOWN"
            counts[status]+=1
            issues.append({
                "status":status,"code":code,"entity_ids":[left_id,right_id],
                "intersection_type":intersection.geom_type,
            })
    if counts["FAIL"]:
        aggregate="FAIL"
    elif counts["UNKNOWN"]:
        aggregate="UNKNOWN_REQUIRES_REVIEW"
    else:
        aggregate="PASS_MEASURED_WALL_CENTERLINES"
    return {
        "schema_version":1,
        "status":aggregate,
        "wall_count":len(walls),
        "issues":issues,
        "issue_counts":counts,
        "missing_room_boundaries":"UNKNOWN_NOT_MODELED",
        "structural_safety":"UNKNOWN_NOT_ASSESSED",
        "building_code_compliance":"UNKNOWN_NOT_CHECKED",
        "geometry_library":"shapely",
        "geometry_library_version":shapely.__version__,
        "distance_tolerance_mm":TOLERANCE_MM,
    }


def assess_explicit_room(vertices) -> dict:
    """Shapely validity of an explicitly supplied closed room polygon.

    Unknown boundaries remain UNKNOWN. Invalid rings are not repaired with
    buffer(0) or make_valid; a reviewer must supply corrected geometry.
    """
    if vertices is None:
        return {"status":"UNKNOWN","code":"ROOM_BOUNDARY_NOT_SUPPLIED"}
    if (type(vertices) not in (list,tuple) or not 4<=len(vertices)<=129):
        return {"status":"FAIL","code":"INVALID_ROOM_RING"}
    for point in vertices:
        if (type(point) not in (list,tuple) or len(point)!=2 or
                any(type(v) is not int or abs(v)>1_000_000 for v in point)):
            return {"status":"FAIL","code":"INVALID_ROOM_VERTEX_MM"}
    if vertices[0]!=vertices[-1]:
        return {"status":"FAIL","code":"OPEN_ROOM_RING"}
    shapely,LineString=_shapely()
    from shapely.geometry import Polygon
    polygon=Polygon(vertices)
    if not polygon.is_valid or polygon.is_empty or polygon.area<=1:
        return {"status":"FAIL","code":"ROOM_POLYGON_INVALID"}
    return {"status":"PASS","code":"VALID_EXPLICIT_ROOM_POLYGON",
            "area_mm2":polygon.area,
            "area_m2":polygon.area/1_000_000,
            "geometry_library_version":shapely.__version__}
