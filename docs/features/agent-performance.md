# PERF-01 — Agent performance, tracing and latency attribution

Status: **DESIGN CONTRACT / NOT IMPLEMENTED** · 2026-10-28. Owner: `src/geometry_harness/telemetry/`. Roadmap: [active workstream](../workstreams/geometry-harness.md). Source cost ledger: [model-cost-observability](model-cost-observability.md).

## Why / scope

Understand a complete 3D task's wall time before optimising it. The partner's ~26 min with ~22 min AI retouch is an *unverified anecdotal baseline*. No assumption that the delay is caused by back-and-forth rather than model latency, queue/agent CLI, repeated scene builds, GPU contention or visual rendering. Trace real run structure first.

Track **hierarchical start/end events** and per-call cost linkage across `task.parse`, `planner`, `llm.generate`, `code.compile`, `blender.build`, `geometry.validate`, `blender.render_preview`, `vlm.judge`, `repair.decide`, `repair.apply`, `scene.reopen`, `artifact.publish`. An absent stage is simply absent; don't create synthetic stages as though they ran.

## Minimal schema v1

```json
{
  "schema_version": 1,
  "run_id": "run-example",
  "trace_id": "trace-example",
  "span_id": "span-003",
  "parent_span_id": "span-001",
  "name": "blender.build",
  "attempt": 1,
  "started_at_utc": "2026-10-28T10:00:00Z",
  "elapsed_ms_monotonic": 1800,
  "status": "PASS",
  "cost_call_id": null,
  "scene_revision": "rev-001",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "error_class": null
}
```

Required: run/trace/span IDs, parent, stage name, attempt, monotonic start/end or duration, wall timestamp for display, status `PASS|FAIL|UNKNOWN|CANCELLED`, source SHA, stage config/provenance. Optional: model/provider/usage, tool name, distinct call_id into **existing** token ledger, memory peak, queue wait, queue/gpu/inference rendering categories, failure code; no sensitive payload. For concurrency, root run wall clock is max(end)−min(start), **not sum of child durations**. Compute inclusive/exclusive cost attribution and DAG critical path using actual dependencies; report UNKNOWN when incomplete telemetry. Child span durations overlapping across multiple workers must not be summed as "total latency".

## Implementation increments

1. Add no-op-by-default/opt-in span context and deterministic JSONL writer with atomic append, fsync, bounded payloads and scrubbed errors.
2. Instrument provider request boundary and idempotent linkage to existing ledger; never invent token fields or prices. Mark started-but-unsettled as UNKNOWN, not 0.
3. Instrument safe AST parser, built-in Blender subprocess, fresh-process reopen, check, gallery and upload.
4. Provide `performance-summary.json` (stage totals and exclusive times, elapsed, critical path, per-stage calls, token/cost references, waits, errors), plus static timeline/gallery; optional read-only Phoenix/OpenTelemetry adapter disabled by default.
5. Extend only affected E2E with host/profile tags, hashes, benchmark task ID and explicit real-vs-mock classification.

## Acceptance and negative cases

- Real G0 and real G1 artifacts produce a trace, event timeline and immutable summary; the existing cost ledger passes reconciliation unchanged.
- Mock provider unit tests confirm parent-child linkage; parallel spans do **not** inflate wall-clock duration.
- Forced timeout, missing Blender, provider error, interrupted call and malformed event yield truthful FAIL/UNKNOWN, never a false green status.
- Scrub tokens, secrets, prompts, private geometry, machine paths and customer identifiers; storage is local gitignored/private GCS where allowed. Offline runs do not emit remote telemetry.
- Benchmark report shows total run latency vs model time and tool/render waits, with explicit denominator and hardware identity.

## Research adaptation

3DCodeVerse's `harness/docs/COST.md` includes measured model/round attribution and a historical cost audit; learn its method, **do not copy** its historical distribution as our expected speedup. Instrument first, then choose target bottleneck. Do not add Phoenix as a mandatory dependency just for display.
