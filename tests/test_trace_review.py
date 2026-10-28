"""No-inference run-review tests: missing cost links must never count as zero."""
import json
from pathlib import Path
import tempfile
import unittest
from geometry_harness.telemetry.spans import TraceRecorder
from geometry_harness.telemetry.review import review, make_html
from geometry_harness.costs.ledger import append_event


class TimelineReviewTests(unittest.TestCase):
    def test_fixture_without_any_ai_has_no_cost_and_valid_timeline(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tracer=TraceRecorder(root)
            with tracer.span("code.compile") as stage:
                pass
            with tracer.span("blender.build",depends_on=(stage.span_id,)):
                pass
            result=review(root)
            self.assertEqual(result["billing_status"],"NOT_APPLICABLE")
            self.assertEqual(result["model_spans"],0)
            self.assertIsNone(result["model_token_usd_estimate"])
            self.assertEqual(result["trace_status"],"COMPLETE")
            self.assertEqual(len(result["timeline"]),2)
            text=make_html(result)
            self.assertIn("code.compile",text)
            self.assertIn("blender.build",text)

    def test_missing_ledger_is_unknown_even_if_span_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tracer=TraceRecorder(root)
            with tracer.span("llm.generate"):
                pass
            result=review(root)
            self.assertEqual(result["billing_status"],"UNKNOWN_MISSING_LEDGER")
            self.assertIsNone(result["model_token_usd_estimate"])

    def test_exact_cost_link_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tracer=TraceRecorder(root)
            with tracer.span("llm.generate") as span:
                span.cost_call_id="paid-1"
            ledger=root/"costs"/"events.jsonl"
            append_event(ledger,{"event":"started","call_id":"paid-1",
                                 "model_requested":"gpt-6-luna","stage":"g1"})
            append_event(ledger,{"event":"settled","call_id":"paid-1",
                                 "model_returned":"gpt-6-luna",
                                 "pricing":{"status":"PRICED","estimated_usd":"0.000010000",
                                            "tokens":{k:0 for k in (
                                              "input_total","input_uncached","input_cache_read",
                                              "input_cache_write_30m","input_cache_write_12h",
                                              "output_total","output_reasoning_subset")}}})
            result=review(root)
            self.assertEqual(result["billing_status"],"COMPLETE_ALL_MODEL_SPANS_RECONCILED")
            self.assertEqual(result["model_token_usd_estimate"],"0.000010000")
            (root/"extra").write_text("unrelated")

    def test_unlinked_spans_never_silent_zero(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tracer=TraceRecorder(root)
            with tracer.span("llm.generate"):
                pass
            ledger=root/"costs"/"events.jsonl"
            append_event(ledger,{"event":"started","call_id":"paid-1",
                                 "model_requested":"gpt-6-luna","stage":"g1"})
            result=review(root)
            self.assertEqual(result["billing_status"],"UNKNOWN_INCOMPLETE_SPAN_COST_LINKAGE")
            self.assertEqual(result["model_token_usd_estimate"],"0")


if __name__=="__main__":
    unittest.main()
