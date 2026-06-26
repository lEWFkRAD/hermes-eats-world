# Architecture Adversarial Review — Hermes Eats World, Phase 0 Perception Spike

**Date:** 2026-06-26
**Reviewer:** Architecture Adversary (subagent)
**Scope:** `spike.py` (495 lines), spec requirements, design document gaps

---

## EXECUTIVE SUMMARY

The spike proves the basic UIA tree walk works. It does not prove anything about the architecture it's supposed to scaffold. There are **22 substantive architectural concerns**, 8 of which are blocking for a production sidecar. The gap between spec intent and spike reality is not incremental — it is structural.

---

## 1. COUPLING VIOLATIONS

### 1.1 Perception ↔ Serialization — No Separation of Concerns
**Location:** `element_to_dict()` (line 147), `main()` (line 455)
**Severity:** HIGH

`element_to_dict()` is simultaneously a tree walker, a serializer, and a pattern extractor. The `main()` function doubles as CLI orchestrator, JSON assembler, and output router. In the spec's 7-component architecture, these map to three distinct build units (Accessibility Introspection Engine, State Serializer, Perception/Verification Loop). The spike collapses all of them into one function with no extractable interface.

**Impact:** When the C# sidecar is built, every one of these responsibilities will need to be surgically separated. Without an explicit interface contract in the spike, the separation will be ad hoc.

### 1.2 Screenshot Capture Hardcodes Absolute Path
**Location:** `capture_frame()` line 337
```python
output_path = f"c:/Users/OnyxB/hermes-eats-world/spikes/001-perception-spike/hermes_spike_{timestamp}.png"
```
**Severity:** MEDIUM (trivial to fix, architecturally revealing)

This is a spike artifact, but it demonstrates no thought about where artifacts live in the sidecar architecture. In production, captured frames would be streamed over WebSocket, not written to disk at a hardcoded path. The absence of any config/dependency injection pattern means the spike teaches the wrong habit.

### 1.3 `get_control_patterns()` is Called Synchronously Inside Tree Walk
**Location:** line 179 — called once per element inside `element_to_dict()`
**Severity:** HIGH

For a tree with 100+ elements, this means 100+ synchronous COM calls per pattern (up to 14 patterns per element). That's **1,400 COM marshalling calls per tree walk**. Each COM call crosses an apartment boundary. This is the single largest scalability concern.

---

## 2. SPEC-TO-IMPLEMENTATION GAPS

### 2.1 No MSAA Fallback (Spec: "UIA primary, MSAA fallback")
**Location:** Entire file — `uiautomation` is the only automation library imported
**Severity:** BLOCKING for T1 universal baseline

The spec explicitly states MSAA fallback for legacy controls. The spike has zero MSAA code. Many enterprise apps (Sage, QuickBooks, legacy Win32) use custom-drawn controls that expose MSAA but not UIA. The tier classification will incorrectly assign T1 to apps that are actually T2.

### 2.2 No Confidence Score (Spec: "Classify tier with confidence score")
**Location:** `classify_tier()` line 352-365
**Severity:** HIGH

The function returns a **string** (`"T1 - Rich accessibility tree"`) instead of a structured confidence score. The spec says "Hermes reasons against this, not pixels" — which means Hermes needs a numeric confidence to decide whether to trust UIA data or request a T2 vision pass. Returning a human-readable string is useless for programmatic reasoning.

**What's needed:** `{ "tier": "T1", "confidence": 0.92, "evidence": { "element_count": 113, "pattern_diversity": 11, "..." } }`

### 2.3 No Element IDs for Cross-Snapshot Referencing
**Location:** `element_to_dict()` line 169-180
**Severity:** BLOCKING for PERCEIVE→PLAN→ACT→VERIFY loop

Elements have no stable, persistent identifier. `AutomationId` is included but is frequently empty (see `state.json` — most elements have `automation_id: ""`). Without stable IDs, the VERIFY step cannot assert "element X now has value Y" because there's no way to correlate elements across snapshots.

**What's needed:** Composite key from `(class_name, automation_id, name_hash, bounding_rect_quantized)` or UIA `NativeWindowHandle`.

### 2.4 No Diffing Between Snapshots
**Location:** Not present
**Severity:** BLOCKING for VERIFY step

The spec's action loop is PERCEIVE → PLAN → ACT → VERIFY. VERIFY requires comparing pre-action and post-action state. The spike produces single-point-in-time snapshots with no diff mechanism. Without diffing, the entire VERIFY concept is unimplemented.

### 2.5 No WebSocket/Tool Surface (Spec: "C#/.NET sidecar with WebSocket tool surface")
**Location:** Entire file — CLI-only via argparse
**Severity:** BLOCKING for integration

The spike is a CLI tool. The spec requires a sidecar service with a WebSocket interface that Hermes can call as a tool. There is zero integration path from spike to Hermes. The CLI design actively works against the service architecture (process-per-call vs persistent connection).

### 2.6 No Action Executor (Spec: "Act T1: invoke control pattern directly")
**Location:** Not present
**Severity:** BLOCKING for ACT step

The spike covers PERCEIVE only. There is no code to invoke an `InvokePattern.Invoke()`, set a value, click a button, or perform any action. Without ACT, the loop is incomplete and the spike cannot validate its own perception (you can't verify perception without testing that actions produce expected state changes).

### 2.7 No UIA Event Subscription (Spec: "subscribing to events instead of polling")
**Location:** Not present
**Severity:** HIGH

The spec mentions event subscription. The spike uses only synchronous tree walks (polling). For a production system watching for state changes (modal dialogs appearing, values updating), polling is both slow and unreliable. UIA provides `Automation.AddAutomationEventHandler()` for exactly this purpose.

---

## 3. FAILURE MODES

### 3.1 Exception Swallowing in `get_control_patterns()`
**Location:** Lines 33-143 — 14 identical `try/except Exception: pass` blocks
**Severity:** HIGH

Silent failures here are catastrophic. If `GetValuePattern()` throws (e.g., UIA host process crashed mid-call), the element silently gets no value pattern. The tier classifier then undercounts patterns, potentially misclassifying a T1 app as T2. In production, every failed pattern probe needs to be logged and surfaced to Hermes.

**Specific risk:** `uiautomation` swallows `COMError` exceptions, which include apartment-state violations, RPC failures, and host-process crashes. These are not recoverable "try again" errors — they indicate the target process is in an inconsistent state.

### 3.2 Elevation/UIPI Blind Spot
**Location:** `find_window()` line 246-272
**Severity:** BLOCKING for elevated targets

The spec calls this out as a risk but the spike has no mitigation. If Hermes runs at integrity level (IL) Medium and targets an elevated window (IL High), `GetChildren()` returns empty or throws. The spike will silently report 0 elements for elevated windows.

**What's needed:** Integrity level detection before attach, documented fallback (require Hermes to run elevated, or use a UAC-prompted broker).

### 3.3 `ApplicationFrameWindow` / UWP Child Window Blind Spot
**Location:** `find_window()` line 246-272
**Severity:** HIGH

Modern UWP/WinUI apps (Settings, Calculator, Mail) host their real content in a child window beneath `ApplicationFrameWindow`. The spike searches only at `SearchDepth=1` (top-level). It will find the frame window but walk the wrong tree.

**Evidence from `state.json`:** The File Explorer test case already shows `Microsoft.UI.Content.DesktopChildSiteBridge` (line 380) — this is a WinUI 3 child site that the spike traversed by accident (because it walked the full tree), not by design. For a UWP app, the top-level window's children would be empty and the spike would misclassify it.

### 3.4 DPI Scaling Ignored in Screenshot
**Location:** `capture_frame()` line 312-349
**Severity:** HIGH for T2 coordinate accuracy

The spec says "T2 coordinate mapping must be DPI-aware." `mss.grab()` returns pixels in **device coordinates**. `element.BoundingRectangle` returns coordinates in **UIA (logical/DPI-unaware) coordinates** for most apps. On a 150% DPI monitor (common on laptops), these do not match. The screenshot will be offset from the actual element bounding box.

**What's needed:** `GetDpiForWindow()` / `SetProcessDpiAwarenessContext()` to reconcile coordinate spaces.

### 3.5 No Rate Limiting on Tree Walks
**Location:** `element_to_dict()` — recursive, unbounded
**Severity:** MEDIUM

Walking the full tree of a complex app (e.g., Visual Studio with multiple solution explorer panes) with `--full` can take 10-30 seconds. If this is called in a loop (the PERCEIVE→PLAN→ACT→VERIFY cycle), it hammers the UIA host process and can cause:
- UIA host process to throttle or drop connections
- Target app to become unresponsive
- Stale reads (tree changes mid-walk)

**What's needed:** Timeout on tree walk, incremental walk (only changed subtrees), or rate limiter.

---

## 4. DESIGN SMELLS

### 4.1 Arbitrary Classification Thresholds
**Location:** `classify_tier()` line 358-365
```python
if total > 50 and len(patterns) > 3:
    return "T1 - Rich accessibility tree"
elif total > 10 and len(patterns) > 0:
    return "T1/T2 - Partial accessibility tree, may need vision fallback"
elif total > 5:
    return "T2 - Sparse accessibility tree, vision primary"
```
**Severity:** MEDIUM (acceptable for spike, must be replaced before production)

These thresholds (`50 elements`, `3 patterns`, `10 elements`, `5 elements`) have no empirical basis. They were chosen by guessing. A well-structured calculator app might have 15 elements with 8 patterns — classified as T1/T2 despite being fully accessible. A bloated Electron app might have 200 div elements with 0 patterns — classified as T1 despite being useless for automation.

**What's needed:** Thresholds calibrated against a benchmark of real target apps (Excel, Outlook, VS Code, Chrome, Notepad, Sage, QuickBooks).

### 4.2 Name Truncation Without Context Awareness
**Location:** line 172: `element.Name[:200]`
**Severity:** MEDIUM

Truncating at 200 characters without any indication of truncation (`...` suffix) means Hermes has no way to know if the name is complete. A truncated `AutomationId` or `Name` could break downstream matching logic. The `ValuePattern.Value` is truncated at 500 chars (line 45) with the same problem.

### 4.3 No Schema Versioning
**Location:** `main()` line 455-471 — JSON output
**Severity:** MEDIUM

The JSON output has no version field. When the schema evolves (and it will), there's no way to distinguish old from new output. Hermes tool output is consumed by an LLM that may have been trained on or cached with a specific schema.

### 4.4 Synchronous Child Enumeration Can Hang
**Location:** line 185: `for child in element.GetChildren()`
**Severity:** MEDIUM

`GetChildren()` in `uiautomation` can block indefinitely on some controls (e.g., virtualized lists, WebView2 hosts). There's no timeout on child enumeration. For the `--full` flag on a complex app, this is a denial-of-service vector.

### 4.5 `list_windows()` Filters by Size Heuristic
**Location:** line 289: `if w < 100 and h < 100: continue`
**Severity:** LOW

This silently drops legitimate small windows (system tray popups, notification toasts, small dialogs) that might be the actual target of automation.

---

## 5. API CONTRACT PROBLEMS

### 5.1 No Stable Output Schema
**Location:** `element_to_dict()` — output structure is implicit
**Severity:** HIGH

There are no Pydantic models, dataclasses, or JSON schemas. The output dict is assembled ad hoc. Key names like `bounded` (not `bounding_box`), `localized_type` (not `role`), and `patterns` (not `control_patterns` or `actions`) are inconsistent with the spec's language.

When the C# sidecar is built, it will need to expose a different serialization format (likely protobuf or typed JSON). Without a formal schema in the spike, there's no contract to implement against.

### 5.2 Missing Fields in Element Dict
**Location:** line 169-180
**Severity:** MEDIUM

Compared to the spec's "Capture: role, name, value, bounding rect, available control patterns":
- **role** is captured as `control_type` + `localized_type` (redundant, not matching spec terminology)
- **value** is nested inside `patterns["value"]["value"]` — not at the top level where the spec implies it should be
- **HWND** is not captured (needed for `PostMessage` in T2)

### 5.3 No Error Response Format
**Location:** `find_window()` returns `None` on failure; `capture_frame()` returns `None`
**Severity:** LOW (CLI context) / HIGH (service context)

In CLI mode, returning `None` and exiting with a message is fine. In a WebSocket service, the consumer needs structured error responses (`{ "error": "window_not_found", "suggestion": [...] }`), not null values that require the caller to check for None everywhere.

---

## 6. MAINTAINABILITY ISSUES

### 6.1 Monolithic File — No Module Structure
**Location:** Single file, 495 lines
**Severity:** MEDIUM for spike, HIGH for production

All functions are at module level. There's no package structure, no imports between modules, no testability. The 7-component spec architecture requires 7 modules (minimum).

### 6.2 No Tests
**Location:** Not present
**Severity:** HIGH

Zero tests. The spike works for Notepad/Explorer but has not been validated against any edge case. No unit tests for `classify_tier()` (pure function, trivially testable). No integration tests.

### 6.3 No Logging
**Location:** Uses `print()` to stdout and `print(..., file=sys.stderr)` for errors
**Severity:** MEDIUM

No structured logging. When running as a sidecar service, `print()` output goes nowhere useful. Needs at minimum Python `logging` with configurable levels.

### 6.4 Dependency Management Absent
**Location:** No `requirements.txt`, `pyproject.toml`, or `pip` constraints
**Severity:** LOW (spike) / MEDIUM (production)

`uiautomation`, `mss`, and `PIL` are imported but there's no dependency specification. `uiautomation` specifically has known compatibility issues with Python 3.12+ and requires careful pinning.

---

## 7. SCALABILITY CONCERNS

### 7.1 Full Tree Walk for Every Perception Tick
**Location:** `element_to_dict()` — recursive full walk
**Severity:** HIGH

The PERCEIVE→PLAN→ACT→VERIFY loop implies multiple perceptions per action cycle (pre-state, post-state for VERIFY). Walking the entire UIA tree twice per action means the cost multiplies. For a tree with 500 elements, that's 7,000+ COM calls per cycle.

**What's needed:** Incremental state tracking, subtree-focused perception (only walk subtrees that are expected to change).

### 7.2 JSON Serialization of Large Trees
**Location:** `main()` line 473: `json.dumps(output, indent=2, default=str)`
**Severity:** MEDIUM

`default=str` is a catch-all that silently converts any non-serializable type to string. This masks type errors and produces inconsistent output. For large trees (thousands of elements), JSON serialization to string and back is expensive. The 80KB truncation heuristic (line 483) is arbitrary.

### 7.3 Memory: Full Tree Retained in Memory
**Location:** `tree` variable in `main()` — entire tree dict held until JSON serialization
**Severity:** LOW-MEDIUM

For the spike this is fine. For a long-running service processing many perceptions, accumulating tree snapshots without bounds will leak memory.

---

## 8. MISSING ARCHITECTURAL DECISIONS

### 8.1 Python Spike vs C# Sidecar — Is the Spike Wasted Effort?
**Severity:** STRATEGIC

The spec says "C#/.NET sidecar" is the suggested stack. The spike is in Python. This is **not inherently wrong** — Python is faster to prototype, and the `uiautomation` library is Python-first. However:

- The C# sidecar will use `UIAutomationClient` (native .NET UIA), which has a **different API surface** than `uiautomation` (Python). Pattern names, control type enums, and error handling are all different.
- The spike's code patterns (recursive dict building, try/except swallowing) will not translate cleanly to C#.
- The tier classification logic (line 352-365) will need to be reimplemented in C# anyway.

**Verdict:** The spike is a proof-of-concept, not a code base to extend. Document this explicitly. Do not plan to port this Python code to C# — plan to port the *design decisions* (tree walking strategy, classification logic) and rewrite from scratch.

### 8.2 No Per-App Profile Caching
**Location:** Not present
**Severity:** HIGH

The spec says "cache learned profiles outside core." The spike has no caching. Every perception walk starts from scratch. In production, the system should cache:
- Element ID mappings (automation_id → element role)
- Known control pattern support per app/process
- UI structure templates (File Explorer always has navigation pane + content pane)

This cache would eliminate redundant tree walks for stable UI regions.

### 8.3 No Governance Integration
**Location:** Not present
**Severity:** HIGH (per spec, "Governance Integration" is build unit #7)

The spec lists "Governance Integration" as a component. The spike has no PII detection, no data classification, no redaction, no audit logging. Given that the target apps include financial software (QuickBooks, Sage), this is a compliance requirement, not optional.

### 8.4 Drag/Target Intake Not Implemented
**Location:** Not present
**Severity:** MEDIUM

Spec lists "Drag/Target Intake" as build unit #6. No mechanism to receive a window handle or target specification from Hermes.

---

## 9. SPEC-RISKS SECTION: VERIFICATION

The spec's own risk section lists concerns. Here's how the spike addresses them:

| Spec Risk | Spike Status | Verdict |
|-----------|-------------|---------|
| Reparenting fragility | Not addressed (no SetParent code) | ✓ Correctly avoided |
| Sparse/custom-drawn UIs | No MSAA fallback | ✗ NOT mitigated |
| Elevation/UIPI | No detection or handling | ✗ NOT mitigated |
| Modal dialogs & focus stealing | No handling | ✗ NOT mitigated |
| DPI scaling | No DPI awareness in capture | ✗ NOT mitigated |
| Per-app quirks | No caching | ✗ NOT mitigated |
| Real client data / governance | No redaction or audit | ✗ NOT mitigated |

**5 of 7 spec risks are unmitigated in the spike.**

---

## PRIORITY REMEDIATION

### P0 — Must fix before Phase 1 design:
1. Add confidence score to tier classification (structured, not string)
2. Add stable element IDs for cross-snapshot correlation
3. Add MSAA fallback path (even if stub, the interface must exist)
4. Formalize output schema (Pydantic models or JSON Schema)
5. Add error response format (structured, not None)

### P1 — Should fix in Phase 1:
6. Add diffing between snapshots (for VERIFY step)
7. Add action executor stub (Invoke, SetValue, Click)
8. Add UIA event subscription interface
9. Fix DPI-aware coordinate mapping
10. Add element ID generation from composite keys
11. Add schema versioning to JSON output

### P2 — Nice to have:
12. Add per-app profile caching
13. Add logging framework
14. Add tests for `classify_tier()` and `summarize_tree()`
15. Add rate limiting / timeout on tree walks
16. Add `requirements.txt`
17. Replace `default=str` with explicit serialization
18. Fix hardcoded path in `capture_frame()`
19. Add truncation indicators (`...`) to truncated strings
20. Add integrity level detection
21. Handle `ApplicationFrameWindow` child drilling
22. Add `NativeWindowHandle` to element dict for T2 PostMessage

---

## FINAL ASSESSMENT

The spike proves the UIA tree walk works on Windows 11 File Explorer. That's its sole deliverable. It does **not** validate:
- The tiered perception architecture (no T0 or T2 implementation)
- The action loop (no ACT or VERIFY)
- The sidecar service model (CLI-only)
- The integration with Hermes (no WebSocket/tool surface)
- Any of the 7 spec risk mitigations

As a **proof-of-concept**, it succeeds. As an **architectural foundation**, it is insufficient. The Phase 1 design must be treated as a greenfield architecture exercise, not an extension of this spike code.
