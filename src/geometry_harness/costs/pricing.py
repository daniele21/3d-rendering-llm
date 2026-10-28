"""Versioned token pricing; costs are usage-derived estimates, not invoices.

Official OpenAI model pricing: https://developers.openai.com/api/docs/models/gpt-6.1-sol
Prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
Rates USD per 1M tokens; standard global API, no fast/region surcharge.
Do not silently apply unknown model, service tier or incomplete usage.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

PRICE_SNAPSHOT = "openai-2026-10-28-standard-global-v1"
LONG_CONTEXT_AT = 272000  # input > 272k billed at long context rates, for entire request
RATE_CARD = {
    "gpt-6.1-sol": {
        "short": ("2", "0.10", "2.50", "5", "10"),
        "long": ("4", "0.20", "5", "10", "15"),
    },
}
MILLION = Decimal(1_000_000)


def _as_tokens(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid or missing {field}")
    return value


def _get_details(usage, style):
    if style == "chat":
        return usage.get("prompt_tokens_details"), usage.get("completion_tokens_details")
    return usage.get("input_tokens_details"), usage.get("output_tokens_details")


def price_usage(usage: dict | None, *, model: str, api_style: str = "chat",
                service_tier: str = "standard", region: str = "global",
                cache_ttl: str = "30m") -> dict:
    """Return exhaustive usage and cost breakdown, or pricing UNKNOWN with a reason.

    Cache reads, writes (30m and 12h) and ordinary input are **disjoint**.
    Output (including reasoning tokens) is charged once; reasoning is a
    reported subset, never a separate additive fee.
    """
    base = {"currency": "USD", "pricing_revision": PRICE_SNAPSHOT,
            "model": model, "service_tier": service_tier, "region": region,
            "api_style": api_style, "cache_ttl": cache_ttl, "status": "UNKNOWN",
            "estimated_usd": None, "components_usd": None,
            "tokens": None, "reason": None}
    try:
        if not isinstance(usage, dict):
            raise ValueError("Provider usage missing")
        if api_style not in {"chat", "responses"}:
            raise ValueError("Unknown API response format")
        if service_tier not in {"standard", "default"} or region != "global":
            raise ValueError("Unsupported service tier or regional pricing")
        if model not in RATE_CARD:
            raise ValueError("No versioned tariff for actual model")
        input_key, output_key = (("prompt_tokens", "completion_tokens")
                                 if api_style == "chat" else ("input_tokens", "output_tokens"))
        ins = _as_tokens(usage.get(input_key), input_key)
        outs = _as_tokens(usage.get(output_key), output_key)
        input_detail, output_detail = _get_details(usage, api_style)
        if not isinstance(input_detail, dict):
            raise ValueError("Detailed input usage missing; cached/uncached cannot be separated")
        cached = _as_tokens(input_detail.get("cached_tokens"), "cached_tokens")
        if output_detail is None:
            reasoning = None
        elif isinstance(output_detail, dict):
            reasoning = output_detail.get("reasoning_tokens")
            if reasoning is not None:
                reasoning = _as_tokens(reasoning, "reasoning_tokens")
        else:
            raise ValueError("Invalid output-token detail")
        if reasoning is not None and reasoning > outs:
            raise ValueError("Reasoning token subset exceeds output")
        writes = input_detail.get("cache_write_tokens", 0)
        if writes is None:
            raise ValueError("Unreported cache-write count")
        writes = _as_tokens(writes, "cache_write_tokens")
        write_breakdown = input_detail.get("cache_write_tokens_details")
        if api_style == "responses" and isinstance(write_breakdown, dict):
            w30 = _as_tokens(write_breakdown.get("ttl_30m_tokens"), "ttl_30m_tokens")
            w12 = _as_tokens(write_breakdown.get("ttl_12h_tokens"), "ttl_12h_tokens")
            if w30 + w12 != writes:
                raise ValueError("Cache-write breakdown inconsistent with total")
        elif writes:
            # Chat Completions uses default 30m writes. Responses can use 12h;
            # without a duration split we MUST NOT invent an allocation.
            if api_style == "responses" and cache_ttl != "30m":
                raise ValueError("Cache-write duration split unavailable")
            w30, w12 = writes, 0
        else:
            w30, w12 = 0, 0
        if cached + writes > ins:
            raise ValueError("Cached/read/write tokens exceed total input")
        ordinary = ins - cached - writes
        rates = RATE_CARD[model]["long" if ins > LONG_CONTEXT_AT else "short"]
        names = ("uncached_input", "cached_input", "cache_write_30m", "cache_write_12h", "output")
        counts = (ordinary, cached, w30, w12, outs)
        amounts = {name: (Decimal(n) * Decimal(rate) / MILLION)
                   for name, n, rate in zip(names, counts, rates)}
        total = sum(amounts.values(), Decimal("0"))
        base.update({
            "status": "PRICED", "reason": None, "context_band": "long" if ins > LONG_CONTEXT_AT else "short",
            "rates_per_million": dict(zip(names, rates)),
            "tokens": {"input_total": ins, "input_uncached": ordinary,
                       "input_cache_read": cached, "input_cache_write_30m": w30,
                       "input_cache_write_12h": w12, "input_cache_write_total": writes,
                       "output_total": outs, "output_reasoning_subset": reasoning,
                       "output_nonreasoning": outs - reasoning if reasoning is not None else None},
            "components_usd": {name: str(value) for name, value in amounts.items()},
            "estimated_usd": str(total.quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)),
        })
    except (ValueError, TypeError) as exc:
        base["reason"] = str(exc)
    return base
