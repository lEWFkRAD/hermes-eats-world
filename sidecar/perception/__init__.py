"""Hermes Eats World — Perception module.

Tree walking, tier classification, control pattern extraction,
and state delta detection between perception passes.
"""

from .classifier import classify_tier
from .delta import ElementChange, StateDelta, state_delta, wait_for_change
from .patterns import get_control_patterns
from .tree_walker import (
    PER_ELEMENT_TIMEOUT,
    TOTAL_TREE_TIMEOUT,
    element_to_dict,
    summarize_tree,
    TreeWalkTimeout,
)

__all__ = [
    "classify_tier",
    "ElementChange",
    "get_control_patterns",
    "element_to_dict",
    "summarize_tree",
    "StateDelta",
    "state_delta",
    "wait_for_change",
    "TreeWalkTimeout",
    "PER_ELEMENT_TIMEOUT",
    "TOTAL_TREE_TIMEOUT",
]
