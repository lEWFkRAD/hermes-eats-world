"""
Hermes Eats World — State Delta Detection
==========================================
Compare two perception snapshots to detect UI changes between consecutive
perception passes. Used for the "observe → act → re-observe" loop pattern.

Detects:
  - Element additions/removals (by ID or name+type fingerprint)
  - Bounding box changes (element moved/resized)
  - Property changes (name, value, enabled state)
  - Tree depth changes

Usage:
    from sidecar.perception import state_delta

    result1 = perceive_target(title="File Explorer")
    # ... do something ...
    result2 = perceive_target(title="File Explorer")

    delta = state_delta(result1.summary, result2.summary, result1.tree, result2.tree)
    print(f"Added: {len(delta.added)}, Removed: {len(delta.removed)}, Changed: {len(delta.changed)}")
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ..schema import Element as ElementModel, TreeSummary

logger = logging.getLogger(__name__)


@dataclass
class ElementChange:
    """A single change detected between two snapshots."""
    element_id: str
    change_type: str  # "added", "removed", "moved", "resized", "property_changed"
    detail: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class StateDelta:
    """Comparison result between two perception snapshots."""
    added: List[ElementChange] = field(default_factory=list)
    removed: List[ElementChange] = field(default_factory=list)
    changed: List[ElementChange] = field(default_factory=list)
    summary_changed: bool = False
    element_count_diff: int = 0
    tier_changed: bool = False

    @property
    def is_significant(self) -> bool:
        """Check if changes are significant enough to trigger reclassification."""
        return bool(self.added or self.removed or len(self.changed) > 5)

    @property
    def total_changes(self) -> int:
        """Total number of changes detected."""
        return len(self.added) + len(self.removed) + len(self.changed)

    def summary(self) -> str:
        """Human-readable summary of changes."""
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)}")
        if self.removed:
            parts.append(f"-{len(self.removed)}")
        if self.changed:
            parts.append(f"~{len(self.changed)}")
        if not parts:
            return "no changes"
        return f"{' '.join(parts)} changes"


def _flatten_elements(element: ElementModel, path: str = "root") -> Dict[str, ElementModel]:
    """Flatten an element tree into a dict of id -> element."""
    result: Dict[str, ElementModel] = {}
    element._path = path  # type: ignore
    result[element.id] = element
    for child in element.children:
        child_path = f"{path}/{child.control_type}_{child.name[:20]}"
        result.update(_flatten_elements(child, child_path))
    return result


def _fingerprint(elem: ElementModel) -> str:
    """Create a fingerprint for matching elements across snapshots.
    
    Uses control_type + name + position as a stable identifier when
    element IDs differ between snapshots.
    """
    bb = elem.bounding_box
    pos = f"{bb.left},{bb.top}" if bb else "0,0"
    return f"{elem.control_type}:{elem.name}:{elem.automation_id}:{pos}"


def _build_fingerprint_map(elements: Dict[str, ElementModel]) -> Dict[str, ElementModel]:
    """Build a fingerprint -> element mapping for cross-snapshot matching."""
    return {
        _fingerprint(elem): elem 
        for elem in elements.values()
    }


def state_delta(
    summary1: Optional[TreeSummary],
    summary2: Optional[TreeSummary],
    tree1: Optional[ElementModel],
    tree2: Optional[ElementModel],
) -> StateDelta:
    """Compare two perception snapshots and detect changes.

    Args:
        summary1: Summary from first perception pass.
        summary2: Summary from second perception pass.
        tree1: Element tree from first pass.
        tree2: Element tree from second pass.

    Returns:
        StateDelta with detected changes.
    """
    delta = StateDelta()

    # 1. Compare summaries
    if summary1 and summary2:
        delta.element_count_diff = summary2.total_elements - summary1.total_elements
        if summary1.total_elements != summary2.total_elements:
            delta.summary_changed = True
        if summary1.max_depth != summary2.max_depth:
            delta.summary_changed = True

    # 2. Compare element trees
    if tree1 and tree2:
        flat1 = _flatten_elements(tree1)
        flat2 = _flatten_elements(tree2)

        fp1 = _build_fingerprint_map(flat1)
        fp2 = _build_fingerprint_map(flat2)

        ids1 = set(fp1.keys())
        ids2 = set(fp2.keys())

        # Added elements
        for fp in ids2 - ids1:
            elem = fp2[fp]
            delta.added.append(ElementChange(
                element_id=elem.id,
                change_type="added",
                detail=f"{elem.control_type} '{elem.name[:30]}'",
            ))

        # Removed elements
        for fp in ids1 - ids2:
            elem = fp1[fp]
            delta.removed.append(ElementChange(
                element_id=elem.id,
                change_type="removed",
                detail=f"{elem.control_type} '{elem.name[:30]}'",
            ))

        # Changed elements (position, size, properties)
        for fp in ids1 & ids2:
            elem1 = fp1[fp]
            elem2 = fp2[fp]

            # Check bounding box changes
            if elem1.bounding_box and elem2.bounding_box:
                bb1 = elem1.bounding_box
                bb2 = elem2.bounding_box

                # Position change
                if bb1.left != bb2.left or bb1.top != bb2.top:
                    delta.changed.append(ElementChange(
                        element_id=elem2.id,
                        change_type="moved",
                        detail=f"{elem2.control_type} moved from ({bb1.left},{bb1.top}) to ({bb2.left},{bb2.top})",
                        old_value=f"({bb1.left},{bb1.top})",
                        new_value=f"({bb2.left},{bb2.top})",
                    ))

                # Size change
                if bb1.width != bb2.width or bb1.height != bb2.height:
                    delta.changed.append(ElementChange(
                        element_id=elem2.id,
                        change_type="resized",
                        detail=f"{elem2.control_type} resized from {bb1.width}x{bb1.height} to {bb2.width}x{bb2.height}",
                        old_value=f"{bb1.width}x{bb1.height}",
                        new_value=f"{bb2.width}x{bb2.height}",
                    ))

            # Property changes
            if elem1.is_enabled != elem2.is_enabled:
                delta.changed.append(ElementChange(
                    element_id=elem2.id,
                    change_type="property_changed",
                    detail=f"{elem2.control_type} enabled: {elem1.is_enabled} -> {elem2.is_enabled}",
                    old_value=str(elem1.is_enabled),
                    new_value=str(elem2.is_enabled),
                ))

            if elem1.name != elem2.name:
                delta.changed.append(ElementChange(
                    element_id=elem2.id,
                    change_type="property_changed",
                    detail=f"{elem2.control_type} name changed",
                    old_value=elem1.name[:50],
                    new_value=elem2.name[:50],
                ))

    logger.debug("State delta: %s", delta.summary())
    return delta


def wait_for_change(
    perceive_fn,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    significant_only: bool = True,
) -> Optional[StateDelta]:
    """Poll for UI changes by repeatedly calling a perception function.

    Args:
        perceive_fn: Callable that returns a PerceptionResult.
        timeout: Max seconds to wait for a change.
        poll_interval: Seconds between perception passes.
        significant_only: If True, only return on significant changes.

    Returns:
        StateDelta if a change was detected, None if timeout.
    """
    import time

    baseline = perceive_fn()
    if not baseline.ok:
        logger.error("Baseline perception failed: %s", baseline.error)
        return None

    start = time.time()
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        current = perceive_fn()
        if not current.ok:
            logger.warning("Perception poll failed: %s", current.error)
            continue

        delta = state_delta(
            baseline.summary, current.summary,
            baseline.tree, current.tree,
        )

        if significant_only and delta.is_significant:
            logger.info("Significant change detected after %.1fs: %s",
                        time.time() - start, delta.summary())
            return delta
        elif not significant_only and delta.total_changes > 0:
            logger.info("Change detected after %.1fs: %s",
                        time.time() - start, delta.summary())
            return delta

    logger.info("No change detected within %.1fs timeout", timeout)
    return None
