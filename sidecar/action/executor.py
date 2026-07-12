"""Policy-gated low-risk action execution with before/after verification."""

from __future__ import annotations

from typing import Callable, Protocol

from ..schema import Element, TreeSnapshot
from .models import ActionKind, ActionReceipt, ActionRequest, ActionStatus
from .policy import POLICY_VERSION, ActionPolicy, plan_action
from .resolver import (
    ResolutionError,
    StaleStateError,
    element_fingerprint,
    require_state,
    resolve_element,
)


class ActionAdapter(Protocol):
    def invoke(self, hwnd: int, element: Element) -> None: ...


SnapshotSupplier = Callable[[], TreeSnapshot]


def execute_action(
    request: ActionRequest,
    policy: ActionPolicy,
    before_snapshot: TreeSnapshot,
    adapter: ActionAdapter,
    after_snapshot: SnapshotSupplier,
) -> ActionReceipt:
    """Execute one explicitly enabled invoke and verify its declared postconditions."""
    planned = plan_action(request, policy)
    if planned.status is ActionStatus.BLOCKED or request.dry_run:
        return planned

    before_fingerprint = None
    after_fingerprint = None
    mutation_attempted = False
    try:
        if request.snapshot_schema_version != before_snapshot.schema_version:
            raise StaleStateError("Snapshot schema version changed")
        if before_snapshot.target.hwnd != request.target_hwnd:
            raise ResolutionError("Fresh snapshot HWND does not match action target")
        if request.action is not ActionKind.INVOKE:
            raise ResolutionError("Only invoke execution is implemented")
        if not request.expected_after:
            raise ResolutionError("Live execution requires explicit expected_after state")

        before = resolve_element(before_snapshot, request.target_element_id)
        require_state(before, request.expected_before, phase="before")
        if "invoke" not in before.patterns:
            raise ResolutionError("Target element does not advertise the invoke pattern")
        if not before.is_enabled or before.is_offscreen:
            raise ResolutionError("Target element is not safely actionable")
        before_fingerprint = element_fingerprint(before)

        mutation_attempted = True
        adapter.invoke(request.target_hwnd, before)

        after_state = after_snapshot()
        after = resolve_element(after_state, request.target_element_id)
        require_state(after, request.expected_after, phase="after")
        after_fingerprint = element_fingerprint(after)
        return _receipt(
            request,
            ActionStatus.EXECUTED,
            "Action executed and postconditions verified",
            before_fingerprint,
            after_fingerprint,
            mutation_attempted,
        )
    except Exception as exc:
        return _receipt(
            request,
            ActionStatus.FAILED,
            str(exc),
            before_fingerprint,
            after_fingerprint,
            mutation_attempted,
        )


def _receipt(
    request: ActionRequest,
    status: ActionStatus,
    message: str,
    before_fingerprint: str | None,
    after_fingerprint: str | None,
    mutation_attempted: bool,
) -> ActionReceipt:
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
        verification={
            "mutation_attempted": mutation_attempted,
            "before_fingerprint": before_fingerprint,
            "after_fingerprint": after_fingerprint,
        },
    )
