# Architecture Harness — CAD floorplan MVP delivery plan

**Status:** APPROVED PLAN / implementing independent first slices. Updated 2026-10-30.
**Canonical scope:** this document supplements [active Geometry workstream](../workstreams/geometry-harness.md) ARCH-01/ARCH-02 and is not evidence of finished capability. **Owner:** 3d-rendering-llm. Branch base: `main` (not the stacked Qwen benchmark PRs #66–#68).

## Product and boundaries

**MVP journey:** Import an existing, explicitly supported DXF, inspect dimensioned walls/openings, ask the agent for one *authorized* local change (first: move a door 300 mm along its host wall), validate changed and unchanged elements, commit a new revision, open an editable output DXF and independently re-import to verify. Save before/after, rejection and rollback evidence. Human approves design decisions. No code-compliance certification.

Do **not** build a generic CAD application, universal IR, PDF raster recognizer, new BIM runtime, or monolithic LLM-to-DXF script. Source CAD measurements are authoritative; model text is not. Private partner plans stay off public GitHub and model data egress is opt-in only.

**Already reusable in THIS repo:** `src/geometry_harness/dxf_safe.py` safe bounded ASCII DXF walls → cube scene, `tests/fixtures/arch01_room_mm.dxf`, native Blender reopen/showcase, `geometry_harness/repair/scoped.py` safe edits/rollback, `telemetry/spans.py`, `validation/issues.py`, provider adapter/usage ledger, immutable artifact SHA manifests, local Mac mini/GCS workflow. Keep old APIs and G0/G1 contracts intact. ARCH-01 real synthetic four-wall Mac pass is narrower than this MVP.

## Reuse-first open-source technical decision records (2026-10-30 research)

| Candidate | Reuse now? | Why / licence / gate |
| --- | --- | --- |
| [ezdxf](https://github.com/mozman/ezdxf) | **YES — optional pinned DXF adapter after parser/round-trip A/B** | Real DXF read/edit/write, layers, blocks and handles; MIT; Python ≥3.11. Avoid maintaining our own general DXF implementation. Continue fail-closed type/size/unsupported-entity validation; don't interpret arbitrary CAD entities as walls. Pinned version, SBOM/licence and input fuzz test before default enable. Never treat a DXF as DWG. |
| [Shapely](https://github.com/shapely/shapely) | **YES — optional geometry backend once basic pure-Python invariants pass** | Mature planar topology, intersections, polygons, STRtree, geometry validity. BSD-3-Clause; GEOS-dependent; explicit precision grid (mm) and geometry validity checks. Never treat approximate predicates or `buffer(0)` as automatic authorized repair. |
| [Google OR-Tools](https://github.com/google/or-tools) | **LATER, layout solver track only** | CP-SAT NoOverlap2D/rectangle packing for constrained layout alternatives. Apache-2.0; not required to move a door. Hard cap solver time, capture infeasible/unknown statuses. |
| [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) | **LATER, IFC/BIM adapter only** | Open-source IFC parsing/authoring; LGPL-3.0-or-later components, GPL Bonsai addon distinction. Isolate version/Blender compatibility, licensing and IFC round-trip gate; no mandatory core dependency. |
| [FloorPlanCAD](https://github.com/floorplancad/floorplancad.github.io) | **RESEARCH ONLY, not fixtures/product training** | Real CAD/SVG recognition data; annotations CC BY-NC 4.0 and drawings copyright not owned by dataset creators; avoid mixing into redistributable commercial/test artifacts without separate rights review. |
| Graph2Plan / House-GAN++ | **RESEARCH ONLY** | Prior art for room-graph/layout optimization, not substitute for auditable DXF edits or licensed production inference. Inspect code/data licences before considering reuse. |

**Build-vs-buy rule:** Domain-specific ID mapping, patch authorization, revision journaling and invariants remain owned and tested in our code; outsource general DXF IO, robust geometry operations, and later optimization/IFC to vetted mature libraries. Start the first pure-python domain schema/validator without mandatory new dependencies to keep current runner fast; add `ezdxf`/Shapely behind capability adapters and compare against legacy `dxf_safe`. No copied upstream source or benchmark reference leakage.

## Dependency DAG and parallel delivery

```text
A0 test protocol & 30 synthetic cases (10 import, 10 reject, 10 edit)
   ├──> B0 schema + stable IDs + deterministic shape/units  ───┐
   │       ├──> B1 ezdxf read/write round trip gated           │
   │       └──> C0 topology/constraint engine (B0 contract) ──┤
   └──> A1 scorer + negative mutation oracle                  │
                                                             v
                                                    D0 typed transactional edit
                                                             |
                                                    D1 DXF export + reimport
                                                             |
                                                 E1 real Mac mini deterministic E2E
                                                             |
                                       E2 Qwen-vs-Luna tool-agent A/B, then repair A/B
                                                             |
                                              F layout optimizer / IFC / 3D
```

Parallel **workstreams**: A fixtures & evidence, B CAD semantic model/import/export, C geometry validation (start with independent pure geometric predicates and bind to B0 after freeze), D edit engine *contract design only until B0+C0*, E agent tool schema/benchmark design *offline until B0*, research licensing independently. Each workstream gets a separate Git branch/PR; **do not merge one PR into another before its declared contract gate**. Code integration/review must be serial at shared boundaries.

## Work packets, acceptance, and blockers

### A — CAD benchmark/evidence (P0; independent)
- A0: versioned `architecture_mvp_v1` suite manifest with **30 categories/scenarios** (10 import, 10 invalid/adversarial, 10 edit). Initially implement a **small explicit fixture subset**; missing datasets remain TODO not fake PASS. Synthetic data only, no partner CAD.
- A1: oracle checks source/input hashes, original plan semantic IDs, operation and expected delta, untouched geometry, units, output SHA, native reopen and independent DXF re-import. Failures: unsupported curve/blocks, absent units, non-watertight room, orphan opening, overlap, stale revision, unauthorized structural edit, repeated patch, corrupt model JSON.
- Reports: exact attempted/pass/fail/unknown denominators, time, provider calls, source SHA; one task/one outcome, no scoring with answer visible to LLM.
- **Gate:** first 10 validated fixtures incl. >=4 negatives and >=2 edit cases, then extend to 30 after importer/editor supports them. CI no dependency on paid model, GCS bundle only in authorized self-hosted run.

### B — 2D CAD semantic core (P0; parallel A)
- B0: `domains/architecture/schema.py`: versioned minimal PlanScene, `Wall` endpoints & thickness (integer millimeters), `Opening` stable ID, host-wall ID, width/offset in mm, locked or unknown structural status, schema source hashes, internal frame. Strict bounded data, `bool` not numeric, bounded coordinates, unique IDs; missing measurements remain UNKNOWN.
- B1: explicit import layer/units map, legacy `dxf_safe` remains available; `ezdxf` handles richer DXF. Preserve handles/unknown supported entities or fail closed; never silently discard unsupported source data. Exact input bytes immutable; output always new path/revision.
- B2: DXF writer preserving supported layers/IDs, re-open roundtrip compares geometry and objects using tolerances; export only accepted revision.
- **Gate:** 1-room/multi-room 2D spec validates; honest missing walls/openings; DXF edit roundtrip zero unexpected changes in supported subset. No blanket claim of arbitrary DWG/DXF compatibility.

### C — geometric constraints (P0; independent math first, then B0 integration)
- C0: small pure math predicates using integer millimeters, orthogonal/oblique segment length, projection to wall, opening interval bounds & clearance, room closed-cycle/adjacency *when explicitly supplied*, uniqueness/collision, coordinate/reference/unit checks. No fabricated authoritative room polygon from a wall just because it appears close.
- C1: optional Shapely engine for wall thickness, intersection/topology; deterministic tolerance and empty/invalid geometry behavior. Typed `GeometryIssue` with target IDs and PASS/FAIL/UNKNOWN; distinguish not-supported from invalid.
- **Gate:** positive/negative/fuzz boundary fixtures and source measurement fidelity; no plan accepted with known hard-constraint violation.

### D — transactional editing (P0; dependency B0+C0)
- Typed operations first: `move_door`, `resize_opening`, `move_partition`; furniture is later. Parameters strictly in integer mm, requested targeted IDs and expected revision; reject locked/structural unknown walls for destructive changes unless explicitly reviewed.
- Copy-on-write patch, preconditions, affected & non-target invariants, geometry validation, accept/reject, immutable revision log, revision hash, rollback and idempotency replay. No LLM-authored Python, no arbitrary DXF commands.
- **Gate:** original → move_door 300mm → accepted DXF reimport; duplicate/replay/stale/invalid patch rejected without any unrelated delta; one tested rollback.

### E — agent tools & A/B (P1; design parallel, execution after D)
- Query-only tools `get_plan_summary`, `inspect_entities`, `query_constraints`; mutation via `propose_patch`, `validate_patch`, `commit_revision`, `rollback`. Exact schemas/descriptions include purpose, selection guidance, precondition/error interpretation, not overconstraining the LLM or leaking reference.
- Controls A = deterministic explicit task; B = Qwen/Luna single call propose typed patch; C = scoped deterministic-first + <=2 bounded model repairs. Same task, provider budget, tools and no hidden retries. Never silently fall back to cloud from local.
- Measure command accuracy, accepted rate, constraint violations, preservation, wall clock/critical path, tokens, call count, RAM/swap, dollars if present, human touch time. Explicit model config/prompt/tool SHA and separate provider status vs geometry success.
- **Gate:** held-out task suite; independent source/answer separation; on-device/no-egress verified if requested. Any paid Luna eval needs explicit budget approval; routine PR cannot spend.

### F — after MVP (P2)
- Multi-alternative floorplans from explicit adjacency constraints with optional OR-Tools CP-SAT; IFC/Bonsai adapter separated from Blender 5.2+ compatibility, optional 3D extrusion as derived view, then partner integration after NDA/rights/real telemetry. No legal-code-compliance guarantee.

## Delivery waves / completion policies

| Wave | Parallel start | Exit gate | Outcome |
| --- | --- | --- | --- |
| W0 (now) | A0 benchmark manifest + B0 schema + C0 bounded pure geometry rules + library licensing matrix | Offline tests green, reviewed schema; no proprietary data or inference | Foundation |
| W1 | A1 validators + B1 import/export prototype + C1 topology adapter | DXF reference, roundtrip and negative gates; no silent layer drops | CAD semantics |
| W2 | D0/D1 transactional edit, E agent tool-schema test | Deterministic move-door success and rejection/rollback, actual Mac native artifacts | MVP deterministic |
| W3 | E Qwen vs Luna single-shot and repair A/B | Paired held-out measured evidence + cost/latency, human review | AI-assisted MVP |
| W4 | F layout alternatives, IFC / 3D view, partner adapter | Only after measured workflow need + license and compatibility review | Expansion |

**Observability / artefacts:** reuse telemetry spans and typed issues, SHA inventories and GCS bucket `gs://project-tests-498508-geometry-showcase` only through the existing WIF-authorized `local-runner-infra/.github/workflows/geometry-mac-mini.yml` job family; do not broaden provider IAM scope. Preserve detailed private input/output per micro-step, split logs by task/phase, keep references and large assets outside source repo; commit small manifests and verified run URLs. Do not claim run finished until Mac/GCS independent gates pass.

**Risks and stop conditions:** ambiguity of real CAD layers/units, IFC licensing/Blender mismatch, Shapely/GEOS precision, hallucinated dimensions, unrelated edits, plugin version drift, no-egress/retention/privacy, freeform model code and arbitrary CAD entities. Any unknown or unsupported critical property must result in UNKNOWN/human review, never silent extrapolation. The original 3DCodeBench/Qwen/Luna scores are **not** evidence of architectural design reliability.

## Immediate tasks and acceptance owner mapping

- A0 benchmark fixture registry + contract tests: independent branch, open PR.
- B0 minimal semantic schema and validation: independent branch, open PR.
- C0 geometry predicate tests: separate branch, work in parallel without modifying B0 and bind after schema gate.
- Research/ADR: same plan branch; choose ezdxf before custom DXF generalized parsing; pin versions and licence check in W1.
- D0/E1 tool signature sketches/issues now, **no unsafe speculative implementation** until contracts tested.

**Status updates** must distinguish `planned`, `code present`, `offline CI pass`, `real Mac E2E pass`, `human accepted`. Avoid treating documentation or synthetic fixture count as proof of a production-ready architecture application.


## Execution tracker — first parallel wave (2026-10-30)

| Stream | Issue | PR | Implemented and tested | Next gate |
| --- | --- | --- | --- | --- |
| A0 | [#69](https://github.com/daniele21/3d-rendering-llm/issues/69) | [#75](https://github.com/daniele21/3d-rendering-llm/pull/75) | Initial immutable registry of 10 synthetic tasks (4 import, 4 negative, 2 edit *registered only*), source SHA and scorer/model separation; offline CI green | Apply B0 parser to cases, implement expected edit oracles; reach 30 |
| B0 | [#70](https://github.com/daniele21/3d-rendering-llm/issues/70) | [#76](https://github.com/daniele21/3d-rendering-llm/pull/76) | Strict PlanScene schema for mm walls and hosted openings, source/revision digest; offline CI green | Integrate C0 and read/write source DXF |
| C0 | [#71](https://github.com/daniele21/3d-rendering-llm/issues/71) | [#77](https://github.com/daniele21/3d-rendering-llm/pull/77) | Pure math bounds, exact intersection decisions, explicit-room polygon validation; offline CI green | Bind to B0 and expand robust topology |
| B1/ezdxf reuse | [#70](https://github.com/daniele21/3d-rendering-llm/issues/70) | [#78](https://github.com/daniele21/3d-rendering-llm/pull/78) | Optional MIT ezdxf 1.4.5 reader, actual pinned-package CI real DXF wall tests PASS; no custom generalized parser | DXF writer, semantic roundtrip, Mac native validation |
| D0 transactional edits | [#72](https://github.com/daniele21/3d-rendering-llm/issues/72) | — | Contract specified only | Blocked by approved B0+C0 and DXF writer |
| E agent tooling | [#73](https://github.com/daniele21/3d-rendering-llm/issues/73) | — | API and three-arm A/B specified only | Execution blocked by D0; no new Luna calls approved |

All implementation PRs are draft and **stacked**, not merged. Do not claim full MVP, all 30 cases, spatial reconstruction, arbitrary DXF, semantics beyond registered types, native Mac edit, or user acceptance. Source code may change under review. The three independent first-wave tracks ran concurrently; B1 follows the B0 contract and uses an isolated optional dependency gate.



## W2 active development — new stacked implementation branches (2026-10-30)

- **D0/D1 [draft PR #79](https://github.com/daniele21/3d-rendering-llm/pull/79)**, branch `feature/architecture-w2-dxf-edit-transaction` stacked on B1 #78. Combines C0 pure geometry predicates, B0 semantic schema and pinned B1 ezdxf. Adds XDATA-annotated R2010 wall/door/window exporter + fail-closed readback; typed `move_door` delta with exact source semantic SHA, explicit unlocked/non-load-bearing host, zero unrelated edits, rollback-plan copy and per-file SHA evidence. Adds CLI `geometry_harness.domains.architecture.e2e_move_door`, generating synthetic before/after DXFs and manifest with no model inference. **Code present; GitHub Actions and real Mac mini validation queued, not yet PASS.** This is not universal import of real-world doors from existing unannotated DXFs. Built-in B1 reader still rejects unknown layers and unannotated door objects.
- **E0 [draft PR #80](https://github.com/daniele21/3d-rendering-llm/pull/80)**, branch `feature/architecture-e0-agent-tools-contract` stacked on B0 #76. Implements 3 read-only, schema-bound tools (`get_plan_summary`, `inspect_entities`, `query_constraints`), including explicit human review on unknown structural status and no normative-compliance claims; no mutating tools until D0 is accepted.
- **Self-hosted acceptance request:** [central run #41111947792](https://github.com/daniele21/local-runner-infra/actions/runs/41111947792), pinned source commit `ab3b93a8e8f473c3e3617ffdabd87680ef27ed61`, uses the existing WIF-restricted `geometry-mac-mini.yml`, zero model calls. Must be marked `PENDING` until the run actually concludes and GCS object inventory is verified. Target private prefix is unique to this run; actual presence not yet asserted.
- **No source branches merged**; merge/rebase must preserve B0 (#76) → B1 (#78) → W2 (#79), with C0 (#77) incorporated via reviewed copy, while A0 (#75) and E0 (#80) remain independently reviewable. After gates, add Shapely optional geometry C1 and a supervised unannotated DXF door-mapping path, then real Qwen vs Luna A/B with separately approved budget.

