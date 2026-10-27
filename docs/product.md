# 3D Rendering LLM — product intent

Status: planned; this repository has not yet implemented the product. This is the intended durable product direction, not a statement of current capabilities.

## Mission
Enable developers and makers to turn natural-language requests into inspectable, editable and verifiable 3D assets, initially using commercial AI APIs to establish quality baselines and ultimately using open-weight LLMs/VLMs with entirely local inference on Apple Silicon.

## Primary users
Developers experimenting with AI-generated Blender assets and makers who want to create, inspect, render and incrementally revise small 3D objects without writing every Blender script manually.

## Core job and value
Prompt -> valid Blender scene -> PNG preview -> inspectable .blend and GLB -> targeted edits -> measured feedback. Every development slice must unlock a real, repeatable user result. Compare code generation, typed tools and hybrid editing using the same tasks.

## Differentiation
Local-first architecture and an offline-ready trust boundary; model-independent agent/tool contracts; deterministic geometry checks plus optional visual judgement; reproducible scene revisions; honest quality/cost/latency benchmarks.

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
8. Start with code-first Blender; trial structured plans, generated 2D references, multiview feedback and MCP only as isolated measured hypotheses. No obligatory CADCraft/2D-first step.

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