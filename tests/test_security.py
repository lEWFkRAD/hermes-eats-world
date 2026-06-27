"""Tests for sidecar.security — Path validation & security."""

import pytest
from pathlib import Path

from sidecar.security import (
    sanitize_path,
    validate_output_path,
    validate_screenshot_path,
)


class TestSanitizePath:
    """Test path sanitization."""

    def test_basic_path(self):
        result = sanitize_path("./output/test.txt")
        assert isinstance(result, Path)
        assert result.name == "test.txt"

    def test_expands_tilde(self):
        result = sanitize_path("~/test.txt")
        assert "~" not in str(result)

    def test_empty_path_raises(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_path("")

    def test_null_bytes_raises(self):
        with pytest.raises(ValueError, match="Null bytes"):
            sanitize_path("test\x00.txt")


class TestValidateOutputPath:
    """Test output path validation."""

    def test_valid_relative_path(self, tmp_path):
        target = tmp_path / "output" / "test.txt"
        result = validate_output_path(str(target), allowed_base=str(tmp_path))
        assert result == target

    def test_valid_absolute_path(self, tmp_path):
        target = tmp_path / "data.json"
        result = validate_output_path(str(target))
        assert result == target

    def test_escapes_allowed_base_raises(self, tmp_path):
        # Path outside the allowed base
        outside = Path.home() / "outside.txt"
        with pytest.raises(ValueError):
            validate_output_path(str(outside), allowed_base=str(tmp_path))

    def test_creates_parent_dir(self, tmp_path):
        target = tmp_path / "nested" / "deep" / "file.txt"
        result = validate_output_path(str(target), allowed_base=str(tmp_path))
        assert result.parent.exists()

    def test_forbidden_ssh_raises(self):
        ssh_path = Path.home() / ".ssh" / "id_rsa"
        with pytest.raises(ValueError, match="forbidden"):
            validate_output_path(str(ssh_path))


class TestValidateScreenshotPath:
    """Test screenshot path validation."""

    def test_png_allowed(self, tmp_path):
        target = tmp_path / "screenshot.png"
        result = validate_screenshot_path(str(target))
        assert result.suffix.lower() == ".png"

    def test_jpg_allowed(self, tmp_path):
        target = tmp_path / "screenshot.jpg"
        result = validate_screenshot_path(str(target))
        assert result.suffix.lower() == ".jpg"

    def test_webp_allowed(self, tmp_path):
        target = tmp_path / "screenshot.webp"
        result = validate_screenshot_path(str(target))
        assert result.suffix.lower() == ".webp"

    def test_txt_raises(self, tmp_path):
        target = tmp_path / "screenshot.txt"
        with pytest.raises(ValueError, match="image extension"):
            validate_screenshot_path(str(target))

    def test_no_extension_raises(self, tmp_path):
        target = tmp_path / "screenshot"
        with pytest.raises(ValueError, match="image extension"):
            validate_screenshot_path(str(target))

    def test_forbidden_path_raises(self):
        ssh_path = Path.home() / ".ssh" / "screenshot.png"
        with pytest.raises(ValueError, match="forbidden"):
            validate_screenshot_path(str(ssh_path))
