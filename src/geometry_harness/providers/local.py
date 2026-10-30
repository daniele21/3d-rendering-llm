"""Korgis-only loopback client for offline restricted Blender-code experiments.

The application delegates loading, model resource admission and residency to
Korgis. No arbitrary endpoint, credentials, proxy, cloud fallback or model
code execution is allowed. Output still goes through safe AST/Blender.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
import time

from geometry_harness.providers.compatible import GeneratedCode, ProviderError, _extract_code

HOST = "127.0.0.1"
PORT = 1235
DEFAULT_MODEL = "qwen3-coder-30b-q4km"
MAX_BODY = 1_048_576


class LocalProviderError(RuntimeError):
    """Fail closed on a local Korgis or model-identity violation."""


@dataclass(frozen=True)
class LocalModelTelemetry:
    total_seconds: float | None
    input_tokens: int | None
    output_tokens: int | None
    tokens_per_second: float | None
    backend: str


def _numeric(value: object) -> float | None:
    if type(value) in (float, int) and math.isfinite(value) and value >= 0:
        return float(value)
    return None


def _count(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


class KorgisLocalCodeProvider:
    def __init__(self, *, model: str = DEFAULT_MODEL, timeout: int = 1200,
                 context_tokens: int = 8192, max_output_tokens: int = 4096,
                 temperature: float = 0.1, seed: int = 42):
        if model != DEFAULT_MODEL:
            raise LocalProviderError("Only the frozen Korgis Qwen3-Coder model key is permitted")
        if not 60 <= timeout <= 1800:
            raise LocalProviderError("Invalid Korgis timeout")
        if not 1024 <= context_tokens <= 8192:
            raise LocalProviderError("Context outside the 32 GB experimental bound")
        if not 128 <= max_output_tokens <= 8192:
            raise LocalProviderError("Output outside the experimental bound")
        if type(temperature) not in (int, float) or not 0 <= temperature <= 1:
            raise LocalProviderError("Invalid local sampling temperature")
        if type(seed) is not int or seed < 0:
            raise LocalProviderError("Invalid seed")
        self.model = model
        self.timeout = timeout
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.seed = seed
        self.last_telemetry: LocalModelTelemetry | None = None
        self.last_identity: dict | None = None

    def _json(self, method: str, path: str, payload: dict | None = None) -> dict:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=self.timeout)
        try:
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            conn.request(
                method, path, body,
                headers={"Accept": "application/json",
                         "Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            if resp.status != 200:
                raise LocalProviderError(
                    f"Korgis on loopback returned HTTP {resp.status} for {path}"
                )
            data = resp.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise LocalProviderError("Oversized local Korgis response")
            try:
                result = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise LocalProviderError("Malformed local Korgis JSON") from None
            if not isinstance(result, dict):
                raise LocalProviderError("Invalid local Korgis response object")
            return result
        except (ConnectionError, TimeoutError, OSError):
            raise LocalProviderError(
                "Korgis unavailable on 127.0.0.1:1235; start the frozen local profile"
            ) from None
        finally:
            conn.close()

    def _identity(self) -> dict:
        identity = self._json("GET", "/v1/runtime/identity")
        if identity.get("protocol_version") != "local-llm-identity-v1":
            raise LocalProviderError("Korgis execution identity protocol mismatch")
        resident = identity.get("models")
        if not isinstance(resident, dict):
            raise LocalProviderError("Missing Korgis resident-model identity")
        selected = resident.get(self.model)
        if not isinstance(selected, dict):
            raise LocalProviderError("Frozen local Qwen model is not resident")
        model = selected.get("model") or {}
        runtime = selected.get("runtime") or {}
        config = runtime.get("config") or {}
        if (model.get("id") != self.model
                or model.get("quantization") != "Q4_K_M"
                or runtime.get("name") != "llama_server"
                or config.get("ctx_size") != self.context_tokens
                or config.get("max_concurrent_requests") != 1):
            raise LocalProviderError(
                "Korgis model, quantization, backend, context or concurrency differs"
            )
        # Korgis' public identity is an allowlisted projection that excludes
        # model paths, prompt content, credentials and private hostnames.
        return identity

    def generate(self, prompt: str) -> GeneratedCode:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise LocalProviderError("Prompt must be 1..12000 characters")
        self.last_telemetry = None
        self.last_identity = self._identity()
        started = time.monotonic()
        result = self._json("POST", "/v1/chat/completions", {
            "model": self.model,
            "stream": False,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "seed": self.seed,
            "enable_thinking": False,
            "show_thinking": False,
            "messages": [
                {"role": "system", "content": (
                    "Write ONLY literal Python Blender 5 bpy statements compatible "
                    "with the user contract. No markdown, other imports, function "
                    "calls, files, network access, subprocesses, external assets "
                    "or computed expressions. Never claim to have rendered."
                )},
                {"role": "user", "content": prompt},
            ],
        })
        if result.get("model") != self.model:
            raise LocalProviderError("Korgis returned a different model identity")
        choices = result.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise LocalProviderError("Korgis did not return exactly one model choice")
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise LocalProviderError("Local generation unfinished or refused")
        msg = choice.get("message")
        if not isinstance(msg, dict):
            raise LocalProviderError("Local generation omitted message")
        usage = result.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        stats = result.get("stats") or {}
        if not isinstance(stats, dict):
            stats = {}
        self.last_telemetry = LocalModelTelemetry(
            total_seconds=(_numeric(stats.get("time_total_seconds"))
                           or round(time.monotonic() - started, 4)),
            input_tokens=_count(usage.get("prompt_tokens")),
            output_tokens=_count(usage.get("completion_tokens")),
            tokens_per_second=_numeric(stats.get("tokens_per_second")),
            backend="llama_server",
        )
        try:
            code = _extract_code(msg.get("content"))
        except ProviderError as exc:
            raise LocalProviderError(f"Local model output rejected: {exc}") from None
        return GeneratedCode(
            model=self.model, code=code,
            input_tokens=self.last_telemetry.input_tokens,
            output_tokens=self.last_telemetry.output_tokens,
            cost_usd=None, call_id="", pricing=None,
        )
