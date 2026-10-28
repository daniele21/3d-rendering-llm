# Geometry Harness (3d-rendering-llm)

A Blender-first, model-independent 3D generation and verification harness. The target is a fully local **open-weight** LLM/VLM workflow; closed API models form the first measured baseline, followed by open-weight local inference. **G0 makes zero AI calls; the initial G1 GPT-6.1 Sol live smoke produced a native Blender scene with a private per-call cost ledger.**

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

## G1: first cost-audited AI-to-Blender smoke (restricted)

The first GPT-6.1 Sol run generated a four-leg table as Blender bpy code on the Mac mini. The code was **never executed as Python**: a strict AST parser accepts only bounded literal cubes, cylinders, UV spheres and named transforms (dimensions, scale, location). An audited in-repo Blender builder converts the accepted data to an editable native scene; a fresh Blender process reopens and verifies it. Unsupported Python fails closed. This proves a **narrow 5-part internal demo**, NOT general procedural modeling or an official 3DCodeBench result.

- [First live AI-generated .blend and PNG + private GCS proof](https://github.com/daniele21/local-runner-infra/actions/runs/40669515643): PASS, model-token estimate **USD 0.003666000**
- [First single-call cost/usage probe](https://github.com/daniele21/local-runner-infra/actions/runs/40668374405): PASS, **USD 0.014708000**
- Combined **two live model requests: USD 0.018374000 estimated token cost**, not an OpenAI invoice or GCS/compute bill.
- Per-call UTC/model/token/cached-read/cache-write/output/reasoning breakdown and pricing snapshot stored privately on GCS; no secrets or user prompts in the accounting ledger.
- Local non-billed test: `PYTHONPATH=src python3 -m geometry_harness.g1 --fixture tests/fixtures/g1_safe_table.py --output runs/g1-fixture` (requires Blender).

G1 is **not complete** against the sprint acceptance criteria until a pinned 3DCodeBench dataset/cohort, independent scoring and visual inspection are done.

## Mac mini CI

Shared macOS runners belong to `daniele21/local-runner-infra`; **G0 must be assigned to a Mac mini**, not generic `local-mac-1`. The dedicated central `geometry-mac-mini.yml` uses the existing `[self-hosted, macOS, ARM64, local-shared]` runners, asserts `local-mac-mini-*` runner identity, and checks out a reviewed source SHA. G0 is triggered by an explicit trusted request; G1 paid experiments require a separate approved, one-call request and are never triggered by routine source PRs. The job publishes `ci-artifacts/showcase/` to a **private Google Cloud Storage bucket** through short-lived GitHub OIDC credentials; GitHub Actions artifact quota is not used. The central GCS setup/permissions runbook is in `local-runner-infra/docs/geometry-gcs-artifacts.md`. Hosted template-health CI remains separate. Source status reporting requires `CENTRAL_SOURCE_TOKEN` permission for this repo.

## Next steps — performance-aware plan (2026-10-28)

The single [active roadmap](docs/workstreams/geometry-harness.md) prioritizes **measured latency tracing, deterministic geometry validation, typed scoped repair and rollback, composite-tool A/B, local open-weight execution**, and a separate **structured DXF→3D architecture vertical**. All are **planned**, not currently accepted production features.

The six-task 3DCodeBench freeze and pricing code on main do **not** establish an official quality result until actual independent-scored E2E, source provenance, and Blender compatibility are verified. Keep the safe AST→audited Blender builder (no arbitrary model Python), approved opt-in paid tests, and truthful FAIL/UNKNOWN evidence gates.

Feature contracts: [tracing](docs/features/agent-performance.md) · [repair](docs/features/repair-policy.md) · [efficiency A/B](docs/features/harness-efficiency-experiments.md) · [Architecture DXF](docs/features/architecture-2d-to-3d.md) · [external integration](docs/features/external-integration-contract.md).

- [Current state](docs/current-state.md)
- [Incremental workstream](docs/workstreams/geometry-harness.md)
- [Visual E2E contract](docs/features/showcase-evidence.md)
- [Proposed architecture](docs/architecture.md)

The historic `template/`, `STANDARD.md` and other `repo-template-sw` artifacts are inherited from initial repository bootstrap; the G0 feature specializes application entrypoints first. Their retirement is a separate reviewed cleanup, not a requirement to inspect the first Blender output.
