"""E5B — operator-mediated CAD replay. NO model calls or automatic approval.

Inspect is read-only. Commit is intentionally impossible in noninteractive
CI (stdin AND stdout must be a TTY); a human must inspect a SHA-bound
review and type the exact approval challenge for this run. This proves
operator interaction, not verified legal identity or construction compliance.

The E3 bundle must be obtained from the fixed private GCS prefix by an
authorized operator. E5A can verify integrity, not external origin by itself.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory

from .agent_patch_gateway import validate_model_proposal
from .approved_agent_transaction import host_approved_dxf_transaction
from .e5_evidence import E5EvidenceReject, TASK_ID, verified_e3_bundle
from .edit_door import CADPatchReject
from .schema import plan_sha256

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _read_only_review(data: dict, *, operation_id: str) -> dict:
    item = data["tasks"][TASK_ID]
    plan = item["plan"]
    resp = item["response"]
    # Frozen E3 target and correct 300mm translation required.
    validated = validate_model_proposal(plan, resp,
                                         host_operation_id=operation_id)
    p = validated["patch"]
    if p["target_id"] != "door_001" or p["delta_mm"] != 300:
        raise E5EvidenceReject("Historical response is not expected bounded move")
    opening = next(o for o in plan["openings"] if o["id"] == p["target_id"])
    host = next(w for w in plan["walls"] if w["id"] == opening["host_wall_id"])
    return {
        "mode": "INSPECT_ONLY_NOT_APPROVED",
        "historical_run_id_claim": data["historical_run_id_claim"],
        "source_integrity": data["status"],
        "read_source_authenticated": data["read_source_authenticated"],
        "original_content_sha_anchor_verified": data.get(
            "original_content_sha_anchor_verified", False),
        "source_anchor_observation_run_id": data.get(
            "source_anchor_observation_run_id"),
        "provider_full_gguf_digest_verified": False,
        "source_plan_sha256": plan_sha256(plan),
        "raw_model_response_sha256": item["response_sha256"],
        "candidate_plan_sha256": validated["candidate_plan_sha256"],
        "target_id": p["target_id"],
        "host_wall_id": host["id"],
        "host_structural_status": host["structural_status"],
        "door_locked": opening["locked"],
        "wall_locked": host["locked"],
        "old_offset_mm": opening["offset_mm"],
        "new_offset_mm": opening["offset_mm"] + p["delta_mm"],
        "delta_mm": p["delta_mm"],
        "other_geometry_changes": "NONE_PER_BOUNDED_PREFLIGHT",
        "normative_code_compliance": "UNKNOWN_NOT_CHECKED",
        "model_calls_this_replay": 0,
    }

def _terminal_consent(review: dict, *, challenge_nonce: str) -> bool:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CADPatchReject("Real terminal interaction required; CI approval refused")
    # A fresh nonce prevents the use of a canned approval from a prior run.
    challenge = ("APPROVE " + review["source_plan_sha256"][:12] + " " +
                 review["candidate_plan_sha256"][:12] + " " + challenge_nonce)
    print("\nUNVERIFIED EXTERNAL GCS PROVENANCE: inspect the original archive acquisition before approval.")
    print("E5 review — synthetic floorplan; no building code certification.")
    for k in ("target_id", "host_wall_id", "host_structural_status",
              "wall_locked", "door_locked", "old_offset_mm", "new_offset_mm",
              "source_plan_sha256", "candidate_plan_sha256",
              "raw_model_response_sha256", "read_source_authenticated"):
        print(f"  {k}: {review[k]}")
    print(f"\nType EXACTLY: {challenge}")
    typed = input("Operator decision (anything else denies): ").strip()
    return typed == challenge

def execute(bundle: Path, *, mode: str, out: Path | None = None) -> dict:
    if mode not in ("inspect", "commit"):
        raise E5EvidenceReject("Unknown E5 mode")
    data = verified_e3_bundle(bundle)
    operation_id = ("host_e5_" + secrets.token_hex(8) if mode == "commit"
                    else "host_e5_preview_001")
    review = _read_only_review(data, operation_id=operation_id)
    if mode == "inspect":
        return review
    if out is None:
        raise E5EvidenceReject("Commit needs fresh output directory")
    destination = Path(out).expanduser()
    if destination.exists() or destination.is_symlink():
        raise CADPatchReject("Refusing existing output directory")
    # No arbitrary caller-injected approval, no environment override and
    # no approved fixture callback in the real CLI.
    nonce = secrets.token_hex(4).upper()
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CADPatchReject("Non-interactive E5 commit forbidden")
    item = data["tasks"][TASK_ID]
    consent = {"value": False, "at": None}
    def interactive_approval(bound: dict) -> bool:
        if (bound["candidate_plan_sha256"] != review["candidate_plan_sha256"] or
                bound["source_plan_sha256"] != review["source_plan_sha256"] or
                bound["model_response_sha256"] != review["raw_model_response_sha256"] or
                bound["target_id"] != review["target_id"] or
                bound["delta_mm"] != review["delta_mm"]):
            raise CADPatchReject("Approval challenge does not match CAD source/patch")
        accepted = _terminal_consent(review, challenge_nonce=nonce)
        if accepted:
            consent["value"] = True
            consent["at"] = datetime.now(timezone.utc).isoformat()
        return accepted
    # The plan is instantiated from the frozen, hash-checked protocol;
    # source file is created only in an isolated private temporary root.
    # No material from the private bundle is committed to the repo.
    with TemporaryDirectory(prefix="arch-e5-source-") as tmp:
        source = Path(tmp) / "validated-e3-plan.json"
        source.write_text(json.dumps(item["plan"], sort_keys=True), encoding="utf8")
        source.chmod(0o600)
        result = host_approved_dxf_transaction(
            source, item["response"], approve=interactive_approval,
            host_operation_id=operation_id,
            out=destination,
        )
    if not consent["value"] or not consent["at"]:
        raise CADPatchReject("Approval was not recorded")
    # This is an operator confirmation record, not verified legal ID or
    # cryptographically certified GCS model provenance.
    receipt = {
        "schema_version": 1,
        "status": "OPERATOR_TTY_CONFIRMED_DXF_REOPENED",
        "operator_terminal_confirmed": True,
        "operator_identity_verified": False,
        "source_gcs_authenticated_by_program": False,
        "original_content_sha_anchor_verified": data.get(
            "original_content_sha_anchor_verified", False),
        "source_anchor_observation_run_id": data.get(
            "source_anchor_observation_run_id"),
        "external_model_provenance_attested": False,
        "source_claim_run_id": data["historical_run_id_claim"],
        "source_claim_sha": data["expected_source_sha_claim"],
        "bundle_inventory_sha256": data["bundle_inventory_sha256"],
        "source_plan_sha256": review["source_plan_sha256"],
        "candidate_plan_sha256": review["candidate_plan_sha256"],
        "model_response_sha256": review["raw_model_response_sha256"],
        "confirmed_at_utc": consent["at"],
        "new_model_calls": 0,
        "transaction_status": result["status"],
    }
    path = destination / "operator-confirmation.json"
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                    encoding="utf8")
    path.chmod(0o600)
    return receipt

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("inspect", "commit"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        result = execute(args.bundle, mode=args.mode, out=args.out)
    except (CADPatchReject, E5EvidenceReject, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status":"E5_BLOCKED",
                          "error_class":type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
