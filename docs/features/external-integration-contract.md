# INT-01 — External partner integration contract and privacy boundary

Status: **DISCOVERY SPEC / NO PARTNER CODE RECEIVED, NO CONTRACT SIGNED BY THIS REPOSITORY** · 2026-10-28. Milestone owner: [active workstream](../workstreams/geometry-harness.md).

## Purpose

Prove that the reusable geometry/AI engine can be integrated into a separate architecture 2D→3D product without absorbing that vendor's entire application, data management, or IP. The partner reports a 100 m² plan taking ~26 minutes, with ~22 minutes called "AI retouch" and ~3–4 computing. All figures are **claims**, not observed performance telemetry; actual source, customer, commercial budget, models and diagrams are undisclosed.

## Required discovery before implementation

1. **Data contracts:** actual 2D formats (raster/PDF/DWG/DXF/IFC), layer mapping, dimensions, source-of-truth conventions, planned mutable artifacts (.blend/GLB/IFC/image-only), resolution, quality and review criteria.
2. **Runtime trace:** stage DAG/critical path, timing and number of LLM calls per round, per-stage tokens/cache, tool calls, Blender subprocesses, rendering settings, retries, human steps, CPU/GPU/memory and queue waits.
3. **Cloud vs local:** vendor/subscription/API terms and access, customer no-egress/on-prem constraints, target local hardware and SLA, model licensing and offline scoring.
4. **Security & legal:** NDA signed prior to repo/data access, least privilege, tenant boundaries, encryption, audit, retention and disposal, external services, IP ownership, customer authorization and commercial scope. Do not presume joint ownership or resale right.
5. **Scope/ROI:** identify the narrow replaceable step, baseline success, model quality needed, time savings required, actual customer willingness to pay. Keep product management/document/email upsell separate.

## Proposed adapter capability interface (design only)

```text
submit_task(input_ref, task_spec, profile, budget) -> run_id
get_status(run_id) -> status, stage, trace summary
get_artifacts(run_id) -> approved native scene, render, validation, manifest
apply_patch(run_id, revision_id, typed_operation) -> new revision or safe error
```

No network-facing server implied; start in-process/CLI and version input/output schemas, UUID/idempotency, cancellation, timeouts, per-call usage, status FAIL/UNKNOWN, revision conflict, and authorized artifact ACLs. Adapter must not bypass safe compiler/typed operation validation. Public part may define only the generic protocol and synthetic examples; a private plugin can implement proprietary formats.

## PoC and decision

- NDA+legal/provenance gate before any sharing; reproduce baseline from same sample and acceptance criteria (including human review).
- Instrument without changing the partner pipeline; locate highest wall-time critical path, high-cost repair sequences and repeated identical failures.
- Replace **one** stage with bounded deterministic-first/typed repair or local model adapter; keep unaffected operations identical.
- Measure full end-to-end wall time, valid accepted outputs, edits preserved, failures and cost, no-egress on requested target; publish **only sanitized aggregation approved by partner**.
- KEEP only after partner signs off quality and a measurable operational advantage is demonstrated without rights/security regressions. If no interchangeable stage exists, stop and reconsider architecture—not force a general-framework rewrite.

## IP/licensing safety

Background IP (pre-existing Geometry Harness and partner product) remains with original owner unless contract says otherwise. Foreground/new integration IP and distribution/licences require counsel-approved agreement; not inferred from this design. Source/code/benchmarks/licence notices, model weight and CAD rights require independent review. No partner identifiers, private drawings, credentials or NDA contents in public issue bodies or source runs.

## External blockers

Partner NDA, repo access, true trace, target machine, deliverable format, customer contract, permissions and quality benchmark are **UNVERIFIED**. None blocks our public deterministic ArchitectureBench or core efficiency experiments.
