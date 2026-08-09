# Hermes Eats World

Windows UI Automation perception sidecar for Hermes Agent. It discovers desktop windows, walks their UIA accessibility trees, classifies how automatable they are, and emits a versioned JSON snapshot that downstream planners can consume.

This repository is packaged as an independently installable Hermes standalone
plugin. Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[AGENTS.md](AGENTS.md) before deploying or changing the action boundary.

> **Status:** v1.0.0. Bounded perception and the standalone plugin
> are supported. Action policy, stale-state checks, and verification receipts are
> stable contracts, but live action execution is not exposed through the CLI.

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

1. Add a Hermes command surface for perception and dry-run action planning.
2. Add an explicitly enabled UIA invoke adapter behind the existing policy gate.
3. Expand calibrated fixtures across common Windows applications.
4. Package signed Windows executables in addition to the Python wheel.

See `spikes/001-perception-spike/SYNTHESIS.md` for the initial research record.

See [CHANGELOG.md](CHANGELOG.md) for released behavior and
[docs/RELEASING.md](docs/RELEASING.md) for the maintainer release process.

## Safety

Desktop automation can click, type, and expose sensitive UI content. Before action support ships, the project needs target scoping, destructive-action confirmation, secret redaction, bounded retries, and immutable action receipts.

## License

MIT. See [LICENSE](LICENSE).
