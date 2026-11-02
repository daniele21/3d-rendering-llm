"""E4: fully deterministic Mac/CI synthetic host-approval-to-DXF proof.

NO actual model calls or human approvals. The proposal is an explicit test
fixture; the host approval is a test fixture callback. Both facts are in
the evidence; this does not replay private Qwen responses from GCS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .approved_agent_transaction import host_approved_dxf_transaction
from .dxf_revision import import_verified_plan_dxf
from .e2e_move_door import run as run_w2
from .schema import plan_sha256


def run(out: Path) -> dict:
    out = Path(out).expanduser().resolve()
    if out.exists():
        raise ValueError("Evidence root must not exist")
    out.mkdir(parents=True, mode=0o700)

    # Reuse the already Mac-proven W2 synthetic plan fixture rather than
    # generating a second independent set of architectural assumptions.
    baseline = run_w2(out / "baseline")
    if baseline["status"] != "PASS_EXACT_SYNTHETIC_DXF_MOVE_AND_ROLLBACK":
        raise ValueError("W2 source fixture failed before E4")

    source_path = out / "baseline" / "original-plan.json"
    original_data = source_path.read_bytes()
    initial = json.loads(original_data)
    response = json.dumps({
        "schema_version": 1,
        "operation_type": "move_door",
        "target_id": "door_001",
        "delta_mm": 300,
    }, separators=(",", ":"), sort_keys=True)

    observations = []
    def host_fixture_approval(bound_summary):
        observations.append(bound_summary)
        return (
            bound_summary["source_plan_sha256"] == plan_sha256(initial)
            and bound_summary["target_id"] == "door_001"
            and bound_summary["delta_mm"] == 300
            and bound_summary["human_approved"] is False
        )

    result = host_approved_dxf_transaction(
        source_path, response,
        host_operation_id="host_e4_fixture_001",
        approve=host_fixture_approval,
        out=out / "approved",
    )
    checked = import_verified_plan_dxf(out / "approved" / "transaction" / "candidate.dxf")
    if not (
        len(observations) == 1
        and len(checked["walls"]) == 4
        and checked["walls"] == initial["walls"]
        and checked["openings"][0]["offset_mm"] == 1500
        and checked["openings"][1:] == initial["openings"][1:]
        and checked["source_sha256"] == initial["source_sha256"]
        and hashlib.sha256(source_path.read_bytes()).hexdigest()
             == hashlib.sha256(original_data).hexdigest()
        and result["status"] == "PASS_HOST_CALLBACK_APPROVED_SYNTHETIC_CAD_REVISION"
    ):
        raise ValueError("E4 synthetic host approval/readback invariant failed")
    evidence = {
        "schema_version": 1,
        "status": "PASS_E4_SYNTHETIC_HOST_FIXTURE_DXF_REOPEN",
        "model_calls_this_run": 0,
        "model_response_origin": "SYNTHETIC_JSON_FIXTURE_NOT_LIVE_QWEN",
        "host_approval_origin": "DETERMINISTIC_FIXTURE_CALLBACK_NOT_HUMAN",
        "human_approved": False,
        "real_partner_cad": False,
        "source_unchanged": True,
        "non_targets_unchanged": True,
        "move_mm": 300,
        "independent_dxf_reopen": True,
        "source_file_sha256": hashlib.sha256(original_data).hexdigest(),
        "accepted_plan_sha256": plan_sha256(checked),
        "rollback_present": (
            out / "approved" / "transaction" / "rollback-plan.json"
        ).is_file(),
        "artifact_paths": sorted(str(p.relative_to(out)) for p in out.rglob("*")
                                 if p.is_file()),
    }
    if not evidence["rollback_present"]:
        raise ValueError("Missing independent rollback artifact")
    (out / "e4-evidence.json").write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf8")
    return evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_class": type(exc).__name__}))
        return 2
    print(json.dumps({
        key: report[key] for key in (
            "status", "model_calls_this_run", "model_response_origin",
            "host_approval_origin", "move_mm", "independent_dxf_reopen",
        )
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
