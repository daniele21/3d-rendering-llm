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
- The Mac mini CI source script has been added to the planning branch; the central runner allowlist and artifact publishing require reviewed deployment in `local-runner-infra`. No Mac job or Blender E2E has been verified yet.
- Upstream integration and inference remain untested; they do not block deterministic G0.

## Next

After central allowlist onboarding and trusted-SHA CI smoke, implement G0 with a real Mac mini showcase bundle; verify native Blender, preview PNG and saved scene, then promote G1. Do not mark any milestone DONE based only on this plan.