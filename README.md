# Hermes Eats World

Windows UI Automation perception sidecar for Hermes Agent. It discovers desktop windows, walks their UIA accessibility trees, classifies how automatable they are, and emits a versioned JSON snapshot that downstream planners can consume.

This repository is packaged as an independently installable Hermes standalone
plugin. Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[AGENTS.md](AGENTS.md) before deploying or changing the action boundary.

> **Status:** early prototype. Perception works; action and verification packages are placeholders. Use it only in a disposable desktop session until safety boundaries are implemented.

## Requirements

- Windows 10 or 11
- Python 3.10+
- An interactive desktop session

## Quick start

Install through Hermes:

```powershell
hermes plugins install lEWFkRAD/hermes-eats-world --enable
```

For source development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
heaw --list
heaw --target "Notepad" --depth 3 --output artifacts\notepad.json
```

UI text values are redacted by default. `--include-raw-values` is available for
explicitly approved debugging sessions, but its output must be treated as sensitive.

Tree walks default to a 30-second deadline and 5,000-element ceiling. Use
`--timeout` and `--max-elements` to lower those bounds for constrained callers.
Perception runs in a disposable worker process; if a UI Automation COM call
hangs past the deadline, the parent terminates the worker and returns a
structured, retryable error instead of freezing the caller.

Run elevated only when inspecting elevated applications. Windows UIPI prevents a normal process from fully inspecting higher-integrity windows.

## What the snapshot contains

- target window metadata and bounds
- a depth-limited accessibility tree
- supported UIA patterns for each element
- a T1–T3 perception classification
- an optional screenshot path
- schema version and UTC timestamp

The JSON contract is defined in `sidecar/schema/models.py`. Breaking contract changes must bump `SCHEMA_VERSION`.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

The test suite keeps pure model and traversal behavior independent of a live Windows desktop. Live UIA smoke tests should be run interactively and documented separately.

## Roadmap

1. Stabilize and test perception contracts.
2. Add explicit action allowlists and dry-run support.
3. Implement post-action verification and audit receipts.
4. Add a Hermes transport boundary and end-to-end fixtures.
5. Package signed Windows releases.

See `spikes/001-perception-spike/SYNTHESIS.md` for the initial research record.

## Safety

Desktop automation can click, type, and expose sensitive UI content. Before action support ships, the project needs target scoping, destructive-action confirmation, secret redaction, bounded retries, and immutable action receipts.

## License

No license has been selected yet. All rights are reserved until the repository
owner adds one. External contributions should not be accepted until that choice
is recorded.
