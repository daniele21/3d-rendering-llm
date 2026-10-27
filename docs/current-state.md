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
- Actual `local-mac-mini-3` ran the G0 workflow. Source checkout succeeded, but Blender was not detected, and the old GitHub artifact upload hit quota. The central workflow is being migrated to a private GCS bucket; cloud IAM/bucket provisioning and a successful real G0 E2E are still unverified.
- Upstream integration and inference remain untested; they do not block deterministic G0.

## Next

Provision the private GCS bucket/WIF and repo variables via `local-runner-infra/scripts/bootstrap_geometry_gcs.sh` with the selected GCP project; install Blender or set `BLENDER_BIN` on `local-mac-mini-3`; request reviewed G0 SHA on `geometry-mac-mini.yml`, inspect `.blend`/PNG and GCS inventory. Existing shared labels are enough to queue (wrong-Mac attempts fail in the runner-name guard); no custom label is required. Do not mark DONE until tests and private GCS upload are proven.