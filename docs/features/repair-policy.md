# VAL-01 / REPAIR-01 / ORCH-01 — Deterministic validation and bounded scoped repair

Status: **FIRST BOUNDED EDIT IMPLEMENTED AND REAL MAC E2E PASS; full repair policy still OPEN** · 2026-10-28. First supported operation: single-object `set_location` (max 0.5 m per axis), guarded by exact original scene spec + .blend SHA, validated after new-process Blender reopen; accepted/rollback artifacts are independent and immutable. Native positive/negative [run 40697004192](https://github.com/daniele21/local-runner-infra/actions/runs/40697004192). Existing trackers: [EX-02 #9](https://github.com/daniele21/3d-rendering-llm/issues/9), [EDIT-01 #11](https://github.com/daniele21/3d-rendering-llm/issues/11). Canonical milestone map: [workstream](../workstreams/geometry-harness.md).

## Design objective and strict boundaries

Reduce unnecessary AI-generated rewrites while keeping geometries demonstrably correct. The local/cloud model must **never execute author-authored Python directly**; proposals compile to an allowlisted typed operation and run through the trusted safe Blender builder on an isolated workspace. First validate cheaply; only then call a VLM/LLM for ambiguities where text/vision interpretation is genuinely required. Always preserve last accepted native checkpoint.

## Schema contracts (versioned)

`GeometryIssue`: `issue_id, status:PASS|FAIL|UNKNOWN, code, severity:blocking|warning|informational, target_ids[], units, expected, observed, tolerance, evidence_artifact_ids[], repairability:deterministic|ambiguous|human_only|none|unknown`. Numeric values only with verifiable measurement; unknown properties remain UNKNOWN. A validator is read-only.

`TypedSceneOperation`: `operation_id, scene_revision, operation_type, target_ids[], parameter_schema_version, params_with_units, preconditions[], expected_postconditions[], idempotency_key, authorized_scope`. First ops are translate/resize/rotate/set_material on stable IDs. Unit conversion and coordinate frame explicit; reject unknown targets, stale revision, impossible transforms and unknown types.

`RepairDecision`: `issue_ids[], policy_id, selected_action:accept|deterministic_fix|scoped_llm_patch|visual_judge|stop|human_review, reason_code, budget_remaining, expected_validation_ids, checkpoint_id, confidence_or_unknown`. Human-readable explanation accompanies machine fields, not chain-of-thought. LLM estimates are not objective validation.

`RevisionRecord`: `revision_id, previous_revision_id, source_artifact_hashes, patch_ids[], validation_report_hash, accepted_at, checkpoint_hash`. Replay in a fresh process verifies semantic geometry and preserved IDs; byte-equal `.blend` not required.

## Execution algorithm

1. Load immutable accepted revision and `TaskSpec`; check trusted input, model capability, authorization and wall/call/spend/memory budgets.
2. Run cheap preflight: compile safe subset, build, reopen in fresh Blender, deterministic geometry checks; output structured report.
3. If required constraints pass and visual evaluation not required, accept; otherwise classify findings using typed rule-based repairability.
4. When **uniquely correctable AND authorized**, compile minimal deterministic patch (never arbitrary Python) and apply in temporary scene with preconditions.
5. For ambiguous but localizable issues, request **scoped patch** from model using only task/spec, affected IDs, defects, relevant measurements and **not** unrelated private scene data or benchmark oracle. Reject unsupported operations.
6. Save a candidate checkpoint, validate affected constraints **and global non-target invariants**. If passed, promote atomically; otherwise discard candidate and retain accepted revision.
7. Visual judging only after executable/geometry gates, on documented rubric and views; not on every round by default.
8. Stop if: accepted; unresolved non-repairable issue; repeated identical error signature; exhausted calls/wall/memory/spend; no authorized changes; tool unavailable; or human decision needed. Missing evidence yields UNKNOWN, not success.

Example **experimental** policy (not a proven optimum):

```yaml
repair:
  policy_version: 1
  max_ai_rounds: 2
  max_tool_calls: 12
  max_active_wall_seconds: 240
  stop_on_repeated_error_signature: true
  no_unapproved_fallback: true
  preserve_last_accepted: true
  visual_judge_mode: on_ambiguous_visual_defect
```

Rules for stop/plateau **cannot** waive blocking dimensions, openings, safety or geometry invariants. Do not set a universal manifold closure condition: only enforce constraints actually requested. No "repair until prettier" indefinite loop.

## Test matrix / gates

| Scenario | Expected decision / evidence |
| --- | --- |
| Fully valid table/room | 0 repair calls, accepted .blend reopen |
| Disconnected fixture part | Deterministic issue referencing stable ID |
| Wrong dimension with uniquely authorized correction | Typed fix, measured tolerance, unchanged other objects |
| Visually ambiguous style but geometrically valid | Optional judge; never claim exact spatial correction from vision alone |
| Stale revision / missing target | Patch rejected, accepted scene unchanged |
| Invalid model patch / attempted Python script | Reject at compiler, no code execution |
| Same error repeats | Bounded stop, issue and last accepted snapshot preserved |
| Timeout / crash / corrupt journal | No silent partial scene acceptance, recovery or UNKNOWN |
| Two independent patches | Disjoint test may fork, but final mutation serialized/rebased and conflicts rejected |

Acceptance is a **real** Blender E2E with `original.blend`, `candidate.blend` only if created, `accepted.blend`, four views (where required), before/after/rollback contact-sheet, `issues.json`, `operations.jsonl`, `revisions.json`, manifest hashes, quality/latency/turn/cost deltas and negative test.

## A/B decision

Compare A = whole scene regeneration versus B = deterministic-first + scoped patch on same task/quality/hardware/provider/budget. Count complete attempts including all failures. KEEP only if quality is non-inferior at preregistered tolerance and accepted-result wall time or cost materially improves. Fixed-round vs adaptive policy is a **separate follow-on experiment**, not conflated with patch quality. See [experiment protocol](harness-efficiency-experiments.md).
