# Luna six-task postmortem — parser policy vs model generation

Historical 2026-10-28 original six-task Luna run: 2/6 native Blender PASS, original CI `INCOMPLETE`, cost ledger `COMPLETE`, model-token estimate USD 0.004875300. Independently re-audited by the authorized GCS operator: 27/27 private objects. **Never change this historical benchmark or its billing.**

## Two independently identified failure classes

- `AquariumTank_seed0`, `ArmChair_seed0`, `Bottle_seed0` originally fail the production AST compiler with `Invalid or unsafe geometry name`. This is a strict naming *contract* issue, not proof the rest of the scripts are safe or geometrically correct. Accepted names match `[A-Za-z][A-Za-z0-9_-]{0,47}`. We must inspect actual literals before any policy change.
- `BrainCoral_seed0` completed its 2048-token output budget with **2048 reasoning tokens** in 19.07095s and `UNFINISHED_RESPONSE`, with original token estimate USD 0.001066600. No valid code/scene resulted. `max_completion_tokens` caps reasoning + visible output together. The provider currently sets `reasoning_effort="low"`. The `gpt-6-luna` API supports `none`, but a future `low` vs `none` A/B would be a **new paid experiment** and is NOT executed by this change.

## Safe no-call diagnostic on the operator's already downloaded bundle

```bash
cd ~/Projects/3d-rendering-llm
git pull --ff-only

PYTHONPATH=src python3 -m geometry_harness.evaluation.rejection_postmortem \
  --bundle ~/geometry-evidence/luna-six-original/historical-evidence \
  --out ~/geometry-evidence/luna-six-name-ablation-01
```

What this does:
1. Re-audits *all* original file hashes, six task IDs, model and actual cost ledger using the existing strict evidence auditor before creating new output.
2. Prints the **exact invalid name literals** and a suggested deterministic ASCII alias for each rejected script.
3. Changes **only literal `.name` string constants** in an AST-derived local *candidate*, never the historical original. If the candidate passes the *unchanged* `compile_bpy_subset` (including unsafe call/loop and duplicate-name prohibitions), writes it in the fresh private output folder and labels `COMPILER_PASS_AFTER_NAME_ABLATION`. If some *second* rule rejects it, reports the next compiler error and does not export a candidate.
4. Never executes generated Python, never runs Blender, never replays Luna, never creates a native scene, never claims better than 2/6 historical scene passes.

**Naming decisions:** normalized aliases are for offline diagnosis only. We should not silently change the production parser to accept arbitrary names or treat compiler acceptance as semantic success. Any future auto-normalizer requires frozen collision policy, stable geometry IDs and independent Blender reopen/visual checks; accepted historical scores must remain immutable.

**Next experiment design:** report `original_compiler_pass`, `alias_only_compiler_pass`, `native_scene_pass_after_alias` and independent prompt/shape similarity as **four different metrics**, with a separate recorded artifact revision. For BrainCoral, test `reasoning_effort="none"` vs `low` under the same fixed output-budget / cost / latency limits *only after a separate explicitly authorized paid run*. For a comprehensive strategy, evaluate a stricter schema of structured primitive objects instead of outputting arbitrary Blender Python.
