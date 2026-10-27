# GitHub CI — Mac mini integration

This project uses repository-scoped runners belonging to `daniele21/local-runner-infra`, **not** runners registered to this repository.

- Canonical integration: https://github.com/daniele21/local-runner-infra/blob/main/docs/integration-guide.md
- The source of truth for tests is `.github/ci/local-test.sh`. The central workflow checks out a trusted exact SHA and executes this script on `[self-hosted, macOS, ARM64, local-shared]`.
- **G0 must use the dedicated Mac mini workflow** in central infrastructure: `geometry-mac-mini.yml`, triggered by `.github/ci/requests/geometry-harness.json` through `scripts/request_geometry_ci.sh <trusted-SHA>`. Its `runs-on` includes the custom `geometry-mac-mini` label and checks the `local-mac-mini-*` runner name. The generic `current.json` / `central-ci.yml` can route to unrelated `local-mac-1` and must not be used for G0. Apply the label to the real Mac mini via reviewed central operating procedure; never invent labels or change runner registrations from source code.
- This is the **central-direct Mac-only** path, not a GitHub-hosted Ubuntu dispatch. Never send arbitrary, unknown, fork or unreviewed PR code onto the personal Mac.
- Check the dedicated central Actions run and `local-ci/mac-mini` status when the source-status PAT has write scope. A successful request is not proof the tests ran successfully; lack of token scope must be reported explicitly.
- The central job uploads `ci-artifacts/showcase/` as GitHub Actions artifacts, including failure diagnostics when available. Source scripts must produce real Gx deliverables and machine-readable checks; mocking a render must not satisfy a milestone.
- Keep existing hosted template validation until the app is specialized and parity is demonstrated; do not edit central Terraform-managed workflows from this source repo.
- Paid LLM API experiments and heavyweight open-weight tests require separate explicit invocation and bounded resources; never trigger them on every source commit.
- Gitignored large render/model artifacts and bounded retention are mandatory. The source script must not alter sibling projects or runner installation state.
