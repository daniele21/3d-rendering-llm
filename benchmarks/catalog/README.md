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
