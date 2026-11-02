# E5 — original local Qwen evidence to operator-approved CAD

**Status on 2026-11-02: software E5A/B exists; authenticated private read and actual human approval still pending.** See issue #91. Do not claim that any completed code or CI run proves those pending steps.

## Upstream immutable runs

- Real local Qwen one-shot 3/3 synthetic smoke: https://github.com/daniele21/local-runner-infra/actions/runs/41395270059
- Geometry source SHA: 72ced4d362832a0e5ebe7f51c64134b0fb88deaf.
- Original private GCS prefix:
  gs://project-tests-498508-geometry-showcase/geometry-harness/architecture-e3/72ced4d362832a0e5ebe7f51c64134b0fb88deaf/41395270059-attempt-1/run-41395270059-attempt-1
- Separate E4 host-callback synthetic proof: https://github.com/daniele21/local-runner-infra/actions/runs/41396310542 (fixture response, NOT actual Qwen replay).

## Authorized GCS acquisition — operator on Mac, not CI

The uploader-only GitHub WIF service account deliberately has no read privilege. Do not expand CI IAM or publish private raw source. Run with a separate **already authorized** local gcloud identity that has read permission on the exact private prefix. From the project root on the Mac:

    git switch main && git pull --ff-only
    bash scripts/architecture_e5_fetch_private.sh "$HOME/geometry-evidence/arch-e5-qwen-real-original-01"

The helper downloads only from the frozen E3 prefix into a fresh local private directory using gcloud storage rsync, then runs read-only E5A verification. No download of model GGUF, inference, GCS uploads, elevated credentials or destructive rsync deletion. A failed read grant is a blocker.

E5A checks the full SHA manifest/lengths/file set, three frozen prompts, system message hash, expected private oracle, model identity projection, per-task telemetry, responses and scoring. Tampering (including modified and self-rehashed local bundles) is rejected. The source-accepting verifier additionally requires immutable SHA fingerprints recorded from an independent, already-authorized Mac/GCS read on [run #41399471418](https://github.com/daniele21/local-runner-infra/actions/runs/41399471418): inventory SHA-256 440fc9f57b27ec22fbe38db3d4c563379bb01861f6615a7e99aea9a8febbce82 and door-response SHA-256 e77fd316f84d7290ab717c4ec6516743e2e78842bcc17591ea51894be76aba16. Synthetic self-consistent fixtures only pass *structural* unit tests and must fail the real anchored verifier. **An internally consistent directory is not cryptographic proof of its external origin.** The operator must review the authenticated gcloud acquisition and original GitHub run independently. Original E3 did not verify full GGUF digest, so neither does E5.

## Read-only review

    PYTHONPATH=src python3 -m geometry_harness.domains.architecture.e5_replay \
      --bundle "$HOME/geometry-evidence/arch-e5-qwen-real-original-01" \
      --mode inspect

Prints bounded door ID, host wall ID/status/locks, old/new millimeter offset, source/model response/candidate SHA, explicit provenance limitation. No model calls, output DXF, network, or approval.

## Explicit operator-only approval and new DXF

Install the already-reviewed optional native DXF dependency in an isolated local environment (ezdxf==1.4.5). An operator, **not GitHub Actions**, can then choose:

    PYTHONPATH=src python3 -m geometry_harness.domains.architecture.e5_replay \
      --bundle "$HOME/geometry-evidence/arch-e5-qwen-real-original-01" \
      --mode commit \
      --out "$HOME/geometry-evidence/arch-e5-approved-01"

Both stdin and stdout must be attached to a real terminal. The operator must review the exact source and candidate SHA, wall facts, entity and dimensions, and type a fresh challenge containing both hash prefixes and a nonce. Unknown structure, locks, forged JSON, source drift, reused output directories and all unattended execution fail closed.

Only after acceptance does the existing E4 transaction write a **NEW** annotated DXF and independently reimport it. Untouched geometry, source invariance and rollback are checked. The private operator confirmation receipt records a terminal acknowledgment, **not verified identity**. This standalone CLI marks source_gcs_authenticated_by_program=false: its local bundle verifier and authenticated source acquisition are separate processes and do not form cryptographic provenance proof. Final E5 requires an external provenance review. Building-code and real-world studio approval are not claimed.

## Gates

- DONE: E5A integrity, frozen source and adversarial tests; no network or inference
- DONE: E5B bounded operator TTY consent contract; no code-generated approval
- DONE: E5C deterministic host-gated E4 integration test, including simulated TTY and native DXF readback in optional pinned CI
- PENDING: actual operator-authorized GCS read of original E3 run and provenance review
- PENDING: actual non-mocked operator confirmation of one candidate
- PENDING: independently audit accepted DXF and private evidence lineage end to end
- PENDING: partner-supervised real DXF mapping and expanded held-out quality study

Do not copy private prompts/responses, geometry plans or approval receipts into public Git.
