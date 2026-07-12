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

1. Keep one logical change per PR and use a `feat/`, `fix/`, `docs/`, `test/`, or
   `ci/` branch.
2. Use Conventional Commits and sign off commits when contributing externally.
3. Add tests for behavior and policy changes.
4. State exactly which checks and live applications were exercised.
5. Disclose AI assistance and the human review performed.
6. Do not weaken redaction, allowlisting, execution gating, stale-state checks,
   verification receipts, or worker isolation without an explicit security review.
7. Do not force-push after review begins.

Report vulnerabilities through the private process in `SECURITY.md`.
