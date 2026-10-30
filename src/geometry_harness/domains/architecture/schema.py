"""Minimal fail-closed architecture 2D PlanScene contract (millimeters).

This is *not* BIM nor a general-purpose CAD schema. It represents only
explicitly measured walls and hosted openings, never inferred rooms.
The source DXF remains immutable and model-authored Python is never run.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

SCHEMA_VERSION = 1
MAX_COORD_MM = 1_000_000
MAX_WALLS = 128
MAX_OPENINGS = 256
ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
STATUSES = frozenset({"unknown", "load_bearing", "non_load_bearing"})
KINDS = frozenset({"door", "window"})


class PlanReject(ValueError):
    """An explicit schema violation; unknown properties are not accepted."""


def _exact_keys(value: Any, required: set[str], optional: set[str] = frozenset(),
                *, label: str) -> dict:
    if type(value) is not dict or not required.issubset(value) or not set(value).issubset(required | optional):
        raise PlanReject(f"{label}: unsupported/missing properties")
    return value


def _int(value: Any, name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise PlanReject(f"{name}: must be bounded integer mm")
    return value


def _id(value: Any, label: str) -> str:
    if type(value) is not str or not ID_PATTERN.fullmatch(value):
        raise PlanReject(f"{label}: invalid stable ID")
    return value


def _point(value: Any, label: str) -> list[int]:
    if (type(value) not in (tuple, list) or len(value) != 2):
        raise PlanReject(f"{label}: require explicit (x,y) mm")
    return [
        _int(value[i], f"{label}[{i}]", -MAX_COORD_MM, MAX_COORD_MM)
        for i in range(2)
    ]


def _wall(raw: Any) -> dict:
    w = _exact_keys(raw, {
        "id", "start_mm", "end_mm", "thickness_mm", "locked", "structural_status",
    }, label="wall")
    start = _point(w["start_mm"], "wall.start_mm")
    end = _point(w["end_mm"], "wall.end_mm")
    length = math.hypot(end[0]-start[0], end[1]-start[1])
    if not 100 <= length <= 30_000:
        raise PlanReject("wall: invalid length 100..30000 mm")
    thickness = _int(w["thickness_mm"], "thickness_mm", 50, 1000)
    if type(w["locked"]) is not bool:
        raise PlanReject("wall.locked: explicit bool required")
    status = w["structural_status"]
    if type(status) is not str or status not in STATUSES:
        raise PlanReject("wall.structural_status: unknown, load_bearing or non_load_bearing")
    return {
        "id": _id(w["id"], "wall.id"),
        "start_mm": start,
        "end_mm": end,
        "thickness_mm": thickness,
        "locked": w["locked"],
        "structural_status": status,
    }


def _opening(raw: Any, walls_by_id: dict) -> dict:
    o = _exact_keys(raw, {
        "id", "kind", "host_wall_id", "offset_mm", "width_mm", "locked",
    }, label="opening")
    host = _id(o["host_wall_id"], "opening.host_wall_id")
    if host not in walls_by_id:
        raise PlanReject(f"opening: unresolved host wall {host}")
    kind = o["kind"]
    if type(kind) is not str or kind not in KINDS:
        raise PlanReject("opening.kind: door or window required")
    offset = _int(o["offset_mm"], "opening.offset_mm", 0, 30_000)
    width = _int(o["width_mm"], "opening.width_mm", 100, 5000)
    if type(o["locked"]) is not bool:
        raise PlanReject("opening.locked: explicit bool required")
    host_wall = walls_by_id[host]
    length = math.hypot(
        host_wall["end_mm"][0] - host_wall["start_mm"][0],
        host_wall["end_mm"][1] - host_wall["start_mm"][1],
    )
    if offset + width > length + 1e-9:
        raise PlanReject("opening extends beyond measured host wall")
    return {
        "id": _id(o["id"], "opening.id"),
        "kind": kind,
        "host_wall_id": host,
        "offset_mm": offset,
        "width_mm": width,
        "locked": o["locked"],
    }


def validate_plan(raw: Any) -> dict:
    """Return canonical JSON-safe scene; never mutate user input.

    A plan with no rooms means room closure/topology is UNKNOWN, not PASS.
    This schema deliberately does not infer room boundaries or demolition
    eligibility from DWG layer naming or lines.
    """
    data = _exact_keys(raw, {
        "schema_version", "units", "coordinate_frame", "revision_id",
        "source_sha256", "walls", "openings",
    }, label="plan")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise PlanReject("Unsupported plan schema version")
    if data["units"] != "mm" or type(data["units"]) is not str:
        raise PlanReject("Plan requires explicit integer millimeters")
    if data["coordinate_frame"] != "local_xy" or type(data["coordinate_frame"]) is not str:
        raise PlanReject("Plan requires local_xy reference frame")
    revision = _id(data["revision_id"], "revision_id")
    sha = data["source_sha256"]
    if type(sha) is not str or not SHA256_PATTERN.fullmatch(sha):
        raise PlanReject("Invalid original source SHA256")
    if (type(data["walls"]) is not list or
            not 1 <= len(data["walls"]) <= MAX_WALLS):
        raise PlanReject("Plan requires 1..128 walls")
    if type(data["openings"]) is not list or len(data["openings"]) > MAX_OPENINGS:
        raise PlanReject("Plan supports 0..256 openings")
    walls = [_wall(x) for x in data["walls"]]
    by_id = {x["id"]: x for x in walls}
    if len(by_id) != len(walls):
        raise PlanReject("Duplicate wall IDs")
    openings = [_opening(x, by_id) for x in data["openings"]]
    opening_ids = [x["id"] for x in openings]
    if len(set(opening_ids)) != len(opening_ids) or set(opening_ids) & set(by_id):
        raise PlanReject("Duplicate/reused stable ID")
    grouped: dict[str, list[tuple[int, int]]] = {}
    for o in openings:
        grouped.setdefault(o["host_wall_id"], []).append(
            (o["offset_mm"], o["offset_mm"]+o["width_mm"])
        )
    for windows in grouped.values():
        ordered = sorted(windows)
        if any(a[1] > b[0] for a,b in zip(ordered, ordered[1:])):
            raise PlanReject("Overlapping hosted openings")
    return {
        "schema_version": SCHEMA_VERSION,
        "units": "mm",
        "coordinate_frame": "local_xy",
        "revision_id": revision,
        "source_sha256": sha,
        "walls": walls,
        "openings": openings,
    }


def plan_sha256(plan: dict) -> str:
    """Stable semantic revision checksum, after strict validation."""
    verified = validate_plan(plan)
    data = json.dumps(verified, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("ascii")).hexdigest()


def plan_summary(plan: dict) -> dict:
    verified = validate_plan(plan)
    return {
        "revision_id": verified["revision_id"],
        "wall_count": len(verified["walls"]),
        "opening_count": len(verified["openings"]),
        "locked_wall_count": sum(x["locked"] for x in verified["walls"]),
        "unknown_structural_count": sum(
            x["structural_status"] == "unknown" for x in verified["walls"]),
        "room_topology": "UNKNOWN_NOT_MODELED",
        "source_sha256": verified["source_sha256"],
        "plan_sha256": plan_sha256(verified),
    }
