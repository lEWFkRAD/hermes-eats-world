"""
Hermes Eats World — Window Targeting
=====================================
Find and attach to windows by exact HWND, title, process name, or class name.
Includes PID→process-name lookup via ctypes (no psutil dependency).
"""

import ctypes
import logging
from typing import List, Optional

import uiautomation

from ..schema.models import BoundingBox, TargetInfo, WindowInfo

logger = logging.getLogger(__name__)


def _pid_to_process_name(pid: int) -> str:
    """Get process name from PID using ctypes (no external deps)."""
    try:
        kernel = ctypes.windll.kernel32
        PROCESS_QUERY_INFO = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = kernel.OpenProcess(PROCESS_QUERY_INFO | PROCESS_VM_READ, False, pid)
        if not handle:
            return ""
        name = ctypes.create_unicode_buffer(260)
        kernel.QueryFullProcessImageNameW(handle, 0, name)
        kernel.CloseHandle(handle)
        # Return just the basename
        return name.value.split("\\")[-1]
    except Exception as e:
        logger.debug("PID lookup failed for %d: %s", pid, e)
        return ""


def find_window(
    title: Optional[str] = None,
    process_name: Optional[str] = None,
    class_name: Optional[str] = None,
    timeout: int = 5,
    hwnd: Optional[int] = None,
) -> Optional[TargetInfo]:
    """Find a window by exact HWND, title, process name, or class name.

    Priority: HWND > title > process_name > class_name (first match wins).
    Uses SubName for substring matching on window titles.

    An HWND lookup is intentionally fail-closed: when the exact handle is invalid
    or inaccessible, do not fall through to a weaker selector that could attach
    to a different window. Hermes HUD mode's ``read_window_below`` tool returns
    this handle as ``window.id`` on Windows.
    """
    if hwnd is not None:
        try:
            win = uiautomation.ControlFromHandle(hwnd)
            if win is not None and win.Exists(0, timeout):
                target = _make_target_info(win)
                if target.hwnd == hwnd:
                    return target
                logger.debug(
                    "HWND lookup returned a different handle: requested=%d actual=%s",
                    hwnd,
                    target.hwnd,
                )
        except Exception as e:
            logger.debug("HWND lookup failed for %d: %s", hwnd, e)
        return None

    # Search by title (substring)
    if title:
        win = uiautomation.WindowControl(searchDepth=1, SubName=title)
        if win.Exists(0, timeout):
            return _make_target_info(win)

    # Search by process name
    if process_name:
        for w in _enumerate_top_windows():
            try:
                pid = w.ProcessId
                actual_name = _pid_to_process_name(pid)
                if actual_name.lower() == process_name.lower():
                    return _make_target_info(w)
            except Exception as e:
                logger.debug("Process name search error: %s", e)

    # Search by class name
    if class_name:
        win = uiautomation.WindowControl(searchDepth=1, ClassName=class_name)
        if win.Exists(0, timeout):
            return _make_target_info(win)

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
            if w_width < min_w or w_height < min_h:
                continue

            windows.append(
                WindowInfo(
                    name=str(w.Name) if w.Name else "",
                    class_name=str(w.ClassName) if w.ClassName else "",
                    automation_id=str(w.AutomationId) if w.AutomationId else "",
                    process_id=w.ProcessId,
                    bounding_box=BoundingBox(
                        left=rect.left,
                        top=rect.top,
                        width=w_width,
                        height=w_height,
                    ),
                    is_enabled=w.IsEnabled,
                )
            )
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
