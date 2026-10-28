# Milestone showcase and evidence contract

Status: **enforced evidence contract**. G0 real Blender+GCS gates PASS; G1 first narrow internal AI-to-native-Blender E2E PASS on 2026-10-28 [run 40669515643](https://github.com/daniele21/local-runner-infra/actions/runs/40669515643). Real 3DCodeBench scoring and visual review still pending; G2–G8 remain planned.
Owner: showcase/test infrastructure and milestone implementation owners.
Read when: implementing a G0–G8 acceptance test, CI artifact publication or visual review.
Execution ordering and current states remain in [the active workstream](../workstreams/geometry-harness.md).

## Why it exists

A passing unit test alone does not show the result of a 3D project. **Every milestone must have a real end-to-end (E2E) showcase test that generates and publishes a human-inspectable deliverable**, plus objective assertions and an intentionally failing/negative scenario. In the PR and CI artifacts a reviewer must be able to see what was generated, open the .blend where relevant, inspect change evidence, and distinguish a real model run from a replay or mocked test.

Implement the minimal common evidence writer in G0, then **extend the same format** rather than inventing new report and storage conventions for later phases.

## Revised sprint application (2026-10-27)

The [active benchmark-driven plan](../workstreams/geometry-harness.md) reorders delivery, **not** evidence rigor:

- G0/S0 still requires deterministic **real** Blender evidence and verified private GCS upload.
- G1/S1 becomes the first **real AI + 3DCodeBench smoke task** showcase; seed a frozen baseline plus source/model/tool identities.
- G5 benchmark tooling starts **in G1/S1** (6 smoke), expands in S2 (24 core) and releases (212 full) instead of waiting for G4. Every benchmark includes failures and cost/latency.
- G2/S2–S4 adds actual orthographic + isometric views, objective geometry gates, blinded visual judge and bounded repair, each with negative-path evidence.
- S3 planner and S5 generated-2D ablations are **separate A/B E2E acceptance slices** even though they are optional strategies, each producing native scene, image, manifest, paired report and failure path. No CADCraft dependency; 2D reference is measured against direct Blender.
- Editing, local model and final Cycles retain G3–G8 real-E2E obligations; the gallery remains available from G0.

**Detailed evaluation spec:** [benchmark-protocol.md](benchmark-protocol.md). Preserve the original G0–G8 test matrix below as per-capability mandatory gates; the sprint mapping dictates when they first become executable. Never use fake test PNGs, synthetic model calls or unscored/UNKNOWN outcomes as proof of a quality improvement.

## Required output of every milestone test

For a successful real showcase test, write to an ignored, unique `runs/<run-id>/showcase/` folder:

```text
showcase/
  index.html                  # offline static gallery; relative links only
  contact-sheet.png           # quick visual proof, even if only one view
  showcase-manifest.json      # identity, mode, environment, checks, artifact hashes
  assertions.json             # machine-readable PASS / FAIL / UNKNOWN per check
  logs/                       # bounded, scrubbed command and process logs
  artifacts/                  # native .blend, generated script, GLB, views as applicable
```

- `index.html` includes task/prompt (scrub secrets), milestone, source commit, model+provider/runtime, real-vs-replay-vs-mock flag, Blender version, images, native file download links, dimensions/checks, elapsed time, costs where relevant, and known gaps. A static HTML gallery is enough until G8.
- `contact-sheet.png` must show actual generated screenshots/renders with view captions. **Never substitute illustrative or stock images**. For editing/revision phases, show before/after/rollback in the same frame; for benchmarking, show comparable outcomes alongside failures.
- `showcase-manifest.json` records `milestone`, `run_id`, `created_at_utc`, `source_sha`, `blender_version`, `platform`, `mode` (real/cloud/local/replay/mock: explicitly typed), `profile`, `status`, `artifacts` (relative path, bytes, SHA-256, media type, role), `checks`, `duration_seconds`, `cost` (or unknown) and optional memory usage. Never include credentials, private prompt payloads, or absolute home paths.
- Require a usable image, complete manifest and underlying native geometry/source appropriate to the milestone; no empty artifact counts or screenshot-only success. Check that declared artifacts actually exist, have nonzero size, matching hashes, are within the owned bundle and can be opened/parsed. For native Blender scenes, reopen with real Blender and re-run semantic checks.
- Every failed attempt still uploads sanitized diagnostics and available render/scene evidence, with **status FAIL or UNKNOWN**, not a misleading successful gallery. Missing critical screenshots or manifests is `EVIDENCE_INCOMPLETE`, never a reason to downgrade the test.
- A replay or mock can validate orchestration cheaply but **cannot satisfy a real Blender/MCP/model milestone**. The manifest and UI must state its evidence tier unmistakably.

### Planned commands and ownership

At G0 use implemented `python3 -m geometry_harness showcase --milestone G0 --output ci-artifacts/showcase/g0`, `python3 -m geometry_harness showcase validate PATH`, and fixture-driven E2E tests. The commands exist and G0 passed the dedicated Mac mini real Blender/GCS integration on run 40664644253. Final human visual review of the private render remains part of the full acceptance ritual. Each later milestone adds its case to the same runner. `geometry showcase --milestone Gx --open` should build/open the static gallery and optionally open the native .blend in Blender; no web hosting required.

Expected test hierarchy: `tests/unit/` for manifest/writer/hashes, `tests/integration/` for Blender and MCP contracts, and `tests/e2e/test_showcase_gX.py` for the real representative user path. Add a negative case per milestone (same test file or companion) proving a distinct failure signal.

## Test-to-deliverable matrix

All test paths below are **planned** and become real when that milestone is implemented. Samples and expected assertions are examples that must be pinned in actual fixtures, not pre-approved results.

| Milestone / planned E2E | Task and demonstrable outputs | Automatic assertions + negative case |
| --- | --- | --- |
| **G0** `test_showcase_g0.py` | Create four-leg table deterministically; `artifacts/scene.blend`, `artifacts/preview.png`, `contact-sheet.png`, manifest | Blender opens saved file; five stable named objects, known dimensions/contacts, valid PNG and no leaked processes. Negative: missing Blender binary or forced render timeout reports precise failure and cleans up. |
| **G1** `test_showcase_g1.py` (first internal narrow safe-AST smoke passed; official 3DCodeBench pending) | Prompt creates table/chair with real closed AI; generated `artifacts/generate.py`, `scene.blend`, `preview.png`, prompt and usage metadata | Actual provider call recorded; produced script executes and saved scene reopens; requested parts present. Negative: invalid script/provider rejection becomes a bounded FAIL with source and logs, not empty output. |
| **G2** `test_showcase_g2.py` | Deliberately flawed geometry → multiview feedback/retry; `artifacts/views/{front,side,top,iso}.png`, `artifacts/before-after.png`, `artifacts/rounds.json`, checks and judge scores | Checks identify injected disconnected leg; initial and repaired revisions separately retained; final constraints checked, attempts bounded; report repair success/failure without fabricating it. Negative: exhausted retry budget returns FAIL, keeping last valid evidence. |
| **G3** `test_showcase_g3.py` | Change only tabletop material using live dcc MCP; `artifacts/before.png`, `after.png`, `tool-actions.json`, edited `scene.blend` | Confirm MCP tool invocation, targeted material change, all unrelated transforms and names unchanged, saved scene reopens. Negative: unknown object/tool timeout makes no destructive partial commit. |
| **G4** `test_showcase_g4.py` | Increase table width → replay in fresh Blender process → rollback; `artifacts/{original,edited,rolledback}.png`, `revisions.json`, `replay-diff.json`, native checkpoints | Replay produces semantically equivalent object geometry/materials; rollback restores baseline measured properties (do not require byte-identical .blend). Negative: corrupted journal/checkpoint triggers recovery without losing accepted revision. |
| **G5** `test_showcase_g5.py` | Fixed benchmark prompts × providers × code/typed/hybrid strategies; `artifacts/matrix.png`, `benchmark.json`, `comparison.html`, representative GLBs | Correct attribution per provider/mode, identical fixtures/budgets, errors included as visible cells, score/latency/cost-per-valid computed from actual runs. Negative: missing run/config mismatch is UNKNOWN/invalid rather than assigned a score. Expensive matrix is opt-in, not per-commit. |
| **G6** `test_showcase_g6.py` | A real open-weight local model creates the same basic table; `artifacts/local-preview.png`, `scene.blend`, `runtime.json`, baseline comparison | Inference endpoint is local, no closed API keys; real Blender geometry check, model identity, wall time and peak memory reported. Negative: unavailable model fails clearly without automatic cloud fallback. |
| **G7** `test_showcase_g7.py` | Offline local LLM+VLM → multiview feedback and repair; `artifacts/offline-sequence.png`, `network-evidence.json`, `rounds.json`, `scene.blend` | Enforce/verify network denial or equivalent trustworthy no-egress proof; all AI decisions local; final scene checks and bounded memory/attempts. Negative: remote endpoint configured or VLM unavailable fails closed or explicitly UNKNOWN, never a silent remote call. |
| **G8** `test_showcase_g8.py` | Same scene rendered preview vs Cycles final, with a browsable gallery; `artifacts/{preview,final}.png`, `render-settings.json`, `scene.blend` and gallery screenshots/video when UI-critical | Both images come from same revision, distinct render settings, scene reopens, links/gallery navigation work; quality/cost delta reported. Negative: final render failure retains preview and reports incomplete result. |

## Validation layers and CI publication

- **Fast checks (every touched change):** schemas, file/manifest integrity, deterministic geometry helpers, mocked provider protocol and small local fixtures; no remote model billing.
- **Integration/PR-ready:** execute the source-owned `.github/ci/local-test.sh` from an exact trusted SHA via `daniele21/local-runner-infra` on `[self-hosted, macOS, ARM64, local-shared]`. These runners are *central-repository scoped*; do not set source `runs-on: self-hosted`. Confirm real Blender E2E for changed milestone and affected prior goldens, with source SHA and environment.
- **Cloud experiments (G1/G2/G5):** workflow_dispatch/manual or explicitly authorized cost-bounded CI with provider secrets gated and unavailable to untrusted change branches. Not part of every push; no passing claim from a mocked provider.
- **Local AI (G6/G7):** dedicated appropriately provisioned self-hosted Mac with locally cached models. Record peak memory, inference duration and verified offline evidence; do not treat ordinary hosted CPU job as representative.
- **UI (G8):** screenshots plus continuous critical-journey video where required by the inherited product UI contract; CI artifacts preserve it.
- **Publish:** central `geometry-mac-mini.yml` uses keyless GitHub OIDC federation to upload `ci-artifacts/showcase/` into **private GCS**, under `gs://BUCKET/geometry-harness/g0/SOURCE_SHA/GITHUB_RUN_ID-attempt-N/`. It uploads diagnostics even if Blender fails, but only passes G0 if real Blender tests succeed and the required GCS object paths are confirmed. No `actions/upload-artifact` dependency or Git binary render commits. Configure via `local-runner-infra/docs/geometry-gcs-artifacts.md`.
- **Retention:** Git retains only small fixtures/schema/tests; private GCS retains immutable run bundles and their hashes. No automatic deletion until the team decides development vs milestone retention; use bucket lifecycle policies afterward. Optional promoted reference examples may be separately published after provenance review.
- **Review ritual:** open `index.html` or `contact-sheet.png`, inspect renders visually, read objective checks, open `scene.blend` when needed, and compare to prior milestone. Automated success alone never attests to artistic quality.

## Milestone promotion rule

A Gx row becomes **DONE** only when its real E2E showcase executed on the target environment, required artifact files and link are available, automatic gates passed, the negative test proves bounded/recoverable failure, and a reviewer can visually inspect the deliverable. For closed-provider experiments, inability to run due to credentials is an explicit **BLOCKED** external gate, not a fake passing test. For local release, offline fidelity is a blocking condition.

A visual evaluation may return UNKNOWN when a judge is unavailable; deterministic geometry PASS is separate and does not allow an unverified claim of visual quality. An artifact bundle that cannot be inspected or reopened cannot qualify as a milestone completion.
