"""No-egress Korgis adapter, strict model identity and frozen prompt smoke."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.benchmark_smoke import EXPECTED_REV
from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.providers.local import (
    DEFAULT_MODEL, KorgisLocalCodeProvider, LocalProviderError,
)
from geometry_harness.local_smoke import LocalSmokeError, run

MODEL = DEFAULT_MODEL


class FakeHTTPResponse:
    status = 200
    def __init__(self, data): self.data = json.dumps(data).encode("utf-8")
    def read(self, n): return self.data[:n]


class FakeHTTPConnection:
    sent = []
    outputs = {}
    def __init__(self, host, port, timeout):
        assert (host, port) == ("127.0.0.1", 1235)
        self.timeout = timeout
        self.path = None
    def request(self, method, path, payload, headers):
        self.sent.append((method, path, json.loads(payload) if payload else None, headers))
        self.path = path
    def getresponse(self): return FakeHTTPResponse(self.outputs[self.path])
    def close(self): pass


def identity(quant="Q4_K_M", ctx=8192, concurrent=1):
    return {"protocol_version": "local-llm-identity-v1", "default_model": MODEL,
            "models": {MODEL: {
                "model": {"id": MODEL, "quantization":quant,
                          "artifact_digest":None,"verification":"available_unverified"},
                "runtime": {"name":"llama_server",
                            "config_digest":"d"*64,
                            "config":{"backend":"llama_server","ctx_size":ctx,
                                      "max_concurrent_requests":concurrent}},
                "hardware":{"system":"darwin","machine":"arm64"}
            }}}


def local_response(code="import bpy\nbpy.ops.mesh.primitive_cube_add()"):
    return {
        "model":MODEL,
        "choices":[{"finish_reason":"stop",
                    "message":{"role":"assistant","content":code}}],
        "usage":{"prompt_tokens":128,"completion_tokens":90},
        "stats":{"time_total_seconds":4.5,"tokens_per_second":20.0},
    }


class KorgisProviderTests(unittest.TestCase):
    def setUp(self):
        FakeHTTPConnection.sent.clear()
        FakeHTTPConnection.outputs = {
            "/v1/runtime/identity": identity(),
            "/v1/chat/completions": local_response(),
        }

    def test_frozen_model_and_memory_profile(self):
        p=KorgisLocalCodeProvider()
        self.assertEqual(p.model,MODEL)
        self.assertEqual((p.context_tokens,p.max_output_tokens),(8192,4096))
        for invalid in ({"model":"another:qwen"}, {"context_tokens":131072},
                        {"max_output_tokens":16384}, {"temperature":-1}):
            with self.assertRaises(LocalProviderError):
                KorgisLocalCodeProvider(**invalid)

    def test_strict_loopback_identity_then_openai_wire(self):
        with patch("geometry_harness.providers.local.http.client.HTTPConnection", FakeHTTPConnection):
            p=KorgisLocalCodeProvider()
            g=p.generate("Create an editable box")
        self.assertEqual(g.model,MODEL)
        self.assertEqual(g.input_tokens,128)
        self.assertEqual(g.output_tokens,90)
        self.assertIsNone(g.cost_usd)
        self.assertEqual(p.last_telemetry.tokens_per_second,20)
        self.assertEqual(p.last_identity["models"][MODEL]["model"]["id"],MODEL)
        self.assertEqual([x[1] for x in FakeHTTPConnection.sent],
                         ["/v1/runtime/identity","/v1/chat/completions"])
        method,path,wire,headers=FakeHTTPConnection.sent[-1]
        self.assertEqual((method,path),("POST","/v1/chat/completions"))
        self.assertEqual(wire["max_tokens"],4096)
        self.assertFalse(wire["stream"])
        self.assertFalse(wire["enable_thinking"])
        self.assertEqual(wire["seed"],42)
        self.assertNotIn("Authorization",headers)

    def test_model_identity_errors_prevent_inference(self):
        for changed in (identity(quant="Q8_0"),identity(ctx=4096),
                        identity(concurrent=3),{"protocol_version":"other","models":{}}):
            FakeHTTPConnection.sent.clear()
            FakeHTTPConnection.outputs["/v1/runtime/identity"]=changed
            with patch("geometry_harness.providers.local.http.client.HTTPConnection",FakeHTTPConnection):
                with self.assertRaises(LocalProviderError):
                    KorgisLocalCodeProvider().generate("a box")
            self.assertEqual(len(FakeHTTPConnection.sent),1)

    def test_fails_closed_on_unfinished_or_wrong_model(self):
        for x in ({"model":"wrong"}, {"choices":[{"finish_reason":"length","message":{"content":"hi"}}]},
                  {"choices":[]}, {"choices":[{"finish_reason":"stop","message":{"content":"not python ("}}]}):
            FakeHTTPConnection.outputs["/v1/chat/completions"]={**local_response(),**x}
            with patch("geometry_harness.providers.local.http.client.HTTPConnection",FakeHTTPConnection):
                with self.assertRaises(LocalProviderError):
                    KorgisLocalCodeProvider().generate("a box")


def stage_fixtures(root: Path, *, tamper: bool = False):
    public, suite = root/"public", root/"suite.json"
    public.mkdir()
    rows=[]
    for task in EXPECTED_IDS:
        folder=public/task
        folder.mkdir()
        descr=("Description for "+task).encode()
        instruction=("Build "+task).encode()
        (folder/"prompt_description.txt").write_bytes(descr)
        (folder/"prompt_instruction.txt").write_bytes(instruction)
        rows.append({
            "task_id":task,
            "prompt_description_sha256":hashlib.sha256(descr).hexdigest(),
            "prompt_instruction_sha256":hashlib.sha256(instruction).hexdigest(),
        })
    suite.write_text(json.dumps({
        "benchmark":"3DCodeBench","schema_version":1,
        "dataset_revision":EXPECTED_REV,"reference_access":"scorer_only",
        "tiers":{"smoke":list(EXPECTED_IDS)},"tasks":rows,
    }))
    (public/"staging-manifest.json").write_text(json.dumps({
        "task_ids":list(EXPECTED_IDS),"dataset_revision":EXPECTED_REV,
        "source_suite_sha256":hashlib.sha256(suite.read_bytes()).hexdigest(),
        "reference_access":"NONE_in_generator_workspace",
    }))
    if tamper:
        (public/EXPECTED_IDS[0]/"prompt_instruction.txt").write_text("tampered!")
    return public,suite


class MockEngine:
    model=MODEL
    context_tokens=8192
    max_output_tokens=4096
    temperature=.1
    seed=42
    last_telemetry=None
    last_identity=None
    def __init__(self, text):
        self.text=text
        self.count=0
    def generate(self, prompt):
        from geometry_harness.providers.compatible import GeneratedCode
        self.count+=1
        return GeneratedCode(self.model,self.text,50,100)


class LocalSmokeTests(unittest.TestCase):
    def test_tampered_frozen_prompt_refused_before_any_request(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            public,suite=stage_fixtures(root,tamper=True)
            engine=MockEngine("import bpy\n")
            with patch("geometry_harness.local_smoke.blender_binary",return_value="/bin/blender"):
                with self.assertRaisesRegex(LocalSmokeError,"hash mismatch"):
                    run(root/"out",public,suite,task_ids=(EXPECTED_IDS[0],),provider=engine)
            self.assertEqual(engine.count,0)
            self.assertFalse((root/"out").exists())

    def test_safe_parser_and_mocked_native_blender(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            public,suite=stage_fixtures(root)
            engine=MockEngine(
                "import bpy\nbpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))\n"
                "obj=bpy.context.object\nobj.name='Glass pane'\nobj.dimensions=(1,1,1)\n"
            )
            def fake_blender(cmd, log, limit=180):
                log.write_text("audited Blender fixture")
                folder=log.parent
                if "build_safe_scene.py" in " ".join(map(str,cmd)):
                    (folder/"scene.blend").write_bytes(b"BLENDER")
                    from geometry_harness.cli import PNG_MAGIC
                    import struct
                    (folder/"preview.png").write_bytes(
                        PNG_MAGIC+bytes((0,0,0,13))+b"IHDR"+struct.pack(">II",800,600))
                else:
                    (folder/"geometry.json").write_text(json.dumps({"passed":True}))
            with patch("geometry_harness.local_smoke.blender_binary",return_value="/bin/blender"),patch(
                "geometry_harness.local_smoke._safe_run",side_effect=fake_blender):
                result=run(root/"out",public,suite,task_ids=(EXPECTED_IDS[0],),provider=engine)
            self.assertEqual(result["native_pass"],1)
            self.assertEqual(result["safe_source_pass"],1)
            self.assertEqual(result["api_cost_usd"],"0")
            self.assertEqual(result["result_rows"][0]["normalized_mesh_names"],1)
            self.assertEqual(engine.count,1)
            self.assertTrue((root/"out"/"local-benchmark.json").exists())


if __name__=="__main__":
    unittest.main()
