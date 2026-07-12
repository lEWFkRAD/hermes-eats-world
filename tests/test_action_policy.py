import pytest
from pydantic import ValidationError

from sidecar.action import (
    ActionKind,
    ActionPolicy,
    ActionRequest,
    ActionStatus,
    RiskLevel,
    plan_action,
)


def request(**overrides):
    values = {
        "target_hwnd": 100,
        "target_element_id": "save-button",
        "action": ActionKind.INVOKE,
        "risk": RiskLevel.LOW,
        "reason": "Save the reviewed draft",
        "snapshot_schema_version": "0.1.0",
    }
    values.update(overrides)
    return ActionRequest(**values)


def test_allowlisted_dry_run_produces_planned_receipt_without_mutation():
    proposal = request()
    receipt = plan_action(proposal, ActionPolicy(allowed_hwnds=frozenset({100})))

    assert receipt.status is ActionStatus.PLANNED
    assert receipt.request_fingerprint == proposal.fingerprint()
    assert receipt.verification == {"mutation_performed": False}


def test_unknown_window_is_blocked_by_default():
    receipt = plan_action(request(), ActionPolicy())

    assert receipt.status is ActionStatus.BLOCKED
    assert "not allowlisted" in receipt.message


def test_destructive_action_is_blocked_even_on_allowlisted_window():
    receipt = plan_action(
        request(risk=RiskLevel.DESTRUCTIVE),
        ActionPolicy(allowed_hwnds=frozenset({100})),
    )

    assert receipt.status is ActionStatus.BLOCKED
    assert "exceeds policy maximum" in receipt.message


def test_live_execution_is_disabled_by_default():
    receipt = plan_action(
        request(dry_run=False),
        ActionPolicy(allowed_hwnds=frozenset({100})),
    )

    assert receipt.status is ActionStatus.BLOCKED
    assert "Execution is disabled" in receipt.message


def test_set_value_requires_a_value_and_other_actions_reject_it():
    with pytest.raises(ValidationError, match="require value"):
        request(action=ActionKind.SET_VALUE)
    with pytest.raises(ValidationError, match="only valid"):
        request(value="secret")


def test_receipt_and_request_are_immutable():
    proposal = request()
    receipt = plan_action(proposal, ActionPolicy(allowed_hwnds=frozenset({100})))

    with pytest.raises(ValidationError):
        proposal.reason = "changed"
    with pytest.raises(ValidationError):
        receipt.message = "changed"
