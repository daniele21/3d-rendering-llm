# PERF-02 — Harness efficiency and latency A/B protocol

Status: **EXPERIMENT DESIGN / NO RESULTS YET** · 2026-10-28. Scope complements—not replaces—[3DCodeBench benchmark protocol](benchmark-protocol.md) and [agent performance schema](agent-performance.md).

## Questions and causal design

Q1: Does cheap deterministic validation reduce *unnecessary* model calls? Q2: Do scoped typed patches reduce accepted-result end-to-end latency versus full regeneration? Q3: When does adaptive stopping help or degrade geometric acceptance? Q4: Do composite tools save sequential turn time without reducing safeguards? Q5: Can an open-weight local model complete the **same task** inside hardware/no-egress constraints?

Do NOT compare only successful samples, vary model and execution strategy simultaneously, treat unknown latency/cost as zero or label a six-task smoke statistically significant. For local vs cloud, model **is** intentionally changed: report as system comparison, not a causal test of repair policy.

## Pre-registered arms and evaluation

| Arm | Intervention | Comparison baseline |
| --- | --- | --- |
| A0 | One direct model→safe AST→Blender, no repair | Frozen cloud baseline |
| A1 | A0 + deterministic validation and structured feedback, no new AI iterations | A0, same task |
| A2 | A1 + typed scoped repair (bounded) | Regenerate-whole-scene repair, equal max calls/time budget |
| A3 | A2 + adaptive decision/stop, optional VLM when needed | A2 with fixed accepted-budget rounds |
| A4 | A3 + selected composite tools/stage cache | A3 with primitive tools, same cold/warm-cache policy |
| A5 | Selected A* with open-weight model and verified offline | Selected cloud A*; explicitly cross-model comparison |

All arms record configured task IDs, prompts, source SHA, accepted geometry, allowed reference files, model/temperature/effort, retries, Blender profile, API tariff snapshot, hardware, memory, judge version, seed/repetitions and concurrency. External 3DCodeBench scoring uses upstream pinned runtime/scorer and licence compliance; synthetic ArchitectureBench is an independent suite. Never leak held-out factory meshes/images to generator.

## Metrics and calculations

Primary outcomes:
- `accepted_scene_rate` = verified valid+accepted native scenes / **all started attempts** (missing geometry or judge != PASS).
- `p50_wall_seconds`, `p90_wall_seconds` from real end-to-end time **with failures/timeouts shown separately and censoring noted**, not just fastest successful outcomes.
- `cost_per_accepted` = total observed eligible task costs / accepted count, otherwise UNKNOWN. Provider token estimate ≠ invoice; local machine energy/compute may be estimated only with documented method.
Secondary: `first_pass_acceptance`, `model_turns_per_attempt`, `tool_calls`, `scoped_patch_success`, `non_target_preservation`, `repair_rounds`, `error_signature_repeats`, `critical_path_model_wait`, `render_seconds`, `peak_RSS`, `no_egress`, visual quality + independent judge uncertainty.

Report paired per-task deltas, distributions, confidence intervals/bootstraps on adequate N, failures and missing/unknown; warmup, retries and cache state must be equal or separately stratified. Human blind review of quality where numerical geometry cannot adjudicate. Visual judge noise must be measured via A/A repeat, not assumed zero.

## Workloads

- Tier 0 deterministic: G0 four-leg table, invalid source, disconnected component, material edit, geometry edit, failed tool and rollback.
- Official 3DCodeBench: existing frozen six real smoke IDs (source main catalog), core 24 and full 212 only once exact dataset revision/scorer/runtime and rights verified. Six is **setup/smoke**, not generalizable benchmark.
- ArchitectureBench separate: ten simple licensed synthetic DXF fixture categories (room, wall, opening, multilayer, bad units, open boundary, missing object, material/geometry edit, rollback). No partner dataset in public source.
- Partner baseline separate/private: same authorized input, same target render/geometry acceptance criteria, hardware and reference, end-to-end reproducible trace (including any human intervention), when NDA signed.

## Targets and STOP/GO

Proposed pre-registration **to be confirmed before running**: ≥20% paired median accepted-outcome latency reduction, ≥30% model turns on repair-dependent tasks, non-inferior verified geometric acceptance within explicitly chosen tolerance, zero unapproved non-target mutation, full evidence for every claimed PASS. These are **hypotheses**, not promised outcomes.

KEEP if improvement plus quality safety gates hold, REWORK if quality/latency trade-off mixed, DROP if clearly worse, INCONCLUSIVE if insufficient power, scorer missing, high unknown fraction, untrusted external environment. Report every arm even when it fails. Avoid p-hacking and selecting winning thresholds after observing results.

## Artifact contract

Each real run stores `performance-summary.json`, `trace.jsonl` (scrubbed), `evaluation.json`, `geometry-issues.json`, `revisions.json` if editing, `showcase-manifest.json`, `costs/events.jsonl` privately when billed, native .blend, representative PNG views, render/config hashes, test logs and negative-case evidence. One gallery compares arms by same task ID with explicit PASS/FAIL/UNKNOWN, latency and cost status. No silent exclusion of timeout/UNKNOWN.

## Operational safeguards

Routine PR checks only offline, synthetic, cheap. Live model tests are explicit trusted-SHA opt-in with known call budget and pre-call spend guard; immutable private GCS ledger required; local experiments must verify no-egress and must not auto-upload unapproved private artifacts. Manage shared Mac mini resources and sequence expensive runs to avoid contaminated parallel timing.
