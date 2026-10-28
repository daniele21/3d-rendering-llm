# G1 model costs — audit and retention policy

Status: cost ledger and price calculator implemented; **no paid G1 call has run yet**. The source of truth for each request is a private JSONL append-only ledger, not an aggregate estimate.

## Per-call evidence
Before outbound HTTP: durable started record (unique call ID, timestamp, model requested, stage, source SHA, GitHub run ID).
After completion or error: durable settled record (outcome, provider request ID, actual returned model, elapsed time, observed numeric usage and the versioned calculation). Crashes leave a pending/unknown record; unsuccessful calls with unreported usage are UNKNOWN, never zero.

Usage fields: input total, uncached input, cache read tokens, cache writes (30 min/12 h), output total, reasoning output subset, model, service tier, processing region, tariff snapshot, USD component amounts, total USD. Cache writes are disjoint from uncached input and reads; reasoning is counted inside output once. Costs are Decimal estimates, not billing invoices. Unknown model, missing usage counter, pricing tier other than Standard/global or inconsistent cache breakdown => UNKNOWN rather than invented USD.

## Local operation
Default ledger: runs/costs/events.jsonl (gitignored). Override via environment variable GEOMETRY_COST_LEDGER. The file is append-only with locking, fsync and owner-only mode 0600. No prompts, API keys, response text, Authorization headers or raw provider exception are stored.

Generate immutable JSON summary:

    PYTHONPATH=src python3 -m geometry_harness.costs.ledger --ledger runs/costs/events.jsonl --output runs/costs/summary.json

Summary includes paired started/settled calls, priced and unpriced counts, cache usage and USD subtotal by model and stage. If any incomplete calls exist, grand_total_status = INCOMPLETE_UNKNOWN_COST: the known subtotal must NOT be presented as total spend. Never overwrite a finalized summary.

## Cloud storage (required for first G1 live execution)
Reuse the existing private bucket, Workload Identity Federation (WIF), SHA-pinned upload convention and ObjectCreator permissions already proven by G0. Configure the dedicated G1 workflow with:
- GEOMETRY_COST_LEDGER = ci-artifacts/showcase/g1/costs/events.jsonl
- report = ci-artifacts/showcase/g1/costs/summary.json
- private destination: gs://project-tests-498508-geometry-showcase/geometry-harness/g1/SOURCE_SHA/RUN_ID-attempt-N/g1/costs/
- upload ledger and report EVEN IF inference or Blender fails, and verify file inventory/hash; G1 cannot pass otherwise.

The dedicated G1 workflow is NOT yet implemented: only G0 and the manual no-inference G1 readiness workflow exist. Therefore local accounting is implemented but cloud logging remains a required G1 blocker. No current run is proof of cloud cost retention. The public source repo must not contain actual usage records or secrets. Keep immutable GCS objects as audit source-of-truth; optionally later ingest them into BigQuery for daily/monthly dashboards and reconciliation with OpenAI Billing and Usage APIs. The ledger is a usage-based estimate, not a full cloud compute or tax invoice.

## GPT-6.1 Sol rates used (USD per 1M tokens, snapshot 2026-10-28)
Standard, global:
- Short context <=272000 input tokens: uncached input $2, cached read $0.10, cache write 30m $2.50, cache write 12h $5, output $10.
- Long context >272000 input tokens: uncached input $4, cached read $0.20, cache write 30m $5, cache write 12h $10, output $15.
- Long context rates apply to the entire request. Chat Completions uses 30-minute cache writes; a future Responses adapter can explicitly separate cache write TTLs.

Prices are versioned in source and embedded per request, so future rate changes never silently rewrite history. Model aliases, Fast/Flex/Batch, regional processing and external tool costs need their own catalog entries, otherwise report UNKNOWN. Official references:
https://developers.openai.com/api/docs/models/gpt-6.1-sol
https://developers.openai.com/api/docs/guides/prompt-caching
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

## Promotion gate
Run automated unit tests and mock-transport ledger tests without paid calls; then enable isolated generated-code execution, a reviewed cost-bounded manual G1 job, mandatory cost-log upload and reconciliation. Treat the first actual model response as the first opportunity to validate provider usage fields; do not infer a cost from code-only tests.
