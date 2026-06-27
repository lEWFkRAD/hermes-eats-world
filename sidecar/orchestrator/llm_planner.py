"""
Hermes Eats World — LLM-Powered Goal Planner
===============================================
Replaces the regex-based planner with an LLM-driven approach that understands
natural language goals and maps them to actionable steps using the current UI state.

Uses the local LLM provider (configured in SidecarConfig) to generate plans.
Falls back to the regex planner if the LLM is unavailable.

Usage:
    from sidecar.orchestrator.llm_planner import LLMPlanner

    planner = LLMPlanner()
    plan = planner.plan("click the Save button", perception_result)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..schema import Element as ElementModel
from .planner import ActionPlan, ActionStep, ActionPlanner

logger = logging.getLogger(__name__)

# ─── LLM Planner Prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Windows GUI automation planner. Your job is to decompose natural language goals into actionable steps that can be executed on a Windows application.

Available action types:
- invoke: Click/press a button, menu item, or clickable element
- set_value: Set the value of a text field, combo box, or editable element
- type_text: Type text into a field (character by character)
- toggle: Toggle a checkbox, toggle button, or switch
- scroll: Scroll within a container or the window
- click: Click at specific coordinates (T2 fallback)
- right_click: Right-click to open context menu
- hover: Hover over an element to trigger tooltips or menus
- drag: Drag from one point to another
- wait: Wait for a condition or timeout

Rules:
1. Generate the minimum number of steps needed
2. Each step should target a specific element from the UI tree when possible
3. Use automation_id when available (most reliable), then name, then control_type
4. For T2/T3 apps (sparse/no UIA), prefer click/type_text with coordinates
5. Include expected_result for each step so the executor can verify success
6. If an element isn't found in the tree, note it and suggest T2 fallback
7. Be specific about target elements — don't guess

Output ONLY valid JSON matching the ActionPlan schema. No markdown, no explanation."""

USER_PROMPT_TEMPLATE = """Goal: {goal}

Current UI state:
- Window: {window_name} (PID {pid})
- Tier: {tier}
- Total elements: {total_elements}

UI Tree (relevant elements):
{tree_summary}

Generate an action plan as JSON:
{{
  "goal": "{goal}",
  "steps": [
    {{
      "id": 1,
      "action_type": "invoke",
      "description": "Click the Save button",
      "target_name": "Save",
      "target_automation_id": "SaveButton",
      "target_control_type": "Button",
      "value": null,
      "expected_result": "File is saved",
      "parameters": {{}}
    }}
  ],
  "confidence": 0.95
}}"""


@dataclass
class LLMPlannerConfig:
    """Configuration for the LLM planner."""
    provider_url: str = "http://127.0.0.1:8001/v1"
    model: str = "qwen3.6-27b"
    timeout: float = 30.0
    max_retries: int = 2
    temperature: float = 0.1
    max_tree_depth: int = 4  # Max depth to include in prompt
    max_elements: int = 100  # Max elements to include in prompt


class LLMPlanner:
    """LLM-powered goal planner for Windows GUI automation.

    Uses a local LLM to understand natural language goals and generate
    executable action plans based on the current UI state.
    """

    def __init__(self, config: Optional[LLMPlannerConfig] = None):
        self.config = config or LLMPlannerConfig()
        self._fallback = ActionPlanner()

    def plan(self, goal: str, state) -> ActionPlan:
        """Generate an action plan for the given goal using LLM.

        Args:
            goal: Natural language description of the goal.
            state: PerceptionResult from the current UI state.

        Returns:
            ActionPlan with ordered steps.
        """
        start = time.time()
        logger.info("LLM planning for goal: %s", goal)

        # Build the tree summary for the prompt
        tree_summary = self._build_tree_summary(state.tree, state.summary)

        # Build the user prompt
        window_name = state.target.name if state.target else "Unknown"
        pid = state.target.process_id if state.target else 0
        user_prompt = USER_PROMPT_TEMPLATE.format(
            goal=goal,
            window_name=window_name,
            pid=pid,
            tier=state.tier.tier,
            total_elements=state.summary.total_elements,
            tree_summary=tree_summary,
        )

        # Try LLM planning
        for attempt in range(1 + self.config.max_retries):
            try:
                plan = self._call_llm(goal, user_prompt)
                if plan and plan.steps:
                    elapsed = time.time() - start
                    logger.info("LLM plan generated in %.1fs: %d steps, confidence=%.2f",
                               elapsed, len(plan.steps), plan.confidence)
                    return plan
                logger.warning("LLM returned empty plan, attempt %d", attempt + 1)
            except Exception as e:
                logger.warning("LLM planning failed (attempt %d): %s", attempt + 1, e)
                if attempt == self.config.max_retries:
                    break

        # Fallback to regex planner
        logger.info("Falling back to regex planner")
        return self._fallback.plan(goal, state)

    def check_goal(self, goal: str, state) -> bool:
        """Check if the goal appears to be achieved using LLM.

        Args:
            goal: The original goal string.
            state: Current PerceptionResult.

        Returns:
            True if the goal appears to be achieved.
        """
        # First try the regex-based check (fast)
        if self._fallback.check_goal(goal, state):
            return True

        # Try LLM-based verification
        try:
            tree_summary = self._build_tree_summary(state.tree, state.summary)
            prompt = f"""Check if this goal is achieved in the current UI state.

Goal: {goal}

Current UI state:
- Window: {state.target.name if state.target else 'Unknown'}
- Total elements: {state.summary.total_elements}

UI Tree:
{tree_summary}

Answer ONLY with JSON: {{"achieved": true}} or {{"achieved": false, "reason": "..."}}"""

            response = self._llm_request(prompt)
            result = json.loads(response)
            achieved = result.get("achieved", False)
            if not achieved:
                reason = result.get("reason", "unknown")
                logger.info("LLM goal check: not achieved (%s)", reason)
            else:
                logger.info("LLM goal check: achieved")
            return achieved
        except Exception as e:
            logger.debug("LLM goal check failed: %s", e)
            return False

    def _call_llm(self, goal: str, prompt: str) -> Optional[ActionPlan]:
        """Call the LLM and parse the response into an ActionPlan."""
        response = self._llm_request(prompt)
        return self._parse_llm_response(goal, response)

    def _llm_request(self, prompt: str) -> str:
        """Make an LLM API request.

        Returns:
            Raw JSON string from the LLM.
        """
        import urllib.request
        import urllib.error

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.config.provider_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.URLError as e:
            raise ConnectionError(f"LLM request failed: {e}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid LLM response: {e}") from e

    def _parse_llm_response(self, goal: str, response: str) -> Optional[ActionPlan]:
        """Parse LLM JSON response into an ActionPlan."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    logger.error("Failed to parse LLM JSON response")
                    return None
            else:
                logger.error("Failed to parse LLM response: %s", response[:200])
                return None

        steps = []
        for step_data in data.get("steps", []):
            step = ActionStep(
                id=step_data.get("id", 0),
                action_type=step_data.get("action_type", "invoke"),
                description=step_data.get("description", ""),
                target_name=step_data.get("target_name"),
                target_automation_id=step_data.get("target_automation_id"),
                target_control_type=step_data.get("target_control_type"),
                value=step_data.get("value"),
                expected_result=step_data.get("expected_result"),
                parameters=step_data.get("parameters", {}),
            )
            steps.append(step)

        # Renumber steps sequentially
        for i, step in enumerate(steps):
            step.id = i + 1

        return ActionPlan(
            goal=goal,
            steps=steps,
            confidence=data.get("confidence", 0.5),
        )

    def _build_tree_summary(self, tree: Optional[ElementModel],
                            summary) -> str:
        """Build a concise tree summary for the LLM prompt.

        Includes element name, automation_id, control_type, patterns,
        and bounding box for interactive elements.
        """
        if not tree:
            return "(no tree available)"

        lines: List[str] = []
        count = 0

        def _walk(elem: ElementModel, depth: int):
            nonlocal count
            if depth > self.config.max_tree_depth:
                return
            if count >= self.config.max_elements:
                return

            # Only include interactive/interesting elements
            is_interactive = (
                elem.is_enabled
                and (elem.patterns or elem.control_type in (
                    "Button", "Text", "ComboBox", "CheckBox", "MenuItem",
                    "ListItem", "HeaderItem", "Edit", "Document", "Pane",
                    "List", "Tree", "Table", "Grid", "ScrollBar",
                    "TabItem", "RadioButton", "Slider", "Spinner",
                ))
            )

            if is_interactive or depth < 2:
                indent = "  " * depth
                patterns = list(elem.patterns.keys()) if elem.patterns else []
                bbox = ""
                if elem.bounding_box:
                    b = elem.bounding_box
                    bbox = f" [{b.left},{b.top},{b.width}x{b.height}]"
                value = ""
                if "ValuePattern" in elem.patterns:
                    v = elem.patterns["ValuePattern"].get("value", "")
                    if v:
                        value = f" value=\"{v[:50]}\""
                line = f"{indent}- {elem.control_type}: \"{elem.name}\""
                if elem.automation_id:
                    line += f" id={elem.automation_id}"
                if patterns:
                    line += f" patterns={patterns}"
                line += bbox + value
                lines.append(line)
                count += 1

            for child in elem.children:
                _walk(child, depth + 1)

        _walk(tree, 0)

        if not lines:
            return "(no interactive elements found)"

        return "\n".join(lines)
