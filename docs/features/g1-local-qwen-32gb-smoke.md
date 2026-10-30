# G1 local 32 GB Mac — Qwen3-Coder GGUF via Korgis

**State: implemented and offline CI-tested; no actual operator model inference
on this Mac has been verified.** This is a separate experiment stacked on
PR #66's deterministic AST name-normalization branch. It does not rewrite
the historical Luna 2/6 result or the independently measured 5/6 derived
counterfactual. No remote model API calls and no automatic cloud fallback.

## Frozen model and on-device boundary

Already downloaded privately on the operator Mac:

    ~/.lmstudio/models/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf

Do not copy the file, invent a model revision or commit the absolute user
path. Korgis uses the `llama_server` backend (llama.cpp / Metal) and serves
its OpenAI-compatible API only at `127.0.0.1:1235`; the app is not allowed
to override or redirect the host. The GGUF is Q4_K_M (~19 GB weights),
but actual RAM usage also includes runtime buffers, macOS, KV cache and Blender.
On the 32 GB Mac, start with context **8192**, output **2048** for a
Luna-budget-matched probe, single request, seed **42** and temp **0.1**.
The model's runtime must be checked for swap pressure before extending output
to 4096 or increasing task count.

**Korgis nuance:** its public admin endpoint refuses to unload the *last*
resident model, by design. Therefore the geometry run is **two-phase**:
generate and safe-compile while Korgis is running; stop the Korgis server to
free memory; perform Blender E2E in a separate no-model phase. Do not
set an Ollama-specific `keep_alive` field, invent an unload success, or launch
a second GGUF copy in Ollama/LM Studio concurrently.

## 1. Verify the existing private GGUF on the Mac

    MODEL_FILE="$HOME/.lmstudio/models/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    test -s "$MODEL_FILE" || { echo "GGUF missing"; exit 1; }
    ls -lh "$MODEL_FILE"
    system_profiler SPHardwareDataType | grep -E 'Chip|Memory'
    sysctl vm.swapusage

This proves local presence and reported file size, **not** that the GGUF
loads fully on Metal or fits peak memory. Compute a private artifact SHA-256
pin if desired (`shasum -a 256 "$MODEL_FILE"`), record it in a private
evidence manifest, and do not expose the personal path.

## 2. Configure a scoped Korgis registry override

Korgis already supports `LOCAL_LLM_REGISTRY_PATHS` and a `path` to a
pre-existing absolute GGUF; no changes to the Korgis repository, its global
model registry, or the existing LM Studio download are required.

    mkdir -p "$HOME/geometry-evidence"
    cat > "$HOME/geometry-evidence/korgis-qwen3-coder-30b.yaml" <<YAML
    models:
      qwen3-coder-30b-q4km:
        model_id: qwen3-coder-30b-q4km
        backend: llama_server
        path: "$MODEL_FILE"
        quantization: Q4_K_M
        thinking_mode: none
        params:
          ctx_size: 8192
          n_gpu_layers: -1
          max_concurrent_requests: 1
          startup_timeout: 600
          enable_thinking: false
          show_thinking: false
    YAML

    export LOCAL_LLM_REGISTRY_PATHS="$HOME/geometry-evidence/korgis-qwen3-coder-30b.yaml"

From the Korgis checkout and its configured Python environment:

    local-llm models
    local-llm serve \
      --model qwen3-coder-30b-q4km \
      --host 127.0.0.1 --port 1235 \
      --ctx-size 8192 --n-gpu-layers -1 \
      --max-concurrent-requests 1 \
      --no-download \
      --inference-cache-max-entries 0

The server must have a compatible current `llama-server` executable and
Metal-enabled backend. If it fails to load, **do not** silently change the
model, offload it all to CPU or enable internet downloads. Inspect the actual
backend error and adjust independently.

Verify from a second terminal:

    curl -fsS http://127.0.0.1:1235/v1/models | jq '.data[] | {id,key,backend}'
    curl -fsS http://127.0.0.1:1235/v1/runtime/identity | jq '{
      protocol_version, default_model,
      model: .models["qwen3-coder-30b-q4km"].model,
      runtime: .models["qwen3-coder-30b-q4km"].runtime,
      hardware: .models["qwen3-coder-30b-q4km"].hardware
    }'
    memory_pressure -Q
    sysctl vm.swapusage

The Geometry Harness client verifies the Korgis identity protocol, exact
`qwen3-coder-30b-q4km` runtime key and ID, quantization `Q4_K_M`,
`llama_server` backend, context=8192 and one concurrent request before
sending each request. Each result records the public privacy-filtered
runtime identity, token counts, wall time, status and immutable source hashes.
The public identity excludes raw local path, prompts and credentials.

## 3. Find the frozen generator-only public prompts

The model side must receive ONLY
`prompt_description.txt` and `prompt_instruction.txt` for each task,
as used in the original Luna run. Never expose reference GLBs or factory
scripts to the generator.

    find "$HOME/geometry-evidence" "$HOME/Projects" \
      \( -name staging-manifest.json -o -name '*suites*.json' \) -print

Use the generator prompt root containing
`staging-manifest.json` and six `<task>/prompt_description.txt` plus
the associated **full suite** JSON created by
`benchmarks/catalog/select_suites.py` (not the compact
`benchmarks/catalog/real_smoke_v1.json`). The harness validates
the suite SHA and both public prompt hashes for every selected task
before making *any* inference request. If the original stage/suite are
not available locally, recover or re-stage **only** those frozen public
texts from the pinned dataset. Do not fabricate a new suite or use a
different dataset revision.

## 4. Run an isolated generation-only 2-task smoke

In the geometry project environment, with Korgis still serving:

    cd ~/Projects/3d-rendering-llm
    git fetch origin
    git switch feature/g1-ollama-32gb-smoke
    git pull --ff-only
    export PYTHONPATH=src
    export PUBLIC_ROOT="/real/path/to/frozen/generator-smoke"
    export SUITE="/real/path/to/frozen/suites.json"

    python3 -m geometry_harness.local_smoke \
      --generate-only \
      --model qwen3-coder-30b-q4km \
      --num-ctx 8192 --num-predict 2048 \
      --public-root "$PUBLIC_ROOT" \
      --suite "$SUITE" \
      --task CoffeeTable_seed0 --task Bottle_seed0 \
      --out "$HOME/geometry-evidence/korgis-qwen-2-task-generation-01"

The runner uses the original Luna CONTRACT plus identical public task
texts, with the safe AST name normalizer and no agent repair. It stores
the raw generated Python (without executing it), safe scene spec and
provider/runtime evidence privately. Exit 1 means at least one source
was not accepted by the strict parser; that is an experimental result,
not permission to weaken the security boundary.

## 5. Release Korgis memory and independently validate Blender

Stop the Korgis server gracefully with Ctrl-C in its terminal.
Verify the model's resident subprocess exited and memory pressure has
subsided, then run Blender **without** any server or model connection:

    cd ~/Projects/3d-rendering-llm
    export PYTHONPATH=src
    python3 -m geometry_harness.evaluation.local_staged_blender \
      --stage "$HOME/geometry-evidence/korgis-qwen-2-task-generation-01" \
      --out "$HOME/geometry-evidence/korgis-qwen-2-task-blender-01"

The staged validator validates recorded SHA/size for every generated file,
recompiles the same safe literal AST, rechecks exact scene-spec equality
and runs only the repository-owned builder/inspector with
`--disable-autoexec`. Scene/result hashes are written to a *new*
private output; no model calls occur during this phase. The return code
is 0 only if every attempted scene passed independent native Blender
reopen; failure statuses and logs remain inspectable.

After confirming memory, speeds and no-egress provenance, run the full
six-task `--generate-only` experiment into an **entirely fresh**
output directory, stop the server, and repeat the separate Blender
validation to obtain the six-task native execution denominator.

## What this does *not* prove

- Same six task texts and same AST do not prove identical model inference
  settings: historical Luna used max **2048 output tokens**. Keep the
  first matched-cap experiment at 2048; any 4096 run is a new profile.
- A low Chamfer CD does not prove semantic/prompt fidelity. First count
  parse/native failures, then score 3D GLBs with the same separately pinned
  reference scorer in a new, verified output, and review four Blender
  views. Korgis cannot provide native GLB/Chamfer scores on its own.
- Real Mac RAM/performance, GGUF compatibility and true no-egress behavior
  are **not verified by GitHub CI**; Korgis runtime identity and Mac
  operator evidence must be inspected before accepting these claims.
- Model-size approximations do not establish actual peak working memory,
  KV-cache overhead or GPU residency. Electricity and hardware
  amortization are also not included in `api_cost_usd = 0`.
