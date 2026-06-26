# Hermes Eats World — Handoff Document

**Last updated:** 2026-06-26
**Branch:** `feat/phase0-sprint1`
**Latest commit:** `398ce95` (fix: remaining advisory findings + credential cleanup)
**Status:** Phase 1 Sprints 1–3 complete. Sprint 4 (Orchestrator) in progress.

---

## Quick Reference

| Item | Value |
|------|-------|
| Repository | `C:\Users\OnyxB\hermes-eats-world\` |
| Python files | 26 files, 3,637 lines |
| Modules | 8 (schema, perception, target, capture, action, service, verify, spikes) |
| Schema version | v1.0.0 |
| Entry point | `python -m sidecar.service` |
| Spec document | `~/AppData/Local/hermes/cache/documents/doc_f03e40aab73b_hermes-eats-world-spec.md` |
| AAR (HTML) | `AAR-phase0-sprint3.html` |

## Architecture at a Glance

```
hermes-eats-world/
├── sidecar/
│   ├── schema/           # Pydantic models + JSON encoder (v1.0.0)
│   ├── perception/       # UIA tree walker, tier classifier, state delta
│   ├── target/           # Window finder, UWP frame drilling
│   ├── capture/          # Screenshot (mss), OCR (pytesseract), template match
│   ├── action/           # T1: UIA patterns, T2: SendInput synthesis
│   ├── service/          # CLI, unified API, structured logging, env check
│   └── verify/           # (empty — planned Sprint 5)
├── spikes/
│   └── 001-perception-spike/  # Phase 0 spike + adversary reviews
├── pyproject.toml
├── requirements.txt
├── AAR-phase0-sprint1.html   # Original AAR
├── AAR-phase0-sprint3.html   # Updated AAR (current)
└── HANDOFF.md               # This file
```

## What Works

### T1 (Accessibility) Pipeline — Fully Working
- **Target acquisition:** Find windows by title, process name, or class name
- **UWP handling:** ApplicationFrameWindow child drilling with fallback
- **Tree walking:** UIA tree walk with ThreadPoolExecutor timeouts (5s/element, 30s total)
- **Pattern extraction:** 14 control pattern types via `GetPattern(PatternId)`
- **Tier classification:** T1/T2/T3 with calibrated thresholds (6 real apps)
- **T1 actions:** `invoke_element()`, `set_value()`, `select_item()` via UIA patterns

### T2 (Vision) Pipeline — Built, OCR Backend Missing
- **Screenshot capture:** `capture_element()`, `capture_window()` via mss + Pillow
- **Template matching:** NCC-based multi-scale template matching, DPI-aware
- **T2 actions:** `synthesize_click()`, `synthesize_type()` via SendInput
- **OCR:** OCREngine class built with lazy init + threading lock. **Backend='none'** (pytesseract not installed, tesseract-ocr binary missing)

### Service Layer
- **CLI:** `--list`, `--target`, `--process`, `--class`, `--screenshot`, `--max-depth`, `--output`, `--json-logs`
- **Unified API:** `perceive_target()` — single entry point with auto-tier selection
- **Structured logging:** JSON logging with `--json-logs` flag
- **Environment check:** DPI awareness, elevation, UIA availability validation

### State Delta Detection
- **StateDeltaDetector:** Compare two TreeSnapshots, detect ADDED/MODIFIED/REMOVED elements
- **Change categorization:** Role changes, value changes, pattern changes, position changes

### Verified & Tested
- **10/10 Sprint 3 tests passing** (imports, schema, perception, delta detection, service)
- **All adversary findings resolved** (Review #1: 9 VALID, Review #2: 7 findings including 3 Critical)

## What's Not Done

### Sprint 4: Orchestrator (In Progress)
- Goal-directed automation engine
- Action planner (decompose goals into steps)
- Executor loop (PERCEIVE → PLAN → ACT → VERIFY)
- Error recovery and retry logic
- CLI integration (`--run-goal`)

### Sprint 5: WebSocket Service + Verify
- WebSocket server (websockets + asyncio)
- Health check endpoint
- Formal verify module with pre/post assertions
- Path validation for output paths (P1-4)
- Configuration management (pydantic-settings)

### Sprint 6: T2 Expansion + Integration
- Expand T2 actions: right-click, drag, hover, scroll
- Install Tesseract OCR backend (requires system binary)
- End-to-end integration test against real apps

### Phase 2: C# Sidecar (Future)
- WinRT Graphics Capture for screenshots
- UIAutomationClient for native UIA access
- UIA event subscription for incremental updates
- Integrity level detection + UAC elevation

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Python over C# for MVP | .NET SDK install fails in headless terminal; Python proved pipeline in one session |
| mss for screenshots | Works for MVP; spec calls for WinRT Graphics Capture but that's Phase 2 |
| ThreadPoolExecutor for timeouts | Prevents COM hangs on GetChildren; 5s/element, 30s total |
| Bridge layer pattern | Separates TargetInfo models from raw uiautomation controls |
| Schema versioning from day one | Allows schema evolution without breaking downstream consumers |
| Lazy OCR initialization | Avoids heavy cold start on first call; defer backend probing to recognize() |
| SendMessageW over PostMessageW | Synchronous text setting with proper ctypes marshaling |

## Environment

- **OS:** Windows 10
- **Python:** 3.11.15
- **Shell:** Git Bash (MSYS2)
- **Installed packages:** uiautomation, mss, pillow, numpy, pydantic, websockets, tenacity
- **NOT installed:** pytesseract (tesseract-ocr system binary missing)

## Running the Code

```bash
# List visible windows
python -m sidecar.service --list

# Perceive a target by process name
python -m sidecar.service --process explorer.exe

# Take a screenshot
python -m sidecar.service --target "File Explorer" --screenshot

# With JSON structured logging
python -m sidecar.service --list --json-logs
```

## Known Issues / Blockers

1. **OCR backend:** pytesseract package not installed. `backend='none'` is the current state — OCR returns empty results gracefully.
2. **WebSocket server:** Not implemented yet (Sprint 5).
3. **Verify module:** Empty `sidecar/verify/` directory. State delta detection exists in `perception/delta.py` but no formal verify module yet.
4. **T2 actions limited:** Only click and type implemented. Right-click, drag, hover, scroll pending.

## Adversary Board Reviews

### Review #1 (Phase 0)
- **4 adversaries:** Security, Architecture, Logic, Operational
- **86 total findings → 9 VALID** (67% FP rate)
- **All 9 resolved** in Sprint 1–2

### Review #2 (Sprint 2)
- **7 findings:** 3 Critical, 2 High, 2 Medium
- **Key catches:** ctypes marshaling bug, off-by-one in select_item, recursion pattern bug
- **All 7 resolved** in commit `398ce95`

## Sensitive Data

**Project source, working tree, and git history are CLEAN.** All credential-reading scripts have been purged from git history. No PII or client data in the codebase.

## Files of Interest

- `sidecar/service/service.py` — Unified service API (`perceive_target()`)
- `sidecar/perception/delta.py` — State delta detection
- `sidecar/action/t1_invoke.py` — T1 action executors
- `sidecar/action/t2_synthesize.py` — T2 action executors (SendInput)
- `sidecar/capture/ocr.py` — OCR engine (lazy init, thread-safe)
- `sidecar/capture/match.py` — Template matching (NCC)
- `sidecar/service/logging.py` — Structured JSON logging
