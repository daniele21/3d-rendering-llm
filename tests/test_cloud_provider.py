"""Provider transport contract; remote network calls disabled in normal tests."""
import io
import json
import os
from unittest.mock import patch
import unittest

from geometry_harness.providers.compatible import (
    GeneratedCode, OpenAICompatibleCodeProvider, ProviderError,
)


def provider():
    return OpenAICompatibleCodeProvider(
        endpoint="https://api.openai.com/v1/chat/completions",
        model="test-model", api_key="not-a-real-key", timeout=5,
    )


class MockResponse:
    def __init__(self, payload):
        self.content = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, count):
        return self.content.read(count)


class ProviderTests(unittest.TestCase):
    def test_import_and_calls_fail_closed_without_opt_in(self):
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": ""}):
            with self.assertRaisesRegex(ProviderError, "disabled"):
                provider().generate("a chair")
            with self.assertRaisesRegex(ProviderError, "disabled"):
                OpenAICompatibleCodeProvider.from_env()

    def test_generated_code_and_unknown_cost(self):
        payload = {"choices": [{"finish_reason": "stop", "message": {"content": "```python\nimport bpy\nbpy.ops.mesh.primitive_cube_add()\n```"}}],
                   "usage": {"prompt_tokens": 50, "completion_tokens": 12}}
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1"}), patch(
            "geometry_harness.providers.compatible.urlopen", return_value=MockResponse(payload)
        ) as send:
            result = provider().generate("create a cube")
        self.assertIsInstance(result, GeneratedCode)
        self.assertIn("primitive_cube_add", result.code)
        self.assertEqual((result.input_tokens, result.output_tokens), (50, 12))
        self.assertIsNone(result.cost_usd)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs["timeout"], 5)
        wire = json.loads(send.call_args.args[0].data)
        self.assertEqual(wire["max_completion_tokens"], 4096)
        self.assertEqual(wire["reasoning_effort"], "low")
        self.assertNotIn("max_tokens", wire)

    def test_truncated_output_is_not_accepted(self):
        payload = {"choices": [{"finish_reason": "length",
                    "message": {"content": "import bpy"}}]}
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1"}), patch(
            "geometry_harness.providers.compatible.urlopen",
            return_value=MockResponse(payload),
        ):
            with self.assertRaisesRegex(ProviderError, "incomplete"):
                provider().generate("cube")

    def test_syntax_error_is_bounded_failure(self):
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1"}), patch(
            "geometry_harness.providers.compatible.urlopen",
            return_value=MockResponse({"choices": [{"finish_reason": "stop", "message": {"content": "def bad(:\n pass"}}]}),
        ):
            with self.assertRaisesRegex(ProviderError, "syntax error"):
                provider().generate("create a cube")

    def test_no_secrets_in_error_and_bad_endpoint(self):
        with self.assertRaisesRegex(ProviderError, "HTTPS"):
            OpenAICompatibleCodeProvider(endpoint="http://localhost/v1/chat/completions",
                                         model="test", api_key="secret")
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1"}), patch(
            "geometry_harness.providers.compatible.urlopen", side_effect=TimeoutError()
        ):
            with self.assertRaises(ProviderError) as raised:
                provider().generate("cube")
            self.assertNotIn("not-a-real-key", str(raised.exception))

    def test_oversized_response_is_rejected(self):
        class OversizedResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _): return b"z" * 262145
        with patch.dict(os.environ, {"GEOMETRY_ALLOW_REMOTE_INFERENCE": "1"}), patch(
            "geometry_harness.providers.compatible.urlopen", return_value=OversizedResponse()
        ):
            with self.assertRaisesRegex(ProviderError, "size"):
                provider().generate("a chair")


if __name__ == "__main__":
    unittest.main()
