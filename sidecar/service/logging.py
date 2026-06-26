"""
Hermes Eats World — Structured Logging
=======================================
JSON structured logging for machine-parseable output. Integrates with
the standard logging module so existing log calls just work.

Usage:
    from sidecar.service.logging import setup_structured_logging

    setup_structured_logging(level="INFO")
    logger = logging.getLogger(__name__)
    logger.info("Window found", extra={"target": "File Explorer", "pid": 1234})
    # Output: {"ts": "2026-01-15T...", "level": "INFO", "module": "...", "msg": "Window found", "target": "File Explorer", "pid": 1234}
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter. Each log line is a valid JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "func": record.funcName,
            "msg": record.getMessage(),
        }

        # Merge any extra fields from the record
        if hasattr(record, "target"):
            log_entry["target"] = record.target
        if hasattr(record, "pid"):
            log_entry["pid"] = record.pid
        if hasattr(record, "tier"):
            log_entry["tier"] = record.tier
        if hasattr(record, "elements"):
            log_entry["elements"] = record.elements
        if hasattr(record, "elapsed"):
            log_entry["elapsed"] = record.elapsed
        if hasattr(record, "error"):
            log_entry["error"] = record.error

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(
    level: str = "INFO",
    output: Optional[str] = None,
    console: bool = False,
) -> None:
    """Set up structured JSON logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        output: If set, write JSON logs to this file path.
        console: Also write JSON logs to stderr.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    root.handlers.clear()

    formatter = StructuredFormatter()

    # Console handler (stderr)
    if console:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # File handler
    if output:
        output_path = os.path.abspath(output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        handler = logging.FileHandler(output_path, encoding="utf-8")
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # If no handler configured, add console by default
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        root.addHandler(handler)


def setup_console_logging(level: str = "INFO", verbose: bool = False) -> None:
    """Set up human-readable console logging (default mode).

    Args:
        level: Log level.
        verbose: If True, use DEBUG level.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO))

    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
