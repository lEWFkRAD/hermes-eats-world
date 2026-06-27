# Hermes Eats World — Handoff Document

**Last updated:** 2026-06-27
**Branch:** `feat/phase0-sprint1`
**Latest commit:** `dab2f1e`
**Status:** Phase 1 Sprints 1–7 COMPLETE. All core features implemented and verified.

---

## Quick Reference

| Item | Value |
|------|-------|
| Repository | `C:\Users\OnyxB\hermes-eats-world\` |
| Python files | 35+ files, 7,000+ lines |
| Modules | 12 (schema, perception, target, capture, action, orchestrator, service, verify, security, config, governance, events) |
| Schema version | v1.0.0 |
| Entry point | `python -m sidecar.service` |
| WebSocket | `ws://127.0.0.1:8765` |
| LLM endpoint | `http://127.0.0.1:8001/v1` (qwen3.6-27b) |
| Tesseract | `C:\Program Files\Tesseract-OCR\tesseract.exe` (v5.4.0) |
| Spec document | `~/AppData/Local/hermes/cache/documents/doc_f03e40aab73b_hermes-eats-world-spec.md` |
| AAR (Sprints 5-7) | `AAR_SPRINTS_5_7.md` |

## Architecture at a Glance

```
hermes-eats-world/
├── sidecar/
│   ├── schema/           # Pydantic models + JSON encoder (v1.0.0)
│   ├── perception/       # UIA tree walker, tier classifier, state delta
│   ├── target/           # Window finder, UWP frame drilling
│   ├── capture/          # Screenshot (mss), OCR (pytesseract), template match
│   ├── action/           # T1: UIA patterns, T2: SendInput (8 actions)
│   ├── orchestrator/     # Goal-directed automation (planner, executor, recovery, governance, events, modals)
│   ├── service/          # CLI, unified API, WebSocket, structured logging, env check
│   ├── verify/           # Pre/post assertions (5 types)
│   ├── config.py         # Pydantic-settings configuration
│   └── security.py       # Path validation + security hardening
├── spikes/
│   └── 001-perception-spike/  # Phase 0 spike + adversary reviews
├── pyproject.toml
├── requirements.txt
├── AAR-phase0-sprint1.html   # Sprint 1 AAR
├── AAR-phase0-sprint3.html   # Sprint 3 AAR
├── AAR-phase0-sprint4.html   # Sprint 4 AAR
├── AAR_SPRINTS_5_7.md        # Sprints 5-7 AAR (current)
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

### T2 (Vision) Pipeline — Fully Working ✅
- **Screenshot capture:** `capture_element()`, `capture_window()` via mss + Pillow
- **Template matching:** NCC-based multi-scale template matching, DPI-aware
- **T2 actions (8 total):** `click_at`, `type_text`, `post_message`, `double_click_at`, `right_click_at`, `hover_at`, `drag`, `scroll_at`
- **OCR:** Tesseract 5.4.0 installed, pytesseract working, verified round-trip

### Service Layer — Fully Working
- **CLI:** `--list`, `--target`, `--process`, `--class`, `--screenshot`, `--max-depth`, `--output`, `--json-logs`, `--run-goal`, `--max-steps`, `--recovery`
- **Unified API:** `perceive_target()` — single entry point with auto-tier selection
- **WebSocket server:** `ws://127.0.0.1:8765` with methods: health, list_windows, perceive_target, run_goal, capture_screenshot
- **Structured logging:** JSON logging with `--json-logs` flag
- **Environment check:** DPI awareness, elevation, UIA availability validation

### State Delta Detection
- **StateDeltaDetector:** Compare two TreeSnapshots, detect ADDED/MODIFIED/REMOVED elements
- **Change categorization:** Role changes, value changes, pattern changes, position changes

### Orchestrator — Fully Working
- **Regex planner:** Decomposes natural language goals into executable steps
- **LLM planner:** LLM-powered goal planning with local model (qwen3.6-27b)
- **Executor loop:** PERCEIVE → PLAN → ACT → VERIFY cycle with configurable max steps
- **Recovery strategies:** Retry, fallback, abort — configurable per execution
- **Governance:** Tamper-evident audit trail, confirmation gates, destructive action blocking
- **Event subscription:** UIA event listeners for incremental updates
- **Modal handler:** Auto-detect and handle modal dialogs (10 built-in rules)

### Verification Module — Fully Working
- **5 assertion types:** `element_exists`, `element_value`, `element_state`, `tree_changed`, `element_absent`
- **Pre/post assertions:** Verify state before and after actions
- **VerificationPlan:** Structured verification with Verifier class

### Configuration & Security
- **Pydantic-settings:** `SIDECAR_` env prefix, `.env` file support
- **Path validation:** `sanitize_path()`, `validate_output_path()`, `validate_screenshot_path()`
- **Forbidden paths:** `C:\Windows`, `C:\Program Files`, `~/.ssh`, `~/.azure`

### Verified & Tested
- **10/10 Sprint 3 tests passing** (imports, schema, perception, delta detection, service)
- **4/4 Sprint 4 tests passing** (orchestrator imports, CLI --help, CLI --run-goal, smoke test)
- **7/7 Sprint 5 tests passing** (WebSocket, verify, config, security, schema, service, protocol)
- **4/4 Sprint 6 tests passing** (T2 expansion, Tesseract OCR, round-trip, circular import fix)
- **5/5 Sprint 7 tests passing** (LLM planner, governance, events, modals, integration)

## What's Not Done

### Phase 2: C# Sidecar (Future)
- WinRT Graphics Capture for screenshots
- UIAutomationClient for native UIA access
- UIA event subscription for incremental updates
- Integrity level detection + UAC elevation

### Future Enhancements
- End-to-end integration tests against real Windows apps
- WebSocket client library (Python/JS)
- LLM planner prompt tuning
- Vision model integration for T3 apps
- Performance optimization via incremental tree updates
- API documentation and tutorials

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
| Regex-based planner (Sprint 4) | Fast intent matching for T1 goals; LLM planner added in Sprint 7 |
| LLM planner with fallback | LLM for complex goals, regex for fast/simple goals |
| Tamper-evident governance | SHA-256 chained audit trail for safety and debugging |

## Environment

- **OS:** Windows 10
- **Python:** 3.11.15
- **Shell:** Git Bash (MSYS2)
- **Installed packages:** uiautomation, mss, pillow, numpy, pydantic, websockets, tenacity, pytesseract
- **Tesseract OCR:** v5.4.0 at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **LLM:** qwen3.6-27b on custom provider at `http://127.0.0.1:8001/v1`

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

# Run a goal against a target
python -m sidecar.service --target "Untitled - Notepad" --run-goal "type hello world"

# WebSocket server (background)
python -m sidecar.service --websocket
```

## Known Issues / Blockers

1. **None blocking** — All core features implemented and verified.
2. **OCR singleton caching** — First call to `get_ocr_engine()` without args creates a "none" backend; subsequent calls with `'pytesseract'` force re-init. Always call with backend name first.
3. **Windows file locks** — Close PIL images before deleting temp files in tests.

## Adversary Board Reviews

### Review #1 (Phase 0)
- **4 adversaries:** Security, Architecture, Logic, Operational
- **86 total findings → 9 VALID** (67% FP rate)
- **All 9 resolved** in Sprint 1–2

### Review #2 (Sprint 2)
- **7 findings:** 3 Critical, 2 High, 2 Medium
- **Key catches:** ctypes marshaling bug, off-by-one in select_item, recursion pattern bug
- **All 7 resolved** in commit `398ce95`

## Sprint 4-7 Bugs Fixed

| Sprint | Bug | File | Fix |
|--------|-----|------|-----|
| 4 | Regex optional capture group → None | `planner.py` | Conditional check for None groups |
| 4 | `_find_element` tree/name null | `planner.py` | Added null check before traversal |
| 4 | Text capture regex lazy quantifier | `planner.py` | Changed `(.+?)` to capture full phrases |
| 4 | `patterns` → None instead of `{}` | `tree_walker.py` | Default to `{}` if None |
| 4 | `patterns` booleans instead of dicts | `tree_walker.py` | Changed `True` → `{"supported": True}` |
| 5 | `AssertionStatus` not exported | `verify/__init__.py` | Added to import + `__all__` |
| 5 | `verify_element_value` checked `elem.name` | `assertions.py` | Check `ValuePattern.value` first |
| 5 | Line grouping used `data["text"]` | `ocr.py` | Use `data["line_num"]` |
| 5 | `sanitize_path()` skipped forbidden paths | `security.py` | Added forbidden path validation |
| 5 | Circular import: service ↔ capture | `service.py` | Lazy import of `capture_window` |
| 6 | Frozen Pydantic `BoundingBox` | `ocr.py` | Build new instance instead of mutating |
| 6 | Singleton cached before backend | `ocr.py` | Force re-init on backend change |
| 7 | `field()` invalid syntax | `governance.py` | `field(default_factory=...)` |
| 7 | `@dataclass` before import | `event_sub.py` | Moved import to top of file |

## Sensitive Data

**Project source, working tree, and git history are CLEAN.** All credential-reading scripts have been purged from git history. No PII or client data in the codebase.

## Files of Interest

- `sidecar/service/service.py` — Unified service API (`perceive_target()`)
- `sidecar/service/websocket_server.py` — WebSocket service server
- `sidecar/orchestrator/planner.py` — Regex-based goal planner
- `sidecar/orchestrator/llm_planner.py` — LLM-powered goal planner ✨
- `sidecar/orchestrator/governance.py` — Audit trail + confirmation gates ✨
- `sidecar/orchestrator/event_sub.py` — UIA event subscription ✨
- `sidecar/orchestrator/modal_handler.py` — Modal dialog handling ✨
- `sidecar/action/t2_synthesize.py` — T2 actions (8 total)
- `sidecar/capture/ocr.py` — OCR engine (pytesseract working)
- `sidecar/verify/assertions.py` — Pre/post assertions
- `sidecar/config.py` — Pydantic-settings configuration
- `sidecar/security.py` — Path validation + security

---

*Handoff updated by Hermes Agent (qwen3.6-27b via MOA)*
*Meow~ 🐱💖*
