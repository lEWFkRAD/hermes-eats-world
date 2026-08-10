from sidecar.action import (
    ActionKind,
    ActionPolicy,
    ActionRequest,
    ActionStatus,
    RiskLevel,
    execute_action,
)
from sidecar.schema import Element, TargetInfo, TierClassification, TreeSnapshot, TreeSummary


def snapshot(*, enabled=True, name="Save", patterns=None, hwnd=100):
    child = Element(
        id="save-button",
        control_type="ButtonControl",
        localized_type="button",
        name=name,
        is_enabled=enabled,
        patterns=patterns if patterns is not None else {"invoke": {"supported": True}},
        depth=1,
    )
    root = Element(
        id="root",
        control_type="WindowControl",
        localized_type="window",
        children=[child],
    )
    return TreeSnapshot(
        target=TargetInfo(name="Editor", hwnd=hwnd),
        tier=TierClassification(tier="T1", label="rich", confidence=1),
        summary=TreeSummary(total_elements=2),
        tree=root,
        timestamp="2026-01-01T00:00:00+00:00",
    )


def request(**overrides):
    values = {
        "target_hwnd": 100,
        "target_element_id": "save-button",
        "action": ActionKind.INVOKE,
        "risk": RiskLevel.LOW,
        "dry_run": False,
        "reason": "Save reviewed work",
        "snapshot_schema_version": "1.1.0",
        "expected_before": {"name": "Save", "is_enabled": True},
        "expected_after": {"name": "Saved"},
    }
    values.update(overrides)
    return ActionRequest(**values)


class RecordingAdapter:
    def __init__(self):
        self.calls = []

    def invoke(self, hwnd, element):
        self.calls.append((hwnd, element.id))


def enabled_policy():
    return ActionPolicy(allowed_hwnds=frozenset({100}), execution_enabled=True)


def test_invoke_executes_only_after_preflight_and_verifies_after_state():
    adapter = RecordingAdapter()

    receipt = execute_action(
        request(), enabled_policy(), snapshot(), adapter, lambda: snapshot(name="Saved")
    )

    assert receipt.status is ActionStatus.EXECUTED
    assert adapter.calls == [(100, "save-button")]
    assert receipt.verification["before_fingerprint"]
    assert receipt.verification["after_fingerprint"]


def test_stale_before_state_fails_without_mutation():
    adapter = RecordingAdapter()

    receipt = execute_action(
        request(), enabled_policy(), snapshot(name="Save As"), adapter, snapshot
    )

    assert receipt.status is ActionStatus.FAILED
    assert "before state mismatch" in receipt.message
    assert adapter.calls == []
    assert receipt.verification["mutation_attempted"] is False


def test_missing_invoke_capability_fails_without_mutation():
    adapter = RecordingAdapter()

    receipt = execute_action(request(), enabled_policy(), snapshot(patterns={}), adapter, snapshot)

    assert receipt.status is ActionStatus.FAILED
    assert "invoke pattern" in receipt.message
    assert adapter.calls == []


def test_failed_postcondition_records_that_mutation_was_attempted():
    adapter = RecordingAdapter()

    receipt = execute_action(request(), enabled_policy(), snapshot(), adapter, snapshot)

    assert receipt.status is ActionStatus.FAILED
    assert "after state mismatch" in receipt.message
    assert adapter.calls == [(100, "save-button")]
    assert receipt.verification["mutation_attempted"] is True


def test_dry_run_never_calls_adapter_or_after_snapshot():
    adapter = RecordingAdapter()
    after_called = False

    def after():
        nonlocal after_called
        after_called = True
        return snapshot()

    receipt = execute_action(request(dry_run=True), enabled_policy(), snapshot(), adapter, after)

    assert receipt.status is ActionStatus.PLANNED
    assert adapter.calls == []
    assert after_called is False


def test_live_execution_requires_explicit_postconditions():
    adapter = RecordingAdapter()

    receipt = execute_action(
        request(expected_after={}), enabled_policy(), snapshot(), adapter, snapshot
    )

    assert receipt.status is ActionStatus.FAILED
    assert "requires explicit expected_after" in receipt.message
    assert adapter.calls == []


def test_adapter_failure_becomes_a_failed_receipt():
    class BrokenAdapter:
        def invoke(self, hwnd, element):
            raise RuntimeError("COM server unavailable")

    receipt = execute_action(request(), enabled_policy(), snapshot(), BrokenAdapter(), snapshot)

    assert receipt.status is ActionStatus.FAILED
    assert receipt.message == "COM server unavailable"
    assert receipt.verification["mutation_attempted"] is True
