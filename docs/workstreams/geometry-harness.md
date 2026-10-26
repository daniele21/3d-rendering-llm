# Geometry Harness — incremental delivery workstream

Status: active
Owner: 3d-rendering-llm
Read when: planning, building, validating or resuming the Geometry Harness.
Product depth: PRODUCT_STRATEGIC (new product, runtime and trust boundary).
Planning baseline: main at 5710a83aa573e91b1c6285eda0bace43e43720d8 (2026-10-26).
State: **planning only**. No milestone is implemented or validated by this document.

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

## Vertical milestone contract

**Showcase gate for G0–G8:** implement the real per-stage `tests/e2e/test_showcase_gX.py` specified in [showcase evidence contract](../features/showcase-evidence.md). Every test must **generate and publish** inspectable PNG/contact sheet + offline gallery + manifest + native files, assert meaningful behavior and test a failure path. Missing or mocked deliverables do not complete a milestone. Commands below are **proposed, not implemented**. Reuse a stable four-leg table fixture initially.

| Slice | Immediately tangible result | Planned user demo | Gate / definition of done | Depends | State |
| --- | --- | --- | --- | --- | --- |
| G0 — Boot + render | .blend + PNG of deterministic 4-leg table, no AI | geometry demo deterministic-table | Fresh setup and doctor; open/re-check 5 objects, dimensions, manifest, timeout cleanup | — | READY |
| G1 — AI creation | Text request -> first AI-rendered object | geometry run --profile cloud --mode code | Script + PNG/.blend/manifest saved; failures bounded; no MCP yet | G0 | BLOCKED |
| G2 — Repair loop | Four views and before/after report | geometry run --feedback geometric-visual | Geometry gates + optional independent judge + bounded retry and round evidence | G1 | BLOCKED |
| G3 — Typed MCP edit | Recolor only tabletop, see before/after | geometry edit RUN --prompt "Blue tabletop" | Real dcc-mcp Blender edit, save/reopen and unchanged other transforms | G1 (parallel with G2) | BLOCKED |
| G4 — Hybrid + rollback | Versions and lossless restoration | geometry rollback RUN REV | Stable IDs, action journal, replay/new-process verification and rollback | G2,G3 | BLOCKED |
| G5 — Agent comparisons | Per-model/strategy gallery and report | geometry benchmark --suite fixtures/core | Fixed prompts/budgets, valid-scene metrics, time/cost and manual spot checks | G4 | BLOCKED |
| G6 — Local code generation | Same table generated by local open-weight model | geometry run --profile local --mode code | No API keys; output validated; peak memory/latency compared with G5 | G1 (parallel with G3–G5) | BLOCKED |
| G7 — Full local loop | Local LLM/VLM creates, judges and repairs offline | geometry run --profile local --offline | Controlled no-egress E2E, cached models and fail-closed optional visual judge | G2,G4,G6 | BLOCKED |
| G8 — Final render workflow | Cycles render and revisable gallery | geometry render RUN --quality final; geometry gallery RUN | Output reopened; preview/final comparison; functional visual review | G4,G5 | BLOCKED |

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
5. Implement the real G0 showcase E2E: output `index.html`, contact sheet, assertions, `.blend`, preview and manifest under `ci-artifacts/showcase/`; reopen/check/hash, review in central Mac Actions artifact.

**CI routing:** `.github/ci/local-test.sh` runs on `daniele21/local-runner-infra` Mac mini via central-direct, pinned source SHA; `local-ci/mac` is authoritative. Current script is *docs-only preflight*, not G0. G0 requires real preview PNG, .blend reopen and showcase bundle; Mac availability cannot be assumed. Paid models remain manual. Details: [evidence contract](../features/showcase-evidence.md).

## Cross-cutting validation

- Fixed suite: cube, table, chair, material edit, geometry edit, malformed script, disconnected leg.
- Compare code/typed/hybrid with equal prompts, budgets and tool versions; report acceptance, geometry, preservation, latency, cost/valid result and visual rubric separately.
- Cheap checks during iteration; affected Blender E2E at integration; hardware/offline/UI-media evidence at release. Calibrate quality thresholds from the baseline, not guesses.

## Resume checkpoint

- Source: main 5710a83aa573e91b1c6285eda0bace43e43720d8, planning branch plan/incremental-geometry-harness.
- Confirmed: repository currently contains repo-template-sw distribution and copied adopter templates, not a specialized Geometry Harness app; only main branch existed at planning time.
- Confirmed upstream: 3DCodeVerse includes code-first agentic pipeline; dcc-mcp-blender and dcc-mcp-core expose typed Blender MCP tooling; integration, macOS compatibility and performance **not yet tested in this repository**.
- Unresolved: exact upstream SHAs/version matrix; first closed vendor/model; chosen local model/VLM; precise resource and quality budgets. None blocks G0.
- Next: implement G0 + its real showcase test/evidence publisher; inspect the PNG and reopen the .blend before G1.

## Durable destinations and lifecycle

At each integration: docs/product.md for settled mission/outcomes, docs/architecture.md for module ownership/integration decisions, docs/features/ for shipped behavior, docs/current-state.md for integrated/blocked/next. Architecture decisions on code-first/MCP state or licensing go in ADR only when settled. Keep this workstream as the sole active execution plan, update states/checkpoint on meaningful handoffs; archive/delete it after roadmap completion once durable knowledge is transferred. Git history records completed work.
