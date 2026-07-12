# Contributing to Hermes Eats World

Hermes Eats World is a Windows-only desktop automation sidecar. Contributions
must preserve its deny-by-default action boundary and machine-readable protocol.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m ruff check sidecar tests
python -m pytest -q
```

Run live UIA tests only in an interactive disposable session. Never commit real
snapshots, screenshots, window inventories, client data, credentials, or logs.

## Pull requests

All changes to `main` go through a pull request. Open an issue before substantial
features, new action kinds, privilege expansion, protocol changes, or changes to
security boundaries. Small documentation and clearly scoped bug fixes may proceed
directly to a PR.

1. Search existing issues and pull requests first.
2. Keep one logical change per PR and use a `feat/`, `fix/`, `docs/`, `test/`, or
   `ci/` branch.
3. Use Conventional Commits and certify external contributions with
   `git commit -s` under the Developer Certificate of Origin.
4. Add tests for behavior and policy changes.
5. State exactly which checks and live applications were exercised.
6. Disclose AI assistance and the human review performed.
7. Do not weaken redaction, allowlisting, execution gating, stale-state checks,
   verification receipts, or worker isolation without an explicit security review.
8. Wait for required CI and resolve every review conversation before merge.
9. Do not force-push after review begins.

Report vulnerabilities through the private process in `SECURITY.md`.

Contributions are licensed under the repository's MIT License.
