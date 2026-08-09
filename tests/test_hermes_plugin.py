import json

from sidecar.hermes_plugin import TOOL_NAME, handle_uia_perceive_window, register
from sidecar.schema import BoundingBox, TargetInfo
from sidecar.service.isolation import IsolatedResult


class FakeContext:
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.registration = None

    def register_tool(self, **kwargs):
        self.registration = kwargs


def test_registers_a_profile_bound_read_only_tool():
    work = FakeContext("work")
    personal = FakeContext("personal")

    register(work)
    register(personal)

    assert work.registration["name"] == TOOL_NAME
    assert work.registration["toolset"] == "hermes_eats_world"
    assert work.registration["schema"]["parameters"]["required"] == ["window_id"]
    assert work.registration["handler"].keywords["profile_name"] == "work"
    assert personal.registration["handler"].keywords["profile_name"] == "personal"


def test_tool_response_is_profile_scoped_and_redacted(monkeypatch):
    target = TargetInfo(
        name="Editor",
        class_name="EditorWindow",
        process_id=42,
        bounding_box=BoundingBox(left=0, top=0, width=800, height=600),
        hwnd=123456,
    )
    seen = {}

    monkeypatch.setattr("sidecar.hermes_plugin.check_uia_available", lambda: True)
    monkeypatch.setattr("sidecar.service.env_check.set_dpi_awareness", lambda: None)
    monkeypatch.setattr("sidecar.target.find_window", lambda **_kwargs: target)

    def fake_run_isolated(_function, request, *, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return IsolatedResult(
            status="success",
            value={
                "tree": {
                    "id": "root",
                    "control_type": "WindowControl",
                    "localized_type": "window",
                    "name": "Editor",
                    "children": [],
                },
                "summary": {"total_elements": 1, "max_depth": 0},
                "tier": {
                    "tier": "T1",
                    "label": "Rich UIA tree",
                    "confidence": 1.0,
                },
                "truncated": False,
            },
        )

    monkeypatch.setattr("sidecar.service.isolation.run_isolated", fake_run_isolated)

    result = json.loads(
        handle_uia_perceive_window(
            {"window_id": 123456, "depth": 4, "max_elements": 250, "timeout": 8},
            profile_name="work",
        )
    )

    assert result["hermes_profile"] == "work"
    assert result["redacted"] is True
    assert result["snapshot"]["target"]["hwnd"] == 123456
    assert result["snapshot"]["screenshot_path"] is None
    assert seen["request"]["include_raw_values"] is False
    assert seen["request"]["max_depth"] == 4
    assert seen["request"]["max_elements"] == 250
    assert seen["timeout"] == 9


def test_tool_fails_closed_when_exact_window_is_missing(monkeypatch):
    monkeypatch.setattr("sidecar.hermes_plugin.check_uia_available", lambda: True)
    monkeypatch.setattr("sidecar.service.env_check.set_dpi_awareness", lambda: None)
    monkeypatch.setattr("sidecar.target.find_window", lambda **_kwargs: None)

    result = json.loads(
        handle_uia_perceive_window({"window_id": 77}, profile_name="personal")
    )

    assert result == {
        "hermes_profile": "personal",
        "error": "window_not_found",
        "message": "Could not attach to exact window id 77.",
        "retryable": True,
    }


def test_tool_rejects_invalid_bounds_without_touching_uia():
    result = json.loads(
        handle_uia_perceive_window(
            {"window_id": 12, "depth": 11},
            profile_name="work",
        )
    )

    assert result["hermes_profile"] == "work"
    assert result["error"] == "invalid_arguments"
