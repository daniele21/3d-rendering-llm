# Geometry Harness — incremental delivery workstream

Status: active
Owner: 3d-rendering-llm
Read when: planning, building, validating or resuming the Geometry Harness.
Product depth: PRODUCT_STRATEGIC (new product, runtime and trust boundary).
Planning baseline: main at 5710a83aa573e91b1c6285eda0bace43e43720d8 (2026-10-26).
State: **planning only**. No milestone is implemented or validated by this document.

## Product intent

- **User:** developer/maker creating and iterating on real 3D assets using AI, first on Apple Silicon.
- **Job:** turn a text request into an inspectable, editable Blender scene, render it, correct errors, compare agents, and eventually run it without remote inference.
- **Desired outcome:** each release produces a tangible artifact and a repeatable demo; models and generation strategies are interchangeable without replacing the scene, renderer or evaluator.
- **Value risks:** better prompts or existing Blender MCP may already solve simple cases; test quality and incremental editing before expanding.
- **Usability risks:** terminal-only results are hard to inspect; publish PNG previews and a simple local gallery before a complex editor.
- **Feasibility risks:** macOS/ARM64 compatibility, MCP state vs code-as-truth, VLM effectiveness, local model tool use, memory/runtime/cost.
- **Viability risks:** inherited template overhead, upstream churn, transitive licenses, nondeterministic renders, API spend and asset sizes.
- **Assumptions to falsify:** (A1) 3DCodeVerse pipeline can run with practical macOS adaptations; (A2) dcc-mcp-blender can edit the resulting saved scene through a stable bridge; (A3) feedback improves acceptance enough to justify added inference; (A4) open-weight models can complete the same elementary tasks within available local memory.
- **Evidence:** staged demos, automated E2E, per-run cost/latency/geometry reports and a fixed comparison suite. No superiority claims without measurements.
- **Post-release learning:** which users/tasks benefit from agentic repair and whether local privacy/low marginal cost compensates for quality and latency gaps.

## Decision and boundaries

**Build a thin product-specific integration harness, not a wholesale merge or replacement of Blender.** Start with code-first, then add MCP editing and hybrid mode. Reuse 3DCodeVerse's tested ideas/modules selectively; run dcc-mcp-blender/dcc-mcp-core as pinned external adapters. Confirm API, version and license compatibility before importing or modifying upstream code.

Initial scope: static props and tiny scenes; Python + uv CLI; Blender as the only renderer/geometry backend; macOS Apple Silicon primary target; closed-model experimentation first; full local open-weight execution later. PNG + .blend + GLB where supported, with editable source and run manifest.

Explicit non-goals for early slices: photorealistic cinematic scenes, large environments, CAD production tolerances, animation, 2D, neural mesh generation, fine-tuning, marketplace/assets, public web hosting, subscription/account infrastructure. Defer custom universal Geometry IR and React editor until evidence justifies them.

## Delivery principles / invariants

1. **Visible first:** each slice ships one documented command, a screenshot/PNG, a native .blend where meaningful and an inspectable per-run directory. Show the output even if a later step is blocked.
2. **One source of truth per execution mode:** code-first = source + dependencies; tool-first = initial snapshot + typed operation journal; hybrid = source/snapshot + replayable patch sequence. Never claim reproducibility from a final screenshot alone.
3. **Never silently overwrite a successful artifact.** Each run/revision has a unique ID; checkpoint before state mutation; rollback and replay are tested before promoting hybrid.
4. **Providers are behind narrow interfaces.** Closed APIs and vendor CLIs are temporary experiment adapters; no renderer/test/eval code may depend on a vendor-specific message format. Local runtime must not require a cloud account.
5. **Separate objective and subjective verification.** Geometry measurements and execution gates precede VLM judgement. A visual score does not certify mesh validity, dimensional accuracy or manufacturing readiness.
6. **Safe execution:** generated bpy code is untrusted; isolated work directory/process, bounded time/memory/iterations, disabled network where supported, secrets outside logs, owned process cleanup, and no arbitrary writes outside workspace.
7. **Offline is a tested property**, not merely a local endpoint: models, textures and assets pre-cached; no outgoing requests; remote fallbacks forbidden in local profile.
8. **Cheap feedback first:** deterministic smoke/format/unit tests during iteration; full affected E2E at integration; real-device GPU/render evidence before release. No heavy render suite on every commit.
9. **Upstream hygiene:** pin SHAs/versions, keep attribution/license inventory, avoid copying large code trees, track deviations in an ADR; verify licensing for code, Blender extension builds, models and datasets independently.
10. **Local-only large artifacts:** do not commit generated .blend/GLB/PNG, model weights, eval caches or full raw transcripts; store manifests/small fixtures in Git and run outputs in ignored directories or bounded CI artifacts.

## Architecture direction (interfaces, not premature implementations)

User prompt/spec -> ProviderAdapter (planner / generator / visual judge, cloud or local)
-> AgentOrchestrator -> ExecutionStrategy (code_first | tool_first | hybrid)
-> BlenderSession (headless build / MCP live edits)
-> DeterministicValidator -> Render(multiview preview / final)
-> VisualJudge (optional) -> RevisionStore + RunManifest -> CLI/gallery/export.

Contracts to introduce only when first consumed:
- SceneArtifact: run_id, source hash, Blender version, native scene path, render paths, exports, dependency/model metadata.
- ToolAction: idempotency key, target stable object ID, typed args, preconditions, postconditions, result, revision ID.
- ValidationReport: execution/geometry/spatial/visual checks with independent PASS/FAIL/UNKNOWN and evidence paths.
- AgentAdapter: structured messages, tool invocations, image input, usage/cost, cancellation; capabilities negotiated rather than assumed.
- ExecutionBudget: iteration, tool, wall-time, model tokens/cost ceilings configurable by profile.

Source integrations to audit: https://github.com/gaoypeng/3dcodeverse (Apache-2.0 code), https://github.com/dcc-mcp/dcc-mcp-blender (MIT source), https://github.com/dcc-mcp/dcc-mcp-core (MIT source). License of particular extension packages, datasets/models and assets must be checked separately. Choose pinned revisions only after integration smoke.

## Vertical milestone contract

Every milestone must have (a) one user-visible story, (b) a fast executable demo, (c) saved output, (d) automated acceptance and failure case, (e) docs explaining how to reproduce, and (f) explicit remaining gaps. The commands below are **planned CLI contracts, not implemented commands**. Use a single small golden fixture (simple table: top + four legs, dimensions, stable object names, neutral material) throughout early slices.

| Slice | Immediately tangible result | Planned user demo | Gate / definition of done | Depends | State |
| --- | --- | --- | --- | --- | --- |
| G0 — Boot + first render | A real table .blend and preview.png without AI | geometry demo deterministic-table | Fresh Mac runs doctor, renders PNG, saves/open-checks .blend, validates 5 named objects/bounds and cleans owned processes; template is specialized | — | READY |
| G1 — First closed-AI creation | A prompt creates a chair/table scene and image | geometry run --profile cloud --mode code --prompt-file examples/table.txt | Model script runs in Blender, output PNG/.blend/manifest saved, errors bounded and actionable; no MCP needed yet | G0 | BLOCKED |
| G2 — See and correct | Four views + geometry report + visible first/last comparison | geometry run --profile cloud --feedback geometric-visual | Script/runtime, dimensions, object count and contact gates; judge consumes only spec/renders/measurements; repair retry bounded; store every round, including failure | G1 | BLOCKED |
| G3 — Edit with MCP | User asks to recolor or raise only one object, and sees before/after | geometry edit <run> --prompt "Change the tabletop to blue" | dcc tool discovery+invocation, state inspect/edit/save, no unintended object transform, real Blender round-trip and typed error handling | G1 (G2 can progress in parallel) | BLOCKED |
| G4 — Hybrid + undo | Original and edited scenes coexist; rollback recovers original | geometry revisions <run>; geometry rollback <run> <revision> | Stable IDs, journal/checkpoint/replay; new process can regenerate edited revision; undo returns original bounds/material; source-vs-session divergence detected | G2,G3 | BLOCKED |
| G5 — Compare agents | Human-readable gallery/report for identical prompts across GPT/Claude/Gemini and 3 strategies | geometry benchmark --suite fixtures/core --profiles cloud | Same fixed tasks/budgets, pinned tool versions, success/geometry/visual/latency/cost; blind sampled assessment; no ungrounded single overall score | G4 | BLOCKED |
| G6 — Local generator | First open-weight model produces the same editable table on the Mac | geometry run --profile local --mode code --prompt-file examples/table.txt | Local endpoint/runtime, deterministic geometry gates, latency and peak memory logged; works without closed API keys; honest quality comparison with G5 | G1 (parallel with G3–G5) | BLOCKED |
| G7 — Fully local loop | Prompt → local LLM → local VLM judge → repaired render, entirely offline | geometry run --profile local --feedback geometric-visual --offline | Controlled no-egress E2E with cached weights/assets, no vendor API calls, graceful VLM unavailable path, bounded resource usage and equivalent manifest | G2,G4,G6 | BLOCKED |
| G8 — Practical rendering workflow | User picks scene/revision, chooses preview vs final Cycles render, inspects gallery | geometry render <run> --quality final; geometry gallery <run> | Usable images, named camera/light/material controls, exports, consistent project re-open, gallery navigation and UI evidence; compare preview/final cost | G4,G5 (local path remains optional until G7) | BLOCKED |

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
5. Review one image and the source/manifest in the milestone PR. **First user-visible payoff: a real .blend and PNG from a clean setup.**

**G0 acceptance evidence (to collect, not already present):** exact SHA, Blender/python versions, reproducible CLI transcript, generated preview PNG, file-open validation, focused tests and automated integration preflight. If macOS rendering cannot be automated yet, label missing hardware verification and do not call it release-ready.

## Cross-cutting test and decision protocol

- Each later slice retains prior goldens (create → save → reopen → edit → reopen → compare); immutable finished revisions and deterministic scene measurements gate regressions.
- Suggested fixed starter suite: box/cylinder, 4-leg table, simple chair, two-object scene, tabletop color edit, leg-height edit, intentional malformed script, intentional disconnected leg. Expand to benchmark datasets only after runner accuracy is proven.
- First A/B: code-first no feedback vs geometric feedback vs geometric+visual; then code-first vs typed MCP vs hybrid. Report cost per **valid** scene, pass rate, wall time, tool failures, revision preservation and visual rubric separately.
- Pin prompt/model/temperature/tool+Blender versions, camera seeds and sample budgets; preserve runs even when failed. Visual judge scores are probabilistic; reference renders and manual spot checks remain necessary.
- Promotion thresholds are chosen from baseline evidence, not invented ahead of measurement. Treat Mac 36-GB-class memory as an experimental budget, not a guarantee that all local VLMs coexist; load/unload roles serially where necessary.
- Release checks: unit/contract + integration Blender run + artifact reopen + focused E2E + security/no-egress for local profile + cleanup; preserve photos/video for material gallery UI critical journeys when introduced.

## Resume checkpoint

- Source: main 5710a83aa573e91b1c6285eda0bace43e43720d8, planning branch plan/incremental-geometry-harness.
- Confirmed: repository currently contains repo-template-sw distribution and copied adopter templates, not a specialized Geometry Harness app; only main branch existed at planning time.
- Confirmed upstream: 3DCodeVerse includes code-first agentic pipeline; dcc-mcp-blender and dcc-mcp-core expose typed Blender MCP tooling; integration, macOS compatibility and performance **not yet tested in this repository**.
- Unresolved: exact upstream SHAs/version matrix; first closed vendor/model; chosen local model/VLM; precise resource and quality budgets. None blocks G0.
- Next: implement G0 only, produce and inspect the very first deterministic PNG and .blend, then proceed to G1.

## Durable destinations and lifecycle

At each integration: docs/product.md for settled mission/outcomes, docs/architecture.md for module ownership/integration decisions, docs/features/ for shipped behavior, docs/current-state.md for integrated/blocked/next. Architecture decisions on code-first/MCP state or licensing go in ADR only when settled. Keep this workstream as the sole active execution plan, update states/checkpoint on meaningful handoffs; archive/delete it after roadmap completion once durable knowledge is transferred. Git history records completed work.
