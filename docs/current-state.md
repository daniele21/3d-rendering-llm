# Current state — Geometry Harness

**Last verified evidence: 2026-10-28. S0/G0 E2E PASS; narrow internal S1/G1 GPT-6.1 Sol→safe Blender E2E PASS. Real pinned six-task smoke was prepared on main, but upstream-comparable 3DCodeBench quality/scorer E2E is NOT YET VERIFIED.**

## Evidence already generated

| Capability | Gate | Proof |
| --- | --- | --- |
| G0 deterministic Blender, native reopen, PNG, geometry, GCS | **PASS technical** | [Mac mini run 40664644253](https://github.com/daniele21/local-runner-infra/actions/runs/40664644253) |
| G1 controlled AST→Blender (trusted fixture, NO AI) including injection rejection | **PASS technical** | [Mac mini run 40669194991](https://github.com/daniele21/local-runner-infra/actions/runs/40669194991) |
| First paid GPT-6.1 Sol request and token ledger; NO Blender execution | **PASS** | [Cost-probe run 40668374405](https://github.com/daniele21/local-runner-infra/actions/runs/40668374405), **$0.014708000** |
| First paid GPT-6.1 Sol → safe Blender geometry → .blend + PNG + independent geometric checks + GCS | **PASS internal G1 smoke** | [Real G1 run 40669515643](https://github.com/daniele21/local-runner-infra/actions/runs/40669515643), **$0.003666000** |
| G1 safe cube+cylinder+sphere primitives, fresh Blender reopen, GCS | **PASS technical, fixture without AI** | [main Mac mini run 40675988573](https://github.com/daniele21/local-runner-infra/actions/runs/40675988573), **33 private GCS objects** |
| Prompt-only staging, real six-task ID freeze tooling and pricing (later main commits) | **SOURCE CODE PRESENT; E2E SCORING OPEN** | [PR #27](https://github.com/daniele21/3d-rendering-llm/pull/27) and main benchmark catalog; frozen IDs are not an upstream-scored result |
| Full G1 quality benchmark on pinned 3DCodeBench smoke IDs and upstream scorer | **NOT DONE / NOT VERIFIED** | Re-run/check exact task and dataset freeze provenance, rights, compatible Blender/scorer and real result artifacts |
| Automated visual quality judgement, live editing, repair, offline models | **NOT DONE** | S2+ |

**Cost accounting:** two authorized real API calls total, **$0.018374000 USD** *estimated model-token cost*. This is not an OpenAI invoice or combined GCS/compute cost. Detailed noncached/cached-read/cached-write/output/reasoning counters and versioned tariff live in private immutable per-run JSONL ledgers; see [model-cost-observability.md](features/model-cost-observability.md). No further paid calls on routine pushes.

**Latest G1 artifact bundle** (PRIVATE, not a public HTTP URL):
`gs://project-tests-498508-geometry-showcase/geometry-harness/g1/c565639be5d932e66b21450bbf9a6af3adbf53f6/40669515643-attempt-1/`

It contains original AI Python source (NOT executed), accepted safe-literal geometry plan, actual native `.blend`, actual `preview.png`, HTML gallery, asserted geometry, per-call ledger and summary. The strict GCS inventory/hash gate passed.

## Architecture currently real

- The default cloud adapter has a **manual explicit** `GEOMETRY_ALLOW_REMOTE_INFERENCE=1`, requires project API secret, uses `gpt-6.1-sol` for the initial internal smoke, and never makes paid calls from ordinary source PR or G0.
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

## Roadmap revision 2026-10-28 — scope versus implementation

The active [workstream](workstreams/geometry-harness.md) now prioritizes **trace → deterministic validation → scoped typed repair → measured composite tools → local AI / synthetic DXF architecture vertical** while preserving S1's external 3DCodeBench scoring gate and G0/G1 security boundaries. This is a **documentation-only planning change**, **not** evidence that PERF-01, VAL-01, REPAIR-01, TOOL-01, ARCH-01/02, LOCAL-01 or the partner integration are implemented.

A more recent source commit on `main` introduced six pinned real 3DCodeBench task identifiers and Luna-specific price/fixture logic; confirm the dataset revision, scorer, benchmark run and corresponding Mac/GCS evidence before promoting a quality benchmark to PASS. Historical internal GPT-6.1 Sol runs remain the evidence for first live G1 safe-geometry smoke; do not mix their prices or model identities with new Luna test configuration.

Next accepted outcome: actual frozen baseline + per-stage traces on target hardware; then objective geometric issue E2E and scoped repair comparison. Partner ~26 min estimate remains unverified, and private repo/data are out of public scope.

Detailed specs: [Agent performance](features/agent-performance.md), [Repair policy](features/repair-policy.md), [Efficiency experiments](features/harness-efficiency-experiments.md), [Architecture 2D→3D](features/architecture-2d-to-3d.md), [Partner integration boundary](features/external-integration-contract.md).
