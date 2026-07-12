"""Resolve action targets and evaluate snapshot preconditions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..schema import Element, TreeSnapshot


class ResolutionError(RuntimeError):
    """The requested element cannot be safely resolved in the current snapshot."""


class StaleStateError(RuntimeError):
    """The current element no longer matches the action's expected state."""


def resolve_element(snapshot: TreeSnapshot, element_id: str) -> Element:
    matches: list[Element] = []
    stack = [snapshot.tree]
    while stack:
        element = stack.pop()
        if element.id == element_id:
            matches.append(element)
        stack.extend(element.children)

    if not matches:
        raise ResolutionError(f"Element '{element_id}' was not found in fresh snapshot")
    if len(matches) > 1:
        raise ResolutionError(f"Element ID '{element_id}' is ambiguous in fresh snapshot")
    return matches[0]


def require_state(element: Element, expected: dict[str, Any], *, phase: str) -> None:
    mismatches = []
    for path, wanted in expected.items():
        actual = _read_path(element, path)
        if actual != wanted:
            mismatches.append(f"{path}: expected {wanted!r}, found {actual!r}")
    if mismatches:
        raise StaleStateError(f"{phase} state mismatch: " + "; ".join(mismatches))


def element_fingerprint(element: Element) -> str:
    payload = element.model_dump(mode="json", exclude={"children"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_path(element: Element, path: str) -> Any:
    allowed = {
        "name": element.name,
        "is_enabled": element.is_enabled,
        "is_offscreen": element.is_offscreen,
        "control_type": element.control_type,
        "automation_id": element.automation_id,
    }
    if path in allowed:
        return allowed[path]
    if path.startswith("patterns."):
        current: Any = element.patterns
        for part in path.split(".")[1:]:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
    raise ValueError(f"Unsupported state path '{path}'")
