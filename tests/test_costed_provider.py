"""Provider mock transport must produce durable per-call costs and errors."""
import io
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from geometry_harness.costs.ledger import load_events, reconcile
from geometry_harness.providers.compatible import OpenAICompatibleCodeProvider, ProviderError


class MockResponse:
    def __init__(self, data):
        self._reader = io.BytesIO(json.dumps(data).encode())

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self._reader.read(n)


def provider():
    return OpenAICompatibleCodeProvider(
        endpoint="https://api.openai.com/v1/chat/completions",
        model="gpt-6.1-sol", api_key="test-not-real",
    )


def payload():
    return {
        "id": "chatcmpl-test", "model": "gpt-6.1-sol", "service_tier": "default",
        "choices": [{"finish_reason": "stop", "message": {"content": "import bpy\nbpy.ops.mesh.primitive_cube_add()"}}],
        "usage": {
            "prompt_tokens": 1000, "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 300},
            "completion_tokens_details": {"reasoning_tokens": 30},
        },
    }


class CostedProviderTests(unittest.TestCase):
    def test_success_and_unpriced_provider_failure_are_both_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "costs" / "events.jsonl"
            env = {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1", "GEOMETRY_COST_LEDGER": str(path)}
            with patch.dict(os.environ, env), patch(
                "geometry_harness.providers.compatible.urlopen",
                return_value=MockResponse(payload()),
            ):
                out = provider().generate("create a cube")
            self.assertEqual(out.input_tokens, 1000)
            self.assertEqual(out.output_tokens, 100)
            self.assertEqual(out.cost_usd, "0.001780000")
            self.assertTrue(out.call_id)
            self.assertEqual(out.pricing["tokens"]["input_uncached"], 500)
            with patch.dict(os.environ, env), patch(
                "geometry_harness.providers.compatible.urlopen", side_effect=TimeoutError()
            ):
                with self.assertRaises(ProviderError):
                    provider().generate("create a cube")
            events = load_events(path)
            self.assertEqual([x["event"] for x in events], ["started", "settled", "started", "settled"])
            self.assertEqual(events[1]["pricing"]["tokens"]["input_cache_write_30m"], 300)
            self.assertEqual(events[-1]["pricing"]["status"], "UNKNOWN")
            self.assertEqual(reconcile(events)["grand_total_status"], "INCOMPLETE_UNKNOWN_COST")
            raw = path.read_text()
            self.assertNotIn("test-not-real", raw)
            self.assertNotIn("create a cube", raw)

    def test_incomplete_model_output_is_still_billed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = payload()
            data["choices"][0]["finish_reason"] = "length"
            path = Path(tmp) / "events.jsonl"
            with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1",
                                          "GEOMETRY_COST_LEDGER": str(path)}), patch(
                "geometry_harness.providers.compatible.urlopen",
                return_value=MockResponse(data),
            ):
                with self.assertRaisesRegex(ProviderError, "incomplete"):
                    provider().generate("cube")
            items = load_events(path)
            self.assertEqual(items[-1]["outcome"], "UNFINISHED_RESPONSE")
            self.assertEqual(items[-1]["pricing"]["status"], "PRICED")


if __name__ == "__main__":
    unittest.main()
