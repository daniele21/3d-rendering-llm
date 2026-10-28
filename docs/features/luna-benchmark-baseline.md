# S1 experimental baseline: GPT-6 Luna + pinned 3DCodeBench

**Model contract from 2026-10-28 onward:** `gpt-6-luna`, the official published OpenAI API identifier. `gpt-6.1-luna` is not a documented API model and **must not be silently substituted**. Prior `gpt-6.1-sol` runs and their historical tariffs remain immutable baseline evidence. If OpenAI later publishes a 6.1 Luna model, separately review its model ID, endpoint, pricing and key access before a migration.

## Frozen public benchmark input

Hugging Face dataset: `YipengGao/3DCode` at exact SHA
`b70b4ee54b93fab76596da5809f3e71c617fa5c2`.

Verified in a real no-inference GitHub Actions job: [pinned freeze](https://github.com/daniele21/3d-rendering-llm/actions/runs/40682618911) — **212 categories; six public task IDs, 12 prompt files**, no hidden reference factories or code exposed in the generator's workspace. Suite SHA256:
`79904d4e83e9075cd08337a99c28d5dbcc00743cc790d37123ed9b7c776a7cd8`.

Frozen six:
1. `CoffeeTable_seed0`
2. `ArmChair_seed0`
3. `Bottle_seed0`
4. `AquariumTank_seed0`
5. `Balloon_seed0`
6. `BrainCoral_seed0`

The first six are intentionally heterogeneous in geometry (furniture, containers, hardware, inflatable and organic), so some **must be expected to fail** the limited cube/cylinder/UV sphere AST dialect. The remaining 18 core tasks are provisional deterministic selections and **not a curated representative 24-task cohort**. The upstream scorer and true task fidelity metrics are not yet integrated.

Source dataset card [3DCode](https://huggingface.co/datasets/YipengGao/3DCode) currently lists MIT and describes Infinigen BSD-3-Clause provenance for factory code. Review notices/re-use rights before redistribution or commercial benchmarking. Reference scripts are held in a temporary scorer-only source folder and deleted immediately after public prompt staging.

## First live run — 2026-10-28

[Central GitHub Actions run 40683850012](https://github.com/daniele21/local-runner-infra/actions/runs/40683850012): six real `gpt-6-luna` API calls, **2/6** accepted native Blender scenes, estimated model token spend **USD $0.004875300**. Provider cost ledger `COMPLETE`, all six attempts counted. Private GCS upload step SUCCESS; **strict CI gate FAILED**, because the initial source erroneously counted the last billable failed task as making the six-task suite incomplete. Corrected for future experiments in [PR #32](https://github.com/daniele21/3d-rendering-llm/pull/32) without running another paid inference. The historical failed run remains unchanged.

The observed pass fraction is an INTERNAL safe-AST native-scene metric, **not official visual/3DCodeBench shape or semantic similarity**; those remain UNKNOWN. No quality-improvement comparison to Sol is valid yet, as earlier Sol trials used a different prompt.

GCS evidence prefix (private):
`gs://project-tests-498508-geometry-showcase/geometry-harness/g1/be1a888dea819925cb855d95c18f4d75c0e934ce/40683850012-attempt-1/g1-benchmark/`

Read without additional model calls (requires your GCS reader permissions):

```bash
ROOT="gs://project-tests-498508-geometry-showcase/geometry-harness/g1/be1a888dea819925cb855d95c18f4d75c0e934ce/40683850012-attempt-1/g1-benchmark"
gcloud storage cat "$ROOT/benchmark.json" | jq '{status,attempted,scene_passes,aborted_reason,task_results}'
gcloud storage cat "$ROOT/cost-summary.json" | jq '{grand_total_status,recorded_calls,priced_subtotal_usd,by_model_stage}'
```

Combined eight recorded API calls: 2 historical Sol ($0.018374000) + 6 Luna ($0.004875300) = **USD $0.023249300** model-token estimates, NOT provider billing/infra invoices.

## First experiment contract

`python -m geometry_harness.benchmark_smoke --output ... --public-root ... --suite ...`

- Paid **manual-only** request on the dedicated Mac mini, explicit user-approved source main SHA and exactly **six** maximum calls to `gpt-6-luna`. No retries. No free/automatic inference from push CI.
- Each request has prompt hash/call ID, stage+task ID in append-only cost ledger, total/uncached/cached-read/cache-write/output/reasoning tokens, model actually returned, timestamp, duration, tariff snapshot and USD estimate. Calls with missing usage are UNKNOWN and stop subsequent paid requests.
- Conservative pre-call upper bound, 2048 output tokens per request, accumulated model-token estimate ≤$0.05; **this is a code-layer guard for API tokens only, not a platform billing hard-stop, and excludes other cloud charges**.
- AI-authored Python is **never executed**. It is parsed into literal bounded cube/cylinder/UV sphere specifications or rejected; only trusted in-repo Blender builder runs. Independently reopen `.blend`, verify named parts/locations/dimensions and PNG. Reject unsafe syntax; preserve unsuccessful attempts and their costs.
- **Only internal metric:** native executable scene rate, with the real denominator 6 and FAIL/UNKNOWN tracked per task. Upstream image similarity, Chamfer, Uni3D, judge and functional prompt fidelity remain **UNKNOWN**, no official leaderboard claim. Potentially very low score is a valid outcome.
- Final evidence needs a private GCS bundle with cost JSONL + summary, per-task output and failure files, a manifest containing SHA-256, exact source/dataset SHA and model; upload **on failure** and require object presence. Source repo commits only configuration and test code, never provider secrets/model outputs.
- Prior two Sol calls cost estimated **$0.018374000** (not invoice). Any Luna spend is a **new independent accounting series**, never rewrite Sol records.

## Reproducible public dataset prep

The no-cost dataset preparation workflow `.github/workflows/geometry-upstream-dataset-freeze.yml` uses the pinned revision and restricts the generator workspace to `prompt_description.txt`, `prompt_instruction.txt`, and staging manifest. It publishes only small metadata artifacts for independent review. To prepare locally, install `huggingface_hub` into a **temporary virtual environment**, then run:

```bash
python benchmarks/catalog/freeze_real.py \
  --output runs/benchmarks/pinned-real-smoke
```

Keep fetched upstream reference Python and visual targets outside the generator execution workspace. No paid test is automatically triggered by the freeze.
