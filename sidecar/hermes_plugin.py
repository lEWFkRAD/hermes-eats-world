"""First-class Hermes plugin integration for exact-window UIA perception.

The plugin is deliberately stateless. Hermes loads and enables it inside the
active profile, while every tool response records that profile name. No state,
screenshots, or raw UI values are shared between profiles.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from functools import partial
from typing import Any

TOOL_NAME = "uia_perceive_window"

TOOL_SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Read a redacted Windows UI Automation tree for one exact native window. "
        "Pass the fresh window.id returned by Hermes HUD mode's read_window_below "
        "tool. The lookup fails closed and never falls back to title or process matching."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_id": {
                "type": "integer",
                "minimum": 1,
                "description": "Exact Windows HWND from read_window_below.window.id.",
            },
            "depth": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "default": 3,
                "description": "Maximum UIA tree depth. Keep this as small as practical.",
            },
            "max_elements": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5000,
                "default": 2000,
                "description": "Hard ceiling for returned UI elements.",
            },
            "timeout": {
                "type": "number",
                "minimum": 1,
                "maximum": 30,
                "default": 15,
                "description": "Killable UIA worker deadline in seconds.",
            },
        },
        "required": ["window_id"],
        "additionalProperties": False,
    },
}


def check_uia_available() -> bool:
    """Expose the tool only on Windows with the UI Automation dependency installed."""
    return sys.platform == "win32" and importlib.util.find_spec("uiautomation") is not None


def _error(profile_name: str, code: str, message: str, *, retryable: bool = False) -> str:
    return json.dumps(
        {
            "hermes_profile": profile_name,
            "error": code,
            "message": message,
            "retryable": retryable,
        },
        indent=2,
    )


def _bounded_int(args: dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    value = args.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return value


def _bounded_timeout(args: dict[str, Any]) -> float:
    value = args.get("timeout", 15)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout must be a number from 1 through 30")
    value = float(value)
    if not 1 <= value <= 30:
        raise ValueError("timeout must be a number from 1 through 30")
    return value


def handle_uia_perceive_window(
    args: dict[str, Any] | None,
    *,
    profile_name: str = "default",
    **_kwargs: Any,
) -> str:
    """Return one redacted, bounded snapshot without writing profile-shared state."""
    args = args or {}
    try:
        window_id = _bounded_int(args, "window_id", 0, 1, 2**63 - 1)
        depth = _bounded_int(args, "depth", 3, 0, 10)
        max_elements = _bounded_int(args, "max_elements", 2000, 1, 5000)
        timeout = _bounded_timeout(args)
    except ValueError as exc:
        return _error(profile_name, "invalid_arguments", str(exc))

    if not check_uia_available():
        return _error(
            profile_name,
            "uia_unavailable",
            "UIA perception requires Windows and the uiautomation package.",
        )

    # Imports stay lazy so Hermes can discover and list the plugin even before
    # the optional Windows runtime dependencies are installed.
    from .schema import SCHEMA_VERSION, Element, TierClassification, TreeSnapshot, TreeSummary
    from .service.env_check import set_dpi_awareness
    from .service.isolation import run_isolated
    from .service.worker import perceive_hwnd
    from .target import find_window

    set_dpi_awareness()
    target = find_window(hwnd=window_id, timeout=min(5, max(1, int(timeout))))
    if target is None or target.hwnd != window_id:
        return _error(
            profile_name,
            "window_not_found",
            f"Could not attach to exact window id {window_id}.",
            retryable=True,
        )

    worker_result = run_isolated(
        perceive_hwnd,
        {
            "hwnd": window_id,
            "class_name": target.class_name,
            "max_depth": depth,
            "include_raw_values": False,
            "max_elements": max_elements,
            "timeout": timeout,
        },
        timeout=timeout + 1,
    )
    if worker_result.status != "success":
        return _error(
            profile_name,
            f"tree_worker_{worker_result.status}",
            worker_result.error or "UIA perception worker failed.",
            retryable=worker_result.status in {"timeout", "crash"},
        )

    payload = worker_result.value
    snapshot = TreeSnapshot(
        schema_version=SCHEMA_VERSION,
        target=target,
        tier=TierClassification.model_validate(payload["tier"]),
        summary=TreeSummary.model_validate(payload["summary"]),
        tree=Element.model_validate(payload["tree"]),
        screenshot_path=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return json.dumps(
        {
            "hermes_profile": profile_name,
            "redacted": True,
            "snapshot": snapshot.model_dump(mode="json"),
        },
        indent=2,
    )


def register(ctx: Any) -> None:
    """Register one read-only tool scoped to the active Hermes profile."""
    ctx.register_tool(
        name=TOOL_NAME,
        toolset="hermes_eats_world",
        schema=TOOL_SCHEMA,
        handler=partial(handle_uia_perceive_window, profile_name=ctx.profile_name),
        check_fn=check_uia_available,
        description="Read a bounded, redacted UIA tree for an exact HUD window handle.",
        emoji="🪟",
    )
