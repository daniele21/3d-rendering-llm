"""Durable hierarchy of sanitized task spans; never emit prompt/response/keys.

Events are owner-only JSONL fsynced using the existing safe append primitive.
A crash leaves a START without END and makes the report explicitly INCOMPLETE.
No network exporter. Monotonic clocks are comparable only within a run/host.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from geometry_harness.costs.ledger import append_event

_CURRENT: ContextVar[str | None] = ContextVar("geometry_current_span", default=None)
_ALLOWED = frozenset({
    "task.run", "llm.generate", "code.compile", "geometry.validate",
    "blender.build", "scene.reopen", "blender.render_preview",
    "artifact.publish", "benchmark.task", "task.parse",
})


class TraceError(ValueError):
    pass


@dataclass
class SpanLink:
    """Mutable stage annotation; only public cost-ledger call IDs allowed."""
    cost_call_id: str | None = None
    span_id: str | None = None


class TraceRecorder:
    def __init__(self, root: Path, *, source_sha: str = "unknown",
                 run_id: str | None = None):
        self.path = Path(root) / "trace.jsonl"
        self.run_id = run_id or uuid4().hex
        self.source_sha = source_sha
        self.trace_id = uuid4().hex
        self._finished: set[str] = set()

    @contextmanager
    def span(self, name: str, *, attempt: int = 1,
             depends_on: tuple[str, ...] = ()):
        if name not in _ALLOWED or type(attempt) is not int or not 1 <= attempt <= 100:
            raise TraceError("Unknown span name or attempt")
        if not isinstance(depends_on, tuple) or len(depends_on) > 16 or len(set(depends_on)) != len(depends_on) or any(
            not isinstance(dep, str) or dep not in self._finished for dep in depends_on
        ):
            raise TraceError("Dependencies must be distinct completed spans from this recorder")
        parent = _CURRENT.get()
        span_id = uuid4().hex
        start_ns = time.monotonic_ns()
        now = datetime.now(timezone.utc).isoformat()
        base = {"schema_version": 1, "run_id": self.run_id,
                "trace_id": self.trace_id, "span_id": span_id,
                "parent_span_id": parent, "depends_on": list(depends_on),
                "name": name, "attempt": attempt,
                "source_sha": self.source_sha}
        append_event(self.path, {**base, "event": "started",
                                 "utc": now, "monotonic_ns": start_ns})
        token = _CURRENT.set(span_id)
        link = SpanLink(span_id=span_id)
        outcome, error_class = "PASS", None
        try:
            yield link
        except BaseException as exc:
            outcome = "CANCELLED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "FAIL"
            error_class = type(exc).__name__
            raise
        finally:
            _CURRENT.reset(token)
            stop_ns = time.monotonic_ns()
            append_event(self.path, {**base, "event": "finished",
                                     "utc": datetime.now(timezone.utc).isoformat(),
                                     "monotonic_ns": stop_ns, "status": outcome,
                                     "error_class": error_class,
                                     "cost_call_id": link.cost_call_id,
                                     "elapsed_ms": round((stop_ns - start_ns) / 1e6, 4)})
            self._finished.add(span_id)


def _union_length(intervals: list[tuple[int, int]]) -> int:
    merged = []
    for lo, hi in sorted(intervals):
        if lo > hi:
            raise TraceError("Negative interval")
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return sum(hi - lo for lo, hi in merged)


def summarize(events: list[dict]) -> dict:
    if not events:
        raise TraceError("No trace events")
    spans = {}
    for event in events:
        sid = event.get("span_id")
        kind = event.get("event")
        if not sid or kind not in ("started", "finished"):
            raise TraceError("Malformed span event")
        obj = spans.setdefault(sid, {})
        if kind in obj:
            raise TraceError("Duplicate span event")
        obj[kind] = event
    if any("started" not in state for state in spans.values()):
        raise TraceError("Finished without start")
    run_ids = {x["started"].get("run_id") for x in spans.values()}
    if len(run_ids) != 1 or None in run_ids:
        raise TraceError("Mixed runs or missing run_id")
    intervals = {}
    unresolved = []
    rows = []
    for sid, state in spans.items():
        start, finish = state["started"], state.get("finished")
        if finish is None:
            unresolved.append(sid)
            continue
        if (finish.get("run_id"), finish.get("trace_id"),
            finish.get("parent_span_id"), finish.get("name")) != (
                start.get("run_id"), start.get("trace_id"),
                start.get("parent_span_id"), start.get("name")):
            raise TraceError("Span start/end identity mismatch")
        lo, hi = start.get("monotonic_ns"), finish.get("monotonic_ns")
        if type(lo) is not int or type(hi) is not int or hi < lo:
            raise TraceError("Invalid monotonic time")
        intervals[sid] = (lo, hi)
    all_starts = [x["started"].get("monotonic_ns") for x in spans.values()]
    all_ends = [x["finished"].get("monotonic_ns") for x in spans.values()
                if "finished" in x]
    if any(type(x) is not int for x in all_starts + all_ends):
        raise TraceError("Incomplete time data")
    for sid, state in spans.items():
        if sid not in intervals:
            continue
        start, end = intervals[sid]
        direct_children = []
        for child_id, child in spans.items():
            if child["started"].get("parent_span_id") != sid:
                continue
            if child_id not in intervals:
                continue
            a, b = intervals[child_id]
            if a < start or b > end:
                raise TraceError("Child span exceeds parent")
            direct_children.append((a, b))
        exclusive = max(0, end - start - _union_length(direct_children))
        finish = state["finished"]
        rows.append({
            "span_id": sid, "parent_span_id": state["started"].get("parent_span_id"),
            "name": state["started"]["name"], "status": finish.get("status"),
            "cost_call_id": finish.get("cost_call_id"),
            "elapsed_ms": round((end-start)/1e6, 4),
            "exclusive_ms": round(exclusive/1e6, 4),
        })
    rows.sort(key=lambda x: (intervals[x["span_id"]][0], x["span_id"]))
    # Only explicit edges authorize a measured dependency chain. We do NOT
    # infer dependencies from temporal proximity, sibling order or nesting.
    dependencies = {}
    for sid, state in spans.items():
        declared = state["started"].get("depends_on", [])
        if not isinstance(declared, list) or len(declared) > 16 or len(set(declared)) != len(declared):
            raise TraceError("Invalid dependency list")
        if sid not in intervals:
            if declared:
                unresolved.append(sid)
            continue
        for dep in declared:
            if not isinstance(dep, str) or dep not in intervals:
                raise TraceError("Unknown or unfinished dependency")
            if intervals[dep][1] > intervals[sid][0]:
                raise TraceError("Dependency was not finished before dependent started")
        dependencies[sid] = declared
    # Explicit edges must be a DAG; topological order comes from measured
    # start timestamps, because each dependency has already finished.
    best = {}
    for sid in sorted(dependencies, key=lambda k: (intervals[k][0], k)):
        previous = max((best[d] for d in dependencies[sid]), key=lambda x: x[0],
                       default=(0, ()))
        best[sid] = (previous[0] + intervals[sid][1] - intervals[sid][0],
                     previous[1] + (sid,))
    has_edges = any(dependencies.values())
    chain = max(best.values(), key=lambda x: x[0], default=(0, ()))
    chain_ids = list(chain[1]) if has_edges and not unresolved else []
    by_sid = {r["span_id"]: r for r in rows}
    critical_names = [by_sid[s]["name"] for s in chain_ids]
    observed_end = max(all_ends) if all_ends else min(all_starts)
    # Run wall-time is a monotonic interval, not the sum of overlapping spans.
    duration = max(0, observed_end - min(all_starts)) / 1e6
    root_intervals = [intervals[sid] for sid,s in spans.items()
                      if sid in intervals and s["started"].get("parent_span_id") is None]
    # Root union indicates covered time; gaps outside roots remain in wall.
    return {
        "schema_version": 1, "run_id": next(iter(run_ids)),
        "status": "INCOMPLETE_UNKNOWN" if unresolved else (
            "FAIL" if any(r["status"] != "PASS" for r in rows) else "COMPLETE"),
        "observed_wall_ms": round(duration, 4),
        "root_coverage_ms": round(_union_length(root_intervals)/1e6, 4),
        "critical_path": ("MEASURED_EXPLICIT_SPAN_DEPENDENCIES"
                          if has_edges and not unresolved else
                          "UNKNOWN_WITH_INCOMPLETE_EVENTS" if unresolved else
                          "UNKNOWN_WITHOUT_DEPENDENCY_EDGES"),
        "critical_chain_ms": (round(chain[0] / 1e6, 4)
                              if chain_ids else None),
        "critical_chain_span_ids": chain_ids,
        "critical_chain_stages": critical_names,
        "critical_chain_scope": ("EXPLICIT_INSTRUMENTED_STAGES_ONLY" if chain_ids
                                 else "UNKNOWN"),
        "note": "Observed root/wall includes gaps; explicit chain sums only declared dependencies, not total task latency or inferred sibling edges.",
        "span_count": len(spans), "unsettled_span_count": len(unresolved),
        "unsettled_span_ids": sorted(unresolved), "spans": rows,
    }


def write_summary(root: Path) -> dict:
    root = Path(root)
    with (root / "trace.jsonl").open(encoding="utf-8") as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    report = summarize(events)
    (root / "performance-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
