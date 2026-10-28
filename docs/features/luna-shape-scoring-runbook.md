# From verified historical GPT-6 Luna evidence to shape-score staging

**Operator-only, zero new model calls.** The historical six-task GCS audit is COMPLETE
(27/27 objects, two native scenes, model-token estimate USD 0.004875300).
Original CI remains `INCOMPLETE`. This runbook does **not** imply official
benchmark comparability, semantic fidelity or scene quality.

## Step 1 — export the two accepted saved scenes (private Mac)

From the updated repository after `git pull --ff-only`, with Blender installed:

```bash
PYTHONPATH=src python3 -m geometry_harness.evaluation.upstream_shape_adapter \
  --input "$HOME/geometry-evidence/luna-six-original/historical-evidence" \
  --out "$HOME/geometry-evidence/luna-six-shape-stage"
```

Expected structural result: six task records in `scorer-staging.json`; native
`CoffeeTable_seed0` and `Balloon_seed0` have verified generated GLBs and
`READY_FOR_ISOLATED_REFERENCE_SCORER`. Other tasks have `UNKNOWN_NO_REFERENCE`
and no generated GLB (do not fabricate one). This only **stages** generated
shapes, preserves original `.blend`, runs no model Python and invokes no LLM.

## Step 2 — gate six externally released ground-truth references

The separate public `3dcodebench/3dcodebench` Hugging Face release contains
`3dcodebench_v1.tar.gz` as **one ~1.95GB object**, not individually downloadable
GLB objects. **Pin** its exact archive release at
`e01cafff7b85a730424c0d053aefec09144eb0b5`. Our generator benchmark
was pinned separately to `YipengGao/3DCode` commit
`b70b4ee54b93fab76596da5809f3e71c617fa5c2`.

Optional, **explicit large download** to Hugging Face's local cache; requires
`huggingface_hub` in the current Python environment:

```bash
python3 -m pip install 'huggingface_hub>=0.30,<2'

PYTHONPATH=src python3 -m geometry_harness.evaluation.reference_provenance \
  --download-archive \
  --out "$HOME/geometry-evidence/luna-six-reference-glbs"
```

Alternatively, if you already have the public `3dcodebench_v1.tar.gz`
archive, pass `--archive /private/path/3dcodebench_v1.tar.gz` instead of
`--download-archive`. The command then still obtains only the 18 small,
original pinned benchmark prompt/factory files from Hugging Face and compares
their exact contents to the archive. Use `--source-root` only for an
already-verified local copy of `YipengGao/3DCode/3DCodeBench`; **supplying
arbitrary local source files is NOT accepted as pinned provenance by the scorer**.

The gate decompresses the archive **sequentially**, never `extractall`,
never executes `.py`, never passes reference scripts to the generator.
It requires six matches across both frozen public prompt texts **and** the
ground-truth script bytes before writing six scorer-only GLBs. Filename
similarity alone is not enough. It rejects bad/missing/duplicate members,
symlinks, corrupt GLB headers and references from a different release.

Output: six `<task>/glb/<task>.glb` files plus
`reference-provenance.json`, with source/release SHA, per-file hashes, matched
prompt and factory hashes, and `official_score=null`. The script does **not**
certify that a packaged GLB was actually produced by its matching factory;
there is no verified rendering profile/Blender 5.0 parity.

**The code will stop if the alternative archive is not byte-identical on
all six prompts/scripts.** Do not relax this to obtain a positive result.

## Step 3 — invoke the pinned scorer in a separate trusted environment

Only after successful provenance validation, clone and review the *published*
upstream scorer (no arbitrary reference factory execution):

```bash
git clone https://github.com/gaoypeng/3dcodebench \
  "$HOME/geometry-evidence/scorer/3dcodebench"

git -C "$HOME/geometry-evidence/scorer/3dcodebench" \
  checkout --detach 42c7780ed3fcbd466f17f058f62e7996233777f7

# In a new isolated Python virtual environment:
python3 -m pip install 'numpy' 'scipy' 'trimesh'

PYTHONPATH=src python3 -m geometry_harness.evaluation.upstream_shape_adapter \
  --out "$HOME/geometry-evidence/luna-six-shape-stage" \
  --upstream "$HOME/geometry-evidence/scorer/3dcodebench" \
  --refs "$HOME/geometry-evidence/luna-six-reference-glbs"
```

The adapter now verifies `reference-provenance.json` first, independently
rehashes all six reference meshes and then calls the scorer at its exact
pinned Git SHA. It requires the six-task denominator. Its Chamfer uses
normalized point clouds, fixed RNG and four yaw rotations. Both a
conditional successful-scenes mean and a failure-penalized six-task mean
are computed by the upstream script, but cannot be assumed equivalent to
the original Blender 5.0 free-Python leaderboard.

## Operator execution result — 2026-10-28

The operator completed the pinned reference download (1.95GB), verified 6/6 prompt and factory script identities and all reference GLBs, then executed the pinned upstream shape scorer on the historical two generated Luna GLBs. The recorded metrics: `n_instances=6`, `n_scored=2`, `cd.conditional_mean=0.33838396924096587`, `cd.penalized_mean=0.7474027587207573`, `model_calls=0`; profile `NONCOMPARABLE_5_2_BLENDER_AND_RESTRICTED_AST`. For per-task scores and yaw-min, inspect the original `shape_chamfer.json`. Do **not** compare its run-relative penalized mean across different task sets/acceptance policies. [Recorded evidence](luna-first-shape-chamfer-results.md).

## Non-negotiable limits

- No additional Luna/API calls; the only possible new costs are public data
  download/bandwidth, local compute and storage.
- No reference GLBs, hidden factory scripts or original generated model code
  are committed to the public repo or passed into the generator.
- `reference-provenance.json` proves *text/script byte identity*, not
  independently rendered reference GLB geometry or Blender version parity.
- If provenance mismatches or the local scorer fails, report `UNKNOWN`;
  **never** substitute fabricated Chamfer = 0.
- The source `gpt-6-luna` examples have an AST-restricted primitive dialect.
  Even a successfully calculated upstream Chamfer metric is a **non-comparable
  exploratory geometry score**, not an official leaderboard score.

Evidence references: private original audit
`~/geometry-evidence/luna-six-original/review/index.html` and public datasets
https://huggingface.co/datasets/3dcodebench/3dcodebench and
https://huggingface.co/datasets/YipengGao/3DCode .
