"""
Hermes Eats World — Action Planner
===================================
Decomposes natural language goals into a sequence of actionable steps.

The planner analyzes the current UI state (perception result) and the goal,
then produces an ordered list of ActionStep objects that the executor can
run. Uses rule-based heuristics for now — no LLM required.

Usage:
    from sidecar.orchestrator.planner import ActionPlanner

    planner = ActionPlanner()
    plan = planner.plan("click the Save button", perception_result)
    for step in plan.steps:
        print(f"Step {step.id}: {step.description}")
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..schema import Element as ElementModel

logger = logging.getLogger(__name__)

# Digit ↔ word forms so a goal phrased with "7" still matches a button whose
# accessible name is "Seven" (UWP Calculator, dial pads, etc.), and vice-versa.
_DIGIT_TO_WORD = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}
_WORD_TO_DIGIT = {word: digit for digit, word in _DIGIT_TO_WORD.items()}


def _search_terms(name_lower: str) -> list[str]:
    """Expand a search string with digit↔word synonyms (exact-token only)."""
    terms = [name_lower]
    if name_lower in _DIGIT_TO_WORD:
        terms.append(_DIGIT_TO_WORD[name_lower])
    elif name_lower in _WORD_TO_DIGIT:
        terms.append(_WORD_TO_DIGIT[name_lower])
    return terms


# ─── Action Step ───────────────────────────────────────────────────

@dataclass
class ActionStep:
    """A single step in an execution plan."""
    id: int
    action_type: str  # "invoke", "set_value", "click", "type_text", "select", "toggle"
    description: str
    target_name: Optional[str] = None       # Name of the element to target
    target_automation_id: Optional[str] = None
    target_control_type: Optional[str] = None
    value: Optional[str] = None             # Value for set_value/type_text
    expected_result: Optional[str] = None   # What we expect to see after this step
    parameters: Dict = field(default_factory=dict)


@dataclass
class ActionPlan:
    """An ordered plan of action steps."""
    goal: str
    steps: List[ActionStep] = field(default_factory=list)
    confidence: float = 1.0


# ─── Goal patterns ─────────────────────────────────────────────────

# (regex_pattern, action_type, extraction_logic)
GOAL_PATTERNS = [
    # Click/invoke patterns
    (r"(?:click|press|tap)\s+(?:the\s+)?(.+?)(?:\s+button)?(?:\s|$)", "invoke", None),
    (r"(?:open|launch|run)\s+(?:the\s+)?(.+?)(?:\s+)?(?:menu|item|dialog)?", "invoke", None),
    (r"(?:select|choose)\s+(?:the\s+)?(.+)", "invoke", None),

    # Text entry patterns
    (r"(?:type|enter|input|write)\s+(.+?)(?:\s+into\s+(?:the\s+)?(.+))?$", "type_text", None),
    (r"(?:set|change|update)\s+(?:the\s+)?(.+?)(?:\s+to\s+(.+))?", "set_value", None),

    # Toggle patterns
    (r"(?:toggle|enable|disable|check|uncheck)\s+(?:the\s+)?(.+)", "toggle", None),

    # Scroll patterns
    (r"(?:scroll\s+(?:to\s+)?(.+))", "scroll", None),

    # Search patterns
    (r"(?:search\s+for\s+(.+))", "search", None),

    # File operations
    (r"(?:save\s*(?:as\s*(.+))?)", "invoke", None),
    (r"(?:open\s+(?:file\s*)?(.+))", "invoke", None),
]


class ActionPlanner:
    """Decompose natural language goals into executable action plans.

    Uses pattern matching and UI state analysis to generate plans.
    No LLM required — pure heuristic approach.
    """

    def plan(self, goal: str, state) -> ActionPlan:
        """Generate an action plan for the given goal.

        Args:
            goal: Natural language description of the goal.
            state: PerceptionResult from the current UI state.

        Returns:
            ActionPlan with ordered steps.
        """
        steps: List[ActionStep] = []
        goal_lower = goal.lower().strip()

        logger.info("Planning for goal: %s", goal)
        logger.info("UI state: %d elements, tier=%s", state.summary.total_elements, state.tier.tier)

        # Try to parse the goal using patterns
        parsed = self._parse_goal(goal_lower, state)
        if parsed:
            steps.extend(parsed)
        else:
            # Fallback: try to find the most likely target element and action
            fallback = self._fallback_plan(goal_lower, state)
            if fallback:
                steps.extend(fallback)

        if not steps:
            logger.warning("Could not generate plan for goal: %s", goal)
            return ActionPlan(goal=goal, steps=[], confidence=0.0)

        # Assign sequential IDs
        for i, step in enumerate(steps):
            step.id = i + 1

        logger.info("Generated plan with %d steps", len(steps))
        return ActionPlan(
            goal=goal,
            steps=steps,
            confidence=min(1.0, len(steps) * 0.3),
        )

    def check_goal(self, goal: str, state) -> bool:
        """Check if the goal appears to be achieved in the current state.

        Args:
            goal: The original goal string.
            state: Current PerceptionResult.

        Returns:
            True if the goal appears to be achieved.
        """
        goal_lower = goal.lower().strip()

        # Check for "save" goal — look for "Untitled" disappearing from title
        if "save" in goal_lower:
            if state.target and "untitled" not in state.target.name.lower():
                return True

        # Check for "type" or "enter" goal — look for text in the target
        if any(w in goal_lower for w in ["type", "enter", "input", "write"]):
            # Check if the typed text appears in the UI tree
            match = re.search(r"(?:type|enter|input|write)\s+(.+?)(?:\s+into)?", goal_lower)
            if match:
                expected_text = match.group(1).strip().strip('"').strip("'")
                if self._text_in_tree(state.tree, expected_text):
                    return True

        # Check for "click" goal — look for state changes
        if "click" in goal_lower or "press" in goal_lower:
            # Hard to verify without pre/post comparison; assume success if no error
            return True

        return False

    def _parse_goal(self, goal: str, state) -> Optional[List[ActionStep]]:
        """Parse a goal using regex patterns and return action steps."""
        for pattern, action_type, _ in GOAL_PATTERNS:
            match = re.search(pattern, goal)
            if match:
                groups = match.groups()
                logger.info("Goal matched pattern: %s → action: %s", pattern, action_type)

                if action_type == "invoke":
                    target = groups[0].strip().strip('"').strip("'")
                    return self._plan_invoke(target, state)

                elif action_type == "set_value":
                    # "set X to Y"
                    if len(groups) >= 2:
                        target = groups[0].strip()
                        value = groups[1].strip().strip('"').strip("'")
                        return self._plan_set_value(target, value, state)
                    else:
                        target = groups[0].strip()
                        return self._plan_invoke(target, state)

                elif action_type == "type_text":
                    text = groups[0].strip().strip('"').strip("'")
                    target = groups[1].strip() if groups[1] else None
                    return self._plan_type_text(text, target, state)

                elif action_type == "toggle":
                    target = groups[0].strip()
                    return self._plan_toggle(target, state)

                elif action_type == "search":
                    query = groups[0].strip()
                    return self._plan_search(query, state)

        return None

    def _fallback_plan(self, goal: str, state) -> Optional[List[ActionStep]]:
        """Fallback: try to infer the action from keywords and UI state."""
        steps: List[ActionStep] = []

        # Find invocable elements
        invocable = self._find_invocable(state.tree)
        editable = self._find_editable(state.tree)

        # If goal mentions a button-like thing, try to find it
        button_keywords = ["button", "click", "press", "tap", "save", "open", "close", "ok", "cancel"]
        for kw in button_keywords:
            if kw in goal:
                # Look for an element with this keyword in the name
                target = self._find_element_by_keyword(state.tree, kw)
                if target:
                    steps.append(ActionStep(
                        id=0,  # Will be renumbered
                        action_type="invoke",
                        description=f"Invoke '{target.name}' (keyword: {kw})",
                        target_name=target.name,
                        target_automation_id=target.automation_id,
                        expected_result=f"'{target.name}' was invoked",
                    ))
                    return steps

        # If goal mentions typing/text
        text_keywords = ["type", "enter", "input", "write", "text"]
        for kw in text_keywords:
            if kw in goal:
                if editable:
                    target = editable[0]  # Use first editable field
                    # Extract text from goal
                    text_match = re.search(r"(?:type|enter|input|write)\s+(.+)", goal)
                    text = text_match.group(1).strip().strip('"').strip("'") if text_match else ""
                    steps.append(ActionStep(
                        id=0,
                        action_type="type_text",
                        description=f"Type '{text[:30]}' into '{target.name}'",
                        target_name=target.name,
                        target_automation_id=target.automation_id,
                        value=text,
                        expected_result=f"Text '{text[:30]}' entered",
                    ))
                    return steps

        # Last resort: try to invoke the first available button
        if invocable:
            target = invocable[0]
            steps.append(ActionStep(
                id=0,
                action_type="invoke",
                description=f"Invoke '{target.name}' (fallback)",
                target_name=target.name,
                target_automation_id=target.automation_id,
                expected_result=f"'{target.name}' was invoked",
            ))
            return steps

        return None

    def _plan_invoke(self, target_name: str, state) -> Optional[List[ActionStep]]:
        """Plan an invoke/click action."""
        # Find the target element
        element = self._find_element(state.tree, target_name)
        if not element:
            # Try keyword matching
            element = self._find_element_by_keyword(state.tree, target_name)

        if not element:
            logger.warning("Could not find element for invoke: %s", target_name)
            return [ActionStep(
                id=0,
                action_type="invoke",
                description=f"Invoke '{target_name}' (element not found, will use T2 fallback)",
                target_name=target_name,
                expected_result=f"'{target_name}' was invoked",
            )]

        return [ActionStep(
            id=0,
            action_type="invoke",
            description=f"Invoke '{element.name}'",
            target_name=element.name,
            target_automation_id=element.automation_id,
            target_control_type=element.control_type,
            expected_result=f"'{element.name}' was invoked",
        )]

    def _plan_set_value(self, target: str, value: str, state) -> Optional[List[ActionStep]]:
        """Plan a set_value action."""
        element = self._find_element(state.tree, target)
        if not element:
            element = self._find_element_by_keyword(state.tree, target)

        if not element:
            return [ActionStep(
                id=0,
                action_type="set_value",
                description=f"Set '{target}' to '{value}' (element not found)",
                target_name=target,
                value=value,
                expected_result=f"'{target}' set to '{value}'",
            )]

        return [ActionStep(
            id=0,
            action_type="set_value",
            description=f"Set '{element.name}' to '{value}'",
            target_name=element.name,
            target_automation_id=element.automation_id,
            value=value,
            expected_result=f"'{element.name}' set to '{value}'",
        )]

    def _plan_type_text(self, text: str, target: Optional[str], state) -> Optional[List[ActionStep]]:
        """Plan a type_text action."""
        if target:
            element = self._find_element(state.tree, target)
        else:
            # Find first editable element
            editable = self._find_editable(state.tree)
            element = editable[0] if editable else None

        if element:
            return [ActionStep(
                id=0,
                action_type="type_text",
                description=f"Type '{text[:30]}' into '{element.name}'",
                target_name=element.name,
                target_automation_id=element.automation_id,
                value=text,
                expected_result=f"Text '{text[:30]}' entered",
            )]

        return [ActionStep(
            id=0,
            action_type="type_text",
            description=f"Type '{text[:30]}' (target: {target or 'first editable'})",
            target_name=target,
            value=text,
            expected_result=f"Text '{text[:30]}' entered",
        )]

    def _plan_toggle(self, target: str, state) -> Optional[List[ActionStep]]:
        """Plan a toggle action."""
        element = self._find_element(state.tree, target)
        if not element:
            element = self._find_element_by_keyword(state.tree, target)

        if element:
            return [ActionStep(
                id=0,
                action_type="toggle",
                description=f"Toggle '{element.name}'",
                target_name=element.name,
                target_automation_id=element.automation_id,
                expected_result=f"'{element.name}' state changed",
            )]

        return [ActionStep(
            id=0,
            action_type="toggle",
            description=f"Toggle '{target}'",
            target_name=target,
            expected_result=f"'{target}' toggled",
        )]

    def _plan_search(self, query: str, state) -> Optional[List[ActionStep]]:
        """Plan a search action: find search box, type query, press Enter."""
        steps: List[ActionStep] = []

        # Look for a search box
        search_box = None
        for elem in self._find_editable(state.tree):
            if any(kw in elem.name.lower() for kw in ["search", "find", "filter"]):
                search_box = elem
                break

        if not search_box:
            editable = self._find_editable(state.tree)
            search_box = editable[0] if editable else None

        if search_box:
            steps.append(ActionStep(
                id=0,
                action_type="type_text",
                description=f"Type '{query}' into search box",
                target_name=search_box.name,
                target_automation_id=search_box.automation_id,
                value=query,
                expected_result=f"Query '{query}' entered in search",
            ))
            steps.append(ActionStep(
                id=0,
                action_type="invoke",
                description="Press Enter to search",
                value="Enter",
                expected_result="Search results displayed",
            ))
        else:
            steps.append(ActionStep(
                id=0,
                action_type="type_text",
                description=f"Search for '{query}'",
                value=query,
                expected_result=f"Search for '{query}'",
            ))

        return steps

    # ─── Element search helpers ────────────────────────────────────

    def _find_element(self, tree: Optional[ElementModel], name: str) -> Optional[ElementModel]:
        """Find an element by name (case-insensitive substring match).

        Two refinements that matter for real apps (esp. UWP):
        - digit↔word synonyms: a goal says "7" but the UWP Calculator button is
          named "Seven" (and vice-versa), so we match either form.
        - prefer an *invocable* match: "7" substring-matches both the static
          TextControl label "7" and the ButtonControl "Seven"; the label can't
          be clicked, so when several elements match we return the one carrying
          an InvokePattern over a plain text node.
        """
        if not tree:
            return None

        terms = _search_terms(name.lower())
        matches: List[ElementModel] = []

        def _search(elem: ElementModel) -> None:
            if elem.name:
                lowered = elem.name.lower()
                if any(term in lowered for term in terms):
                    matches.append(elem)
            for child in elem.children:
                _search(child)

        _search(tree)
        if not matches:
            return None

        invocable = next((m for m in matches if "InvokePattern" in m.patterns), None)
        return invocable or matches[0]

    def _find_element_by_keyword(self, tree: Optional[ElementModel], keyword: str) -> Optional[ElementModel]:
        """Find an element whose name contains the keyword."""
        if not tree:
            return None
        return self._find_element(tree, keyword)

    def _find_invocable(self, tree: Optional[ElementModel]) -> List[ElementModel]:
        """Find all invocable elements."""
        if not tree:
            return []
        results: List[ElementModel] = []

        def _search(elem: ElementModel):
            if "InvokePattern" in elem.patterns and elem.is_enabled:
                results.append(elem)
            for child in elem.children:
                _search(child)

        _search(tree)
        return results

    def _find_editable(self, tree: Optional[ElementModel]) -> List[ElementModel]:
        """Find all editable (ValuePattern) elements."""
        if not tree:
            return []
        results: List[ElementModel] = []

        def _search(elem: ElementModel):
            if "ValuePattern" in elem.patterns:
                vp = elem.patterns["ValuePattern"]
                if not vp.get("readonly", False) and elem.is_enabled:
                    results.append(elem)
            for child in elem.children:
                _search(child)

        _search(tree)
        return results

    def _text_in_tree(self, tree: Optional[ElementModel], text: str) -> bool:
        """Check if text appears in any element's name or value."""
        if not tree:
            return False

        text_lower = text.lower()

        def _search(elem: ElementModel) -> bool:
            if text_lower in elem.name.lower():
                return True
            # Check value pattern
            if "ValuePattern" in elem.patterns:
                if text_lower in elem.patterns["ValuePattern"].get("value", "").lower():
                    return True
            for child in elem.children:
                if _search(child):
                    return True
            return False

        return _search(tree)
