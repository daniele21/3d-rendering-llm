"""Minimal opt-in OpenAI-compatible text-to-Blender-code provider.

This adapter **only generates code text**; it does not execute it. Execution
must later use the bounded Blender process and filesystem restrictions from
the Geometry Harness. Closed model calls are never part of automatic CI.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """Sanitized provider or configuration failure."""


@dataclass(frozen=True)
class GeneratedCode:
    model: str
    code: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: None = None  # Unknown until an audited pricing source is configured.


def _endpoint(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.fragment or parsed.query):
        raise ProviderError("Cloud provider endpoint must be a bare HTTPS URL")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"} or parsed.hostname.endswith(".local"):
        raise ProviderError("Loopback/local endpoints require a separate local adapter")
    if parsed.path.rstrip("/") != "/v1/chat/completions":
        raise ProviderError("Endpoint must target /v1/chat/completions")
    return url


def _extract_code(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("Model returned no code")
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[0].strip().lower() in {"```", "```python"} or lines[-1].strip() != "```":
            raise ProviderError("Invalid fenced code response")
        text = "\n".join(lines[1:-1]).strip()
    if not text or len(text) > 160_000:
        raise ProviderError("Generated Blender code is empty or too long")
    try:
        ast.parse(text, filename="generated_blender.py")
    except SyntaxError as exc:
        raise ProviderError(f"Generated Blender Python syntax error at line {exc.lineno}") from None
    return text + "\n"


class OpenAICompatibleCodeProvider:
    def __init__(self, *, endpoint: str, model: str, api_key: str, timeout: int = 60,
                 max_output_tokens: int = 4096):
        self.endpoint = _endpoint(endpoint)
        if not model.strip() or any(x in model for x in "\r\n"):
            raise ProviderError("Missing or invalid model identifier")
        if not api_key:
            raise ProviderError("Provider API key is required for this opt-in profile")
        if not 1 <= timeout <= 180 or not 1 <= max_output_tokens <= 8192:
            raise ProviderError("Provider limits outside permitted range")
        self.model = model
        self._key = api_key
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens

    @classmethod
    def from_env(cls) -> "OpenAICompatibleCodeProvider":
        if os.environ.get("GEOMETRY_ALLOW_REMOTE_INFERENCE") != "1":
            raise ProviderError("Remote inference disabled; set GEOMETRY_ALLOW_REMOTE_INFERENCE=1 explicitly")
        return cls(
            endpoint=os.environ.get("GEOMETRY_CLOUD_ENDPOINT", "https://api.openai.com/v1/chat/completions"),
            model=os.environ.get("GEOMETRY_CLOUD_MODEL", "").strip(),
            api_key=os.environ.get("GEOMETRY_CLOUD_API_KEY", ""),
        )

    def generate(self, prompt: str) -> GeneratedCode:
        if os.environ.get("GEOMETRY_ALLOW_REMOTE_INFERENCE") != "1":
            raise ProviderError("Remote inference is disabled")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12_000:
            raise ProviderError("Prompt must be nonempty and within 12,000 characters")
        body = {
            "model": self.model,
            "max_completion_tokens": self.max_output_tokens,
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": (
                    "Write ONLY executable Blender Python 5.0 source code for the user request. "
                    "Use bpy to build named editable scene objects. No markdown, external files, "
                    "network calls, subprocesses or download operations. "
                    "Do not claim a render was generated; output source only."
                )},
                {"role": "user", "content": prompt},
            ],
        }
        request = Request(self.endpoint, data=json.dumps(body).encode("utf-8"),
                          headers={"Authorization": "Bearer " + self._key,
                                   "Content-Type": "application/json"},
                          method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(262145)
        except HTTPError as exc:
            raise ProviderError(f"Cloud provider returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError("Cloud provider unavailable or timed out") from None
        if len(raw) > 262144:
            raise ProviderError("Provider response exceeds size limit")
        try:
            payload = json.loads(raw)
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ProviderError("Model generation incomplete or refused")
            message = choice["message"]["content"]
            usage = payload.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            def token(key):
                value = usage.get(key)
                return value if type(value) is int and value >= 0 else None
            return GeneratedCode(model=self.model, code=_extract_code(message),
                                 input_tokens=token("prompt_tokens"),
                                 output_tokens=token("completion_tokens"))
        except (UnicodeDecodeError, json.JSONDecodeError, IndexError, KeyError, TypeError):
            raise ProviderError("Provider response has no valid generated code") from None
