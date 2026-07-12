"""
Hermes Eats World — Control Pattern Extraction
===============================================
Extract supported UIA control patterns from a uiautomation element.
Returns a dict of pattern name → pattern state dict.
"""

import logging
from typing import Any, Dict

import uiautomation

logger = logging.getLogger(__name__)

# Map pattern names to their PatternId integer values
PATTERN_MAP = {
    "invoke": uiautomation.PatternId.InvokePattern,
    "value": uiautomation.PatternId.ValuePattern,
    "toggle": uiautomation.PatternId.TogglePattern,
    "selection": uiautomation.PatternId.SelectionPattern,
    "expandCollapse": uiautomation.PatternId.ExpandCollapsePattern,
    "scroll": uiautomation.PatternId.ScrollPattern,
    "transform": uiautomation.PatternId.TransformPattern,
    "window": uiautomation.PatternId.WindowPattern,
    "selectionItem": uiautomation.PatternId.SelectionItemPattern,
    "grid": uiautomation.PatternId.GridPattern,
    "text": uiautomation.PatternId.TextPattern,
    "scrollItem": uiautomation.PatternId.ScrollItemPattern,
    "dock": uiautomation.PatternId.DockPattern,
}


def get_control_patterns(element, *, include_raw_values: bool = False) -> Dict[str, Dict[str, Any]]:
    """Extract all supported control patterns from a UIA element.

    Attempts to GetPattern for each pattern type. Failed probes are
    silently skipped (logged at debug level).

    Returns a dict mapping pattern names to their state dicts.
    """
    patterns: Dict[str, Dict[str, Any]] = {}
    failures = 0

    for name, pattern_id in PATTERN_MAP.items():
        try:
            pattern_obj = element.GetPattern(pattern_id)
            if pattern_obj is not None:
                patterns[name] = _probe_pattern(
                    name, pattern_obj, include_raw_values=include_raw_values
                )
        except Exception as e:
            failures += 1
            logger.debug("Failed to probe pattern %s: %s", name, e)

    if failures > 0:
        logger.debug("Pattern extraction: %d/%d probes failed", failures, len(PATTERN_MAP))

    return patterns


def _probe_pattern(name: str, pattern_obj, *, include_raw_values: bool = False) -> Dict[str, Any]:
    """Probe a single pattern and return its state dict."""
    state: Dict[str, Any] = {"supported": True}

    if name == "value":
        try:
            value = str(pattern_obj.Value)
            state["value"] = value if include_raw_values else "[REDACTED]"
            state["value_length"] = len(value)
            state["readonly"] = pattern_obj.ReadOnly
        except Exception as e:
            logger.debug("Value pattern error: %s", e)

    elif name == "toggle":
        try:
            state["state"] = int(pattern_obj.ToggleState)
        except Exception as e:
            logger.debug("Toggle pattern error: %s", e)

    elif name == "expandCollapse":
        try:
            state["state"] = int(pattern_obj.ExpandCollapseState)
        except Exception as e:
            logger.debug("ExpandCollapse pattern error: %s", e)

    elif name == "scroll":
        try:
            state["horizontally_scrollable"] = pattern_obj.HorizontallyScrollable
            state["vertically_scrollable"] = pattern_obj.VerticallyScrollable
        except Exception as e:
            logger.debug("Scroll pattern error: %s", e)

    elif name == "transform":
        try:
            state["can_move"] = pattern_obj.CanMove
            state["can_resize"] = pattern_obj.CanResize
            state["can_rotate"] = pattern_obj.CanRotate
        except Exception as e:
            logger.debug("Transform pattern error: %s", e)

    elif name == "window":
        try:
            state["can_maximize"] = pattern_obj.CanMaximize
            state["can_minimize"] = pattern_obj.CanMinimize
            state["is_modal"] = pattern_obj.IsModal
            state["is_topmost"] = pattern_obj.IsTopmost
            state["window_state"] = int(pattern_obj.WindowVisualState)
        except Exception as e:
            logger.debug("Window pattern error: %s", e)

    elif name == "selectionItem":
        try:
            state["is_selected"] = pattern_obj.IsSelected
        except Exception as e:
            logger.debug("SelectionItem pattern error: %s", e)

    elif name == "grid":
        try:
            state["row_count"] = pattern_obj.RowCount
            state["column_count"] = pattern_obj.ColumnCount
        except Exception as e:
            logger.debug("Grid pattern error: %s", e)

    elif name == "dock":
        try:
            state["dock"] = int(pattern_obj.Dock)
        except Exception as e:
            logger.debug("Dock pattern error: %s", e)

    return state
