"""No-cost six-task Luna benchmarking tests: reject code, preserve every billable call."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.benchmark_smoke import MODEL, EXPECTED_REV, conservative_max_usd, run, ShowcaseError
from geometry_harness.costs.ledger import load_events, reconcile

IDS = ["CoffeeTable_seed0","ArmChair_seed0","Bottle_seed0",
       "AquariumTank_seed0","Balloon_seed0","BrainCoral_seed0"]


class FakeResponse:
    def __init__(self, result):
        self.buf = io.BytesIO(json.dumps(result).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.buf.read(n)


def answer():
    return {
        "id":"chatcmpl-fake","model":"gpt-6-luna","service_tier":"default",
        "choices":[{"finish_reason":"stop","message":{"content":(
            "import bpy\nfor i in range(4):\n"
            "    bpy.ops.mesh.primitive_cube_add()\n")}}],
        "usage":{"prompt_tokens":500, "completion_tokens":100,
                 "prompt_tokens_details":{"cached_tokens":0,"cache_write_tokens":0},
                 "completion_tokens_details":{"reasoning_tokens":10}},
    }


def inputs(root):
    public = root / "public"
    public.mkdir()
    suite = root / "suite.json"
    suite.write_text(json.dumps({"benchmark":"3DCodeBench", "dataset_revision":EXPECTED_REV,
                                 "reference_access":"scorer_only", "tiers":{"smoke":IDS}}))
    (public / "staging-manifest.json").write_text(json.dumps({
        "task_ids":IDS, "dataset_revision":EXPECTED_REV, "reference_access":"NONE_in_generator_workspace",
    }))
    for task in IDS:
        part = public / task
        part.mkdir()
        (part/"prompt_description.txt").write_text("Describe a physical object.")
        (part/"prompt_instruction.txt").write_text("Build its geometry.")
    return public, suite


class LunaSmokeTests(unittest.TestCase):
    def test_conservative_upper_bound_includes_cache_write_and_output(self):
        self.assertGreater(conservative_max_usd("small"), 0)
        self.assertLess(conservative_max_usd("small") * 6, 0.05)

    def test_wrong_model_fails_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public, suite = inputs(root)
            with patch.dict(os.environ, {
                "GEOMETRY_ALLOW_REMOTE_INFERENCE":"1",
                "GEOMETRY_CLOUD_MODEL":"gpt-6.1-sol",
                "GEOMETRY_CLOUD_API_KEY":"fake",
                "GEOMETRY_COST_LEDGER":str(root/"out"/"costs"/"events.jsonl"),
            }), patch("geometry_harness.providers.compatible.urlopen") as http:
                with self.assertRaisesRegex(ShowcaseError,"Luna-only"):
                    run(root/"out", public, suite)
                http.assert_not_called()
            self.assertFalse((root/"out").exists())

    def test_last_billed_model_failure_is_counted_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public, suite = inputs(root)
            out = root/"out"
            calls = {"n": 0}
            def respond(*_args, **_kwargs):
                calls["n"] += 1
                data = answer()
                if calls["n"] == 6:
                    data["choices"][0]["finish_reason"] = "length"
                return FakeResponse(data)
            env = {"GEOMETRY_ALLOW_REMOTE_INFERENCE":"1", "GEOMETRY_CLOUD_MODEL":MODEL,
                   "GEOMETRY_CLOUD_API_KEY":"fake-not-real",
                   "GEOMETRY_COST_LEDGER":str(out/"costs"/"events.jsonl")}
            with patch.dict(os.environ, env), patch(
                    "geometry_harness.benchmark_smoke.blender_binary",
                    return_value="/fake/not/executed"), patch(
                    "geometry_harness.providers.compatible.urlopen",
                    side_effect=respond):
                result = run(out, public, suite)
            self.assertEqual(calls["n"], 6)
            self.assertEqual(result["status"], "COMPLETE_INTERNAL_SMOKE")
            self.assertEqual(result["task_failures"], 6)
            self.assertEqual(result["model_calls_recorded"], 6)
            self.assertEqual(result["cost_reconciliation"], "COMPLETE")
            self.assertEqual(result["aborted_reason"], "ProviderError")
            self.assertEqual(reconcile(load_events(out/"costs"/"events.jsonl"))["priced_subtotal_usd"],
                             "0.000600000")
            last = json.loads((out/"tasks"/IDS[-1]/"result.json").read_text())
            self.assertEqual(last["provider_outcome"], "FAIL_OR_NOT_RUN")
            self.assertEqual(last["error_class"], "ProviderError")

    def test_six_invalid_3d_scripts_are_six_costed_failures_no_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public, suite = inputs(root)
            out = root/"out"
            env = {"GEOMETRY_ALLOW_REMOTE_INFERENCE":"1", "GEOMETRY_CLOUD_MODEL":MODEL,
                   "GEOMETRY_CLOUD_API_KEY":"fake-not-real",
                   "GEOMETRY_COST_LEDGER":str(out/"costs"/"events.jsonl")}
            with patch.dict(os.environ, env), patch(
                    "geometry_harness.benchmark_smoke.blender_binary",
                    return_value="/fake/not/executed"), patch(
                    "geometry_harness.providers.compatible.urlopen",
                    side_effect=lambda *_a, **_k: FakeResponse(answer())):
                result = run(out, public, suite)
            self.assertEqual(result["status"], "COMPLETE_INTERNAL_SMOKE")
            self.assertEqual(result["attempted"], 6)
            self.assertEqual(result["model_calls_recorded"], 6)
            self.assertEqual(result["scene_passes"], 0)
            self.assertEqual(result["quality_status"], "UNKNOWN_NO_UPSTREAM_SCORER")
            self.assertEqual(result["model_estimated_usd"], "0.000600000")
            events = load_events(out/"costs"/"events.jsonl")
            self.assertEqual(len(events), 12)
            self.assertEqual({x.get("benchmark_task_id") for x in events}, set(IDS))
            self.assertEqual(reconcile(events)["grand_total_status"], "COMPLETE")
            self.assertEqual(json.loads((out/"bundle-manifest.json").read_text())["model"], MODEL)
            self.assertNotIn("fake-not-real", (out/"costs"/"events.jsonl").read_text())
            for tid in IDS:
                task = json.loads((out/"tasks"/tid/"result.json").read_text())
                self.assertEqual(task["safe_source"], "FAIL")
                self.assertEqual(task["native_scene"], "UNKNOWN")
                self.assertFalse((out/"tasks"/tid/"scene.blend").exists())


if __name__ == "__main__":
    unittest.main()
