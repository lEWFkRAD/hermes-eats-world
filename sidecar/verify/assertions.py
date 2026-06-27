"""
Hermes Eats World — Verify Assertions
======================================
Pre/post assertion system for the PERCEIVE→PLAN→ACT→VERIFY loop.

Every action should be wrapped with assertions that confirm the expected
state change happened. This is the backstop against unbounded automation.

Assertion types:
    - element_exists: A named element is present in the tree
    - element_value: An element has a specific value
    - element_state: An element has a specific state (checked, selected, etc.)
    - tree_changed: The tree structure changed after an action
    - element_absent: A named element is NOT present in the tree

Usage:
    from sidecar.verify import Verifier, VerificationPlan

    plan = VerificationPlan(
        pre_assertions=[
            {"type": "element_exists", "name": "Submit Button", "control_type": "Button"},
        ],
        post_assertions=[
            {"type": "tree_changed", "min_changes": 1},
        ],
    )

    verifier = Verifier()
    pre_result = verifier.check_pre(tree_snapshot, plan)
    # ... execute action ...
    post_result = verifier.check_post(pre_snapshot, post_snapshot, plan)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..schema.models import Element

logger = logging.getLogger(__name__)


class AssertionStatus(Enum):
    """Result of a single assertion."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AssertionResult:
    """Result of evaluating one assertion."""
    assertion_type: str
    status: AssertionStatus
    description: str
    expected: Any = None
    actual: Any = None
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.assertion_type,
            "status": self.status.value,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
            "details": self.details,
        }


@dataclass
class VerificationPlan:
    """A set of pre/post assertions for an action or goal.

    Attributes:
        pre_assertions: Assertions that must pass BEFORE the action.
        post_assertions: Assertions that must pass AFTER the action.
        require_all_pre: If True, ALL pre-assertions must pass. Default: True.
        require_all_post: If True, ALL post-assertions must pass. Default: True.
    """
    pre_assertions: List[Dict[str, Any]] = field(default_factory=list)
    post_assertions: List[Dict[str, Any]] = field(default_factory=list)
    require_all_pre: bool = True
    require_all_post: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pre_assertions": self.pre_assertions,
            "post_assertions": self.post_assertions,
            "require_all_pre": self.require_all_pre,
            "require_all_post": self.require_all_post,
        }


# ---------------------------------------------------------------------------
# Assertion evaluators
# ---------------------------------------------------------------------------

def _find_element(tree: Element, name: str, control_type: Optional[str] = None) -> Optional[Element]:
    """Find an element in the tree by name (case-insensitive substring)."""
    if not tree or not name:
        return None
    name_lower = name.lower()

    def _search(elem: Element) -> Optional[Element]:
        if elem.name and name_lower in elem.name.lower():
            if control_type is None or (elem.control_type and control_type.lower() in elem.control_type.lower()):
                return elem
        for child in elem.children:
            result = _search(child)
            if result:
                return result
        return None

    return _search(tree)


def _count_elements(tree: Element) -> int:
    """Count total elements in the tree."""
    if not tree:
        return 0
    count = 1
    for child in tree.children:
        count += _count_elements(child)
    return count


def _tree_hash(tree: Element) -> int:
    """Compute a simple hash of the tree structure for change detection."""
    if not tree:
        return 0
    parts = []
    if tree.name:
        parts.append(tree.name)
    if tree.control_type:
        parts.append(tree.control_type)
    for child in tree.children:
        parts.append(str(_tree_hash(child)))
    return hash(tuple(parts))


def verify_element_exists(tree: Element, name: str, control_type: Optional[str] = None) -> AssertionResult:
    """Check if an element exists in the tree."""
    elem = _find_element(tree, name, control_type)
    desc = f"Element '{name}' exists"
    if control_type:
        desc += f" (type: {control_type})"

    if elem:
        return AssertionResult(
            assertion_type="element_exists",
            status=AssertionStatus.PASSED,
            description=desc,
            expected=name,
            actual=elem.name,
        )
    return AssertionResult(
        assertion_type="element_exists",
        status=AssertionStatus.FAILED,
        description=desc,
        expected=name,
        actual="not found",
        details=f"Searched {_count_elements(tree)} elements in tree",
    )


def verify_element_absent(tree: Element, name: str, control_type: Optional[str] = None) -> AssertionResult:
    """Check that an element does NOT exist in the tree."""
    elem = _find_element(tree, name, control_type)
    desc = f"Element '{name}' is absent"

    if not elem:
        return AssertionResult(
            assertion_type="element_absent",
            status=AssertionStatus.PASSED,
            description=desc,
            expected="absent",
            actual="absent",
        )
    return AssertionResult(
        assertion_type="element_absent",
        status=AssertionStatus.FAILED,
        description=desc,
        expected="absent",
        actual=elem.name,
    )


def verify_element_value(tree: Element, name: str, expected_value: str,
                         control_type: Optional[str] = None) -> AssertionResult:
    """Check that an element has the expected value."""
    elem = _find_element(tree, name, control_type)
    desc = f"Element '{name}' has value '{expected_value}'"

    if not elem:
        return AssertionResult(
            assertion_type="element_value",
            status=AssertionStatus.FAILED,
            description=desc,
            expected=expected_value,
            actual="element not found",
        )

    # Check ValuePattern first, then fall back to element name
    vp = elem.patterns.get("ValuePattern", {})
    actual_value = vp.get("value", elem.name or "")
    if expected_value.lower() in actual_value.lower():
        return AssertionResult(
            assertion_type="element_value",
            status=AssertionStatus.PASSED,
            description=desc,
            expected=expected_value,
            actual=actual_value,
        )
    return AssertionResult(
        assertion_type="element_value",
        status=AssertionStatus.FAILED,
        description=desc,
        expected=expected_value,
        actual=actual_value,
    )


def verify_element_state(tree: Element, name: str, pattern: str,
                         expected_state: Any, control_type: Optional[str] = None) -> AssertionResult:
    """Check that an element's control pattern has the expected state.

    Args:
        tree: The UIA tree snapshot.
        name: Element name to find.
        pattern: Pattern name (e.g., "TogglePattern", "SelectionPattern").
        expected_state: Expected state value.
        control_type: Optional control type filter.
    """
    elem = _find_element(tree, name, control_type)
    desc = f"Element '{name}' has {pattern} state {expected_state}"

    if not elem:
        return AssertionResult(
            assertion_type="element_state",
            status=AssertionStatus.FAILED,
            description=desc,
            expected=expected_state,
            actual="element not found",
        )

    patterns = elem.patterns or {}
    pattern_data = patterns.get(pattern)

    if not pattern_data:
        return AssertionResult(
            assertion_type="element_state",
            status=AssertionStatus.FAILED,
            description=desc,
            expected=f"{pattern}={expected_state}",
            actual=f"pattern '{pattern}' not available",
            details=f"Available patterns: {list(patterns.keys())}",
        )

    # Check common state keys
    actual_state = pattern_data.get("state", pattern_data.get("isSelected", pattern_data.get("isChecked")))

    if actual_state == expected_state:
        return AssertionResult(
            assertion_type="element_state",
            status=AssertionStatus.PASSED,
            description=desc,
            expected=expected_state,
            actual=actual_state,
        )
    return AssertionResult(
        assertion_type="element_state",
        status=AssertionStatus.FAILED,
        description=desc,
        expected=expected_state,
        actual=actual_state,
    )


def verify_tree_changed(pre_tree: Element, post_tree: Element,
                        min_changes: int = 1) -> AssertionResult:
    """Check that the tree structure changed after an action.

    Compares tree hashes and element counts to detect structural changes.
    """
    pre_count = _count_elements(pre_tree) if pre_tree else 0
    post_count = _count_elements(post_tree) if post_tree else 0
    pre_hash = _tree_hash(pre_tree) if pre_tree else 0
    post_hash = _tree_hash(post_tree) if post_tree else 0

    count_diff = abs(post_count - pre_count)
    hash_changed = pre_hash != post_hash
    desc = f"Tree changed (min {min_changes} changes)"

    if count_diff >= min_changes or hash_changed:
        return AssertionResult(
            assertion_type="tree_changed",
            status=AssertionStatus.PASSED,
            description=desc,
            expected=f"≥{min_changes} changes",
            actual=f"count_diff={count_diff}, hash_changed={hash_changed}",
            details=f"pre: {pre_count} elements, post: {post_count} elements",
        )
    return AssertionResult(
        assertion_type="tree_changed",
        status=AssertionStatus.FAILED,
        description=desc,
        expected=f"≥{min_changes} changes",
        actual="no significant change detected",
        details=f"pre: {pre_count} elements, post: {post_count} elements",
    )


# ---------------------------------------------------------------------------
# Verifier class
# ---------------------------------------------------------------------------

class Verifier:
    """Evaluate assertion plans against UIA tree snapshots.

    Usage:
        verifier = Verifier()
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "Submit"}],
            post_assertions=[{"type": "tree_changed", "min_changes": 1}],
        )

        # Check pre-conditions
        pre_ok, pre_results = verifier.check_pre(snapshot, plan)
        if not pre_ok:
            raise RuntimeError(f"Pre-conditions failed: {pre_results}")

        # ... execute action ...

        # Check post-conditions
        post_ok, post_results = verifier.check_post(snapshot, new_snapshot, plan)
    """

    def __init__(self):
        self._evaluators = {
            "element_exists": self._eval_element_exists,
            "element_absent": self._eval_element_absent,
            "element_value": self._eval_element_value,
            "element_state": self._eval_element_state,
            "tree_changed": self._eval_tree_changed,
        }

    def check_pre(self, tree: Element, plan: VerificationPlan) -> tuple:
        """Check pre-action assertions against the current tree.

        Returns:
            (all_passed: bool, results: List[AssertionResult])
        """
        if not plan.pre_assertions:
            return True, []

        results = []
        for assertion in plan.pre_assertions:
            result = self._evaluate(assertion, tree, pre_tree=tree, post_tree=None)
            results.append(result)

        passed = sum(1 for r in results if r.status == AssertionStatus.PASSED)
        if plan.require_all_pre:
            all_ok = passed == len(results)
        else:
            all_ok = passed > 0

        if not all_ok:
            failed = [r for r in results if r.status == AssertionStatus.FAILED]
            logger.warning(
                "Pre-assertion check failed: %d/%d passed", passed, len(results)
            )
            for r in failed:
                logger.warning("  FAILED: %s (expected %s, got %s)", r.description, r.expected, r.actual)

        return all_ok, results

    def check_post(self, pre_tree: Element, post_tree: Element,
                   plan: VerificationPlan) -> tuple:
        """Check post-action assertions against the before/after trees.

        Returns:
            (all_passed: bool, results: List[AssertionResult])
        """
        if not plan.post_assertions:
            return True, []

        results = []
        for assertion in plan.post_assertions:
            result = self._evaluate(assertion, post_tree, pre_tree=pre_tree, post_tree=post_tree)
            results.append(result)

        passed = sum(1 for r in results if r.status == AssertionStatus.PASSED)
        if plan.require_all_post:
            all_ok = passed == len(results)
        else:
            all_ok = passed > 0

        if not all_ok:
            failed = [r for r in results if r.status == AssertionStatus.FAILED]
            logger.warning(
                "Post-assertion check failed: %d/%d passed", passed, len(results)
            )
            for r in failed:
                logger.warning("  FAILED: %s (expected %s, got %s)", r.description, r.expected, r.actual)

        return all_ok, results

    def _evaluate(self, assertion: Dict[str, Any], tree: Element,
                  pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        """Evaluate a single assertion dict."""
        assert_type = assertion.get("type", "element_exists")
        evaluator = self._evaluators.get(assert_type)

        if not evaluator:
            return AssertionResult(
                assertion_type=assert_type,
                status=AssertionStatus.SKIPPED,
                description=f"Unknown assertion type: {assert_type}",
            )

        return evaluator(assertion, tree, pre_tree, post_tree)

    # ─── Internal evaluators ────────────────────────────────────────

    def _eval_element_exists(self, assertion: Dict, tree: Element,
                              pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        return verify_element_exists(
            tree,
            name=assertion["name"],
            control_type=assertion.get("control_type"),
        )

    def _eval_element_absent(self, assertion: Dict, tree: Element,
                              pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        return verify_element_absent(
            tree,
            name=assertion["name"],
            control_type=assertion.get("control_type"),
        )

    def _eval_element_value(self, assertion: Dict, tree: Element,
                             pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        return verify_element_value(
            tree,
            name=assertion["name"],
            expected_value=assertion["expected_value"],
            control_type=assertion.get("control_type"),
        )

    def _eval_element_state(self, assertion: Dict, tree: Element,
                             pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        return verify_element_state(
            tree,
            name=assertion["name"],
            pattern=assertion["pattern"],
            expected_state=assertion["expected_state"],
            control_type=assertion.get("control_type"),
        )

    def _eval_tree_changed(self, assertion: Dict, tree: Element,
                            pre_tree: Optional[Element], post_tree: Optional[Element]) -> AssertionResult:
        min_changes = assertion.get("min_changes", 1)
        if pre_tree is None or post_tree is None:
            return AssertionResult(
                assertion_type="tree_changed",
                status=AssertionStatus.SKIPPED,
                description="tree_changed requires both pre and post snapshots",
            )
        return verify_tree_changed(pre_tree, post_tree, min_changes=min_changes)
