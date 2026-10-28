"""Ledger handles complete, incomplete and concurrent calls without secrets."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from geometry_harness.costs.ledger import append_event, load_events, reconcile, LedgerError
from geometry_harness.costs.pricing import price_usage


def priced():
    return price_usage({"prompt_tokens": 1000, "completion_tokens": 100,
                        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                        "completion_tokens_details": {"reasoning_tokens": 30}},
                       model="gpt-6.1-sol")


class LedgerTests(unittest.TestCase):
    def test_append_reconcile_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger" / "events.jsonl"
            append_event(path, {"call_id": "a", "event": "started",
                                "model_requested": "gpt-6.1-sol", "stage": "generation"})
            append_event(path, {"call_id": "a", "event": "settled",
                                "outcome": "COMPLETED", "pricing": priced()})
            append_event(path, {"call_id": "b", "event": "started",
                                "model_requested": "gpt-6.1-sol", "stage": "generation"})
            r = reconcile(load_events(path))
            self.assertEqual(r["recorded_calls"], 2)
            self.assertEqual(r["grand_total_status"], "INCOMPLETE_UNKNOWN_COST")
            self.assertEqual(r["priced_subtotal_usd"], "0.003000000")
            self.assertEqual(r["by_model_stage"][0]["priced_calls"], 1)
            self.assertEqual(r["by_model_stage"][0]["unpriced_calls"], 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("secret", path.read_text())

    def test_malformed_or_orphan_rejected(self):
        with self.assertRaises(LedgerError):
            reconcile([{"call_id": "a", "event": "settled", "pricing": priced()}])
        with self.assertRaises(LedgerError):
            reconcile([{"call_id": "a", "event": "started"},
                       {"call_id": "a", "event": "started"}])

    def test_symlink_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "events.jsonl"
            link.symlink_to(Path(tmp) / "target")
            with self.assertRaises(LedgerError):
                append_event(link, {"event": "started", "call_id": "a"})


if __name__ == "__main__":
    unittest.main()
