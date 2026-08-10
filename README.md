# Hermes Eats World

Windows UI Automation perception sidecar for Hermes Agent. It discovers desktop windows, walks their UIA accessibility trees, classifies how automatable they are, and emits a versioned JSON snapshot that downstream planners can consume.

This repository is packaged as an independently installable Hermes standalone
plugin. Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[AGENTS.md](AGENTS.md) before deploying or changing the action boundary.

> **Status:** v1.1.0. Profile-aware exact-window perception is available as a
> native Hermes plugin. Action policy, stale-state checks, and verification
> receipts remain library contracts; the plugin and CLI expose no live actions.

## Requirements

- Windows 10 or 11
- Python 3.10+
- An interactive desktop session

## Quick start

Install and enable the Git plugin for the active Hermes profile, then create its
versioned UIA runtime:

```powershell
hermes plugins install lEWFkRAD/hermes-eats-world --enable
hermes heaw setup
hermes gateway restart
```

The plugin registers the read-only `uia_perceive_window` tool. It accepts the
fresh `read_window_below.window.id`, redacts ValuePattern text and password
controls, never captures a screenshot, and runs UIA traversal in a killable,
profile-owned runtime. Element labels and automation IDs remain available for
perception and can still be sensitive; every response describes that boundary.

`hermes heaw setup` installs Windows UIA dependencies under the active
`HERMES_HOME\plugin-runtimes` directory. It does not modify Hermes's own Python
environment. Use `hermes heaw status` to inspect the runtime.

### Multiple Hermes profiles

Hermes profiles are isolated by `HERMES_HOME`; select each profile, then install,
set up, and enable the plugin independently in every profile that should receive
desktop perception:

```powershell
hermes profile use work
hermes plugins install lEWFkRAD/hermes-eats-world --enable
hermes heaw setup
hermes gateway restart

hermes profile use personal
hermes plugins install lEWFkRAD/hermes-eats-world --enable
hermes heaw setup
hermes gateway restart
```

Run `hermes profile use default` afterward if you want to restore the default
profile. Hermes 0.20 profile selection is sticky, so each command after
`profile use` targets the selected profile until you switch again.

Each profile loads its own plugin registration and every tool response includes
the active `hermes_profile`. Runtime dependencies are isolated under that
profile's `HERMES_HOME`; the tool itself does not persist snapshots, screenshots,
caches, or UI content. Do not pass one profile's HUD handle to another profile.

For source development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
heaw --list
heaw --target "Notepad" --depth 3 --output artifacts\notepad.json
```

The published wheel has no mandatory dependencies, so installing its Hermes
entry point cannot upgrade the host environment. Developers who need the direct
`heaw` CLI can install the explicit `runtime` extra.

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

UIA ValuePattern text and password-control labels are redacted by default.
Element names, window titles, and AutomationIds may still contain private data,
so every snapshot remains a sensitive artifact. `--include-raw-values` is
available only in the developer CLI for explicitly approved debugging sessions.

The Hermes tool defaults to 500 elements, a 15-second deadline, and a 128 KiB
model-output budget. `mode: summary` omits the tree. Oversized results fail
closed with smaller suggested parameters. One scan may run per profile at a
time. The developer CLI retains broader expert controls.

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
See [docs/TESTING.md](docs/TESTING.md) for the sanitized smoke command and
release application matrix.

## Roadmap

1. Expand calibrated live fixtures across Office, Explorer, browsers, WinUI,
   UWP, DPI, elevation, and stale-window scenarios.
2. Add query and pagination modes for very large accessibility trees.
3. Package a signed Windows executable as an alternative isolated runtime.
4. Keep any future action capability in a separate, explicitly enabled plugin.

See `spikes/001-perception-spike/SYNTHESIS.md` for the initial research record.

See [CHANGELOG.md](CHANGELOG.md) for released behavior and
[docs/RELEASING.md](docs/RELEASING.md) for the maintainer release process.

## Safety

Desktop automation can click, type, and expose sensitive UI content. Before action support ships, the project needs target scoping, destructive-action confirmation, secret redaction, bounded retries, and immutable action receipts.

## License

MIT. See [LICENSE](LICENSE).
