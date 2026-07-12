# Agent Instructions

## Scope

This repository contains a Windows UI Automation sidecar and safety contracts for
future verified desktop actions.

## Required checks

Before handing off any change, run:

```powershell
python -m ruff check sidecar tests
python -m pytest -q
python -m build --wheel
git diff --check
```

For targeting, capture, DPI, packaging, or worker-boundary changes, also run a
sanitized live Windows smoke test and describe the exact target used.

## Non-negotiable boundaries

- Preserve complete JSON on stdout; diagnostics belong on stderr.
- Redact UI values by default.
- Keep UIA work behind the killable worker boundary.
- Keep action execution deny-by-default and HWND-scoped.
- Never execute an action from stale state or without explicit postconditions.
- Never add arbitrary script, shell, coordinate-click, or keystroke execution as
  a shortcut around typed actions.
- Treat screenshots, UI trees, logs, and receipts as sensitive.
- Never commit generated artifacts or real user/client content.

Do not claim physical or live-app verification unless it actually occurred.
