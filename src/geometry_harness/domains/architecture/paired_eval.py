"""Offline paired CAD-agent benchmark scorer; never calls an LLM.

Implements evidence/instruction separation, failure-inclusive denominator and
model-id caveats for early architecture A/B. External model responses without
authenticated provider traces are REPLAY_UNVERIFIED, never live model proof.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .agent_patch_gateway import validate_model_proposal
from .edit_door import CADPatchReject
from .schema import validate_plan

MODEL_KEYS=("qwen_local","luna_cloud")
MAX_CASES=32


class PairedEvalReject(ValueError):
    pass


def _sha_json(x: dict) -> str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode("utf8")).hexdigest()


def split_public_private(cases: list[dict]) -> tuple[list[dict],list[dict]]:
    """Freeze task instructions separate from private scoring expectations."""
    if (type(cases) is not list or not 1<=len(cases)<=MAX_CASES):
        raise PairedEvalReject("Expected bounded test cases")
    public,private=[],[]
    seen=set()
    for item in cases:
        if (type(item) is not dict or set(item)!=
                {"task_id","instruction","plan","expected_outcome",
                 "expected_target","expected_delta_mm"}):
            raise PairedEvalReject("Malformed task with ambiguous oracle")
        tid=item["task_id"]
        if (type(tid) is not str or not tid.startswith("arch_") or
                tid in seen or type(item["instruction"]) is not str
                or not 20<=len(item["instruction"])<=400):
            raise PairedEvalReject("Invalid task identity/instructions")
        seen.add(tid)
        plan=validate_plan(item["plan"])
        expected=item["expected_outcome"]
        if (expected not in {"EDIT","REVIEW"} or
                type(item["expected_target"]) is not str or
                type(item["expected_delta_mm"]) is not int or
                not -1000<=item["expected_delta_mm"]<=1000):
            raise PairedEvalReject("Invalid hidden scoring oracle")
        public.append({"task_id":tid,"instruction":item["instruction"],
                       "plan":plan})
        private.append({"task_id":tid,"expected_outcome":expected,
                        "expected_target":item["expected_target"],
                        "expected_delta_mm":item["expected_delta_mm"]})
    return public,private


def _read_model_action(action_text: str) -> dict:
    if type(action_text) is not str or not 1<=len(action_text.encode("utf8"))<=2048:
        return {"kind":"INVALID_RESPONSE"}
    try:
        data=json.loads(action_text)
    except (ValueError,UnicodeError):
        return {"kind":"INVALID_RESPONSE"}
    if (type(data) is dict and
            set(data)=={"schema_version","decision","reason_code"} and
            data["schema_version"]==1 and data["decision"]=="review_required" and
            data["reason_code"] in {
                "STRUCTURAL_UNKNOWN","LOCKED_ENTITY","AMBIGUOUS_TARGET"
            }):
        return {"kind":"REVIEW", "reason_code":data["reason_code"]}
    return {"kind":"PATCH"}


def score_paired_replay(cases: list[dict], responses: dict) -> dict:
    """Score supplied text, not performance of a claimed live provider.

    Only REPLAY_UNVERIFIED is valid for this API; live provider tracing and
    actual API/model identity must be added in a separately audited runner.
    """
    public,private=split_public_private(cases)
    if (type(responses) is not dict or set(responses)!=set(MODEL_KEYS)
            or any(type(responses[m]) is not dict for m in MODEL_KEYS)):
        raise PairedEvalReject("Require two explicit model-labelled response maps")
    expected_ids={x["task_id"] for x in public}
    if any(set(responses[m])!=expected_ids for m in MODEL_KEYS):
        raise PairedEvalReject("Missing or extra responses distort paired denominator")
    lookup={x["task_id"]:x for x in private}
    rows=[]
    for task in public:
        tid=task["task_id"]
        oracle=lookup[tid]
        per={}
        for model in MODEL_KEYS:
            text=responses[model][tid]
            status="REJECTED"
            reason="INVALID_MODEL_OUTPUT"
            action=_read_model_action(text)
            if action["kind"]=="REVIEW":
                status="REVIEW_REQUESTED"
                reason=action["reason_code"]
            elif action["kind"]=="PATCH":
                try:
                    result=validate_model_proposal(
                        task["plan"],text,host_operation_id="host_eval_001")
                    patch=result["patch"]
                    status="PATCH_VALIDATED_NOT_COMMITTED"
                    reason="VALIDATED"
                except (CADPatchReject,ValueError,TypeError):
                    status="REJECTED"
                    reason="PATCH_REJECTED"
            matched=(oracle["expected_outcome"]=="EDIT" and
                     status=="PATCH_VALIDATED_NOT_COMMITTED" and
                     patch["target_id"]==oracle["expected_target"] and
                     patch["delta_mm"]==oracle["expected_delta_mm"]) if status=="PATCH_VALIDATED_NOT_COMMITTED" else (
                     oracle["expected_outcome"]=="REVIEW" and
                     status=="REVIEW_REQUESTED")
            per[model]={"status":status,"reason":reason,"expected_behavior_met":matched,
                        "response_sha256":hashlib.sha256(
                            text.encode("utf8")).hexdigest()
                            if type(text) is str else None}
        rows.append({"task_id":tid,"model_results":per})
    scores={
        model:{
            "correct":sum(r["model_results"][model]["expected_behavior_met"]
                          for r in rows),
            "denominator":len(rows),
            "accuracy":sum(r["model_results"][model]["expected_behavior_met"]
                            for r in rows)/len(rows),
        } for model in MODEL_KEYS
    }
    return {
        "schema_version":1,"protocol":"ARCH_CAD_PAIRED_REPLAY_V1",
        "evidence_status":"REPLAY_UNVERIFIED_NOT_LIVE_MODEL_COMPARISON",
        "model_call_count":0,
        "model_labels_unverified":True,
        "candidate_plan_commits":0,
        "source_tasks_sha256":_sha_json({"cases":cases}),
        "public_prompt_sha256":_sha_json({"public":public}),
        "private_oracle_sha256":_sha_json({"private":private}),
        "task_count":len(rows),
        "scores":scores,"tasks":rows,
        "warning":"Response labels are not cryptographically tied to provider output. No real model comparison or paid calls took place.",
    }
