# Optional cone counterfactual for Qwen Bottle

Status: code implemented, 147+ offline tests passed; real Mac replay and reference Chamfer still pending.

The historical two-task Korgis result remains **CoffeeTable native PASS; Bottle AST FAIL (1/2)**. The generation-only report's 0 native passes means Blender was intentionally not run in that phase.

The original Bottle source starts with a valid Blender cone, which the original three-primitive contract correctly rejects. The new parser opt-in `allow_cone=True` permits bounded cones with literal radius1/radius2, depth, vertices and location. The default remains `False`. Only trusted Blender builder code can run, not generated Python.

## Replay on the Mac (Korgis stopped)

```bash
cd ~/Projects/3d-rendering-llm
git fetch origin
git switch feature/g1-cone-opt-in-bottle-replay
git pull --ff-only
export PYTHONPATH=src
python3 -m geometry_harness.evaluation.cone_counterfactual \
  --stage "$HOME/geometry-evidence/korgis-qwen-2-task-generation-01" \
  --baseline "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01" \
  --out "$HOME/geometry-evidence/korgis-bottle-cone-counterfactual-01"
```

Original source SHA inventory and baseline report SHA must match before a new Blender scene is attempted. Output is an isolated `cone-counterfactual.json` (and potentially a `preview.png` and `scene.blend`). No model calls occur. A derived 2/2 cannot be reported as original model success.

```bash
jq '{status,baseline_original_native_pass,counterfactual_native_scene,post_hoc_combined_native_pass,cone_count,generated_mesh_objects,new_model_calls}' "$HOME/geometry-evidence/korgis-bottle-cone-counterfactual-01/cone-counterfactual.json"
open "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01/tasks/CoffeeTable_seed0/preview.png"
open "$HOME/geometry-evidence/korgis-bottle-cone-counterfactual-01/tasks/Bottle_seed0/preview.png"
```

## Optional pinned shape scoring

Requires already-verified six reference GLBs under a scorer-only private directory with `reference-provenance.json`, and upstream 3dcodebench checkout pinned at `42c7780ed3fcbd466f17f058f62e7996233777f7`. The scorer rejects unverified references and scripts; never sends them to the model.

```bash
python3 -m geometry_harness.evaluation.local_qwen_shape \
  --stage "$HOME/geometry-evidence/korgis-qwen-2-task-generation-01" \
  --baseline "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01" \
  --derived "$HOME/geometry-evidence/korgis-bottle-cone-counterfactual-01" \
  --upstream "/path/to/pinned/3dcodebench" \
  --refs "/path/to/verified/private/refs" \
  --out "$HOME/geometry-evidence/korgis-qwen-cone-shape-01"
```

Metrics are per-task with same 8192-point seeded protocol, not official leaderboard results. Missing scorer/references mean UNKNOWN; a technically valid native scene does not imply semantic fidelity. Keep large evidence in private GCS under a unique new prefix and only commit pointers after an actual upload.
