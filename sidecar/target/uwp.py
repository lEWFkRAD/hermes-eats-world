"""
Hermes Eats World — UWP / ApplicationFrameWindow Child Drilling
===============================================================
Modern UWP/WinUI apps wrap their real content inside ApplicationFrameWindow
child windows. This module drills into the frame to find the actual content
window with the richest UIA tree.
"""

import logging
from typing import Optional

import uiautomation

logger = logging.getLogger(__name__)

# Class names that indicate a hosting frame
FRAME_CLASSES = {
    "ApplicationFrameWindow",       # UWP apps
    "Windows.UI.Core.CoreWindow",   # WinUI/UWP core window
    "DesktopWindowXamlSource",       # Win32+UWP hybrid
}

# Content window class hints
CONTENT_CLASSES = {
    "DesktopChildSiteBridge",       # WinUI 3 content
    "Windows.UI.Core.CoreWindow",   # UWP content
    "IME",                          # IME host
}


def is_frame_window(class_name: str) -> bool:
    """Check if a window class name indicates a hosting frame."""
    return class_name in FRAME_CLASSES


def drill_frame(frame_control) -> Optional[uiautomation.Control]:
    """Drill into an ApplicationFrameWindow to find the real content window.
    
    Strategy:
    1. Get children of the frame
    2. Look for known content window classes
    3. If none found, pick the child with the largest bounding rect
    4. Return the content window, or None if drilling fails
    """
    try:
        children = frame_control.GetChildren()
        if not children:
            logger.warning("Frame window has no children — cannot drill")
            return None

        # Priority 1: Known content window classes
        for child in children:
            try:
                cls = child.ClassName or ""
                if cls in CONTENT_CLASSES:
                    logger.info("Found content window: %s", cls)
                    return child
            except Exception:
                continue

        # Priority 2: Largest bounding rect (likely the content)
        best_child = None
        best_area = 0
        for child in children:
            try:
                rect = child.BoundingRectangle
                area = rect.width() * rect.height()
                if area > best_area:
                    best_area = area
                    best_child = child
            except Exception:
                continue

        if best_child and best_area > 0:
            logger.info("Selected largest child window (area=%d)", best_area)
            return best_child

        logger.warning("Could not find suitable content window in frame")
        return None

    except Exception as e:
        logger.error("Frame drilling failed: %s", e)
        return None
