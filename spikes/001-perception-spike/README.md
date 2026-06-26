# 001: Perception Spike (Phase 0)

**Question:** Can we attach to a running Windows application, walk its UIA accessibility tree, extract structured element state as JSON, and capture a visual frame?

**Given/When/Then:**
- **Given** a running Windows application window
- **When** we attach via UI Automation and walk the element tree
- **Then** we produce structured JSON state with element roles, names, values, bounding rects, and available control patterns

**Approach:** Python + `uiautomation` library for UIA tree walking, `mss` for screen capture. Running on Windows 10 via Git Bash/MSYS2.

**Key risk:** Will the UIA library work correctly through the MSYS2/bash environment? COM/Windows API calls should work fine from Python on Windows regardless of shell.

**Target test app:** Notepad (simple, known UIA structure)

## Verdict: [TO BE FILLED]
