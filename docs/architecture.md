# Geometry Harness — proposed architecture

Status: **target design, not as-built** (2026-10-26). Implement only the smallest subset consumed by the current vertical milestone. Product intent lives in product.md; milestone execution and dependencies live in workstreams/geometry-harness.md.

## Components and data path

Prompt/spec -> ProviderAdapter (cloud agent/LLM or local open-weight LLM)
-> AgentOrchestrator -> ExecutionStrategy (code-first / tool-first / hybrid)
-> BlenderSession + renderer -> DeterministicValidator -> optional VisualJudge
-> RevisionStore + RunManifest -> CLI, PNG gallery and export.

**Code-first:** generate reproducible Blender Python in an isolated workspace, run a bounded Blender subprocess, store source and native .blend, then preview and validate. The generated script and declared assets are authoritative; renders and GLB are derived.

**Tool-first:** connect to a Blender session via dcc-mcp-blender + dcc-mcp-core, discover/describe/call whitelisted tools. A typed operation journal records stable target IDs, preconditions, revisions and postconditions. Blender state is never considered replayable just because a tool call succeeded.

**Hybrid:** initialize from code-first source/snapshot then apply verified MCP edits. Persist starting scene + operation journal + immutable checkpoints. Detect out-of-band mutations and compare replayed transforms, object identities and material state with the accepted revision. If replay fails, retain native checkpoint as recoverable rather than claiming perfect source reconstruction.

## Reuse strategy and legal boundaries

- 3DCodeVerse (https://github.com/gaoypeng/3dcodeverse): study/adapt orchestration, code generation, multiview, deterministic checks, visual judge, repair and run telemetry. Take the *smallest viable slice* and pin tested version. Source code Apache-2.0; published datasets/assets may use different licences.
- dcc-mcp-blender (https://github.com/dcc-mcp/dcc-mcp-blender): integrate through a pinned MCP adapter for typed Blender operations, scene inspection and rendering.
- dcc-mcp-core (https://github.com/dcc-mcp/dcc-mcp-core): reuse discovery, description, routing and typed-call contracts before inventing a new registry.
- Track upstream SHA, notices, modifications, extension build/Blender GPL implications, dataset/model/texture rights in an inventory before distributing binaries. Avoid vendor lock-in and whole-tree copy/paste.
- No hard dependency on a hosted AI account in core Blender/runtime/test modules.

## Interfaces to grow on demand

- ProviderAdapter: message formats, structured output, tool calls, image input and usage records. Query capabilities instead of assuming that every local model supports tool calling or vision.
- SceneArtifact: run ID, source SHA, Blender/tool versions, prompt/settings hashes, native scene location, renders, exports and provenance.
- ToolAction: action ID, scene revision, target persistent object ID, typed parameters, pre/postconditions, result/error, idempotency token.
- ValidationReport: execution, geometry, spatial and visual findings with status PASS / FAIL / UNKNOWN and direct evidence references.
- ExecutionBudget: max wall-clock, model tokens, spend, repair iterations, tool calls, assets/render resolution, memory.
- Execution adapters own cleanup across success/failure/interrupt. The agent may not write outside the owned run directory.

## Rendering and validation

Every milestone's real Blender/model/MCP E2E must publish a reviewable PNG contact sheet, offline HTML gallery, manifest, objective assertions, native scene and negative-path evidence; see [showcase and evidence contract](features/showcase-evidence.md). Gallery/report generation is a G0 concern reused by all later vertical slices, not a final-phase add-on.

Blender preview (fast neutral materials and fixed orthographic/isometric cameras) is the primary early feedback surface. Production quality renders with Cycles and richer materials are a *later option*, not the first dependency.

Order: syntax/runtime -> Blender build/load -> deterministic object geometry (dimensions, expected parts, gaps/contacts when specified) -> cheap multi-view preview -> optional VLM rubric -> bounded repair. Keep subjective appearance separate from geometric correctness. VLM receives spec, render and measurements but not the generator's private reasoning.

Initial fixture: tabletop, four legs and stable IDs; fixed dimensions and tolerances recorded in test data. Later fixtures: chair, multiple objects, material-only edit, geometry-only edit, malformed script, disconnected component. Real task comparisons use same models/prompts/budgets and store failure cases too.

## Runtime profiles and offline acceptance

The first experiments may use GPT/Claude/Gemini (and their agent CLIs) with explicit credentials and usage accounting. Local adapters must work with open-weight endpoints, e.g. local OpenAI-compatible inference, Korgis, llama.cpp or MLX. Do not assume that a chat-completions API automatically implements a coding agent; tool dispatch and recovery remain harness-owned.

Full-local release means *all* planning, code generation, visual interpretation and repair run with local weights; network egress disabled/monitored; cached models and assets; no hidden remote VLM or image API. On memory-limited Apple Silicon hardware, use serial model load/unload if concurrent LLM + VLM is impractical and report peak memory. If local judgement is unavailable, return UNKNOWN, not a synthetic PASS.

## Project/runtime structure after adoption

- src/geometry_harness/agents, providers, execution, integrations/dcc, blender, validation, rendering, revisions, evaluation;
- config/profiles and typed tool catalog; examples/ and tests/fixtures;
- benchmarks for small controlled A/B suites, with large datasets external;
- runs/ generated files gitignored and pruned by documented policy;
- future frontend/ or static gallery only when a tangible visual review need is confirmed.

Start with Python/uv CLI plus a headless Blender executable. Keep the Blender embedded Python runtime separate from orchestration dependencies. Prefer subprocess/MCP boundaries. Extend to React/Three.js only after a compact gallery has demonstrated the necessary interaction.

## Delivery constraints

- Do not promote a run solely because Blender returned exit code zero: reopening artifacts, geometry and metadata checks are separate gates.
- Never replace the last valid checkpoint with unvalidated edits; roll back on failure.
- Explicit owner/contract for each component; adapters isolate upstream updates.
- Secrets scrubbed; network/cost/timeouts explicit; source/prompt hashes and build IDs persisted.
- CI progression: cheap static + unit; integration runs real Blender headless; quality/E2E on appropriate macOS runners and reference images; gated release validates residual hardware and offline claims.
- These are design decisions to validate progressively, not claims that the repository already implements them.