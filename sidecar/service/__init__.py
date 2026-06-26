"""Hermes Eats World — Service module.

Provides:
- perceive_target(): Unified perception API with auto T1/T2/T3 selection
- list_windows_api(): List visible windows
- CLI entry point (python -m sidecar.service)
"""

from .service import (
    PerceptionResult,
    ensure_environment,
    perceive_target,
    list_windows_api,
    tier_needs_vision,
    tier_can_invoke,
)

__all__ = [
    "PerceptionResult",
    "ensure_environment",
    "perceive_target",
    "list_windows_api",
    "tier_needs_vision",
    "tier_can_invoke",
]
