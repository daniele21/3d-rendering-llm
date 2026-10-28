# Geometry Harness — Coding Agent Guide

This is the **3d-rendering-llm application**, not the generic `repo-template-sw` distributor. Goal: reproducible editable 3D geometry and visible milestones, ultimately with fully local open-weight LLM/VLM inference. No cloud account or network access may be necessary for deterministic G0 and later offline modes.

## Current executable scope

- Root README: user commands. `docs/product.md`: durable product direction.
- `docs/workstreams/geometry-harness.md`: active G0–G8 dependency DAG and task state (not implementation evidence).
- `docs/features/showcase-evidence.md`: mandatory real end-to-end (E2E) visual artifact contract for each slice.
- `docs/features/benchmark-protocol.md`: immutable external benchmark cohorts, source/provenance isolation, paired A/B, FAIL/UNKNOWN and cost accounting. Benchmark reference factories must never leak into generator context.
- `docs/architecture.md`: proposed code-first / typed MCP / hybrid boundaries.
- `src/geometry_harness/`: CLI and stdlib orchestration; `src/geometry_harness/blender/`: code executed in Blender embedded Python.
- `tests/test_g0_contract.py`: fast contract tests; `tests/e2e/test_showcase_g0.py`: real Blender showcase + tamper-failure test.
- `.github/ci/local-test.sh`: source-owned Mac validation, called by central runner repository `daniele21/local-runner-infra`. Read `.github/AGENTS.md` for runner security.

## Non-negotiable invariants

1. Each milestone ends with a real inspectable scene/render, machine assertions and a negative test. Mock/replay is not a real Blender/model result.
2. Never claim Gx DONE until the real representative E2E and required assets exist; include commit/run/environment identity, limits and gaps.
3. Code-first truth is generator code; eventual MCP truth requires checkpoint + typed action journal; preserve previous accepted revisions and detect divergence.
4. Keep provider logic separate from geometry and rendering. Closed API experiments are opt-in, credential bounded and measurable. No API required for G0.
5. Generated script execution is bounded and must not write outside owned work directories. Detect failure, keep diagnostic logs, clean owned child processes.
6. Geometry invariants checked deterministically in a separate Blender session; visual score cannot replace geometric evidence.
7. Every outbound paid model call, including retries and VLM judges, must pass through the per-call started/settled private cost ledger. Use the versioned model price card to record uncached, cached read, 30m/12h cache writes, output and reasoning subset; unknown usage/price is UNKNOWN, never $0. Mandatory private GCS log+summary proof before a G1 run is accepted. See docs/features/model-cost-observability.md.
8. Do not commit run outputs, .blend, image products, AI model weights or secrets.
9. Existing local Mac runners are scoped to private `local-runner-infra`; do not register new runners or put its labels into source workflow. Run only trusted exact commits.

## Development workflow

Iteration: cheap focused unit checks. Integration: validate exact head/base, source diff, real E2E and artifact hashes, inspect PNG and reopen `.blend`. Release: complete target Mac evidence, cleanup and offline guarantees where claimed. A failed remote gate remains a blocker, not a user-run manual task just because an agent lacks Blender.

For G0:

```bash
export PYTHONPATH="$PWD/src"
python3 -m unittest discover -s tests -p test_g0_contract.py -v
python3 -m geometry_harness doctor
GEOMETRY_SHOWCASE_DIR="$PWD/ci-artifacts/showcase/g0" python3 -m unittest discover -s tests/e2e -p test_showcase_g0.py -v
python3 -m geometry_harness showcase validate ci-artifacts/showcase/g0
```

Read relevant source rather than all inherited template docs. Converge parallel work into one vertical deliverable, maintain fast tests and never weaken a legitimate gate to green a failing CI run.
