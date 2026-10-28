# 3DCodeBench benchmark data adapter

Track [BH-01 #4](https://github.com/daniele21/3d-rendering-llm/issues/4). This
module is **not** a benchmark result or an official scorer. It performs
deterministic, leak-safe catalog discovery on a separately downloaded
3DCodeBench evaluation dataset.

1. Pin an exact Hugging Face dataset revision (40-hex commit), review the
   evaluation dataset's licensing and Infinigen attribution, and fetch
   only the `3DCodeBench/` directory to an **ignored external cache**.
2. Run:

   ```bash
   python3 benchmarks/catalog/select_suites.py \
      --root /external/cache/3DCodeBench \
      --dataset-revision EXACT_HF_DATASET_COMMIT \
      --output /external/artifacts/3dcodebench-suites.json
   ```

3. The catalog requires a real 24+ directory input; the smoke/core sets are
   deterministic but **provisional and unstratified** until a reviewer curates
   category coverage. Provide `--curated review.json` with arrays
   `{"smoke":[6 IDs],"core":[24 IDs]}`; smoke must be a subset of core.
   Do not describe provisional selections as representative.
4. **Crucial:** generated manifests contain only category IDs and hashes of
   the two public prompt files, not the factory code or reference geometry.
   Never mount `3DCodeBench/<task>/*.py` or scorer reference images into
   the generator context. Dataset code, independent scoring and local files
   belong on the scorer side of the trust boundary.
5. Blender 5.0 is required for an upstream-comparable suite. Smoke/core
   scoring stays blocked until real runtime/data rights and model E2E exist.
   Other Blender versions must use separate score profiles.

The benchmark repository source is Apache-2.0, but its dataset is a separately
distributed asset built on Infinigen. Track dataset rights separately from
code license. P3D-Bench code is MIT while its data is non-commercial; never
import that dataset blindly into commercial product tests.


## Stage generator-visible public prompts only (no ground truth)

The upstream [3DCodeBench benchmark documentation](https://github.com/gaoypeng/3dcodebench/blob/main/benchmark/README.md) confirms 212 directories named `<Name>_seed0`, each containing `prompt_description.txt`, `prompt_instruction.txt` and the held-out `<Name>_seed0.py` factory. The [Hugging Face dataset card](https://huggingface.co/datasets/YipengGao/3DCode) labels the overall release MIT and states factory scripts retain **Infinigen BSD-3-Clause** provenance. Confirm downstream redistribution and benchmark use in context; do not ingest hidden reference script in the model-facing workspace.

Pin an actual dataset commit SHA (not `main`) after downloading only the `3DCodeBench/` tree to a separate restricted location. Never commit the factory files, reference images or bulky datasets to this source repo.

Generate a catalog with the exact source revision:

```bash
python3 benchmarks/catalog/select_suites.py \
  --root /private/3dcodebench/3DCodeBench \
  --dataset-revision FULL_40_HEX_HF_DATASET_COMMIT \
  --output runs/benchmarks/suites-provisional.json
```

Stage only the six public-text prompts, validating exact bytes and hashes against the manifest:

```bash
python3 benchmarks/catalog/stage_prompts.py \
  --dataset-root /private/3dcodebench/3DCodeBench \
  --suite runs/benchmarks/suites-provisional.json \
  --tier smoke \
  --out runs/benchmarks/generator-smoke
```

The generator workspace receives **only** `prompt_description.txt`, `prompt_instruction.txt` and `staging-manifest.json`; **no** `.py` reference factory, image, mesh or scoring metadata. The tool refuses to overwrite output, refuses symlinks, checks UTF-8, task IDs, prompt size and SHA256. The separate scorer must work outside this directory with separately controlled reference access. No upstream scorer is invoked by this staging operation and it does not produce quality scores.

**Current limitation:** `select_suites.py` produces a deterministic provisional but unstratified 6/24 selection by ID hash unless a reviewed curated file is provided. This is **not yet a frozen 3DCodeBench smoke baseline**. Before publishing numbers: verify actual dataset revision/rights, inspect category diversity, pin Blender 5.0 and official metric conditions, and run the task generator+independent scorer. Current G1 real table is a separate *internal smoke*, not leaderboard evidence.
