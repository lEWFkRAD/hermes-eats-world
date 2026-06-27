"""Hermes Eats World — Action module.

T1 actions: Direct UIA control pattern invocation.
T2 actions: Vision-guided input synthesis (SendInput / PostMessage).
"""

from .t1_invoke import invoke_pattern, set_value, toggle_state
from .t2_synthesize import (
    click_at, type_text, post_message, double_click_at,
    right_click_at, hover_at, drag, scroll_at,
)

__all__ = [
    # T1 actions
    "invoke_pattern",
    "set_value",
    "toggle_state",
    # T2 actions
    "click_at",
    "type_text",
    "post_message",
    "double_click_at",
    "right_click_at",
    "hover_at",
    "drag",
    "scroll_at",
]
