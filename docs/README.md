# 3D Rendering LLM documentation

This documentation combines existing implementation evidence and a forward plan. G0 and narrow safe-AST G1 E2E are already verified; independent 3DCodeBench quality scoring and repair/local/CAD are **not** complete. See [current state](current-state.md); do not infer done status from the roadmap.

- [Product direction](product.md) — users, outcomes, non-goals and local-first promise.
- [Proposed architecture](architecture.md) — code-first 3DCodeVerse, typed dcc MCP, hybrid revisions, validation and local provider boundaries.
- [Current state](current-state.md) — integrated status and next executable task.
- [Active implementation workstream](workstreams/geometry-harness.md) — dependency graph and milestone gates.
- [Benchmark evaluation protocol](features/benchmark-protocol.md) — frozen 3DCodeBench smoke/core/full, scoring, reference isolation, A/B 2D experiments and licensing.
- [Visual showcase & E2E evidence contract](features/showcase-evidence.md) — G0–G8 test cases, real artifacts, image galleries, failure checks and CI publication.

Only the active workstream owns delivery-state progression. After implementation, actual runtime behavior and architecture docs must reflect the code, not the original proposal.
## 2026-10-28 performance-aware extension

- [Active Geometry Harness workstream](workstreams/geometry-harness.md) — **only active delivery roadmap**, dependencies, owners and gates.
- [Agent performance and tracing](features/agent-performance.md) — stages, spans, critical path and cost ledger integration.
- [Deterministic validation and scoped repair](features/repair-policy.md) — typed defects, safe patches, rollback and adaptive policy.
- [Harness efficiency A/B](features/harness-efficiency-experiments.md) — experimental arms, latency/quality, no-leak data, PASS/FAIL/UNKNOWN.
- [Structured Architecture 2D→3D](features/architecture-2d-to-3d.md) — separate synthetic DXF adapter and objective geometry checks.
- [External integration boundary](features/external-integration-contract.md) — NDA-gated private customer/partner PoC, public contracts only.
