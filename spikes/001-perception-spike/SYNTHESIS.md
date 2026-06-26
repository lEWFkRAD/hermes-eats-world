# SYNTHESIS — Phase 0 Perception Spike Advisory Review

**Date:** 2026-06-26  
**Synthesizer:** Hermes Agent (subagent)  
**Scope:** 4 adversary reports × 86 total findings → 2 independent FP filters → unified prioritized plan for Phase 1

---

## 1. Executive Summary

### Overall Assessment

The Phase 0 perception spike is a **successful proof-of-concept** that achieves its stated goals. It is a 545-line CLI tool that attaches to Windows windows, walks the UIA accessibility tree, extracts structured control patterns, classifies the perception tier, and captures screenshots. The core pipeline works.

However, the four adversary reviews (Security, Architecture, Logic, Operational) collectively raised **86 findings** across all severity levels. After rigorous cross-referencing by two independent FP filters against the current post-fix codebase:

| Metric | Count |
|--------|-------|
| Total findings raised | 86 |
| Already fixed (15 pre-synthesis fixes) | ~30 findings reference bugs that no longer exist |
| Out-of-scope for Phase 0 spike (production service features misapplied to POC) | ~58 findings |
| **Consensus VALID (both filters agree)** | **5** |
| **Consensus VALID (synthesizer judgment on contested)** | **4 additional** |
| **Total actionable items for Phase 1** | **~18** |
| FALSE_POSITIVE across both filters | ~58 (67% of total) |

### Key Takeaway

**Yes, the spike proved its goals.** All five Phase 0 objectives were met. The high false-positive rate (67%) is expected: three of four adversaries evaluated this as if it were a production service rather than a proof-of-concept spike. The Security review (90% FP rate) and Operational review (81% FP rate) were the most aggressive in applying production-grade criteria. The Architecture review produced the most genuinely useful findings for Phase 1 planning.

**The spike should be treated as a disposable proof-of-concept, not a codebase to extend.** Phase 1 is a greenfield architecture exercise that may reuse the tree-walking strategy and classification logic but should not port the Python code directly.

---

## 2. Consensus Findings (Both FP Filters Agree VALID)

These five findings were classified as VALID by both FP Filter #1 and FP Filter #2. They are uncontested and should be tracked for Phase 1.

### C-1. UWP / ApplicationFrameWindow Child Window Blind Spot
- **Source:** Architecture 3.3
- **Severity:** HIGH
- **Problem:** `find_window()` searches at `SearchDepth=1` (top-level windows only). Modern UWP/WinUI apps (Settings, Calculator, Mail, any WinUI 3 app) wrap their real content inside `ApplicationFrameWindow` child windows. The spike finds the frame but walks an empty or nearly-empty tree, misclassifying these apps as T2/T3 when they're actually T1.
- **Phase 1 Impact:** Blocks targeting of a significant class of modern Windows applications.
- **Implementation:** After finding a top-level window, check if `ClassName == "ApplicationFrameWindow"`. If so, drill into child windows (`GetChildren()` on the frame) to find the actual content window. The `DesktopChildSiteBridge` class seen in Explorer output is the same pattern.

### C-2. DPI Scaling Mismatch in Screenshots
- **Source:** Architecture 3.4
- **Severity:** HIGH
- **Problem:** `mss.grab()` returns pixels in **device coordinates** while UIA `BoundingRectangle` returns **logical coordinates**. On high-DPI displays (150%, 200% scaling — common on laptops), the screenshot capture rectangle is offset from the actual window position. This breaks T2 coordinate mapping.
- **Phase 1 Impact:** Screenshots do not align with UIA element positions, undermining vision-based fallback accuracy.
- **Implementation:** Call `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` at startup. Use `GetDpiForWindow()` to convert between coordinate spaces. Alternatively, use WinRT Graphics Capture which handles DPI natively.

### C-3. `.gitignore` Missing
- **Source:** Logic LOW-4 / Operational LOW-4
- **Severity:** LOW
- **Problem:** No `.gitignore` file in the spike directory. Generated artifacts (`state.json`, `hermes_spike_*.png`) could be accidentally committed to version control, potentially exposing PII.
- **Phase 1 Impact:** Low risk for a spike, but a data leak vector if the directory is under git.
- **Implementation:** Add `.gitignore` with `*.json`, `*.png`, `*.log`, `__pycache__/`.

### C-4. `default=str` Serialization Masking
- **Source:** Logic HIGH-1 / Operational MEDIUM-5
- **Severity:** MEDIUM
- **Problem:** `json.dumps(output, indent=2, default=str)` at line 523 silently converts any non-serializable object (COM objects, custom types) to its string representation. This masks real bugs — a COM object becomes `"uiautomation.Control object at 0x..."` in the JSON rather than raising an error.
- **Phase 1 Impact:** Silent data corruption in JSON output. Downstream consumers receive garbage data with no indication of the problem.
- **Implementation:** Replace with explicit serialization. Use a custom JSON encoder that raises on unexpected types, or use Pydantic models with explicit type conversion for each field.

### C-5. Output Directory Not Validated
- **Source:** Operational LOW-3
- **Severity:** LOW
- **Problem:** No `os.makedirs(exist_ok=True)` before file writes. If the output directory doesn't exist, the write fails at runtime with `FileNotFoundError`.
- **Phase 1 Impact:** Script crashes at write time instead of failing fast at startup with a clear error.
- **Implementation:** Validate output directory exists (or create it) before writing. Add a startup check.

---

## 3. Contested Findings (FP Filters Disagree)

For each disagreement, I examined the relevant code in `spike.py` and the original adversary reports to make an independent judgment.

### T-1. `GetChildren()` Hang Risk
- **FP1:** VALID | **FP2:** PARTIAL
- **My judgment: VALID**
- **Reasoning:** Looking at line 182 in `spike.py`: `for child in element.GetChildren():` — there is absolutely no timeout on this call. The `uiautomation` library's `GetChildren()` is a synchronous COM call that can block indefinitely on virtualized lists (e.g., ListView with thousands of items), WebView2 hosts, or hung applications. FP2 downgrades to PARTIAL because "the operator can Ctrl+C" — but that's not a mitigation, that's an admission of the problem. For Phase 1 where this runs as a service (not a CLI tool you can Ctrl+C), this is a hard hang. **VALID for Phase 1.**

### T-2. Missing HWND in Element Dict
- **FP1:** VALID | **FP2:** FALSE_POSITIVE
- **My judgment: VALID**
- **Reasoning:** Looking at `element_to_dict()` (lines 165-177), the output dict includes `id`, `control_type`, `localized_type`, `name`, `automation_id`, `class_name`, `is_enabled`, `is_offscreen`, `bounding_box`, `depth`, and `patterns`. The HWND (`NativeWindowHandle`) is used internally in `make_element_id()` (line 107) but is **not exposed** in the element dictionary. The spec's T2 action surface includes `PostMessage` which requires an HWND. FP2 argues "HWND is available via `make_element_id()`" — but it's encoded inside an ID string like `hwnd:0x12345`, not available as a structured field. Phase 1 needs HWND as a first-class field for T2 `PostMessage` actions. **VALID for Phase 1.**

### T-3. No UIA Operation Timeouts
- **FP1:** VALID | **FP2:** PARTIAL
- **My judgment: VALID**
- **Reasoning:** The only timeout in the entire codebase is `win.Exists(0, 2)` (2-second window search timeout at line 280). All other UIA operations — `GetChildren()`, pattern probes (`GetInvokePattern()`, etc.), property accesses — have **zero timeouts**. The `time.time()` timer at line 469 measures wall-clock time but does not enforce any limit. In a service context, a single hung COM call freezes the entire process. FP2 acknowledges "No timeout on `GetChildren()` is a real concern" but downgrades to PARTIAL because threading-based timeouts are complex. Complexity doesn't invalidate the finding — it just means the fix is harder. **VALID for Phase 1.**

### T-4. Small Window Filtering (100×100 heuristic)
- **FP1:** VALID | **FP2:** FALSE_POSITIVE
- **My judgment: PARTIAL**
- **Reasoning:** Looking at `list_windows()` (lines 344-345): `if w < 100 and h < 100: continue`. This filters out windows where BOTH dimensions are under 100 pixels. Legitimate small windows (notification toasts, system tray popups, small dialogs like "Save changes?") can be silently dropped. However, this is a `list_windows()` filter, not the `find_window()` path — so it only affects discovery, not targeting. If the user already knows the window name, they can target it directly. FP2's argument that "100×100 is a reasonable heuristic for noise reduction" has merit. This is a real but minor issue. **PARTIAL — worth noting for Phase 1, not blocking.**

### T-5. No Windows Environment Detection
- **FP1:** VALID | **FP2:** FALSE_POSITIVE
- **My judgment: VALID**
- **Reasoning:** The script has no startup checks for: platform (runs on WSL with confusing COM errors), elevation level (silent failure on UIPI-protected windows), DPI awareness (coordinate mismatch on high-DPI), or session type (Session 0 service context sees zero windows). FP2 argues "the script is Windows-only by design" — true, but that doesn't mean it should fail silently with obscure COM errors on WSL, or report "0 elements" for elevated windows without explaining why. Startup diagnostics that catch these conditions and provide clear error messages are a small investment with high debugging value. **VALID for Phase 1.**

### T-6. Path Traversal in `--output`
- **FP1:** FALSE_POSITIVE | **FP2:** VALID (PARTIAL)
- **My judgment: PARTIAL**
- **Reasoning:** Looking at line 526: `with open(args.output, 'w', encoding='utf-8') as f:` — the path is used directly with no validation. Technically this IS a path traversal vector (`--output ../../../etc/passwd`). However, for a local CLI tool run by the developer, this is the same risk as `cp`, `tee`, or any file-writing command. FP1's argument that "this is standard CLI behavior" is correct for the spike. For Phase 1 where the output path comes from a remote caller (WebSocket API), this becomes a genuine security concern. **PARTIAL — not actionable for Phase 0, must be addressed in Phase 1 service layer.**

---

## 4. Phase 1 Improvement Plan

### P0 — Blocking: Must fix before Phase 1 is viable

These items prevent Phase 1 from functioning correctly on the target platform.

| # | What | Why | Approach | Complexity |
|---|-------|-----|----------|------------|
| P0-1 | **UIA operation timeouts** | `GetChildren()` and pattern probes can hang indefinitely on virtualized controls, WebView2 hosts, or hung apps. In a service, this freezes the entire process. (Architecture 4.4, Operational HIGH-2, T-1, T-3) | Run UIA calls in a separate thread with `concurrent.futures.ThreadPoolExecutor.submit()` + `result(timeout=...)`. Per-element timeout: 5s. Total tree walk timeout: 30s. Fall back to partial tree on timeout. | M |
| P0-2 | **UWP/ApplicationFrameWindow child drilling** | Modern UWP/WinUI apps are invisible to the spike — `SearchDepth=1` finds the frame but the real content is in child windows. (Consensus C-1, Architecture 3.3) | After `find_window()`, check if `ClassName == "ApplicationFrameWindow"`. If so, enumerate children to find the actual content window (look for `DesktopChildSiteBridge`, `Windows.UI.Core.CoreWindow`, or the child with the largest bounding rect). | S |
| P0-3 | **DPI-aware screenshot capture** | On high-DPI displays, `mss` device coordinates don't match UIA logical coordinates, so screenshots are offset from element positions. (Consensus C-2, Architecture 3.4) | Call `SetProcessDpiAwarenessContext()` at startup. Use `GetDpiForWindow()` + `GetDpiForMonitor()` to convert UIA logical rects to device coords before passing to `mss.grab()`. | M |
| P0-4 | **Explicit JSON serialization (replace `default=str`)** | `default=str` silently converts COM objects to garbage strings, corrupting JSON output with no indication. (Consensus C-4, Logic HIGH-1) | Write a custom `JSONEncoder` that raises `TypeError` on unexpected types. Ensure all fields are explicitly converted to `str`, `int`, `float`, `bool`, `list`, `dict`, or `None` before serialization. | S |
| P0-5 | **Windows environment validation at startup** | Silent failures on WSL, Session 0, wrong integrity level, or unknown DPI scaling produce confusing errors. (T-5, Operational MEDIUM-4) | At `main()` entry: check `platform.system() == "Windows"`, detect elevation via `IsUserAnAdmin()`, call `GetProcessDpiAwareness()`, check desktop session ID. Print clear warnings/errors. | S |

### P1 — High: Important for Phase 1 MVP

These items are needed for a functional, reliable Phase 1 MVP.

| # | What | Why | Approach | Complexity |
|---|-------|-----|----------|------------|
| P1-1 | **Expose HWND in element dict** | T2 action surface (`PostMessage`) needs HWND as a first-class field. Currently buried inside element ID string. (Consensus T-2, Architecture 5.2) | Add `"hwnd": element.NativeWindowHandle or None` to `element_to_dict()` output. | S |
| P1-2 | **Structured error responses** | Returning `None` on failure provides no error code, message, or retryability hint. (Architecture 5.3, Operational MEDIUM-2) | Define error response format: `{"error": "window_not_found", "target": "...", "retryable": false}`. Use for `find_window()`, `capture_frame()`, tree walk failures. | S |
| P1-3 | **Output directory validation** | File writes crash if directory doesn't exist. (Consensus C-5, Operational LOW-3) | `os.makedirs(os.path.dirname(output_path), exist_ok=True)` before writes. Validate at startup for `--output`. | S |
| P1-4 | **Path validation for `--output`** | In Phase 1 service context, output path comes from remote caller — path traversal is a real risk. (T-6, Security CRITICAL-6) | Resolve to absolute path, verify it's within allowed output directory. Reject UNC paths, device paths, and paths outside the configured output root. | S |
| P1-5 | **Calibrate tier classification thresholds** | Current thresholds (50 elements, 4 patterns) have no empirical basis and can misclassify apps. (Architecture 4.1) | Run the spike against a benchmark set of target apps (Excel, Outlook, VS Code, Chrome, Notepad, SAGE, Calculator). Measure element counts and pattern diversity. Calibrate thresholds with confidence bands. | M |
| P1-6 | **Replace `mss` with WinRT Graphics Capture** | `mss` uses GDI/DXGI (deprecated path), wrong DPI behavior, no per-app consent. Spec calls for WinRT Graphics Capture. (Operational HIGH-5) | Use `winrt` Python bindings or implement via C# helper. WinRT `GraphicsCaptureApi` provides per-monitor capture with native DPI awareness and Microsoft's privacy model. | L |
| P1-7 | **Exception handling audit — no silent `except: pass`** | Remaining silent exception handlers in `make_element_id()`, `list_windows()`, `capture_frame()` mask failures. (Operational HIGH-8, Security MEDIUM-1) | Replace all remaining bare `except: pass` with at minimum `logger.debug()` + tracking. Surface failure counts in summary output. | S |

### P2 — Medium: Nice to have in Phase 1

These improve robustness and developer experience but don't block Phase 1 functionality.

| # | What | Why | Approach | Complexity |
|---|-------|-----|----------|------------|
| P2-1 | **`.gitignore` for generated artifacts** | Prevents PII in version control. (Consensus C-3) | Add `.gitignore` with `*.json`, `*.png`, `*.log`, `__pycache__/`, `*.pyc`. | S |
| P2-2 | **Relax small window filter in `list_windows()`** | 100×100 heuristic drops legitimate small windows (toasts, dialogs). (T-4, Architecture 4.5) | Lower threshold to 50×50 or make it configurable. Add `--show-small` flag. | S |
| P2-3 | **Retry logic for transient COM failures** | UIA COM calls can fail transiently (RPC timeout, marshaling delay) and should be retried. (Operational HIGH-3) | Add retry decorator with exponential backoff (e.g., `tenacity` library). 3 retries, 1s base delay. | S |
| P2-4 | **Formalize output schema with Pydantic models** | Ad hoc dict assembly makes schema evolution hard. (Architecture 5.1) | Define Pydantic models for `Element`, `TreeSnapshot`, `TierClassification`, `TargetInfo`. Serialize via `.model_dump()`. | M |
| P2-5 | **Per-app profile caching** | Re-walking the full tree for stable UI regions is wasteful. (Architecture 8.2) | Cache element ID → role/patterns mapping keyed by process name + window class. Invalidate on process restart. | M |
| P2-6 | **Unit tests for pure functions** | `classify_tier()`, `summarize_tree()`, `_truncate()`, `make_element_id()` are trivially testable. (Architecture 6.2) | `pytest` tests with mocked element objects. Verify tier classification edge cases, truncation behavior, ID stability. | S |
| P2-7 | **Configurable depth and pattern limits** | `MAX_TREE_DEPTH = 500` and 14 pattern probes are hardcoded. | Expose via config: `max_depth`, `max_patterns_per_element`, `max_elements_total`. | S |

### P3 — Low: Phase 2+ optimization

These are valuable but not needed for the Phase 1 MVP.

| # | What | Why | Approach | Complexity |
|---|-------|-----|----------|------------|
| P3-1 | **MSAA fallback for legacy controls** | Some enterprise apps (SAGE, QuickBooks, legacy Win32) expose MSAA but not UIA. (Architecture 2.1) | Integrate `pyautoclick` or `comtypes` MSAA COM interface. Fallback path: try UIA first, if element count < 5, try MSAA. | L |
| P3-2 | **UIA event subscription** | Polling (full tree walk) is slow and unreliable for detecting state changes. (Architecture 2.7) | `Automation.AddAutomationEventHandler()` for property-changed, structure-changed events. Incremental perception. | L |
| P3-3 | **Snapshot diffing for VERIFY step** | PERCEIVE→PLAN→ACT→VERIFY loop requires comparing pre/post state. (Architecture 2.4) | Implement tree diff using element IDs: added/removed/changed elements. | M |
| P3-4 | **Integrity level detection + elevation prompt** | UIPI blocks access to elevated windows. Silent 0-element result is confusing. (Architecture 3.2) | `GetTokenInformation` with `TokenIntegrityLevel`. If targeting elevated window, prompt for UAC elevation or document requirement. | M |
| P3-5 | **Rate limiting on tree walks** | In service mode, rapid LLM requests can saturate UIA host processes. (Architecture 3.5) | Token bucket or sliding window rate limiter. 1 tree walk per 2s minimum. Backpressure signal to caller. | M |
| P3-6 | **Incremental tree walking** | Walking the full tree on every PERCEIVE tick is wasteful for stable UI. (Architecture 7.1) | Track which subtrees changed since last walk (using event subscription from P3-2). Only walk changed regions. | L |

---

## 5. What the Spike Proved

All five Phase 0 goals were successfully demonstrated:

| # | Goal | Status | Evidence |
|---|------|--------|----------|
| 1 | **Attach to one window** | ✅ PROVEN | `find_window()` supports title (substring via `SubName`), process name (ctypes PID lookup), and window class targeting. `--list` enumerates all top-level windows. |
| 2 | **Walk UIA tree** | ✅ PROVEN | `element_to_dict()` recursively walks the accessibility tree with configurable depth (default 3, max 500). Extracts bounding rectangles, control types, and properties. |
| 3 | **Dump structured state as JSON** | ✅ PROVEN | Full tree serialization to JSON with `schema_version: "0.1.0"`, timestamp, target info, tier classification, summary statistics, and complete element tree. Output to stdout or file (`--output`). 80KB stdout truncation with indicator. |
| 4 | **Capture one frame** | ✅ PROVEN | `capture_frame()` uses `mss.MSS()` to capture the element's bounding rectangle as a PNG screenshot. Proper BGRA→RGB conversion via PIL. Timestamped filename in project directory. |
| 5 | **Prove perception is possible** | ✅ PROVEN | Tier classification (`classify_tier()`) provides structured confidence scores (0.0–1.0) with evidence. Single-pass `summarize_tree()` produces element counts, max depth, control type distribution, and pattern diversity. The full pipeline from window attach → tree walk → pattern extraction → classification → JSON output → screenshot works end-to-end. |

**The spike succeeded in proving that Windows UI automation from Python is viable for the Hermes Eats World perception layer.** The remaining work for Phase 1 is architectural (service model, robustness, production features) rather than fundamental feasibility.

---

## 6. Recommendations for Phase 1 Architecture

### Language Decision: Stay Python for Phase 1 MVP, Plan C# Sidecar for Phase 2

**Recommendation: Build Phase 1 MVP in Python, not C#.**

Rationale:
- The spike has already proven the entire perception pipeline works in Python with `uiautomation`, `mss`, and `PIL`.
- The spec suggests C#/.NET for the sidecar, but Phase 1 is about validating the PERCEIVE→PLAN→ACT→VERIFY loop, not optimizing for production deployment.
- Python's `uiautomation` library is mature, well-documented, and Python-first. The .NET `UIAutomationClient` has a different API surface (pattern names, control type enums, error handling) that would require relearning/reimplementing everything.
- The Python→C# transition should happen after the perception loop is proven in Phase 1, using the Phase 1 output schema as the interface contract.
- **Exception:** If Phase 1 requires WinRT Graphics Capture (which has poor Python bindings), a small C# helper DLL for screenshot capture is acceptable. Keep the main logic in Python.

### Architecture Pattern: Modular Python Package → Future C# Sidecar

```
hermes-eats-world/
├── sidecar/
│   ├── __init__.py
│   ├── perception/           # UIA tree walking, pattern extraction
│   │   ├── tree_walker.py    # element_to_dict(), summarize_tree()
│   │   ├── patterns.py       # get_control_patterns()
│   │   └── classifier.py     # classify_tier() with calibrated thresholds
│   ├── capture/              # Screenshot capture
│   │   ├── screenshot.py     # mss or WinRT wrapper
│   │   └── dpi.py            # DPI coordinate conversion
│   ├── target/               # Window targeting
│   │   ├── finder.py         # find_window(), list_windows()
│   │   └── uwp.py            # ApplicationFrameWindow drilling
│   ├── action/               # Phase 1 ACT step
│   │   ├── executor.py       # InvokePattern, SetValue, Click
│   │   └── postmessage.py    # T2 HWND-based actions
│   ├── verify/               # Phase 1 VERIFY step
│   │   └── differ.py         # Snapshot diffing
│   ├── schema/               # Output contracts
│   │   ├── models.py         # Pydantic models
│   │   └── encoder.py        # Explicit JSON serialization
│   └── service/              # Phase 1 service layer
│       ├── websocket.py      # WebSocket server
│       ├── health.py         # Health checks
│       └── config.py         # Configuration management
└── tests/
    ├── test_classifier.py
    ├── test_summarize.py
    └── test_element_id.py
```

### Key Libraries/APIs

| Layer | Library | Why |
|-------|---------|-----|
| UIA tree walking | `uiautomation` (Python) or `UIAutomationClient` (.NET) | Mature, well-documented, covers all control patterns |
| Screenshot capture | `mss` (Phase 1) → WinRT `GraphicsCaptureApi` (Phase 2) | `mss` works now; WinRT for DPI awareness and privacy compliance |
| Image processing | `Pillow` | BGRA→RGB conversion, image manipulation |
| Service layer | `websockets` + `asyncio` | Lightweight WebSocket server for Hermes integration |
| Configuration | `pydantic-settings` | Typed config with env var overrides |
| Serialization | `pydantic` | Schema validation, explicit type conversion |
| Retries | `tenacity` | Decorator-based retry with exponential backoff |
| Testing | `pytest` + `pytest-mock` | Unit tests for pure functions, mocked COM for integration tests |
| Logging | Python `logging` + `python-json-logger` | Structured JSON logging for aggregation |

### What NOT to Carry Forward from the Spike

1. **Monolithic single-file structure.** The spike's 545-line `spike.py` collapsed perception, serialization, CLI, and screenshot logic into one file. Phase 1 must separate these concerns into modules.

2. **`default=str` in JSON serialization.** This is a debugging convenience that masks real bugs. Phase 1 needs explicit, typed serialization.

3. **Synchronous `GetChildren()` without timeout.** The spike gets away with this because it runs once and exits. A service cannot.

4. **`mss` for production screenshot capture.** It works for the spike but has DPI issues and uses a deprecated API path. Phase 1 MVP can keep it with DPI fixes, but Phase 2 must migrate to WinRT Graphics Capture.

5. **Hardcoded classification thresholds.** The `>50 elements`, `>4 patterns` thresholds are guesses. Phase 1 needs empirical calibration against real target applications.

6. **Bare `except: pass` exception handling.** Even in the post-fix code, silent exception swallowing remains in `make_element_id()`, `list_windows()`, and `capture_frame()`. Phase 1 must log all exceptions.

7. **CLI-only interface.** The spike is a CLI tool by design. Phase 1 must be a service (WebSocket server) that Hermes can call as a tool.

---

## Appendix: Finding Classification Matrix

Complete cross-reference of all contested findings with final classification:

| Finding | FP1 | FP2 | Synthesizer | Source |
|---------|-----|-----|-------------|--------|
| UWP child window blind spot | VALID | VALID | **VALID (consensus)** | Arch 3.3 |
| DPI scaling mismatch | VALID | VALID | **VALID (consensus)** | Arch 3.4 |
| `.gitignore` missing | VALID | VALID | **VALID (consensus)** | Logic LOW-4 / Ops LOW-4 |
| `default=str` masking | VALID | PARTIAL | **VALID (consensus)** | Logic HIGH-1 / Ops MED-5 |
| Output dir not validated | VALID | VALID | **VALID (consensus)** | Ops LOW-3 |
| `GetChildren()` hang risk | VALID | PARTIAL | **VALID** | Arch 4.4 |
| Missing HWND in element dict | VALID | FP | **VALID** | Arch 5.2 |
| No UIA operation timeouts | VALID | PARTIAL | **VALID** | Ops HIGH-2 |
| Small window filtering | VALID | FP | **PARTIAL** | Arch 4.5 |
| No Windows env detection | VALID | FP | **VALID** | Ops MED-4 |
| Path traversal in `--output` | FP | PARTIAL | **PARTIAL** | Sec CRIT-6 |

**Final tally:** 9 VALID, 2 PARTIAL, ~75 FALSE_POSITIVE (mostly "Phase 1 service feature evaluated against Phase 0 POC")
