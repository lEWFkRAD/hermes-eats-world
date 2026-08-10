# Changelog

All notable changes are documented here. This project follows Semantic
Versioning and uses GitHub Releases for distributable artifacts.

## [Unreleased]

## [1.1.0] - 2026-08-09

### Added

- Exact `--window-id` / `--hwnd` targeting for a safe handoff from Hermes
  Desktop HUD mode's `read_window_below.window.id` on Windows.
- First-class Hermes plugin entry points for directory and pip installations.
- A profile-aware, read-only `uia_perceive_window` tool that reports the active
  Hermes profile while keeping perception stateless.
- A profile-owned `hermes heaw setup` runtime that isolates UIA dependencies
  from Hermes's Python environment.
- Summary mode, a hard model-output byte budget, and per-profile scan concurrency.

### Security

- Exact-handle targeting fails closed when the supplied HWND is invalid or
  inaccessible instead of falling back to an ambiguous title or process match.
- The worker revalidates both HWND and process identity before and after traversal.
- Password controls are always redacted, worker errors are sanitized, and
  responses describe which label fields remain sensitive instead of claiming
  complete redaction.

## [1.0.0] - 2026-07-12

### Added

- Installable Windows `kind: standalone` Hermes plugin manifest.
- Exact-HWND window discovery and UIA accessibility-tree perception.
- Versioned Pydantic snapshot, error, target, tier, and element contracts.
- Default redaction for UIA value patterns with explicit raw-value opt-in.
- Killable subprocess isolation for potentially blocking UIA/COM calls.
- Depth, element-count, and wall-clock traversal limits.
- Multi-monitor screenshot capture with collision-resistant filenames.
- Deny-by-default action policies, risk levels, HWND allowlists, and dry runs.
- Fresh-snapshot resolution, stale-state rejection, invoke capability checks,
  explicit postconditions, and immutable verification receipts.
- Windows CI, wheel packaging, security policy, contribution rules, issue forms,
  PR checklist, and MIT license.

### Supported boundary

- The CLI supports perception and screenshot capture.
- Action execution exists as an adapter-facing Python contract and is covered by
  controlled tests. The CLI does not expose live clicking or typing in v1.0.0.
- The release is Windows-only and requires an interactive desktop session.

[1.0.0]: https://github.com/lEWFkRAD/hermes-eats-world/releases/tag/v1.0.0
[1.1.0]: https://github.com/lEWFkRAD/hermes-eats-world/releases/tag/v1.1.0
