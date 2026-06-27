"""
Hermes Eats World — Path Validation & Security
================================================
Path validation for output paths to prevent path traversal and writing
to sensitive system locations.

Usage:
    from sidecar.security import validate_output_path, sanitize_path

    safe_path = validate_output_path("/tmp/output/snapshot.json")
    # Raises ValueError if path escapes allowed directories
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


# Paths that are NEVER allowed for output
_FORBIDDEN_PATHS: Set[Path] = set()


def _get_forbidden_paths() -> Set[Path]:
    """Get the set of forbidden output path prefixes (lazy init)."""
    global _FORBIDDEN_PATHS
    if _FORBIDDEN_PATHS:
        return _FORBIDDEN_PATHS

    _FORBIDDEN_PATHS = {
        Path.home() / ".ssh",
        Path.home() / ".azure",
    }

    # Windows-specific
    try:
        _FORBIDDEN_PATHS.update([
            Path("C:/Windows"),
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path("C:/ProgramData"),
            Path("C:/Users/OnyxB/.hermes"),  # Don't overwrite Hermes config
        ])
    except (OSError, ValueError):
        pass

    return _FORBIDDEN_PATHS


def sanitize_path(path_str: str) -> Path:
    """Sanitize a path string by resolving it and removing traversal sequences.

    Args:
        path_str: The input path string.

    Returns:
        A resolved Path object with traversal sequences removed.

    Raises:
        ValueError: If the path is empty or null bytes are detected.
    """
    if not path_str:
        raise ValueError("Path cannot be empty")

    if "\x00" in path_str:
        raise ValueError("Null bytes detected in path")

    # Resolve the path (expands ~, .., symlinks)
    path = Path(path_str).expanduser().resolve()

    # Check against forbidden paths
    for forbidden in _get_forbidden_paths():
        try:
            path.relative_to(forbidden)
        except ValueError:
            continue
        raise ValueError(f"Access denied to forbidden path: {forbidden}")

    return path


def validate_output_path(path_str: str, allowed_base: Optional[str] = None) -> Path:
    """Validate an output path is safe to write to.

    Args:
        path_str: The output path to validate.
        allowed_base: If set, the output path must be under this directory.

    Returns:
        The resolved, validated Path.

    Raises:
        ValueError: If the path is invalid, contains traversal, or
            escapes allowed directories.
    """
    sanitized = sanitize_path(path_str)

    # Check against forbidden paths
    for forbidden in _get_forbidden_paths():
        try:
            sanitized.relative_to(forbidden)
        except ValueError:
            # Not under this forbidden path — try next
            continue
        # If we get here, it IS under a forbidden path
        raise ValueError(
            f"Output path is under forbidden directory: {forbidden}"
        )

    # Check against allowed base if specified
    if allowed_base:
        base = Path(allowed_base).expanduser().resolve()
        try:
            sanitized.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Output path {sanitized} is not under allowed base {base}"
            )

    # Ensure parent directory exists and is writable
    parent = sanitized.parent
    if not parent.exists():
        logger.info("Creating output directory: %s", parent)
        parent.mkdir(parents=True, exist_ok=True)

    return sanitized


def validate_screenshot_path(path_str: str, allowed_base: Optional[str] = None) -> Path:
    """Validate a screenshot output path.

    Same as validate_output_path but also ensures the file extension
    is an image format.

    Args:
        path_str: The screenshot path to validate.
        allowed_base: If set, the path must be under this directory.

    Returns:
        The validated Path.

    Raises:
        ValueError: If the path is invalid or has an unsupported extension.
    """
    validated = validate_output_path(path_str, allowed_base)

    allowed_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
    if validated.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"Screenshot path must have an image extension: {allowed_extensions}. "
            f"Got: {validated.suffix}"
        )

    return validated
