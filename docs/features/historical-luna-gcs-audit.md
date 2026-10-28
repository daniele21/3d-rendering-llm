# Historical six-task Luna audit — operator-only retrieval

**Status:** reproducible read-only audit helper implemented, but **NOT executed against GCS** here. The CI service account `geometry-g0-uploader@project-tests-498508.iam.gserviceaccount.com` has only bucket-scoped `roles/storage.objectCreator` (see `local-runner-infra/scripts/bootstrap_geometry_gcs.sh`). It has **no** `storage.objects.get` or `storage.objects.list`. Do not widen CI service-account IAM, publish bucket contents or copy provider secrets into Actions solely for the audit.

## With an already-authorized personal GCS reader

```bash
# Auth on trusted operator machine; use an existing user with private-bucket read rights
gcloud auth list
gcloud storage ls 'gs://project-tests-498508-geometry-showcase/geometry-harness/g1/be1a888dea819925cb855d95c18f4d75c0e934ce/40683850012-attempt-1/g1-benchmark/'
PYTHONPATH=src python3 -m geometry_harness.evaluation.historical_luna \
  --out ~/geometry-evidence/luna-six-original-readonly-20261028
open ~/geometry-evidence/luna-six-original-readonly-20261028/review/index.html
```

If the operator has only a previously downloaded **private** bundle, the no-network mode is:

```bash
PYTHONPATH=src python3 -m geometry_harness.evaluation.historical_luna \
  --source-local /private/g1-benchmark \
  --out ~/geometry-evidence/luna-six-local-review
```

This **does not** trigger Luna or rerun 3DCodeBench. It verifies original SHA256, the exact six task IDs, ledger/cost consistency and native Blender pass artifacts; reports the original CI state as **INCOMPLETE**, keeping its cost ledger `COMPLETE`. Expected historic evidence from logs: six billed calls, 2/6 native scenes and estimated USD 0.004875300. These are **not new verified audit results** until a reader runs the tool.

## Reference mesh sourcing decision

Two sources must not be conflated:

1. Pinned current generator benchmark: `YipengGao/3DCode` at `b70b4ee54b93fab76596da5809f3e71c617fa5c2`. Its `3DCodeBench/` contains prompt text and reference Blender 5.0 Python **but not already-rendered GLBs**. We must not execute the factory Python on the shared Mac mini.
2. Separately released `3dcodebench/3dcodebench` archive on Hugging Face: documented `data/<Category>_seed0/glb/<Category>_seed0.glb` and matching reference views. It is around **1.95 GB** compressed. Its license card says BSD-3-Clause, whereas the pinned `YipengGao/3DCode` dataset card reports MIT with upstream Infinigen BSD-3 code lineage. **Treat these as separate revisions/releases; do not download the 1.95 GB archive into the source repo, do not assume prompt/mesh equivalence, and do not report official comparable Chamfer until source hashes, script/caption identities and render profiles are independently checked.**

Upstream official scorer commit pinned by the bridge: `42c7780ed3fcbd466f17f058f62e7996233777f7`. Historic metric remains `UNKNOWN_NOT_RUN` until a private scorer obtains six validated references and a matching evaluation profile.

Sources: https://huggingface.co/datasets/YipengGao/3DCode and https://huggingface.co/datasets/3dcodebench/3dcodebench and https://github.com/gaoypeng/3dcodebench .

**Security:** No broad IAM `objectViewer` role should be granted to a model-executing runner. Prefer an already-authorized operator to download *only* the exact historic six-task bundle into private storage, review it, and keep reference meshes in a distinct scorer-owned directory.
