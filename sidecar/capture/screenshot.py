"""
Hermes Eats World — Screenshot Capture
=======================================
Capture window screenshots using mss, with DPI-aware coordinate conversion.
Outputs PNG files with timestamped names in the project directory.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

import mss
import mss.tools
from PIL import Image

from ..schema.models import BoundingBox
from ..service.env_check import logical_to_device

logger = logging.getLogger(__name__)


def capture_window(
    bounding_box: BoundingBox,
    hwnd: Optional[int] = None,
    output_dir: str = ".",
) -> Optional[str]:
    """Capture a screenshot of a window's bounding box.
    
    Args:
        bounding_box: The window's UIA bounding rectangle.
        hwnd: Optional HWND for DPI coordinate conversion.
        output_dir: Directory to save the PNG file.
    
    Returns:
        Path to the saved PNG, or None on failure.
    """
    # Convert logical → device coordinates
    if hwnd and hwnd != 0:
        left, top, width, height = logical_to_device(
            hwnd,
            bounding_box.left,
            bounding_box.top,
            bounding_box.width,
            bounding_box.height,
        )
    else:
        left = bounding_box.left
        top = bounding_box.top
        width = bounding_box.width
        height = bounding_box.height

    monitor = {
        "top": max(0, top),
        "left": max(0, left),
        "width": width,
        "height": height,
    }

    # Ensure output dir exists
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) / f"capture_{timestamp}.png"

    try:
        with mss.MSS() as sct:
            sct_img = sct.grab(monitor)
        
        # Convert BGRA → RGB
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.save(str(output_path), "PNG")
        logger.info("Saved screenshot to %s", output_path)
        return str(output_path)
    
    except Exception as e:
        logger.error("Screenshot capture failed: %s", e)
        return None


def capture_element(
    element,
    output_dir: str = ".",
) -> Optional[str]:
    """Capture a screenshot of a specific UIA element's bounding box.
    
    Args:
        element: uiautomation element to capture.
        output_dir: Directory to save the PNG file.
    
    Returns:
        Path to the saved PNG, or None on failure.
    """
    try:
        rect = element.BoundingRectangle
        bbox = BoundingBox(
            left=rect.left,
            top=rect.top,
            width=rect.width(),
            height=rect.height(),
        )
        hwnd = element.NativeWindowHandle or None
        return capture_window(bbox, hwnd, output_dir)
    except Exception as e:
        logger.error("Element screenshot capture failed: %s", e)
        return None
