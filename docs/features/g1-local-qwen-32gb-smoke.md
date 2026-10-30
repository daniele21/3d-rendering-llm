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

## 2a. Troubleshooting: Korgis requires llama-server build 10621+

An actual operator startup attempt on 2026-10-30 found the model GGUF
on disk (~17 GiB in `ls -lh`), then Korgis refused to start because
`resolve_llama_server_binary` found no compatible standalone
`llama-server`. **This is a pre-inference binary compatibility gate,
not evidence of a bad model or insufficient RAM.** Korgis requires a
`llama-server --version` showing attributable build/commit and build
**10621 or newer**, and deliberately refuses older/unattributable builds.
Do **not** enable `llama_server_allow_unvalidated` or reduce its floor.

Use a current **standalone** Homebrew distribution of llama.cpp
(not the `llama-cpp-python` wheel and not the Ollama binary):

    brew install llama.cpp
    # If already installed but old: brew upgrade llama.cpp
    LLAMA_SERVER="$(brew --prefix llama.cpp)/bin/llama-server"
    test -x "$LLAMA_SERVER" || { echo "llama-server missing"; exit 1; }
    "$LLAMA_SERVER" --version 2>&1

Verify the version output shows the required build and commit. From
Korgis's normal Python environment, pass that exact executable via
`--llama-server-bin "$LLAMA_SERVER"` on the `uv run --frozen local-llm
serve ...` command, or export `LOCAL_LLM_SERVER_BIN="$LLAMA_SERVER"`
in the Korgis terminal. Korgis does not bypass a failed compatibility
check for an explicitly configured binary. Homebrew's llama.cpp
formula includes `llama-server` and prebuilt Apple Silicon binaries.

If `llama-server --version` still cannot be attributed, record the
output and check that the selected executable and system architecture
are correct. Do not infer that the weights were loaded if startup
failed before backend construction.

## 3. Find the frozen generator-only public prompts

The model side must receive ONLY
`prompt_description.txt` and `prompt_instruction.txt` for each task,
as used in the original Luna run. Never expose reference GLBs or factory
scripts to the generator.

    find "$HOME/geometry-evidence" "$HOME/Projects" \
      \( -name staging-manifest.json -o -name '*suites*.json' \) -print

The operator's initial `find` on 2026-10-30 found *only unrelated ASR
suite JSON files*: neither the original Luna staging manifest nor the full
3DCodeBench suite were present in those searched locations. Do NOT point
the geometry benchmark at the ASR suites.

If the original stage/suite have been moved or removed, the repository now
contains `benchmarks/catalog/freeze_public_only.py`. It downloads **only**
the two **public text prompts** for each of 212 category IDs at the pinned
dataset revision (never source factories, reference media or GLBs),
reconstructs the complete suite in a temporary restricted workspace,
requires it to hash **exactly**
`79904d4e83e9075cd08337a99c28d5dbcc00743cc790d37123ed9b7c776a7cd8`,
then writes twelve public smoke prompt files and the exact historical
`suite.json`. It cannot silently switch dataset or selection.

**Run this preparation while Korgis is stopped**, to preserve RAM:

    cd ~/Projects/3d-rendering-llm
    git fetch origin
    git switch feature/g1-ollama-32gb-smoke
    git pull --ff-only

    uv run --no-project --with "huggingface_hub>=0.30,<2" \
      python benchmarks/catalog/freeze_public_only.py \
        --output "$HOME/geometry-evidence/frozen-luna-public-only-01"

    export PUBLIC_ROOT="$HOME/geometry-evidence/frozen-luna-public-only-01/generator-public-smoke"
    export SUITE="$HOME/geometry-evidence/frozen-luna-public-only-01/suite.json"
    shasum -a 256 "$SUITE"

The resulting suite hash **must** match the above; otherwise the
tool fails before staging. No model requests occur, and no model API
keys are used. No hidden reference scripts or geometry assets enter
the generator workspace. Set `PUBLIC_ROOT` and `SUITE` in the later
geometry terminal; they are not automatically exported by Korgis.
This is the historical **frozen original task text**, *not* a different
benchmark.

Before running inference, check RAM while the server is loaded and
while it is stopped:

    memory_pressure -Q
    sysctl vm.swapusage

The first observed Korgis status was 16% free memory with 15 GiB swap
already used. High swap *alone* is not proof of active thrashing or
bad hardware fit; observe performance and swap **growth** over time.
Close heavy unrelated processes; if pressure remains consistently high,
stop and do not start two tasks until the Mac is stable. Explicit
`n_gpu_layers=-1` is a configuration intent, not independently
verified full GPU residency. The model GGUF identity was
`evidence_grade=partial` with `artifact_digest=null`; record a
private SHA-256 of the GGUF before evidence-grade comparisons.

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
