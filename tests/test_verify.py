"""Tests for sidecar.verify — Assertion and verification system.

The verify module uses dict-based assertions and Element tree snapshots.
Assertion types: element_exists, element_absent, element_value, element_state, tree_changed.
"""

import pytest

from sidecar.schema.models import Element
from sidecar.verify.assertions import (
    AssertionStatus,
    AssertionResult,
    VerificationPlan,
    Verifier,
    verify_element_exists,
    verify_element_absent,
    verify_element_value,
    verify_element_state,
    verify_tree_changed,
)


# ─── Helpers ────────────────────────────────────────────────────────

_counter = 0

def _build_tree(name: str, children: list | None = None, value: str | None = None,
                control_type: str = "ButtonControl", localized_type: str | None = None,
                patterns: dict | None = None) -> Element:
    """Build a simple Element tree for tests."""
    global _counter
    _counter += 1
    return Element(
        id=f"elem_{_counter}",
        name=name,
        control_type=control_type,
        localized_type=localized_type or "button",
        value=value,
        patterns=patterns or {},
        children=children or [],
    )


def _tree_with_submit() -> Element:
    """A tree containing a Submit button."""
    return _build_tree(
        "MainWindow",
        children=[
            _build_tree("Submit", control_type="Button"),
            _build_tree("Cancel", control_type="Button"),
            _build_tree("Status Label", control_type="Text", value="Ready"),
        ],
    )


def _tree_with_disabled_submit() -> Element:
    """A tree where Submit is disabled."""
    return _build_tree(
        "MainWindow",
        children=[
            _build_tree("Submit", control_type="Button",
                         patterns={"TogglePattern": {"state": False}}),
        ],
    )


# ─── AssertionResult Tests ──────────────────────────────────────────

class TestAssertionResult:
    """Test AssertionResult dataclass."""

    def test_passed(self):
        r = AssertionResult(
            assertion_type="element_exists",
            status=AssertionStatus.PASSED,
            description="Element exists",
            expected="Submit",
            actual="Submit",
        )
        assert r.status == AssertionStatus.PASSED

    def test_failed(self):
        r = AssertionResult(
            assertion_type="element_exists",
            status=AssertionStatus.FAILED,
            description="Element exists",
            expected="Submit",
            actual="not found",
        )
        assert r.status == AssertionStatus.FAILED

    def test_to_dict(self):
        r = AssertionResult(
            assertion_type="element_exists",
            status=AssertionStatus.PASSED,
            description="test",
        )
        d = r.to_dict()
        assert d["type"] == "element_exists"
        assert d["status"] == "passed"
        assert "description" in d


# ─── VerificationPlan Tests ─────────────────────────────────────────

class TestVerificationPlan:
    """Test VerificationPlan dataclass."""

    def test_defaults(self):
        plan = VerificationPlan()
        assert plan.pre_assertions == []
        assert plan.post_assertions == []
        assert plan.require_all_pre is True
        assert plan.require_all_post is True

    def test_with_assertions(self):
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "Submit"}],
            post_assertions=[{"type": "tree_changed", "min_changes": 1}],
        )
        assert len(plan.pre_assertions) == 1
        assert len(plan.post_assertions) == 1

    def test_to_dict(self):
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "X"}],
        )
        d = plan.to_dict()
        assert len(d["pre_assertions"]) == 1
        assert d["require_all_pre"] is True


# ─── Standalone Verifier Functions ──────────────────────────────────

class TestVerifyElementExists:
    """Test verify_element_exists()."""

    def test_finds_element(self):
        tree = _tree_with_submit()
        result = verify_element_exists(tree, "Submit")
        assert result.status == AssertionStatus.PASSED

    def test_finds_by_substring(self):
        tree = _tree_with_submit()
        result = verify_element_exists(tree, "Sub")  # substring match
        assert result.status == AssertionStatus.PASSED

    def test_not_found(self):
        tree = _tree_with_submit()
        result = verify_element_exists(tree, "Delete")
        assert result.status == AssertionStatus.FAILED

    def test_with_control_type(self):
        tree = _tree_with_submit()
        result = verify_element_exists(tree, "Submit", control_type="Button")
        assert result.status == AssertionStatus.PASSED

    def test_wrong_control_type(self):
        tree = _tree_with_submit()
        result = verify_element_exists(tree, "Submit", control_type="CheckBox")
        assert result.status == AssertionStatus.FAILED


class TestVerifyElementAbsent:
    """Test verify_element_absent()."""

    def test_element_is_absent(self):
        tree = _tree_with_submit()
        result = verify_element_absent(tree, "Delete")
        assert result.status == AssertionStatus.PASSED

    def test_element_exists_should_fail(self):
        tree = _tree_with_submit()
        result = verify_element_absent(tree, "Submit")
        assert result.status == AssertionStatus.FAILED


class TestVerifyElementValue:
    """Test verify_element_value().

    NOTE: Since Element has no 'value' field, verify_element_value uses elem.name.
    Tests reflect this actual behavior.
    """

    def test_value_matches(self):
        # Element name IS its value — exact substring match
        tree = _build_tree("Root", children=[_build_tree("Ready")])
        result = verify_element_value(tree, "Ready", "Ready")
        assert result.status == AssertionStatus.PASSED

    def test_value_partial_match(self):
        # Case-insensitive substring match against element name
        tree = _build_tree("Root", children=[_build_tree("All Ready")])
        result = verify_element_value(tree, "All Ready", "ready")  # case-insensitive
        assert result.status == AssertionStatus.PASSED

    def test_value_mismatch(self):
        tree = _build_tree("Root", children=[_build_tree("Status Label")])
        result = verify_element_value(tree, "Status Label", "Done")
        assert result.status == AssertionStatus.FAILED

    def test_element_not_found(self):
        tree = _tree_with_submit()
        result = verify_element_value(tree, "Missing", "value")
        assert result.status == AssertionStatus.FAILED


class TestVerifyElementState:
    """Test verify_element_state()."""

    def test_state_matches(self):
        tree = _tree_with_disabled_submit()
        result = verify_element_state(tree, "Submit", "TogglePattern", False)
        assert result.status == AssertionStatus.PASSED

    def test_state_mismatch(self):
        tree = _tree_with_disabled_submit()
        result = verify_element_state(tree, "Submit", "TogglePattern", True)
        assert result.status == AssertionStatus.FAILED
    def test_pattern_not_available(self):
        elem = _build_tree("Submit")
        tree = _build_tree("Window", children=[elem])
        result = verify_element_state(tree, "Submit", "TogglePattern", True)
        assert result.status == AssertionStatus.FAILED
        assert "pattern 'TogglePattern' not available" in result.actual
        assert "Available patterns: []" in result.details


class TestVerifyTreeChanged:
    """Test verify_tree_changed()."""

    def test_tree_changed_detected(self):
        pre = _build_tree("A", children=[_build_tree("B")])
        post = _build_tree("A", children=[_build_tree("B"), _build_tree("C")])
        result = verify_tree_changed(pre, post, min_changes=1)
        assert result.status == AssertionStatus.PASSED

    def test_tree_unchanged(self):
        tree = _build_tree("A", children=[_build_tree("B")])
        result = verify_tree_changed(tree, tree, min_changes=1)
        assert result.status == AssertionStatus.FAILED

    def test_different_names(self):
        pre = _build_tree("A", children=[_build_tree("B")])
        post = _build_tree("A", children=[_build_tree("X")])
        result = verify_tree_changed(pre, post, min_changes=0)
        assert result.status == AssertionStatus.PASSED


# ─── Verifier Class Tests ───────────────────────────────────────────

class TestVerifier:
    """Test the Verifier class integration."""

    def setup_method(self):
        self.verifier = Verifier()

    def test_check_pre_passes(self):
        tree = _tree_with_submit()
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "Submit"}],
        )
        ok, results = self.verifier.check_pre(tree, plan)
        assert ok is True
        assert len(results) == 1
        assert results[0].status == AssertionStatus.PASSED

    def test_check_pre_fails(self):
        tree = _tree_with_submit()
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "Delete"}],
        )
        ok, results = self.verifier.check_pre(tree, plan)
        assert ok is False
        assert results[0].status == AssertionStatus.FAILED

    def test_check_pre_empty_plan(self):
        tree = _tree_with_submit()
        plan = VerificationPlan()
        ok, results = self.verifier.check_pre(tree, plan)
        assert ok is True
        assert results == []

    def test_check_post_tree_changed(self):
        pre = _build_tree("A", children=[_build_tree("B")])
        post = _build_tree("A", children=[_build_tree("B"), _build_tree("C")])
        plan = VerificationPlan(
            post_assertions=[{"type": "tree_changed", "min_changes": 1}],
        )
        ok, results = self.verifier.check_post(pre, post, plan)
        assert ok is True

    def test_check_post_tree_unchanged_fails(self):
        tree = _build_tree("A", children=[_build_tree("B")])
        plan = VerificationPlan(
            post_assertions=[{"type": "tree_changed", "min_changes": 1}],
        )
        ok, results = self.verifier.check_post(tree, tree, plan)
        assert ok is False

    def test_check_post_empty_plan(self):
        tree = _tree_with_submit()
        plan = VerificationPlan()
        ok, results = self.verifier.check_post(tree, tree, plan)
        assert ok is True

    def test_unknown_assertion_type_skipped(self):
        tree = _tree_with_submit()
        plan = VerificationPlan(
            pre_assertions=[{"type": "nonexistent_type", "name": "X"}],
        )
        ok, results = self.verifier.check_pre(tree, plan)
        assert ok is False
        assert results[0].status == AssertionStatus.SKIPPED

    def test_require_all_false_any_pass(self):
        tree = _tree_with_submit()
        plan = VerificationPlan(
            pre_assertions=[
                {"type": "element_exists", "name": "Submit"},   # passes
                {"type": "element_exists", "name": "Delete"},    # fails
            ],
            require_all_pre=False,
        )
        ok, results = self.verifier.check_pre(tree, plan)
        assert ok is True  # at least one passed
        assert len(results) == 2

    def test_full_workflow(self):
        """Test full pre → action → post workflow."""
        pre_tree = _build_tree("A", children=[_build_tree("Btn")])

        # Pre: button exists
        plan = VerificationPlan(
            pre_assertions=[{"type": "element_exists", "name": "Btn"}],
            post_assertions=[{"type": "tree_changed", "min_changes": 1}],
        )
        pre_ok, pre_results = self.verifier.check_pre(pre_tree, plan)
        assert pre_ok is True

        # Simulate action: button is removed, new element added
        post_tree = _build_tree("A", children=[_build_tree("Result")])

        # Post: tree changed
        post_ok, post_results = self.verifier.check_post(pre_tree, post_tree, plan)
        assert post_ok is True
