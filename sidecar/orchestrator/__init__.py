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
from .planner import ActionStep, ActionPlan
from .executor import Executor
from .recovery import RecoveryStrategy, RecoveryResult, RetryPolicy, ErrorType, RecoveryAction

__all__ = [
    "Orchestrator",
    "OrchestratorConfig",
    "StepResult",
    "ExecutionResult",
    "StepStatus",
    "ExecutionStatus",
    "ActionStep",
    "ActionPlan",
    "Executor",
    "RecoveryStrategy",
    "RecoveryResult",
    "RetryPolicy",
    "ErrorType",
    "RecoveryAction",
]
