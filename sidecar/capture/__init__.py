"""Hermes Eats World — Capture module.

Provides screenshot capture (mss), OCR fallback (pytesseract/easyocr/surya),
and template matching for T2 vision-based perception.
"""

from .ocr import (
    OCRResult,
    OCRWord,
    OCRLine,
    OCREngine,
    get_ocr_engine,
)
from .match import (
    TemplateMatch,
    template_match,
    template_match_image,
    find_text_region,
)
from .screenshot import capture_element, capture_window

__all__ = [
    # Screenshot capture
    "capture_element",
    "capture_window",
    # OCR
    "OCRResult",
    "OCRWord",
    "OCRLine",
    "OCREngine",
    "get_ocr_engine",
    # Template matching
    "TemplateMatch",
    "template_match",
    "template_match_image",
    "find_text_region",
]
