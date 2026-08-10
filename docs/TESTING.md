# Windows integration testing

Unit tests deliberately avoid depending on a shared interactive desktop. Before
releasing targeting, DPI, capture, runtime, or worker-boundary changes, run the
sanitized exact-HWND smoke test from an interactive Windows session:

```powershell
python scripts/live_uia_smoke.py --taskbar
```

The taskbar case uses depth 0, inspects one generic root, emits summary metadata
only, and verifies that the requested and returned HWNDs match. To test a blank
or synthetic application window without recording its contents:

```powershell
python scripts/live_uia_smoke.py --hwnd 0x123456
```

## Release matrix

Use synthetic or blank content only. Never capture client or personal data.

| Surface | Required check |
| --- | --- |
| Windows taskbar | Exact HWND, depth 0, one-element summary |
| Blank Notepad | Label/value redaction and stale-HWND rejection after close |
| File Explorer test folder | Win32 tree traversal and bounded output |
| Blank Office document | Office UIA tree and non-elevated process identity |
| Chromium/Electron test page | Deep-tree output budget and summary fallback |
| WinUI/UWP test app | Frame drilling while outer HWND/PID stays stable |
| Multi-monitor at mixed DPI | Bounds stay on the correct virtual desktop |
| Elevated test app | Normal-user inspection fails closed |
| `work` and `personal` profiles | Separate runtime paths and profile labels |

Record the application, synthetic fixture, requested HWND, returned HWND, depth,
element count, and pass/fail result. Do not record UI text, screenshots, window
titles, paths, usernames, process command lines, or other host-identifying data.
