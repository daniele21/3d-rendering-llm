# Current state — Geometry Harness

Status: **G0 code candidate / 2026-10-27 benchmark-driven roadmap update (planning only)**. Source of this plan: `plan/benchmark-driven-e2e-sprints` branched from `feature/g0-blender-showcase`. Do not mark G0 done until actual Mac Blender E2E and private GCS upload evidence are verified.

## Current milestone

**S0 / G0:** Deterministic Blender four-leg table -> reopened `.blend`, real PNG/contact-sheet/gallery/manifest -> verified private GCS bundle. This is *not* an AI quality result.

## Parallel lanes NOW

| Area | Tracking | Can proceed before real G0? | Real E2E gate |
| --- | --- | --- | --- |
| A — Mac/Blender & GCS | [GH-00 #3](https://github.com/daniele21/3d-rendering-llm/issues/3) | Yes, primary blocker | Real Blender S0 E2E with reopened native file and verified upload |
| B — Benchmark provenance/suites | [BH-01 #4](https://github.com/daniele21/3d-rendering-llm/issues/4) | Yes, task registry/rights; rendering needs Blender | Freeze 6 smoke + 24 core + 212 full task IDs, data rights, Blender 5.0 profile |
| C — Metrics/reporting | [BH-02 #5](https://github.com/daniele21/3d-rendering-llm/issues/5) | Yes, schema/cheap tests | Real report using S1 generated artifacts; no phantom scores |
| D — Cloud provider adapter | [AI-01 #6](https://github.com/daniele21/3d-rendering-llm/issues/6) | Yes, API contracts without billing | Real approved model call -> generated scene, bounded failure |
| Convergence — S1 E2E | [AI-02 #7](https://github.com/daniele21/3d-rendering-llm/issues/7) | No, depends on A + B + D + C-minimum | Real prompt -> Blender -> benchmark -> gallery & GCS |

Future isolated hypothesis tracks: structured planner [#8](https://github.com/daniele21/3d-rendering-llm/issues/8), multiview/checks/repair [#9](https://github.com/daniele21/3d-rendering-llm/issues/9), 2D references [#10](https://github.com/daniele21/3d-rendering-llm/issues/10), edit MCP/rollback [#11](https://github.com/daniele21/3d-rendering-llm/issues/11), local inference [#12](https://github.com/daniele21/3d-rendering-llm/issues/12), final Cycles quality [#13](https://github.com/daniele21/3d-rendering-llm/issues/13). Prototype can be parallel; acceptance requires end-to-end measured output.

## Evidence/blockers

- Source branch `feature/g0-blender-showcase` already contains specialized G0 entrypoints, Blender scene creation, contract tests and E2E showcase test candidate. That **does not prove the target Mac rendering passed**.
- Last recorded central Mac mini G0 attempt checked out code, but Blender was not detected. GitHub Actions artifact quota was an issue; the workflow has been moving to private GCS. In a later bootstrap log, the bucket/WIF setup reportedly succeeded; **a successful Blender run, gallery inspection and verified uploaded GCS inventory are still not established**. Verify existing setup first, rather than re-provision blindly.
- No model/provider integration, paid experiment, 3DCodeBench benchmark result or A/B planner/2D experiment has passed this repository's E2E gates yet. All linked issues are tracked, not automatically started/finished.
- G0 Mac workflow is owned centrally by `daniele21/local-runner-infra`: only trusted exact SHAs, Mac mini-specific workflow, no source self-hosted labels/infra edits.

## Immediate next actions

1. Lane A runs the dedicated Mac mini exact-SHA pipeline; checks Blender availability, native scene assertions, gallery, SHA and GCS bundle.
2. Lanes B/C/D establish stable interfaces (TaskSpec / EvaluationRecord / ProviderAdapter), pinned datasets and deterministic unit+failure checks in separate file scopes.
3. Integrator of [#7](https://github.com/daniele21/3d-rendering-llm/issues/7) combines accepted handoffs into **one S1 real model-generated showcase**, captures budget and first frozen baseline.
4. All further experiments compare paired artifacts against that baseline; promote only with observed quality/cost/latency, not architectural intuition.

## Single sources of truth

- [Active sprint roadmap, dependency DAG and issues](workstreams/geometry-harness.md)
- [Benchmark protocol: task cohorts, leakage, score, 2D ablation](features/benchmark-protocol.md)
- [Showcase E2E and artifact gates](features/showcase-evidence.md)
- [Proposed runtime architecture](architecture.md)
