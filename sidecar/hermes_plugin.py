"""Hermes plugin registration for profile-scoped Windows UIA perception."""

from __future__ import annotations

import json
import threading
from functools import partial
from typing import Any

from .plugin_runtime import (
    configure_cli,
    handle_cli,
    run_runtime_worker,
    runtime_available,
    runtime_python,
)

TOOL_NAME = "uia_perceive_window"
_SCAN_SLOT = threading.BoundedSemaphore(1)

TOOL_SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Read one bounded Windows UI Automation snapshot for the exact native window "
        "returned by Hermes HUD mode. ValuePattern text and password controls are redacted, "
        "but labels and automation identifiers can still be sensitive. The lookup fails closed "
        "and never falls back to title or process matching."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_id": {
                "type": "integer",
                "minimum": 1,
                "description": "Fresh Windows HWND from read_window_below.window.id.",
            },
            "mode": {
                "type": "string",
                "enum": ["tree", "summary"],
                "default": "tree",
                "description": "Return the bounded UIA tree or only target/tier/summary metadata.",
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
                "maximum": 2000,
                "default": 500,
                "description": "Hard ceiling for inspected UI elements.",
            },
            "max_output_bytes": {
                "type": "integer",
                "minimum": 16384,
                "maximum": 262144,
                "default": 131072,
                "description": "Maximum UTF-8 size of the returned JSON payload.",
            },
            "timeout": {
                "type": "number",
                "minimum": 1,
                "maximum": 30,
                "default": 15,
                "description": "Killable runtime deadline in seconds.",
            },
        },
        "required": ["window_id"],
        "additionalProperties": False,
    },
}


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


def _mode(args: dict[str, Any]) -> str:
    value = args.get("mode", "tree")
    if value not in {"tree", "summary"}:
        raise ValueError("mode must be 'tree' or 'summary'")
    return value


def handle_uia_perceive_window(
    args: dict[str, Any] | None,
    *,
    profile_name: str = "default",
    **_kwargs: Any,
) -> str:
    """Run one exact-window snapshot through the profile-owned isolated runtime."""
    args = args or {}
    try:
        request = {
            "window_id": _bounded_int(args, "window_id", 0, 1, 2**63 - 1),
            "mode": _mode(args),
            "depth": _bounded_int(args, "depth", 3, 0, 10),
            "max_elements": _bounded_int(args, "max_elements", 500, 1, 2000),
            "max_output_bytes": _bounded_int(
                args, "max_output_bytes", 131072, 16384, 262144
            ),
            "timeout": _bounded_timeout(args),
        }
    except ValueError as exc:
        return _error(profile_name, "invalid_arguments", str(exc))

    if not runtime_available():
        return _error(
            profile_name,
            "runtime_unavailable",
            f"Activate '{profile_name}' with 'hermes profile use {profile_name}', run "
            "'hermes heaw setup' on Windows, then restart that profile's gateway.",
        )

    if not _SCAN_SLOT.acquire(blocking=False):
        return _error(
            profile_name,
            "scan_in_progress",
            "Another UIA scan is already running in this Hermes profile.",
            retryable=True,
        )

    try:
        result = run_runtime_worker(request, timeout=request["timeout"] + 2)
    finally:
        _SCAN_SLOT.release()

    result["hermes_profile"] = profile_name
    encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > request["max_output_bytes"]:
        return _error(
            profile_name,
            "output_budget_exceeded",
            "The UIA result exceeded the configured model-output budget.",
            retryable=True,
        )
    return encoded.decode("utf-8")


def register(ctx: Any) -> None:
    """Register a read-only tool and operator setup command for the active profile."""
    ctx.register_tool(
        name=TOOL_NAME,
        toolset="hermes_eats_world",
        schema=TOOL_SCHEMA,
        handler=partial(handle_uia_perceive_window, profile_name=ctx.profile_name),
        check_fn=runtime_available,
        description=TOOL_SCHEMA["description"],
        emoji="🪟",
    )
    ctx.register_cli_command(
        name="heaw",
        help="Set up and inspect the isolated Hermes Eats World runtime",
        setup_fn=configure_cli,
        handler_fn=handle_cli,
        description=(
            "Create a profile-owned Python runtime for Windows UI Automation without "
            "modifying Hermes's Python environment."
        ),
    )


__all__ = [
    "TOOL_NAME",
    "TOOL_SCHEMA",
    "handle_uia_perceive_window",
    "register",
    "runtime_python",
]
