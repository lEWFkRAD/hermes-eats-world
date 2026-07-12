"""Deny-by-default policy evaluation for desktop action proposals."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ActionKind, ActionReceipt, ActionRequest, ActionStatus, RiskLevel

POLICY_VERSION = "0.1.0"


@dataclass(frozen=True)
class ActionPolicy:
    allowed_actions: frozenset[ActionKind] = field(
        default_factory=lambda: frozenset(
            {ActionKind.INVOKE, ActionKind.SELECT, ActionKind.EXPAND, ActionKind.COLLAPSE}
        )
    )
    allowed_hwnds: frozenset[int] = field(default_factory=frozenset)
    maximum_risk: RiskLevel = RiskLevel.MEDIUM
    execution_enabled: bool = False


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.DESTRUCTIVE: 3,
}


def plan_action(request: ActionRequest, policy: ActionPolicy) -> ActionReceipt:
    """Evaluate a proposal and emit an immutable plan or rejection receipt."""
    blocked_reason = _blocked_reason(request, policy)
    status = ActionStatus.BLOCKED if blocked_reason else ActionStatus.PLANNED
    message = blocked_reason or "Action passed policy evaluation; no mutation performed"
    return ActionReceipt(
        request_id=request.request_id,
        request_fingerprint=request.fingerprint(),
        status=status,
        action=request.action,
        risk=request.risk,
        target_hwnd=request.target_hwnd,
        target_element_id=request.target_element_id,
        dry_run=request.dry_run,
        policy_version=POLICY_VERSION,
        message=message,
        verification={"mutation_performed": False},
    )


def _blocked_reason(request: ActionRequest, policy: ActionPolicy) -> str | None:
    if request.target_hwnd not in policy.allowed_hwnds:
        return "Target HWND is not allowlisted"
    if request.action not in policy.allowed_actions:
        return f"Action kind '{request.action.value}' is not allowlisted"
    if _RISK_ORDER[request.risk] > _RISK_ORDER[policy.maximum_risk]:
        return f"Risk '{request.risk.value}' exceeds policy maximum"
    if not request.dry_run and not policy.execution_enabled:
        return "Execution is disabled; submit as dry_run"
    return None
