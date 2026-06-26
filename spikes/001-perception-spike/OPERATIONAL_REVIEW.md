# OPERATIONAL ADVERSARIAL REVIEW
## Hermes Eats World — Phase 0 Perception Spike (`spike.py`)

**Review date:** 2026-06-26
**Reviewer:** Operations/Deployment Adversary (subagent)
**Scope:** `spike.py` (495 lines), deployment-readiness, reliability, monitoring, configuration, resource management
**Context:** Windows 10 sidecar service for CPA firm infrastructure handling real client financial data

---

## EXECUTIVE SUMMARY

This is a **CLI script masquerading as the foundation of a production sidecar service**. Every operational requirement from the spec is absent. There is no service model, no health checks, no structured logging, no configuration management, no dependency pinning, no process monitoring, no graceful shutdown, no resource cleanup, no rate limiting, no retry logic, and no rollback path. The script has **26 operational findings** (5 CRITICAL, 8 HIGH, 7 MEDIUM, 6 LOW).

The gap between "runs from Git Bash on one developer's machine" and "production sidecar handling financial data" is not incremental — it is a complete rewrite.

---

## FINDINGS

### [CRITICAL-1] No service model — process lifecycle is entirely unmanaged

**Location:** Entire file. Entry point is `if __name__ == "__main__": main()` (line 494-495).

**What this means:** This is a CLI script that starts, runs once, and exits. There is no event loop, no message pump, no WebSocket server, no daemon mode, no Windows service registration, no systemd unit, no supervisor config.

**Operational impact:**
- **No auto-restart:** If the process crashes (COM error, unhandled exception, Python crash), it stays dead. Nothing restarts it. The sidecar is dead until a human notices and manually reruns it.
- **No monitoring integration:** No process name to watch, no PID file, no status endpoint, no heartbeat. Infrastructure monitoring (Prometheus, Datadog, Nagios, Windows Performance Monitor) has nothing to attach to.
- **No uptime tracking:** Cannot answer "how long has the sidecar been running?" or "when did it last restart?"
- **No rolling update:** Cannot update without killing the process and starting a new one (manual downtime).

**Spec violation:** "Must work as a sidecar service exposed via local WebSocket." This is neither a service nor does it expose anything via WebSocket.

**Remediation:** Windows service (`win32service` / `pywin32`), or a proper async event loop with WebSocket server (`websockets` / `fastapi`), wrapped in a process manager (supervisor, systemd-equivalent for Windows, or a Windows service wrapper).

---

### [CRITICAL-2] No graceful shutdown handling — COM resources leak on termination

**Location:** Entire file. No `atexit`, no signal handlers, no `try/finally`, no context managers for COM resources.

**What this means:** The `uiautomation` library holds COM apartments and RPC connections to UIA host processes. When this script is killed (Ctrl+C, taskkill, OOM, crash), those COM connections are not cleanly released.

**Operational impact:**
- **Hung COM objects:** UIA host processes (`UIHost.exe`) may remain alive after the Python process dies, holding references to UI elements. These orphaned COM references can cause the target application (Excel, SAGE) to behave strangely or refuse new UIA connections.
- **RPC channel leaks:** Each `uiautomation` COM call opens RPC channels. Without proper `CoUninitialize()`, these accumulate. After enough restarts (e.g., if some external process repeatedly launches this script), the machine can exhaust RPC endpoints.
- **File handle leaks:** If `capture_frame()` is interrupted mid-write, the PNG file is corrupted/truncated with no cleanup.
- **JSON file corruption:** If `--output` is interrupted mid-write, the output file is partially written JSON — garbage that downstream consumers will fail to parse.

**Remediation:** `atexit.register()` cleanup handler, `signal.signal()` for SIGINT/SIGTERM, context managers around file writes, explicit COM apartment cleanup.

---

### [CRITICAL-3] No structured logging — impossible to diagnose production incidents

**Location:** Lines 317, 329, 344, 348, 382-398, 405-491 — all `print()` calls.

**What this means:** Every log message is a `print()` to stdout or `print(..., file=sys.stderr)`. No timestamps, no severity levels, no log rotation, no structured format, no log shipping.

**Operational impact:**
- **No incident diagnostics:** When the sidecar stops responding, there are no logs to investigate. The operator has no record of what the last operation was, what window was targeted, or what error occurred.
- **No log aggregation:** Cannot ship logs to Splunk, Datadog, ELK, or Azure Monitor. In a CPA firm with compliance requirements, this is unacceptable.
- **No log rotation:** If this were running in a loop (as a service would), `print()` output would either fill a console buffer or fill a redirected file to disk until the filesystem is full.
- **No severity differentiation:** "ERROR: No bounding rectangle" (line 317) and "Tree walk completed in 0.42s" (line 426) are logged identically. Cannot filter by severity.
- **Timestamps are present in JSON output (line 456) but NOT in log messages.** The `print()` calls have no temporal context.
- **Print output captured in shell history/terminal buffers** — PII exposure (covered in security review).

**Remediation:** Python `logging` module minimum, `structlog` or `python-json-logger` for structured output. Log rotation via `logging.handlers.RotatingFileHandler`. Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). Correlation IDs for request tracing.

---

### [CRITICAL-4] Hardcoded absolute paths — breaks on every machine except one developer's

**Location:** Line 337:
```python
output_path = f"c:/Users/OnyxB/hermes-eats-world/spikes/001-perception-spike/hermes_spike_{timestamp}.png"
```

**What this means:** The screenshot output path is hardcoded to:
- A specific username: `OnyxB`
- A specific project path: `hermes-eats-world/spikes/001-perception-spike/`
- Forward slashes on Windows (works in Python but is inconsistent)

**Operational impact:**
- **Will not run on any other machine** without code modification. A second developer, a build server, a production machine, a test VM — all fail.
- **No `--output` override for screenshots:** The `capture_frame()` function accepts `output_path=None` and defaults to the hardcoded path. The `--output` CLI argument (line 376) only controls JSON output, not screenshots. A user can override JSON output but NOT screenshot output.
- **Path uses POSIX-style forward slashes on Windows** — works in Python 3 but would break if passed to any Windows API call or shell command.

**Remediation:** Environment variable (`HERMES_EATS_OUTPUT_DIR`), config file, or `--screenshot-output` CLI argument. Use `pathlib.Path.home()` instead of hardcoded `C:\Users\OnyxB`.

---

### [CRITICAL-5] No dependency management — cannot reproduce the environment

**Location:** No `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, or `constraints.txt` anywhere in the project.

**What this means:** Dependencies are installed in the Hermes Agent venv and assumed to be available:
- `uiautomation 2.0.29` (confirmed installed)
- `mss 10.2.0` (confirmed installed)
- `Pillow 12.2.0` (confirmed installed)

**Operational impact:**
- **No reproducible builds:** Deploying to another machine requires manual `pip install` of unknown versions. Could install `uiautomation 2.0.31` which may have breaking changes.
- **No version pinning:** Even if someone creates a `requirements.txt` tomorrow, there's no record of what versions actually work. `uiautomation` specifically has known Python 3.12+ compatibility issues.
- **No transitive dependency tracking:** `mss` has no dependencies, but `Pillow` pulls in `packaging`. No lock file means transitive deps are untracked.
- **No supply chain security:** No hash pinning, no trusted publishing verification. In a financial services context, this is a compliance gap.

**Remediation:** `requirements.txt` with pinned versions minimum. `pip-tools` or `uv` for lock files. `pyproject.toml` with project metadata.

---

### [HIGH-1] No health checks — cannot verify sidecar is alive

**Location:** Not present.

**What this means:** There is no `/health` endpoint, no heartbeat, no status command, no watchdog integration.

**Operational impact:**
- **No readiness probe:** Load balancers, orchestrators, and process managers cannot determine if the sidecar is ready to accept requests.
- **No liveness probe:** Cannot detect a hung/deadlocked process (e.g., COM apartment frozen, infinite loop in tree walk).
- **Silent failures:** If the sidecar catches an exception and returns `None` (lines 318, 349), the caller has no way to distinguish "window not found" from "sidecar is broken."
- **No metrics:** Cannot track tree walk latency, screenshot capture time, error rates, or uptime.

**Remediation:** WebSocket `/health` or HTTP `/healthz` endpoint. Periodic heartbeat. Prometheus metrics endpoint.

---

### [HIGH-2] No timeout on UIA operations — hung applications block indefinitely

**Location:** 
- Line 250-252: `win.Exists(0, 2)` — 2-second timeout (good, but only here)
- Line 185: `for child in element.GetChildren()` — **no timeout**
- Line 147-194: `element_to_dict()` — **no timeout**
- Lines 29-143: `get_control_patterns()` — 14 pattern probes, **no timeout per probe or total**
- Line 421-423: `time.time()` timer exists but only for logging, not enforcement

**What this means:** If a target application (Excel, SAGE) hangs, freezes, or enters an inconsistent state, `GetChildren()` or any pattern probe can block indefinitely. There is no timeout mechanism to abort a hung tree walk.

**Operational impact:**
- **Infinite block:** A frozen Excel process holding the UIA COM connection will block the tree walk forever. The sidecar process is effectively dead.
- **Cascading failure:** If the sidecar is supposed to serve multiple requests, one hung request blocks everything.
- **No circuit breaker:** No mechanism to detect "this app is consistently hanging" and stop retrying.
- **`--full` flag is a DoS vector:** With `max_depth=999` (line 419) and no timeout, walking a complex app tree with hung children is a guaranteed hang.

**Remediation:** `concurrent.futures` with `timeout`, or run UIA calls in separate threads with `threading.Timer` abort. Per-operation timeout (e.g., 5s per element, 30s total tree walk).

---

### [HIGH-3] No retry logic — transient failures treated as permanent

**Location:** Lines 33-143: `try/except Exception: pass` in every pattern probe. Lines 249-270: `try/except Exception: pass` in every `find_window` branch.

**What this means:** Every COM interaction that could fail transiently (window redraw, RPC timeout, COM marshaling delay) is silently swallowed with no retry attempt.

**Operational impact:**
- **Flaky perception:** A UIA host process that is slow to respond on the first call but would succeed on retry is treated as "pattern not supported." This corrupts the tier classification.
- **Silent data loss:** `find_window()` tries title, then class_name, then process_name. If the title search raises a COM error (not "not found" but actual COM failure), it falls through to the next search without logging the error. A window that exists might be reported as not found.
- **No exponential backoff:** Transient failures (which are common in COM-based systems under load) are not retried at all.
- **No dead man's switch:** No tracking of "how many failures in a row" to alert operators.

**Remediation:** Retry decorator with exponential backoff (e.g., `tenacity` or `backoff` library). Configurable max retries. Alert threshold for repeated failures.

---

### [HIGH-4] No rate limiting — rapid-fire LLM requests can overwhelm UIA host processes

**Location:** Not present. The PERCEIVE→PLAN→ACT→VERIFY loop (from spec) implies multiple tree walks per action cycle.

**What this means:** If Hermes (the LLM) sends rapid perception requests, each one triggers a full synchronous UIA tree walk with 1,400+ COM calls (for a 100-element tree with 14 patterns each).

**Operational impact:**
- **UIA host process saturation:** The UIA host process (`UIHost.exe`) can be overwhelmed by rapid COM calls, causing it to throttle or drop connections.
- **Target application degradation:** Heavy UIA polling can make the target application (Excel, SAGE) visibly slow or unresponsive.
- **Stale reads:** If the tree walk takes 3 seconds and the UI changes during the walk, the result is inconsistent (part of the tree reflects old state, part reflects new state).
- **No backpressure:** No mechanism to tell the caller "slow down" when the sidecar is overloaded.

**Remediation:** Rate limiter (e.g., 1 tree walk per 2 seconds minimum). Token bucket or sliding window. Backpressure signal to caller.

---

### [HIGH-5] `mss` vs Windows Graphics Capture — spec deviation

**Location:** Line 26: `import mss`. Line 320: `with mss.mss() as sct:`.

**What this means:** The spec explicitly calls for **Windows Graphics Capture (WinRT API)**. `mss` is a GDI/DXGI wrapper — a completely different API surface.

**Operational impact:**
- **DPI awareness:** `mss` captures in device coordinates. WinRT Graphics Capture can capture in logical coordinates. On high-DPI displays (common on modern laptops at 150% scaling), `mss` screenshots will be misaligned with UIA bounding rectangles.
- **Virtual desktop isolation:** WinRT Graphics Capture can capture individual virtual desktops. `mss` captures the active monitor regardless of virtual desktop.
- **Performance:** WinRT Graphics Capture is GPU-accelerated and can capture without blocking the UI thread. `mss` uses DXGI which is efficient but not the same API path.
- **Future compatibility:** Microsoft is deprecating GDI/DXGI screen capture in favor of WinRT Graphics Capture for privacy and security reasons. The `mss` approach may break in future Windows updates.
- **Privacy compliance:** WinRT requires explicit consent from the captured application (per Microsoft's privacy model). This is actually a *security feature* that the spec likely intended. `mss` bypasses this consent mechanism.

**Remediation:** Replace `mss` with `windows.graphics.capture` (WinRT) or use the Windows Community Toolkit's screen capture API.

---

### [HIGH-6] No configuration management — all settings are CLI arguments

**Location:** Lines 369-378: `argparse.ArgumentParser` with 9 CLI arguments.

**What this means:** Every parameter (target window, depth, screenshot toggle, output path) must be passed via CLI arguments. There is no config file (`.yaml`, `.toml`, `.json`, `.ini`), no environment variable support, and no defaults beyond hardcoded values.

**Operational impact:**
- **Service deployment impossible:** A Windows service cannot be configured with CLI arguments — it needs a config file. Every config change requires modifying the service startup command and restarting.
- **No environment-specific configs:** Cannot have different configs for dev/staging/production (different output paths, different log levels, different target apps).
- **Secrets in CLI arguments:** CLI arguments are visible in process listings (`tasklist`, `Get-Process` in PowerShell). If credentials or sensitive paths are passed as arguments, they're exposed to any process that can enumerate processes.
- **No hot-reload:** Config changes require process restart. No `watch` or `SIGHUP`-style reload.

**Remediation:** Config file (`config.yaml` or `config.toml`) with environment variable overrides. Hierarchical config (defaults → file → env → CLI). Config schema validation.

---

### [HIGH-7] Screenshot file accumulation — unbounded disk growth

**Location:** Line 336-337: Timestamped filenames with no cleanup.

**What this means:** Each screenshot is saved as `hermes_spike_YYYYMMDD_HHMMSS.png` (~122KB each based on the existing file). There is no:
- Maximum file count limit
- Age-based rotation
- Size-based rotation
- Cleanup/expiration policy

**Operational impact:**
- **Disk space leak:** At 1 screenshot/minute, that's ~175MB/day, ~5.3GB/month. At 1 screenshot/second, that's ~10.5GB/day. The disk will eventually fill.
- **No alerting:** No warning when the output directory exceeds a size threshold.
- **Forensic data retention:** In a financial services context, uncontrolled screenshot accumulation creates an unmanaged data retention problem (GDPR, SOX, etc.).
- **Filename collision:** If two screenshots are captured in the same second (race condition), the second overwrites the first silently.

**Remediation:** Maximum file count (e.g., keep last 100). Age-based rotation (e.g., delete files older than 24 hours). Size-based rotation (e.g., cap total at 1GB). Or better: stream screenshots over WebSocket instead of writing to disk.

---

### [HIGH-8] `except Exception: pass` — real failures silently dropped

**Location:** Lines 37, 48, 55, 62, 69, 81, 93, 107, 114, 121, 128, 135, 142, 165, 191, 253, 262, 270, 305 — **20 bare `except` blocks** that silently swallow exceptions.

**What this means:** Every COM interaction that could fail is wrapped in `try/except Exception: pass` with no logging, no metrics, no fallback, and no indication to the caller.

**Operational impact:**
- **Silent corruption:** If `GetValuePattern()` fails (line 41-48), the element has no "value" pattern. The tier classifier undercounts patterns, potentially misclassifying a T1 app as T2. Hermes makes wrong decisions based on incomplete data.
- **Debugging impossible:** When a production operator sees "window found but 0 patterns," there's no record of which pattern probes failed or why.
- **Security blindness:** Access denied errors (UIPI violations) are silently swallowed. The operator has no feedback that they're running at the wrong integrity level.
- **Pattern probe count is wrong:** The spec's tier classification depends on pattern diversity. If pattern probes fail silently, the classification is unreliable.

**Remediation:** At minimum, log the exception (`logger.debug("Pattern probe failed: %s", e)`). Better: track failure counts per pattern type and surface in the summary.

---

### [MEDIUM-1] No process isolation — runs in whatever Python environment invokes it

**Location:** Entire file. No virtual environment check, no sandboxing, no process separation.

**What this means:** The script runs in whatever Python environment is active. There's no check for:
- Virtual environment activation
- Python version compatibility
- Required system permissions
- Admin elevation

**Operational impact:**
- **Dependency conflicts:** If run in the wrong Python environment, imports may fail or load wrong versions.
- **Privilege escalation risk:** If a process manager runs this as SYSTEM or Administrator (common for services), it gains access to ALL windows including elevated ones — a privilege amplification risk.
- **No environment validation:** No startup check to verify all dependencies are present and correct versions.

**Remediation:** `pyproject.toml` with Python version constraint. Startup health check that validates environment. Document required privilege level.

---

### [MEDIUM-2] No error response format for service consumers

**Location:** Line 318: `return None` (capture_frame on no bbox). Line 349: `return None` (capture_frame on error). Line 272: `return None` (find_window on not found).

**What this means:** Error conditions return `None` with a `print()` to stderr. In a CLI context this is acceptable. In a WebSocket service context, the consumer receives `null` with no error code, no error message, and no suggestion for remediation.

**Operational impact:**
- **Caller cannot distinguish errors:** `None` could mean "window not found," "COM error," "screenshot failed," "permission denied," or "programmer forgot to return a value."
- **No error classification:** No way to distinguish retryable errors (transient COM failure) from non-retryable errors (window doesn't exist).
- **No structured error reporting:** Hermes (the LLM) cannot reason about errors without structured error information.

**Remediation:** Structured error responses: `{ "error": "window_not_found", "target": "...", "suggestion": "try --list" }`. Error codes for retryable vs non-retryable.

---

### [MEDIUM-3] No upgrade path — updates require manual intervention

**Location:** Not present.

**What this means:** There is no mechanism to update the sidecar without:
1. Killing the running process
2. Replacing the file
3. Restarting the process

**Operational impact:**
- **Downtime on every update:** Cannot roll out a bugfix without the sidecar being unavailable.
- **No rollback:** If the new version has a bug, there's no way to quickly revert to the previous version.
- **No version tracking:** No way to know which version is running (`spike.py` has no version string).
- **No canary deployment:** Cannot run old and new versions side by side.

**Remediation:** Version string in code. Graceful shutdown signal (drain connections, finish current request, then exit). Process manager that supports rolling restarts.

---

### [MEDIUM-4] No Windows-specific environment detection

**Location:** Not present. The script has no platform check, no elevation check, no DPI awareness check.

**What this means:** The script assumes:
- It's running on Windows (UIA is Windows-only, but no explicit check)
- It's running with sufficient permissions (no UIPI/elevation check)
- DPI scaling is 100% (no `SetProcessDpiAwarenessContext` call)
- The desktop session is interactive (no check for RDP, session 0, or service context)

**Operational impact:**
- **Silent failure on non-Windows:** Running on Linux (WSL) or macOS produces confusing COM errors instead of a clear "Windows required" message.
- **UIPI failures are silent:** If running at Medium IL targeting High IL windows, UIA returns empty trees. The script reports "0 elements" with no indication of why.
- **DPI scaling breaks coordinate mapping:** At 150% DPI, `mss` coordinates and UIA coordinates don't match. Screenshots are offset from bounding boxes.
- **Service context failure:** Windows services run in Session 0 (non-interactive desktop). UIA requires an interactive desktop (Session 1+). Running as a Windows service would silently fail to see any windows.

**Remediation:** Platform check at startup. Elevation detection (`ctypes.windll.shell32.IsUserAnAdmin()`). DPI awareness call. Session detection with clear error messages.

---

### [MEDIUM-5] JSON output uses `default=str` — masks serialization errors

**Location:** Line 473: `json.dumps(output, indent=2, default=str)`

**What this means:** Any non-serializable Python object (COM objects, custom types, file handles) is silently converted to its string representation instead of raising an error.

**Operational impact:**
- **Silent data corruption:** A COM object that should have been extracted as a specific value instead becomes `"uiautomation.Control object at 0x000001..."`. The JSON is valid but the data is garbage.
- **No validation:** No way to detect that a value was incorrectly serialized.
- **Inconsistent output:** The same field might be a number in one run (when the value was an int) and a string in another run (when `default=str` converted a COM object).

**Remediation:** Explicit serialization for each field type. Pydantic models with validators. Fail fast on unserializable types.

---

### [MEDIUM-6] No backup/restore for state

**Location:** Not present. The spec mentions "if this tool modifies state (future), how do you undo?"

**What this means:** The current spike is read-only (PERCEIVE only), so this is partially a future concern. However:
- The `state.json` file (95KB) is overwritten on each run with no backup
- No versioned state snapshots for diffing
- No undo mechanism for when ACT is implemented

**Operational impact:**
- **No rollback:** When Phase 1 implements ACT (clicking buttons, entering data), there will be no way to undo an incorrect action.
- **No state history:** Cannot reconstruct the sequence of state changes for debugging or compliance.

**Remediation:** Versioned state snapshots. Pre-action state capture (for undo). State change log with before/after values.

---

### [MEDIUM-7] No Windows-specific graceful degradation

**Location:** Lines 25-27: `import uiautomation`, `import mss`. No `try/except ImportError` at module level.

**What this means:** If either dependency is missing, the script crashes at import time with an unhelpful traceback. There's no graceful degradation (e.g., "running without screenshot support").

**Operational impact:**
- **All-or-nothing:** Missing `mss` means the entire script fails to start, even though tree walking doesn't need `mss`.
- **No partial operation:** Cannot degrade to "tree walk only, no screenshots" if the screenshot dependency fails.

**Remediation:** Lazy imports. `try/except ImportError` with graceful degradation. Startup diagnostics that report missing optional dependencies.

---

### [LOW-1] Duplicate import inside function

**Location:** Line 22: `from datetime import datetime`. Line 335: `from datetime import datetime` (inside `capture_frame`).

**What this means:** `datetime` is imported at module level (line 22) and again inside `capture_frame()` (line 335). The inner import is redundant.

**Operational impact:** Minimal — Python caches imports, so this is a no-op after the first import. But it's a code smell suggesting the developer wasn't aware of the module-level import.

---

### [LOW-2] PIL imported inside function body

**Location:** Line 340: `from PIL import Image as PilImage` (inside `capture_frame`).

**What this means:** PIL import is deferred to screenshot time. Import errors only surface when `--screenshot` is used.

**Operational impact:** Startup succeeds even when PIL is missing/broken. The error only appears during screenshot capture, which could be the first (and only) operation in production.

---

### [LOW-3] Output directory permissions not checked

**Location:** Lines 339-342, 475-477: File writes without directory existence or permission checks.

**What this means:** If the output directory doesn't exist (e.g., on a new machine), the file write fails with `FileNotFoundError`. No `os.makedirs(exist_ok=True)` or permission check.

**Operational impact:** Script crashes at write time instead of failing fast at startup with a clear error message.

---

### [LOW-4] No `.gitignore` for generated artifacts

**Location:** No `.gitignore` file in the project.

**What this means:** `state.json` (95KB of extracted UI tree data) and `hermes_spike_20260626_123714.png` (122KB screenshot) exist in the project directory. If this were in a Git repository, these would be tracked unless explicitly ignored.

**Operational impact:**
- **PII in version control:** `state.json` contains extracted UI data including window names, element values, and potentially sensitive information. Committing this to Git is a data leak.
- **Repository bloat:** Binary files (PNG) in Git bloat the repository.

**Remediation:** `.gitignore` with `*.json`, `*.png`, `*.log` patterns. Pre-commit hook to prevent accidental commits of sensitive files.

---

### [LOW-5] 80,000 character stdout truncation is arbitrary

**Location:** Lines 483-485:
```python
if len(json_str) > 80000:
    print(json_str[:80000])
    print(f"\n... [truncated, total {len(json_str)} chars. Use --output to save full JSON]")
```

**What this means:** The stdout output is truncated at 80KB with a message to use `--output`. The truncation point is arbitrary and the truncated output is invalid JSON.

**Operational impact:** If someone pipes stdout to another process (e.g., `python spike.py --target "..." | jq .`), the truncated output causes a JSON parse error with no clear indication of why.

---

### [LOW-6] No resource monitoring during tree walk

**Location:** Lines 421-426: Timer exists for logging but no resource tracking.

**What this means:** The script measures wall-clock time for tree walks but tracks nothing else: memory usage, CPU time, COM call count, RPC latency, or error rates.

**Operational impact:** Cannot answer "is the tree walk getting slower over time?" or "is memory usage growing with each walk?" — both are important for detecting resource leaks in a long-running service.

---

## SPEC REQUIREMENTS vs OPERATIONAL IMPLEMENTATION

| Spec Requirement | Status | Gap Severity |
|---|---|---|
| Sidecar service | **MISSING** | CRITICAL |
| Local WebSocket interface | **MISSING** | CRITICAL |
| OathLedger logging | **MISSING** | CRITICAL |
| Hermes Interceptor routing | **MISSING** | CRITICAL |
| Health checks | **MISSING** | HIGH |
| Structured logging | **MISSING** | HIGH |
| Configuration management | **MISSING** | HIGH |
| Process monitoring | **MISSING** | HIGH |
| Graceful shutdown | **MISSING** | HIGH |
| Dependency management | **MISSING** | MEDIUM |
| Retry logic | **MISSING** | MEDIUM |
| Rate limiting | **MISSING** | MEDIUM |
| Upgrade path | **MISSING** | MEDIUM |
| Resource cleanup | **MISSING** | MEDIUM |
| Windows Graphics Capture (WinRT) | **WRONG API** (`mss` used) | HIGH |
| Environment validation | **MISSING** | MEDIUM |
| Backup/restore | **MISSING** | MEDIUM |

**0 of 17 operational requirements are met.**

---

## RISK MATRIX

| Risk | Probability | Impact | Mitigation Exists? |
|---|---|---|---|
| Sidecar crashes, stays dead | HIGH | HIGH | NO |
| COM resources leak on kill | HIGH | MEDIUM | NO |
| Hung app blocks sidecar forever | HIGH | HIGH | NO |
| Disk fills from screenshots | MEDIUM | MEDIUM | NO |
| Transient COM failures lose data | HIGH | HIGH | NO |
| Wrong DPI breaks coordinate mapping | HIGH | MEDIUM | NO |
| Running in service context sees 0 windows | HIGH | HIGH | NO |
| Rapid LLM requests saturate UIA | MEDIUM | HIGH | NO |
| Dependencies drift between environments | MEDIUM | MEDIUM | NO |
| PII leaked via stdout | HIGH | HIGH | NO |

---

## PRIORITY REMEDIATION

### P0 — Cannot deploy without:
1. **Service wrapper** — Windows service or async event loop with WebSocket server
2. **Graceful shutdown** — Signal handlers, `atexit`, COM cleanup
3. **Structured logging** — Python `logging` with rotation, levels, structured format
4. **Dependency management** — `requirements.txt` with pinned versions
5. **Timeout on UIA operations** — Per-element and total tree walk timeouts
6. **Configuration management** — Config file with env var overrides

### P1 — Must address before handling production data:
7. **Health checks** — `/health` endpoint or equivalent
8. **Retry logic** — Exponential backoff for transient COM failures
9. **Rate limiting** — Token bucket for tree walk requests
10. **Fix hardcoded paths** — Environment variable or config-driven paths
11. **Replace `mss` with WinRT Graphics Capture** — Per spec requirement
12. **Error response format** — Structured errors, not `None`
13. **Environment validation** — Platform, elevation, DPI, session checks
14. **Screenshot lifecycle management** — Rotation, cleanup, or stream instead of disk

### P2 — Should address for production readiness:
15. **Upgrade path** — Version tracking, graceful drain, rolling restart
16. **Resource monitoring** — Memory, CPU, COM call counts
17. **Backup/restore** — State versioning, undo mechanism
18. **`.gitignore`** — Prevent PII in version control
19. **Replace `default=str`** — Explicit serialization with validation
20. **Fix duplicate imports** — Cleanup module-level imports
21. **Output directory validation** — `makedirs(exist_ok=True)` at startup
22. **Graceful degradation** — Optional dependency handling
23. **Fix stdout truncation** — Return valid JSON or structured error
24. **Performance monitoring** — Track tree walk latency trends
25. **Process isolation** — Virtual environment enforcement
26. **Schema versioning** — Version field in JSON output

---

## FINAL ASSESSMENT

This is a **proof-of-concept CLI script**. It demonstrates that UIA tree walking works from Python on Windows. That is its sole achievement.

As a **production sidecar service**, it is non-functional:
- It cannot run as a service (no event loop, no WebSocket, no daemon mode)
- It cannot be monitored (no health checks, no metrics, no logs)
- It cannot be configured (no config file, hardcoded paths)
- It cannot be deployed (no dependency management, no environment validation)
- It cannot survive failures (no retry, no timeout, no graceful shutdown)
- It cannot be operated (no logging, no error reporting, no resource monitoring)
- It uses the wrong screenshot API (mss instead of WinRT Graphics Capture)

**The operational gap is total.** Every infrastructure concern identified in this review requires work that is orthogonal to the spike's core perception logic. Phase 1 cannot be an "extension" of this code — it must be a new project that imports or re-implements the tree walking logic within a proper service architecture.

The existing architecture review and security review cover the design and security gaps respectively. This operational review confirms that **infrastructure-level concerns are equally unaddressed**. All three reviews point to the same conclusion: treat the spike as a disposable proof-of-concept and build Phase 1 from a proper service architecture template.
