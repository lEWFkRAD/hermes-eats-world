# Main branch protection

The repository's `main` branch should enforce the following GitHub rules. These
settings are maintained in GitHub, while this file records the intended policy
for recovery and audit.

## Pull requests

- Require a pull request before merging.
- Require one approving review and dismiss stale approvals when new commits land.
- Require review from Code Owners.
- Require all review conversations to be resolved.
- Allow repository administrators to bypass for emergency security fixes.

## Required checks

- Require the stable `Required PR checks` status check.
- Require branches to be up to date before merging.

`Required PR checks` is the aggregate gate in `.github/workflows/ci.yml`. It
fails unless lint/policy checks, the Windows Python test matrix, wheel build and
clean installation, and pull-request DCO validation all succeed. Requiring only
the aggregate avoids branch-rule churn when the test matrix changes.

## History and safety

- Block force pushes and branch deletion.
- Do not permit a failing required check to be bypassed for routine changes.
- Keep GitHub Actions workflow permissions read-only by default.
- Never add secrets to workflows triggered by fork pull requests.
- Never replace `pull_request` with `pull_request_target` for code execution.

