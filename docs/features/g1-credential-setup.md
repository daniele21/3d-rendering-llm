# G1 cloud API credentials — setup without exposing keys

**Status:** provisioning guide and provider contract only; G1 end-to-end model-generated Blender scenes are not yet validated. **No model calls are performed** by the readiness workflow.

## Security boundary

- G0 and routine fast CI remain **deterministic, free of provider keys, no remote inference**.
- Only the private central repo `daniele21/local-runner-infra` may receive the billing credential. The public source repo `daniele21/3d-rendering-llm` must **never** store it as a secret, variable, issue, commit, file, README example, or log.
- The central G1 readiness workflow is triggered **manually**; it only checks that a secret exists and never reveals its value or calls the OpenAI API.
- The future paid G1 workflow must be separate from G0 and feature-PR CI, pin a reviewed immutable source SHA, guard the actual runner and secret scope, impose wall-time/output/call budgets, and not execute model-generated Python unsandboxed on a personal Mac. **A valid key alone is not permission to run a billed experiment or unsafe generated code.**
- Use a dedicated OpenAI Platform **project** and scoped key/service account rather than a personal cross-project key. Set sensible spending alerts and a low test budget (for example $5–10 for the first smoke) and confirm actual billing configuration. ChatGPT subscription and API usage are distinct.

## One-time actions on a trusted workstation

1. In the OpenAI Platform create/select a project (e.g. `geometry-harness-evals`) and generate a project-specific secret key, ideally restricted to the **Chat Completions** endpoint. Use [project API keys](https://platform.openai.com/api-keys) and [limits](https://platform.openai.com/settings/organization/limits) to review model access, usage and budget. Do not paste the key into a ChatGPT conversation.
2. Authenticate GitHub CLI `gh auth status`, then store the value securely in the **central repo**:
   ```bash
   gh secret set GEOMETRY_CLOUD_API_KEY -R daniele21/local-runner-infra
   ```
   This command interactively accepts the secret through the CLI; do not pass the value as a command-line argument, echo it, or commit a `.env` file.
3. Configure a non-secret model name, currently `gpt-6.1-sol` (reasoning effort `low` for first smoke; provider can be compared later):
   ```bash
   gh variable set GEOMETRY_CLOUD_MODEL -R daniele21/local-runner-infra --body 'gpt-6.1-sol'
   ```
4. Check **presence only**:
   ```bash
   gh secret list -R daniele21/local-runner-infra
   gh variable list -R daniele21/local-runner-infra
   ```
5. Once `geometry-g1-readiness.yml` is merged into the central private `main`, run its explicit manual **zero-cost credential check**:
   ```bash
   gh workflow run geometry-g1-readiness.yml -R daniele21/local-runner-infra --ref main
   gh run list -R daniele21/local-runner-infra --workflow geometry-g1-readiness.yml --limit 3
   ```
   Review the check logs for `Credential present; model gpt-6.1-sol; no API calls`. If it fails, verify permissions and secret name; never print the secret.

## Source provider contract

`src/geometry_harness/providers/compatible.py` consumes `GEOMETRY_CLOUD_API_KEY`, `GEOMETRY_CLOUD_MODEL`, `GEOMETRY_CLOUD_ENDPOINT` (default `https://api.openai.com/v1/chat/completions`), and **explicit** `GEOMETRY_ALLOW_REMOTE_INFERENCE=1`. Without all required settings, model generation fails closed. The current provider uses `max_completion_tokens` and low reasoning for the code-first baseline, validates Python syntax but does **not** run the code, render, or produce an official benchmark score.

For a future local manual test, the trusted experiment wrapper must pass `GEOMETRY_ALLOW_REMOTE_INFERENCE=1` only within the approved, cost-bounded **G1** step, not as a persistent machine/global environment variable. G0 never sets it.

## Acceptance before first billed G1

- [ ] Dedicated secret configured **only** on central private repo; readiness check passes without disclosing value
- [ ] Model/endpoint permission tested against a reviewed budget and documented pricing
- [ ] Real G1 user journey prompts a real model once -> stores provenance/script -> validates generated content safely -> builds real Blender native scene -> preview -> independent reopen/geometry -> gallery/manifest -> private GCS bundle
- [ ] Runner isolation and generated-code execution sandbox reviewed; never execute arbitrary model code directly on the Mac host
- [ ] Provider rejection/timeout/exceeded budget triggers FAIL with sanitized diagnostics; source/outputs preserved when safe
- [ ] 3DCodeBench prompts + reference factory/source segregated, dataset revision and rights frozen, baseline quality metrics honest
- [ ] No automatic repeat model calls from ordinary pushes, PRs or G0

See [benchmark protocol](benchmark-protocol.md) and [workstream](../workstreams/geometry-harness.md).
