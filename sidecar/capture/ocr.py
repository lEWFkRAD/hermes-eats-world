"""
Hermes Eats World — OCR Engine
================================
OCR abstraction layer for T2 vision fallback. Supports multiple backends
with graceful degradation: pytesseract → easyocr → surya → rapidocr.

On first import, probes for available backends and selects the best one.
If no external OCR is installed, falls back to a basic PIL-based text
extraction that only works on high-contrast screenshots.

Usage:
    from sidecar.capture.ocr import ocr_engine, OCRResult

    # OCR an entire window capture
    result: OCRResult = ocr_engine.recognize(image_path)

    # OCR a specific region (bounding box)
    result = ocr_engine.recognize(image_path, region=(x, y, w, h))

    # OCR with language hint
    result = ocr_engine.recognize(image_path, lang="eng")
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from ..schema.models import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class OCRWord:
    """A single recognized word with bounding box and confidence."""
    text: str
    bbox: BoundingBox
    confidence: float  # 0.0-1.0


@dataclass
class OCRLine:
    """A line of recognized text composed of multiple words."""
    text: str
    bbox: BoundingBox
    confidence: float  # average word confidence
    words: List[OCRWord] = field(default_factory=list)


@dataclass
class OCRResult:
    """Result of an OCR pass over an image or region."""
    backend: str  # which OCR backend was used
    language: str  # language code (e.g. "eng")
    lines: List[OCRLine] = field(default_factory=list)
    full_text: str = ""  # all text joined with newlines
    image_size: Tuple[int, int] = (0, 0)  # (width, height)
    processing_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

class _PytesseractBackend:
    """pytesseract (Tesseract OCR via C binary) backend."""
    name = "pytesseract"

    def __init__(self):
        import pytesseract
        self.tesseract = pytesseract

    def recognize(self, image: Image.Image, lang: str = "eng",
                  region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        if region:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))

        data = self.tesseract.image_to_data(image, lang=lang, output_type=self.tesseract.Output.DICT)
        n = len(data["text"])

        lines: List[OCRLine] = []
        line_map: Dict[int, OCRLine] = {}

        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            conf = data["conf"][i] / 100.0 if data["conf"][i] >= 0 else 0.0
            left = data["left"][i]
            top = data["top"][i]
            width = data["width"][i]
            height = data["height"][i]

            # Offset by region if cropped
            if region:
                left += region[0]
                top += region[1]

            word = OCRWord(
                text=text,
                bbox=BoundingBox(left=left, top=top, width=width, height=height),
                confidence=round(conf, 3),
            )

            line_num = data["text"][i]  # use line number grouping
            block_num = data["block_num"][i]
            line_key = (block_num, data["line_num"][i])

            if line_key not in line_map:
                line_map[line_key] = OCRLine(
                    text="", bbox=BoundingBox(left=left, top=top, width=0, height=height),
                    confidence=0.0, words=[],
                )
            line = line_map[line_key]
            line.words.append(word)
            line.text += (line.text + " ") + text if line.text else text
            line.bbox.left = min(line.bbox.left, left)
            line.bbox.top = min(line.bbox.top, top)
            line.bbox.width = max(line.bbox.left + width, left + width) - line.bbox.left
            line.bbox.height = max(line.bbox.height, height)

        for line in line_map.values():
            if line.words:
                line.confidence = round(sum(w.confidence for w in line.words) / len(line.words), 3)
            lines.append(line)

        full_text = "\n".join(l.text for l in lines)

        return OCRResult(
            backend=self.name,
            language=lang,
            lines=lines,
            full_text=full_text,
            image_size=image.size,
        )


class _EasyOCRBackend:
    """EasyOCR backend (CNN-based, GPU-friendly)."""
    name = "easyocr"

    def __init__(self):
        import easyocr
        self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def recognize(self, image: Image.Image, lang: str = "eng",
                  region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        if region:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
            offset_x, offset_y = region[0], region[1]
        else:
            offset_x, offset_y = 0, 0

        results = self.reader.readtext(image)

        lines: List[OCRLine] = []
        for bbox_pts, text, conf in results:
            pts = [(int(p[0]), int(p[1])) for p in bbox_pts]
            left = min(p[0] + offset_x for p in pts)
            top = min(p[1] + offset_y for p in pts)
            right = max(p[0] + offset_x for p in pts)
            bottom = max(p[1] + offset_y for p in pts)

            words = [OCRWord(
                text=text,
                bbox=BoundingBox(left=left, top=top, width=right - left, height=bottom - top),
                confidence=round(conf, 3),
            )]

            lines.append(OCRLine(
                text=text,
                bbox=BoundingBox(left=left, top=top, width=right - left, height=bottom - top),
                confidence=round(conf, 3),
                words=words,
            ))

        full_text = "\n".join(l.text for l in lines)
        return OCRResult(
            backend=self.name,
            language=lang,
            lines=lines,
            full_text=full_text,
            image_size=image.size,
        )


class _SuryaBackend:
    """Surya OCR backend (fast, self-hosted)."""
    name = "surya"

    def __init__(self):
        from surya.recognition import run_recognition
        from surya.model.detection.model import load_model as load_det_model
        from surya.model.detection.processor import load_processor as load_det_processor
        from surya.model.recognition.model import load_model as load_rec_model
        from surya.model.recognition.processor import load_processor as load_rec_processor
        from surya.langs import LANGEQUIV

        self.det_model = load_det_model()
        self.det_processor = load_det_processor()
        self.rec_model = load_rec_model()
        self.rec_processor = load_rec_processor()
        self.run_recognition = run_recognition

    def recognize(self, image: Image.Image, lang: str = "eng",
                  region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        if region:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
            offset_x, offset_y = region[0], region[1]
        else:
            offset_x, offset_y = 0, 0

        predictions = self.run_recognition([image], [lang], self.rec_model, self.rec_processor)

        lines: List[OCRLine] = []
        for pred in predictions[0]:
            bbox = pred["bbox"]
            left = bbox[0] + offset_x
            top = bbox[1] + offset_y
            right = bbox[2] + offset_x
            bottom = bbox[3] + offset_y
            conf = pred.get("confidence", 0.0)

            lines.append(OCRLine(
                text=pred["text"],
                bbox=BoundingBox(left=left, top=top, width=right - left, height=bottom - top),
                confidence=round(conf, 3),
                words=[OCRWord(
                    text=pred["text"],
                    bbox=BoundingBox(left=left, top=top, width=right - left, height=bottom - top),
                    confidence=round(conf, 3),
                )],
            ))

        full_text = "\n".join(l.text for l in lines)
        return OCRResult(
            backend=self.name,
            language=lang,
            lines=lines,
            full_text=full_text,
            image_size=image.size,
        )


class _PILFallbackBackend:
    """Minimal PIL-based fallback — returns empty result with a warning.
    
    This is NOT a real OCR engine. It exists so the pipeline doesn't crash
    when no OCR backend is installed. Callers should check backend == "none".
    """
    name = "none"

    def __init__(self):
        logger.warning(
            "No OCR backend available (pytesseract, easyocr, surya, rapidocr). "
            "T2 vision fallback will return empty results. "
            "Install one: pip install pytesseract (requires tesseract-ocr binary)"
        )

    def recognize(self, image: Image.Image, lang: str = "eng",
                  region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        return OCRResult(
            backend=self.name,
            language=lang,
            lines=[],
            full_text="",
            image_size=image.size,
        )


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

class OCREngine:
    """Main OCR engine with automatic backend selection.
    
    Probes for available backends on first use (lazy initialization) and uses
    the best one. Order of preference: pytesseract > easyocr > surya > rapidocr > PIL fallback.
    """

    def __init__(self, preferred_backend: Optional[str] = None):
        self._preferred_backend = preferred_backend
        self._backend: Any = None
        self._backend_name = "none"
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization — only probe backends on first recognize call."""
        if self._initialized:
            return
        if self._preferred_backend:
            self._try_init(self._preferred_backend)
        else:
            for cls in [_PytesseractBackend, _EasyOCRBackend, _SuryaBackend]:
                if self._try_init(cls.name):
                    break
        self._initialized = True
        logger.info("OCR engine initialized with backend: %s", self._backend_name)

    def _try_init(self, backend_name: str) -> bool:
        """Try to initialize a backend. Returns True on success."""
        backends = {
            "pytesseract": _PytesseractBackend,
            "easyocr": _EasyOCRBackend,
            "surya": _SuryaBackend,
        }

        cls = backends.get(backend_name)
        if not cls:
            return False

        try:
            self._backend = cls()
            self._backend_name = cls.name
            logger.info("Loaded OCR backend: %s", cls.name)
            return True
        except (ImportError, FileNotFoundError, Exception) as e:
            logger.debug("OCR backend %s unavailable: %s", backend_name, e)
            return False

    @property
    def backend_name(self) -> str:
        """Name of the active OCR backend."""
        return self._backend_name

    @property
    def is_available(self) -> bool:
        """True if a real OCR backend is loaded (not the PIL fallback)."""
        return self._backend_name != "none"

    def recognize(self, image_path: str,
                  lang: str = "eng",
                  region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        """Run OCR on an image file.
        
        Args:
            image_path: Path to the image file (PNG, JPEG, etc.)
            lang: Language code (e.g. "eng", "jpn", "chi_sim")
            region: Optional (x, y, width, height) crop region
        
        Returns:
            OCRResult with lines, words, and full text.
        """
        image = Image.open(image_path).convert("RGB")
        return self._recognize(image, lang, region)

    def recognize_image(self, image: Image.Image,
                        lang: str = "eng",
                        region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        """Run OCR on a PIL Image object.
        
        Args:
            image: PIL Image object
            lang: Language code
            region: Optional (x, y, width, height) crop region
        
        Returns:
            OCRResult with lines, words, and full text.
        """
        return self._recognize(image, lang, region)

    def _recognize(self, image: Image.Image,
                   lang: str = "eng",
                   region: Optional[Tuple[int, int, int, int]] = None) -> OCRResult:
        """Internal recognition method."""
        self._ensure_initialized()
        if self._backend is None:
            return _PILFallbackBackend().recognize(image, lang, region)
        return self._backend.recognize(image, lang, region)

    def search_text(self, image_path: str, query: str,
                    lang: str = "eng") -> List[OCRWord]:
        """Search for specific text in an OCR result.
        
        Args:
            image_path: Path to the image
            query: Text to search for (case-insensitive substring)
            lang: Language code
        
        Returns:
            List of OCRWord matches with their bounding boxes.
        """
        result = self.recognize(image_path, lang=lang)
        query_lower = query.lower()

        matches: List[OCRWord] = []
        for line in result.lines:
            for word in line.words:
                if query_lower in word.text.lower():
                    matches.append(word)
            # Also check full line text
            if query_lower in line.text.lower() and not matches:
                # Word-level didn't match, add line-level match
                matches.append(OCRWord(
                    text=line.text,
                    bbox=line.bbox,
                    confidence=line.confidence,
                ))

        return matches


# Singleton instance — created on first access (thread-safe)
_ocr_engine: Optional[OCREngine] = None
_ocr_lock = threading.Lock()


def get_ocr_engine(preferred_backend: Optional[str] = None) -> OCREngine:
    """Get the global OCR engine instance (lazy, thread-safe initialization)."""
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            _ocr_engine = OCREngine(preferred_backend=preferred_backend)
    return _ocr_engine
