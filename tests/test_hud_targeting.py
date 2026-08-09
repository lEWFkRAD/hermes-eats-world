import argparse

import pytest

from sidecar.service.cli import parse_window_id
from sidecar.target import finder


class FakeWindow:
    Name = "Notes"
    ClassName = "Notepad"
    ProcessId = 42
    NativeWindowHandle = 123456
    AutomationId = ""
    IsEnabled = True

    class BoundingRectangle:
        left = 10
        top = 20

        @staticmethod
        def width():
            return 800

        @staticmethod
        def height():
            return 600

    def __init__(self, exists=True):
        self.exists = exists

    def Exists(self, _wait_seconds, _timeout_seconds):
        return self.exists


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("123456", 123456), ("0x1E240", 123456), ("0X1e240", 123456)],
)
def test_parse_window_id_accepts_hermes_decimal_and_windows_hex(raw, expected):
    assert parse_window_id(raw) == expected


@pytest.mark.parametrize("raw", ["0", "-1", "not-a-handle", "0xZZ"])
def test_parse_window_id_rejects_invalid_handles(raw):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_window_id(raw)


def test_find_window_uses_exact_hud_window_id(monkeypatch):
    window = FakeWindow()
    seen = []

    def control_from_handle(hwnd):
        seen.append(hwnd)
        return window

    monkeypatch.setattr(finder.uiautomation, "ControlFromHandle", control_from_handle)

    target = finder.find_window(hwnd=123456)

    assert seen == [123456]
    assert target is not None
    assert target.hwnd == 123456
    assert target.name == "Notes"


def test_invalid_hud_window_id_fails_closed_without_weaker_fallback(monkeypatch):
    monkeypatch.setattr(
        finder.uiautomation,
        "ControlFromHandle",
        lambda _hwnd: FakeWindow(exists=False),
    )

    def unexpected_title_lookup(**_kwargs):
        raise AssertionError("must not fall back to a title match")

    monkeypatch.setattr(finder.uiautomation, "WindowControl", unexpected_title_lookup)

    assert finder.find_window(hwnd=123456, title="Notes") is None


def test_exact_lookup_rejects_a_mismatched_native_handle(monkeypatch):
    window = FakeWindow()
    window.NativeWindowHandle = 654321
    monkeypatch.setattr(finder.uiautomation, "ControlFromHandle", lambda _hwnd: window)

    assert finder.find_window(hwnd=123456) is None
