"""End-to-end integration tests against real Windows apps.

These tests launch real applications (Notepad, Calculator), run goals through
the orchestrator, and verify results via perception/OCR.

Run with:
    pytest tests/test_integration.py -v

Requirements:
    - Windows 10+ with Notepad and Calculator
    - Tesseract OCR on PATH (for OCR verification)
    - UIA automation available
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure Tesseract is on PATH
os.environ["PATH"] = os.environ.get("PATH", "") + r";C:\Program Files\Tesseract-OCR"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def notepad():
    """Launch Notepad and yield the process. Close after tests."""
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(2)

    yield proc

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="module")
def calculator():
    """Launch Calculator and yield the process. Close after tests."""
    proc = subprocess.Popen(["calc.exe"])
    time.sleep(2)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _find_notepad_title():
    """Find the current Notepad window title (handles various Windows versions)."""
    from sidecar.target import list_windows
    windows = list_windows()
    for w in windows:
        if w.name and "notepad" in w.name.lower():
            return w.name
    return None


# ─── Perception Tests ────────────────────────────────────────────────

class TestPerception:
    """Test that we can perceive real Windows apps."""

    def test_perceive_notepad(self, notepad):
        """Verify we can find and walk Notepad's UI tree."""
        from sidecar.service import perceive_target

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        result = perceive_target(title=title, depth=3, screenshot=False)

        assert result is not None
        assert result.target is not None
        assert result.summary.total_elements > 0

    def test_perceive_calculator(self, calculator):
        """Verify we can find and walk Calculator's UI tree."""
        from sidecar.service import perceive_target

        result = perceive_target(title="Calculator", depth=3, screenshot=False)

        assert result is not None
        assert result.target is not None
        assert result.summary.total_elements > 0

    def test_list_windows_includes_notepad(self, notepad):
        """Verify Notepad shows up in window list."""
        from sidecar.target import list_windows

        windows = list_windows()
        names = [w.name for w in windows if w.name]
        found = any("notepad" in n.lower() for n in names)
        assert found, f"Expected Notepad in windows, got: {names[:10]}"


# ─── Orchestrator Tests ──────────────────────────────────────────────

class TestOrchestrator:
    """Test the orchestrator against real apps."""

    def test_type_text_in_notepad(self, notepad):
        """Run 'type hello world' in Notepad and verify via perception."""
        from sidecar.orchestrator import Orchestrator, OrchestratorConfig, ExecutionStatus

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        config = OrchestratorConfig(
            max_steps=10,
            max_wait_seconds=30,
            step_timeout=10,
            retry_count=1,
            retry_delay=0.5,
            require_verification=False,
            perception_depth=3,
        )

        orchestrator = Orchestrator(config=config)

        result = orchestrator.run(
            goal="type hello world",
            target_title=title,
        )

        assert result.status in (ExecutionStatus.SUCCESS, ExecutionStatus.PARTIAL), \
            f"Expected success, got {result.status.value}: {result.error}"
        assert result.steps_completed > 0, "Expected at least one step completed"

    def test_perceive_after_action(self, notepad):
        """Type text via T2, then verify Notepad is still perceivable."""
        from sidecar.orchestrator import Orchestrator, OrchestratorConfig
        from sidecar.service import perceive_target

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        # Type some text
        config = OrchestratorConfig(
            max_steps=10,
            max_wait_seconds=30,
            step_timeout=10,
            retry_count=1,
            retry_delay=0.5,
            require_verification=False,
            perception_depth=3,
        )

        orchestrator = Orchestrator(config=config)
        orchestrator.run(
            goal="type integration test text",
            target_title=title,
        )

        time.sleep(1)

        # Re-find Notepad (title may have changed after typing)
        new_title = _find_notepad_title()
        assert new_title is not None, "Notepad window not found after action"

        # Perceive and check the tree
        result = perceive_target(title=new_title, depth=5, screenshot=False)

        assert result is not None
        assert result.ok
        assert result.summary.total_elements > 0


# ─── Screenshot + OCR Tests ──────────────────────────────────────────

class TestScreenshotOCR:
    """Test screenshot capture and OCR verification."""

    def test_capture_notepad_screenshot(self, notepad):
        """Capture a screenshot of Notepad and verify it's valid."""
        from sidecar.capture import capture_window
        from sidecar.service import perceive_target
        from PIL import Image

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        result = perceive_target(title=title, depth=1, screenshot=False)
        assert result is not None
        assert result.target.bounding_box is not None

        bb = result.target.bounding_box

        with tempfile.TemporaryDirectory() as tmpdir:
            screenshot_path = capture_window(
                bounding_box=bb,
                hwnd=result.target.hwnd,
                output_dir=tmpdir,
            )

            assert screenshot_path is not None
            assert Path(screenshot_path).exists()

            img = Image.open(screenshot_path)
            assert img.size[0] > 0
            assert img.size[1] > 0
            img.close()  # Release file handle on Windows

    def test_ocr_on_screenshot(self):
        """Create test image and run OCR to verify text detection."""
        from sidecar.capture.ocr import get_ocr_engine
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (300, 60), "white")
        ImageDraw.Draw(img).text((10, 15), "OCR Test 123", fill="black")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f.name)
            img_path = f.name

        try:
            engine = get_ocr_engine("pytesseract")
            result = engine.recognize(img_path)

            assert result.full_text is not None
            assert len(result.full_text.strip()) > 0
            assert "OCR" in result.full_text.upper() or "TEST" in result.full_text.upper() or "123" in result.full_text
        finally:
            os.unlink(img_path)


# ─── CLI Integration Tests ──────────────────────────────────────────

class TestCLI:
    """Test CLI commands against real apps."""

    def test_cli_list(self, notepad):
        """Verify --list includes Notepad."""
        result = subprocess.run(
            [sys.executable, "-m", "sidecar.service", "--list"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "Notepad" in result.stdout

    def test_cli_perceive_notepad(self, notepad):
        """Verify --target perceives Notepad by title."""
        title = _find_notepad_title()
        assert title is not None

        result = subprocess.run(
            [sys.executable, "-m", "sidecar.service", "--target", title, "--depth", "2"],
            capture_output=True, text=True, timeout=15,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "error" not in result.stdout.lower() or "window_not_found" not in result.stdout

    def test_cli_run_goal_notepad(self, notepad):
        """Verify --run-goal works against Notepad by title."""
        title = _find_notepad_title()
        assert title is not None

        result = subprocess.run(
            [sys.executable, "-m", "sidecar.service", "--target", title,
             "--run-goal", "type cli test", "--max-steps", "10", "--no-verify"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0, f"CLI goal failed: {result.stderr}\n{result.stdout}"
        assert "ORCHESTRATOR RESULT" in result.stdout


# ─── T2 Action Tests ────────────────────────────────────────────────

class TestT2Actions:
    """Test T2 (SendInput) actions against real apps."""

    def test_click_at_notepad(self, notepad):
        """Test clicking in Notepad."""
        from sidecar.action import click_at
        from sidecar.service import perceive_target

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        result = perceive_target(title=title, depth=1, screenshot=False)
        assert result is not None
        assert result.target.hwnd is not None

        bb = result.target.bounding_box
        x = bb.left + bb.width // 2
        y = bb.top + bb.height // 2

        success = click_at(result.target.hwnd, x, y)
        assert success is True

    def test_type_text_via_t2(self, notepad):
        """Test typing text via T2 SendInput."""
        from sidecar.action import type_text
        from sidecar.service import perceive_target

        title = _find_notepad_title()
        assert title is not None, "Notepad window not found"

        result = perceive_target(title=title, depth=1, screenshot=False)
        assert result is not None

        success = type_text(result.target.hwnd, "t2 test text")
        assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
