"""Finite, overlap-correct span reports. No paid calls or secrets."""
import json
from pathlib import Path
import tempfile
import unittest

from geometry_harness.telemetry.spans import TraceRecorder, summarize, TraceError, write_summary


def ev(i, event, t, parent=None, name="blender.build", status="PASS", cost=None):
    x = {"span_id": i, "run_id": "r", "trace_id": "t", "name": name,
         "parent_span_id": parent, "monotonic_ns": t, "event": event}
    if event == "finished":
        x.update({"status": status, "cost_call_id": cost})
    return x


class TraceTests(unittest.TestCase):
    def test_overlapping_children_are_union_not_added(self):
        trace = [
            ev("root", "started", 0, name="task.run"),
            ev("a", "started", 1000000, parent="root"),
            ev("b", "started", 3000000, parent="root"),
            ev("a", "finished", 6000000, parent="root", cost="call-a"),
            ev("b", "finished", 8000000, parent="root"),
            ev("root", "finished", 10000000, name="task.run"),
        ]
        r = summarize(trace)
        self.assertEqual(r["status"], "COMPLETE")
        self.assertEqual(r["observed_wall_ms"], 10)
        root = next(s for s in r["spans"] if s["name"] == "task.run")
        self.assertEqual(root["exclusive_ms"], 3)
        self.assertEqual(r["critical_path"], "UNKNOWN_WITHOUT_DEPENDENCY_EDGES")

    def test_explicit_dag_chain_is_measured_not_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            tracer = TraceRecorder(Path(td))
            with tracer.span("code.compile") as first:
                pass
            with tracer.span("blender.build", depends_on=(first.span_id,)) as second:
                pass
            with tracer.span("scene.reopen", depends_on=(second.span_id,)):
                pass
            report = write_summary(Path(td))
            self.assertEqual(report["critical_path"], "MEASURED_EXPLICIT_SPAN_DEPENDENCIES")
            self.assertEqual(report["critical_chain_stages"],
                             ["code.compile", "blender.build", "scene.reopen"])
            self.assertGreaterEqual(report["critical_chain_ms"], 0)
            self.assertLessEqual(report["critical_chain_ms"], report["observed_wall_ms"] + 1)

    def test_dependency_fails_closed_when_unfinished_or_foreign(self):
        with tempfile.TemporaryDirectory() as td:
            tracer = TraceRecorder(Path(td))
            with self.assertRaises(TraceError):
                with tracer.span("scene.reopen", depends_on=("other-trace",)):
                    pass
            with tracer.span("task.run") as root:
                with self.assertRaises(TraceError):
                    with tracer.span("scene.reopen", depends_on=(root.span_id,)):
                        pass

    def test_synthetic_overlapping_siblings_need_explicit_dag(self):
        e = [ev("a", "started", 0), ev("b", "started", 1000),
             ev("a", "finished", 4000), ev("b", "finished", 5000)]
        report = summarize(e)
        self.assertEqual(report["critical_path"], "UNKNOWN_WITHOUT_DEPENDENCY_EDGES")
        self.assertIsNone(report["critical_chain_ms"])

    def test_missing_end_is_unknown_not_zero(self):
        r = summarize([ev("root", "started", 0, name="task.run")])
        self.assertEqual(r["status"], "INCOMPLETE_UNKNOWN")
        self.assertEqual(r["unsettled_span_ids"], ["root"])

    def test_bad_identity_or_child_outside_parent_rejected(self):
        with self.assertRaises(TraceError):
            summarize([ev("a", "started", 0), ev("a", "finished", -1)])
        with self.assertRaises(TraceError):
            summarize([
                ev("root", "started", 0, name="task.run"),
                ev("a", "started", 1, parent="root"),
                ev("a", "finished", 100, parent="root"),
                ev("root", "finished", 50, name="task.run"),
            ])

    def test_real_append_permissions_cost_link_and_sanitized_exception(self):
        with tempfile.TemporaryDirectory() as td:
            recorder = TraceRecorder(Path(td), source_sha="sha1")
            with recorder.span("task.run"):
                with recorder.span("llm.generate") as item:
                    item.cost_call_id = "abc123"
                with self.assertRaisesRegex(ValueError, "secret"):
                    with recorder.span("code.compile"):
                        raise ValueError("secret prompt that must never be logged")
            report = write_summary(Path(td))
            self.assertEqual(report["span_count"], 3)
            self.assertEqual(report["status"], "FAIL")
            source = (Path(td) / "trace.jsonl").read_text()
            self.assertNotIn("secret prompt", source)
            self.assertIn("abc123", source)
            self.assertEqual((Path(td) / "trace.jsonl").stat().st_mode & 0o777, 0o600)
            self.assertTrue((Path(td) / "performance-summary.json").is_file())

    def test_unapproved_stage(self):
        with tempfile.TemporaryDirectory() as td:
            recorder = TraceRecorder(Path(td))
            with self.assertRaises(TraceError):
                with recorder.span("Authorization: hunter2"):
                    pass


if __name__ == "__main__":
    unittest.main()
