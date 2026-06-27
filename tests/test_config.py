"""Tests for sidecar.config — Configuration management."""

import pytest

from sidecar.config import SidecarConfig, get_config, set_config, reset_config


class TestSidecarConfig:
    """Test default values and validation."""

    def test_defaults(self):
        config = SidecarConfig()
        assert config.ws_host == "127.0.0.1"
        assert config.ws_port == 8765
        assert config.ws_token is None
        assert config.ws_max_connections == 5
        assert config.ws_request_timeout == 120.0
        assert config.max_depth == 3
        assert config.max_steps == 20
        assert config.timeout == 5.0
        assert config.log_level == "INFO"
        assert config.json_logs is False

    def test_ws_port_range(self):
        with pytest.raises(Exception):
            SidecarConfig(ws_port=0)
        with pytest.raises(Exception):
            SidecarConfig(ws_port=70000)

    def test_log_level_validation(self):
        config = SidecarConfig(log_level="debug")
        assert config.log_level == "DEBUG"
        with pytest.raises(Exception, match="Invalid log level"):
            SidecarConfig(log_level="INVALID")

    def test_output_dir_validation(self):
        config = SidecarConfig(output_dir="./output")
        assert config.output_dir is not None

    def test_to_dict(self):
        config = SidecarConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert "ws_host" in d
        assert "ws_port" in d

    def test_model_dump(self):
        config = SidecarConfig(ws_port=9999)
        d = config.model_dump()
        assert d["ws_port"] == 9999


class TestConfigSingleton:
    """Test the global config singleton."""

    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_get_config_creates_instance(self):
        cfg = get_config()
        assert isinstance(cfg, SidecarConfig)

    def test_get_config_returns_same_instance(self):
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_set_config(self):
        custom = SidecarConfig(ws_port=9999)
        set_config(custom)
        assert get_config().ws_port == 9999

    def test_reset_config(self):
        get_config()  # warm up
        reset_config()
        cfg = get_config()
        assert cfg.ws_port == 8765  # back to default


class TestConfigEnv:
    """Test environment variable overrides."""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SIDECAR_WS_PORT", "9999")
        monkeypatch.setenv("SIDECAR_LOG_LEVEL", "DEBUG")
        cfg = SidecarConfig()
        assert cfg.ws_port == 9999
        assert cfg.log_level == "DEBUG"
