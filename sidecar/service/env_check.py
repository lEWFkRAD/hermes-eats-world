"""
Hermes Eats World — Windows Environment Validation
===================================================
Runs at startup to validate the environment and provide clear error messages
instead of obscure COM failures. Covers:
- Platform check (Windows only)
- DPI awareness detection
- Elevation/integrity level
- Session ID (Session 0 service context check)
- UIA availability
"""

import ctypes
import logging
import platform
import sys
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EnvCheckResult:
    """Result of environment validation."""
    passed: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return len(self.errors) == 0

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        logger.warning(f"ENV WARNING: {msg}")

    def add_error(self, msg: str):
        self.passed = False
        self.errors.append(msg)
        logger.error(f"ENV ERROR: {msg}")

    def add_info(self, key: str, value):
        self.info[key] = value

    def report(self) -> str:
        lines = ["\n=== Hermes Eats World — Environment Check ===\n"]
        for k, v in self.info.items():
            lines.append(f"  {k}: {v}")
        if self.warnings:
            lines.append("\n  WARNINGS:")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")
        if self.errors:
            lines.append("\n  ERRORS:")
            for e in self.errors:
                lines.append(f"    ✖ {e}")
        lines.append(f"\n  Result: {'✅ PASS' if self.is_ok else '❌ FAIL'}")
        lines.append("")
        return "\n".join(lines)


def check_environment() -> EnvCheckResult:
    """Run all environment checks. Returns result with warnings/errors."""
    result = EnvCheckResult()

    # 1. Platform check
    os_name = platform.system()
    result.add_info("Platform", os_name)
    result.add_info("Python", sys.version.split()[0])
    if os_name != "Windows":
        result.add_error(
            f"Running on {os_name} — Hermes Eats World requires Windows. "
            f"UIA COM calls will fail with obscure errors."
        )
        return result  # No point continuing

    # 2. Check UIA availability
    try:
        import uiautomation
        result.add_info("uiautomation", "available")
    except ImportError:
        result.add_error("uiautomation module not installed. Run: pip install uiautomation")
        return result

    # 3. DPI awareness
    dpi_awareness = _get_dpi_awareness()
    result.add_info("DPI awareness", dpi_awareness)
    if dpi_awareness == "Unaware":
        result.add_warning(
            "Process is DPI-unaware. Screenshot coordinates may not align with UIA "
            "element positions on high-DPI displays. Call set_dpi_awareness() at startup."
        )

    # 4. Elevation check
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        result.add_info("Elevated", is_admin)
        if not is_admin:
            result.add_warning(
                "Not running as Administrator. Some elevated windows (e.g. Task Manager, "
                "UAC dialogs) may have 0 elements due to UIPI restrictions."
            )
    except Exception as e:
        result.add_warning(f"Could not check elevation: {e}")

    # 5. Session check
    try:
        session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        result.add_info("Session ID", session_id)
        if session_id == 0:
            result.add_warning(
                "Running in Session 0 (service context). No interactive windows will "
                "be visible. Run in an interactive session instead."
            )
    except Exception as e:
        result.add_warning(f"Could not check session: {e}")

    # 6. Monitor DPI info
    try:
        monitors = _get_monitor_dpi_info()
        result.add_info("Monitors", monitors)
    except Exception as e:
        result.add_warning(f"Could not get monitor DPI info: {e}")

    return result


def set_dpi_awareness():
    """Set process to per-monitor v2 DPI awareness.
    
    Must be called early in the process, before any windows are created.
    Returns True if successful, False otherwise.
    """
    try:
        # Windows 10 1703+ (RS2)
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = 0x01200000
        awareness_v2 = ctypes.c_void_p(0x01200000).value
        result = ctypes.windll.shcore.SetProcessDpiAwarenessContext(awareness_v2)
        if result != 0:
            logger.info("Set DPI awareness to PER_MONITOR_AWARE_V2")
            return True
    except AttributeError:
        pass  # SetProcessDpiAwarenessContext not available (pre-RS2)
    except Exception as e:
        logger.debug("SetProcessDpiAwarenessContext failed: %s", e)

    try:
        # Fallback: Windows 8.1+
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        result = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        # 0 = success, 1 = already set (also fine)
        if result in (0, 1):
            logger.debug("DPI awareness set to per-monitor (result=%d)", result)
            return True
    except AttributeError:
        pass
    except Exception as e:
        logger.debug("SetProcessDpiAwareness failed: %s", e)

    logger.warning("Could not set DPI awareness — screenshots may be misaligned on high-DPI displays")
    return False


# Module-level DPI awareness cache (doesn't change at runtime)
_dpi_awareness_cache: Optional[str] = None


def _get_dpi_awareness() -> str:
    """Get current DPI awareness level as a human-readable string.
    Cached at module level since it doesn't change at runtime."""
    global _dpi_awareness_cache
    if _dpi_awareness_cache is not None:
        return _dpi_awareness_cache

    try:
        buf = ctypes.c_ulong()
        result = ctypes.windll.shcore.GetProcessDpiAwareness(
            ctypes.c_void_p(ctypes.windll.kernel32.GetCurrentProcess()),
            ctypes.byref(buf),
        )
        if result == 0:
            # 0 = DPI_UNAWARE, 1 = SYSTEM_DPI_AWARE, 2 = PER_MONITOR_DPI_AWARE
            awareness_map = {0: "Unaware", 1: "System-aware", 2: "Per-monitor"}
            _dpi_awareness_cache = awareness_map.get(buf.value, f"Unknown ({buf.value})")
            return _dpi_awareness_cache
    except Exception:
        pass
    _dpi_awareness_cache = "Unknown"
    return _dpi_awareness_cache


def _get_monitor_dpi_info() -> str:
    """Get DPI info for all monitors."""
    try:
        import uiautomation
        desktop = uiautomation.WindowControl(searchDepth=1, Name="Program Manager")
        if not desktop.Exists(0, 0):
            return "unable to enumerate"
        
        # Get primary monitor DPI
        hdc = ctypes.windll.user32.GetDC(0)
        dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        
        scale = dpi_x / 96.0
        return f"{dpi_x} DPI ({scale:.1%} scale)"
    except Exception as e:
        return f"error: {e}"


def get_window_dpi(hwnd: int) -> int:
    """Get the DPI for a specific window. Returns dots per inch."""
    try:
        return ctypes.windll.shcore.GetDpiForWindow(hwnd)
    except Exception:
        return 96  # Default 100%


def logical_to_device(hwnd: int, left: int, top: int, width: int, height: int):
    """Convert UIA coordinates to device (pixel) coordinates.
    
    IMPORTANT: When the process is per-monitor DPI-aware, UIA already returns
    device-pixel coordinates, so no scaling is needed. Only apply scaling
    when the process is DPI-unaware (UIA returns logical coords).
    
    Uses GetDpiForWindow to get the target window's DPI scale factor.
    """
    # When per-monitor DPI-aware, UIA returns device coordinates directly.
    # No conversion needed.
    awareness = _get_dpi_awareness()
    if awareness in ("Per-monitor", "System-aware"):
        return left, top, width, height
    
    # DPI-unaware: UIA returns logical coordinates, scale to device pixels
    dpi = get_window_dpi(hwnd)
    scale = dpi / 96.0
    if scale == 1.0:
        return left, top, width, height
    
    return (
        int(left * scale),
        int(top * scale),
        int(width * scale),
        int(height * scale),
    )
