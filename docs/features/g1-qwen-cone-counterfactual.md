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

## 2026-10-30: Qwen Chamfer export failed with Blender exit 14

The first operator Qwen `local_qwen_shape` attempt exited in the GLB export
phase with `Trusted Blender builder failed with exit 14`. **This is not a
Chamfer metric and cannot be interpreted as a model/shape failure.** The
pipeline has already validated the Qwen scenes and reference/scorer identities
before exporting, but must inspect the *private* Blender traceback in
`exports/<task>/export.log` to confirm the immediate exception.

Code inspection uncovered a mismatched identity contract: the normalized
Qwen scene's inspected `geometry_id` values are `mesh_001`, `mesh_002`,
etc., deliberately separate from readable names (`tabletop`, etc.). The
legacy GLB exporter had incorrectly insisted on `geometry_id == name` for
all meshes. The fix sends an explicit name-to-stable-ID map derived **only**
from the independent Blender `geometry.json`, already SHA-verified by the
shape runner. Exporter checks that exact mapping and rejects missing/duplicate
or modified IDs. The original Luna legacy export path still demands
`geometry_id == name` when no explicit mapping is supplied, preserving its
previous safety contract. No model code execution or source rewrites.

Before retrying, **preserve the first failed private folder**; examine its
logs, without deleting anything:

```bash
find "$HOME/geometry-evidence/korgis-qwen-cone-shape-01/exports" \
  -name export.log -print -exec tail -n 55 {} \;

jq -r '.mesh_objects[] | [.name, .geometry_id] | @tsv' \
  "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01/tasks/CoffeeTable_seed0/geometry.json"
```

On updated feature branch, rerun to a NEW output path:

```bash
cd ~/Projects/3d-rendering-llm
git fetch origin && git pull --ff-only
export PYTHONPATH=src
python3 -m geometry_harness.evaluation.local_qwen_shape \
  --stage "$HOME/geometry-evidence/korgis-qwen-2-task-generation-01" \
  --baseline "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01" \
  --derived "$HOME/geometry-evidence/korgis-bottle-cone-counterfactual-01" \
  --upstream "$HOME/geometry-evidence/3dcodebench-scorer" \
  --refs "$HOME/geometry-evidence/luna-six-reference-glbs" \
  --out "$HOME/geometry-evidence/korgis-qwen-cone-shape-02"
```

The previous `...-01` output must never be reused or overwritten. Updated
errors report the specific failing task and log path. If a new failure
occurs, inspect that log; other causes (GLTF addon, Blender version, scene
contents) still require specific diagnosis. Real Mac shape scores remain
UNKNOWN until the scorer actually runs.
