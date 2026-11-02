"""Offline E5 evidence integrity + operator-gate contracts.

The provider here is explicitly a FAKE. Its self-consistent replay must
NEVER become authenticated proof of Qwen/GCS origin. No network/models.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

from geometry_harness.domains.architecture.e5_evidence import (
    E5EvidenceReject, verified_e3_bundle, TASK_ID,
)
from geometry_harness.domains.architecture.e5_replay import execute as e5_execute
from geometry_harness.domains.architecture.local_qwen_smoke import execute as e3_execute
from geometry_harness.domains.architecture.edit_door import CADPatchReject

EDIT = '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":300}'
UNKNOWN = '{"schema_version":1,"decision":"review_required","reason_code":"STRUCTURAL_UNKNOWN"}'
LOCKED = '{"schema_version":1,"decision":"review_required","reason_code":"LOCKED_ENTITY"}'

class FakeNotRealQwen:
    def __init__(self):
        self.calls = 0
    def preflight(self):
        return {
            "identity_protocol":"local-llm-identity-v1",
            "model":"qwen3-coder-30b-q4km", "quantization":"Q4_K_M",
            "backend":"llama_server", "ctx_size":8192,
            "concurrent_requests":1, "gguf_full_digest_verified":False,
            "identity_projection_sha256":"a"*64,
        }
    def generate(self, prompt):
        response = (EDIT, UNKNOWN, LOCKED)[self.calls]
        self.calls += 1
        from geometry_harness.domains.architecture.korgis_cad import SYSTEM_MESSAGE
        return {"response_text":response, "model":"qwen3-coder-30b-q4km",
                "backend":"korgis_llama_server_loopback",
                "finish_reason":"stop",
                "system_prompt_sha256":hashlib.sha256(SYSTEM_MESSAGE.encode()).hexdigest(),
                "duration_seconds":0.001,
                "input_tokens":100,"output_tokens":30}

def make_fake(root):
    fake = FakeNotRealQwen()
    report = e3_execute(root, preflight_only=False, provider=fake)
    assert fake.calls == 3 and report["correct"] == 3
    return root

def rehash_manifest(root):
    """Simulate an attacker able to rewrite a self-consistent local bundle."""
    p=root/"artifact-inventory.json"
    manifest=json.loads(p.read_text())
    for x in manifest["files"]:
        data=(root/x["path"]).read_bytes()
        x["sha256"]=hashlib.sha256(data).hexdigest()
        x["bytes"]=len(data)
    p.write_text(json.dumps(manifest))

class EvidenceGateTests(unittest.TestCase):
    def test_entire_fake_bundle_has_integrity_not_external_provenance(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            r=verified_e3_bundle(root)
            self.assertTrue(r["file_integrity_verified"])
            self.assertFalse(r["read_source_authenticated"])
            self.assertFalse(r["gguf_full_digest_verified"])
            self.assertEqual(r["historical_run_id_claim"],41395270059)
            self.assertEqual(r["tasks"][TASK_ID]["response"],EDIT)
            summary=e5_execute(root,mode="inspect")
            self.assertEqual(summary["new_offset_mm"],1500)
            self.assertEqual(summary["old_offset_mm"],1200)
            self.assertEqual(summary["host_structural_status"],"non_load_bearing")
            self.assertFalse(summary["read_source_authenticated"])

    def test_mutated_response_rejected_even_if_manifest_rehashed(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            raw=root/"tasks"/TASK_ID/"raw-response.txt"
            raw.write_text('{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":400}')
            with self.assertRaises(E5EvidenceReject):
                verified_e3_bundle(root)
            rehash_manifest(root)
            with self.assertRaisesRegex(E5EvidenceReject,"Task response"):
                verified_e3_bundle(root)

    def test_modified_private_oracle_or_frozen_prompt_rejected(self):
        for target in ("protocol.json","tasks/arch_locked_wall/public-prompt.txt"):
            with self.subTest(target=target),TemporaryDirectory() as tmp:
                root=make_fake(Path(tmp)/"private-e3")
                path=root/target
                if target=="protocol.json":
                    p=json.loads(path.read_text())
                    p["private_oracle_sha256"]="1"*64
                    path.write_text(json.dumps(p))
                else:
                    path.write_text("fake prompt")
                rehash_manifest(root)
                with self.assertRaises(E5EvidenceReject):
                    verified_e3_bundle(root)

    def test_missing_extra_or_symlinked_file_denied(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            (root/"injected.txt").write_text("extra")
            with self.assertRaises(E5EvidenceReject):
                verified_e3_bundle(root)
            (root/"injected.txt").unlink()
            replaced=root/"tasks"/TASK_ID/"raw-response.txt"
            replaced.unlink()
            replaced.symlink_to(root/"protocol.json")
            with self.assertRaises(E5EvidenceReject):
                verified_e3_bundle(root)

    def test_noninteractive_commit_fails_without_output(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            out=Path(tmp)/"committed"
            with patch("geometry_harness.domains.architecture.e5_replay.sys.stdin") as stdin:
                stdin.isatty.return_value=False
                with self.assertRaisesRegex(CADPatchReject,"Non-interactive"):
                    e5_execute(root,mode="commit",out=out)
            self.assertFalse(out.exists())

    def test_negative_review_cases_never_reach_mutation_gateway(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            records=verified_e3_bundle(root)["tasks"]
            from geometry_harness.domains.architecture.agent_patch_gateway import validate_model_proposal
            for tid in ("arch_unknown_wall","arch_locked_wall"):
                with self.subTest(tid=tid),self.assertRaises(CADPatchReject):
                    validate_model_proposal(
                        records[tid]["plan"],records[tid]["response"],
                        host_operation_id="host_negative_001")

    def test_only_strict_interactive_challenge_can_approve(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            out=Path(tmp)/"committed"
            with patch("geometry_harness.domains.architecture.e5_replay.sys.stdin") as sin, \
                 patch("geometry_harness.domains.architecture.e5_replay.sys.stdout") as sout, \
                 patch("builtins.input", return_value="approve") as answer:
                sin.isatty.return_value=True
                sout.isatty.return_value=True
                with self.assertRaisesRegex(CADPatchReject,"Host denied"):
                    e5_execute(root,mode="commit",out=out)
            self.assertFalse(out.exists())
            answer.assert_called_once()

    @unittest.skipUnless(__import__("importlib").util.find_spec("ezdxf") is not None,
                         "Real DXF positive integration runs in pinned ezdxf CI")
    def test_simulated_terminal_confirmation_roundtrip(self):
        """Only a MOCK terminal in CI; never evidence of real human approval."""
        from geometry_harness.domains.architecture.e5_replay import _read_only_review
        from geometry_harness.domains.architecture.dxf_revision import import_verified_plan_dxf
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            out=Path(tmp)/"committed"
            preview=_read_only_review(verified_e3_bundle(root),
                                      operation_id="host_e5_1234567890abcdef")
            confirmation=("APPROVE "+preview["source_plan_sha256"][:12]+" "+
                          preview["candidate_plan_sha256"][:12]+" 9A9A9A9A")
            with patch("geometry_harness.domains.architecture.e5_replay.secrets.token_hex",
                       side_effect=["1234567890abcdef","9a9a9a9a"]), \
                 patch("geometry_harness.domains.architecture.e5_replay.sys.stdin") as sin, \
                 patch("geometry_harness.domains.architecture.e5_replay.sys.stdout") as sout, \
                 patch("builtins.input",return_value=confirmation):
                sin.isatty.return_value=True
                sout.isatty.return_value=True
                result=e5_execute(root,mode="commit",out=out)
            self.assertEqual(result["status"],"OPERATOR_TTY_CONFIRMED_DXF_REOPENED")
            self.assertTrue(result["operator_terminal_confirmed"])
            self.assertFalse(result["operator_identity_verified"])
            self.assertFalse(result["source_gcs_authenticated_by_program"])
            self.assertFalse(result["external_model_provenance_attested"])
            after=import_verified_plan_dxf(out/"transaction"/"candidate.dxf")
            self.assertEqual(after["openings"][0]["offset_mm"],1500)
            self.assertEqual(result["candidate_plan_sha256"],
                             preview["candidate_plan_sha256"])
            self.assertTrue((out/"transaction"/"rollback-plan.json").is_file())

    def test_invalid_modelled_source_file_never_approved(self):
        with TemporaryDirectory() as tmp:
            root=make_fake(Path(tmp)/"private-e3")
            data=json.loads((root/"protocol.json").read_text())
            data["model"]="another-model"
            (root/"protocol.json").write_text(json.dumps(data))
            rehash_manifest(root)
            with self.assertRaisesRegex(E5EvidenceReject,"protocol"):
                e5_execute(root,mode="inspect")

if __name__=="__main__":
    unittest.main()
