"""Killable subprocess boundary for potentially blocking UI Automation work."""

from __future__ import annotations

import multiprocessing
import queue
import traceback
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class IsolatedResult:
    status: str
    value: Any = None
    error: str | None = None
    traceback: str | None = None
    exit_code: int | None = None


def _child_entry(result_queue, function: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        result_queue.put({"status": "success", "value": function(*args)})
    except BaseException as exc:
        result_queue.put(
            {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        )


def run_isolated(
    function: Callable[..., Any],
    *args: Any,
    timeout: float,
    start_method: str = "spawn",
) -> IsolatedResult:
    """Run a module-level callable in a process that can be forcibly terminated."""
    context = multiprocessing.get_context(start_method)
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_child_entry,
        args=(result_queue, function, args),
        daemon=True,
    )
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        result_queue.close()
        return IsolatedResult(
            status="timeout",
            error=f"Worker exceeded {timeout:g} seconds and was terminated",
            exit_code=process.exitcode,
        )

    try:
        payload = result_queue.get(timeout=1)
    except queue.Empty:
        return IsolatedResult(
            status="crash",
            error="Worker exited without returning a result",
            exit_code=process.exitcode,
        )
    finally:
        result_queue.close()

    return IsolatedResult(exit_code=process.exitcode, **payload)
