"""E4 host-only approval integration, no model calls or partner CAD."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import Mock

from geometry_harness.domains.architecture.approved_agent_transaction import (
    host_approved_dxf_transaction,
)
from geometry_harness.domains.architecture.dxf_revision import import_verified_plan_dxf
from geometry_harness.domains.architecture.edit_door import CADPatchReject

EZDXF = importlib.util.find_spec("ezdxf") is not None

PROPOSAL = json.dumps({
    "schema_version": 1, "operation_type": "move_door",
    "target_id": "door_001", "delta_mm": 300,
})


def plan():
    return {
        "schema_version": 1, "units": "mm", "coordinate_frame": "local_xy",
        "revision_id": "rev_001",
        "source_sha256": hashlib.sha256(b"synthetic-only-plan-source").hexdigest(),
        "walls": [
            {"id": "wall_001", "start_mm": [0, 0], "end_mm": [5000, 0],
             "thickness_mm": 150, "locked": False,
             "structural_status": "non_load_bearing"},
            {"id": "wall_002", "start_mm": [5000, 0], "end_mm": [5000, 4000],
             "thickness_mm": 150, "locked": True,
             "structural_status": "unknown"},
        ],
        "openings": [
            {"id": "door_001", "kind": "door", "host_wall_id": "wall_001",
             "offset_mm": 1200, "width_mm": 900, "locked": False},
            {"id": "window_001", "kind": "window", "host_wall_id": "wall_002",
             "offset_mm": 500, "width_mm": 900, "locked": True},
        ],
    }


def write_plan(root, value=None):
    source = root / "original.json"
    source.write_text(json.dumps(plan() if value is None else value), encoding="utf8")
    return source


class ApprovalGateTests(TestCase):
    def test_explicit_denial_does_not_create_output_or_mutate_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_plan(root)
            before = source.read_bytes()
            approve = Mock(return_value=False)
            with self.assertRaisesRegex(CADPatchReject, "Host denied"):
                host_approved_dxf_transaction(source, PROPOSAL, approve=approve,
                                               host_operation_id="host_0001",
                                               out=root / "proposed")
            self.assertFalse((root / "proposed").exists())
            self.assertEqual(before, source.read_bytes())
            approval = approve.call_args.args[0]
            self.assertEqual(approval["delta_mm"], 300)
            self.assertFalse(approval["human_approved"])
            self.assertNotIn("model_text", approval)

    def test_non_boolean_approval_and_no_callback_are_denied(self):
        for candidate in ("yes", 1, None, False):
            with self.subTest(candidate=candidate), TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = write_plan(root)
                with self.assertRaises(CADPatchReject):
                    host_approved_dxf_transaction(
                        source, PROPOSAL,
                        approve=lambda _: candidate,
                        host_operation_id="host_0002", out=root / "output")
                self.assertFalse((root / "output").exists())
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_plan(root)
            with self.assertRaisesRegex(CADPatchReject, "callback"):
                host_approved_dxf_transaction(
                    source, PROPOSAL, approve=None,
                    host_operation_id="host_0003", out=root / "output")

    def test_structural_unknown_or_forbidden_model_json_never_reaches_host(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = plan()
            value["walls"][0]["structural_status"] = "unknown"
            source = write_plan(root, value)
            approver = Mock(return_value=True)
            with self.assertRaises(CADPatchReject):
                host_approved_dxf_transaction(
                    source, PROPOSAL, approve=approver,
                    host_operation_id="host_0004", out=root / "output")
            approver.assert_not_called()
            value["walls"][0]["structural_status"] = "non_load_bearing"
            source.write_text(json.dumps(value), encoding="utf8")
            for raw in (
                '{"schema_version":1,"operation_type":"move_door",'
                '"target_id":"door_001","delta_mm":300,"commit":true}',
                '{"schema_version":1,"operation_type":"move_door",'
                '"target_id":"door_001","delta_mm":300,"delta_mm":400}',
            ):
                with self.subTest(raw=raw), self.assertRaises(CADPatchReject):
                    host_approved_dxf_transaction(
                        source, raw, approve=approver,
                        host_operation_id="host_0004", out=root / "output")
            approver.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_approval_source_race_is_rejected_before_any_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_plan(root)
            def hostile_callback(_):
                source.write_text(json.dumps({**plan(), "revision_id": "rev_CHANGED"}))
                return True
            with self.assertRaisesRegex(CADPatchReject, "changed during approval"):
                host_approved_dxf_transaction(
                    source, PROPOSAL, approve=hostile_callback,
                    host_operation_id="host_0005", out=root / "output")
            self.assertFalse((root / "output").exists())

    @skipUnless(EZDXF, "Pinned ezdxf CI covers actual DXF roundtrip")
    def test_approved_proposal_writes_new_verified_dxf_and_preserves_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_plan(root)
            old = source.read_bytes()
            observed = []
            def host_callback(summary):
                observed.append(summary)
                return True
            result = host_approved_dxf_transaction(
                source, PROPOSAL, approve=host_callback,
                host_operation_id="host_0006", out=root / "accepted")
            self.assertEqual(result["status"],
                             "PASS_HOST_CALLBACK_APPROVED_SYNTHETIC_CAD_REVISION")
            self.assertTrue(result["actual_dxf_reimport"])
            self.assertFalse(result["human_approved"])
            self.assertFalse(result["provider_identity_verified"])
            self.assertTrue(result["no_model_calls"])
            self.assertEqual(old, source.read_bytes())
            reread = import_verified_plan_dxf(root/"accepted"/"transaction"/"candidate.dxf")
            self.assertEqual(reread["openings"][0]["offset_mm"], 1500)
            self.assertEqual(reread["walls"], plan()["walls"])
            self.assertEqual(reread["openings"][1:], plan()["openings"][1:])
            self.assertEqual(observed[0]["source_file_sha256"],
                             hashlib.sha256(old).hexdigest())
            self.assertEqual(result["approved_candidate_sha256"],
                             result["accepted_revision_sha256"])
            self.assertTrue((root/"accepted"/"transaction"/"rollback-plan.json").is_file())
            self.assertTrue((root/"accepted"/"host-acceptance-manifest.json").is_file())
            with self.assertRaises(CADPatchReject):
                host_approved_dxf_transaction(
                    source, PROPOSAL, approve=lambda _: True,
                    host_operation_id="host_0007", out=root / "accepted")


if __name__ == "__main__":
    import unittest
    unittest.main()
