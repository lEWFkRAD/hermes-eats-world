"""
Hermes Eats World — T1 Actions (Direct UIA Control Pattern Invocation)
======================================================================
Invoke UIA control patterns directly against elements. Deterministic,
no coordinate guessing.

Usage:
    from sidecar.action import invoke_pattern, set_value, toggle_state

    # Click/invoke a button
    invoke_pattern(element)

    # Set a text field value
    set_value(element, "new text")

    # Toggle a checkbox
    toggle_state(element, True)
"""

import logging
from typing import Any, Optional

import uiautomation as auto

logger = logging.getLogger(__name__)


class ActionError(Exception):
    """Raised when a T1 action fails."""
    pass


def invoke_pattern(element: Any, timeout: float = 5.0) -> bool:
    """Invoke the InvokePattern on an element (e.g. click a button).

    Args:
        element: uiautomation Control element.
        timeout: Seconds to wait for the action.

    Returns:
        True if the invoke succeeded.

    Raises:
        ActionError: If the element doesn't support InvokePattern.
    """
    try:
        pattern = element.GetInvokePattern(timeout=timeout)
        if pattern is None:
            raise ActionError(f"Element does not support InvokePattern: {element.ControlType}")

        pattern.Invoke()
        logger.info("Invoked element: %s", element.Name)
        return True
    except ActionError:
        raise
    except Exception as e:
        raise ActionError(f"InvokePattern failed: {e}") from e


def set_value(element: Any, value: str, timeout: float = 5.0) -> bool:
    """Set the ValuePattern value on an element (e.g. text field).

    Args:
        element: uiautomation Control element.
        value: The string value to set.
        timeout: Seconds to wait for the action.

    Returns:
        True if the value was set.

    Raises:
        ActionError: If the element doesn't support ValuePattern.
    """
    try:
        pattern = element.GetValuePattern(timeout=timeout)
        if pattern is None:
            raise ActionError(f"Element does not support ValuePattern: {element.ControlType}")

        if not pattern.IsReadOnly:
            pattern.SetValue(value)
            logger.info("Set value '%s' on element: %s", value[:40], element.Name)
            return True
        else:
            raise ActionError(f"Element is read-only: {element.Name}")
    except ActionError:
        raise
    except Exception as e:
        raise ActionError(f"ValuePattern.SetValue failed: {e}") from e


def toggle_state(element: Any, desired_state: bool, timeout: float = 5.0) -> bool:
    """Toggle the TogglePattern state on an element (e.g. checkbox).

    Args:
        element: uiautomation Control element.
        desired_state: True for checked/pressed, False for unchecked.
        timeout: Seconds to wait for the action.

    Returns:
        True if the toggle succeeded.

    Raises:
        ActionError: If the element doesn't support TogglePattern.
    """
    try:
        pattern = element.GetTogglePattern(timeout=timeout)
        if pattern is None:
            raise ActionError(f"Element does not support TogglePattern: {element.ControlType}")

        current_state = pattern.ToggleState  # 0=off, 1=on, 2=indeterminate
        current_on = current_state == 1

        if current_on != desired_state:
            pattern.Toggle()
            logger.info("Toggled element '%s' to %s", element.Name, "on" if desired_state else "off")

        return True
    except ActionError:
        raise
    except Exception as e:
        raise ActionError(f"TogglePattern failed: {e}") from e


def select_item(element: Any, index: int, timeout: float = 5.0) -> bool:
    """Select an item in a SelectionPattern or ItemContainerPattern.

    Args:
        element: uiautomation Control element (combobox, list, grid, etc.)
        index: Zero-based index of the item to select.
        timeout: Seconds to wait for the action.

    Returns:
        True if selection succeeded.

    Raises:
        ActionError: If the element doesn't support selection.
    """
    try:
        # Try SelectionPattern first
        sel_pattern = element.GetSelectionPattern(timeout=timeout)
        if sel_pattern:
            items = sel_pattern.Current.Selection
            if items:
                # Iterate to find the item at the requested index
                for i, item in enumerate(items):
                    if i == index:
                        item.Select()
                        logger.info("Selected item %d in: %s", index, element.Name)
                        return True

        # Fall back to expanding and clicking
        expand_pattern = element.GetExpandCollapsePattern(timeout=timeout)
        if expand_pattern and expand_pattern.Current.ExpandCollapseState != 2:  # 2 = Expanded
            expand_pattern.Expand()

        # Try clicking child items
        children = element.GetChildren()
        if children and index < len(children):
            children[index].Click()
            logger.info("Selected child %d of: %s", index, element.Name)
            return True

        raise ActionError(f"No selection method available for: {element.Name}")
    except ActionError:
        raise
    except Exception as e:
        raise ActionError(f"Selection failed: {e}") from e
