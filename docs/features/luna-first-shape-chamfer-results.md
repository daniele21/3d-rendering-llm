# First GPT-6 Luna six-task shape baseline — 2026-10-28

**Status: UPSTREAM_SHAPE_CHAMFER_EXECUTED; NONCOMPARABLE to official 3DCodeBench leaderboard.** This is an operator-run internal assessment of the six original paid Luna task attempts (2 valid Blender scenes; 4 missing generated GLBs), without new provider calls. The original CI remains `INCOMPLETE`.

## Measured and pinned evidence

| Field | Result |
| --- | --- |
| Input tasks | 6 pinned task IDs from `YipengGao/3DCode@b70b4ee54b93fab76596da5809f3e71c617fa5c2` |
| Reference release | `3dcodebench/3dcodebench@e01cafff7b85a730424c0d053aefec09144eb0b5` |
| Full archive SHA256 | `459944518cb6e5f2a1f8de70ab273f557f4fe243b5dba7b44bb50c0e7b9563bc` |
| Reference gate | `SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET`: 6 factory script and 12 prompt files byte-identical. GLB content independently hashed and structurally checked, but not independently regenerated from matched scripts. |
| Scorer commit | `gaoypeng/3dcodebench@42c7780ed3fcbd466f17f058f62e7996233777f7` |
| Scorer script SHA256 | `598f23abbb6fdc776f52edb771c7137e40146686f60b2d22f9ad8317a11cb2ec` |
| Generated GLBs scored | **2/6**: `CoffeeTable_seed0`, `Balloon_seed0`; 4 missing |
| **CD conditional mean** | **0.33838396924096587** (two valid GLBs only) |
| **CD penalized mean** | **0.7474027587207573** (six attempted tasks) |
| Model calls on scoring step | **0**; USD **$0 additional model-token cost** |
| Original generation cost | Luna six attempts: **USD $0.004875300** estimated model tokens |
| Profile | **NONCOMPARABLE_5_2_BLENDER_AND_RESTRICTED_AST** |

## What the score does and does not say

Pinned upstream `metrics/shape_chamfer.py` samples **8192 mesh-surface points per GLB**, centers and independently scales each point cloud to a unit sphere, then calculates the sum of the **two squared nearest-neighbor distances**. Lower Chamfer means more similar normalized surfaces *under identical scoring conditions*. It does not measure real-world size, correct scale, connectivity, materials, visual quality or semantic adherence to the text prompt. The scorer also calculates orientation-robust `cd_yawmin` over four Z yaw rotations (0, 90, 180, 270 degrees). The operator has now provided all six per-instance entries from the private original JSON (see below).

The upstream `penalized_mean` assigns **1.5 × the worst observed valid CD in that same run** to each of the four missing/failed GLBs, then averages over six. The original per-instance scorer JSON has now identified exactly which task generated each measured CD. The per-failure penalty for the plain CD is **0.9519121534606532** (1.5 × Balloon's 0.6346081023071021); the penalized six-task CD is **0.7474027587207573** in the actual upstream aggregate (computed from full precision; minor representation differences are possible). This is a run-relative penalty, **not** an absolute threshold. This penalty is **run-relative, not a fixed reference threshold**. Do not interpret 0.3384 as 33.84% quality, or 0.7474 as a directly comparable cross-cohort score. Preserve both means and the true 2/6 completion rate. The two per-task numeric Chamfer results cannot be assigned to particular objects from the summary alone.

To inspect per-task values and the yaw-aligned metric **without calling Luna again**, on the authorized operator Mac:

    FILE="$HOME/geometry-evidence/luna-six-shape-stage/results/text_to_3D/gpt-6-luna/_metrics/shape_chamfer.json"
    jq '{n_instances,n_ok,n_points,normalization,yaw_alignment,penalty_cd,cd,cd_yawmin,per_instance:[.per_instance[]|{instance,status,cd,cd_yawmin,yaw_argmin}]}' "$FILE"

## Original per-instance scorer results — operator JSON inspection 2026-10-28

The operator ran `jq` on the private `shape_chamfer.json` at `~/geometry-evidence/luna-six-shape-stage/results/text_to_3D/gpt-6-luna/_metrics/`. The following are **observed per-task values**, not scores guessed from the aggregate:

| Instance | Upstream status | CD (normalized squared) | CD yaw-min | Winning Z yaw |
| --- | --- | ---: | ---: | ---: |
| `CoffeeTable_seed0` | `OK` | **0.04215983617482963** | **0.04215983617482963** | 0° |
| `Balloon_seed0` | `OK` | **0.6346081023071021** | **0.5759648164497149** | 270° |
| `AquariumTank_seed0` | `NO_GEN_GLB` | N/A | N/A | N/A |
| `ArmChair_seed0` | `NO_GEN_GLB` | N/A | N/A | N/A |
| `Bottle_seed0` | `NO_GEN_GLB` | N/A | N/A | N/A |
| `BrainCoral_seed0` | `NO_GEN_GLB` | N/A | N/A | N/A |

### Cohort aggregates and missing-mesh policy

| Metric | Conditional mean, valid 2/6 | Failure-penalized mean, all 6 |
| --- | ---: | ---: |
| Normalized squared CD | **0.33838396924096587** | **0.7474027587207573** (recorded upstream) |
| Yaw-min normalized squared CD | **0.30906232631227226** | **0.6789855918871389** (derived using upstream 1.5× worst rule) |

The yaw-min penalty is `1.5 × 0.5759648164497149 = 0.8639472246745723`. The yaw-min six-task mean shown here is **derived algebraically** from the supplied per-task entries, not copied from the aggregate JSON; its value should be checked against `cd_yawmin.penalized_mean` in the private file before using it in A/B reports. Four missing GLBs are penalized **in the cohort aggregate only**. Their original statuses remain `NO_GEN_GLB`, not `OK` or 0-distance.

Balloon improves by **9.24%** when the generated cloud is rotated by 270° around Z, but its yaw-min CD is still much higher than CoffeeTable's. This makes simple orientation mismatch an insufficient explanation for that shape gap. This test is a *normalized geometric shape comparison*, not a real-world dimension, appearance, assembly/contact, prompt fidelity or official leaderboard measure.

### Next failure diagnosis (no model calls)

Inspect the four failed tasks' original `result.json` and the optional generated Python **as plain text only**; never execute it. Distinguish provider refusal/truncation, AST coverage rejection, unsafe structure, native Blender failure and geometrical nonconformity. In parallel, inspect CoffeeTable and Balloon reference/output images side by side and compare named parts and mesh topology. Prioritize making the four missing tasks produce acceptable safe scenes, then improve Balloon shape fidelity; repeat scoring only with identical pinned task, reference and scorer protocols.

## Scientific gates still open

1. Confirm the derived yaw-min penalized aggregate against the raw private JSON; create aligned reference/output preview pairs for CoffeeTable and Balloon without model inference.
2. Independently test part count, geometry contacts, dimensions and human-approved prompt adherence; normalized Chamfer alone cannot distinguish semantic correctness.
3. Freeze the benchmark protocol, failure penalty and identical cohort for **paired** direct/planner/repair comparisons; do not make broad decisions on six observations. Expand to a 24-task core only with a measured budget.
4. Confirm the comparison's Blender/runtime and safe AST scope. The original experiment used native Blender 5.2.3 and restricted cube/cylinder/sphere, whereas upstream free-Python Blender 5.0 executability is a different evaluation target. **No official 3DCodeBench rank or image/semantic score is established.**

The operator downloaded the 1.95 GB public archive with the published checksum; the archive itself, private historical GLBs, model code, reference scripts and private image assets must **not** be committed to GitHub. This document records only summary metrics and public hashes.
