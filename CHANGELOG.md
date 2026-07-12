# Changelog

All notable changes are documented here. This project follows Semantic
Versioning and uses GitHub Releases for distributable artifacts.

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
