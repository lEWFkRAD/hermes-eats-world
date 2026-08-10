import io
import sys

from sidecar import plugin_worker
from sidecar.schema import BoundingBox, TargetInfo


def target(hwnd=123, process_id=42):
    return TargetInfo(
        name="Editor",
        class_name="EditorWindow",
        process_id=process_id,
        bounding_box=BoundingBox(left=0, top=0, width=800, height=600),
        hwnd=hwnd,
    )


def request(**overrides):
    result = {
        "window_id": 123,
        "mode": "tree",
        "depth": 3,
        "max_elements": 500,
        "max_output_bytes": 131072,
        "timeout": 10,
    }
    result.update(overrides)
    return result


def payload(name="Editor"):
    return {
        "tree": {
            "id": "root",
            "control_type": "WindowControl",
            "localized_type": "window",
            "name": name,
            "automation_id": "editor",
            "children": [],
        },
        "summary": {"total_elements": 1, "max_depth": 0},
        "tier": {"tier": "T1", "label": "Rich UIA tree", "confidence": 1.0},
        "truncated": False,
    }


def test_worker_returns_explicit_redaction_metadata(monkeypatch):
    monkeypatch.setattr(plugin_worker, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(plugin_worker, "find_window", lambda **_kwargs: target())
    monkeypatch.setattr(plugin_worker, "perceive_hwnd", lambda _request: payload())

    result = plugin_worker.perceive_request(request())

    assert result["sensitive_artifact"] is True
    assert result["redaction"]["password_controls"] is True
    assert result["redaction"]["element_names"] is False
    assert result["snapshot"]["target"]["hwnd"] == 123
    assert result["output_bytes"] > 0


def test_summary_mode_omits_tree(monkeypatch):
    monkeypatch.setattr(plugin_worker, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(plugin_worker, "find_window", lambda **_kwargs: target())
    monkeypatch.setattr(plugin_worker, "perceive_hwnd", lambda _request: payload())

    result = plugin_worker.perceive_request(request(mode="summary"))

    assert "tree" not in result["snapshot"]
    assert result["snapshot"]["summary"]["total_elements"] == 1


def test_worker_fails_closed_on_output_budget(monkeypatch):
    monkeypatch.setattr(plugin_worker, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(plugin_worker, "find_window", lambda **_kwargs: target())
    monkeypatch.setattr(
        plugin_worker,
        "perceive_hwnd",
        lambda _request: payload(name="sensitive " * 500),
    )

    result = plugin_worker.perceive_request(request(max_output_bytes=500))

    assert result["error"] == "output_budget_exceeded"
    assert "sensitive sensitive" not in str(result)
    assert result["suggested_parameters"]["mode"] == "summary"


def test_worker_rejects_different_exact_handle(monkeypatch):
    monkeypatch.setattr(plugin_worker, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(plugin_worker, "find_window", lambda **_kwargs: target(hwnd=999))

    result = plugin_worker.perceive_request(request())

    assert result["error"] == "window_not_found"


def test_worker_stdout_is_ascii_safe_json(monkeypatch):
    stdin = io.StringIO('{"window_id": 123}')
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(
        plugin_worker,
        "perceive_request",
        lambda _request: {"label": "Opaque — vision only"},
    )

    assert plugin_worker.main() == 0
    assert "\\u2014" in stdout.getvalue()
