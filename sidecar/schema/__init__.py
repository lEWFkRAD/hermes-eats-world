"""Hermes Eats World — Schema module."""

from .encoder import HermesEncoder, make_error, make_success, serialize_dict, serialize_model
from .models import (
    SCHEMA_VERSION,
    BoundingBox,
    Element,
    ErrorResponse,
    HealthResponse,
    TargetInfo,
    TierClassification,
    TreeSnapshot,
    TreeSummary,
    WindowInfo,
)

__all__ = [
    "BoundingBox",
    "Element",
    "ErrorResponse",
    "HermesEncoder",
    "HealthResponse",
    "SCHEMA_VERSION",
    "TreeSnapshot",
    "TreeSummary",
    "TierClassification",
    "TargetInfo",
    "WindowInfo",
    "make_error",
    "make_success",
    "serialize_dict",
    "serialize_model",
]
