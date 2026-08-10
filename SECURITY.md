# Security Policy

Hermes Eats World can inspect desktop accessibility trees, capture screenshots,
and eventually invoke explicitly approved controls. Those capabilities can expose
credentials, client records, financial data, private communications, and other
sensitive information. Report vulnerabilities privately.

## Reporting

Use GitHub private vulnerability reporting. If it is unavailable, contact the
maintainer privately. Do not open a public issue containing credentials, captured
UI content, exploit details, client information, or host-identifying data.

Reports should identify the affected version, expected security boundary,
reproduction steps using sanitized data, and practical impact.

## Threat model

The Windows user, local Hermes installation, and explicitly selected target
application are trusted. Unselected windows, window titles, accessibility values,
screenshots, logs, model output, generated action proposals, and stale snapshots
are untrusted.

The project is not a multi-user remote-desktop service. Do not expose it over a
network or run it in a shared interactive session.

### Perception

- UIA `ValuePattern` text and password-control labels are redacted by default.
- Raw values require `--include-raw-values` and must be treated as sensitive.
- JSON snapshots and PNG captures are sensitive artifacts even when values are
  redacted; labels, titles, AutomationIds, geometry, and screenshots may still
  disclose data. Plugin responses report this field-level redaction boundary and
  never claim that the full artifact is safe to publish.
- UIA work runs in a killable child process with time, element, and depth bounds.
- Target attachment uses an exact HWND after discovery. Callers must still verify
  process identity and intended window ownership.
- The plugin revalidates the exact HWND and owning process inside the worker
  before and after traversal to detect handle reuse or target replacement.
- Tool output has a hard byte budget and one scan may run per profile at a time.

### Actions

- Action policy is deny-by-default.
- Live execution is disabled unless explicitly enabled by the embedding caller.
- Target HWNDs and action kinds must be allowlisted.
- Destructive and above-policy risk levels are rejected.
- A live invoke requires a fresh matching snapshot, stable element resolution,
  declared preconditions, an advertised invoke pattern, and explicit
  postconditions.
- Receipts record request fingerprints and before/after verification evidence.

The current CLI does not expose live action execution. Do not add a bypass that
accepts arbitrary coordinates, scripts, key sequences, or unverified model output.

### Deployment

- Run as a normal user. Elevation expands the set of windows and secrets visible
  to the process.
- Keep plugin dependencies in the profile-owned runtime created by
  `hermes heaw setup`; do not install them into Hermes's Python environment.
- Use a dedicated or disposable desktop session for development.
- Do not place snapshots, screenshots, or logs in synchronized or public folders.
- Rotate any credential observed during raw-value debugging.
- Keep generated artifacts out of Git; the repository ignores JSON, PNG, logs,
  and video by default.

## Supported versions

Security fixes are applied to the latest `1.x` release and the default branch.
Pre-1.0 revisions are unsupported.
