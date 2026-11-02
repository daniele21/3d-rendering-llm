"""E4: host-approved typed CAD proposal -> independently reopened DXF revision.

No model inference, no executable model code and no user-facing commit tool.
The model supplies *only* bounded proposal JSON. An independently trusted
host callback approves a source-and-candidate-hash-bound summary before any
filesystem output. Callback approval is NOT a claim of human acceptance.
Real-world unannotated DXFs and architectural code compliance are unsupported.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from .agent_patch_gateway import validate_model_proposal
from .dxf_revision import import_verified_plan_dxf
from .edit_door import CADPatchReject, run_move_door
from .schema import plan_sha256, validate_plan


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_pairs(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise CADPatchReject("Duplicate plan JSON key")
        result[key] = val
    return result


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n",
                    encoding="utf8")
    path.chmod(0o600)


def host_approved_dxf_transaction(
    source_plan_path: Path,
    model_json: str,
    *,
    approve: Callable[[dict], bool],
    host_operation_id: str,
    out: Path,
) -> dict:
    """Commit only when a trusted host independently approves this precise patch.

    The host callback is not serializable and is never in the LLM tool schema.
    It sees only the candidate measurements and fingerprints. No model text
    is evaluated as code, and no file writes occur before the approval.
    """
    source_plan_path = Path(source_plan_path).expanduser()
    out_arg = Path(out).expanduser()
    if not callable(approve):
        raise CADPatchReject("Host approval callback is mandatory")
    if source_plan_path.is_symlink() or not source_plan_path.is_file():
        raise CADPatchReject("Regular non-symlinked source plan required")
    if out_arg.exists() or out_arg.is_symlink():
        raise CADPatchReject("Fresh output directory required")
    source = source_plan_path.resolve(strict=True)
    destination = out_arg.resolve()
    source_bytes = source.read_bytes()
    if not 1 <= len(source_bytes) <= 2_000_000:
        raise CADPatchReject("Source plan size outside audited bounds")
    try:
        original = validate_plan(json.loads(
            source_bytes, object_pairs_hook=_strict_pairs))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CADPatchReject("Invalid source plan or duplicate keys") from exc

    validated = validate_model_proposal(
        original, model_json, host_operation_id=host_operation_id)
    patch = validated["patch"]
    approved_input = {
        "schema_version": 1,
        "operation_id": host_operation_id,
        "target_id": patch["target_id"],
        "delta_mm": patch["delta_mm"],
        "source_file_sha256": _sha(source_bytes),
        "source_plan_sha256": patch["expected_plan_sha256"],
        "candidate_plan_sha256": validated["candidate_plan_sha256"],
        "model_response_sha256": _sha(model_json.encode("utf8")),
        "human_approved": False,
        "review_context": "HOST_ONLY_TESTABLE_CALLBACK_NOT_MODEL_AUTHORIZATION",
    }
    # Explicit identity check: only literal True qualifies, not "yes" or 1.
    if approve(dict(approved_input)) is not True:
        raise CADPatchReject("Host denied proposed CAD transaction")
    # Protect against modifications during independent approval.
    if _sha(source.read_bytes()) != approved_input["source_file_sha256"]:
        raise CADPatchReject("Source bytes changed during approval")

    destination.mkdir(parents=True, mode=0o700)
    _write_json(destination / "host-approval-record.json", approved_input)
    transaction = run_move_door(source, patch, destination / "transaction")
    if transaction["status"] != "ACCEPTED":
        raise CADPatchReject("Independent DXF transaction did not accept candidate")
    reread = import_verified_plan_dxf(destination / "transaction" / "candidate.dxf")
    if (plan_sha256(reread) != approved_input["candidate_plan_sha256"] or
            not transaction["source_unchanged"] or
            not transaction["non_targets_unchanged"] or
            _sha(source.read_bytes()) != approved_input["source_file_sha256"]):
        raise CADPatchReject("Revision/source conservation failed")

    report = {
        "experiment": "ARCHITECTURE_E4_HOST_APPROVED_DXF_V1",
        "status": "PASS_HOST_CALLBACK_APPROVED_SYNTHETIC_CAD_REVISION",
        "source_file_sha256": approved_input["source_file_sha256"],
        "model_response_sha256": approved_input["model_response_sha256"],
        "approved_candidate_sha256": approved_input["candidate_plan_sha256"],
        "accepted_revision_sha256": transaction["accepted_revision_sha256"],
        "host_callback_approved": True,
        "human_approved": False,
        "provider_identity_verified": False,
        "no_model_calls": True,
        "code_compliance": "UNKNOWN_NOT_CHECKED",
        "actual_dxf_reimport": True,
        "non_targets_unchanged": True,
        "source_unchanged": True,
        "artifacts": [],
    }
    for artifact in sorted(destination.rglob("*")):
        if artifact.is_file():
            report["artifacts"].append({
                "path": str(artifact.relative_to(destination)),
                "sha256": _sha(artifact.read_bytes()),
                "bytes": artifact.stat().st_size,
            })
    _write_json(destination / "host-acceptance-manifest.json", report)
    return report
