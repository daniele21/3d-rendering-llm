"""Strict loopback-only Ollama code generator for private, 32-GB Mac experiments.

No cloud fallback, API keys or remote URL configuration. Ollama is only used
for generating text; the existing AST validator and audited Blender builder
remain mandatory and execute no model-authored Python.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import re
import time

from geometry_harness.providers.compatible import GeneratedCode, _extract_code

LOOPBACK = "127.0.0.1"
PORT = 11434
CHAT_PATH = "/api/chat"
DEFAULT_MODEL = "qwen3-coder:30b-a3b-q4_K_M"
TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
MAX_BODY = 1_048_576


class LocalProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalModelTelemetry:
    total_seconds: float | None
    load_seconds: float | None
    prompt_eval_seconds: float | None
    eval_seconds: float | None
    prompt_tokens: int | None
    output_tokens: int | None
    tokens_per_second: float | None
    done_reason: str | None


def _nanoseconds(data: dict, name: str) -> float | None:
    value = data.get(name)
    if type(value) is not int or value < 0:
        return None
    return round(value / 1e9, 5)


def _count(data: dict, name: str) -> int | None:
    value = data.get(name)
    return value if type(value) is int and value >= 0 else None


class OllamaLocalCodeProvider:
    def __init__(self, *, model: str = DEFAULT_MODEL, timeout: int = 600,
                 context_tokens: int = 8192, max_output_tokens: int = 4096,
                 temperature: float = 0.1, seed: int = 42):
        if (not TAG.fullmatch(model) or "cloud" in model.lower()):
            raise LocalProviderError("Only explicit non-cloud Ollama model tags allowed")
        if not 60 <= timeout <= 1200:
            raise LocalProviderError("Invalid local timeout")
        if not 1024 <= context_tokens <= 16384:
            raise LocalProviderError("Context outside bounded 32-GB experimental profile")
        if not 128 <= max_output_tokens <= 8192:
            raise LocalProviderError("Output budget outside safe local profile")
        if type(temperature) not in (int, float) or not 0 <= temperature <= 1:
            raise LocalProviderError("Invalid local temperature")
        self.model = model
        self.timeout = timeout
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.seed = seed
        self.last_telemetry: LocalModelTelemetry | None = None

    def generate(self, prompt: str) -> GeneratedCode:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise LocalProviderError("Prompt must contain 1..12000 characters")
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": 0,  # Release 19-GB weights before launching Blender.
            "options": {
                "num_ctx": self.context_tokens, "num_predict": self.max_output_tokens,
                "temperature": self.temperature, "seed": self.seed,
            },
            "messages": [
                {"role": "system", "content": (
                    "Write only Blender 5 bpy Python that follows the user contract. "
                    "Never call files, network, subprocess or arbitrary execution. "
                    "No markdown or commentary; output literal Python statements."
                )},
                {"role": "user", "content": prompt},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        # http.client goes directly to this hard-coded loopback address;
        # no proxies, remote endpoints, redirects or API keys.
        connection = http.client.HTTPConnection(LOOPBACK, PORT, timeout=self.timeout)
        started = time.monotonic()
        self.last_telemetry = None
        try:
            connection.request(
                "POST", CHAT_PATH, data,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise LocalProviderError(f"Local Ollama returned HTTP {response.status}")
            content = response.read(MAX_BODY + 1)
            if len(content) > MAX_BODY:
                raise LocalProviderError("Local response too large")
            try:
                result = json.loads(content)
            except (ValueError, UnicodeDecodeError):
                raise LocalProviderError("Malformed local Ollama JSON") from None
        except (ConnectionError, TimeoutError, OSError):
            raise LocalProviderError(
                "Local Ollama unavailable; check ollama serve and the loaded model"
            ) from None
        finally:
            connection.close()
        if not isinstance(result, dict) or result.get("done") is not True:
            raise LocalProviderError("Ollama generation is not completed")
        actual_model = result.get("model")
        if actual_model != self.model:
            raise LocalProviderError("Local server returned a different model")
        reason = result.get("done_reason")
        if reason != "stop":
            raise LocalProviderError("Local generation stopped without full completion")
        message = result.get("message")
        if not isinstance(message, dict):
            raise LocalProviderError("Missing local Ollama response message")
        self.last_telemetry = LocalModelTelemetry(
            total_seconds=_nanoseconds(result, "total_duration"),
            load_seconds=_nanoseconds(result, "load_duration"),
            prompt_eval_seconds=_nanoseconds(result, "prompt_eval_duration"),
            eval_seconds=_nanoseconds(result, "eval_duration"),
            prompt_tokens=_count(result, "prompt_eval_count"),
            output_tokens=_count(result, "eval_count"),
            tokens_per_second=(
                round(result["eval_count"] / (result["eval_duration"] / 1e9), 2)
                if type(result.get("eval_count")) is int
                and type(result.get("eval_duration")) is int
                and result["eval_duration"] > 0 else None
            ),
            done_reason=reason,
        )
        code = _extract_code(message.get("content"))
        return GeneratedCode(
            model=self.model, code=code,
            input_tokens=self.last_telemetry.prompt_tokens,
            output_tokens=self.last_telemetry.output_tokens,
            cost_usd=None, call_id="", pricing=None,
        )
