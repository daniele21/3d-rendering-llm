"""Typed, read-only geometry diagnostics grounded in observed Blender coordinates.

All numerical requirements must come from an explicit task contract, never
inferred from the model-generated scene itself. Missing evidence is UNKNOWN.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


class ValidationError(ValueError):
    pass


_ALLOWED = {"dimensions", "floor_contact", "vertical_contact"}
_MAX_REQUIREMENTS = 128


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"Invalid finite {label}")
    return float(value)


def _vec(value, label):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValidationError(f"{label} must be a 3-vector")
    return [_number(v, label) for v in value]


def _issue(rule, status, observed=None, reason=None):
    return {
        "issue_id": f"geometry-{rule['id']}",
        "code": rule["type"],
        "status": status,
        "severity": "blocking",
        "affected_ids": [rule[k] for k in ("object_id", "support_id", "supported_id") if k in rule],
        "expected": {k: v for k, v in rule.items() if k not in ("id", "type")},
        "observed": observed,
        "units": "m",
        "tolerance_m": rule.get("tolerance_m", 0.01),
        "repairability": "unknown" if status == "UNKNOWN" else (
            "none" if status == "PASS" else "deterministic_candidate"),
        "reason": reason,
    }


def validate(geometry: dict | None, task_contract: dict) -> dict:
    if not isinstance(task_contract, dict) or task_contract.get("schema_version") != 1:
        raise ValidationError("Task geometry contract must be schema v1")
    if task_contract.get("units") != "m":
        raise ValidationError("Metric metres required: no guessed units")
    requirements = task_contract.get("requirements")
    if not isinstance(requirements, list) or len(requirements) > _MAX_REQUIREMENTS or not requirements:
        raise ValidationError("Bounded nonempty task requirements required")
    ids = set()
    for rule in requirements:
        if not isinstance(rule, dict) or rule.get("type") not in _ALLOWED:
            raise ValidationError("Unsupported geometry requirement")
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.isidentifier() or len(rid) > 64 or rid in ids:
            raise ValidationError("Missing or duplicated requirement ID")
        ids.add(rid)
        tolerance = _number(rule.get("tolerance_m", 0.01), "tolerance")
        if tolerance < 0 or tolerance > 1:
            raise ValidationError("Tolerance must be in [0,1] metres")
        for key in ("object_id", "support_id", "supported_id"):
            if key in rule and (not isinstance(rule[key], str) or not rule[key].isidentifier()):
                raise ValidationError("Unsafe object ID")
        if rule["type"] in {"floor_contact", "dimensions"} and "object_id" not in rule:
            raise ValidationError("Missing object_id")
        if rule["type"] == "dimensions":
            expected = _vec(rule.get("expected_dimensions_m"), "expected dimensions")
            if any(v <= 0 for v in expected):
                raise ValidationError("Expected dimensions must be positive")
        if rule["type"] == "vertical_contact" and (
            not rule.get("support_id") or not rule.get("supported_id")
            or rule["support_id"] == rule["supported_id"]):
            raise ValidationError("Missing distinct support and supported IDs")
    observed: dict[str, dict] = {}
    valid_evidence = isinstance(geometry, dict) and geometry.get("passed") is True
    if valid_evidence and isinstance(geometry.get("mesh_objects"), list):
        try:
            for obj in geometry["mesh_objects"]:
                name = obj["geometry_id"]
                if name != obj["name"] or name in observed:
                    valid_evidence = False
                    break
                center = _vec(obj["center"], "observed center")
                dims = _vec(obj["dimensions"], "observed dimensions")
                if any(v <= 0 for v in dims):
                    valid_evidence = False
                    break
                observed[name] = {"center": center, "dimensions": dims}
        except (TypeError, KeyError, ValidationError):
            valid_evidence = False
    else:
        valid_evidence = False
    results = []
    for rule in requirements:
        tolerance = float(rule.get("tolerance_m", 0.01))
        keys = [rule[k] for k in ("object_id", "support_id", "supported_id") if k in rule]
        if not valid_evidence:
            results.append(_issue(rule, "UNKNOWN", reason="missing_or_untrusted_blender_measurements"))
            continue
        if any(key not in observed for key in keys):
            results.append(_issue(rule, "FAIL", reason="required_mesh_missing"))
            continue
        if rule["type"] == "dimensions":
            obj = observed[rule["object_id"]]
            actual = obj["dimensions"]
            expected = [_number(x, "expected dimensions") for x in rule["expected_dimensions_m"]]
            ok = all(abs(x-y) <= tolerance for x, y in zip(actual, expected))
            results.append(_issue(rule, "PASS" if ok else "FAIL",
                                  observed={"dimensions_m": actual},
                                  reason=None if ok else "dimension_outside_tolerance"))
        elif rule["type"] == "floor_contact":
            obj = observed[rule["object_id"]]
            floor = _number(rule.get("floor_z_m", 0.0), "floor z")
            bottom = obj["center"][2] - obj["dimensions"][2] / 2
            ok = abs(bottom-floor) <= tolerance
            results.append(_issue(rule, "PASS" if ok else "FAIL",
                                  observed={"bottom_z_m": bottom},
                                  reason=None if ok else "floor_gap_or_penetration"))
        else:
            support, target = observed[rule["support_id"]], observed[rule["supported_id"]]
            a = support["center"][2] + support["dimensions"][2]/2
            b = target["center"][2] - target["dimensions"][2]/2
            overlap = all(
                abs(support["center"][i] - target["center"][i]) <=
                (support["dimensions"][i] + target["dimensions"][i])/2 + tolerance
                for i in (0, 1))
            ok = abs(a-b) <= tolerance and overlap
            results.append(_issue(rule, "PASS" if ok else "FAIL",
                                  observed={"support_top_z_m": a, "supported_bottom_z_m": b,
                                            "overlap_xy": overlap},
                                  reason=None if ok else "disconnected_support"))
    statuses = [r["status"] for r in results]
    status = "FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "PASS"
    return {
        "schema_version": 1, "task_contract_id": task_contract.get("task_id"),
        "status": status, "requirements_count": len(results),
        "pass_count": statuses.count("PASS"), "fail_count": statuses.count("FAIL"),
        "unknown_count": statuses.count("UNKNOWN"), "issues": results,
        "read_only": True,
        "warning": "Task-specific geometric checks only; no claim of semantic or visual correctness.",
    }


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geometry", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    contract = json.loads(a.contract.read_text(encoding="utf-8"))
    measured = json.loads(a.geometry.read_text(encoding="utf-8")) if a.geometry.exists() else None
    report = validate(measured, contract)
    if a.out.exists():
        p.error("Refusing to overwrite validation evidence")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in
                      ("status", "pass_count", "fail_count", "unknown_count")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
