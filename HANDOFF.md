# Hermes Eats World — Handoff Document

**Last updated:** 2026-06-26
**Branch:** `feat/phase0-sprint1`
**Latest commit:** `dab2f1e` (feat: Sprint 4 — orchestrator, CLI integration, and tree walker fixes)
**Status:** Phase 1 Sprints 1–4 complete. Sprint 5 (WebSocket + Verify) next.

---

## Quick Reference

| Item | Value |
|------|-------|
| Repository | `C:\Users\OnyxB\hermes-eats-world\` |
| Python files | 31 files, 5,359 lines |
| Modules | 9 (schema, perception, target, capture, action, orchestrator, service, verify, spikes) |
| Schema version | v1.0.0 |
| Entry point | `python -m sidecar.service` |
| Spec document | `~/AppData/Local/hermes/cache/documents/doc_f03e40aab73b_hermes-eats-world-spec.md` |
| AAR (HTML) | `AAR-phase0-sprint4.html` |

## Architecture at a Glance

```
hermes-eats-world/
├── sidecar/
│   ├── schema/           # Pydantic models + JSON encoder (v1.0.0)
│   ├── perception/       # UIA tree walker, tier classifier, state delta
│   ├── target/           # Window finder, UWP frame drilling
│   ├── capture/          # Screenshot (mss), OCR (pytesseract), template match
│   ├── action/           # T1: UIA patterns, T2: SendInput synthesis
│   ├── orchestrator/     # Goal-directed automation (planner, executor, recovery)
│   ├── service/          # CLI, unified API, structured logging, env check
│   └── verify/           # (empty — planned Sprint 5)
├── spikes/
│   └── 001-perception-spike/  # Phase 0 spike + adversary reviews
├── pyproject.toml
├── requirements.txt
├── AAR-phase0-sprint1.html   # Original AAR
├── AAR-phase0-sprint3.html   # Sprint 3 AAR
├── AAR-phase0-sprint4.html   # Sprint 4 AAR (current)
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
- **CLI:** `--list`, `--target`, `--process`, `--class`, `--screenshot`, `--max-depth`, `--output`, `--json-logs`, `--run-goal`, `--max-steps`, `--recovery`
- **Unified API:** `perceive_target()` — single entry point with auto-tier selection
- **Structured logging:** JSON logging with `--json-logs` flag
- **Environment check:** DPI awareness, elevation, UIA availability validation

### State Delta Detection
- **StateDeltaDetector:** Compare two TreeSnapshots, detect ADDED/MODIFIED/REMOVED elements
- **Change categorization:** Role changes, value changes, pattern changes, position changes

### Orchestrator (Sprint 4) — Fully Working
- **Action planner:** Decomposes natural language goals into executable steps (regex-based intent matching)
- **Executor loop:** PERCEIVE → PLAN → ACT → VERIFY cycle with configurable max steps
- **Recovery strategies:** Retry, fallback, abort — configurable per execution
- **CLI integration:** `--run-goal` flag for one-shot goal execution
- **Smoke tested:** Notepad `type hello world` succeeds in 1.3s, 43 elements detected

### Verified & Tested
- **10/10 Sprint 3 tests passing** (imports, schema, perception, delta detection, service)
- **4/4 Sprint 4 tests passing** (orchestrator imports, CLI --help, CLI --run-goal, smoke test)
- **All adversary findings resolved** (Review #1: 9 VALID, Review #2: 7 findings including 3 Critical)

## What's Not Done

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
| Regex-based planner (Sprint 4) | Fast intent matching for T1 goals; LLM planner deferred to Sprint 7+ |

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

# Run a goal against a target (Sprint 4)
python -m sidecar.service --target "Untitled - Notepad" --run-goal "type hello world"
```

## Known Issues / Blockers

1. **OCR backend:** pytesseract package not installed. `backend='none'` is the current state — OCR returns empty results gracefully.
2. **WebSocket server:** Not implemented yet (Sprint 5).
3. **Verify module:** Empty `sidecar/verify/` directory. State delta detection exists in `perception/delta.py` but no formal verify module yet.
4. **T2 actions limited:** Only click and type implemented. Right-click, drag, hover, scroll pending.
5. **Planner scope:** Current planner is regex-based — handles common patterns (click, type, navigate, open). Complex/novel goals need an LLM planner (future sprint).

## Adversary Board Reviews

### Review #1 (Phase 0)
- **4 adversaries:** Security, Architecture, Logic, Operational
- **86 total findings → 9 VALID** (67% FP rate)
- **All 9 resolved** in Sprint 1–2

### Review #2 (Sprint 2)
- **7 findings:** 3 Critical, 2 High, 2 Medium
- **Key catches:** ctypes marshaling bug, off-by-one in select_item, recursion pattern bug
- **All 7 resolved** in commit `398ce95`

## Sprint 4 Bugs Fixed

| Bug | File | Fix |
|-----|------|-----|
| Regex optional capture group → None | `sidecar/orchestrator/planner.py` | Conditional check: `groups[1].strip() if groups[1] else None` |
| `_find_element` tree/name null | `sidecar/orchestrator/planner.py` | Added null check before tree traversal |
| Text capture regex lazy quantifier | `sidecar/orchestrator/planner.py` | Changed `(.+?)` to capture full phrases with spaces |
| `patterns` → None instead of `{}` | `sidecar/perception/tree_walker.py` | Default to `{}` if `_get_control_patterns` returns None |
| `patterns` booleans instead of dicts | `sidecar/perception/tree_walker.py` | Changed `True` → `{"supported": True}` for Pydantic validation |

## Sensitive Data

**Project source, working tree, and git history are CLEAN.** All credential-reading scripts have been purged from git history. No PII or client data in the codebase.

## Files of Interest

- `sidecar/service/service.py` — Unified service API (`perceive_target()`)
- `sidecar/service/cli.py` — CLI with orchestrator support (`--run-goal`)
- `sidecar/perception/delta.py` — State delta detection
- `sidecar/action/t1_invoke.py` — T1 action executors
- `sidecar/action/t2_synthesize.py` — T2 action executors (SendInput)
- `sidecar/capture/ocr.py` — OCR engine (lazy init, thread-safe)
- `sidecar/capture/match.py` — Template matching (NCC)
- `sidecar/service/logging.py` — Structured JSON logging
- `sidecar/orchestrator/planner.py` — Goal-to-steps planner (regex intent matching)
- `sidecar/orchestrator/executor.py` — PERCEIVE→PLAN→ACT→VERIFY loop
- `sidecar/orchestrator/recovery.py` — Retry/fallback/abort strategies
