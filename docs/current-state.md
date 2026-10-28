# Current state — Geometry Harness

**Last verified evidence: 2026-10-28. S0/G0 E2E PASS; historical Sol narrow internal G1 table PASS. Six genuine public 3DCodeBench prompts were tested with GPT-6 Luna: 6 priced calls, 2/6 native Blender scenes, STRICT CI GATE FAILED; full upstream-comparable scorer and quality E2E remain NOT VERIFIED.**

## Evidence already generated

| Capability | Gate | Proof |
| --- | --- | --- |
| G0 deterministic Blender, native reopen, PNG, geometry, GCS | **PASS technical** | [Mac mini run 40664644253](https://github.com/daniele21/local-runner-infra/actions/runs/40664644253) |
| G1 controlled AST→Blender (trusted fixture, NO AI) including injection rejection | **PASS technical** | [Mac mini run 40669194991](https://github.com/daniele21/local-runner-infra/actions/runs/40669194991) |
| First paid GPT-6.1 Sol request and token ledger; NO Blender execution | **PASS** | [Cost-probe run 40668374405](https://github.com/daniele21/local-runner-infra/actions/runs/40668374405), **$0.014708000** |
| First paid GPT-6.1 Sol → safe Blender geometry → .blend + PNG + independent geometric checks + GCS | **PASS internal G1 smoke** | [Real G1 run 40669515643](https://github.com/daniele21/local-runner-infra/actions/runs/40669515643), **$0.003666000** |
| G1 safe cube+cylinder+sphere primitives, fresh Blender reopen, GCS | **PASS technical, fixture without AI** | [main Mac mini run 40675988573](https://github.com/daniele21/local-runner-infra/actions/runs/40675988573), **33 private GCS objects** |
| Prompt-only staging, real six-task ID freeze tooling and pricing (later main commits) | **SOURCE CODE PRESENT; E2E SCORING OPEN** | [PR #27](https://github.com/daniele21/3d-rendering-llm/pull/27) and main benchmark catalog; frozen IDs are not an upstream-scored result |
| Real 212-task HF dataset revision freeze, six generator-facing public text tasks | **PASS technical** | [No-inference run 40682618911](https://github.com/daniele21/3d-rendering-llm/actions/runs/40682618911); dataset b70b4ee54b93fab76596da5809f3e71c617fa5c2; pinned suite SHA 79904d4e83e9075cd08337a99c28d5dbcc00743cc790d37123ed9b7c776a7cd8; reference scripts excluded |
| First six real Luna 3DCodeBench prompts: native Blender executability | **2/6 preliminary; original CI FAILED** | [Run 40683850012](https://github.com/daniele21/local-runner-infra/actions/runs/40683850012): 6 recorded API calls, 2 scenes, cost $0.004875300, private GCS upload step success, strict evidence gate failed because task failure was misclassified as incomplete; reporting corrected in PR #32, no paid rerun |
| PERF-01 duration spans/cost links and failure records on native Blender fixture | **PASS narrow E2E; critical path DAG OPEN** | [PR #41](https://github.com/daniele21/3d-rendering-llm/pull/41), Mac mini [run 40690265805](https://github.com/daniele21/local-runner-infra/actions/runs/40690265805), source fixture contains hashed trace.jsonl/performance-summary.json; spans include AI/compile/Blender boundaries, critical-path DAG correctly UNKNOWN until edges exist |
| VAL-01 geometric issues and Blender four-view preview | **PASS narrow E2E; generalized task validators OPEN** | [PR #42](https://github.com/daniele21/3d-rendering-llm/pull/42), Mac mini [run 40689986944](https://github.com/daniele21/local-runner-infra/actions/runs/40689986944); task-specific floor/dimensions/contact measurements, true four camera PNGs, original .blend unchanged |
| G1 integration automatic 8 table geometry contacts + four camera views, independent native reopen | **PASS G1 fixture E2E; zero cloud calls** | [PR #44](https://github.com/daniele21/3d-rendering-llm/pull/44), corrected Mac mini [run 40691475882](https://github.com/daniele21/local-runner-infra/actions/runs/40691475882), **77 private GCS objects**. Initial [run 40691165626](https://github.com/daniele21/local-runner-infra/actions/runs/40691165626) FAILED due double-write test and was fixed without weakening immutable output |
| BH-02 six-task Luna evidence re-audit/HTML gallery | **PASS offline; historical private bundle review NOT RUN** | [PR #43](https://github.com/daniele21/3d-rendering-llm/pull/43): verifies exact task IDs, hashes, per-task statuses and re-reconciles six raw cost events. Not an upstream 3DCodeBench image/shape quality scorer |
| PERF-01 dependency critical chain on native G1 stage spans | **PASS bounded real E2E** | [PR #46](https://github.com/daniele21/3d-rendering-llm/pull/46); Mac [40697522356](https://github.com/daniele21/local-runner-infra/actions/runs/40697522356). Reports measured explicit chain only, not full wall-clock DAG/unknown edges |
| EDIT-01 one-object typed repair and rollback on native Blender | **PASS bounded real E2E** | [PR #47](https://github.com/daniele21/3d-rendering-llm/pull/47); Mac [40697004192](https://github.com/daniele21/local-runner-infra/actions/runs/40697004192), disconnected leg repaired, non-targets preserved, rejected candidate rolled back and source hash preserved; zero AI calls |
| BH-02 trusted native GLB export + pinned upstream shape scorer adapter | **PASS export E2E; reference scoring NOT RUN** | [PR #49](https://github.com/daniele21/3d-rendering-llm/pull/49); combined Mac [40698095542](https://github.com/daniele21/local-runner-infra/actions/runs/40698095542), GLB proof + repair PASS, 130 GCS objects; upstream commit `42c7780ed3fcbd466f17f058f62e7996233777f7`; no six scorer-private reference GLBs yet |
| ARCH-01 first independent structured DXF wall geometry | **PASS restricted real Mac E2E** | [PR #51](https://github.com/daniele21/3d-rendering-llm/pull/51), source-wall-layer hardening [#54](https://github.com/daniele21/3d-rendering-llm/pull/54): four editable 6 × 4m room walls in millimetre DXF; real `.blend` fresh reopen and geometry validation. [Mac run 40702702395](https://github.com/daniele21/local-runner-infra/actions/runs/40702702395), GCS 145 uploaded objects, zero model calls. Doors/windows/diagonal walls unsupported |
| PERF-01 observed G1 timeline + read-only model-call ledger cross-check | **PASS restricted real Mac E2E** | [PR #52](https://github.com/daniele21/3d-rendering-llm/pull/52), [Mac run 40701519157](https://github.com/daniele21/local-runner-infra/actions/runs/40701519157), private GCS 138 objects; new `trace-review.json`, `timeline.html`, missing cost links marked UNKNOWN. Full causal network/queue critical path still OPEN |
| Historical six-task Luna GCS read-only audit | **READY, NOT EXECUTED against GCS** | [PR #53](https://github.com/daniele21/3d-rendering-llm/pull/53), operator-only `geometry_harness.evaluation.historical_luna`, offline tests PASS. GitHub OIDC uploader only ObjectCreator, no read permissions; original GCS run stays FAILED, cost $0.004875300 historical, real evidence audit blocked until authorized user executes |
| Full G1 quality benchmark on pinned 3DCodeBench smoke IDs and upstream scorer | **NOT DONE / NOT VERIFIED** | Re-run/check exact task and dataset freeze provenance, rights, compatible Blender/scorer and real result artifacts |
| Automated visual quality judgement, live editing, repair, offline models | **NOT DONE** | S2+ |

**Cost accounting:** eight observed real API calls total: 2 historical Sol requests **$0.018374000** plus 6 Luna benchmark requests **$0.004875300**, combined **$0.023249300 USD** *estimated model-token cost*. This is not an OpenAI invoice or combined GCS/compute cost. Detailed noncached/cached-read/cached-write/output/reasoning counters and versioned tariff live in private immutable per-run JSONL ledgers; see [model-cost-observability.md](features/model-cost-observability.md). No further paid calls on routine pushes.

**Latest G1 artifact bundle** (PRIVATE, not a public HTTP URL):
`gs://project-tests-498508-geometry-showcase/geometry-harness/g1/c565639be5d932e66b21450bbf9a6af3adbf53f6/40669515643-attempt-1/`

It contains original AI Python source (NOT executed), accepted safe-literal geometry plan, actual native `.blend`, actual `preview.png`, HTML gallery, asserted geometry, per-call ledger and summary. The strict GCS inventory/hash gate passed.

**Exact model choice:** `gpt-6-luna` is the published API ID. `gpt-6.1-luna` is not documented; the central G1 workflow pins Luna, with no silent Sol fallback. The 2/6 metric is internal AST-restricted Blender executability, not the upstream visual or 3D-shape score. Original failed CI remains immutable, without a paid retry.

## Architecture currently real

- The default cloud adapter has a **manual explicit** `GEOMETRY_ALLOW_REMOTE_INFERENCE=1`, requires project API secret, used `gpt-6.1-sol` in the historical internal smoke and now selects documented `gpt-6-luna` for future explicitly approved paid experiments, and never makes paid calls from ordinary source PR or G0.
- G0 and the G1 fixture use real Blender 5.2.3 on macOS ARM64.
- Model-authored Python is currently *never* handed to a Blender subprocess. We parse a **strict, bounded Blender bpy subset supporting cubes, cylinders and UV spheres** using Python AST (no exec/eval), reject imports/functions/loops/network/file ops, convert it to validated data, then execute our own audited Blender builder and an independent inspector in a new Blender process.
- This means **G1 currently supports only a narrow set of literal cube-, cylinder- and sphere-based shapes**, not arbitrary procedural Blender generation. Native editability is preserved in the produced scene. Future quality comparisons must state this restriction.
- Full upstream 3DCodeBench nominal environment targets Blender 5.0; the Mac fixture used Blender 5.2.3. Do **not** publish official comparable benchmark results before pinning/verifying the scorer and licence environment.

## Next work in parallel

| Lane | What is ready | Next acceptance work | Tracking |
| --- | --- | --- | --- |
| A: real AI product journey | First internal real table AI→Blender success | Inspect actual private PNG/.blend and improve compiler coverage safely, keeping editable named objects | [G1 #7](https://github.com/daniele21/3d-rendering-llm/issues/7) |
| B: benchmark | Leak-free catalog adapter with 6/24 provisional selection | Leak-safe prompt-only staging and hash checks now implemented on main. Verify the main real-six-task freeze/revision and rights, run approved real smoke with Blender/scorer and capture independent results | [BH-01 #4](https://github.com/daniele21/3d-rendering-llm/issues/4) |
| C: evaluation | Paired FAIL/UNKNOWN comparator and G1 real Blender geometry checks | Per-task gallery, 4-view rendering and independent prompt-criterion scoring, frozen baseline | [BH-02 #5](https://github.com/daniele21/3d-rendering-llm/issues/5) |
| D: accounting/FinOps | Live per-call cached/read/write token ledger and immutable private GCS events | Aggregate by model/stage/day, provide cost dashboard and reconcile against actual OpenAI invoice plus GCS/compute | [COST-02 #23](https://github.com/daniele21/3d-rendering-llm/issues/23) |

Design/adapter prototypes may proceed independently; paired performance claims require a frozen baseline. After that, compare structured planner [#8](https://github.com/daniele21/3d-rendering-llm/issues/8), bounded repair [#9](https://github.com/daniele21/3d-rendering-llm/issues/9), 2D-assisted [#10](https://github.com/daniele21/3d-rendering-llm/issues/10), editing [#11](https://github.com/daniele21/3d-rendering-llm/issues/11), and local inference [#12](https://github.com/daniele21/3d-rendering-llm/issues/12).

## Source of truth

- [Sprint / dependency roadmap](workstreams/geometry-harness.md)
- [Benchmark scoring and data isolation protocol](features/benchmark-protocol.md)
- [Real E2E milestone evidence rules](features/showcase-evidence.md)
- [Live token cost records and cloud retention](features/model-cost-observability.md)

[G0+G1 integration PR #2](https://github.com/daniele21/3d-rendering-llm/pull/2) merged into `main` on 2026-10-28 as `bf40932da49fac276c9a1d7362ca6855117dd71c`. New work branches must start from `main` and follow branch/CI gates. The legacy `feature/g0-blender-showcase` is retained for history, not the active integration target.

## Wave 2 implementation snapshot (2026-10-28)

Three independently staged changes #46 PERF-01, #47 EDIT-01 and #49 BH-02 are now in main. The native Blender tests passed on Mac mini using no model API calls. PERF-01 reports only explicit stage dependency chains, not end-to-end root critical path with queue/network waits. EDIT-01 supports just one bounded `set_location` patch over a revision-hashed scene spec and .blend, precondition checked; it validates independent geometry and preserves rollback hashes. BH-02 can export safe edited native scenes as real GLBs under `--disable-autoexec` and invoke the pinned upstream shape scorer *only* with six supplied scorer-private real reference GLBs. No historical six-task private run has yet been re-audited with that adapter; no official 3DCodeBench shape, image or semantic score is claimed. Historical eight API calls and estimated $0.023249300 token costs are unchanged.

## Wave 1 implementation snapshot (2026-10-28)

**Merged to main:** #41 PERF-01 event spans + per-stage cost-reference, #42 VAL-01 typed geometry PASS/FAIL/UNKNOWN and trusted real four-view script, #43 BH-02 six-task immutable artifact/cost re-audit, #44 G1 production fixture integration (8 independent contact checks and four automatic views). Both Mac mini evidence passes were verified on exact reviewed PR SHAs, and all related code is in main. G0 remains zero-cost. Existing Luna six-task 2/6 quality and $0.004875300 estimated cost are historical and unchanged; **no paid API inference was run for Wave 1**.

The next acceptance gates are (1) actual provider-run span/cost linkage incl failed calls and dependency-aware critical-path timeline, (2) upstream 3DCodeBench scorer plus Blender 5.0/reference isolation and retrieval of historical six-task private evidence, and (3) broader task-specific geometry constraints and malformed/missing scene cases before scoped edits. Local preview views do not constitute a VLM judge or semantic truth. The architecture DXF vertical remains separate.

## Roadmap revision 2026-10-28 — scope versus implementation

The active [workstream](workstreams/geometry-harness.md) now prioritizes **trace → deterministic validation → scoped typed repair → measured composite tools → local AI / synthetic DXF architecture vertical** while preserving S1's external 3DCodeBench scoring gate and G0/G1 security boundaries. This is a **documentation-only planning change**, **not** evidence that PERF-01, VAL-01, REPAIR-01, TOOL-01, ARCH-01/02, LOCAL-01 or the partner integration are implemented.

A more recent source commit on `main` introduced six pinned real 3DCodeBench task identifiers and Luna-specific price/fixture logic; confirm the dataset revision, scorer, benchmark run and corresponding Mac/GCS evidence before promoting a quality benchmark to PASS. Historical internal GPT-6.1 Sol runs remain the evidence for first live G1 safe-geometry smoke; do not mix their prices or model identities with new Luna test configuration.

Next accepted outcome: actual frozen baseline + per-stage traces on target hardware; then objective geometric issue E2E and scoped repair comparison. Partner ~26 min estimate remains unverified, and private repo/data are out of public scope.

Detailed specs: [Agent performance](features/agent-performance.md), [Repair policy](features/repair-policy.md), [Efficiency experiments](features/harness-efficiency-experiments.md), [Architecture 2D→3D](features/architecture-2d-to-3d.md), [Partner integration boundary](features/external-integration-contract.md).
