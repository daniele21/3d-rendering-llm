"""Read-only, bounded tool interface for architectural AI planning (E0).

These tools never execute model-generated code, commit CAD edits or expose
held-out expected geometry. They distinguish unknown structural state from
permission to modify. Mutation is an explicit future dependency on D0.
"""
from __future__ import annotations

from .schema import PlanReject, plan_summary, validate_plan


class ToolCallReject(PlanReject):
    pass


TOOLS = (
    {
        "name":"get_plan_summary",
        "description":(
            "Understand the current measured plan and its revision before planning "
            "a change. Returns counts, stable revision identity and limitations. "
            "Never infer room topology or missing dimensions."
        ),
        "parameters":{"type":"object","additionalProperties":False,"properties":{}},
    },
    {
        "name":"inspect_entities",
        "description":(
            "Inspect up to five specific wall/opening IDs before proposing changes. "
            "Use when a reference such as 'this wall' is ambiguous, or to verify "
            "the target and hosted opening; do not request all entities speculatively. "
            "Missing IDs return a typed error, not guessed geometry."
        ),
        "parameters":{
            "type":"object","additionalProperties":False,
            "properties":{
                "entity_ids":{
                    "type":"array","minItems":1,"maxItems":5,"uniqueItems":True,
                    "items":{"type":"string","maxLength":48}
                },
            },"required":["entity_ids"]
        },
    },
    {
        "name":"query_constraints",
        "description":(
            "Check whether an existing door is on a documented, explicitly "
            "non-load-bearing and unlocked host wall; return geometry and "
            "unknown facts separately. UNKNOWN structural status requires "
            "human review, not an automatic permission to create a new opening."
        ),
        "parameters":{
            "type":"object","additionalProperties":False,
            "properties":{"target_id":{"type":"string","maxLength":48}},
            "required":["target_id"],
        },
    },
)


def _checked_args(name: str, args: object) -> dict:
    allowed={tool["name"] for tool in TOOLS}
    if type(name) is not str or name not in allowed:
        raise ToolCallReject("Unsupported or mutation-capable tool")
    if type(args) is not dict:
        raise ToolCallReject("Tool parameters must be JSON object")
    if name=="get_plan_summary":
        if args:
            raise ToolCallReject("Summary tool takes no arguments")
    elif name=="inspect_entities":
        if set(args)!={"entity_ids"}:
            raise ToolCallReject("Inspect requires entity_ids only")
        ids=args["entity_ids"]
        if (type(ids) is not list or not 1<=len(ids)<=5 or
                any(type(i) is not str or not 1<=len(i)<=48 for i in ids)
                or len(set(ids))!=len(ids)):
            raise ToolCallReject("Inspect IDs must be one to five unique stable strings")
    elif name=="query_constraints":
        if set(args)!={"target_id"} or type(args["target_id"]) is not str:
            raise ToolCallReject("query_constraints requires target_id only")
    return args


def invoke_read_tool(plan: dict, name: str, args: dict) -> dict:
    data=validate_plan(plan)
    _checked_args(name,args)
    if name=="get_plan_summary":
        return {"status":"PASS","result":plan_summary(data),
                "assurance":"MEASURED_PLAN_SCHEMA_ONLY_NOT_NORMATIVE_COMPLIANCE"}
    by_id={x["id"]:("wall",x) for x in data["walls"]}
    by_id.update({x["id"]:("opening",x) for x in data["openings"]})
    if name=="inspect_entities":
        ids=args["entity_ids"]
        unknown=[i for i in ids if i not in by_id]
        if unknown:
            return {"status":"FAIL","error_code":"UNKNOWN_ENTITY_IDS",
                    "unknown_ids":unknown,"objects":[]}
        return {"status":"PASS","objects":[
            {"kind":by_id[i][0],"data":by_id[i][1]} for i in ids]}
    ident=args["target_id"]
    if ident not in by_id or by_id[ident][0]!="opening":
        return {"status":"FAIL","error_code":"OPENING_NOT_FOUND","target_id":ident}
    opening=by_id[ident][1]
    wall=by_id[opening["host_wall_id"]][1]
    authorization=(
        opening["kind"]=="door" and not opening["locked"] and
        not wall["locked"] and wall["structural_status"]=="non_load_bearing"
    )
    return {
        "status":"PASS" if authorization else "UNKNOWN_REQUIRES_REVIEW",
        "target_id":ident,
        "opening_kind":opening["kind"],
        "host_wall_id":wall["id"],
        "source_revision":data["revision_id"],
        "geometry":{
            "offset_mm":opening["offset_mm"],"width_mm":opening["width_mm"],
            "wall_start_mm":wall["start_mm"],"wall_end_mm":wall["end_mm"]
        },
        "facts":{
            "opening_locked":opening["locked"],
            "host_wall_locked":wall["locked"],
            "host_structural_status":wall["structural_status"]
        },
        "authorized_for_automatic_move":authorization,
        "building_code_compliance":"UNKNOWN_NOT_CHECKED",
    }
