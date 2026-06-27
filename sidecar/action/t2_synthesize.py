"""
Hermes Eats World — T2 Actions (Vision-Guided Input Synthesis)
===============================================================
Synthesize mouse/keyboard input for T2 (sparse) and T3 (opaque) apps.
Coordinates are derived from OCR bounding boxes or template matching.

Uses ctypes to call Win32 SendInput / PostMessage directly.

Usage:
    from sidecar.action import click_at, type_text, post_message

    # Click at a specific device coordinate
    click_at(hwnd, x=100, y=200)

    # Type text into a window
    type_text(hwnd, "hello world")

    # Send a WM_SETTEXT message directly
    post_message(hwnd, "WM_SETTEXT", text="value")
"""

import logging
import struct
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Win32 constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_CHAR = 0x0102
WM_SETTEXT = 0x000C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

# Win32 API handles — argtypes set after struct definitions below
USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _INPUT_MOUSE(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUT_KEYBOARD(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUT_U(ctypes.Union):
    _fields_ = [
        ("mi", _INPUT_MOUSE),
        ("ki", _INPUT_KEYBOARD),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_U),
    ]


# Set argtypes for all Win32 API calls after struct definitions
PINPUT = ctypes.POINTER(_INPUT)
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.PostMessageW.restype = wintypes.BOOL
USER32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.SendMessageW.restype = wintypes.LPARAM
USER32.SendInput.argtypes = [wintypes.UINT, PINPUT, ctypes.c_int]
USER32.SendInput.restype = wintypes.UINT
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
USER32.ClientToScreen.restype = wintypes.BOOL
USER32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
USER32.ScreenToClient.restype = wintypes.BOOL
USER32.GetSystemMetrics.argtypes = [ctypes.c_int]
USER32.GetSystemMetrics.restype = ctypes.c_int


def _get_screen_dimensions() -> Tuple[int, int]:
    """Get virtual screen dimensions for SendInput absolute coordinates."""
    width = USER32.GetSystemMetrics(0)   # SM_CXVIRTUALSCREEN
    height = USER32.GetSystemMetrics(1)  # SM_CYVIRTUALSCREEN
    return width, height


def _absolute_coords(x: int, y: int) -> Tuple[int, int]:
    """Convert screen coordinates to SendInput absolute format (0-65535)."""
    width, height = _get_screen_dimensions()
    ax = int(x * 65535 / max(width, 1))
    ay = int(y * 65535 / max(height, 1))
    return ax, ay


def _send_input(inp: _INPUT) -> bool:
    """Send a single INPUT structure to the system."""
    result = USER32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if result != 1:
        logger.error("SendInput failed: %d", ctypes.get_last_error())
        return False
    return True


def client_to_screen(hwnd: int, cx: int, cy: int) -> Tuple[int, int]:
    """Convert client coordinates to screen coordinates."""
    point = wintypes.POINT(cx, cy)
    USER32.ClientToScreen(hwnd, ctypes.byref(point))
    return (point.x, point.y)


def screen_to_client(hwnd: int, sx: int, sy: int) -> Tuple[int, int]:
    """Convert screen coordinates to client coordinates."""
    point = wintypes.POINT(sx, sy)
    USER32.ScreenToClient(hwnd, ctypes.byref(point))
    return (point.x, point.y)


# ---------------------------------------------------------------------------
# Public T2 actions
# ---------------------------------------------------------------------------

def click_at(hwnd: int, x: int, y: int,
             button: str = "left", client_coords: bool = False) -> bool:
    """Click at a specific coordinate using SendInput.

    Args:
        hwnd: Target window handle (used for client_to_screen if needed).
        x: X coordinate (screen or client).
        y: Y coordinate (screen or client).
        button: "left" or "right" mouse button.
        client_coords: If True, x/y are in client coordinates.

    Returns:
        True if the click was sent successfully.
    """
    if client_coords:
        x, y = client_to_screen(hwnd, x, y)

    ax, ay = _absolute_coords(x, y)

    if button == "left":
        down_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN
        up_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP
    else:
        down_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_RIGHTDOWN
        up_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_RIGHTUP

    # Move to position
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = ax
    inp.u.mi.dy = ay
    inp.u.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
    if not _send_input(inp):
        return False

    time.sleep(0.01)  # Brief pause for move

    # Button down
    inp.u.mi.dwFlags = down_flags
    inp.u.mi.dx = ax
    inp.u.mi.dy = ay
    if not _send_input(inp):
        return False

    time.sleep(0.02)  # Press duration

    # Button up
    inp.u.mi.dwFlags = up_flags
    if not _send_input(inp):
        return False

    logger.info("T2 click at (%d, %d) on hwnd=%d", x, y, hwnd)
    return True


def type_text(hwnd: int, text: str) -> bool:
    """Type text into a window using SendInput keyboard events.

    Args:
        hwnd: Target window handle.
        text: Text string to type.

    Returns:
        True if the text was sent successfully.
    """
    # Ensure window is focused
    USER32.SetForegroundWindow(hwnd)
    time.sleep(0.05)  # Brief focus delay

    success = True
    for char in text:
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD

        # Key down (Unicode scan code)
        inp.u.ki.wScan = ord(char)
        inp.u.ki.dwFlags = KEYEVENTF_UNICODE
        if not _send_input(inp):
            success = False
            break

        # Key up
        inp.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        if not _send_input(inp):
            success = False
            break

        time.sleep(0.02)  # Typing cadence

    if success:
        logger.info("T2 typed '%s' into hwnd=%d", text[:40], hwnd)
    else:
        logger.error("T2 type_text failed for hwnd=%d", hwnd)

    return success


def post_message(hwnd: int, msg: str, text: Optional[str] = None,
                 wparam: int = 0, lparam: int = 0) -> bool:
    """Send a Windows message directly to a window.

    Args:
        hwnd: Target window handle.
        msg: Message name (e.g. "WM_SETTEXT", "WM_CHAR").
        text: Text data for WM_SETTEXT.
        wparam: WPARAM value.
        lparam: LPARAM value.

    Returns:
        True if the message was posted.
    """
    messages = {
        "WM_SETTEXT": WM_SETTEXT,
        "WM_CHAR": WM_CHAR,
        "WM_LBUTTONDOWN": WM_LBUTTONDOWN,
        "WM_LBUTTONUP": WM_LBUTTONUP,
        "WM_RBUTTONDOWN": WM_RBUTTONDOWN,
        "WM_RBUTTONUP": WM_RBUTTONUP,
        "WM_KEYDOWN": WM_KEYDOWN,
        "WM_KEYUP": WM_KEYUP,
    }

    msg_code = messages.get(msg)
    if msg_code is None:
        logger.error("Unknown message: %s", msg)
        return False

    if msg == "WM_SETTEXT" and text is not None:
        # WM_SETTEXT requires SendMessageW (not PostMessageW) with LPCWSTR
        # Use c_wchar_p for proper wide string marshaling
        result = USER32.SendMessageW(hwnd, WM_SETTEXT, 0, ctypes.c_wchar_p(text))
    else:
        # Pack client coordinates into lparam if provided
        result = USER32.PostMessageW(hwnd, msg_code, wparam, lparam)

    if result == 0:
        logger.error("PostMessage %s failed for hwnd=%d", msg, hwnd)
        return False

    logger.info("T2 PostMessage %s to hwnd=%d", msg, hwnd)
    return True


def double_click_at(hwnd: int, x: int, y: int,
                    client_coords: bool = False) -> bool:
    """Double-click at a specific coordinate.

    Args:
        hwnd: Target window handle.
        x, y: Coordinates.
        client_coords: If True, x/y are in client coordinates.

    Returns:
        True if both clicks succeeded.
    """
    if not click_at(hwnd, x, y, client_coords=client_coords):
        return False
    time.sleep(0.15)  # Double-click interval
    return click_at(hwnd, x, y, client_coords=client_coords)


def right_click_at(hwnd: int, x: int, y: int,
                   client_coords: bool = False) -> bool:
    """Right-click at a specific coordinate.

    Args:
        hwnd: Target window handle.
        x, y: Coordinates.
        client_coords: If True, x/y are in client coordinates.

    Returns:
        True if the right-click was sent successfully.
    """
    return click_at(hwnd, x, y, button="right", client_coords=client_coords)


def hover_at(hwnd: int, x: int, y: int,
             client_coords: bool = False, duration: float = 0.1) -> bool:
    """Move mouse to a position without clicking (hover).

    Useful for triggering tooltips, hover states, or focus changes.

    Args:
        hwnd: Target window handle.
        x, y: Coordinates.
        client_coords: If True, x/y are in client coordinates.
        duration: How long to hold the hover (seconds).

    Returns:
        True if the hover was sent successfully.
    """
    if client_coords:
        x, y = client_to_screen(hwnd, x, y)

    ax, ay = _absolute_coords(x, y)

    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = ax
    inp.u.mi.dy = ay
    inp.u.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
    if not _send_input(inp):
        return False

    time.sleep(duration)

    logger.info("T2 hover at (%d, %d) on hwnd=%d for %.2fs", x, y, hwnd, duration)
    return True


def drag(hwnd: int, x1: int, y1: int, x2: int, y2: int,
         button: str = "left", client_coords: bool = False,
         steps: int = 5, step_delay: float = 0.02) -> bool:
    """Drag from one point to another.

    Moves mouse to start, presses button, interpolates to end, releases.

    Args:
        hwnd: Target window handle.
        x1, y1: Start coordinates.
        x2, y2: End coordinates.
        button: "left" or "right" mouse button.
        client_coords: If True, x/y are in client coordinates.
        steps: Number of interpolation steps (smoother drag).
        step_delay: Delay between steps in seconds.

    Returns:
        True if the drag completed successfully.
    """
    if client_coords:
        x1, y1 = client_to_screen(hwnd, x1, y1)
        x2, y2 = client_to_screen(hwnd, x2, y2)

    if button == "left":
        down_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN
        up_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP
    else:
        down_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_RIGHTDOWN
        up_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_RIGHTUP

    # Move to start position
    ax1, ay1 = _absolute_coords(x1, y1)
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = ax1
    inp.u.mi.dy = ay1
    inp.u.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
    if not _send_input(inp):
        return False

    time.sleep(0.02)

    # Button down
    inp.u.mi.dwFlags = down_flags
    if not _send_input(inp):
        return False

    time.sleep(0.02)

    # Interpolate and move
    ax2, ay2 = _absolute_coords(x2, y2)
    for i in range(1, steps + 1):
        t = i / steps  # 0.0 to 1.0
        cx = int(ax1 + (ax2 - ax1) * t)
        cy = int(ay1 + (ay2 - ay1) * t)
        inp.u.mi.dx = cx
        inp.u.mi.dy = cy
        inp.u.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
        if not _send_input(inp):
            return False
        time.sleep(step_delay)

    # Button up
    inp.u.mi.dwFlags = up_flags
    if not _send_input(inp):
        return False

    logger.info("T2 drag (%d,%d) -> (%d,%d) on hwnd=%d", x1, y1, x2, y2, hwnd)
    return True


MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x0100
WHEEL_DELTA = 120


def scroll_at(hwnd: int, x: int, y: int,
              delta: int = 120, direction: str = "vertical",
              client_coords: bool = False) -> bool:
    """Scroll at a specific coordinate.

    Args:
        hwnd: Target window handle.
        x, y: Scroll center coordinates.
        delta: Scroll amount. Positive = up/right, negative = down/left.
               Default WHEEL_DELTA (120) = one scroll tick.
        direction: "vertical" or "horizontal".
        client_coords: If True, x/y are in client coordinates.

    Returns:
        True if the scroll was sent successfully.
    """
    if client_coords:
        x, y = client_to_screen(hwnd, x, y)

    ax, ay = _absolute_coords(x, y)

    # Move to the scroll target first
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = ax
    inp.u.mi.dy = ay
    inp.u.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
    if not _send_input(inp):
        return False

    time.sleep(0.02)

    # Send wheel event
    if direction == "horizontal":
        flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_HWHEEL
    else:
        flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_WHEEL

    inp.u.mi.dx = ax
    inp.u.mi.dy = ay
    inp.u.mi.mouseData = delta
    inp.u.mi.dwFlags = flags
    if not _send_input(inp):
        return False

    logger.info("T2 scroll %s delta=%d at (%d,%d) on hwnd=%d", direction, delta, x, y, hwnd)
    return True
