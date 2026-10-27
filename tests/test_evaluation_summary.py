"""Fast paired report checks; synthetic scores are NOT release evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from geometry_harness.evaluation.summary import (
    EvaluationRecord, EvaluationError, compare, html_report,
)


def row(task, arm, status="PASS", visual=None, cost=None, model="model", revision="rev"):
    return EvaluationRecord.parse({
        "task_id": task, "suite_revision": revision, "arm": arm,
        "model": model, "blender_version": "5.0", "source_sha": "sha",
        "status": status, "duration_seconds": 5.0, "cost_usd": cost,
        "visual_score": visual, "geometry_status": status, "run_id": arm + task,
    })


class SummaryTests(unittest.TestCase):
    def test_pairing_fail_unknown_no_fake_cost_or_visual(self):
        report = compare([
            row("A", "direct", cost=1.0, visual=.4),
            row("A", "planner", cost=2.0, visual=.8),
            row("B", "direct", status="FAIL"),
            row("B", "planner", status="UNKNOWN"),
        ], "direct", "planner")
        self.assertEqual(report["matched_tasks"], 2)
        self.assertEqual(report["arms"]["direct"]["fail_count"], 1)
        self.assertEqual(report["arms"]["planner"]["unknown_count"], 1)
        self.assertIsNone(report["arms"]["direct"]["cost_per_accepted_usd"])
        self.assertEqual(report["arms"]["direct"]["visual_scored_count"], 1)
        self.assertEqual(report["arms"]["planner"]["pass_count"], 1)

    def test_unmatched_or_incompatible_are_excluded(self):
        report = compare([
            row("A", "direct"), row("A", "planner"),
            row("B", "direct"), row("C", "direct"),
            row("C", "planner", revision="different"),
        ], "direct", "planner")
        self.assertEqual(report["matched_tasks"], 1)
        self.assertEqual({x["reason"] for x in report["excluded_tasks"]},
                         {"missing_arm", "unpaired_configuration"})

    def test_duplicate_pair_and_missing_all_rejected(self):
        with self.assertRaisesRegex(EvaluationError, "Duplicate"):
            compare([row("A", "direct"), row("A", "direct"), row("A", "planner")],
                    "direct", "planner")
        with self.assertRaisesRegex(EvaluationError, "No matched"):
            compare([row("A", "direct")], "direct", "planner")

    def test_bad_score_and_html_escape(self):
        with self.assertRaises(EvaluationError):
            row("a", "direct", visual=1.5)
        with self.assertRaises(EvaluationError):
            row("a", "direct", cost=-1)
        report = compare([row("<script>alert(1)</script>", "direct"),
                          row("<script>alert(1)</script>", "planner")], "direct", "planner")
        page = html_report(report)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
