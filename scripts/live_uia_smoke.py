#!/usr/bin/env python3
"""Sanitized live exact-HWND smoke test for an interactive Windows session."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys

from sidecar.plugin_worker import perceive_request


def taskbar_hwnd() -> int:
    if sys.platform != "win32":
        raise RuntimeError("live UIA smoke tests require native Windows")
    hwnd = int(ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None))
    if hwnd < 1:
        raise RuntimeError("could not find the Windows Shell_TrayWnd taskbar")
    return hwnd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--taskbar", action="store_true", help="Use the generic taskbar root")
    selector.add_argument("--hwnd", type=lambda value: int(value, 0), help="Use a sanitized HWND")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hwnd = taskbar_hwnd() if args.taskbar else args.hwnd
    result = perceive_request(
        {
            "window_id": hwnd,
            "mode": "summary",
            "depth": 0,
            "max_elements": 1,
            "max_output_bytes": 16384,
            "timeout": 5,
        }
    )
    if result.get("error"):
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1
    target = result["snapshot"]["target"]
    if target["hwnd"] != hwnd:
        raise RuntimeError("returned target HWND did not match the requested HWND")
    sanitized = {
        "ok": True,
        "requested_hwnd": hwnd,
        "returned_hwnd": target["hwnd"],
        "process_id_present": bool(target.get("process_id")),
        "element_count": result["snapshot"]["summary"]["total_elements"],
        "mode": "summary",
    }
    print(json.dumps(sanitized, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
