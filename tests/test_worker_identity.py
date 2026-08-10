import pytest

from sidecar.schema import Element, TierClassification, TreeSummary
from sidecar.service import worker


class FakeControl:
    def __init__(self, hwnd=123, process_id=42):
        self.NativeWindowHandle = hwnd
        self.ProcessId = process_id

    def Exists(self, *_args):
        return True


def request(**overrides):
    result = {
        "hwnd": 123,
        "class_name": "EditorWindow",
        "expected_process_id": 42,
        "max_depth": 1,
        "include_raw_values": False,
        "max_elements": 10,
        "timeout": 2,
    }
    result.update(overrides)
    return result


def stub_tree(monkeypatch):
    root = Element(id="root", control_type="WindowControl", localized_type="window")
    monkeypatch.setattr(worker, "element_to_dict", lambda *_a, **_k: (root, False))
    monkeypatch.setattr(worker, "summarize_tree", lambda _root: TreeSummary(total_elements=1))
    monkeypatch.setattr(
        worker,
        "classify_tier",
        lambda _summary: TierClassification(tier="T1", label="Rich", confidence=1.0),
    )
    monkeypatch.setattr(worker, "is_frame_window", lambda _name: False)


def test_worker_revalidates_handle_and_process(monkeypatch):
    stub_tree(monkeypatch)
    monkeypatch.setattr(
        worker.uiautomation,
        "ControlFromHandle",
        lambda _hwnd: FakeControl(),
    )

    result = worker.perceive_hwnd(request())

    assert result["summary"]["total_elements"] == 1


def test_worker_rejects_process_change_before_walk(monkeypatch):
    stub_tree(monkeypatch)
    monkeypatch.setattr(
        worker.uiautomation,
        "ControlFromHandle",
        lambda _hwnd: FakeControl(process_id=99),
    )

    with pytest.raises(RuntimeError, match="process identity changed before"):
        worker.perceive_hwnd(request())


def test_worker_rejects_identity_change_after_walk(monkeypatch):
    stub_tree(monkeypatch)
    controls = iter([FakeControl(), FakeControl(hwnd=999)])
    monkeypatch.setattr(worker.uiautomation, "ControlFromHandle", lambda _hwnd: next(controls))

    with pytest.raises(RuntimeError, match="identity changed during"):
        worker.perceive_hwnd(request())
