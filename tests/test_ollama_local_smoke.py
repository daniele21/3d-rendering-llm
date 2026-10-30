"""No-network local provider and pinned prompt smoke regression contracts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.benchmark_smoke import EXPECTED_REV
from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.providers.local import (
    DEFAULT_MODEL, OllamaLocalCodeProvider, LocalProviderError,
)
from geometry_harness.local_smoke import _load_prompts, LocalSmokeError, run


class FakeHTTPResponse:
    status = 200
    def __init__(self, data): self.data = json.dumps(data).encode("utf-8")
    def read(self, n): return self.data[:n]


class FakeHTTPConnection:
    sent = []
    response = None
    def __init__(self, host, port, timeout):
        assert (host, port) == ("127.0.0.1", 11434)
        self.timeout = timeout
    def request(self, method, path, payload, headers):
        self.sent.append((method, path, json.loads(payload), headers))
    def getresponse(self): return self.response
    def close(self): pass


def valid_response(code="import bpy\nbpy.ops.mesh.primitive_cube_add()"):
    return {
        "model": DEFAULT_MODEL,
        "done": True, "done_reason": "stop",
        "message": {"role": "assistant", "content": code},
        "total_duration": 3000000000,
        "load_duration": 1000000000,
        "prompt_eval_duration": 500000000,
        "eval_duration": 1500000000,
        "prompt_eval_count": 123, "eval_count": 60,
    }


class LoopbackProviderTests(unittest.TestCase):
    def setUp(self):
        FakeHTTPConnection.sent.clear()

    def test_no_cloud_or_unpinned_model(self):
        for model in ("qwen3-coder:480b-cloud", "https://evil.test", "qwen3-coder",
                      "qwen:cloud", "../other:model", "qwen:bad tag"):
            with self.assertRaises(LocalProviderError):
                OllamaLocalCodeProvider(model=model)

    def test_19gb_32gb_profile_is_bounded(self):
        p = OllamaLocalCodeProvider()
        self.assertEqual(p.model, "qwen3-coder:30b-a3b-q4_K_M")
        self.assertEqual((p.context_tokens, p.max_output_tokens), (8192, 4096))
        for kw in ({"context_tokens": 131072}, {"max_output_tokens": 20000},
                   {"temperature": -1}):
            with self.assertRaises(LocalProviderError):
                OllamaLocalCodeProvider(**kw)

    def test_ollama_wire_is_strictly_loopback_and_unloads_before_blender(self):
        FakeHTTPConnection.response = FakeHTTPResponse(valid_response())
        with patch("geometry_harness.providers.local.http.client.HTTPConnection", FakeHTTPConnection):
            p = OllamaLocalCodeProvider()
            generated = p.generate("Create a box")
        self.assertEqual(generated.model, DEFAULT_MODEL)
        self.assertEqual(generated.input_tokens, 123)
        self.assertEqual(generated.output_tokens, 60)
        self.assertIsNone(generated.cost_usd)
        self.assertEqual(p.last_telemetry.tokens_per_second, 40)
        self.assertEqual(p.last_telemetry.total_seconds, 3)
        self.assertEqual(len(FakeHTTPConnection.sent), 1)
        method, path, data, headers = FakeHTTPConnection.sent[0]
        self.assertEqual((method, path), ("POST", "/api/chat"))
        self.assertEqual(data["keep_alive"], 0)
        self.assertFalse(data["stream"])
        self.assertEqual(data["options"]["num_ctx"], 8192)
        self.assertEqual(data["options"]["num_predict"], 4096)
        self.assertEqual(data["options"]["seed"], 42)
        self.assertNotIn("Authorization", headers)

    def test_incomplete_response_and_model_switch_are_refused(self):
        for change in ({"done_reason": "length"}, {"model": "remote:model"},
                       {"done": False}):
            payload = {**valid_response(), **change}
            FakeHTTPConnection.response = FakeHTTPResponse(payload)
            with patch("geometry_harness.providers.local.http.client.HTTPConnection", FakeHTTPConnection):
                with self.assertRaises(LocalProviderError):
                    OllamaLocalCodeProvider().generate("Create a box")


def stage_fixtures(root: Path, *, tamper: bool = False):
    public, suite = root/"public", root/"suite.json"
    public.mkdir()
    rows = []
    for task in EXPECTED_IDS:
        folder = public / task
        folder.mkdir()
        descr = ("Description for " + task).encode()
        instructions = ("Build " + task).encode()
        (folder/"prompt_description.txt").write_bytes(descr)
        (folder/"prompt_instruction.txt").write_bytes(instructions)
        rows.append({
            "task_id":task,
            "prompt_description_sha256":hashlib.sha256(descr).hexdigest(),
            "prompt_instruction_sha256":hashlib.sha256(instructions).hexdigest(),
        })
    payload = {
        "benchmark":"3DCodeBench", "schema_version":1, "dataset_revision":EXPECTED_REV,
        "reference_access":"scorer_only", "tiers":{"smoke":list(EXPECTED_IDS)},
        "tasks":rows,
    }
    suite.write_text(json.dumps(payload))
    (public/"staging-manifest.json").write_text(json.dumps({
        "task_ids":list(EXPECTED_IDS), "dataset_revision":EXPECTED_REV,
        "source_suite_sha256":hashlib.sha256(suite.read_bytes()).hexdigest(),
        "reference_access":"NONE_in_generator_workspace",
    }))
    if tamper:
        (public/EXPECTED_IDS[0]/"prompt_instruction.txt").write_text("maliciously changed")
    return public,suite


class MockLocalEngine:
    model = DEFAULT_MODEL
    context_tokens = 8192
    max_output_tokens = 4096
    temperature = .1
    seed = 42
    last_telemetry = None
    def __init__(self, text):
        self.text=text
        self.count=0
    def generate(self, prompt):
        from geometry_harness.providers.compatible import GeneratedCode
        self.count+=1
        return GeneratedCode(self.model,self.text,50,100)


class LocalSmokeTests(unittest.TestCase):
    def test_invalid_or_tampered_prompts_never_send_model_requests(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            public,suite=stage_fixtures(root,tamper=True)
            engine=MockLocalEngine("import bpy\n")
            with patch("geometry_harness.local_smoke.blender_binary",
                       return_value="/bin/blender"):
                with self.assertRaisesRegex(LocalSmokeError, "hash mismatch"):
                    run(root/"out",public,suite,task_ids=(EXPECTED_IDS[0],),
                        provider=engine)
            self.assertEqual(engine.count,0)
            self.assertFalse((root/"out").exists())

    def test_one_real_contract_compiled_and_native_e2e_mocked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            public,suite=stage_fixtures(root)
            engine=MockLocalEngine(
                "import bpy\nbpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))\n"
                "obj=bpy.context.object\nobj.name='Glass pane'\nobj.dimensions=(1,1,1)\n"
            )
            def fake_blender(cmd, log, limit=180):
                folder=log.parent
                log.write_text("audited fake Blender fixture")
                if "build_safe_scene.py" in " ".join(map(str,cmd)):
                    (folder/"scene.blend").write_bytes(b"BLENDER")
                    (folder/"preview.png").write_bytes(
                        b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00"*8 +
                        b"\\x00\\x00\\x03\\x20" + b"\\x00\\x00\\x02\\x58"
                    )
                else:
                    (folder/"geometry.json").write_text(json.dumps({"passed":True}))
            with patch("geometry_harness.local_smoke.blender_binary",
                       return_value="/bin/blender"), patch(
                "geometry_harness.local_smoke._safe_run",side_effect=fake_blender):
                report=run(root/"out",public,suite,task_ids=(EXPECTED_IDS[0],),
                           provider=engine)
            self.assertEqual(engine.count,1)
            self.assertEqual(report["native_pass"],1)
            self.assertEqual(report["safe_source_pass"],1)
            self.assertEqual(report["new_model_calls"],1)
            self.assertEqual(report["api_cost_usd"],"0")
            self.assertEqual(report["result_rows"][0]["normalized_mesh_names"],1)
            self.assertTrue((root/"out"/"local-benchmark.json").exists())


if __name__ == "__main__":
    unittest.main()
