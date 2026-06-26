"""
Hermes Eats World — UIA Tree Walker
====================================
Walk the UIA accessibility tree and produce structured Element models.
Includes: stable element IDs, depth capping, single-pass summarization,
and truncation tracking.
"""

import hashlib
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import uiautomation

from ..schema.models import BoundingBox, Element, TreeSummary

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_DEPTH = 3
HARD_MAX_DEPTH = 500
MAX_NAME_LEN = 200


def make_element_id(element) -> str:
    """Generate a stable composite ID for cross-snapshot correlation.
    
    Hash of: name + control_type + bounding_rect.
    """
    try:
        name = str(element.Name) if element.Name else ""
        ctrl_type = str(element.ControlTypeName)
        rect = element.BoundingRectangle
        rect_str = f"{rect.left},{rect.top},{rect.width()},{rect.height()}"
        raw = f"{name}|{ctrl_type}|{rect_str}"
        return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    except Exception as e:
        logger.debug("Failed to make element ID: %s", e)
        return hashlib.md5(str(id(element)).encode()).hexdigest()[:12]


def _truncate(s: str, max_len: int = MAX_NAME_LEN) -> str:
    """Truncate long strings and append indicator."""
    if len(s) > max_len:
        return s[:max_len] + "... [truncated]"
    return s


def _get_bounding_rect(element) -> Optional[BoundingBox]:
    """Extract bounding box from a UIA element, or None."""
    try:
        rect = element.BoundingRectangle
        return BoundingBox(
            left=rect.left,
            top=rect.top,
            width=rect.width(),
            height=rect.height(),
        )
    except Exception as e:
        logger.debug("Failed to get bounding rect: %s", e)
        return None


def element_to_dict(
    element,
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_DEPTH,
    from_patterns: Optional[Dict[str, Any]] = None,
) -> Tuple[Element, bool]:
    """Convert a UIA element to an Element model with children.
    
    Returns (Element, truncated) where truncated is True if we stopped
    recursing due to the depth limit.
    """
    truncated = False

    # Build element dict
    elem = Element(
        id=make_element_id(element),
        control_type=str(element.ControlTypeName),
        localized_type=str(element.LocalizedControlType),
        name=_truncate(str(element.Name) if element.Name else ""),
        automation_id=_truncate(str(element.AutomationId) if element.AutomationId else ""),
        class_name=str(element.ClassName) if element.ClassName else "",
        hwnd=element.NativeWindowHandle or None,
        is_enabled=element.IsEnabled,
        is_offscreen=element.IsOffscreen,
        bounding_box=_get_bounding_rect(element),
        depth=depth,
        patterns=from_patterns,
    )

    # Recurse into children if depth allows
    if depth < max_depth:
        try:
            children = element.GetChildren()
            if children:
                for child in children:
                    child_elem, child_truncated = element_to_dict(
                        child, depth + 1, max_depth, from_patterns
                    )
                    elem.children.append(child_elem)
                    if child_truncated:
                        truncated = True
        except Exception as e:
            logger.debug("Failed to get children at depth %d: %s", depth, e)
    else:
        truncated = True

    if truncated:
        elem.truncated = True

    return elem, truncated


def summarize_tree(root_element: Element) -> TreeSummary:
    """Single-pass walk of an Element tree that computes aggregate statistics.
    
    Counts elements, max depth, control type distribution, and pattern
    diversity in a single traversal. Operates on the Element model (not
    raw UIA controls) to avoid redundant COM calls.
    """
    total = 0
    max_depth = 0
    control_types: Counter = Counter()
    patterns: Counter = Counter()

    stack: list = [root_element]

    while stack:
        elem = stack.pop()
        total += 1
        max_depth = max(max_depth, elem.depth)

        control_types[elem.control_type] += 1

        for pat_name in elem.patterns:
            patterns[pat_name] += 1

        for child in elem.children:
            stack.append(child)

    return TreeSummary(
        total_elements=total,
        max_depth=max_depth,
        control_types=dict(control_types.most_common()),
        control_patterns=dict(patterns.most_common()),
    )
