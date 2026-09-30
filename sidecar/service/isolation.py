"""Killable subprocess boundary for potentially blocking UI Automation work."""

from __future__ import annotations

import multiprocessing
import queue
import time
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
    deadline = time.monotonic() + timeout
    process.start()
    try:
        # Drain while the child is alive. Joining first can deadlock when its
        # Queue feeder fills the pipe and cannot finish flushing a large result.
        payload = None
        while payload is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                payload = result_queue.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                if not process.is_alive():
                    # The child may have flushed and exited between the timed
                    # read and is_alive(). Check once more before calling it a crash.
                    try:
                        payload = result_queue.get_nowait()
                    except queue.Empty:
                        return IsolatedResult(
                            status="crash",
                            error="Worker exited without returning a result",
                            exit_code=process.exitcode,
                        )
        if payload is not None:
            process.join(max(0, deadline - time.monotonic()))
        if payload is None or process.is_alive():
            _terminate_worker(process)
            return IsolatedResult(
                status="timeout",
                error=f"Worker exceeded {timeout:g} seconds and was terminated",
                exit_code=process.exitcode,
            )
        return IsolatedResult(exit_code=process.exitcode, **payload)
    finally:
        if process.is_alive():
            _terminate_worker(process)
        result_queue.close()
        if not process.is_alive():
            process.close()


def _terminate_worker(process) -> None:
    process.terminate()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)
