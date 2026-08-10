import json

from sidecar import hermes_plugin
from sidecar.hermes_plugin import TOOL_NAME, handle_uia_perceive_window, register


class FakeContext:
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.registration = None
        self.cli_registration = None

    def register_tool(self, **kwargs):
        self.registration = kwargs

    def register_cli_command(self, **kwargs):
        self.cli_registration = kwargs


def test_registers_profile_bound_tool_and_setup_command():
    work = FakeContext("work")
    personal = FakeContext("personal")

    register(work)
    register(personal)

    assert work.registration["name"] == TOOL_NAME
    assert work.registration["toolset"] == "hermes_eats_world"
    assert work.registration["schema"]["parameters"]["required"] == ["window_id"]
    assert work.registration["handler"].keywords["profile_name"] == "work"
    assert personal.registration["handler"].keywords["profile_name"] == "personal"
    assert work.cli_registration["name"] == "heaw"
    assert work.cli_registration["handler_fn"] is hermes_plugin.handle_cli


def test_tool_response_is_profile_scoped_and_privacy_is_explicit(monkeypatch):
    seen = {}
    monkeypatch.setattr(hermes_plugin, "runtime_available", lambda: True)

    def fake_worker(request, *, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return {
            "sensitive_artifact": True,
            "redaction": {
                "value_patterns": True,
                "password_controls": True,
                "element_names": False,
                "automation_ids": False,
            },
            "snapshot": {"target": {"hwnd": 123456}},
        }

    monkeypatch.setattr(hermes_plugin, "run_runtime_worker", fake_worker)

    result = json.loads(
        handle_uia_perceive_window(
            {
                "window_id": 123456,
                "depth": 4,
                "max_elements": 250,
                "max_output_bytes": 65536,
                "timeout": 8,
            },
            profile_name="work",
        )
    )

    assert result["hermes_profile"] == "work"
    assert result["sensitive_artifact"] is True
    assert result["redaction"]["value_patterns"] is True
    assert result["redaction"]["element_names"] is False
    assert "redacted" not in result
    assert seen["request"]["depth"] == 4
    assert seen["request"]["max_elements"] == 250
    assert seen["request"]["max_output_bytes"] == 65536
    assert seen["timeout"] == 10


def test_tool_requires_profile_runtime(monkeypatch):
    monkeypatch.setattr(hermes_plugin, "runtime_available", lambda: False)

    result = json.loads(
        handle_uia_perceive_window({"window_id": 77}, profile_name="personal")
    )

    assert result["error"] == "runtime_unavailable"
    assert "hermes profile use personal" in result["message"]
    assert "hermes heaw setup" in result["message"]


def test_tool_rejects_invalid_bounds_before_runtime_check():
    result = json.loads(
        handle_uia_perceive_window(
            {"window_id": 12, "depth": 11},
            profile_name="work",
        )
    )

    assert result["hermes_profile"] == "work"
    assert result["error"] == "invalid_arguments"


def test_tool_rejects_parallel_scan(monkeypatch):
    class BusySlot:
        def acquire(self, *, blocking):
            assert blocking is False
            return False

        def release(self):  # pragma: no cover - must not be called
            raise AssertionError("busy slot cannot be released")

    monkeypatch.setattr(hermes_plugin, "runtime_available", lambda: True)
    monkeypatch.setattr(hermes_plugin, "_SCAN_SLOT", BusySlot())

    result = json.loads(handle_uia_perceive_window({"window_id": 12}, profile_name="work"))

    assert result["error"] == "scan_in_progress"
    assert result["retryable"] is True
