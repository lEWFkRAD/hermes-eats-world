"""
Hermes Eats World — UIA Tree Walker
====================================
Walk the UIA accessibility tree and produce structured Element models.
Includes: stable element IDs, depth capping, single-pass summarization,
and truncation tracking.
"""

import hashlib
import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ..schema.models import BoundingBox, Element, TreeSummary

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_DEPTH = 3
HARD_MAX_DEPTH = 50
DEFAULT_MAX_ELEMENTS = 5000
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_NAME_LEN = 200


def make_element_id(element, path: str = "0") -> str:
    """Generate a stable composite ID for cross-snapshot correlation.

    Hash of stable-ish UIA identity fields plus the element's ancestry path.
    """
    try:
        name = str(element.Name) if element.Name else ""
        ctrl_type = str(element.ControlTypeName)
        automation_id = str(element.AutomationId) if element.AutomationId else ""
        class_name = str(element.ClassName) if element.ClassName else ""
        raw = f"{path}|{automation_id}|{class_name}|{ctrl_type}|{name}"
        return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    except Exception as e:
        logger.debug("Failed to make element ID: %s", e)
        return hashlib.md5(path.encode()).hexdigest()[:12]


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
    *,
    include_raw_values: bool = False,
    max_elements: int = DEFAULT_MAX_ELEMENTS,
    deadline: Optional[float] = None,
    path: str = "0",
    _counter: Optional[List[int]] = None,
) -> Tuple[Element, bool]:
    """Convert a UIA element to an Element model with children.

    Returns (Element, truncated) where truncated is True if we stopped
    recursing due to the depth limit.
    """
    truncated = False
    if _counter is None:
        _counter = [0]
    if deadline is None:
        deadline = time.monotonic() + DEFAULT_TIMEOUT_SECONDS
    if time.monotonic() >= deadline:
        raise TimeoutError("UIA tree walk exceeded its total time limit")
    if _counter[0] >= max_elements:
        raise RuntimeError(f"UIA tree walk exceeded {max_elements} elements")
    _counter[0] += 1

    # Patterns are control-specific. Reusing the root control's patterns for every
    # descendant makes summaries and action planning materially incorrect.
    if from_patterns is None:
        from .patterns import get_control_patterns

        from_patterns = get_control_patterns(element, include_raw_values=include_raw_values)

    # Build element dict
    elem = Element(
        id=make_element_id(element, path),
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
                for index, child in enumerate(children):
                    child_elem, child_truncated = element_to_dict(
                        child,
                        depth + 1,
                        max_depth,
                        include_raw_values=include_raw_values,
                        max_elements=max_elements,
                        deadline=deadline,
                        path=f"{path}.{index}",
                        _counter=_counter,
                    )
                    elem.children.append(child_elem)
                    if child_truncated:
                        truncated = True
        except (RuntimeError, TimeoutError):
            raise
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
