"""E5A — fail-closed offline integrity verification of private E3 Qwen evidence.

Reads a manually authorized, local copy of GCS run-41395270059-attempt-1.
No GCS auth, networking, model calls, or CAD writes. An internally
consistent directory is NOT cryptographic proof of its external origin.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .korgis_cad import MODEL, PROFILE, SYSTEM_MESSAGE
from .local_qwen_smoke import (
    EXPERIMENT, evaluate_response, frozen_cases, frozen_public_prompt,
)
from .paired_eval import split_public_private
from .schema import validate_plan

RUN_ID = 41395270059
SOURCE_SHA = "72ced4d362832a0e5ebe7f51c64134b0fb88deaf"
GCS_RELATIVE = (
    f"geometry-harness/architecture-e3/{SOURCE_SHA}/"
    f"{RUN_ID}-attempt-1/run-{RUN_ID}-attempt-1"
)
MAX_BUNDLE_BYTES = 3_000_000
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = "arch_move_door_300"
# Independent SHA-only observation from original authenticated Mac/GCS read:
# https://github.com/daniele21/local-runner-infra/actions/runs/41399471418
ORIGINAL_INVENTORY_SHA256 = "440fc9f57b27ec22fbe38db3d4c563379bb01861f6615a7e99aea9a8febbce82"
ORIGINAL_DOOR_RESPONSE_SHA256 = "e77fd316f84d7290ab717c4ec6516743e2e78842bcc17591ea51894be76aba16"



class E5EvidenceReject(ValueError):
    """Incomplete, contradictory, or tampered E3 evidence."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value) -> str:
    return _sha(json.dumps(value, sort_keys=True).encode("utf8"))


def _json(data: bytes, label: str):
    if len(data) > 500_000:
        raise E5EvidenceReject(f"{label}: oversized metadata")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise E5EvidenceReject(f"{label}: duplicated JSON field")
            result[k] = v
        return result
    try:
        return json.loads(data, object_pairs_hook=unique)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise E5EvidenceReject(f"{label}: invalid JSON") from exc


def _safe_path(root: Path, relative: str) -> Path:
    if (type(relative) is not str or not relative or
            len(relative) > 180 or relative.startswith("/") or "\\" in relative):
        raise E5EvidenceReject("Invalid inventory path")
    path = Path(relative)
    if any(x in ("", ".", "..") for x in path.parts):
        raise E5EvidenceReject("Inventory traversal")
    absolute = root / path
    if (absolute.is_symlink() or
            any(p.is_symlink() for p in absolute.parents if p != root.parent) or
            not absolute.is_file()):
        raise E5EvidenceReject("Missing, nonregular or symlinked evidence")
    if not absolute.resolve().is_relative_to(root):
        raise E5EvidenceReject("Evidence escapes approved root")
    return absolute


def _verify_e3_bundle_structure(root: Path) -> dict:
    """Verify every expected E3 output byte against its original manifest.

    The root must have been obtained independently by an authorized operator.
    Never trust an arbitrary local directory to establish provider provenance.
    The verified return object holds private raw response ONLY in memory.
    """
    path = Path(root).expanduser()
    if path.is_symlink() or not path.is_dir():
        raise E5EvidenceReject("Private E3 evidence directory required")
    path = path.resolve(strict=True)
    cases = frozen_cases()
    public, private = split_public_private(cases)
    ids = [item["task_id"] for item in cases]
    fixed = {"protocol.json", "run-report.json", "model-identity.json"}
    for tid in ids:
        fixed.update({f"tasks/{tid}/{name}" for name in
                      ("public-prompt.txt", "raw-response.txt", "result.json")})
    expected = fixed | {"artifact-inventory.json"}
    actual = set()
    total = 0
    for item in path.rglob("*"):
        if item.is_symlink() or (not item.is_dir() and not item.is_file()):
            raise E5EvidenceReject("Unsupported evidence entry")
        if item.is_file():
            relative = item.relative_to(path).as_posix()
            actual.add(relative)
            total += item.stat().st_size
    if actual != expected or total > MAX_BUNDLE_BYTES:
        raise E5EvidenceReject("Wrong evidence file inventory or size")

    inventory = _json((path / "artifact-inventory.json").read_bytes(), "inventory")
    if (type(inventory) is not dict or set(inventory) !=
            {"schema_version", "files", "artifact_count"} or
            type(inventory["schema_version"]) is not int or
            inventory["schema_version"] != 1 or
            type(inventory["files"]) is not list or
            inventory["artifact_count"] != len(fixed) or
            len(inventory["files"]) != len(fixed)):
        raise E5EvidenceReject("Incorrect E3 artifact manifest")
    inventory_files = {}
    for element in inventory["files"]:
        if (type(element) is not dict or set(element) !=
                {"path", "sha256", "bytes"} or
                type(element["bytes"]) is not int or element["bytes"] < 0 or
                type(element["sha256"]) is not str or not
                SHA_PATTERN.fullmatch(element["sha256"]) or
                element["path"] in inventory_files):
            raise E5EvidenceReject("Malformed or duplicate artifact entry")
        file = _safe_path(path, element["path"])
        data = file.read_bytes()
        if _sha(data) != element["sha256"] or len(data) != element["bytes"]:
            raise E5EvidenceReject("Artifact checksum or length mismatch")
        inventory_files[element["path"]] = data
    if set(inventory_files) != fixed:
        raise E5EvidenceReject("Unexpected manifest path set")

    protocol = _json(inventory_files["protocol.json"], "protocol")
    report = _json(inventory_files["run-report.json"], "report")
    identity = _json(inventory_files["model-identity.json"], "identity")
    if (protocol.get("experiment") != EXPERIMENT or
            protocol.get("mode") != "SINGLE_CALL_PER_TASK" or
            protocol.get("schema_version") != 1 or
            protocol.get("task_count") != 3 or
            protocol.get("max_model_calls") != 3 or
            protocol.get("model") != MODEL or
            protocol.get("profile") != PROFILE or
            protocol.get("local_only") is not True or
            protocol.get("synthetic_only") is not True or
            protocol.get("scorer_visible_to_model") is not False or
            protocol.get("model_python_executed") is not False or
            protocol.get("multi_turn_tool_calls") is not False or
            protocol.get("system_sha256") != _sha(SYSTEM_MESSAGE.encode("utf8")) or
            protocol.get("public_tasks_sha256") != _canonical_hash(public) or
            protocol.get("private_oracle_sha256") != _canonical_hash(private) or
            type(protocol.get("prompt_sha256")) is not dict or
            set(protocol["prompt_sha256"]) != set(ids)):
        raise E5EvidenceReject("E3 frozen protocol mismatch")
    if (identity.get("identity_protocol") != "local-llm-identity-v1" or
            identity.get("model") != MODEL or
            identity.get("quantization") != "Q4_K_M" or
            identity.get("backend") != "llama_server" or
            identity.get("ctx_size") != 8192 or
            identity.get("concurrent_requests") != 1 or
            identity.get("gguf_full_digest_verified") is not False or
            not isinstance(identity.get("identity_projection_sha256"), str) or
            not SHA_PATTERN.fullmatch(identity["identity_projection_sha256"])):
        raise E5EvidenceReject("E3 projected runtime identity mismatch")
    if (report.get("experiment") != EXPERIMENT or
            report.get("status") != "EXECUTED_REAL_LOCAL_PROVIDER_WITH_FAILURES_RECORDED" or
            report.get("source") != "synthetic_only" or
            report.get("model") != MODEL or report.get("task_count") != 3 or
            report.get("model_attempts") != 3 or
            report.get("provider_completed") != 3 or
            report.get("correct") != 3 or report.get("accuracy") != 1.0 or
            report.get("cad_commits") != 0 or
            report.get("new_luna_calls") != 0 or
            report.get("cloud_fallback") is not False or
            report.get("multi_turn_agent_evaluated") is not False or
            report.get("scoring_mode") != "TOOL_GROUNDED_ONE_SHOT" or
            type(report.get("per_task")) is not list or
            len(report["per_task"]) != 3):
        raise E5EvidenceReject("Reported benchmark contract mismatch")

    rows = {}
    for original in cases:
        tid = original["task_id"]
        prompt = frozen_public_prompt(original).encode("utf8")
        if (_sha(prompt) != protocol["prompt_sha256"][tid] or
                inventory_files[f"tasks/{tid}/public-prompt.txt"] != prompt):
            raise E5EvidenceReject("Frozen task prompt differs from real evidence")
        record = _json(inventory_files[f"tasks/{tid}/result.json"], tid)
        response_bytes = inventory_files[f"tasks/{tid}/raw-response.txt"]
        if len(response_bytes) > 2048:
            raise E5EvidenceReject("Oversized model response")
        try:
            response = response_bytes.decode("utf8")
        except UnicodeError as exc:
            raise E5EvidenceReject("Invalid UTF-8 model response") from exc
        expected_score = evaluate_response(original, response)
        telemetry = record.get("provider_telemetry")
        if (record.get("task_id") != tid or record.get("model") != MODEL or
                record.get("provider_status") != "COMPLETED" or
                expected_score["correct"] is not True or
                record.get("evaluation") != expected_score or
                type(telemetry) is not dict or
                telemetry.get("model") != MODEL or
                telemetry.get("backend") != "korgis_llama_server_loopback" or
                telemetry.get("finish_reason") != "stop" or
                telemetry.get("system_prompt_sha256") !=
                protocol["system_sha256"]):
            raise E5EvidenceReject("Task response, score or telemetry mismatch")
        rows[tid] = {"response": response, "response_sha256": _sha(response_bytes),
                     "plan": validate_plan(original["plan"]),
                     "scorer": expected_score}
    reported = report["per_task"]
    if ([x.get("task_id") for x in reported] != ids or
            any(x.get("provider_status") != "COMPLETED" or
                x.get("evaluation") != rows[x["task_id"]]["scorer"]
                for x in reported)):
        raise E5EvidenceReject("Task score report inconsistency")
    return {
        "status": "INTEGRITY_VERIFIED_EXTERNAL_PROVENANCE_UNATTESTED",
        "experiment": EXPERIMENT,
        "historical_run_id_claim": RUN_ID,
        "expected_source_sha_claim": SOURCE_SHA,
        "expected_gcs_relative_prefix": GCS_RELATIVE,
        "model": MODEL,
        "gguf_full_digest_verified": False,
        "file_integrity_verified": True,
        "read_source_authenticated": False,
        "model_calls_this_replay": 0,
        "tasks": rows,
        "bundle_inventory_sha256": _sha((path / "artifact-inventory.json").read_bytes()),
    }

def verified_e3_bundle(root: Path) -> dict:
    """Accept only byte-identical E3 archive anchored by independent GCS read.

    The original SHA-only observation was captured from the fixed private
    source namespace on Mac run 41399471418. This proves content identity
    to that observation; the original full GGUF digest remains unverified.
    """
    report = _verify_e3_bundle_structure(root)
    if (report["bundle_inventory_sha256"] != ORIGINAL_INVENTORY_SHA256 or
            report["tasks"][TASK_ID]["response_sha256"] != ORIGINAL_DOOR_RESPONSE_SHA256):
        raise E5EvidenceReject("Original authenticated GCS content SHA anchor mismatch")
    report["original_content_sha_anchor_verified"] = True
    report["source_anchor_observation_run_id"] = 41399471418
    return report
