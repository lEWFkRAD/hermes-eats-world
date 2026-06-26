"""
Hermes Eats World — Template Matching
======================================
Template matching for T2 vision fallback. Locates UI elements by visual
similarity using PIL-based normalized cross-correlation.

Usage:
    from sidecar.capture.match import template_match

    # Find a template in a screenshot
    matches = template_match(screenshot_path, template_path, threshold=0.8)

    # Find with multiple templates (for finding buttons, icons, etc.)
    matches = template_match(screenshot_path, [t1_path, t2_path], threshold=0.75)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from ..schema.models import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    """A single template match result."""
    template_path: str  # path of the matched template
    bbox: BoundingBox   # location in the target image
    confidence: float   # 0.0-1.0 match score
    offset: Tuple[int, int]  # (x, y) top-left corner


def template_match(
    target_path: str,
    template_path: str,
    threshold: float = 0.8,
    max_matches: int = 1,
) -> List[TemplateMatch]:
    """Find a template image inside a target image.

    Uses normalized cross-correlation via PIL + numpy.

    Args:
        target_path: Path to the full screenshot/window capture.
        template_path: Path to the template (small UI region to find).
        threshold: Minimum correlation score (0.0-1.0).
        max_matches: Maximum number of matches to return.

    Returns:
        List of TemplateMatch sorted by confidence (highest first).
    """
    target = Image.open(target_path).convert("L")  # grayscale
    template = Image.open(template_path).convert("L")

    return _match_images(target, template, template_path, threshold, max_matches)


def template_match_image(
    target: Image.Image,
    template: Image.Image,
    threshold: float = 0.8,
    max_matches: int = 1,
    template_label: str = "template",
) -> List[TemplateMatch]:
    """Find a template image inside a target image (PIL objects).

    Args:
        target: Full screenshot as PIL Image.
        template: Small UI region to find.
        threshold: Minimum correlation score.
        max_matches: Maximum number of matches to return.
        template_label: Label for the template (for result).

    Returns:
        List of TemplateMatch sorted by confidence.
    """
    target_gray = target.convert("L") if target.mode != "L" else target
    template_gray = template.convert("L") if template.mode != "L" else template

    return _match_images(target_gray, template_gray, template_label, threshold, max_matches)


def _match_images(
    target: Image.Image,
    template: Image.Image,
    template_label: str,
    threshold: float,
    max_matches: int,
) -> List[TemplateMatch]:
    """Core template matching using sliding window normalized correlation."""
    target_arr = np.array(target, dtype=np.float64)
    template_arr = np.array(template, dtype=np.float64)

    th, tw = template_arr.shape
    th_img, tw_img = target_arr.shape

    # Template must be smaller than target
    if tw >= tw_img or th >= th_img:
        logger.warning(
            "Template (%dx%d) is not smaller than target (%dx%d) — skipping",
            tw, th, tw_img, th_img,
        )
        return []

    # Normalize template
    t_mean = template_arr.mean()
    t_std = template_arr.std()
    if t_std < 1e-6:
        logger.warning("Template has near-zero variance — skipping")
        return []
    template_norm = (template_arr - t_mean) / (t_std * th * tw)

    # Sliding window normalized cross-correlation
    # For performance, we use a block-based approach
    results: List[Tuple[int, int, float]] = []

    # Step size — higher = faster but less precise
    step = max(1, min(tw, th) // 4)

    for y in range(0, th_img - th + 1, step):
        for x in range(0, tw_img - tw + 1, step):
            block = target_arr[y:y + th, x:x + tw]

            b_mean = block.mean()
            b_std = block.std()
            if b_std < 1e-6:
                continue

            # Normalized correlation
            correlation = np.sum(
                ((block - b_mean) / (b_std * th * tw)) * template_norm
            )

            if correlation >= threshold:
                # Refine with sub-pixel search around the match
                refined_x, refined_y, refined_score = _refine_match(
                    target_arr, template_arr, x, y, correlation
                )
                results.append((refined_x, refined_y, refined_score))

    # Remove duplicates (non-maximum suppression)
    results = _non_max_suppression(results, tw, th)

    # Sort by confidence and limit
    results.sort(key=lambda r: r[2], reverse=True)
    results = results[:max_matches]

    return [
        TemplateMatch(
            template_path=template_label,
            bbox=BoundingBox(left=x, top=y, width=tw, height=th),
            confidence=round(score, 4),
            offset=(x, y),
        )
        for x, y, score in results
    ]


def _refine_match(
    target: np.ndarray,
    template: np.ndarray,
    x: int,
    y: int,
    initial_score: float,
) -> Tuple[int, int, float]:
    """Refine a coarse match with sub-step search."""
    th, tw = template.shape
    th_img, tw_img = target.shape

    best_x, best_y = x, y
    best_score = initial_score

    # Search a small neighborhood with step=1
    margin = max(1, min(tw, th) // 8)
    for dy in range(-margin, margin + 1):
        for dx in range(-margin, margin + 1):
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx + tw > tw_img or ny + th > th_img:
                continue

            block = target[ny:ny + th, nx:nx + tw]
            b_mean = block.mean()
            b_std = block.std()
            if b_std < 1e-6:
                continue

            t_mean = template.mean()
            t_std = template.std()
            correlation = np.sum(
                ((block - b_mean) / (b_std * th * tw)) *
                ((template - t_mean) / (t_std * th * tw))
            )

            if correlation > best_score:
                best_score = correlation
                best_x, best_y = nx, ny

    return best_x, best_y, best_score


def _non_max_suppression(
    matches: List[Tuple[int, int, float]],
    tw: int,
    th: int,
) -> List[Tuple[int, int, float]]:
    """Remove overlapping matches, keeping the highest-confidence one."""
    if not matches:
        return []

    # Sort by confidence descending
    matches.sort(key=lambda m: m[2], reverse=True)

    kept: List[Tuple[int, int, float]] = []
    overlap_threshold = 0.5  # IoU threshold

    for x, y, score in matches:
        is_new = True
        for kx, ky, _ in kept:
            # Calculate IoU
            ix1 = max(x, kx)
            iy1 = max(y, ky)
            ix2 = min(x + tw, kx + tw)
            iy2 = min(y + th, ky + th)

            if ix2 > ix1 and iy2 > iy1:
                intersection = (ix2 - ix1) * (iy2 - iy1)
                union = tw * th * 2 - intersection
                iou = intersection / union if union > 0 else 0

                if iou > overlap_threshold:
                    is_new = False
                    break

        if is_new:
            kept.append((x, y, score))

    return kept


def find_text_region(
    target_path: str,
    query: str,
    ocr_result,  # OCRResult from ocr.py
    iou_threshold: float = 0.5,
) -> List[TemplateMatch]:
    """Find the visual region of a text query using OCR results.

    Uses OCR bounding boxes directly — no template matching needed.
    Useful for locating labels, button text, etc.

    Args:
        target_path: Path to the screenshot (for reference).
        query: Text to find (case-insensitive substring).
        ocr_result: OCRResult from the ocr_engine.
        iou_threshold: Not used (kept for API consistency).

    Returns:
        List of TemplateMatch with locations of matching text.
    """
    query_lower = query.lower()
    matches: List[TemplateMatch] = []

    for line in ocr_result.lines:
        for word in line.words:
            if query_lower in word.text.lower():
                matches.append(TemplateMatch(
                    template_path=f"text:{query}",
                    bbox=word.bbox,
                    confidence=word.confidence,
                    offset=(word.bbox.left, word.bbox.top),
                ))

        # Line-level fallback
        if query_lower in line.text.lower() and not any(
            m.template_path == f"text:{query}" for m in matches
        ):
            matches.append(TemplateMatch(
                template_path=f"text:{query}",
                bbox=line.bbox,
                confidence=line.confidence,
                offset=(line.bbox.left, line.bbox.top),
            ))

    # Deduplicate by location
    seen = set()
    unique: List[TemplateMatch] = []
    for m in matches:
        key = (m.bbox.left, m.bbox.top)
        if key not in seen:
            seen.add(key)
            unique.append(m)

    unique.sort(key=lambda m: m.confidence, reverse=True)
    return unique
