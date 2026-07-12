"""UI Automation perception work executed inside the killable worker process."""

from __future__ import annotations

import time
from typing import Any

import uiautomation

from ..perception import classify_tier, element_to_dict, summarize_tree
from ..target import drill_frame, is_frame_window


def perceive_hwnd(request: dict[str, Any]) -> dict[str, Any]:
    """Attach to one HWND and return serializable perception models."""
    control = uiautomation.ControlFromHandle(request["hwnd"])
    if control is None or not control.Exists(0, 3):
        raise RuntimeError("Could not attach to target HWND")

    if is_frame_window(request["class_name"]):
        content = drill_frame(control)
        if content is not None:
            control = content

    root, truncated = element_to_dict(
        control,
        depth=0,
        max_depth=request["max_depth"],
        include_raw_values=request["include_raw_values"],
        max_elements=request["max_elements"],
        deadline=time.monotonic() + request["timeout"],
    )
    summary = summarize_tree(root)
    tier = classify_tier(summary)
    return {
        "tree": root.model_dump(mode="json"),
        "summary": summary.model_dump(mode="json"),
        "tier": tier.model_dump(mode="json"),
        "truncated": truncated,
    }
