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
