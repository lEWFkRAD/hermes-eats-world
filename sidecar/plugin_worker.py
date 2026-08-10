"""One-request JSON worker executed by the plugin-owned Python runtime."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

from .schema import SCHEMA_VERSION
from .service.env_check import set_dpi_awareness
from .service.worker import perceive_hwnd
from .target import find_window

REDACTION_METADATA = {
    "value_patterns": True,
    "password_controls": True,
    "element_names": False,
    "automation_ids": False,
}


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {"error": code, "message": message, "retryable": retryable}


def perceive_request(request: dict[str, Any]) -> dict[str, Any]:
    """Return one exact-HWND snapshot with explicit privacy and size metadata."""
    window_id = request["window_id"]
    set_dpi_awareness()
    target = find_window(hwnd=window_id, timeout=min(5, max(1, int(request["timeout"]))))
    if target is None or target.hwnd != window_id:
        return _error(
            "window_not_found",
            f"Could not attach to exact window id {window_id}.",
            retryable=True,
        )

    payload = perceive_hwnd(
        {
            "hwnd": window_id,
            "class_name": target.class_name,
            "expected_process_id": target.process_id,
            "max_depth": request["depth"],
            "include_raw_values": False,
            "max_elements": request["max_elements"],
            "timeout": request["timeout"],
        }
    )
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "target": target.model_dump(mode="json"),
        "tier": payload["tier"],
        "summary": payload["summary"],
        "screenshot_path": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if request["mode"] == "tree":
        snapshot["tree"] = payload["tree"]

    result = {
        "sensitive_artifact": True,
        "redaction": REDACTION_METADATA,
        "truncated": bool(payload["truncated"]),
        "snapshot": snapshot,
    }
    encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > request["max_output_bytes"]:
        return {
            "error": "output_budget_exceeded",
            "message": "The UIA snapshot exceeded the configured model-output budget.",
            "retryable": True,
            "sensitive_artifact": True,
            "redaction": REDACTION_METADATA,
            "summary": payload["summary"],
            "suggested_parameters": {
                "mode": "summary",
                "depth": max(0, request["depth"] - 1),
                "max_elements": max(1, request["max_elements"] // 2),
            },
        }
    result["output_bytes"] = len(encoded)
    return result


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        result = perceive_request(request)
    except BaseException as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        result = _error(
            "tree_worker_error",
            "The isolated UIA worker could not complete the snapshot.",
            retryable=True,
        )
    # ASCII-safe JSON avoids Windows console-codepage corruption when the
    # parent process decodes the worker pipe as UTF-8.
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
