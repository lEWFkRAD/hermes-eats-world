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

Install the Python package once into Hermes's environment so the plugin entry
point and Windows UIA dependencies are available:

```powershell
python -m pip install "git+https://github.com/lEWFkRAD/hermes-eats-world.git"
hermes plugins enable hermes-eats-world
hermes gateway restart
```

The plugin registers the read-only `uia_perceive_window` tool. It accepts the
fresh `read_window_below.window.id`, always redacts raw UI values, never captures
a screenshot, and runs UIA traversal behind the killable worker boundary.

### Multiple Hermes profiles

Hermes profiles are isolated by `HERMES_HOME`. The package is installed once,
but plugin enablement is intentionally per profile:

```powershell
hermes -p work plugins enable hermes-eats-world
hermes -p personal plugins enable hermes-eats-world
hermes -p work gateway restart
hermes -p personal gateway restart
```

Each profile loads its own plugin registration and every tool response includes
the active `hermes_profile`. The tool is stateless and does not write snapshots,
screenshots, caches, or other files that could leak across profiles. Do not pass
one profile's HUD window handle to another profile; each call must use a fresh
`read_window_below.window.id` from the requesting profile's current turn.

For source development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
heaw --list
heaw --target "Notepad" --depth 3 --output artifacts\notepad.json
```

### Hermes HUD mode

Hermes Desktop HUD mode floats over the application the user is working in.
Hermes's `read_window_below` tool returns metadata for that application; on
Windows, its `window.id` is the exact native window handle. Pass that value to
the sidecar instead of re-matching a possibly ambiguous title or process:

```powershell
heaw --window-id 123456 --depth 3
# Hexadecimal HWNDs are accepted too:
heaw --hwnd 0x1E240 --depth 3
```

Treat this as a fresh handoff. Call `read_window_below` again after the HUD is
moved, the foreground application changes, or before planning an action. An
invalid or inaccessible exact handle fails closed; the sidecar never falls back to a
different title/process match. HUD handoff does not enable actions, capture a
screenshot, or include raw UI values unless those capabilities are requested
separately.

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

1. Register exact-handle HUD perception as a typed Hermes tool.
2. Add a Hermes command surface for perception and dry-run action planning.
3. Add an explicitly enabled UIA invoke adapter behind the existing policy gate.
4. Expand calibrated fixtures across common Windows applications.
5. Package signed Windows executables in addition to the Python wheel.

See `spikes/001-perception-spike/SYNTHESIS.md` for the initial research record.

See [CHANGELOG.md](CHANGELOG.md) for released behavior and
[docs/RELEASING.md](docs/RELEASING.md) for the maintainer release process.

## Safety

Desktop automation can click, type, and expose sensitive UI content. Before action support ships, the project needs target scoping, destructive-action confirmation, secret redaction, bounded retries, and immutable action receipts.

## License

MIT. See [LICENSE](LICENSE).
