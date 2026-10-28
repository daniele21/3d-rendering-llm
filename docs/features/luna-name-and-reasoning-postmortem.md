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

## Actual operator findings and safe native continuation (2026-10-28)

The operator has executed the six-task postmortem against their independently audited private GCS bundle. All three original compiler failures were restricted to **literal object-name policy** and then passed the **unchanged** safe-AST compiler:

| Task | Previously rejected literal names | After name-only AST ablation |
| --- | ---: | --- |
| `AquariumTank_seed0` | 22 | `COMPILER_PASS_AFTER_NAME_ABLATION` |
| `ArmChair_seed0` | 15 | `COMPILER_PASS_AFTER_NAME_ABLATION` |
| `Bottle_seed0` | 16 | `COMPILER_PASS_AFTER_NAME_ABLATION` |

Total: **53 descriptive mesh names normalized**. Names like `Bottle_-_main_body` contain hyphens but **are allowed** by our current `[A-Za-z][A-Za-z0-9_-]{0,47}` mesh-name rule. These are mesh labels, not Python variable identifiers.

This raises compiler feasibility from the historical two accepted native scenes to **five of six scripts that can now be compiled**, NOT yet five independently verified Blender scenes. The remaining `BrainCoral_seed0` failure was a **reasoning-token/output-budget exhaustion** and cannot be corrected by aliasing. Original historic costs, CI failure, scene count and shape scores remain unchanged.

### Test the actual three derived scenes without paying Luna

[PR #64](https://github.com/daniele21/3d-rendering-llm/pull/64) adds `native_name_ablation`, which re-audits the original private bundle, regenerates candidate ASTs and verifies exact derived source SHA, then runs **only repository-owned** Blender builder/independent inspector on all three. Real Mac CI has passed on **synthetic** three-task fixtures; it did **not** process the user's historical private model outputs.

On the same authorized operator Mac (after this PR is on `main`):

```bash
cd ~/Projects/3d-rendering-llm
git pull --ff-only
PYTHONPATH=src python3 -m geometry_harness.evaluation.native_name_ablation \
  --bundle ~/geometry-evidence/luna-six-original/historical-evidence \
  --ablation ~/geometry-evidence/luna-six-name-ablation-01 \
  --out ~/geometry-evidence/luna-six-native-name-ablation-01
```

Inspect `~/geometry-evidence/luna-six-native-name-ablation-01/native-name-ablation.json` and the derived per-task `scene.blend`, `preview.png`, `reopened-geometry.json`. An exit code of 1 means one or more **derived native** failures (no automatic retry or AI requests). Failed candidates and their Blender logs remain in the new evidence directory; the original baseline is never modified.

**Do not** upload the private generated code or reference assets into public GitHub issues/commits. Only aggregate outcomes and relative hashes may be recorded in the roadmap. Later scoring can export the accepted new `.blend` files and compute Chamfer with the **already pinned** reference meshes and scorer, but derived results must have a distinct experiment ID. Separate all four metrics: compiler pass, native scene pass, shape similarity and semantic fidelity.
