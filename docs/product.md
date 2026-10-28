# 3D Rendering LLM — product intent

Status: evolving product intent; G0 deterministic and a narrow G1 safe-AST-to-Blender E2E are implemented, but full product, repair/local/CAD are not. This is the intended durable product direction, not a statement of current capabilities.

## Mission
Enable developers and makers to turn natural-language requests into inspectable, editable and verifiable 3D assets, initially using commercial AI APIs to establish quality baselines and ultimately using open-weight LLMs/VLMs with entirely local inference on Apple Silicon.

## Primary users
Primary: developers/makers generating and incrementally editing safe, verifiable Blender assets on Apple Silicon. Secondary **discovery track**, not yet an adopted enterprise product: studios needing private structured planimetry 2D→3D and specific measurable changes via a domain adapter. Customer/project/document management and full CAD/BIM certification are not an MVP goal.

## Core job and value
Prompt -> valid Blender scene -> PNG preview -> inspectable .blend and GLB -> targeted edits -> measured feedback. Every development slice must unlock a real, repeatable user result. Compare code generation, typed tools and hybrid editing using the same tasks.

## Differentiation
Local-first architecture and a verifiable no-egress goal; model-independent typed agent/tool contracts; **deterministic validation before costly vision/reasoning**, scoped bounded repair and checkpoint/rollback; **measured per-stage critical path and cost per accepted artifact**; separate generic 3D and architecture domain journeys. These are product goals; implementation state lives in current-state.md.

## Non-goals for MVP
Photorealistic full scenes, animation, large worlds, CAD certification, 2D editing, image-to-mesh neural generation, model training, hosted account infrastructure and a complex graphical editor. Evaluate additions only when experiments show value.

## Product principles
1. Visible deliverable at every milestone (image, native file, repeatable command).
2. Source/edit history and reproducibility over a one-off attractive screenshot.
3. Geometric correctness verified in software; subjective appearance scored separately.
4. Cloud optional for research only; the finished workflow can run offline on compatible hardware.
5. Simple CLI and lightweight visual gallery before broad UI investment.
6. Bounded memory, cost, process lifetime and generated-code permissions.
7. Benchmark-driven agile delivery: every sprint ends in real, human-inspectable Blender E2E plus negative case, and compares frozen input tasks, geometry, visual quality, editing preservation, latency and cost against the accepted baseline.
8. Start with constrained code-first Blender; trial structured plans, generated 2D references, multiview, bounded scoped repair and MCP as isolated measured hypotheses. No obligatory CADCraft/2D-first step for generic generation.
9. Prefer deterministic tools over LLM turns when the answer is objective and authorized; preserve independence of provider and trusted geometry builder.
10. Structured DXF import is a separate opt-in domain vertical; measure against deterministic builder, not an image-only benchmark.
11. Partner/customer files stay private and are not shipped in public tests, docs or artifacts.

## Quality attributes
| Attribute | Product promise | Engineering owner |
| --- | --- | --- |
| Privacy | Offline profile has no remote inference, uploads or network fallbacks | provider/runtime/offline tests |
| Reproducibility | Preserve source, edits, Blender/tool versions and artifact lineage | revision/run manifest |
| Reliability | Errors, timeouts and failed edits do not destroy the last valid scene | execution/recovery tests |
| Performance/cost | Show time, token cost and peak memory; benchmark regressions | evaluation/runtime |
| Portability | Begin on macOS ARM64 while isolating OS/Blender-specific dependencies | Blender adapter/CI |

## Success signals
- **Acceptance:** fresh setup generates, opens and measures a known .blend, later validates AI-generated/editable results.
- **Outcome:** user can create a scene then request a local edit without manually rebuilding everything.
- **Impact (only after real use):** share of task attempts resulting in accepted scenes, edit success and latency/cost vs simpler tools.

Active staged implementation: [Geometry Harness workstream](workstreams/geometry-harness.md). Proposed architecture: [architecture.md](architecture.md).