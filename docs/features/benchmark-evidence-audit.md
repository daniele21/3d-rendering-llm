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
