# Geometry Harness — incremental delivery workstream

Status: active
Owner: 3d-rendering-llm
Read when: planning, building, validating or resuming the Geometry Harness.
Product depth: PRODUCT_STRATEGIC (new product, runtime and trust boundary).
Planning baseline: main at 5710a83aa573e91b1c6285eda0bace43e43720d8 (2026-10-26).
State: **benchmark-driven sprint plan approved for proposal (2026-10-27), not implementation evidence**. G0 code is a candidate; Mac Blender + private GCS acceptance remains unverified. Later G1–G8 milestones are not implemented or validated by this document.

## Product intent

- Product depth: PRODUCT_STRATEGIC. Primary user: maker/developer on Apple Silicon.
- Problem: create an editable, verifiable Blender scene from text, then revise it without rebuilding by hand.
- Desired outcome: visible, repeatable and measured artifact per milestone; closed-provider baseline, then fully offline open-weight inference.
- Risks: effectiveness vs direct Blender MCP; Mac compatibility; code/MCP replay; VLM quality; local memory and licences.
- Assumptions to verify: 3DCodeVerse ports to Mac; MCP edits bridge reliably; feedback helps; local LLM completes basic tasks.
- Success evidence: E2E artifact acceptance, edit preservation, cost/latency/quality reports, no-egress local run.
- Post-release: when is agentic repair more valuable than direct tool calls?
- Durable source: [product.md](../product.md).

## Decision and boundaries

**Build a thin product-specific integration harness, not a wholesale merge or replacement of Blender.** Start with code-first, then add MCP editing and hybrid mode. Reuse 3DCodeVerse's tested ideas/modules selectively; run dcc-mcp-blender/dcc-mcp-core as pinned external adapters. Confirm API, version and license compatibility before importing or modifying upstream code.

Initial scope: static props and tiny scenes; Python + uv CLI; Blender as the only renderer/geometry backend; macOS Apple Silicon primary target; closed-model experimentation first; full local open-weight execution later. PNG + .blend + GLB where supported, with editable source and run manifest.

Explicit non-goals for early slices: photorealistic cinematic scenes, large environments, CAD production tolerances, animation, 2D, neural mesh generation, fine-tuning, marketplace/assets, public web hosting, subscription/account infrastructure. Defer custom universal Geometry IR and React editor until evidence justifies them.

## Delivery principles / invariants

1. Every slice provides a runnable command, PNG, .blend when relevant, manifest and tests; never infrastructure alone.
2. Code truth = source; MCP truth = snapshot + typed journal; hybrid = source/snapshot + replayable patches.
3. Stable IDs, immutable accepted artifacts, checkpoint/rollback and verified replay; detect divergence.
4. Vendor logic never enters geometry/render/evals. Offline = no credentials, network, or cloud fallback.
5. Deterministic geometry checks before subjective VLM; preserve failures and UNKNOWN.
6. Sandbox generated code, bound memory/time/cost and clean owned processes on exit.
7. Pin upstream + notices; check code, datasets, packages, models and assets separately.
8. Keep heavy runs, weights and generated files out of Git.

## Architecture direction

See [proposed architecture](../architecture.md): model-independent agent; code-first (3DCodeVerse), typed MCP (dcc-mcp-blender/core), hybrid revision ledger, deterministic validation and optional visual judge. All are proposed, not yet tested. Pin upstream revisions only after smoke; track licences/notices.

## Agile, benchmark-driven execution plan (2026-10-27)

**Goal stays unchanged:** prompt -> editable/verifiable Blender scene -> inspectable render -> targeted refinement -> local/offline option. Blender remains geometry/render backend. CADCraft is **not** an implementation dependency; text->2D->3D is a *controlled ablation*, not the default route. Evidence from image-conditioned 3D, 2D layouts, orthographic reconstructions and 3DCodeVerse motivates experiments, not a blanket 2D-first architecture.

### Product/sprint invariants

1. **Vertical user journey every sprint:** runnable command -> real Blender scene (when geometry is in scope) -> reopen + geometry checks -> PNG/contact-sheet -> HTML gallery -> manifest/assertions/negative test. No solely-infrastructure sprint counts as shipped.
2. **Benchmarks start at S1, not G5.** Use [benchmark protocol](../features/benchmark-protocol.md): 3DCodeBench 6 smoke / 24 stratified core / 212 release; paired task IDs/configs, independent evaluators and strict reference isolation. Add realistic BlenderWorld journeys *separately* once its own runtime is available.
3. **Evidence-driven decisions:** one hypothesis at a time against a frozen baseline, report visual quality, valid-scenes, geometry, preservation, cost and latency separately. Record KEEP / REWORK / DROP with evidence, including unsuccessful hypotheses and UNKNOWN.
4. **Agile promotion gate:** a sprint candidate is DONE only with real E2E **including negative path**, exact commit/run environment identity and inspectable immutable artifacts (or documented unavailable external prerequisites). Feature flags keep unfinished experiments out of the accepted path.
5. **Cost controls:** cheap local checks and deterministic Blender in routine CI; billed models, GPU-heavy scorers, full 212 cases and local LLM/VLM runs are explicit opt-in with time/token/spend limits. Fail closed; never treat mocks as model/geometry evidence.
6. **Source truth + portability:** preserve Blender Python source, scene/native checkpoints, hashes and revision lineage; no project-wide 2D/CAD intermediate schema until a measured experiment supports it.
7. **Keep releases shippable:** each candidate must still complete the previous accepted user journey. "Green" unit tests alone do not justify integration.
8. **Separate benchmark rules from product rules:** benchmark-specific reference geometries, prompts and scoring MUST NOT become hidden generator guidance. Compliance/licence of benchmark code, datasets, assets and model weights is verified independently.

### Sprint roadmap: smallest increment with visible output

| Sprint | Hypothesis or user improvement | E2E deliverable / pass gate | Dependencies | Primary tracking |
| --- | --- | --- | --- | --- |
| **S0 = G0** | Deterministic Blender reproducibility + artifact pipeline | True Mac mini Blender table; new-process .blend reopen; PNG, gallery, manifest, negative missing-Blender/timeout; **verified GCS bundle** | existing G0 candidate | [GH-00 #3](https://github.com/daniele21/3d-rendering-llm/issues/3) |
| **S1 = G1 + benchmark MVP** | First AI-generated editable object is measurable | One real paid/approved AI prompt -> Blender script -> .blend/PNG -> 3DCodeBench smoke task metrics and error path; freeze first baseline | S0; task catalogue/provider | [AI-02 #7](https://github.com/daniele21/3d-rendering-llm/issues/7) |
| **S2 = early G2/G5 evidence** | Broader fixed geometry/multiview benchmarks discover defects | Frozen 24 core subset report, 4-view render + deterministic geometry checks, error taxonomy, compare to S1 | S1 | [BH-02 #5](https://github.com/daniele21/3d-rendering-llm/issues/5), [EX-02 #9](https://github.com/daniele21/3d-rendering-llm/issues/9) |
| **S3 = planner ablation** | Explicit geometry/parts/relations improve generation | Direct vs structured-planner paired 3D scenes, gallery, quality/cost/latency and KEEP/DROP decision | S1 + evaluation | [EX-01 #8](https://github.com/daniele21/3d-rendering-llm/issues/8) |
| **S4 = G2 bounded repair** | Geometry and independent multiview judge can fix a known failure | Before/after views, valid checks, bounded retries, preservation of last accepted scene, score/cost delta | S2 | [EX-02 #9](https://github.com/daniele21/3d-rendering-llm/issues/9) |
| **S5 = 2D-assisted ablation** | 2D concept, orthographic projections or scene layout improve relevant categories | Text-only vs auto-generated 2D references on same prompts, separate oracle-image control, valid .blend/renders and relative lift | S1 + evaluation; S4 optional | [EX-03 #10](https://github.com/daniele21/3d-rendering-llm/issues/10) |
| **S6 = G3/G4** | Targeted edits and rollback preserve independent geometry | Real Blender edit via code vs typed MCP, reopened .blend, before/after/rollback and non-target invariants | S1, G0 | [EDIT-01 #11](https://github.com/daniele21/3d-rendering-llm/issues/11) |
| **S7+ = G6/G7/G8** | Better render quality and local execution preserve result reliability | Preview vs Cycles same revision; open-weight text and later local vision+repair no-egress on Apple Silicon | S1, S4 where relevant | [RENDER-01 #13](https://github.com/daniele21/3d-rendering-llm/issues/13), [LOCAL-01 #12](https://github.com/daniele21/3d-rendering-llm/issues/12) |

**Non-waterfall:** S0–S1 are acceptance gates, not a ban on parallel exploration. S3/S4/S5 strategy prototypes and S7 render/local adapters can start independently behind flags/isolated code paths; only claim sprint improvement after a measured end-to-end run using the stable suite. G5 becomes an *ongoing benchmarking capability* rather than an end-stage feature; G8 gallery exists from G0 and final Cycles polish comes later.

### Tracked dependency DAG + safe parallel lanes

**READY NOW (parallel, no shared writes; preparation != sprint completion):**

| Lane | Issue | Explicit file ownership | Handoff / gate |
| --- | --- | --- | --- |
| A — target runtime/evidence | [GH-00 #3](https://github.com/daniele21/3d-rendering-llm/issues/3) | `src/geometry_harness/blender/`, G0 E2E, CI script | G0 real Blender + GCS verification |
| B — reference benchmark/provenance | [BH-01 #4](https://github.com/daniele21/3d-rendering-llm/issues/4) | `benchmarks/catalog/`, `benchmarks/fixtures/`, benchmark tests | immutable task IDs, license/version manifest, 6/24/212 suites |
| C — quality/evaluation contracts | [BH-02 #5](https://github.com/daniele21/3d-rendering-llm/issues/5) | `src/geometry_harness/evaluation/`, `benchmarks/reporting/` | EvaluationRecord schema, comparators, negative tests |
| D — provider/code-generation contract | [AI-01 #6](https://github.com/daniele21/3d-rendering-llm/issues/6) | `src/geometry_harness/providers/`, `agents/`, `config/profiles/` | model adapter and safe code runner contract, **no cloud billing in automatic CI** |

**CONVERGE:** [AI-02 #7](https://github.com/daniele21/3d-rendering-llm/issues/7) alone owns CLI wiring and the G1 showcase. Depends on verified A, B-smoke, D, and C-minimum evaluation schema. No parallel conflicting CLI edits.

**READY FOR DESIGN, NOT ACCEPTED E2E:** [EX-01 #8](https://github.com/daniele21/3d-rendering-llm/issues/8) planner, [EX-02 #9](https://github.com/daniele21/3d-rendering-llm/issues/9) validation/repair, [EX-03 #10](https://github.com/daniele21/3d-rendering-llm/issues/10) 2D references, [EDIT-01 #11](https://github.com/daniele21/3d-rendering-llm/issues/11) editing/rollback, [LOCAL-01 #12](https://github.com/daniele21/3d-rendering-llm/issues/12) local, [RENDER-01 #13](https://github.com/daniele21/3d-rendering-llm/issues/13) final. Each uses non-overlapping owned folders, can prototype behind strategy/adapters, and must rebase/verify exact integration SHA before merge.

**Integration contract for coding agents:** write one concrete interface note before fan-out (TaskSpec, EvaluationRecord, SourceArtifact/RunManifest, bounded ExecutionBudget). Each lane uses an isolated branch/worktree from the same reviewed base; never modify other lanes' directories without coordination. Merge one user-visible vertical slice at a time; run cheap tests on every change, actual Blender on target for integration, and cost-bounded model tests only when explicitly authorized. If a runner is inaccessible or model credentials are absent, report BLOCKED and preserve diagnostics rather than substitute fake evidence.

### Stage-gate decision and benchmark policy

- **S0:** exact trusted source SHA on dedicated Mac mini, Blender build and reopen, GCS upload object paths/sha256 confirmed; GCS bootstrap may already exist, verify before changing infra.
- **S1:** first *real* model call, a 3DCodeBench task, actual script/native scene/renders and negative provider/script handling; capture stable task IDs and model config. Prior to this, no claim of AI-quality improvement.
- **Every A/B sprint:** paired immutable prompts and task IDs; same generator, budgets, environment and scoring unless the tested variable is intentionally changed; report repetitions/uncertainty and both pass rate and cost per accepted result. No cherry-picked showcase results.
- **2D ablation:** never use benchmark reference image/factory as generative input in the text-only comparison. Treat externally supplied reference views as a *different supervised condition*. Count all reference-generation costs and note hidden geometry ambiguity.
- **Local/offline:** fail closed if any remote provider active; model not found or VLM missing => explicit FAIL/UNKNOWN with no fallback.
- **Release:** full frozen suite 212 only when supported by data/runtime/licensing and approved compute budget, plus optional BlenderWorld tasks in its separately pinned environment. Do not assert official leaderboard comparability unless the upstream full scorer, runtime and evaluation settings match.

### Durable tracking / review cadence

- **Canonical delivery state:** this workstream; **execution checklists and work boundaries:** linked GitHub issues #3–#13; **evaluation protocol and suite identity:** [benchmark-protocol.md](../features/benchmark-protocol.md); **artifact gate:** [showcase-evidence.md](../features/showcase-evidence.md).
- Per issue attach branch/PR, exact source SHA, commands, target runner, failure evidence, gallery/GCS links and quality metrics. No GitHub issue is marked complete just because code exists.
- At each sprint demo: open current and previous galleries side-by-side, read objective PASS/FAIL/UNKNOWN and costs, document findings and next narrow hypothesis. On rejected experiments document why and keep the baseline.
- This roadmap change is *planning only*, not proof that GH-00/BH-01/BH-02/AI-01 are implemented.

## Vertical milestone contract

**Showcase gate for G0–G8:** implement the real per-stage `tests/e2e/test_showcase_gX.py` specified in [showcase evidence contract](../features/showcase-evidence.md). Every test must **generate and publish** inspectable PNG/contact sheet + offline gallery + manifest + native files, assert meaningful behavior and test a failure path. Missing or mocked deliverables do not complete a milestone. Commands below are **proposed, not implemented**. Reuse a stable four-leg table fixture initially.

| Slice | Immediately tangible result | Planned user demo | Gate / definition of done | Depends | State |
| --- | --- | --- | --- | --- | --- |
| G0 — Boot + render | .blend + PNG of deterministic 4-leg table, no AI | geometry showcase --milestone G0 | Fresh setup and doctor; open/re-check 5 objects, dimensions, manifest, timeout cleanup | — | ACTIVE |
| G1 — AI creation | Text request -> first AI-rendered object | geometry run --profile cloud --mode code | Script + PNG/.blend/manifest saved; failures bounded; no MCP yet | G0 | BLOCKED |
| G2 — Repair loop | Four views and before/after report | geometry run --feedback geometric-visual | Geometry gates + optional independent judge + bounded retry and round evidence | G1 | BLOCKED |
| G3 — Typed MCP edit | Recolor only tabletop, see before/after | geometry edit RUN --prompt "Blue tabletop" | Real dcc-mcp Blender edit, save/reopen and unchanged other transforms | G1 (parallel with G2) | BLOCKED |
| G4 — Hybrid + rollback | Versions and lossless restoration | geometry rollback RUN REV | Stable IDs, action journal, replay/new-process verification and rollback | G2,G3 | BLOCKED |
| G5 — Comprehensive comparisons (ongoing since S1) | Per-model/strategy gallery and report | geometry benchmark --suite fixtures/core | Fixed prompts/budgets, valid-scene metrics, time/cost and manual spot checks | G4 | BLOCKED |
| G6 — Local code generation | Same table generated by local open-weight model | geometry run --profile local --mode code | No API keys; output validated; peak memory/latency compared with G5 | G1 (parallel with G3–G5) | BLOCKED |
| G7 — Full local loop | Local LLM/VLM creates, judges and repairs offline | geometry run --profile local --offline | Controlled no-egress E2E, cached models and fail-closed optional visual judge | G2,G4,G6 | BLOCKED |
| G8 — Final render workflow (gallery begins at G0) | Cycles render and revisable gallery | geometry render RUN --quality final; geometry gallery RUN | Output reopened; preview/final comparison; functional visual review | G4,G5 | BLOCKED |

### Implementation tasks, ownership and parallel work

| ID | Owns/writes | Scope / integration boundary | Depends | Parallel |
| --- | --- | --- | --- | --- |
| G0a | root app scaffold, AGENTS.md, README.md, .engineering/, scripts/, docs/product.md | **Adopt** copied repo-template-sw as this app; remove template-project identity and unused shipped template content; preserve only fit engineering contracts; pin Python/uv and command/CI semantics | — | with G0b after interface agreement |
| G0b | src/.../blender/, fixtures/, tests/smoke/ | Blender doctor, minimal Python build, bounded headless render, dimensions/open/export smoke; no AI | — | yes, separate files |
| G1a | src/.../providers/, config/profiles/ | Provider abstraction, API key safety, capabilities, cloud CLI/API adapter; explicit opt-in remote usage | G0 | with G1b |
| G1b | src/.../agents/, src/.../runs/, tests/e2e/ | Adapt minimal 3DCodeVerse code-first build; capture script, output, timings/usage/errors; cheap run fixture | G0 | yes, converge into G1 |
| G2a | src/.../validation/, src/.../render/ | Reuse geometric gates, fixed multiview cameras, reports and render comparison | G1 | with G2b |
| G2b | src/.../judges/, src/.../repair/ | Judge/repair loop with bounded iterations, independent spec and no generator reasoning leak | G1 | yes, converge into G2 |
| G3a | src/.../integrations/dcc/, config/tools/ | MCP session bridge, discovery/search-describe-call, typed tool whitelists, Blender version compatibility | G1 | with G2 |
| G4a | src/.../revisions/, tests/replay/ | Journaling, stable IDs, snapshots, replay consistency, rollback, crash recovery | G2,G3 | no, owns state contract |
| G5a | benchmarks/, src/.../evaluation/, tests/fixtures/ | Task registry, provider x mode matrix, reports, quality/cost/latency statistics, artifact lineage | G4 | with G6 |
| G6a | src/.../providers/local/, config/profiles/local.* | Korgis/llama.cpp/MLX compatible runtime contract; text generation fallback if tool calling weak | G1 | yes |
| G7a | src/.../judges/local/, tests/offline/ | Open-weight VLM, offline/no-egress checks, memory/residency control | G2,G6 | with G5/G8 |
| G8a | frontend/ or minimal static viewer, src/.../render/final/ | Gallery first; add React/Three.js only if static viewer insufficient, later material editor | G4 | with G7 |

**Integration policy:** non-overlapping subtasks may use separate working trees but join one feature branch for each visible slice. Integrate coherent outcomes into the shared branch after required automated gates; do not publish a waterfall of technical-only PRs. Define contracts before parallel edits.

## Executable current slice — G0

1. Inspect repo-template-sw content; perform project adoption instead of pretending current template is already application code. Update root README/AGENTS and specialize the engineering command/E2E configs; remove or relocate unrelated template-distribution machinery deliberately.
2. Build only a deterministic tabletop + four-leg Blender fixture; use explicit metric units, object naming, camera/light, fixed preview settings and an isolated output directory.
3. Provide native install/doctor/demo/check/test commands with no cloud or model dependency. One command must produce preview.png, scene.blend and manifest.json.
4. Test open/re-save, count/names, bounds/contacts, missing Blender error, timeout and cleanup; run on local Apple Silicon or repository-owned automated macOS runner when available.
5. Implement the real G0 showcase E2E: output `index.html`, contact sheet, assertions, `.blend`, preview and manifest under `ci-artifacts/showcase/`; reopen/check/hash, persist to private GCS from the Mac mini workflow, and review the downloaded bundle.

**CI routing:** `.github/ci/local-test.sh` runs via central `geometry-mac-mini.yml` on a `local-mac-mini-*` runner at pinned source SHA. The G0 code exists; real Blender is still missing in verified runner preflight. G0 requires PNG, reopened .blend and a passing private GCS upload gate; source `local-ci/mac-mini` status is secondary. GCS setup is documented in central `docs/geometry-gcs-artifacts.md`. Paid models remain manual. Details: [evidence contract](../features/showcase-evidence.md).

## Cross-cutting validation

- Fixed developmental suite: cube, table, chair, material edit, geometry edit, malformed script, disconnected leg; add a frozen non-leaking 3DCodeBench 6/24/212 benchmark suite after licensing/version validation. See benchmark-protocol.md.
- Compare code/typed/hybrid with equal prompts, budgets and tool versions; report acceptance, geometry, preservation, latency, cost/valid result and visual rubric separately.
- Cheap checks during iteration; affected Blender E2E at integration; hardware/offline/UI-media evidence at release. Calibrate quality thresholds from the baseline, not guesses.

## Resume checkpoint

- Source: main 5710a83aa573e91b1c6285eda0bace43e43720d8, planning branch plan/incremental-geometry-harness.
- Confirmed: repository currently contains repo-template-sw distribution and copied adopter templates, not a specialized Geometry Harness app; only main branch existed at planning time.
- Confirmed upstream: 3DCodeVerse includes code-first agentic pipeline; dcc-mcp-blender and dcc-mcp-core expose typed Blender MCP tooling; integration, macOS compatibility and performance **not yet tested in this repository**.
- Unresolved: exact upstream SHAs/version matrix; first closed vendor/model; chosen local model/VLM; precise resource and quality budgets. None blocks G0.
- Next: provision GCS/WIF, install Blender on Mac mini, rerun G0 and inspect the bucket's .blend/PNG plus SHA-256 manifest before marking DONE.

## Durable destinations and lifecycle

At each integration: docs/product.md for settled mission/outcomes, docs/architecture.md for module ownership/integration decisions, docs/features/ for shipped behavior, docs/current-state.md for integrated/blocked/next. Architecture decisions on code-first/MCP state or licensing go in ADR only when settled. Keep this workstream as the sole active execution plan, update states/checkpoint on meaningful handoffs; archive/delete it after roadmap completion once durable knowledge is transferred. Git history records completed work.
