"""Hermes Eats World — Verify module.

Provides:
- AssertionResult: Result of a single verification assertion
- VerificationPlan: A plan of pre/post assertions for an action
- Verifier: Evaluate assertions against UIA tree snapshots
- verify_element_exists, verify_element_value, verify_element_state
"""

from .assertions import (
    AssertionStatus,
    AssertionResult,
    VerificationPlan,
    Verifier,
    verify_element_exists,
    verify_element_value,
    verify_element_state,
    verify_tree_changed,
)

__all__ = [
    "AssertionStatus",
    "AssertionResult",
    "VerificationPlan",
    "Verifier",
    "verify_element_exists",
    "verify_element_value",
    "verify_element_state",
    "verify_tree_changed",
]
