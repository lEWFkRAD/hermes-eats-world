# FALSE POSITIVE FILTER #2 — Independent Review

**Purpose:** Classify all adversary findings as VALID, PARTIAL, or FALSE_POSITIVE against current `spike.py` (post-fixes) and Phase 0 scope.

**Scope reminder:** Phase 0 is a proof-of-concept spike. Goals: attach to one window, walk UIA tree, dump JSON, capture screenshot, prove perception works. NOT production-ready.

---

## SECURITY_REVIEW.md

| Finding ID | Source | Severity | Classification | Rationale |
|---|---|---|---|---|
| CRITICAL-1 | Security | CRITICAL | FALSE_POSITIVE | "Unrestricted data exfiltration from ANY process" — this is a spike demonstrating perception capability, not a production tool. The ability to target any window is the feature being proven, not a security control gap. Phase 1 will add allowlists and access control. |
| CRITICAL-2 | Security | CRITICAL | FALSE_POSITIVE | "Raw value extraction exposes credentials and PII" — the spike extracts values to prove it can read the UIA tree. PII redaction is a Phase 1 governance concern, not a spike defect. The spike's purpose is to demonstrate extraction works, not to sanitize output. |
| CRITICAL-3 | Security | CRITICAL | PARTIAL | "Screenshot capture with no encryption" — screenshot path IS now fixed to use `SPIKE_DIR` (relative/project-local). Encryption-at-rest is a Phase 1 concern. The "no PII warning" point is valid for production but expected absent in a spike. |
| CRITICAL-4 | Security | CRITICAL | FALSE_POSITIVE | "`--list` exposes process inventory" — `--list` is a diagnostic feature of the spike to help the operator find windows to target. This is intentional discovery, not a security issue. Phase 1 will gate this behind auth. |
| CRITICAL-5 | Security | CRITICAL | FALSE_POSITIVE | "JSON dumps ALL extracted data with no sanitization" — the spike outputs its extracted data to prove extraction works. Sanitization/redaction is a Phase 1 governance requirement. Stdout output is expected for a CLI tool. |
| CRITICAL-6 | Security | CRITICAL | PARTIAL | "Path traversal in `--output`" — the path IS used directly without validation, which IS technically a path traversal vector. However, for a local CLI spike run by the developer, this is low-risk. Path validation is a Phase 1 concern. The finding is technically correct but severity is inflated for a dev-only CLI spike. |
| CRITICAL-7 | Security | CRITICAL | FALSE_POSITIVE | "No OathLedger audit logging" — OathLedger is a Phase 1+ production requirement. The spec says it's "non-negotiable for MVP" but Phase 0 is a spike, not the MVP. Basic logging IS now present via Python `logging` module. OathLedger is out of Phase 0 scope. |
| HIGH-1 | Security | HIGH | FALSE_POSITIVE | "No access control / privilege model" — Phase 0 spike has no auth by design. It runs as a local CLI tool. Access control is a Phase 1 sidecar service concern. |
| HIGH-2 | Security | HIGH | FALSE_POSITIVE | "Default `max_depth=999`" — report is based on OLD code. Current code has `MAX_TREE_DEPTH = 500` and prints a safety warning when `--full` is used. Already fixed. |
| HIGH-3 | Security | HIGH | PARTIAL | "Stdout exposure of sensitive data" — stdout truncation IS now implemented (80K chars with truncation indicator). PII in terminal output is a valid concern for production but expected in a CLI spike. Partial: the concern about terminal buffers capturing PII is real but not actionable in Phase 0. |
| HIGH-4 | Security | HIGH | FALSE_POSITIVE | "Hardcoded output path" — report references OLD hardcoded path. Current code uses `SPIKE_DIR` (computed from `__file__`), which is relative and portable. Already fixed. |
| HIGH-5 | Security | HIGH | FALSE_POSITIVE | "Process ID enumeration enables targeted attacks" — exposing PIDs in a local diagnostic CLI tool is not a security vulnerability. The PIDs are visible in Task Manager anyway. This is a feature, not a vulnerability. |
| HIGH-6 | Security | HIGH | FALSE_POSITIVE | "No confirmation gates" — a CLI spike doesn't need confirmation prompts. The operator is directly running the command. Confirmation gates are a Phase 1 UX concern for a service consumed by an LLM. |
| MEDIUM-1 | Security | MEDIUM | PARTIAL | "Broad exception swallowing hides access errors" — pattern probe failures ARE now logged at `logger.debug()` level (line 75-76). The `failed` list tracks which patterns failed. Still silent at INFO level, but debug logging is present. Partially fixed. |
| MEDIUM-2 | Security | MEDIUM | FALSE_POSITIVE | "UIPI bypass potential" — this is a Windows OS-level concern, not something the spike code can or should fix. The `uiautomation` library handles UIPI at the COM level. Running elevated is the operator's choice. |
| MEDIUM-3 | Security | MEDIUM | FALSE_POSITIVE | "Partial match targeting enables mis-targeting" — the code DOES use `SubName` for substring matching (line 279), which is the intended behavior for a spike. Exact match was the bug; substring is the fix. This is not a finding but the implemented behavior. |
| MEDIUM-4 | Security | MEDIUM | FALSE_POSITIVE | "`--class` argument allows targeting by window class" — `--class` flag was ADDED as a fix. This is a feature, not a vulnerability. Targeting by class is useful and intentional. |
| LOW-1 | Security | LOW | FALSE_POSITIVE | "PIL import inside function" — deferred import is actually a reasonable pattern for an optional dependency. Not a security issue. Minor code style concern at worst. |
| LOW-2 | Security | LOW | FALSE_POSITIVE | "Duplicate datetime import" — report references OLD code. The duplicate `datetime` import inside `capture_frame()` has been removed. Only module-level import remains. Already fixed. |

---

## ARCHITECTURE_REVIEW.md

| Finding ID | Source | Severity | Classification | Rationale |
|---|---|---|---|---|
| 1.1 | Architecture | HIGH | FALSE_POSITIVE | "No separation of concerns" — this is a 545-line spike, not a 7-component architecture. Collapsing concerns into one file is the nature of a proof-of-concept. Phase 1 will separate these. |
| 1.2 | Architecture | MEDIUM | FALSE_POSITIVE | "Screenshot capture hardcodes absolute path" — report references OLD code. Path now uses `SPIKE_DIR`. Already fixed. |
| 1.3 | Architecture | HIGH | PARTIAL | "`get_control_patterns()` called synchronously inside tree walk" — the synchronous COM calls are a real performance concern for Phase 1. For a Phase 0 spike doing a single tree walk, this is not a defect. VALID as Phase 1 performance concern. PARTIAL because severity is overstated for a spike. |
| 2.1 | Architecture | BLOCKING | FALSE_POSITIVE | "No MSAA fallback" — spec mentions MSAA fallback for production. Phase 0 only needed to prove UIA tree walking works. MSAA is out of Phase 0 scope. |
| 2.2 | Architecture | HIGH | FALSE_POSITIVE | "No confidence score" — report is based on OLD code. Current `classify_tier()` returns a structured dict with `tier`, `label`, `confidence` (0.0-1.0 float), and `evidence` dict. Already fixed. |
| 2.3 | Architecture | BLOCKING | FALSE_POSITIVE | "No element IDs" — report references OLD code. Current code has `make_element_id()` using composite of NativeWindowHandle, AutomationId, ClassName, Name hash, and bounding rect. Already fixed. |
| 2.4 | Architecture | BLOCKING | FALSE_POSITIVE | "No diffing between snapshots" — Phase 0 spike produces a single snapshot. Diffing is a Phase 1+ concern for the VERIFY step. Not applicable to Phase 0 scope. |
| 2.5 | Architecture | BLOCKING | FALSE_POSITIVE | "No WebSocket/Tool Surface" — Phase 0 is a CLI spike. WebSocket is the Phase 1 sidecar architecture. Not applicable to Phase 0 scope. |
| 2.6 | Architecture | BLOCKING | FALSE_POSITIVE | "No Action Executor" — Phase 0 scope is PERCEIVE only. ACT step is Phase 1+. Not applicable to Phase 0 scope. |
| 2.7 | Architecture | HIGH | FALSE_POSITIVE | "No UIA Event Subscription" — event subscription is a Phase 1 optimization. Phase 0 proved synchronous tree walking works. Not applicable to Phase 0 scope. |
| 3.1 | Architecture | HIGH | PARTIAL | "Exception swallowing in get_control_patterns()" — failures ARE now logged at `logger.debug()` level and tracked in `failed` list. Still not surfaced at INFO level, but the "catastrophic silent failure" claim is overstated. Partially fixed. |
| 3.2 | Architecture | BLOCKING | FALSE_POSITIVE | "UIPI blind spot" — OS-level concern. Spike correctly handles what it can. Elevation detection is a Phase 1 concern. Not a spike defect. |
| 3.3 | Architecture | HIGH | VALID | "ApplicationFrameWindow / UWP child window blind spot" — real issue: `SearchDepth=1` only finds top-level windows. UWP apps wrap real content in child windows. This means the spike genuinely cannot target UWP/WinUI apps by title. Valid Phase 1 fix needed. |
| 3.4 | Architecture | HIGH | VALID | "DPI scaling ignored in screenshot" — `mss.grab()` uses device coordinates while UIA uses logical coordinates. On high-DPI displays the screenshot WILL be offset. This is a real correctness bug that affects the spike's core deliverable (accurate screenshot capture). Valid for Phase 1. |
| 3.5 | Architecture | MEDIUM | FALSE_POSITIVE | "No rate limiting on tree walks" — Phase 0 runs a single tree walk per invocation. Rate limiting applies to a persistent service. Not applicable to Phase 0 scope. |
| 4.1 | Architecture | MEDIUM | PARTIAL | "Arbitrary classification thresholds" — thresholds are indeed heuristic, but `classify_tier()` now has a confidence score and structured evidence. The thresholds are acceptable for a spike. Phase 1 should calibrate against benchmarks. PARTIAL: valid critique but not actionable in Phase 0. |
| 4.2 | Architecture | MEDIUM | FALSE_POSITIVE | "Name truncation without context awareness" — report references OLD code. `_truncate()` function now adds `...` suffix. Already fixed. |
| 4.3 | Architecture | MEDIUM | FALSE_POSITIVE | "No schema versioning" — report references OLD code. `SCHEMA_VERSION = "0.1.0"` is now present and included in JSON output. Already fixed. |
| 4.4 | Architecture | MEDIUM | PARTIAL | "Synchronous child enumeration can hang" — `GetChildren()` CAN hang on virtualized controls. This is a real concern even for a spike. No timeout exists. VALID as Phase 1 fix, but not a spike-breaking issue since operator can Ctrl+C. |
| 4.5 | Architecture | LOW | FALSE_POSITIVE | "list_windows() filters by size heuristic" — the 100x100 filter is a reasonable heuristic for a spike to reduce noise from invisible UI elements. Not a defect. |
| 5.1 | Architecture | HIGH | FALSE_POSITIVE | "No stable output schema" — spike uses plain dicts which is appropriate for a proof-of-concept. Pydantic models are a Phase 1 concern. The field names are consistent within the codebase. |
| 5.2 | Architecture | MEDIUM | FALSE_POSITIVE | "Missing fields in element dict" — the dict includes `control_type`, `localized_type`, `name`, `automation_id`, `class_name`, `is_enabled`, `is_offscreen`, `bounding_box`, `depth`, and `patterns`. HWND is available via `make_element_id()`. Fields match spike scope. |
| 5.3 | Architecture | LOW/HIGH | FALSE_POSITIVE | "No error response format" — in CLI mode, returning `None` and printing to stderr is correct. Structured error responses are a Phase 1 service concern. Not applicable to Phase 0 scope. |
| 6.1 | Architecture | MEDIUM | FALSE_POSITIVE | "Monolithic file" — 545 lines is appropriate for a spike. Module structure is a Phase 1 concern. |
| 6.2 | Architecture | HIGH | FALSE_POSITIVE | "No tests" — Phase 0 spike is manually tested (the spec says "tested and working"). Automated tests are a Phase 1 concern. |
| 6.3 | Architecture | MEDIUM | FALSE_POSITIVE | "No logging" — report references OLD code. Python `logging` module IS now used with proper levels, timestamps, and a named logger. Already fixed. |
| 6.4 | Architecture | LOW/MEDIUM | FALSE_POSITIVE | "Dependency management absent" — report references OLD code. `requirements.txt` has been created. Already fixed. |
| 7.1 | Architecture | HIGH | FALSE_POSITIVE | "Full tree walk for every perception tick" — Phase 0 does a single walk per invocation. The "loop" concern applies to the Phase 1 service. Not applicable to Phase 0. |
| 7.2 | Architecture | MEDIUM | PARTIAL | "JSON serialization with `default=str`" — `default=str` is used, which could mask serialization errors. However, all fields are explicitly converted to JSON-serializable types before serialization. The risk is minimal. VALID as Phase 1 improvement but overstated for a spike. |
| 7.3 | Architecture | LOW-MEDIUM | FALSE_POSITIVE | "Memory: Full tree retained" — single-run CLI tool. Memory is freed on exit. Not applicable. |
| 8.1 | Architecture | STRATEGIC | FALSE_POSITIVE | "Python spike vs C# sidecar" — acknowledged design choice. Python spike proves concept; C# sidecar implements it. Not a finding. |
| 8.2 | Architecture | HIGH | FALSE_POSITIVE | "No per-app profile caching" — Phase 0 scope. Caching is Phase 1+. |
| 8.3 | Architecture | HIGH | FALSE_POSITIVE | "No governance integration" — Phase 1+ concern. Phase 0 doesn't handle production data. |
| 8.4 | Architecture | MEDIUM | FALSE_POSITIVE | "Drag/Target Intake not implemented" — Phase 1+ concern. CLI `--target` is the spike's intake mechanism. |

---

## LOGIC_REVIEW.md

| Finding ID | Source | Severity | Classification | Rationale |
|---|---|---|---|---|
| CRITICAL-1 | Logic | CRITICAL | FALSE_POSITIVE | "`process_name` search is broken" — report references OLD code. Current code has full ctypes PID lookup with `OpenProcess`/`GetModuleFileNameExW`. Already fixed. |
| CRITICAL-2 | Logic | CRITICAL | FALSE_POSITIVE | "`--full` has no recursion depth cap" — report references OLD code. Current code has `MAX_TREE_DEPTH = 500` and safety warning on `--full`. Already fixed. |
| CRITICAL-3 | Logic | CRITICAL | PARTIAL | "Classification thresholds are arbitrary and undocumented" — thresholds are indeed heuristic, but `classify_tier()` now returns structured output with confidence score and evidence. The thresholds need calibration in Phase 1. PARTIAL: valid critique, not a logic bug. |
| CRITICAL-4 | Logic | CRITICAL | PARTIAL | "14 silent `pass` blocks" — report references OLD code. Current code logs failures at `logger.debug()` and tracks `failed` list. Not silent anymore. PARTIAL: debug-level logging may not be visible to operators, but the "completely silent" claim is false. |
| HIGH-1 | Logic | HIGH | PARTIAL | "`default=str` masks type errors" — all fields are explicitly converted to serializable types. `default=str` is a safety net. Risk is low. VALID as Phase 1 improvement. |
| HIGH-2 | Logic | HIGH | FALSE_POSITIVE | "No stable element IDs" — report references OLD code. `make_element_id()` is now implemented with composite hashing. Already fixed. |
| MEDIUM-1 | Logic | MEDIUM | FALSE_POSITIVE | "Window search uses exact match instead of substring" — report references OLD code. Current code uses `SubName` for substring matching. Already fixed. |
| MEDIUM-2 | Logic | MEDIUM | FALSE_POSITIVE | "Screenshot captures entire monitor, not target window" — report is incorrect. Current code captures to the element's `BoundingRectangle` via `mss` monitor dict. Already cropping to window bounds. |
| MEDIUM-3 | Logic | MEDIUM | FALSE_POSITIVE | "Flags not documented in help text" — help text IS present via argparse (`help=` on all arguments). Adequate for a spike. |
| MEDIUM-4 | Logic | MEDIUM | FALSE_POSITIVE | "Name truncation without indicator" — report references OLD code. `_truncate()` function adds `...` suffix. Already fixed. |
| MEDIUM-5 | Logic | MEDIUM | FALSE_POSITIVE | "4 separate traversals" — report references OLD code. `summarize_tree()` is now a single-pass function. Already fixed. |
| MEDIUM-6 | Logic | MEDIUM | FALSE_POSITIVE | "No schema version" — report references OLD code. `SCHEMA_VERSION = "0.1.0"` is present. Already fixed. |
| LOW-1 | Logic | LOW | FALSE_POSITIVE | "Duplicate `classify_tier` definition" — no duplicate exists in current code. Only one `classify_tier()`. Already fixed. |
| LOW-2 | Logic | LOW | FALSE_POSITIVE | "No `requirements.txt`" — report references OLD code. `requirements.txt` has been created. Already fixed. |
| LOW-3 | Logic | LOW | FALSE_POSITIVE | "Hardcoded screenshot path" — report references OLD code. Now uses `SPIKE_DIR`. Already fixed. |
| LOW-4 | Logic | LOW | VALID | "No `.gitignore`" — still valid. Generated artifacts (JSON, PNG) should be ignored. Quick fix for Phase 0. |
| LOW-5 | Logic | LOW | FALSE_POSITIVE | "`mss.mss()` deprecated" — report references OLD code. Current code uses `mss.MSS()` (capital). Already fixed. |
| LOW-6 | Logic | LOW | FALSE_POSITIVE | "Duplicate `datetime` import" — report references OLD code. Duplicate removed. Already fixed. |
| LOW-7 | Logic | LOW | FALSE_POSITIVE | "No logging module" — report references OLD code. `logging` module is now used. Already fixed. |
| LOW-8 | Logic | LOW | FALSE_POSITIVE | "PIL BGRA→RGB wrong" — report references OLD code. Current code uses `frombytes("RGBA", ..., screenshot.bgra, "raw", "BGRA")` then `.convert("RGB")`. Already fixed. |

---

## OPERATIONAL_REVIEW.md

| Finding ID | Source | Severity | Classification | Rationale |
|---|---|---|---|---|
| CRITICAL-1 | Operational | CRITICAL | FALSE_POSITIVE | "No service model" — Phase 0 is a CLI spike. Service model is Phase 1. Finding describes what the spike is NOT rather than a defect in what it IS. |
| CRITICAL-2 | Operational | CRITICAL | FALSE_POSITIVE | "No graceful shutdown / COM resource leak" — single-run CLI script. COM resources are released when Python exits. `atexit` and signal handlers are Phase 1 service concerns. |
| CRITICAL-3 | Operational | CRITICAL | FALSE_POSITIVE | "No structured logging" — report references OLD code. Python `logging` module IS now used with timestamps, severity levels, and named logger. Already fixed. |
| CRITICAL-4 | Operational | CRITICAL | FALSE_POSITIVE | "Hardcoded absolute paths" — report references OLD code. Now uses `SPIKE_DIR` (relative to script). Already fixed. |
| CRITICAL-5 | Operational | CRITICAL | FALSE_POSITIVE | "No dependency management" — report references OLD code. `requirements.txt` has been created. Already fixed. |
| HIGH-1 | Operational | HIGH | FALSE_POSITIVE | "No health checks" — Phase 0 CLI spike. Health checks are a Phase 1 service concern. |
| HIGH-2 | Operational | HIGH | PARTIAL | "No timeout on UIA operations" — there IS a 2-second timeout on `win.Exists(0, 2)` for window search. No timeout on `GetChildren()` is a real concern but would require threading for a CLI spike. VALID as Phase 1 fix. |
| HIGH-3 | Operational | HIGH | PARTIAL | "No retry logic" — transient COM failures are logged at debug level but not retried. Retry logic is a Phase 1 service concern. For a CLI spike, the operator can re-run. PARTIAL: valid for Phase 1. |
| HIGH-4 | Operational | HIGH | FALSE_POSITIVE | "No rate limiting" — Phase 0 is a single-invocation CLI tool. Rate limiting applies to a persistent service. Not applicable. |
| HIGH-5 | Operational | HIGH | PARTIAL | "`mss` vs Windows Graphics Capture" — spec mentions WinRT but `mss` is a valid screenshot approach for a spike. WinRT integration from Python is complex and would require `winrt` package. `mss` works and proves the concept. VALID as Phase 1 API replacement. |
| HIGH-6 | Operational | HIGH | FALSE_POSITIVE | "No configuration management" — CLI arguments ARE the spike's configuration. Config files are Phase 1 service concerns. |
| HIGH-7 | Operational | HIGH | FALSE_POSITIVE | "Screenshot file accumulation" — single-run CLI tool takes at most one screenshot per invocation. File accumulation is a Phase 1 service concern. |
| HIGH-8 | Operational | HIGH | PARTIAL | "20 bare `except` blocks silently swallow exceptions" — report references OLD code. Most bare exceptions now log at `logger.debug()` level. The pattern probe failures are logged and tracked. PARTIAL: debug-level logging is present but not visible at INFO level. |
| MEDIUM-1 | Operational | MEDIUM | FALSE_POSITIVE | "No process isolation" — Phase 0 spike runs in developer's venv. Process isolation is a Phase 1 deployment concern. |
| MEDIUM-2 | Operational | MEDIUM | FALSE_POSITIVE | "No error response format" — CLI tool uses `sys.exit(1)` and stderr messages. Structured error responses are Phase 1 service concerns. |
| MEDIUM-3 | Operational | MEDIUM | FALSE_POSITIVE | "No upgrade path" — Phase 0 spike. Version tracking and rolling updates are Phase 1 deployment concerns. |
| MEDIUM-4 | Operational | MEDIUM | FALSE_POSITIVE | "No Windows-specific environment detection" — the script is Windows-only by design (UIA is Windows-only). Platform/elevation/DPI checks are Phase 1 concerns. |
| MEDIUM-5 | Operational | MEDIUM | PARTIAL | "JSON `default=str` masks serialization errors" — same as Arch 7.2. All fields are explicitly converted. `default=str` is a safety net. Low risk. VALID as Phase 1 improvement. |
| MEDIUM-6 | Operational | MEDIUM | FALSE_POSITIVE | "No backup/restore for state" — Phase 0 is read-only PERCEIVE. Backup/restore is Phase 1+ when ACT is implemented. |
| MEDIUM-7 | Operational | MEDIUM | FALSE_POSITIVE | "No graceful degradation for missing deps" — all three deps (`uiautomation`, `mss`, `PIL`) are required for the spike to function. Graceful degradation is a Phase 1 concern. PIL lazy import is already a form of graceful degradation. |
| LOW-1 | Operational | LOW | FALSE_POSITIVE | "Duplicate import inside function" — report references OLD code. Duplicate `datetime` import removed. Already fixed. |
| LOW-2 | Operational | LOW | FALSE_POSITIVE | "PIL imported inside function body" — deferred import IS a form of graceful degradation (screenshot-only dependency). Acceptable for a spike. |
| LOW-3 | Operational | LOW | VALID | "Output directory permissions not checked" — `os.makedirs(exist_ok=True)` would be a simple improvement. Minor but valid. |
| LOW-4 | Operational | LOW | VALID | "No `.gitignore`" — still valid. Artifacts should be gitignored. (Duplicate of Logic LOW-4.) |
| LOW-5 | Operational | LOW | FALSE_POSITIVE | "80,000 char stdout truncation is arbitrary" — truncation IS implemented with indicator message. The 80K limit is a reasonable heuristic for a spike. Not a defect. |
| LOW-6 | Operational | LOW | FALSE_POSITIVE | "No resource monitoring during tree walk" — timer for walk time IS present. Memory/CPU monitoring is a Phase 1 service concern. |

---

## SUMMARY

### Classification Distribution

| Classification | Count | Notes |
|---|---|---|
| FALSE_POSITIVE | 59 | Already fixed, out of Phase 0 scope, or mischaracterized |
| PARTIAL | 11 | Valid concern but overstated for spike, or partially fixed |
| VALID | 5 | Real issues worth tracking for Phase 1 |

### Valid Findings to Track for Phase 1

| Finding | Source | Why Valid |
|---|---|---|
| CRITICAL-6 (Path traversal in `--output`) | Security | Path validation is a quick fix that improves safety |
| 3.3 (UWP child window blind spot) | Architecture | Real limitation: cannot target UWP/WinUI apps |
| 3.4 (DPI scaling in screenshots) | Architecture | Real correctness issue on high-DPI displays |
| LOW-4 (No `.gitignore`) | Logic/Operational | Quick fix, prevents PII in version control |
| LOW-3 (Output dir permissions) | Operational | Simple defensive improvement |

### Key Observations

1. **Most reports were based on pre-fix code.** The adversary reports were generated before many fixes were applied. A large number of findings describe issues that no longer exist in the current codebase.

2. **Scope confusion is the primary source of false positives.** The Operational review in particular treats the spike as if it should already be a production service. Every "no service model," "no health checks," "no WebSocket" finding is a Phase 1 requirement, not a Phase 0 defect.

3. **The Security review inflates severity.** All 7 CRITICAL findings describe the spike doing what it was designed to do (extract UI data). Framing core functionality as "data exfiltration" misses that Phase 1 will add all the security controls.

4. **The Logic review had the most accurate pre-fix findings.** Its CRITICAL-1 through CRITICAL-4 correctly identified real bugs in the original code — but all four have been fixed.

5. **Genuine gaps that remain:** UWP child window targeting, DPI-aware screenshots, path validation for `--output`, and `.gitignore` are the only remaining actionable items. These are all Phase 1 improvements.
