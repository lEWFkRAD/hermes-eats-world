"""
Hermes Eats World — Executor
=============================
Executes action steps by routing to T1 (UIA patterns) or T2 (SendInput).

The executor takes an ActionStep and the current PerceptionResult,
finds the target element, and dispatches to the appropriate action
module based on the tier classification and available patterns.

T1 (preferred): Direct UIA control pattern invocation.
T2 (fallback): Vision-guided SendInput synthesis.

Usage:
    from sidecar.orchestrator.executor import Executor

    executor = Executor()
    success = executor.execute(step, perception_result, target_params)
"""

import logging
import time
from typing import Dict, Optional

from ..action import invoke_pattern, set_value, toggle_state, click_at, type_text as t2_type_text
from ..schema import Element as ElementModel
from .planner import ActionStep

logger = logging.getLogger(__name__)


class Executor:
    """Execute action steps using T1/T2 strategies.

    Routes actions to the appropriate module based on:
    1. Action type (invoke, set_value, toggle, type_text)
    2. Tier classification (T1 → UIA patterns, T2/T3 → SendInput)
    3. Available control patterns on the target element
    """

    def execute(
        self,
        action: ActionStep,
        state,
        target_params: Dict,
    ) -> bool:
        """Execute an action step.

        Args:
            action: The ActionStep to execute.
            state: PerceptionResult from the current UI state.
            target_params: Target window parameters (title, process, class).

        Returns:
            True if the action succeeded.
        """
        action_type = action.action_type
        description = action.description

        logger.info("Executing step %d: [%s] %s", action.id, action_type, description)

        try:
            if action_type == "invoke":
                return self._execute_invoke(action, state, target_params)
            elif action_type == "set_value":
                return self._execute_set_value(action, state, target_params)
            elif action_type == "type_text":
                return self._execute_type_text(action, state, target_params)
            elif action_type == "toggle":
                return self._execute_toggle(action, state, target_params)
            elif action_type == "click":
                return self._execute_click(action, state, target_params)
            elif action_type == "select":
                return self._execute_select(action, state, target_params)
            else:
                logger.error("Unknown action type: %s", action_type)
                return False

        except Exception as e:
            logger.exception("Action execution failed: %s", e)
            return False

    def _find_target_element(self, action: ActionStep, tree: ElementModel) -> Optional[ElementModel]:
        """Find the target element for an action."""
        # Priority: automation_id > name > control_type
        if action.target_automation_id:
            return self._find_by_automation_id(tree, action.target_automation_id)

        if action.target_name:
            elem = self._find_by_name(tree, action.target_name)
            if elem:
                return elem

        if action.target_control_type:
            elems = self._find_by_type(tree, action.target_control_type)
            if elems:
                return elems[0]

        return None

    def _execute_invoke(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute an invoke/click action."""
        # T1: Try direct UIA InvokePattern
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and "InvokePattern" in elem.patterns:
                # Find the actual uiautomation control
                control = self._find_control(state, elem)
                if control:
                    try:
                        invoke_pattern(control)
                        logger.info("T1 invoke succeeded on '%s'", elem.name)
                        return True
                    except Exception as e:
                        logger.warning("T1 invoke failed, trying T2: %s", e)

        # T2: Fallback to SendInput click at element center
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and elem.bounding_box:
                bb = elem.bounding_box
                center_x = bb.left + bb.width // 2
                center_y = bb.top + bb.height // 2
                hwnd = state.target.hwnd if state.target else None
                if hwnd:
                    try:
                        click_at(hwnd, center_x, center_y)
                        logger.info("T2 click succeeded at (%d, %d)", center_x, center_y)
                        return True
                    except Exception as e:
                        logger.error("T2 click failed: %s", e)

        logger.error("Could not invoke target: %s", action.description)
        return False

    def _execute_set_value(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute a set_value action."""
        if action.value is None:
            logger.error("set_value requires a value")
            return False

        # T1: Try direct UIA ValuePattern
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and "ValuePattern" in elem.patterns:
                control = self._find_control(state, elem)
                if control:
                    try:
                        set_value(control, action.value)
                        logger.info("T1 set_value succeeded: '%s' → '%s'", elem.name, action.value[:40])
                        return True
                    except Exception as e:
                        logger.warning("T1 set_value failed, trying T2: %s", e)

        # T2: Fallback to typing via SendInput
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and elem.bounding_box:
                bb = elem.bounding_box
                center_x = bb.left + bb.width // 2
                center_y = bb.top + bb.height // 2
                hwnd = state.target.hwnd if state.target else None
                if hwnd:
                    try:
                        # Click to focus first
                        click_at(hwnd, center_x, center_y)
                        time.sleep(0.1)
                        # Then type
                        t2_type_text(hwnd, action.value)
                        logger.info("T2 type_text succeeded: '%s'", action.value[:40])
                        return True
                    except Exception as e:
                        logger.error("T2 type_text failed: %s", e)

        logger.error("Could not set value for: %s", action.description)
        return False

    def _execute_type_text(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute a type_text action."""
        if action.value is None:
            logger.error("type_text requires a value")
            return False

        # Try to find a text input field
        target_elem = None
        if state.tree:
            if action.target_name or action.target_automation_id:
                target_elem = self._find_target_element(action, state.tree)

            if not target_elem:
                # Find first editable element
                target_elem = self._find_first_editable(state.tree)

        # T1: Try ValuePattern.SetValue
        if target_elem and "ValuePattern" in target_elem.patterns:
            control = self._find_control(state, target_elem)
            if control:
                try:
                    set_value(control, action.value)
                    logger.info("T1 type_text succeeded on '%s'", target_elem.name)
                    return True
                except Exception as e:
                    logger.warning("T1 type_text failed, trying T2: %s", e)

        # T2: Fallback to SendInput
        if target_elem and target_elem.bounding_box:
            bb = target_elem.bounding_box
            center_x = bb.left + bb.width // 2
            center_y = bb.top + bb.height // 2
        else:
            # Use window center as fallback
            if state.target and state.target.bounding_box:
                bb = state.target.bounding_box
                center_x = bb.left + bb.width // 2
                center_y = bb.top + bb.height // 2
            else:
                logger.error("No target coordinates for type_text")
                return False

        hwnd = state.target.hwnd if state.target else None
        if hwnd:
            try:
                click_at(hwnd, center_x, center_y)
                time.sleep(0.1)
                t2_type_text(hwnd, action.value)
                logger.info("T2 type_text succeeded: '%s'", action.value[:40])
                return True
            except Exception as e:
                logger.error("T2 type_text failed: %s", e)

        return False

    def _execute_toggle(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute a toggle action."""
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and "TogglePattern" in elem.patterns:
                control = self._find_control(state, elem)
                if control:
                    try:
                        # Determine desired state from goal context
                        desired = True  # Default to enable/check
                        toggle_state(control, desired)
                        logger.info("T1 toggle succeeded on '%s'", elem.name)
                        return True
                    except Exception as e:
                        logger.warning("T1 toggle failed, trying T2: %s", e)

        # T2: Fallback to click
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and elem.bounding_box:
                bb = elem.bounding_box
                center_x = bb.left + bb.width // 2
                center_y = bb.top + bb.height // 2
                hwnd = state.target.hwnd if state.target else None
                if hwnd:
                    try:
                        click_at(hwnd, center_x, center_y)
                        logger.info("T2 toggle (click) succeeded on '%s'", elem.name)
                        return True
                    except Exception as e:
                        logger.error("T2 toggle failed: %s", e)

        return False

    def _execute_click(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute a direct click action (T2 SendInput)."""
        if state.tree:
            elem = self._find_target_element(action, state.tree)
            if elem and elem.bounding_box:
                bb = elem.bounding_box
                center_x = bb.left + bb.width // 2
                center_y = bb.top + bb.height // 2
                hwnd = state.target.hwnd if state.target else None
                if hwnd:
                    try:
                        click_at(hwnd, center_x, center_y)
                        logger.info("T2 click succeeded on '%s'", elem.name)
                        return True
                    except Exception as e:
                        logger.error("T2 click failed: %s", e)

        return False

    def _execute_select(self, action: ActionStep, state, target_params: Dict) -> bool:
        """Execute a select action."""
        # For now, treat as invoke
        return self._execute_invoke(action, state, target_params)

    # ─── Element search helpers ────────────────────────────────────

    def _find_by_name(self, tree: ElementModel, name: str) -> Optional[ElementModel]:
        """Find element by name (case-insensitive substring)."""
        name_lower = name.lower()

        def _search(elem: ElementModel) -> Optional[ElementModel]:
            if name_lower in elem.name.lower():
                return elem
            for child in elem.children:
                result = _search(child)
                if result:
                    return result
            return None

        return _search(tree)

    def _find_by_automation_id(self, tree: ElementModel, automation_id: str) -> Optional[ElementModel]:
        """Find element by exact AutomationId."""
        def _search(elem: ElementModel) -> Optional[ElementModel]:
            if elem.automation_id == automation_id:
                return elem
            for child in elem.children:
                result = _search(child)
                if result:
                    return result
            return None

        return _search(tree)

    def _find_by_type(self, tree: ElementModel, control_type: str) -> list:
        """Find all elements of a control type."""
        results = []
        type_lower = control_type.lower()

        def _search(elem: ElementModel):
            if type_lower in elem.control_type.lower():
                results.append(elem)
            for child in elem.children:
                _search(child)

        _search(tree)
        return results

    def _find_first_editable(self, tree: ElementModel) -> Optional[ElementModel]:
        """Find the first editable (ValuePattern) element."""
        def _search(elem: ElementModel) -> Optional[ElementModel]:
            if "ValuePattern" in elem.patterns:
                vp = elem.patterns["ValuePattern"]
                if not vp.get("readonly", False):
                    return elem
            for child in elem.children:
                result = _search(child)
                if result:
                    return result
            return None

        return _search(tree)

    def _find_control(self, state, elem: ElementModel):
        """Find the live uiautomation control for an Element model.

        Walks the live UIA tree to find the matching control by name + automation_id.
        """
        from ..service.service import perceive_target
        from ..target import find_window

        target_params = {
            "title": state.target.name if state.target else None,
        }

        target_result = find_window(
            title=target_params.get("title"),
            timeout=5,
        )
        if not target_result:
            return None

        control = target_result.control

        # Search for the matching control in the live tree
        def _search(ctrl, elem: ElementModel):
            if (ctrl.Name == elem.name and
                ctrl.AutomationId == elem.automation_id and
                ctrl.ControlType == elem.control_type):
                return ctrl

            try:
                for child in ctrl.GetChildren() or []:
                    result = _search(child, elem)
                    if result:
                        return result
            except Exception:
                pass

            return None

        return _search(control, elem)
