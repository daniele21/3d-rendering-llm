# First GPT-6 Luna six-task shape baseline — 2026-10-28

**Status: UPSTREAM_SHAPE_CHAMFER_EXECUTED; NONCOMPARABLE to official 3DCodeBench leaderboard.** This is an operator-run internal assessment of the six original paid Luna task attempts (2 valid Blender scenes; 4 missing generated GLBs), without new provider calls. The original CI remains \`INCOMPLETE\`.

## Measured and pinned evidence

| Field | Result |
| --- | --- |
| Input tasks | 6 pinned task IDs from \`YipengGao/3DCode@b70b4ee54b93fab76596da5809f3e71c617fa5c2\` |
| Reference release | \`3dcodebench/3dcodebench@e01cafff7b85a730424c0d053aefec09144eb0b5\` |
| Full archive SHA256 | \`459944518cb6e5f2a1f8de70ab273f557f4fe243b5dba7b44bb50c0e7b9563bc\` |
| Reference gate | \`SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET\`: 6 factory script and 12 prompt files byte-identical. GLB content independently hashed and structurally checked, but not independently regenerated from matched scripts. |
| Scorer commit | \`gaoypeng/3dcodebench@42c7780ed3fcbd466f17f058f62e7996233777f7\` |
| Scorer script SHA256 | \`598f23abbb6fdc776f52edb771c7137e40146686f60b2d22f9ad8317a11cb2ec\` |
| Generated GLBs scored | **2/6**: \`CoffeeTable_seed0\`, \`Balloon_seed0\`; 4 missing |
| **CD conditional mean** | **0.33838396924096587** (two valid GLBs only) |
| **CD penalized mean** | **0.7474027587207573** (six attempted tasks) |
| Model calls on scoring step | **0**; USD **$0 additional model-token cost** |
| Original generation cost | Luna six attempts: **USD $0.004875300** estimated model tokens |
| Profile | **NONCOMPARABLE_5_2_BLENDER_AND_RESTRICTED_AST** |

## What the score does and does not say

Pinned upstream \`metrics/shape_chamfer.py\` samples **8192 mesh-surface points per GLB**, centers and independently scales each point cloud to a unit sphere, then calculates the sum of the **two squared nearest-neighbor distances**. Lower Chamfer means more similar normalized surfaces *under identical scoring conditions*. It does not measure real-world size, correct scale, connectivity, materials, visual quality or semantic adherence to the text prompt. The scorer also calculates orientation-robust \`cd_yawmin\` (four Z yaw rotations of 0, 90, 180, 270 degrees), but the operator's console excerpt did not include those values.

The upstream \`penalized_mean\` assigns **1.5 × the worst observed valid CD in that same run** to each of the four missing/failed GLBs, then averages over six. This penalty is **run-relative, not a fixed reference threshold**. Do not interpret 0.3384 as 33.84% quality, or 0.7474 as a directly comparable cross-cohort score. Preserve both means and the true 2/6 completion rate. The two per-task numeric Chamfer results cannot be assigned to particular objects from the summary alone.

To inspect per-task values and the yaw-aligned metric **without calling Luna again**, on the authorized operator Mac:

    FILE="$HOME/geometry-evidence/luna-six-shape-stage/results/text_to_3D/gpt-6-luna/_metrics/shape_chamfer.json"
    jq '{n_instances,n_ok,n_points,normalization,yaw_alignment,penalty_cd,cd,cd_yawmin,per_instance:[.per_instance[]|{instance,status,cd,cd_yawmin,yaw_argmin}]}' "$FILE"

## Scientific gates still open

1. Inspect original per-task \`shape_chamfer.json\` including all six statuses, two valid numeric scores, \`cd_yawmin\` and penalty; produce a fixed-camera reference/output preview pair for CoffeeTable and Balloon without model inference.
2. Independently test part count, geometry contacts, dimensions and human-approved prompt adherence; normalized Chamfer alone cannot distinguish semantic correctness.
3. Freeze the benchmark protocol, failure penalty and identical cohort for **paired** direct/planner/repair comparisons; do not make broad decisions on six observations. Expand to a 24-task core only with a measured budget.
4. Confirm the comparison's Blender/runtime and safe AST scope. The original experiment used native Blender 5.2.3 and restricted cube/cylinder/sphere, whereas upstream free-Python Blender 5.0 executability is a different evaluation target. **No official 3DCodeBench rank or image/semantic score is established.**

The operator downloaded the 1.95 GB public archive with the published checksum; the archive itself, private historical GLBs, model code, reference scripts and private image assets must **not** be committed to GitHub. This document records only summary metrics and public hashes.
