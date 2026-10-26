# Current state — Geometry Harness

Status: G0 implementation candidate on feature/g0-blender-showcase; its Blender rendering has not yet been verified on Mac. Main is the integrated docs baseline.

## Current milestone

G0 — Adopt the template as this project and deliver a deterministic Blender table (.blend + preview.png + manifest) on macOS ARM64, without any model or API.

## Active workstreams

| Workstream | Current executable slice | State | Blocker |
| --- | --- | --- | --- |
| [Geometry Harness](workstreams/geometry-harness.md) | G0 | ACTIVE | Target Mac E2E and artifact inspection pending |

## Repository blockers

- Product app entrypoints and root README/AGENTS are specialized on feature/g0-blender-showcase; some legacy template distribution files remain for later cleanup.
- The Mac mini CI source script has been added to the planning branch; the central runner allowlist and artifact publishing require reviewed deployment in `local-runner-infra`. No Mac job or Blender E2E has been verified yet.
- Upstream integration and inference remain untested; they do not block deterministic G0.

## Next

Run reviewed feature/g0-blender-showcase SHA through central Mac mini CI; inspect full showcase, resolve genuine runtime failures, then promote G1. The status token currently lacks source write permission (HTTP 403). Do not mark any milestone DONE based only on this plan.