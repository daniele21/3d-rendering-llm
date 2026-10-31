"""Fail-closed agent proposal gateway to the audited CAD transaction engine.

The LLM can suggest ONLY a bounded typed patch, never Python, DXF commands,
revisions, or an approval. Host adds revision-bound preconditions and calls
the audited D0 dry-run. A separate caller/user approval is required before
run_move_door() may be invoked; this module exposes no commit tool.
"""
from __future__ import annotations

import json
import re

from .agent_tools import TOOLS, invoke_read_tool
from .edit_door import CADPatchReject, preflight_move_door
from .schema import plan_sha256, validate_plan

MAX_PROPOSAL_BYTES=2048
PROPOSAL_KEYS=frozenset({"schema_version","operation_type","target_id","delta_mm"})
OPERATIONS=frozenset({"move_door"})


def proposed_mutation_tool() -> dict:
    """Tool spec for machine-readable proposals, NOT direct CAD execution."""
    return {
        "name":"propose_patch",
        "description":(
            "After inspecting the plan revision, propose one local bounded door "
            "translation (signed integer millimeters, nonzero, magnitude <=1000). "
            "Use inspect_entities and query_constraints first if the door/host "
            "is ambiguous or may be locked. A proposed patch is NOT executed; "
            "the host validates it and requires independent approval before commit. "
            "Never invent a structural classification, wall or door ID."
        ),
        "parameters":{
            "type":"object","additionalProperties":False,
            "properties":{
                "schema_version":{"type":"integer","enum":[1]},
                "operation_type":{"type":"string","enum":["move_door"]},
                "target_id":{"type":"string","minLength":1,"maxLength":48},
                "delta_mm":{"type":"integer","minimum":-1000,"maximum":1000},
            },
            "required":["schema_version","operation_type","target_id","delta_mm"],
        },
    }


def agent_tool_contracts() -> list[dict]:
    """Only 4 model-visible tools. No commit/export/rollback exposed to LLM."""
    return [*TOOLS, proposed_mutation_tool()]


def _read_json_no_duplicate_keys(pairs):
    data={}
    for key,value in pairs:
        if key in data:
            raise CADPatchReject("Duplicate proposal JSON key")
        data[key]=value
    return data


def parse_proposal_json(payload: str) -> dict:
    if type(payload) is not str or not 1<=len(payload.encode("utf-8"))<=MAX_PROPOSAL_BYTES:
        raise CADPatchReject("Bounded JSON proposal payload required")
    try:
        parsed=json.loads(
            payload,object_pairs_hook=_read_json_no_duplicate_keys,
            parse_constant=lambda x: (_ for _ in ()).throw(CADPatchReject("Nonfinite JSON"))
        )
    except (ValueError,TypeError,OverflowError,UnicodeError) as exc:
        raise CADPatchReject(f"Invalid proposal: {type(exc).__name__}") from exc
    if type(parsed) is not dict or set(parsed)!=PROPOSAL_KEYS:
        raise CADPatchReject("Only exact allowlisted proposal keys are accepted")
    if (type(parsed["schema_version"]) is not int or parsed["schema_version"]!=1
            or type(parsed["operation_type"]) is not str or
            parsed["operation_type"] not in OPERATIONS
            or type(parsed["target_id"]) is not str or not
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}",parsed["target_id"])
            or type(parsed["delta_mm"]) is not int or
            not 1<=abs(parsed["delta_mm"])<=1000):
        raise CADPatchReject("Unsupported proposal, target or integer-mm magnitude")
    return parsed


def validate_model_proposal(plan: dict, payload: str,
                            *, host_operation_id: str) -> dict:
    """Read-only D0 preflight; never writes output or commits CAD.

    The host-generated operation ID must not originate in the model output.
    Invalid proposals return typed FAIL and no candidate, for bounded
    repair feedback or human clarification. Caller chooses approval workflow.
    """
    source=validate_plan(plan)
    proposal=parse_proposal_json(payload)
    matches=[x for x in source["openings"] if x["id"]==proposal["target_id"]]
    if len(matches)!=1 or matches[0]["kind"]!="door":
        raise CADPatchReject("Proposed target is not a documented door")
    patch={
        "schema_version":1,
        "operation_id":host_operation_id,
        "operation_type":"move_door",
        "target_id":proposal["target_id"],
        "expected_plan_sha256":plan_sha256(source),
        "expected_offset_mm":matches[0]["offset_mm"],
        "delta_mm":proposal["delta_mm"],
    }
    candidate,evidence=preflight_move_door(source,patch)
    return {
        "status":"VALIDATED_PROPOSAL_NOT_COMMITTED",
        "patch":patch,
        "candidate_plan_sha256":plan_sha256(candidate),
        "validation":{
            "geometry_status":evidence["geometry_gate"]["status"],
            "non_targets_unchanged":True,
            "requires_host_approval":True,
            "code_compliance":"UNKNOWN_NOT_CHECKED",
        },
        "model_calls":0,
    }
