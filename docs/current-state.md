# Current state — Geometry Harness

Status: planning only. The repository currently contains repo-template-sw distribution files, not a running 3D application.

## Current milestone

G0 — Adopt the template as this project and deliver a deterministic Blender table (.blend + preview.png + manifest) on macOS ARM64, without any model or API.

## Active workstreams

| Workstream | Current executable slice | State | Blocker |
| --- | --- | --- | --- |
| [Geometry Harness](workstreams/geometry-harness.md) | G0 | READY | None known; real Blender/macOS execution not yet verified |

## Repository blockers

- Product repo specialization not done; current root AGENTS.md/README.md still describe repo-template-sw.
- Upstream integration, Blender runtime and inference have not been tested in this repository. These do not block deterministic G0.

## Next

Implement G0 on a feature branch; verify native Blender build, preview image and saved scene on the target Mac, then update integrated docs and promote G1. Do not mark any milestone DONE based only on this plan.