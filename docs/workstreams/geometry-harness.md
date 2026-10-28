# Geometry Harness — active delivery workstream

Status: **ACTIVE PLAN / NOT IMPLEMENTATION EVIDENCE**
Owner: `3d-rendering-llm`; source branch: `main`; plan revision: 2026-10-28.
Single source of truth for milestone priority, dependencies, issue ownership, and acceptance: this document.
Detailed contracts: [agent-performance](../features/agent-performance.md), [repair-policy](../features/repair-policy.md), [harness-efficiency-experiments](../features/harness-efficiency-experiments.md), [architecture-2d-to-3d](../features/architecture-2d-to-3d.md), [external integration](../features/external-integration-contract.md).
Verified implementation truth is maintained **only** in [current-state](../current-state.md), using CI run IDs/SHAs and artifact inventories.

## North star, motivation, and scope

Produce **reopenable, editable, objectively verifiable 3D scenes** with the fewest necessary model turns and tool round-trips, initially with an opt-in cloud baseline and ultimately with a **complete no-egress local inference** path on compatible Apple Silicon. Preserve the general text-to-3D product while adding a separate architecture-oriented structured 2D-to-3D journey. Do **not** pivot the core into a full CAD application.

Potential partner scenario (discovery-only, not a confirmed contract): an architecture/design studio wants private 2D-to-3D conversion and targeted changes. A partner reports ~26 min per 100 m² plan (~3–4 min computing and ~22 min AI retouch). **These timings are unverified and do not prove an AI repair-loop cause.** Before proposing speedups, capture stage traces, actual run count, failures, retries, render waits, provider latency and concurrent work. The private partner's repo, documents, NDA terms, CAD files, prices, and customer data are **not** to be copied into this public repository.

Research inspirations, not verified gains here:
- [3DCodeVerse harness](https://github.com/gaoypeng/3dcodeverse/tree/main/harness): execute/measure/validate, cheap geometric gates before VLM, typed defects, scoped work, stages cached by input hash, cost and wall clock guards. Its [historical cost audit](https://github.com/gaoypeng/3dcodeverse/blob/main/harness/docs/COST.md) analysed 61 runs / 7,544 model calls and illustrates long-turn and refinement costs; hardware/model/dataset differ, so **do not transfer percentages**.
- [dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender), [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core): trial **whitelisted** typed operations against direct safe-builder edits; do not adopt all tools or permit unrestricted code execution.
- [SWE-agent](https://github.com/SWE-agent/SWE-agent): narrow, actionable agent-computer interfaces.
- Workflow/meta-tool and CAD papers are hypotheses to test, not authority to claim a latency benefit.

## Accurate baseline and non-negotiable invariants

As of this planning snapshot: **G0 real Blender/GCS PASS**, **one internal G1 real model→safe AST→Blender/.blend/PNG/GCS PASS**. The accepted G1 execution accepts only a bounded literal `bpy` subset (cube/cylinder/UV sphere and supported transforms) and uses an **audited builder**; it does *not* execute model-authored Python. The source `main` has a real six-task 3DCodeBench freeze/prompt-staging implementation (benchmark catalog PRs #27 and later main changes), but the **independent upstream-scored 3DCodeBench G1 baseline remains OPEN** until an actual comparable run passes. G2–G8, local no-egress, live editing and repair have no completed E2E evidence. Do not report a frozen suite or unit test as achieved benchmark quality.

1. **Security:** never directly `exec` AI-generated Python, expand untrusted AST acceptance merely for convenience, disable isolated processes, or expose filesystem/network/tool escapes. Typed operations must pass through bounded validated execution. Private data and secrets stay private.
2. **Truthful acceptance:** no milestone DONE without a real applicable E2E on approved target, native reopen, PNG/contact sheet/gallery, hashes, independent assertions, negative path, correct FAIL/UNKNOWN and inspectable artifact bundle.
3. **Geometry before appearance:** syntax/build/safe execution → deterministic invariants → cheap multi-view → optional separate visual judge. An attractive image never substitutes for valid geometry.
4. **Revisions:** stable object identity, per-operation pre/postconditions, immutable accepted checkpoint, replay validation and rollback; no destructive partial commits.
5. **Measurement:** stage spans and actual critical-path wall time, provider latency, tokens, cache usage, per-call ledger ID; no wall-clock double-count for overlapping spans and no missing usage represented as $0.
6. **Reproducibility:** task/spec/strategy/model/pricing/Blender/source SHA/scorer/version pins; upstream benchmark answers never visible to generator.
7. **Budget:** cheap unit/offline tests on routine PR; billed inference manual and approved; max cost, calls, retries, runtime, memory and concurrency. No implicit fallback from local to cloud.
8. **Minimality:** grow modules only after a vertical task consumes a contract; no generic Geometry IR, full CAD stack, UI platform, training/LoRA, or orchestration mega-framework in this plan.

## Active roadmap — dependency milestones (supersedes the 2026-10-27 sprint order)

Milestones are **acceptance gates**, not a prohibition on parallel isolated implementation. The existing G0–G8 names retain meaning for compatibility; new PERF/VAL/REPAIR/TOOL/ARCH/INT tracks cut across them.

| Stage | Goal and user-visible output | Dependencies/gate | State |
| --- | --- | --- | --- |
| **S0/G0** | Real deterministic Blender + reopened .blend/PNG/gallery/manifest/GCS | Exact Mac mini CI, negative cases | **PASS technical** |
| **S1/G1** | Real cloud LLM → safe Blender scene, six real smoke tasks with valid upstream-comparable scorer and frozen artifacts; time/cost tracing on the same runs | S0; benchmark rights/version and approved inference | **PARTIAL**: internal smoke PASS, official benchmark OPEN |
| **S1T/PERF-01** | Hierarchical stage spans and per-stage latency, linked to immutable cost ledger; dependency critical path and visual timeline remaining | Real G0/G1 fixtures; no new paid call for routine checks | **PARTIAL: narrow E2E PASS, DAG critical path OPEN** |
| **S2/VAL-01** | Typed deterministic PASS/FAIL/UNKNOWN with affected IDs, four native Blender views and injected dimension/contact errors | Frozen scene identity + real Blender | **PARTIAL: narrow table E2E PASS; generality OPEN** |
| **S3/EX-01** | Direct vs bounded typed planner: paired scenes, geometric acceptance and end-to-end time/cost | S1 quality suite + stable TaskSpec/metrics | **PLANNED P1** |
| **S4/REPAIR-01** | Scoped typed patch vs full-regeneration baseline, immutable checkpoints, new-process replay/rollback, no unintended delta | S2 validator + revision contract; measured trials | **PLANNED P0** |
| **S4P/ORCH-01** | Adaptive bounded repair policy including cheap-first, repeat-signature handling and skip/stop decisions; A/B | PERF-01 + REPAIR-01 + paired baseline | **PLANNED P1** |
| **S5/EX-03** | **Generated** 2D reference ablation vs text→3D (preserve separate oracle controls) | S1 scoring; keep existing #10 experimental | **PLANNED P1** |
| **S5A/ARCH-01** | **Imported** structured DXF→editable Blender scene with objective floorplan checks; CAD suite separate from 3DCodeBench | Safe deterministic builder + architecture fixtures | **PLANNED P1, parallel prototype** |
| **S6/G3–G4/EDIT-01** | Scene edits via audited typed operations vs optional pinned Blender MCP adapter, re-open, preserve unrelated objects, replay/rollback | REPAIR-01 contracts | **PLANNED P1** |
| **S6T/TOOL-01** | Evidence-selected composite tools, stage caching and safe disjoint parallel tasks; measured A/B | PERF traces + typed calls; no scene-wide parallel writes | **PLANNED P1** |
| **S7/G6–G7/LOCAL-01** | Same task using open-weight local model, bounded memory and **verified no-egress**; optional local VLM only when measured | Valid cloud baseline; safe provider contract; offline tester | **PLANNED P1** |
| **S7R/G8** | Cycles final vs preview from same saved accepted scene, separate final-render budget | Valid geometry/edit checkpoint | **PLANNED P2** |
| **S8/INT-01** | Partner-independent integration contract then private opt-in connector PoC, with actual partner baseline and agreed terms | NDA + code audit + customer consent + accepted core slices | **DISCOVERY/BLOCKED externally** |

**Execution order for value:** baseline + tracing → cheap validator → typed revision/scoped repair → adaptive repair/meta-tools if measured → local vs cloud and structured-CAD vertical → partner integration after discovery. A local provider probe and synthetic DXF fixture may begin in parallel, but no claims of comparative improvement until the appropriate baseline exists.

### Wave 2 implementation checkpoint (2026-10-28)

- **PERF-01 / #46:** explicit predecessor span IDs produce measured stage dependency chains; G1 true Blender E2E + private GCS PASS on Mac mini run 40697522356. Complete causal DAG across queue/provider/network/parallel workers and end-to-end accepted-result wall time remain OPEN.
- **EDIT-01 / #47:** first bounded `set_location` operation with revision hashes and optimistic preconditions; actual Blender accepted checkpoint and negative rollback confirmed with unchanged non-target identities and source hash, Mac run 40697004192 PASS. Multi-object transactions, rotations, material edits, smarter scoped LLM repair and paired A/B latency/cost remain OPEN.
- **BH-02 / #49:** trusted autoexec-disabled GLB export for our native scene and exact upstream 3DCodeBench Chamfer commit `42c7780...` adapter, Mac run 40698095542 PASS (130 private GCS artifacts). Source .blend unchanged. First Luna six-task generated outputs still need private-bucket re-audit and six scorer-only reference GLBs in an isolated environment; Blender 5.2 vs official 5.0 comparability remains OPEN.
- **Cost gate:** 0 additional provider model calls in this wave; historical two Sol and six Luna total estimated USD $0.023249300 persists. No provider invoice/infra reconciliation claimed.

### Wave 1 implementation checkpoint (2026-10-28)

- **#41 PERF-01:** event spans started/finished with fail-closed incomplete traces and cost ledger ID links; G1 + six-task Luna smoke stage instrumentation merged. Safe monotonic overlap-aware wall/exclusive durations and hashed private GCS evidence PASS on Mac. **DAG critical path, complete total-run root interval, resource counters and visual timeline are NOT DONE.**
- **#42 VAL-01:** task-contract-aware dimensions/floor/support findings and read-only real Blender front/side/top/isometric views merged, with actual Mac validation. **Not a generalized semantic judge.**
- **#43 BH-02:** read-only six-task Luna artifact audit and cost-ledger re-reconciliation, SHA checks, failure-inclusive gallery, offline tests PASS. **Actual private historical bundle has not been reviewed with this new tool; official upstream scorer still OPEN.**
- **#44 G1 integrator:** the real native table fixture automatically generates an 8-contact geometry report and four views, with traces and hash manifest. Mac run 40691475882 PASS, GCS 77 uploaded objects. First integration test failure 40691165626 remains historical evidence; replay fixed by using a new output directory. **No additional Luna calls made.**
- New development should branch from current main. Next priority: reconcile actual run traces/cost IDs, pinned official 3DCodeBench 5.0 scorer and reference-only environment, then typed-scoped repair/checkpoints. Do not turn the six-task 2/6 native acceptance into an official visual quality claim.

## Work packages: tasks, deliverables, negative paths, ownership

### PERF-01 · Agent tracing and bottleneck attribution (P0; new issue to track)
Owner: `src/geometry_harness/telemetry/`, `tests/telemetry/`, report adapter only in `evaluation/`. Extend, do not replace, `costs/` append-only ledger.
- Build `ExecutionTrace` with run/span/parent IDs, stage, attempt, status, monotonic duration, model/tool/runtime ID, token/cost ledger references, inputs/outputs hashes and recorded failure class. No secrets, unredacted prompts, home paths, private CAD geometry.
- Instrument actual cloud adapter, safe AST translation, audited builder, separate Blender inspector/reopen, renderer, scorer, tool and repair boundaries. Record both exclusive/inclusive timing and critical path from start/end timestamps (not sum of parallel span durations).
- Export scrubbed local JSON/JSONL and deterministic `performance-summary.json`; optional OpenTelemetry/OpenInference/Phoenix exporter **off by default**, no network dependencies.
- Acceptance: G0+G1 local/target runs emit complete spans and linked immutable cost summary; incomplete/failure paths preserve diagnostic evidence and UNKNOWN; no timing double-count; negative cases timeout/provider missing/process crash; verify private CI storage and review report.

### VAL-01 · Cheap-first deterministic geometric findings (P0; extends #9 and #5)
Owner: `src/geometry_harness/validation/`, validation tests; leave Blender builder ownership with current owner.
- Introduce typed `GeometryIssue` (`code, severity, affected_ids, expected, actual, units, tolerance, evidence, repairability, status`) and `ValidationReport`; schema-version them and embed hashes in manifest.
- Validate executable/native scene and object IDs first, then dimension/placement/contact/connectivity/non-target invariants **only where task constraints require them**; do not require manifold/closed mesh universally. Add 4-view cheap previews and only conditional independent VLM judge for irreducible perceptual quality.
- One negative fixture with disconnected object, one dimensional tolerance failure, one missing evidence case (UNKNOWN); no mocked VLM credited as visual success.
- Acceptance: reliable PASS/FAIL/UNKNOWN, numeric object-specific findings and real Blender E2E + gallery with failure cases. Validation cannot mutate scene.

### REPAIR-01 · Typed scoped patches, checkpoints and guarded execution (P0; extends #9/#11)
Owner: `src/geometry_harness/revisions/` and `repair/` with shared one-time `TypedSceneOperation` contract. Single integrator owns scene state interface.
- Stable persistent IDs and scene revision SHA; typed allowlisted `translate/resize/rotate/material` initial ops, with bounds, units, target checks and idempotency token. Later domain-specific door/wall operations only with explicit constraints.
- One trusted builder applies the patch within isolated staging scene; verify preconditions + postconditions + non-target invariants; atomic accept moves reference to new checkpoint. Crash/error keeps last accepted revision. Compare fresh-process replay; preserve original/edited/reverted .blend and before/after/rollback images.
- A/B `whole_scene_regenerate` vs `scoped_patch` on same controlled injected defect. Count all AI turns, tool calls, wall clock, failed attempts and error preservation.
- Acceptance: identical task and quality requirements, no unauthorized modification, reproducible rollback and negative tests for stale revision, target missing, corrupted journal, tool timeout.

### ORCH-01 · Adaptive decision/repair policy (P1; extends #9)
Owner: `src/geometry_harness/repair/policy.py` (one owner with REPAIR).
- Policy route: already satisfied→accept; deterministic fix with proof and permission→tool; ambiguous localized→LLM scoped patch; visual ambiguity→optional independent judge; repeated signature/stagnation/budget exhausted→stop/alternative/human review.
- Pin default **experimental** limits (e.g. 2 AI rounds, 12 tool calls, 240 active seconds), not empirically optimized promises. Preserve mandatory geometry constraints even if visual score plateaus.
- A/B fixed rounds vs policy with same baseline, execution budget and quality gates; separate improvement from safety/reliability outcomes; reject policy if it only hides difficult failures.
- Acceptance: full run trace shows decision reasons and remaining budget; negative cases prove no extra remote calls after stop and preservation of accepted artifact.

### TOOL-01 · Composite tools, stage cache and restricted parallelism (P1; new issue)
Owner: `src/geometry_harness/execution/`, optional `integrations/dcc/` after licence/version audit.
- Extract top recurring tool-call patterns from **actual** traces, then implement at most 2–3 composites initially: `inspect_geometry`, `render_validation_views`, `apply_verified_patch`. Every composite internally preserves per-step validations, errors, trace attribution and authorizations.
- Cache deterministic outputs by input hash + scene revision + Blender/tool/config versions; invalidation must handle geometry/material/camera changes; never assume stochastic model responses are safe reusable cache objects.
- Parallelize independent validation or disjoint immutable jobs only; mutation of the same scene is serialized/locked. No nested unbounded fan-out.
- A/B old primitive sequence vs composite under same conditions; fallback retained on measured regression.
- Acceptance: latency and tool-turn delta with no geometric/non-target regressions, negative cache invalidation, concurrent version conflict, missing tool/MCP, timeout.

### LOCAL-01 · Local model as interchangeable executor (P1; extends #12)
Owner: `src/geometry_harness/providers/local/`, offline test profiles. Can prototype after ProviderAdapter contract, before later milestone acceptance.
- Feature/capability negotiation for structured output, vision, tool use, context, tokens, memory, retries. Local models return the same safe typed AST-plan or operations; no arbitrary model code execution.
- Test basic same fixed fixture cloud vs local with no-egress evidence, peak RSS/latency, quality and total cost modelled separately. Never automatically fall back to cloud. Serial model load/unload if hardware memory requires.
- Full local create→inspect→repair and optional local VLM is a separate gate after REPAIR-01.
- Acceptance: real local model+Blender native reopen, offline network-denial, untrusted endpoint fail-closed and clear UNKNOWN for unavailable local visual judgement.

### ARCH-01 / ARCH-02 · Architecture vertical (P1; new issues)
Owner: `src/geometry_harness/domains/architecture/`, `benchmarks/architecture/`; generic core untouched.
- Initially **DXF only**, synthetic fixtures with disclosed units, layer mapping, walls/openings and tolerances; deterministic parsing and geometry first. Record missing layer conventions, open boundaries and ambiguity as FAIL/UNKNOWN rather than hallucinated geometry. Use bounded domain schema, not global Geometry IR.
- 10 synthetic fixtures (simple room, walls, door/window, multiple layers, bad units, missing opening, unclosed boundary, changes/rollback). Separate real customer test assets privately after authorization, **never public repo**.
- Gate: synthetic DXF → safe builder → reopened editable .blend/preview → objective measured wall/door positions and negatives, no LLM needed for known geometry. AI only for ambiguous intent/styling/changes that cannot be resolved safely.
- EX-03 #10 stays **a distinct generated-reference ablation**, not replaced with DXF input; no dataset reference leakage.

### INT-01 · Partner integration discovery / PoC (P1, externally gated; new issue)
Owner: future adapter behind documented local-only protocol, NOT partner code in source.
- After mutual NDA: observe real input/output formats, layers, iteration/repair loops, duration by stage, hardware, privacy/legal requirements, API terms and deployment, data flows, actual customer scope/budget. Validate whether there is a real editable model or image-only target.
- Define `submit_task/status/get_artifacts/apply_patch` conceptual interface; no network endpoint implementation until integration needs confirmed.
- Establish ownership of background IP (general harness) and foreground/client-specific connectors contractually. Partner repo, raw CAD, NDA-covered information, production credentials **private**.
- A/B partner pipeline vs bounded replacement on same authorized test cases, identical hardware/input/quality criteria and human sign-off; do not promise the reported 26→X minute reduction.
- Gate: verified telemetry + one replaceable step identified, successful sandbox PoC and independently accepted output; otherwise REWORK/DROP.

## Scientific benchmark and experiment protocol (PERF-02)

See the [benchmark protocol](../features/benchmark-protocol.md) and [full performance experiment contract](../features/harness-efficiency-experiments.md).
- Keep official 3DCodeBench public 6/24/212 cohort and upstream scorer isolated from generator, pinning exact revision/right/version. Internal AST-limited scene smoke is **not** an official score. Separate architecture/real-CAD suite and no mixing metrics.
- Experimental arms (same task/model/profile and fixed budgets except explicit intervention): A0 direct; A1 + deterministic gates; A2 + scoped repair; A3 + adaptive policy; A4 + measured composite tools; A5 chosen configuration with local model (model changes, so not a same-model causal A/B).
- Primary: paired P50/P90 **end-to-end accepted outcome** wall time and acceptance rate; support: model turns, tool calls, retries, trace critical path, geometric pass, non-target edit preservation, cost per accepted and peak RAM. Report failures/UNKNOWN, denominator and censored timeouts.
- Provisional practical targets to **pre-register**, not promises: >=20% P50 time reduction, >=30% model-turn reduction, no increase in blocking geometry failures, 100% evidence for claimed PASS. A six-item smoke is descriptive only; core 24+ paired replications/uncertainty are required for generalization.
- Stop/go: KEEP only if quality non-inferior at preregistered tolerance and improved latency/cost under approved budget; REWORK if mixed; DROP if consistently worse; INCONCLUSIVE if missing judge/runtime or insufficient sample. Never quietly swap task IDs or delete failures.

## Delivery sequence, isolation, and PR gates

**Wave 0 — planning (this revision):** documents/schemas/ownership/gates only; no inference calls, no runtime or CI label changes.
**Wave 1 (parallel, independent paths):** W1-PERF tracing/report; W1-BH external dataset/scorer baseline #4/#5/#7; W1-VAL typed issues & real geometric negative fixture. LOCAL adapter contract and DXF synthetic fixture research can be built on separate branches, but no accepted A/B yet.
**Wave 2 (converge):** stable scene object identity & checkpoint contract, guarded typed patch and real rollback E2E. One owner of scene revision to prevent parallel conflicting work.
**Wave 3 (parallel experiments):** bounded repair vs full regeneration, planner A/B, generated 2D ablation; compare only on frozen same-task run configuration.
**Wave 4:** optional adaptive policy and composites selected by traces; experimental no-egress local model/vision; deterministic DXF build and architecture suite.
**Wave 5:** partner code audit and private adapter after NDA; 4K Cycles only after accepted geometry and preview.

Suggested atomic PR sequence with exit gates:
1. `docs(plan)` this roadmap + feature specs, AGENTS + state; documentation-only.
2. `feat(perf)` spans, reports, cost-ledger linkage + G0/G1 E2E.
3. `feat(benchmark)` verified independent real smoke baseline and negative path.
4. `feat(validation)` typed geometry findings + 4-view real Blender evidence.
5. `feat(revisions)` stable IDs/checkpoints and typed patch executor.
6. `feat(repair)` one localized injected defect+rollback and A/B.
7. `feat(orchestration)` adaptive policy + decision report paired A/B.
8. `feat(tools)` evidence-chosen composites and cache A/B.
9. `feat(architecture)` DXF synthetic fixtures → native Blender validated.
10. `feat(local)` no-egress local basic E2E and measured comparison.
11. `feat(integration)` privately scoped partner adapter after authorizations.

**Parallel branch rules:** new branches from current `main`, explicit owner paths, no shared writes or accidental auto-merge, independently run fast contracts, verify exact trusted SHA on target Mac mini/GCS at integration; **costed calls opt-in and budget-approved**. A docs-only PR is not a run-quality proof. All production claims need actual negative-case E2E evidence.

**CI routing:** source `.github/workflows` only hosts cheap unit/template checks. Real Blender/GCS and approved billed requests run through centrally owned `daniele21/local-runner-infra` with verified `local-mac-mini-*` identity, pinned source SHA, WIF private bucket and exact artifact/hash inventory. No local runner labels provisioned from this public repo. Private/offline runs are not automatically uploaded: use separately authorized exports.

## Issue mapping / backlog (no issue is implicitly closed)

Existing: [#3 G0](https://github.com/daniele21/3d-rendering-llm/issues/3), [#4 catalog](https://github.com/daniele21/3d-rendering-llm/issues/4), [#5 evaluation](https://github.com/daniele21/3d-rendering-llm/issues/5), [#6 providers](https://github.com/daniele21/3d-rendering-llm/issues/6), [#7 G1](https://github.com/daniele21/3d-rendering-llm/issues/7), [#8 planner](https://github.com/daniele21/3d-rendering-llm/issues/8), [#9 validation/repair](https://github.com/daniele21/3d-rendering-llm/issues/9), [#10 generated-2D](https://github.com/daniele21/3d-rendering-llm/issues/10), [#11 edits](https://github.com/daniele21/3d-rendering-llm/issues/11), [#12 local](https://github.com/daniele21/3d-rendering-llm/issues/12), [#13 Cycles](https://github.com/daniele21/3d-rendering-llm/issues/13), [#23 FinOps](https://github.com/daniele21/3d-rendering-llm/issues/23).

New tracking **created**: [#33 PERF-01 — tracing](https://github.com/daniele21/3d-rendering-llm/issues/33), [#34 PERF-02 — efficiency A/B](https://github.com/daniele21/3d-rendering-llm/issues/34), [#35 TOOL-01 — composites/cache](https://github.com/daniele21/3d-rendering-llm/issues/35), [#36 ARCH-01 — imported DXF→3D](https://github.com/daniele21/3d-rendering-llm/issues/36), [#37 ARCH-02 — architecture fixtures/metrics](https://github.com/daniele21/3d-rendering-llm/issues/37), [#38 INT-01 — generic interface / private discovery boundary](https://github.com/daniele21/3d-rendering-llm/issues/38). Existing #9 owns deterministic validation/repair policy, #11 owns typed scene operation/revision implementation, #12 owns local execution. Avoid duplicate owners.

## Decisions / risks / validation before productization

- Risks: longer multi-round contexts, VLM noise, MCP chatty operations, unsafe AST expansion, invalid cache keys, limited local RAM, non-comparable 3DCodeBench environments, partner claims without evidence, customer IP leakage.
- Prefer simple direct builder over agent planning if A/B does not support improvement; prefer deterministic patch to LLM; prefer compositor only when trace shows actual repeated pattern; prefer no tool expansion over unsafe tools.
- **IP / distribution**: inspect licences of upstream source, models, textures, data and DCC plugins independently; Blender GPL and deployment implications need specific counsel. No assumed rights to partner materials. Background/foreground IP terms require signed agreement, not code comments.
- Open questions for partner: exact data formats (DXF/DWG/PDF/IFC), whether scene is native editable, requested 4K target, stage breakdown, calls per loop, revision semantics, target machines, no-egress vs on-prem cloud, commercial budget and success criteria.
- No estimation of speedup is accepted without repeatable partner measurements.

## End-of-sprint acceptance checklist

- [ ] Correct source SHA/branch/runtime, deterministic task IDs, scorer/prompt/settings pins and licence inventory.
- [ ] Real input→output native scene opened in independent Blender process; objective and negative geometry checks; visual gallery inspected.
- [ ] Error/timeout/cancel and UNKNOWN preserved; no silent fallback; previous accepted scene survives.
- [ ] Cost ledger complete or explicitly UNKNOWN; trace critical path reconciled; environment and memory captured.
- [ ] A/B paired denominator, identical constraints except intervention, quality/latency/cost decision KEEP/REWORK/DROP/INCONCLUSIVE.
- [ ] Private-only data/artifacts stored in approved environment; no secrets/models/images in Git.
- [ ] Documentation evidence state updated in [current-state](../current-state.md) after passing runs; never confuse this planning text with done work.
