# Six-task Luna evidence audit (BH-02 first slice)

Status: implemented artifact inspector. **Private historic GCS bundle verified by authorized operator on 2026-10-28 (27/27 objects; 6 task records, 2 native Blender PASS; USD $0.004875300 estimated). NOT an official 3DCodeBench shape/image scorer.** Does not rerun a model, execute AI Python, or retrieve scorer-private reference factories.

## Evidence gate

Provide a local copy of the immutable G1 benchmark bundle. The auditor verifies the exact six IDs, dataset SHA, Luna model, all SHA256 and sizes, one per-task record for each ID, absence of reference factory scripts, and numeric per-call costs recalculated from the *original ledger* (not just the saved report). An accepted native result must contain the hashed .blend signature, independent Blender geometry-inspection JSON and preview PNG. It reports PASS/FAIL/UNKNOWN with the unchanged six-task denominator, and makes a standalone HTML gallery with previews only for verified scene artifacts. It leaves independent image/shape scores as UNKNOWN.

Run after a private-bucket reader has copied the original g1-benchmark directory:

    PYTHONPATH=src python3 -m geometry_harness.evaluation.benchmark_evidence --root /private/g1-benchmark --out /private/luna-review
    open /private/luna-review/index.html

Historic private GCS prefix:
gs://project-tests-498508-geometry-showcase/geometry-harness/g1/be1a888dea819925cb855d95c18f4d75c0e934ce/40683850012-attempt-1/g1-benchmark/

Original run 40683850012: six real Luna API calls, 2 native Blender PASS outcomes, model-token estimate USD 0.004875300. Cost ledger COMPLETE, GCS upload step succeeded, but final strict workflow FAILED because benchmark status was INCOMPLETE. The offline audit cannot rewrite that history.

## Official upstream scorer — separate gate

The 3DCodeBench upstream repository https://github.com/gaoypeng/3dcodebench documents executability, shape_chamfer, failure_taxonomy and image similarity using SigLIP-2/DINOv3, shape Uni3D and optional LLM judge. Upstream expects Blender 5.0 and its own generated Python / GLB artifact conventions; our current narrow AST geometry uses Blender 5.2.3 and native .blend + PNG. Similarity figures are **not comparable** without a reviewed, pinned environment and correct reference rendering/mesh protocol.

Next steps: pin official scorer SHA, dependencies and licence terms; keep hidden reference factories in a separate restricted scorer environment (no unsafe Python execution on shared Mac). Implement trusted GLB export from accepted native scene and independently verify geometry, scale, task ID and failure policy. Test upstream scorers on known accepted/rejected/unknown cases and only then score the original Luna scene outputs without redoing paid inference. Report every missing or unsupported metric as UNKNOWN, never fabricated zero.

**This PR does not claim official 3DCodeBench quality.**

## Operator-run native GLB staging — verified 2026-10-28

The operator executed the existing trusted exporter against the **previously audited** six-task Luna source bundle. The result is a locally generated `scorer-staging.json` with `model_calls=0`, `new_api_cost_estimate_usd="0"`, `original_run_status="INCOMPLETE"`, and `scoring_status="NOT_RUN_NO_REFERENCE_GLBS"`.

| Task ID | Native scene | Exported GLB | SHA256 |
| --- | --- | ---: | --- |
| `CoffeeTable_seed0` | PASS | 60,724 bytes | `9172fd95b587f52374233d6d9788106a418f400074a8ffcc144402be7a0d1345` |
| `Balloon_seed0` | PASS | 746,316 bytes | `10224636e4c2de720d1a664dd54efe656fddcc340c52bf01d4ad3f33eddd6bb3` |
| `ArmChair_seed0`, `Bottle_seed0`, `AquariumTank_seed0`, `BrainCoral_seed0` | UNKNOWN | Not generated | No fabricated GLB/quality metric |

The six-task denominator and model token estimate USD $0.004875300 are unchanged. This export demonstrates that the **two previously accepted** native scenes can be handed to a separate reference scorer. It does NOT establish prompt fidelity, mesh similarity, reference equivalence or an official 3DCodeBench score.

### Next scoring gate: provenance-matched reference GLBs

The pinned upstream [Chamfer scorer](https://github.com/gaoypeng/3dcodebench/blob/42c7780ed3fcbd466f17f058f62e7996233777f7/metrics/shape_chamfer.py) expects `--results-root` and `--data-root`, 8192 sampled surface points by default, independently unit-sphere-normalized point clouds and four yaw orientations. It writes a six-task report with `n_ok`, per-task status, conditional and penalized mean. **The penalized mean is run-relative**, so it must not be compared across unrelated cohorts or protocol versions.

Potential reference sources: the 3DCodeBench benchmark's own `YipengGao/3DCode` reference factories (not to be executed in the shared generator environment) and the separately published [3dcodebench/3dcodebench](https://huggingface.co/datasets/3dcodebench/3dcodebench) release containing GLBs and prompts in a compressed archive (about 1.95 GB). Before scoring, compare the **exact public prompt bytes** of all six entries against our pinned `YipengGao/3DCode@b70b4ee54b93fab76596da5809f3e71c617fa5c2` freeze, verify reference mesh integrity and pin the other release revision; do not assume equivalence from matching instance names. The broader `3DCodeData/` includes 12,720 seeded training instances whose geometry is also **not automatically identical** to the canonical `_seed0` benchmark tasks.

Run `upstream_shape_adapter --upstream ... --refs ...` **only after** the six scorer-private GLBs have been validated. Record both a conditional score (only valid meshes) and a six-task failure-inclusive score, while preserving each missing task's original `UNKNOWN` status in the native execution report. Even a successful Chamfer calculation remains **NONCOMPARABLE to the upstream official code-executability leaderboard** because this experiment uses a strict AST subset and Blender 5.2.3 rather than the upstream free-Python Blender 5.0 execution path.

## Trusted upstream shape scorer bridge (Wave 2)

[PR #49](https://github.com/daniele21/3d-rendering-llm/pull/49) adds a native .blend → GLB exporter executed only from audited source with Blender autoexec disabled, and an adapter for upstream 3DCodeBench `metrics/shape_chamfer.py` pinned at Git commit `42c7780ed3fcbd466f17f058f62e7996233777f7`. Positive native export and source non-mutation verified in [Mac run 40698095542](https://github.com/daniele21/local-runner-infra/actions/runs/40698095542). The adapter refuses scoring without every expected real scorer-private reference GLB, a matching repository commit and six-task denominator. It does **not** execute hidden reference factory Python or any LLM Python on the Mac mini.

After authorized read-only retrieval of historical GCS evidence, staging can run locally without any new model calls:

```bash
PYTHONPATH=src python3 -m geometry_harness.evaluation.upstream_shape_adapter \
  --input /private/g1-benchmark --out /private/luna-shape-stage
```

Scoring (only on reviewed isolated environment with six *pre-generated trusted reference GLBs* and pinned upstream checkout):

```bash
PYTHONPATH=src python3 -m geometry_harness.evaluation.upstream_shape_adapter \
  --out /private/luna-shape-stage \
  --upstream /private/scorer/3dcodebench \
  --refs /private/scorer/reference-meshes
```

Upstream shape metric is relative to its references; **our narrow AST code execution is not the upstream Blender 5.0 free-Python execution protocol**. The code explicitly labels outputs NONCOMPARABLE to the official reference leaderboard until a compatible version/profile and tasks are verified. The six Luna historical outputs have not yet been scored.

## Operator GLB staging completed — 2026-10-28

The operator ran `geometry_harness.evaluation.upstream_shape_adapter --input ... --out ...`
against the previously audited six-task private bundle. This is an **actual operator run**,
not a repository CI run, and it did **not** call an AI model.

- Output directory: `~/geometry-evidence/luna-six-shape-stage/` (also a second immutable
  staging run under `~/geometry-evidence/luna-shape-6fiBlR1c/stage/`).
- Original source revision: `be1a888dea819925cb855d95c18f4d75c0e934ce`;
  frozen data revision `b70b4ee54b93fab76596da5809f3e71c617fa5c2`.
- `CoffeeTable_seed0`: **60,724-byte** exported GLB,
  SHA-256 `9172fd95b587f52374233d6d9788106a418f400074a8ffcc144402be7a0d1345`.
- `Balloon_seed0`: **746,316-byte** exported GLB,
  SHA-256 `10224636e4c2de720d1a664dd54efe656fddcc340c52bf01d4ad3f33eddd6bb3`.
- `ArmChair_seed0`, `Bottle_seed0`, `AquariumTank_seed0`,
  `BrainCoral_seed0`: no native accepted scene and no generated GLB;
  remain explicitly `UNKNOWN`, not an invented empty/zero-valued mesh.
- Staging status: `NOT_RUN_NO_REFERENCE_GLBS`,
  `model_calls=0`, `new_api_cost_estimate_usd=0`.
  Original run remained `INCOMPLETE`, with recorded estimated model-token
  cost USD `0.004875300`.

**Next acceptance gate:** obtain a consistent set of **six scorer-private reference
GLBs**, verify each prompt against the pinned 3DCodeBench source and check
Blender/scorer version comparability. The separate
`3dcodebench/3dcodebench` tar archive (about 1.95 GB) includes reference GLBs
and prompts, but it is a different release; never assume equivalence without
per-task content checks. Do not run reference factory Python or create an
"official score" from the two exported GLBs alone.


## Real public six-reference equivalence PASS — 2026-10-28

[Hosted zero-LLM public provenance CI run 40714389048](https://github.com/daniele21/3d-rendering-llm/actions/runs/40714389048) completed **SUCCESS**. It fetched both exact Hugging Face dataset revisions, streamed the full public ~1.95 GB archive, and verified for **all six** task IDs:

- description and instruction bytes match the frozen source revision;
- ground-truth factory script bytes match the same frozen source;
- a well-formed reference GLB exists under `data/<task>/glb/<task>.glb`;
- the full compressed archive SHA-256 matches the published archive metadata:
  `459944518cb6e5f2a1f8de70ab273f557f4fe243b5dba7b44bb50c0e7b9563bc`.

The run uploaded only a **public, 1.8 KB provenance JSON artifact** containing hashes: **no meshes, scripts, private GCS data, paid model calls or benchmark scores**. Initial real CI attempts exposed Hugging Face cache symlinks and the public archive's nested `glb/` layout. The final runner fixes these while retaining fail-closed handling of supplied symlinks and of archive mismatches. Offline contracts passed on the final SHA.

**This certifies six reference input identities, not Luna shape similarity.** Ground-truth mesh render correctness, Blender 5.0 comparability and the two generated GLB shapes versus these references remain to be scored.

### Next: scorer-only local setup (existing operator's Mac)

The operator's original six Luna outputs have already been exported privately to:
`~/geometry-evidence/luna-six-shape-stage/` (CoffeeTable + Balloon GLBs;
four other task outputs remain without valid native scenes).

On the authorized machine only, outside the generator's worktree:

```bash
cd ~/Projects/3d-rendering-llm
git pull --ff-only
python3 -m venv ~/geometry-evidence/scorer-env
source ~/geometry-evidence/scorer-env/bin/activate
python -m pip install "huggingface_hub>=0.30,<2" "numpy>=1.26" "scipy>=1.11" "trimesh>=4.0"

PYTHONPATH=src python -m geometry_harness.evaluation.reference_provenance \
  --download-archive \
  --out ~/geometry-evidence/luna-six-reference-glbs

git clone https://github.com/gaoypeng/3dcodebench.git \
  ~/geometry-evidence/3dcodebench-scorer
git -C ~/geometry-evidence/3dcodebench-scorer checkout \
  42c7780ed3fcbd466f17f058f62e7996233777f7
PYTHONPATH=src python -m geometry_harness.evaluation.upstream_shape_adapter \
  --out ~/geometry-evidence/luna-six-shape-stage \
  --upstream ~/geometry-evidence/3dcodebench-scorer \
  --refs ~/geometry-evidence/luna-six-reference-glbs
```

The reference download may transfer approximately **1.95 GB** (plus the 18
small source text/factory files) and uses local disk cache. It must not be
performed on every CI push or on a model-executing shared runner. The
`upstream_shape_adapter` verifies both source and scorer code SHA before
launching the pinned, externally sourced scorer process; keep it in a separate
restricted environment and never supply model API credentials. Output should
include `shape-scorer-provenance.json` and upstream `shape_chamfer.json`.
Conditional and penalized scores must be reported together, including the
four missing generated GLBs; the result is an *internal noncomparable
Blender 5.2.3/safe-AST profile*, not official 3DCodeBench leaderboard rank.
