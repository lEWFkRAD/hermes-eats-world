"""
Hermes Eats World — Explicit JSON Encoder
==========================================
No `default=str` — we serialize everything explicitly through Pydantic models.
This module provides serialization utilities that raise on unexpected types.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from .models import TreeSnapshot, ErrorResponse, WindowInfo, HealthResponse


class HermesEncoder(json.JSONEncoder):
    """Custom JSON encoder that raises on unexpected types.
    
    Unlike `default=str`, this explicitly handles known non-standard types
    and raises TypeError for anything unexpected — no silent data corruption.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        # Raise on anything unexpected — DO NOT fall back to str()
        raise TypeError(f"Cannot serialize type {type(obj).__name__}: {obj!r}")


def serialize_model(model) -> str:
    """Serialize a Pydantic model to pretty JSON. Always uses explicit models,
    never `default=str`. Raises ValueError if serialization fails."""
    try:
        return model.model_dump_json(indent=2)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Serialization failed: {e}") from e


def serialize_dict(data: Dict[str, Any]) -> str:
    """Serialize a plain dict with the strict encoder.
    
    Raises TypeError on non-serializable types instead of silently
    converting them to garbage strings.
    """
    return json.dumps(data, indent=2, cls=HermesEncoder)


def make_success(data: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap data in a success response envelope."""
    return {
        "status": "success",
        "data": data,
    }


def make_error(
    error: str,
    message: str,
    target: Optional[str] = None,
    retryable: bool = False,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Create and serialize a structured error response."""
    err = ErrorResponse(
        error=error,
        message=message,
        target=target,
        retryable=retryable,
        details=details,
    )
    return serialize_model(err)
