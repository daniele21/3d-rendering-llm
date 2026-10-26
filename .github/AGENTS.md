# GitHub CI — Mac mini integration

This project uses repository-scoped runners belonging to `daniele21/local-runner-infra`, **not** runners registered to this repository.

- Canonical integration: https://github.com/daniele21/local-runner-infra/blob/main/docs/integration-guide.md
- The source of truth for tests is `.github/ci/local-test.sh`. The central workflow checks out a trusted exact SHA and executes this script on `[self-hosted, macOS, ARM64, local-shared]`.
- Request execution by a trusted change to the central repository's `.github/ci/requests/current.json`, via the central `scripts/request_ci.sh` helper. Do not add `runs-on: self-hosted` here: it would not find the centrally registered runners.
- This is the **central-direct Mac-only** path, not a GitHub-hosted Ubuntu dispatch. Never send arbitrary, unknown, fork or unreviewed PR code onto the personal Mac.
- Check `local-ci/mac` on the exact source commit and central Actions logs. A successful request is not proof the tests ran successfully.
- The central job uploads `ci-artifacts/showcase/` as GitHub Actions artifacts, including failure diagnostics when available. Source scripts must produce real Gx deliverables and machine-readable checks; mocking a render must not satisfy a milestone.
- Keep existing hosted template validation until the app is specialized and parity is demonstrated; do not edit central Terraform-managed workflows from this source repo.
- Paid LLM API experiments and heavyweight open-weight tests require separate explicit invocation and bounded resources; never trigger them on every source commit.
- Gitignored large render/model artifacts and bounded retention are mandatory. The source script must not alter sibling projects or runner installation state.
