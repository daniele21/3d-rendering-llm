# G1 native-name normalization and counterfactual five-scene scoring

**No model calls in this change.** The immutable historical GPT-6 Luna run
remains 2/6 with status INCOMPLETE. Separate 3/3 native scene recoveries make
5/6 a *counterfactual*, not a measured production rate. Their shape quality is
UNKNOWN until the private offline scorer runs.

## Normalization in normal workflows

The default compiler compile_bpy_subset(source) remains historically strict.
Only the live G1 path and future benchmark runner opt in with
compile_bpy_subset(source, normalize_names=True). The permitted AST subset and
safe Blender builder stay unchanged: generated Python is never executed.

- Preserve all valid mesh names. Literal invalid printable names of up to 128
  Unicode characters become deterministic ASCII slugs, capped at 48 characters.
  Non-Latin-only names get part_NNN.
- Distinct labels colliding after normalization receive deterministic suffixes
  (__2, __3), without overwriting an originally valid name. Identical original
  names fail closed instead of silently gaining different identities.
- Reject control/bidi characters, separators, oversized labels, computed name
  expressions, unauthorized imports/loops/calls and original duplicate names.
- Each part carries a frozen-source ordinal ID mesh_NNN. The private scene-spec
  records original label, normalized name, ID and changed flag. The audited
  Blender builder persists the ID and the independent inspector checks it.
  IDs are stable for a fixed primitive order, not across source reordering.

This cannot rescue BrainCoral's reasoning-token exhaustion, nor guarantee that
an accepted shape matches the text description. G1's table semantic checker
still requires tabletop and leg_1 to leg_4 rather than inferring them from labels.

## Run on the authorized Mac after PR merge

All prerequisites already exist in the private operator evidence folders from
the prior experiments. Requires Blender, the original two-scene scorer stage,
all six verified reference GLBs, pinned upstream scorer and isolated Python
dependencies (numpy, scipy and trimesh).

    cd ~/Projects/3d-rendering-llm
    git pull --ff-only
    export PYTHONPATH=src
    python3 -m geometry_harness.evaluation.counterfactual_shape \
      --original "$HOME/geometry-evidence/luna-six-original/historical-evidence" \
      --baseline-stage "$HOME/geometry-evidence/luna-six-shape-stage" \
      --derived "$HOME/geometry-evidence/luna-six-native-name-ablation-01" \
      --out "$HOME/geometry-evidence/luna-six-five-scene-shape-01" \
      --upstream "$HOME/geometry-evidence/scorer/3dcodebench" \
      --refs "$HOME/geometry-evidence/luna-six-reference-glbs"

Use a new --out on every **new export** attempt; never point it at the
original bundle or the original scorer stage. Before running Blender, the CLI independently validates
original audit/cost, original pinned scorer provenance, hashes of both existing
generated GLBs, hashes of every derived native artifact, deterministic name-only
source transform, original SHA and reopened geometry/mesh names.

It then copies the original **generated** two GLBs and exports only the three
accepted derived .blend scenes through the audited Blender exporter with
--disable-autoexec. The pinned six-instance scorer runs with the *same six*
scorer-only references. BrainCoral stays NO_GEN_GLB. The command never executes
model-authored code or sends requests to the model.

Outputs: separate scorer-staging.json, shape-scorer-provenance.json, raw upstream
shape_chamfer.json and counterfactual-shape-results.json. The last report gives
per-task CD/yaw-min, conditional and penalized means, and checks identical
reference/scorer hashes and reproducibility of the two original CD/yaw-min
values to absolute 1e-6. On mismatch, the score claim remains UNKNOWN and the
command fails. Omit --upstream/--refs to stage only; that leaves quality UNKNOWN.

**Comparison limitations:** Five-scene conditional mean is a different
successful-task subset, not a paired improvement over the old two-scene mean.
The scorer's penalized mean depends on the cohort's worst valid CD and cannot
be compared as if the penalty were fixed. Use per-task matched scores and
execution coverage separately. Chamfer omits semantic/visual quality and does
not confer an official 3DCodeBench leaderboard result.

The remaining gates are real Mac native E2E of stable IDs and a human-reviewed
reference/render comparison. BrainCoral none-vs-low remains a separately
authorized paid experiment.


## Recover from missing pinned scorer after exports were staged

If the first attempt printed "Scorer staging and pinned upstream script required",
the five GLBs are likely already exported. **Do not delete that output**. The
initial version performed the path check *after* creating output, which made a
simple rerun fail with "output already exists". This version checks the scorer
and reference paths **before** exporting and adds a guarded --resume option.

Locate the actual checkout on the same Mac (the original 2/6 score used it):

    find "$HOME/geometry-evidence" "$HOME/Projects" \
      -type f -name shape_chamfer.py -print 2>/dev/null

The correct --upstream value is the directory *above* metrics/, with a real
metrics/shape_chamfer.py script, at git commit
42c7780ed3fcbd466f17f058f62e7996233777f7. Check with
`git -C "/path/to/checkout" rev-parse HEAD`. Do **not** supply a different
version or bypass the commit/hash gate.

After pulling the new feature branch, re-use the existing export stage without
running Blender again:

    cd ~/Projects/3d-rendering-llm
    git pull --ff-only
    export PYTHONPATH=src
    python3 -m geometry_harness.evaluation.counterfactual_shape \
      --resume \
      --original "$HOME/geometry-evidence/luna-six-original/historical-evidence" \
      --baseline-stage "$HOME/geometry-evidence/luna-six-shape-stage" \
      --derived "$HOME/geometry-evidence/luna-six-native-name-ablation-01" \
      --out "$HOME/geometry-evidence/luna-six-five-scene-shape-01" \
      --upstream "/ACTUAL/PINNED/3dcodebench/ROOT" \
      --refs "$HOME/geometry-evidence/luna-six-reference-glbs"

Resume re-audits the private original/native source provenance, six staged
task rows and hashes of all five generated GLBs, checks the two originals are
byte-identical to the frozen baseline, verifies each derived expected-ID export
and refuses any prior scorer output. It does **not** overwrite GLBs, re-export
or regenerate scenes; it scores only the existing verified stage. Resume itself
never calls Luna. It refuses a partial/tampered stage; in that case preserve
the failed output as evidence and use a **new** --out after fixing preflight.

## When the finished scorer reports an unpaired baseline (2026-10-28)

The original pinned upstream script uses `rng = np.random.default_rng(seed)`
**once for all tasks**, then draws two random surface sample seeds for each
present reference+generated mesh. Its alphabetical iteration order means that
making previously missing AquariumTank, ArmChair and Bottle GLBs present
changes the RNG state used for Balloon and CoffeeTable. Merely re-running
with global `--seed 0` does **not** guarantee byte-identical per-task CD
across a two-scene vs five-scene cohort. The strict `1e-6` matching gate
therefore fails **even when source/ref GLB bytes and pinned script are
unchanged**. This is a protocol mismatch, not evidence of tampering by itself.
Never increase the tolerance arbitrarily to make it pass.

The original reporting command wrote
`counterfactual-shape-results.json` with UNKNOWN and null per-instance
scores on this gate failure; the **actual upstream** per-scene scores remain
preserved in the separate raw private
`results/text_to_3D/gpt-6-luna/_metrics/shape_chamfer.json`.

A read-only diagnosis is available after updating the branch:

    cd ~/Projects/3d-rendering-llm
    git pull --ff-only
    export PYTHONPATH=src
    python3 -m geometry_harness.evaluation.counterfactual_shape \
      --diagnose-existing \
      --original "$HOME/geometry-evidence/luna-six-original/historical-evidence" \
      --baseline-stage "$HOME/geometry-evidence/luna-six-shape-stage" \
      --derived "$HOME/geometry-evidence/luna-six-native-name-ablation-01" \
      --out "$HOME/geometry-evidence/luna-six-five-scene-shape-01" \
      --upstream "$HOME/geometry-evidence/3dcodebench-scorer" \
      --refs "$HOME/geometry-evidence/luna-six-reference-glbs"

It does **not** invoke the scorer again, change files, export Blender, or use
model APIs. It independently checks original/derived evidence and stage hashes,
scorer script+commit, and all six reference hashes. If those match and exactly
5/6 per-instance statuses are scored, it returns
`DESCRIPTIVE_5_SCENES_NOT_PAIRED` with the genuine per-task CD, yaw-min,
and baseline drift. If provenance fails, the metric remains UNKNOWN/null.

**This is not a new paired benchmark acceptance.** Before reporting precise
same-protocol differences across runs, score every scene under independent
per-task RNG initialization in an isolated scratch cohort, invoking the
unchanged pinned scorer once per task. Compute a *new* per-task-seeded
baseline and counterfactual, never overwrite the historical run. Repeatedly
running the existing six-task scorer with `--seed 0` does not solve it.

## Actual operator 5-scene shape observations (2026-10-28)

The authorized operator completed frozen scorer and reference verification
(`frozen_scorer_matches=true`, `frozen_references_match=true`) and
independently confirmed **5/6 generated GLBs**. The original 2/6 paid source
status remains immutable. This is an **observed descriptive, unpaired**
five-scene Chamfer run; source code, reference GLBs and full prompts remain
private and are not copied to this repository.

| Task | Source | CD | CD yaw-min | Status |
| --- | --- | ---: | ---: | --- |
| AquariumTank_seed0 | recovered name-only | 0.04923519730128536 | 0.028346598152854535 | OK |
| ArmChair_seed0 | recovered name-only | 0.03720740155858683 | 0.03720740155858683 | OK |
| Balloon_seed0 | original | 0.6380648866633449 | 0.5785731185346104 | OK |
| Bottle_seed0 | recovered name-only | 0.013277971985460558 | 0.013277971985460558 | OK |
| BrainCoral_seed0 | unrecovered token exhaustion | N/A | N/A | NO_GEN_GLB |
| CoffeeTable_seed0 | original | 0.044120591181097436 | 0.044120591181097436 | OK |

The observed five-scene **conditional mean CD** is
`0.15638120973795502`, with **run-relative penalized mean CD**
`0.2898338964474654`. These are not official leaderboard scores and
MUST NOT be portrayed as a causal quality improvement from the old two-scene
conditional mean (`0.33838396924096587`) or old dynamic penalized mean
(`0.7474027587207573`): different accepted subset and advancing sampling
RNG. Balloon dominates the distance; its geometry should be reviewed
separately. Even low CD does not prove prompt-specific shape semantics,
proper real-world dimensions, materials or detailed visual fidelity.

The two original tasks had historical CD `0.04215983617482963`
(CoffeeTable) / `0.6346081023071021` (Balloon) but newly observed
`0.044120591181097436` / `0.6380648866633449`. The exact original
pair score gate fails as expected when the upstream scorer advances one RNG
across the now-five successful tasks; no reference/scorer provenance mismatch
was observed.

### A new reproducible per-task sampling protocol (operator action pending)

The repo now includes `geometry_harness.evaluation.paired_task_shape`: it
first **revalidates the entire same private evidence chain** and the published
frozen scorer script, then runs the *unchanged* pinned scorer in independent
temporary result roots **once per task** with seed 0 and 8192 sample points.
It includes both baseline and candidate GLB scoring for CoffeeTable/Balloon
to verify exact same-seed scores; then scores the three recovered candidates
independently. BrainCoral remains missing. The output has a new protocol
name, separated from all prior runs. No API calls, new Blender exports,
new reference downloads or edits of existing evidence are involved.

From the same authorized Mac, in the isolated `scorer-env`:

    cd ~/Projects/3d-rendering-llm
    git pull --ff-only
    export PYTHONPATH=src
    ROOT="$HOME/geometry-evidence"
    python3 -m geometry_harness.evaluation.paired_task_shape \
      --original "$ROOT/luna-six-original/historical-evidence" \
      --baseline-stage "$ROOT/luna-six-shape-stage" \
      --derived "$ROOT/luna-six-native-name-ablation-01" \
      --existing-stage "$ROOT/luna-six-five-scene-shape-01" \
      --upstream "$ROOT/3dcodebench-scorer" \
      --refs "$ROOT/luna-six-reference-glbs" \
      --out "$ROOT/luna-six-per-task-chamfer-01"

The fresh output contains `paired-one-task-chamfer.json`, plus isolated
raw metric JSON, generated GLB SHA and stdout/stderr for each of **7 scorer
invocations** (2 original baseline + 5 candidate). Keep this output **private**.
The baseline and counterfactual conditional means still cover 2 vs 5 valid
scenes and are not identical-task paired *quality improvements*. This new
protocol gives invariant per-task sampled CD regardless of task omissions;
the original run's historical CD remains unchanged.
