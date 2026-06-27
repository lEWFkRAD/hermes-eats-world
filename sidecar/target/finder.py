"""
Hermes Eats World — Window Targeting
=====================================
Find and attach to windows by title (substring), process name, or class name.
Includes PID→process-name lookup via ctypes (no psutil dependency).

Returns both TargetInfo metadata AND the live uiautomation Control handle,
so the caller doesn't need to re-attach (eliminates the double-attach bug).
"""

import ctypes
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import uiautomation

from ..schema.models import BoundingBox, TargetInfo, WindowInfo

logger = logging.getLogger(__name__)


@dataclass
class WindowTarget:
    """Combined target: metadata + live control handle.
    
    Avoids the double-attach anti-pattern where find_window() returns
    metadata and the caller re-attaches with a new WindowControl().
    """
    info: TargetInfo
    control: uiautomation.Control
    # For tracing/debugging
    search_method: str = field(default="")  # "title", "process", "class"


def _pid_to_process_name(pid: int) -> str:
    """Get process name from PID using ctypes (no external deps)."""
    try:
        kernel = ctypes.windll.kernel32
        PROCESS_QUERY_INFO = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = kernel.OpenProcess(PROCESS_QUERY_INFO | PROCESS_VM_READ, False, pid)
        if not handle:
            return ""
        try:
            size = ctypes.c_ulong(260)
            name = ctypes.create_unicode_buffer(size.value)
            # QueryFullProcessImageNameW requires lpdwSize (in/out) as the 4th
            # argument; omitting it makes the call fail and yields an empty name.
            if not kernel.QueryFullProcessImageNameW(
                handle, 0, name, ctypes.byref(size)
            ):
                return ""
            # Return just the basename
            return name.value.split("\\")[-1]
        finally:
            kernel.CloseHandle(handle)
    except Exception as e:
        logger.debug("PID lookup failed for %d: %s", pid, e)
        return ""


def find_window(
    title: Optional[str] = None,
    process_name: Optional[str] = None,
    class_name: Optional[str] = None,
    timeout: int = 5,
    hwnd: Optional[int] = None,
) -> Optional[WindowTarget]:
    """Find a window by hwnd, title, process name, or class name.

    Priority: hwnd (exact) > title > process_name > class_name (first match wins).
    `hwnd` is the precise, unambiguous selector — title is a substring match that
    can hit the wrong window when titles collide, so callers that already know the
    handle (e.g. the desktop picker) should pass hwnd to avoid mis-targeting.

    Returns WindowTarget with both metadata AND the live control handle,
    so the caller can walk the tree immediately without re-attaching.

    For backward compatibility, the returned object is also truthy/falsy
    like the old TargetInfo return.
    """
    # Search by hwnd (exact, unambiguous) — preferred selector.
    if hwnd:
        for w in _enumerate_top_windows():
            try:
                if w.NativeWindowHandle == hwnd:
                    return WindowTarget(
                        info=_make_target_info(w),
                        control=w,
                        search_method="hwnd",
                    )
            except Exception as e:
                logger.debug("hwnd search error: %s", e)
        # An hwnd was explicitly requested but not found — do NOT silently fall
        # back to a fuzzy title match on a different window.
        return None

    # Search by title (substring)
    if title:
        win = uiautomation.WindowControl(searchDepth=1, SubName=title)
        if win.Exists(0, timeout):
            return WindowTarget(
                info=_make_target_info(win),
                control=win,
                search_method="title",
            )

    # Search by process name
    if process_name:
        for w in _enumerate_top_windows():
            try:
                pid = w.ProcessId
                actual_name = _pid_to_process_name(pid)
                if process_name.lower() in actual_name.lower():
                    return WindowTarget(
                        info=_make_target_info(w),
                        control=w,
                        search_method="process",
                    )
            except Exception as e:
                logger.debug("Process name search error: %s", e)

    # Search by class name
    if class_name:
        win = uiautomation.WindowControl(searchDepth=1, ClassName=class_name)
        if win.Exists(0, timeout):
            return WindowTarget(
                info=_make_target_info(win),
                control=win,
                search_method="class",
            )

    return None


def list_windows(min_size: tuple = (100, 100)) -> List[WindowInfo]:
    """List all visible top-level windows (filtered by minimum size)."""
    windows: List[WindowInfo] = []
    min_w, min_h = min_size

    for w in _enumerate_top_windows():
        try:
            rect = w.BoundingRectangle
            w_width = rect.width()
            w_height = rect.height()
            if w_width < min_w and w_height < min_h:
                continue

            windows.append(WindowInfo(
                name=str(w.Name) if w.Name else "",
                class_name=str(w.ClassName) if w.ClassName else "",
                automation_id=str(w.AutomationId) if w.AutomationId else "",
                process_id=w.ProcessId,
                hwnd=w.NativeWindowHandle or None,
                bounding_box=BoundingBox(
                    left=rect.left,
                    top=rect.top,
                    width=w_width,
                    height=w_height,
                ),
                is_enabled=w.IsEnabled,
            ))
        except Exception as e:
            logger.debug("Error enumerating window: %s", e)

    return windows


def _enumerate_top_windows():
    """Yield all top-level window controls."""
    try:
        desktop = uiautomation.GetRootControl()
        for child in desktop.GetChildren():
            if child.ControlTypeName == "WindowControl":
                yield child
    except Exception as e:
        logger.error("Failed to enumerate windows: %s", e)


def _make_target_info(win) -> TargetInfo:
    """Build a TargetInfo model from a uiautomation window control."""
    try:
        rect = win.BoundingRectangle
        bbox = BoundingBox(
            left=rect.left,
            top=rect.top,
            width=rect.width(),
            height=rect.height(),
        )
    except Exception:
        bbox = None

    return TargetInfo(
        name=str(win.Name) if win.Name else "",
        class_name=str(win.ClassName) if win.ClassName else "",
        process_id=win.ProcessId,
        bounding_box=bbox,
        hwnd=win.NativeWindowHandle or None,
    )
