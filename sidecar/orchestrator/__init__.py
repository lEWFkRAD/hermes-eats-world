"""Hermes Eats World — Orchestrator module.

Goal-directed automation engine: PERCEIVE → PLAN → ACT → VERIFY loop.

Public API:
    from sidecar.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(max_steps=20)
    orch = Orchestrator(config=config)
    result = orch.run(goal="click the Save button", target_title="Notepad")
"""

from .orchestrator import (
    Orchestrator,
    OrchestratorConfig,
    StepResult,
    ExecutionResult,
    StepStatus,
    ExecutionStatus,
)
from .planner import ActionStep, ActionPlan, ActionPlanner
from .executor import Executor
from .recovery import RecoveryStrategy, RecoveryResult, RetryPolicy, ErrorType, RecoveryAction
from .llm_planner import LLMPlanner, LLMPlannerConfig
from .governance import (
    GovernanceTrail, GovernanceConfig, GovernanceMiddleware,
    AuditEntry, SAFE_ACTIONS, RISKY_ACTIONS, DESTRUCTIVE_ACTIONS,
)
from .event_sub import (
    EventSubscriber, UIAEvent,
    EVENT_TREE_STRUCTURE_CHANGED, EVENT_FOCUS_CHANGED,
    EVENT_DIALOG_OPENED, EVENT_WINDOW_OPENED, EVENT_TEXT_CHANGED,
)
from .modal_handler import (
    ModalHandler, ModalDialog,
    click_ok, click_cancel, click_yes, click_no,
)

__all__ = [
    # Core
    "Orchestrator",
    "OrchestratorConfig",
    "StepResult",
    "ExecutionResult",
    "StepStatus",
    "ExecutionStatus",
    # Planning
    "ActionStep",
    "ActionPlan",
    "ActionPlanner",
    "LLMPlanner",
    "LLMPlannerConfig",
    # Execution
    "Executor",
    # Recovery
    "RecoveryStrategy",
    "RecoveryResult",
    "RetryPolicy",
    "ErrorType",
    "RecoveryAction",
    # Governance
    "GovernanceTrail",
    "GovernanceConfig",
    "GovernanceMiddleware",
    "AuditEntry",
    "SAFE_ACTIONS",
    "RISKY_ACTIONS",
    "DESTRUCTIVE_ACTIONS",
    # Events
    "EventSubscriber",
    "UIAEvent",
    "EVENT_TREE_STRUCTURE_CHANGED",
    "EVENT_FOCUS_CHANGED",
    "EVENT_DIALOG_OPENED",
    "EVENT_WINDOW_OPENED",
    "EVENT_TEXT_CHANGED",
    # Modal handling
    "ModalHandler",
    "ModalDialog",
    "click_ok",
    "click_cancel",
    "click_yes",
    "click_no",
]
