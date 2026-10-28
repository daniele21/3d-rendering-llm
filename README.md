# Geometry Harness (3d-rendering-llm)

A Blender-first, model-independent 3D generation and verification harness. The target is a fully local **open-weight** LLM/VLM workflow; closed GPT/Claude/Gemini APIs are planned for early experiments and baselines. **G0 is deliberately deterministic and makes no AI calls.**

## G0: first tangible result

Requires macOS Apple Silicon (CI target), Python 3.11+ and Blender 4.5+ installed as `blender` or `/Applications/Blender.app/Contents/MacOS/Blender`. Alternatively set `BLENDER_BIN` to the Blender executable. Initial implementation uses only Python's standard library outside Blender; no API key is needed.

```bash
git clone https://github.com/daniele21/3d-rendering-llm
cd 3d-rendering-llm
export PYTHONPATH="$PWD/src"
python3 -m geometry_harness doctor
python3 -m geometry_harness showcase --milestone G0 --output runs/my-first-table
python3 -m geometry_harness showcase validate runs/my-first-table
open runs/my-first-table/index.html
open runs/my-first-table/artifacts/scene.blend
```

This *real* Blender execution creates an editable `.blend`, `preview.png`, `contact-sheet.png`, offline `index.html`, `geometry.json`, `assertions.json`, generator source and hashed `showcase-manifest.json`. A separate Blender process reopens the saved scene to verify five named mesh objects, dimensions, locations, floor and tabletop contacts. The negative E2E scenario corrupts a PNG and verifies checksum rejection.

The output folder must not already contain files (runs are immutable). Generated outputs and large model/data caches stay out of Git.

## Mac mini CI

Shared macOS runners belong to `daniele21/local-runner-infra`; **G0 must be assigned to a Mac mini**, not generic `local-mac-1`. The dedicated central `geometry-mac-mini.yml` requires the verified `geometry-mac-mini` label plus `macOS,ARM64,local-shared`, and validates the `local-mac-mini-*` runner name. The reviewed operator runs `bash scripts/request_geometry_ci.sh <trusted-SHA>` in the central repo once that label exists. The job publishes `ci-artifacts/showcase/` to a **private Google Cloud Storage bucket** through short-lived GitHub OIDC credentials; GitHub Actions artifact quota is not used. The central GCS setup/permissions runbook is in `local-runner-infra/docs/geometry-gcs-artifacts.md`. Hosted template-health CI remains separate. Source status reporting requires `CENTRAL_SOURCE_TOKEN` permission for this repo.

## Planned next steps

G1 closed-agent text-to-Blender; G2 multiview validation/repair; G3 typed MCP editing with dcc-mcp-blender; G4 hybrid replay and rollback; G5 benchmark galleries; G6 open-weight local generation; G7 offline local VLM repair; G8 final Cycles quality and gallery.

- [Current state](docs/current-state.md)
- [Incremental workstream](docs/workstreams/geometry-harness.md)
- [Visual E2E contract](docs/features/showcase-evidence.md)
- [Proposed architecture](docs/architecture.md)

The historic `template/`, `STANDARD.md` and other `repo-template-sw` artifacts are inherited from initial repository bootstrap; the G0 feature specializes application entrypoints first. Their retirement is a separate reviewed cleanup, not a requirement to inspect the first Blender output.
