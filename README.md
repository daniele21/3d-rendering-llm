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

Shared macOS self-hosted runners belong to `daniele21/local-runner-infra`; **do not add self-hosted runs-on directly in this source repo**. Only reviewed, exact-SHA execution through the central private repo can run `.github/ci/local-test.sh`. The central job uploads `ci-artifacts/showcase/` as Actions evidence. Hosted template-health CI is retained separately during initial project specialization. This runner does not automatically have permissions to post source statuses unless `CENTRAL_SOURCE_TOKEN` is authorized for this repository.

## Planned next steps

G1 closed-agent text-to-Blender; G2 multiview validation/repair; G3 typed MCP editing with dcc-mcp-blender; G4 hybrid replay and rollback; G5 benchmark galleries; G6 open-weight local generation; G7 offline local VLM repair; G8 final Cycles quality and gallery.

- [Current state](docs/current-state.md)
- [Incremental workstream](docs/workstreams/geometry-harness.md)
- [Visual E2E contract](docs/features/showcase-evidence.md)
- [Proposed architecture](docs/architecture.md)

The historic `template/`, `STANDARD.md` and other `repo-template-sw` artifacts are inherited from initial repository bootstrap; the G0 feature specializes application entrypoints first. Their retirement is a separate reviewed cleanup, not a requirement to inspect the first Blender output.
