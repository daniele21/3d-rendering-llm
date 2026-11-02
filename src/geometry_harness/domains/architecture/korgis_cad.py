"""Strict Korgis loopback JSON-text provider for architecture CAD proposals.

Reuses the Korgis identity contract established by Geometry G1 #67, but
does NOT reuse its Blender-Python output extractor. Does not load/start a
local model, execute returned code or fall back to remote inference.
"""
from __future__ import annotations
import hashlib
import http.client
import json
import math
import time

HOST="127.0.0.1"
PORT=1235
MODEL="qwen3-coder-30b-q4km"
MAX_RESPONSE_BYTES=131072
SYSTEM_MESSAGE=(
    "You are a bounded CAD assistant. Use ONLY the measured architecture "
    "information supplied in the user message. Never invent wall structure, "
    "dimensions, permissions or IDs. Output ONLY one JSON object with one "
    "of exactly two shapes. For an authorized move: "
    '{"schema_version":1,"operation_type":"move_door","target_id":"door_001","delta_mm":300}. '
    "For a blocked or unknown structural/locked/ambiguous request: "
    '{"schema_version":1,"decision":"review_required","reason_code":"STRUCTURAL_UNKNOWN"}. '
    "Allowed review reason codes: STRUCTURAL_UNKNOWN, LOCKED_ENTITY, "
    "AMBIGUOUS_TARGET. No prose, markdown, tool calls, Python or DXF source."
)
PROFILE={"model":MODEL,"ctx_size":8192,"max_tokens":384,
         "temperature":0.0,"seed":42,"enable_thinking":False}
class LocalCADProviderReject(RuntimeError):
    pass

def _nonnegative(v):
    return v if type(v) in (float,int) and math.isfinite(v) and v>=0 else None

def _usage(v):
    return v if type(v) is int and 0<=v<=1_000_000 else None

class KorgisCADTextProvider:
    def __init__(self,*,timeout=180,context_tokens=8192,max_output_tokens=384,
                 seed=42,temperature=0.0):
        if (type(timeout) is not int or not 60<=timeout<=600 or
                type(context_tokens) is not int or context_tokens!=8192 or
                type(max_output_tokens) is not int or max_output_tokens!=384 or
                type(seed) is not int or seed!=42 or
                type(temperature) not in (int,float) or temperature!=0):
            raise LocalCADProviderReject("Only frozen 32GB Qwen CAD profile allowed")
        self.timeout=timeout
        self.identity=None

    def _request(self,method,path,payload=None):
        if path not in ("/v1/runtime/identity","/v1/chat/completions"):
            raise LocalCADProviderReject("Only two frozen loopback endpoints allowed")
        conn=http.client.HTTPConnection(HOST,PORT,timeout=self.timeout)
        try:
            body=None if payload is None else json.dumps(payload,separators=(",",":")).encode("utf8")
            conn.request(method,path,body,headers={
                "Accept":"application/json","Content-Type":"application/json"})
            resp=conn.getresponse()
            if resp.status!=200:
                raise LocalCADProviderReject(f"Korgis local endpoint {path} returned HTTP {resp.status}")
            raw=resp.read(MAX_RESPONSE_BYTES+1)
            if len(raw)>MAX_RESPONSE_BYTES:
                raise LocalCADProviderReject("Korgis oversized response")
            try:
                result=json.loads(raw)
            except (UnicodeError,ValueError):
                raise LocalCADProviderReject("Invalid JSON from Korgis") from None
            if type(result) is not dict:
                raise LocalCADProviderReject("Invalid Korgis top-level response")
            return result
        except (TimeoutError,OSError,ConnectionError) as exc:
            raise LocalCADProviderReject("Korgis unavailable at 127.0.0.1:1235") from None
        finally:
            conn.close()

    def preflight(self):
        identity=self._request("GET","/v1/runtime/identity")
        if identity.get("protocol_version")!="local-llm-identity-v1":
            raise LocalCADProviderReject("Korgis protocol identity mismatch")
        models=identity.get("models")
        selected=models.get(MODEL) if type(models) is dict else None
        if type(selected) is not dict:
            raise LocalCADProviderReject("Frozen local model not resident in Korgis")
        model=selected.get("model")
        runtime=selected.get("runtime")
        if type(model) is not dict or type(runtime) is not dict:
            raise LocalCADProviderReject("Incomplete local model identity")
        cfg=runtime.get("config")
        if (type(cfg) is not dict or
                model.get("id")!=MODEL or
                model.get("quantization")!="Q4_K_M" or
                runtime.get("name")!="llama_server" or
                cfg.get("ctx_size")!=8192 or
                cfg.get("max_concurrent_requests")!=1):
            raise LocalCADProviderReject("Korgis resident model/backend/resource profile drift")
        # Only allowlisted facts. Do not publish local paths or raw identity.
        self.identity={
            "identity_protocol":"local-llm-identity-v1",
            "model":MODEL,"quantization":"Q4_K_M",
            "backend":"llama_server","ctx_size":8192,
            "concurrent_requests":1,
            "identity_projection_sha256":hashlib.sha256(
                json.dumps(identity,sort_keys=True,default=str).encode("utf8")).hexdigest(),
            "gguf_full_digest_verified":False,
        }
        return dict(self.identity)

    def generate(self,prompt):
        if self.identity is None:
            raise LocalCADProviderReject("Read-only Korgis identity preflight required first")
        if type(prompt) is not str or not 1<=len(prompt)<=8000:
            raise LocalCADProviderReject("Bounded synthetic prompt required")
        request={
            "model":MODEL,"stream":False,"max_tokens":384,
            "temperature":0.0,"seed":42,"enable_thinking":False,
            "show_thinking":False,
            "messages":[{"role":"system","content":SYSTEM_MESSAGE},
                        {"role":"user","content":prompt}],
        }
        started=time.monotonic()
        data=self._request("POST","/v1/chat/completions",request)
        elapsed=round(time.monotonic()-started,5)
        if data.get("model")!=MODEL:
            raise LocalCADProviderReject("Model response identity mismatch")
        choices=data.get("choices")
        if type(choices) is not list or len(choices)!=1 or type(choices[0]) is not dict:
            raise LocalCADProviderReject("Invalid Korgis choice count")
        choice=choices[0]
        if choice.get("finish_reason")!="stop":
            raise LocalCADProviderReject("Model did not complete a bounded response")
        msg=choice.get("message")
        response=msg.get("content") if type(msg) is dict else None
        if type(response) is not str or not 1<=len(response.encode("utf8"))<=2048:
            raise LocalCADProviderReject("Missing or oversized model JSON text")
        usage=data.get("usage") or {}
        if type(usage) is not dict:
            usage={}
        stats=data.get("stats") or {}
        if type(stats) is not dict:
            stats={}
        return {
            "response_text":response,
            "model":MODEL,
            "duration_seconds":elapsed,
            "provider_reported_seconds":_nonnegative(stats.get("time_total_seconds")),
            "tokens_per_second":_nonnegative(stats.get("tokens_per_second")),
            "input_tokens":_usage(usage.get("prompt_tokens")),
            "output_tokens":_usage(usage.get("completion_tokens")),
            "finish_reason":"stop",
            "backend":"korgis_llama_server_loopback",
            "system_prompt_sha256":hashlib.sha256(SYSTEM_MESSAGE.encode("utf8")).hexdigest(),
        }
