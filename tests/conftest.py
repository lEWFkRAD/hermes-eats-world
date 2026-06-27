"""Shared test fixtures for the sidecar test suite."""

import pytest


@pytest.fixture(autouse=True)
def reset_forbidden_paths():
    """Reset the lazy-initialized _FORBIDDEN_PATHS global before each test."""
    from sidecar import security
    security._FORBIDDEN_PATHS = set()
    yield
    security._FORBIDDEN_PATHS = set()


@pytest.fixture(autouse=True)
def reset_config():
    """Reset the config singleton before each test."""
    from sidecar import config
    config._config_instance = None
    yield
    config._config_instance = None
