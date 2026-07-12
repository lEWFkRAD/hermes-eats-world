"""
Hermes Eats World — Schema Models
=================================
Pydantic models for all structured output. These are the source of truth
for the JSON contract between the sidecar and Hermes.

Schema versioning: Bump SCHEMA_VERSION on breaking changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


# ─── Bounding Box ────────────────────────────────────────────────


class BoundingBox(BaseModel):
    """Pixel coordinates of a UI element."""

    model_config = ConfigDict(frozen=True)

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


# ─── Control Patterns ────────────────────────────────────────────


class InvokePattern(BaseModel):
    supported: bool = True


class ValuePattern(BaseModel):
    supported: bool = True
    value: str = ""
    readonly: bool = False


class TogglePattern(BaseModel):
    supported: bool = True
    state: int = 0  # 0=Off, 1=On, 2=Indeterminate


class SelectionPattern(BaseModel):
    supported: bool = True


class ExpandCollapsePattern(BaseModel):
    supported: bool = True
    state: int = 0  # 0=Collapsed, 1=Expanded, 2=Partial, 3=LeafNode


class ScrollPattern(BaseModel):
    supported: bool = True
    horizontally_scrollable: bool = False
    vertically_scrollable: bool = False


class TransformPattern(BaseModel):
    supported: bool = True
    can_move: bool = False
    can_resize: bool = False
    can_rotate: bool = False


class WindowPattern(BaseModel):
    supported: bool = True
    can_maximize: bool = False
    can_minimize: bool = False
    is_modal: bool = False
    is_topmost: bool = False
    window_state: int = 0  # 0=Collapsed, 1=Normal, 2=Maximized


class SelectionItemPattern(BaseModel):
    supported: bool = True
    is_selected: bool = False


class GridPattern(BaseModel):
    supported: bool = True
    row_count: int = 0
    column_count: int = 0


class TextPattern(BaseModel):
    supported: bool = True


class ScrollItemPattern(BaseModel):
    supported: bool = True


class DockPattern(BaseModel):
    supported: bool = True
    dock: int = 0  # 0=None, 1=Top, 2=Left, 3=Bottom, 4=Right, 5=Fill


# ─── UI Element ──────────────────────────────────────────────────


class Element(BaseModel):
    """A single UI element in the accessibility tree."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Stable element ID for cross-snapshot correlation")
    control_type: str = Field(description="UIA control type name (e.g. 'ButtonControl')")
    localized_type: str = Field(description="Human-readable control type (e.g. 'button')")
    name: str = Field(default="", description="Element name (truncated to 200 chars)")
    automation_id: str = Field(default="", description="UIA AutomationId")
    class_name: str = Field(default="", description="Window class name")
    hwnd: Optional[int] = Field(default=None, description="Native HWND for T2 PostMessage actions")
    is_enabled: bool = True
    is_offscreen: bool = False
    bounding_box: Optional[BoundingBox] = None
    depth: int = 0
    patterns: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Available control patterns and their state",
    )
    children: List[Element] = Field(default_factory=list)
    truncated: bool = Field(
        default=False,
        description="True if children were truncated due to depth limit",
    )


# ─── Tree Summary ────────────────────────────────────────────────


class TreeSummary(BaseModel):
    """Aggregate statistics about the UIA tree."""

    total_elements: int = 0
    max_depth: int = 0
    control_types: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each control type, sorted descending",
    )
    control_patterns: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each pattern type found, sorted descending",
    )


# ─── Tier Classification ────────────────────────────────────────


class TierClassification(BaseModel):
    """Perception tier with confidence score and supporting evidence."""

    tier: str = Field(
        description="T1 = Rich tree, T1/T2 = Partial, T2 = Sparse/Vision primary",
    )
    label: str = Field(description="Human-readable tier description")
    confidence: float = Field(ge=0.0, le=1.0, description="0.0-1.0 confidence")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting data: element_count, unique_pattern_types, etc.",
    )


# ─── Target Info ─────────────────────────────────────────────────


class TargetInfo(BaseModel):
    """Information about the targeted window."""

    name: str
    class_name: str = ""
    process_id: int = 0
    bounding_box: Optional[BoundingBox] = None
    hwnd: Optional[int] = None


# ─── Tree Snapshot (root response) ──────────────────────────────


class TreeSnapshot(BaseModel):
    """Complete structured snapshot of a window's UI state."""

    schema_version: str = SCHEMA_VERSION
    target: TargetInfo
    tier: TierClassification
    summary: TreeSummary
    tree: Element
    screenshot_path: Optional[str] = None
    timestamp: str = Field(description="ISO 8601 UTC timestamp")


# ─── Window List Item ────────────────────────────────────────────


class WindowInfo(BaseModel):
    """A single window from the window list."""

    name: str
    class_name: str = ""
    automation_id: str = ""
    process_id: int = 0
    bounding_box: Optional[BoundingBox] = None
    is_enabled: bool = True


# ─── Error Response ──────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Structured error response for API consumers."""

    error: str = Field(description="Error code (machine-readable)")
    message: str = Field(description="Human-readable error description")
    target: Optional[str] = None
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


# ─── Health Check ────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"  # ok, degraded, error
    version: str = SCHEMA_VERSION
    uptime_seconds: float = 0.0
    warnings: List[str] = Field(default_factory=list)
