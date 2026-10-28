"""Deterministic pricing tests. No network and no billed calls."""
import unittest

from geometry_harness.costs.pricing import price_usage


def chat(i=12000, cached=4000, writes=7000, output=500):
    return {
        "prompt_tokens": i, "completion_tokens": output,
        "prompt_tokens_details": {"cached_tokens": cached, "cache_write_tokens": writes},
        "completion_tokens_details": {"reasoning_tokens": 200},
    }


class PricingTests(unittest.TestCase):
    def test_cache_read_write_and_reasoning_not_double_billed(self):
        r = price_usage(chat(), model="gpt-6.1-sol")
        self.assertEqual(r["status"], "PRICED")
        self.assertEqual(r["tokens"]["input_uncached"], 1000)
        self.assertEqual(r["tokens"]["input_cache_read"], 4000)
        self.assertEqual(r["tokens"]["input_cache_write_30m"], 7000)
        self.assertEqual(r["tokens"]["output_total"], 500)
        self.assertEqual(r["tokens"]["output_reasoning_subset"], 200)
        # (1000*2 + 4000*.1 + 7000*2.5 + 500*10)/1e6
        self.assertEqual(r["estimated_usd"], "0.024900000")

    def test_long_context_is_full_request_rate(self):
        r = price_usage(chat(i=273000, cached=4000, writes=7000, output=500),
                        model="gpt-6.1-sol")
        self.assertEqual(r["context_band"], "long")
        self.assertEqual(r["rates_per_million"]["output"], "15")
        self.assertEqual(r["tokens"]["input_uncached"], 262000)
        self.assertEqual(r["estimated_usd"], "1.097300000")

    def test_short_long_boundary_and_missing_unknown(self):
        r = price_usage(chat(i=272000, cached=4000, writes=7000), model="gpt-6.1-sol")
        self.assertEqual(r["context_band"], "short")
        for r in (
            price_usage(None, model="gpt-6.1-sol"),
            price_usage(chat(), model="gpt-unknown"),
            price_usage(chat(), model="gpt-6.1-sol", service_tier="fast"),
            price_usage(chat(), model="gpt-6.1-sol", region="eu"),
            price_usage({"prompt_tokens": 200, "completion_tokens": 10}, model="gpt-6.1-sol"),
            price_usage(chat(i=1000), model="gpt-6.1-sol"),
        ):
            self.assertEqual(r["status"], "UNKNOWN")
            self.assertIsNone(r["estimated_usd"])

    def test_explicit_response_cache_write_lifetimes(self):
        usage = {
            "input_tokens": 12000, "output_tokens": 500,
            "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000,
                "cache_write_tokens_details": {"ttl_30m_tokens": 3000, "ttl_12h_tokens": 4000}},
            "output_tokens_details": {"reasoning_tokens": 200},
        }
        r = price_usage(usage, model="gpt-6.1-sol", api_style="responses", cache_ttl="12h")
        self.assertEqual(r["status"], "PRICED")
        # (1000*2 + 4000*.1 + 3000*2.5 + 4000*5 + 500*10)/1e6
        self.assertEqual(r["estimated_usd"], "0.034900000")

    def test_incomplete_response_duration_breakdown_unknown(self):
        usage = {
            "input_tokens": 12000, "output_tokens": 500,
            "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000},
        }
        r = price_usage(usage, model="gpt-6.1-sol", api_style="responses", cache_ttl="12h")
        self.assertEqual(r["status"], "UNKNOWN")
        usage["input_tokens_details"]["cache_write_tokens_details"] = {
            "ttl_30m_tokens": 8000, "ttl_12h_tokens": 0,
        }
        r = price_usage(usage, model="gpt-6.1-sol", api_style="responses")
        self.assertEqual(r["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
