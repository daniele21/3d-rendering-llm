"""No network/model in CI. Real Korgis must be checked on self-hosted Mac."""
import json
import tempfile
from pathlib import Path
import unittest

from geometry_harness.domains.architecture.korgis_cad import (
    KorgisCADTextProvider, LocalCADProviderReject, MODEL, SYSTEM_MESSAGE
)
from geometry_harness.domains.architecture.local_qwen_smoke import (
    execute, evaluate_response, frozen_cases, frozen_public_prompt
)

class FakeKorgis(KorgisCADTextProvider):
    def __init__(self,*,bad_identity=False):
        super().__init__()
        self.calls=[]
        self.bad_identity=bad_identity
    def _request(self,method,path,payload=None):
        self.calls.append((method,path,payload))
        if path=="/v1/runtime/identity":
            return {
                "protocol_version":"local-llm-identity-v1",
                "models":{MODEL:{
                    "model":{"id":MODEL,
                             "quantization":"Q4_K_M" if not self.bad_identity else "Q8_0"},
                    "runtime":{"name":"llama_server",
                               "config":{"ctx_size":8192,
                                         "max_concurrent_requests":1}}
                }}
            }
        return {"model":MODEL,"choices":[{"finish_reason":"stop","message":{
            "content":'{"schema_version":1,"operation_type":"move_door",'
                      '"target_id":"door_001","delta_mm":300}'}}],
            "usage":{"prompt_tokens":65,"completion_tokens":25},
            "stats":{"time_total_seconds":0.3}}

class ProviderContractTests(unittest.TestCase):
    def test_preflight_requires_matching_model_without_generation(self):
        p=FakeKorgis()
        summary=p.preflight()
        self.assertEqual(summary["model"],MODEL)
        self.assertFalse(summary["gguf_full_digest_verified"])
        self.assertEqual([x[1] for x in p.calls],["/v1/runtime/identity"])
        with self.assertRaises(LocalCADProviderReject):
            FakeKorgis(bad_identity=True).preflight()

    def test_generate_is_local_json_not_blender(self):
        p=FakeKorgis()
        with self.assertRaises(LocalCADProviderReject):
            p.generate("request before preflight")
        p.preflight()
        result=p.generate("move door_001 300mm")
        self.assertEqual(result["input_tokens"],65)
        request=p.calls[-1][2]
        self.assertEqual(request["model"],MODEL)
        self.assertFalse(request["enable_thinking"])
        self.assertEqual(request["max_tokens"],384)
        self.assertEqual(request["messages"][0]["content"],SYSTEM_MESSAGE)
        self.assertNotIn("bpy",request["messages"][0]["content"])
        self.assertEqual(request["messages"][1]["role"],"user")

    def test_preflight_does_not_run_inference(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"preflight"
            fake=FakeKorgis()
            r=execute(root,preflight_only=True,provider=fake)
            self.assertEqual(r["status"],"PREFLIGHT_OK_MODEL_RESIDENT")
            self.assertEqual(r["model_calls"],0)
            self.assertEqual(len(fake.calls),1)
            self.assertTrue((root/"artifact-inventory.json").exists())
            self.assertFalse((root/"tasks").exists())

    def test_wrong_identity_is_blocked_with_zero_calls(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeKorgis(bad_identity=True)
            r=execute(Path(td)/"blocked",preflight_only=False,provider=fake)
            self.assertEqual(r["status"],"BLOCKED_MODEL_NOT_RESIDENT_OR_IDENTITY_DRIFT")
            self.assertEqual(r["model_calls"],0)
            self.assertEqual(len(fake.calls),1)

    def test_fake_provider_in_results_is_not_live_model_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"smoke"
            fake=FakeKorgis()
            r=execute(root,preflight_only=False,provider=fake)
            self.assertEqual(r["task_count"],3)
            self.assertEqual(r["model_attempts"],3)
            self.assertEqual(r["provider_completed"],3)
            self.assertEqual(r["correct"],1) # unsafe moves rejected
            self.assertEqual(len(fake.calls),4)
            self.assertEqual(r["cad_commits"],0)
            self.assertEqual(r["new_luna_calls"],0)
            self.assertTrue((root/"tasks/arch_move_door_300/result.json").exists())
            self.assertFalse((root/"tasks/arch_move_door_300/source.py").exists())
            self.assertEqual(json.loads((root/"artifact-inventory.json").read_text())["artifact_count"],12)

    def test_json_review_is_scored_only_on_expected_case(self):
        tasks=frozen_cases()
        review='{"schema_version":1,"decision":"review_required","reason_code":"STRUCTURAL_UNKNOWN"}'
        self.assertFalse(evaluate_response(tasks[0],review)["correct"])
        self.assertTrue(evaluate_response(tasks[1],review)["correct"])
        self.assertFalse(evaluate_response(tasks[2],review)["correct"])
        # LLM-controlled JSON types must not crash the evaluator.
        malformed='{"schema_version":1,"decision":"review_required","reason_code":[]}'
        self.assertFalse(evaluate_response(tasks[1],malformed)["correct"])
        public_prompt=frozen_public_prompt({"instruction":tasks[0]["instruction"],
                                            "plan":tasks[0]["plan"]})
        self.assertIn("query_constraints",public_prompt)
        self.assertNotIn("expected_delta_mm",public_prompt)

if __name__=="__main__":
    unittest.main()
