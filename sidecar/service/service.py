"""
Hermes Eats World — Unified Perception Service
================================================
Single entry point that auto-selects T1/T2/T3 strategy based on
target app characteristics. Wraps the full pipeline: find window → walk tree → classify → output.

Public API:
    from sidecar.service.service import perceive_target, list_windows_api

    result = perceive_target(title="File Explorer")
    if result.ok:
        print(f"Tier: {result.tier}, Elements: {result.summary.total_elements}")
    else:
        print(f"Error: {result.error}")

    windows = list_windows_api()
    for w in windows:
        print(f"{w.name} (PID {w.process_id})")
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from ..perception import (
    classify_tier, element_to_dict, get_control_patterns, summarize_tree,
    PER_ELEMENT_TIMEOUT, TOTAL_TREE_TIMEOUT,
)
from ..schema import (
    SCHEMA_VERSION,
    Element as ElementModel,
    ErrorResponse,
    TreeSnapshot,
    TreeSummary,
    TierClassification,
    WindowInfo,
)
from ..target import find_window, list_windows, is_frame_window, drill_frame, WindowTarget
from .env_check import check_environment, set_dpi_awareness

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PerceptionResult — unified return type for perceive_target()
# ---------------------------------------------------------------------------

@dataclass
class PerceptionResult:
    """Result of a perception pass. Either success (ok=True) or error (ok=False)."""
    ok: bool
    error: Optional[str] = None
    target: Optional[WindowInfo] = None
    tier: Optional[TierClassification] = None
    summary: Optional[TreeSummary] = None
    tree: Optional[ElementModel] = None
    screenshot_path: Optional[str] = None
    elapsed: float = 0.0
    timestamp: Optional[str] = None

    def to_snapshot(self) -> TreeSnapshot:
        """Convert to TreeSnapshot for JSON serialization."""
        if not self.ok:
            raise ValueError("Cannot convert error result to snapshot")
        return TreeSnapshot(
            schema_version=SCHEMA_VERSION,
            target=self.target,
            tier=self.tier,
            summary=self.summary,
            tree=self.tree,
            screenshot_path=self.screenshot_path,
            timestamp=self.timestamp or datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Environment initialization
# ---------------------------------------------------------------------------

_env_initialized = False


def ensure_environment() -> bool:
    """Set up DPI awareness and check environment. Idempotent."""
    global _env_initialized
    if _env_initialized:
        return True
    set_dpi_awareness()
    env = check_environment()
    _env_initialized = True
    if not env.is_ok:
        logger.error("Environment check failed: %s", env.report())
        return False
    logger.debug("Environment OK: %s", env.report())
    return True


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def perceive_target(
    title: Optional[str] = None,
    process: Optional[str] = None,
    class_name: Optional[str] = None,
    depth: int = 3,
    screenshot: bool = False,
    output_file: Optional[str] = None,
    timeout: float = 5.0,
) -> PerceptionResult:
    """Perceive a target window and return structured UI state.

    Auto-selects T1 (direct UIA), T2 (vision fallback), or T3 (opaque)
    strategy based on the classification result.

    Args:
        title: Window title substring match.
        process: Process name (e.g. "notepad.exe").
        class_name: Window class name.
        depth: Max tree walk depth (default 3, max 500).
        screenshot: Capture a window screenshot.
        output_file: If set, write JSON snapshot to this path.
        timeout: Window find timeout in seconds.

    Returns:
        PerceptionResult with ok=True on success, ok=False on error.
    """
    start = time.time()

    # Ensure environment is ready
    if not ensure_environment():
        return PerceptionResult(ok=False, error="Environment check failed")

    # 1. Find window
    target_result = find_window(
        title=title,
        process_name=process,
        class_name=class_name,
        timeout=timeout,
    )

    if target_result is None:
        query = title or process or class_name or "unknown"
        return PerceptionResult(
            ok=False,
            error=f"window_not_found: Could not find window matching '{query}'",
            elapsed=time.time() - start,
        )

    target: WindowTarget = target_result
    target_info = target.info
    win = target.control

    logger.info(
        "Found via %s: %s (PID %d, class %s)",
        target.search_method, target_info.name, target_info.process_id, target_info.class_name,
    )

    # 2. UWP frame drilling
    if is_frame_window(target_info.class_name):
        logger.info("ApplicationFrameWindow detected — drilling")
        content = drill_frame(win)
        if content:
            win = content
            logger.info("Drilled to: %s", content.ClassName)
        else:
            logger.warning("Frame drilling failed — using frame")

    # 3. Get root patterns
    patterns = get_control_patterns(win)

    # 4. Walk tree
    max_depth = min(depth, 500)
    root_elem, truncated = element_to_dict(
        win, depth=0, max_depth=max_depth, from_patterns=patterns,
    )
    if truncated:
        logger.warning("Tree truncated at depth %d", max_depth)

    # 5. Summarize and classify
    summary = summarize_tree(root_elem)
    tier = classify_tier(summary)

    elapsed = time.time() - start

    # 6. Screenshot (optional)
    screenshot_path = None
    if screenshot and target_info.bounding_box:
        from ..capture.screenshot import capture_window
        screenshot_path = capture_window(
            target_info.bounding_box,
            target_info.hwnd,
            output_dir=str(Path(__file__).parents[2]),
        )

    # 7. Build result
    result = PerceptionResult(
        ok=True,
        target=target_info,
        tier=tier,
        summary=summary,
        tree=root_elem,
        screenshot_path=screenshot_path,
        elapsed=elapsed,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # 8. Write output file if requested
    if output_file:
        from ..schema import serialize_model
        snapshot = result.to_snapshot()
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(serialize_model(snapshot))
        logger.info("Saved snapshot to %s", output_path)

    logger.info(
        "PERCEIVE: %d elems, tier=%s (conf=%.2f), %.1fs",
        summary.total_elements, tier.tier, tier.confidence, elapsed,
    )

    return result


def list_windows_api(min_size: int = 100) -> List[WindowInfo]:
    """List all visible windows (programmatic API).

    Args:
        min_size: Minimum width/height to include (default 100).

    Returns:
        List of WindowInfo objects.
    """
    if not ensure_environment():
        return []
    return list_windows(min_size=(min_size, min_size))


# ---------------------------------------------------------------------------
# Convenience: tier-aware action routing
# ---------------------------------------------------------------------------

def tier_needs_vision(tier: TierClassification) -> bool:
    """Check if a tier classification needs vision fallback.

    Returns True for T2 (sparse) and T3 (opaque) apps.
    """
    return tier.tier in ("T2", "T3")


def tier_can_invoke(tier: TierClassification) -> bool:
    """Check if a tier classification supports direct UIA pattern invocation.

    Returns True for T1 and T1/T2 apps.
    """
    return tier.tier in ("T1", "T1/T2")
