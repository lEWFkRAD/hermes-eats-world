"""
Hermes Eats World — Configuration Management
=============================================
Centralized configuration using pydantic-settings. Loads from environment
variables, .env files, and defaults.

Usage:
    from sidecar.config import SidecarConfig

    config = SidecarConfig()
    print(config.ws_host, config.ws_port)

Environment variables (prefix SIDECAR_):
    SIDECAR_WS_HOST        WebSocket bind address (default: 127.0.0.1)
    SIDECAR_WS_PORT        WebSocket bind port (default: 8765)
    SIDECAR_WS_TOKEN       Auth token for WebSocket clients
    SIDECAR_MAX_DEPTH      Default tree walk depth (default: 3)
    SIDECAR_MAX_STEPS      Default orchestrator max steps (default: 20)
    SIDECAR_LOG_LEVEL      Logging level (default: INFO)
    SIDECAR_OUTPUT_DIR     Default output directory for screenshots/snapshots
    SIDECAR_TIMEOUT        Default window find timeout (default: 5)
    SIDECAR_REQUEST_TIMEOUT WebSocket request timeout (default: 120)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SidecarConfig(BaseSettings):
    """Central configuration for the sidecar.

    All settings can be overridden via environment variables with the
    SIDECAR_ prefix (e.g., SIDECAR_WS_PORT=9000). A .env file in the
    project root is also supported.
    """

    model_config = SettingsConfigDict(
        env_prefix="SIDECAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── WebSocket Server ──────────────────────────────────────────
    ws_host: str = Field(default="127.0.0.1", description="WebSocket bind address")
    ws_port: int = Field(default=8765, ge=1, le=65535, description="WebSocket bind port")
    ws_token: Optional[str] = Field(default=None, description="Auth token for WebSocket clients")
    ws_max_connections: int = Field(default=5, ge=1, le=20, description="Max concurrent WebSocket connections")
    ws_request_timeout: float = Field(default=120.0, gt=0, description="Per-request timeout in seconds")

    # ─── Perception ────────────────────────────────────────────────
    max_depth: int = Field(default=3, ge=1, le=500, description="Default tree walk depth")
    timeout: float = Field(default=5.0, gt=0, description="Window find timeout in seconds")

    # ─── Orchestrator ──────────────────────────────────────────────
    max_steps: int = Field(default=20, ge=1, description="Default orchestrator max steps")
    step_timeout: float = Field(default=15.0, gt=0, description="Timeout per step in seconds")
    retry_count: int = Field(default=2, ge=0, description="Retries per failed step")
    retry_delay: float = Field(default=1.0, ge=0, description="Delay between retries")
    require_verification: bool = Field(default=True, description="Verify after each step")

    # ─── Output ────────────────────────────────────────────────────
    output_dir: str = Field(
        default="./output",
        description="Default output directory for screenshots and snapshots",
    )

    # ─── Logging ───────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level")
    json_logs: bool = Field(default=False, description="Use structured JSON log output")

    # ─── Validation ────────────────────────────────────────────────
    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        """Validate and resolve the output directory path."""
        path = Path(v).expanduser().resolve()
        # Prevent writing to sensitive system paths
        sensitive_prefixes = [
            Path("/"),
            Path("C:/Windows"),
            Path("/c/Windows"),
            Path("C:/Program Files"),
            Path("/c/Program Files"),
            Path("C:/ProgramData"),
            Path("/c/ProgramData"),
        ]
        for prefix in sensitive_prefixes:
            try:
                path.relative_to(prefix)
                raise ValueError(f"Output directory cannot be under {prefix}")
            except ValueError as e:
                if "Output directory cannot be" in str(e):
                    raise
        return str(path)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid}")
        return v.upper()

    def to_dict(self) -> dict:
        """Export config as a plain dict."""
        return self.model_dump()


# Module-level singleton
_config: Optional[SidecarConfig] = None


def get_config() -> SidecarConfig:
    """Get the global SidecarConfig instance (lazy initialization)."""
    global _config
    if _config is None:
        _config = SidecarConfig()
    return _config


def set_config(config: SidecarConfig):
    """Replace the global config (useful for tests)."""
    global _config
    _config = config


def reset_config():
    """Reset the global config (useful for tests)."""
    global _config
    _config = None


def apply_logging(config: Optional[SidecarConfig] = None):
    """Apply logging configuration from the SidecarConfig."""
    cfg = config or get_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
