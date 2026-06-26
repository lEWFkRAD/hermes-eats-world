# LOGIC ADVERSARIAL REVIEW
## Hermes Eats World — Phase 0 Perception Spike (`spike.py`)

**Review date:** 2026-06-26
**Reviewer:** Logic/Correctness Adversary (subagent)
**Scope:** `spike.py` (~495 lines), logical correctness, algorithm correctness, edge cases, specification compliance

---

## EXECUTIVE SUMMARY

**4 CRITICAL, 2 HIGH, 6 MEDIUM, 8 LOW findings.**

The spike proves the UIA tree walking concept but has significant logic bugs, edge case failures, and specification deviations that would cause incorrect tier classification, missed UI elements, and unreliable perception in production.

---

## FINDINGS

### [CRITICAL-1] `process_name` search is broken — never actually searches by process name

**Location:** `find_window()` function — `process_name` parameter exists but is never used in any search.

**What this means:** The function signature accepts `process_name` but the search logic only tries `Name=title` (exact window title match) and `ClassName=class_name`. The `process_name` parameter is dead code.

**Impact:** Users cannot search for windows by executable/process name. This is a core feature gap for targeting apps like Excel or Sage 50 where window titles vary but process names are stable.

**Remediation:** Implement PID lookup via `psutil` or `ctypes.windll` to resolve process name → PID → window handles.

---

### [CRITICAL-2] `--full` flag has no recursion depth cap — stack overflow risk

**Location:** `element_to_dict()` recursive call with `max_depth` parameter. When `--full` is used, `max_depth` defaults to 999.

**What this means:** Deeply nested UI trees (e.g., complex web pages, CAD tools, nested containers) can cause Python stack overflow or extreme latency. No safety warning is issued.

**Impact:** `python spike.py --target "..." --full` on a complex app can crash the interpreter or hang indefinitely.

**Remediation:** Cap `max_depth` to 500, add safety warning when approaching the cap.

---

### [CRITICAL-3] `classify_tier()` classification thresholds are arbitrary and undocumented

**Location:** Lines ~345-360 — tier classification uses hardcoded thresholds:
- T1: `unique_patterns >= 4` AND `total_elements >= 20`
- T2: `unique_patterns >= 2` AND `total_elements >= 5`
- T3: everything else

**What this means:** These thresholds were chosen without empirical validation. An app with 3 pattern types and 50 elements is classified T3 despite having rich content. An app with 5 patterns and 2 elements is T1 despite being nearly empty.

**Impact:** Incorrect tier classification leads to wrong fallback strategy decisions. Hermes may attempt pure UIA automation on apps that need vision fallback, or vice versa.

**Remediation:** Document threshold rationale, add confidence score, consider a weighted scoring system instead of binary thresholds.

---

### [CRITICAL-4] `get_control_patterns()` silently swallows ALL exceptions — 14 `pass` blocks

**Location:** Lines 29-143 — every control pattern probe is wrapped in `try/except Exception: pass` with no logging, no error tracking, no fallback.

**What this means:** If a pattern probe fails due to COM errors, access denied, timeout, or any other reason, the failure is completely silent. The caller has no way to know how many patterns failed vs how many were genuinely unsupported.

**Impact:** Tier classification is based on incomplete pattern data. An element that supports all 14 patterns but fails on 12 due to transient COM errors will appear to support only 2 patterns, potentially misclassifying T1→T3.

**Remediation:** Log failures, track failure counts, distinguish "pattern not supported" from "pattern probe failed."

---

### [HIGH-1] `element_to_dict()` uses `default=str` for JSON serialization — masks type errors

**Location:** Line ~473 — `json.dumps(output, indent=2, default=str)`

**What this means:** Non-serializable Python objects (COM objects, custom types) are silently converted to their string representation instead of raising an error. A COM object becomes `"uiautomation.Control object at 0x000001..."` in the JSON.

**Impact:** Silent data corruption. The JSON is valid but contains garbage data that downstream consumers cannot parse meaningfully.

**Remediation:** Explicit serialization for each field type. Fail fast on unserializable types.

---

### [HIGH-2] No stable element IDs — impossible to correlate elements across snapshots

**Location:** `element_to_dict()` — elements have no unique identifier.

**What this means:** Without stable IDs, comparing two tree snapshots to detect UI changes is impossible. You cannot tell if an element moved, was added, was removed, or just changed its properties.

**Impact:** Phase 1 state tracking requires element correlation across time. Without IDs, this requires expensive heuristic matching on every comparison.

**Remediation:** Add stable element IDs using a composite key (e.g., hash of name + control type + position in tree).

---

### [MEDIUM-1] Window search uses `Name=title` (exact match) instead of substring

**Location:** Line ~250 — `auto.WindowControl(SearchDepth=1, Name=title)`

**What this means:** Window title must match exactly. "File Explorer" works but "File" does not. Users must know the exact window title.

**Impact:** Poor UX, requires users to run `--list` first to get exact titles.

**Remediation:** Use `SubName` for substring matching, or fall back to substring if exact match fails.

---

### [MEDIUM-2] Screenshot captures entire monitor, not target window

**Location:** `capture_frame()` — uses `mss` to capture the active monitor.

**What this means:** If the target window is smaller than the screen or partially occluded, the screenshot contains irrelevant content. The bounding box info is present but the screenshot is not cropped to the window.

**Impact:** Wasted bandwidth/storage. Vision models receive irrelevant visual context.

**Remediation:** Crop screenshot to target window bounding rectangle.

---

### [MEDIUM-3] `--screenshot` and `--output` flags are wired but not documented in help text

**Location:** CLI argument parser — flags exist but help text is minimal.

**What this means:** Users don't know these flags exist without reading the source code.

**Impact:** Poor discoverability.

**Remediation:** Improve help text with descriptions and examples.

---

### [MEDIUM-4] Name truncation at 200 chars without truncation indicator

**Location:** `element_to_dict()` — `name = name[:200]`

**What this means:** Long element names (e.g., file paths, URLs) are silently truncated. Downstream consumers cannot tell if a name was truncated.

**Impact:** Loss of information without indication. A truncated file path is useless.

**Remediation:** Append `"..."` indicator when truncating.

---

### [MEDIUM-5] `summarize_tree()` does 4 separate traversals for summary stats

**Location:** `main()` — calls `count_elements()`, `count_patterns()`, `max_depth()`, and `classify_tier()` separately.

**What this means:** The tree is walked 4 times to compute summary statistics that could be computed in a single pass.

**Impact:** Unnecessary performance overhead, especially for large trees.

**Remediation:** Combine into single-pass `summarize_tree()` function.

---

### [MEDIUM-6] No schema version in JSON output

**Location:** JSON output — no version field.

**What this means:** Downstream consumers cannot detect schema changes. A future version that changes field names or structure will silently break consumers.

**Impact:** No forward/backward compatibility tracking.

**Remediation:** Add `schema_version` field to JSON output.

---

### [LOW-1] Duplicate `classify_tier` function definition

**Location:** Two definitions of `classify_tier` in the file.

**What this means:** The second definition overwrites the first. The first is dead code.

**Impact:** Confusion during maintenance.

---

### [LOW-2] No `requirements.txt`

**Location:** Project root — missing dependency file.

**Impact:** Cannot reproduce environment.

---

### [LOW-3] Hardcoded screenshot path

**Location:** `capture_frame()` — absolute path with username.

**Impact:** Breaks on other machines.

---

### [LOW-4] No `.gitignore`

**Location:** Project root — missing `.gitignore`.

**Impact:** Generated artifacts (JSON, PNG) could be committed to version control.

---

### [LOW-5] `mss.mss()` deprecated — should use `mss.MSS()`

**Location:** `capture_frame()` — uses deprecated API.

**Impact:** Deprecation warning on every screenshot.

---

### [LOW-6] Duplicate `datetime` import

**Location:** Module-level import + import inside `capture_frame()`.

**Impact:** Minor code smell.

---

### [LOW-7] No logging module usage — all `print()` statements

**Location:** Entire file.

**Impact:** No severity levels, no timestamps, no log rotation.

---

### [LOW-8] PIL pixel format: `mss` returns BGRA but code creates RGB Image

**Location:** `capture_frame()` — `Image.frombytes('RGB', ...)`.

**Impact:** Potential color channel swap (red/blue inverted) depending on `mss` version and output format.

**Remediation:** Verify `mss` output format and convert BGRA→RGB properly.

---

## FINAL ASSESSMENT

The spike demonstrates UIA tree walking from Python works. However, it has **4 critical logic bugs** that would cause incorrect behavior in production:

1. `process_name` search is dead code
2. `--full` has no depth cap (stack overflow risk)
3. Classification thresholds are arbitrary and undocumented
4. Silent exception swallowing corrupts pattern data

These should be fixed before proceeding to Phase 1. The remaining HIGH/MEDIUM findings are design improvements that Phase 1 should address during the architecture redesign.
