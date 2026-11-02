"""Exact integer-mm 2D CAD predicates independent of any LLM or CAD backend.

Pure mathematical functions only; no geometry inference or side effects.
For nonrectilinear plans, robust topology will be delegated to a pinned
Shapely/GEOS adapter in C1, not implemented with ad-hoc heuristics here.
"""
from __future__ import annotations

from math import isqrt

MAX_COORD_MM = 1_000_000


class GeometryReject(ValueError):
    pass


def _point(p, name: str) -> tuple[int, int]:
    if (type(p) not in (list, tuple) or len(p) != 2
            or any(type(x) is not int or abs(x) > MAX_COORD_MM for x in p)):
        raise GeometryReject(f"{name}: expected bounded integer-mm (x,y)")
    return (p[0], p[1])


def _segment(start, end) -> tuple[tuple[int,int],tuple[int,int],int]:
    a = _point(start, "segment.start")
    b = _point(end, "segment.end")
    dx,dy = b[0]-a[0], b[1]-a[1]
    sq = dx*dx+dy*dy
    if not 100*100 <= sq <= 30000*30000:
        raise GeometryReject("wall length must be 100..30000 mm")
    return a,b,sq


def opening_on_wall(start, end, *, offset_mm, width_mm, margin_mm=0) -> dict:
    """Check an opening range without modifying CAD geometry.

    Integer squared-distance avoids accepting an opening outside a host wall.
    margin=0 allows intervals to meet ends or another opening exactly.
    """
    a,b,length_sq = _segment(start, end)
    for label,val,lo,hi in (
        ("offset_mm",offset_mm,0,30000),
        ("width_mm",width_mm,100,5000),
        ("margin_mm",margin_mm,0,5000)):
        if type(val) is not int or not lo <= val <= hi:
            raise GeometryReject(f"{label} outside safe integer range")
    required = offset_mm + width_mm + margin_mm
    # Exact comparison of rational squared lengths. Avoid sqrt precision.
    within = offset_mm >= margin_mm and required*required <= length_sq
    return {
        "status": "PASS" if within else "FAIL",
        "code": "OPENING_WITHIN_WALL" if within else "OPENING_EXCEEDS_HOST_WALL",
        "length_mm": round(length_sq**.5, 6),
        "offset_mm": offset_mm, "width_mm": width_mm, "margin_mm": margin_mm,
    }


def project_on_wall(start, end, point, *, max_lateral_mm=1) -> dict:
    """Project an already measured point onto a segment, without guessing units.

    All validity decisions use integer squared distances. The returned
    longitudinal offset is a *measurement*, not a tool-authorized modification.
    """
    a,b,sq = _segment(start, end)
    p=_point(point,"point")
    if type(max_lateral_mm) is not int or not 0<=max_lateral_mm<=1000:
        raise GeometryReject("Invalid projection tolerance")
    dx,dy=b[0]-a[0],b[1]-a[1]
    ex,ey=p[0]-a[0],p[1]-a[1]
    dot=ex*dx+ey*dy
    cross=ex*dy-ey*dx
    on_segment=0<=dot<=sq
    near_line=cross*cross <= max_lateral_mm*max_lateral_mm*sq
    return {
        "status": "PASS" if on_segment and near_line else "FAIL",
        "code": "ON_HOST_WALL" if on_segment and near_line else "OFF_HOST_WALL",
        "projected_offset_mm": round(dot / (sq**.5), 6),
        "lateral_distance_mm": round(abs(cross)/(sq**.5), 6),
        "within_segment": on_segment,
    }


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def segments_relation(a_start,a_end,b_start,b_end) -> str:
    """Return NONE/TOUCH/CROSS/COLLINEAR_OVERLAP for bounded segments."""
    a=_point(a_start,"a_start"); b=_point(a_end,"a_end")
    c=_point(b_start,"b_start"); d=_point(b_end,"b_end")
    if a==b or c==d:
        raise GeometryReject("Zero-length segment")
    o1,o2,o3,o4 = _cross(a,b,c),_cross(a,b,d),_cross(c,d,a),_cross(c,d,b)

    def within(p,q,r):
        return min(p[0],q[0])<=r[0]<=max(p[0],q[0]) and min(p[1],q[1])<=r[1]<=max(p[1],q[1])

    if o1==o2==o3==o4==0:
        if not (max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0])) and
                max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1]))):
            return "NONE"
        # Distinguish intersection of positive length from endpoint touch.
        axis = 0 if abs(b[0]-a[0])>=abs(b[1]-a[1]) else 1
        overlap = min(max(a[axis],b[axis]),max(c[axis],d[axis])) - max(min(a[axis],b[axis]),min(c[axis],d[axis]))
        return "COLLINEAR_OVERLAP" if overlap>0 else "TOUCH"
    if o1*o2<0 and o3*o4<0:
        return "CROSS"
    if (o1==0 and within(a,b,c) or o2==0 and within(a,b,d)
            or o3==0 and within(c,d,a) or o4==0 and within(c,d,b)):
        return "TOUCH"
    return "NONE"


def room_topology_status(vertices) -> dict:
    """Only validate an EXPLICIT polygon; never infer rooms from wall lines."""
    if vertices is None:
        return {"status":"UNKNOWN","code":"ROOM_BOUNDARY_NOT_PROVIDED"}
    if type(vertices) not in (list,tuple) or not 4<=len(vertices)<=129:
        return {"status":"FAIL","code":"INVALID_EXPLICIT_ROOM_RING"}
    try:
        pts=[_point(x,"room.vertex") for x in vertices]
    except GeometryReject:
        return {"status":"FAIL","code":"INVALID_EXPLICIT_ROOM_RING"}
    if pts[0]!=pts[-1] or len(set(pts[:-1]))<3:
        return {"status":"FAIL","code":"OPEN_OR_DEGENERATE_ROOM_RING"}
    if any(pts[i]==pts[i+1] for i in range(len(pts)-1)):
        return {"status":"FAIL","code":"DUPLICATE_ROOM_EDGE"}
    area2 = sum(
        pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1]
        for i in range(len(pts)-1)
    )
    if area2==0:
        return {"status":"FAIL","code":"ZERO_AREA_ROOM"}
    for i in range(len(pts)-1):
        for j in range(i+1,len(pts)-1):
            if abs(i-j)<=1 or (i==0 and j==len(pts)-2):
                continue
            if segments_relation(pts[i],pts[i+1],pts[j],pts[j+1])!="NONE":
                return {"status":"FAIL","code":"SELF_INTERSECTING_ROOM"}
    return {"status":"PASS","code":"VALID_EXPLICIT_ROOM_RING",
            "area_mm2": abs(area2)//2 if abs(area2)%2==0 else abs(area2)/2}
