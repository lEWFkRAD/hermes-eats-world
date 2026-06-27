"""
Hermes Eats World — Orchestrator Core
======================================
The main controller: PERCEIVE → PLAN → ACT → VERIFY loop.

Ties together the planner, executor, and recovery strategy into a
goal-directed automation engine. Maintains state between steps and
handles the orchestration loop.

Usage:
    from sidecar.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(max_steps=20)
    orch = Orchestrator(config=config)
    result = orch.run(goal="click the Save button", target_title="Notepad")
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..schema import Element as ElementModel

logger = logging.getLogger(__name__)


# ─── Status enums ──────────────────────────────────────────────────

class StepStatus(Enum):
    """Status of a single step in the execution plan."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ExecutionStatus(Enum):
    """Overall execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ─── Data models ───────────────────────────────────────────────────

@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    max_steps: int = 20
    max_wait_seconds: float = 300.0
    step_timeout: float = 15.0
    retry_count: int = 2
    retry_delay: float = 1.0
    require_verification: bool = True
    # Depth 3 is too shallow for nested UWP/XAML apps: e.g. the Windows
    # Calculator keypad lives ~4-5 levels below the drilled content window, so at
    # depth 3 the orchestrator perceives only frame chrome (~19 elements, no
    # buttons) and every "click <button>" fails. Depth 5 reaches the actionable
    # controls (keypad present, ~81 elements) and plateaus there.
    perception_depth: int = 5


@dataclass
class StepResult:
    """Result of a single step execution."""
    id: int
    action_type: str
    description: str
    status: StepStatus = StepStatus.PENDING
    duration: float = 0.0
    error: Optional[str] = None
    retries: int = 0
    verified: bool = False


@dataclass
class ExecutionResult:
    """Result of a full orchestrator run."""
    goal: str
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    steps_total: int = 0
    steps_completed: int = 0
    elapsed: float = 0.0
    step_results: List[StepResult] = field(default_factory=list)
    error: Optional[str] = None
    final_state: Optional[Dict] = None


# ─── Element matching helpers ──────────────────────────────────────

def find_element_by_name(tree: ElementModel, name: str, control_type: Optional[str] = None) -> Optional[ElementModel]:
    """Find an element in the tree by name (case-insensitive substring match)."""
    name_lower = name.lower()

    def _search(elem: ElementModel) -> Optional[ElementModel]:
        if name_lower in elem.name.lower():
            if control_type is None or control_type.lower() in elem.control_type.lower():
                return elem
        for child in elem.children:
            result = _search(child)
            if result:
                return result
        return None

    return _search(tree)


def find_element_by_automation_id(tree: ElementModel, automation_id: str) -> Optional[ElementModel]:
    """Find an element by exact AutomationId match."""
    def _search(elem: ElementModel) -> Optional[ElementModel]:
        if elem.automation_id == automation_id:
            return elem
        for child in elem.children:
            result = _search(child)
            if result:
                return result
        return None

    return _search(tree)


def find_elements_by_type(tree: ElementModel, control_type: str) -> List[ElementModel]:
    """Find all elements of a specific control type."""
    results: List[ElementModel] = []
    type_lower = control_type.lower()

    def _search(elem: ElementModel):
        if type_lower in elem.control_type.lower():
            results.append(elem)
        for child in elem.children:
            _search(child)

    _search(tree)
    return results


def find_invocable_elements(tree: ElementModel) -> List[ElementModel]:
    """Find all elements that support the InvokePattern."""
    results: List[ElementModel] = []

    def _search(elem: ElementModel):
        if "InvokePattern" in elem.patterns:
            results.append(elem)
        for child in elem.children:
            _search(child)

    _search(tree)
    return results


def find_editable_elements(tree: ElementModel) -> List[ElementModel]:
    """Find all elements that support the ValuePattern (text fields, etc.)."""
    results: List[ElementModel] = []

    def _search(elem: ElementModel):
        if "ValuePattern" in elem.patterns:
            vp = elem.patterns["ValuePattern"]
            if not vp.get("readonly", False):
                results.append(elem)
        for child in elem.children:
            _search(child)

    _search(tree)
    return results


# ─── Orchestrator ──────────────────────────────────────────────────

class Orchestrator:
    """Goal-directed automation orchestrator.

    Runs the PERCEIVE → PLAN → ACT → VERIFY loop until the goal is achieved,
    a step limit is hit, or an unrecoverable error occurs.

    Attributes:
        config: Orchestrator configuration.
        planner: ActionPlanner instance.
        executor: Executor instance.
        recovery: RecoveryStrategy instance.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._planner = None
        self._executor = None
        self._recovery = None
        self._step_results: List[StepResult] = []
        self._start_time: float = 0.0

    @property
    def planner(self):
        if self._planner is None:
            from .planner import ActionPlanner
            self._planner = ActionPlanner()
        return self._planner

    @property
    def executor(self):
        if self._executor is None:
            from .executor import Executor
            self._executor = Executor()
        return self._executor

    @property
    def recovery(self):
        if self._recovery is None:
            from .recovery import RecoveryStrategy
            self._recovery = RecoveryStrategy()
        return self._recovery

    def run(
        self,
        goal: str,
        target_title: Optional[str] = None,
        target_process: Optional[str] = None,
        target_class: Optional[str] = None,
    ) -> ExecutionResult:
        """Run the orchestrator loop for a given goal.

        Args:
            goal: Natural language description of the goal.
            target_title: Window title to target.
            target_process: Process name to target.
            target_class: Window class name to target.

        Returns:
            ExecutionResult with the outcome of the run.
        """
        self._start_time = time.time()
        self._step_results = []

        target_params = {
            "title": target_title,
            "process": target_process,
            "class_name": target_class,
        }

        logger.info("Orchestrator starting. Goal: %s", goal)

        # Step 0: Initial perception
        initial_state = self._perceive(target_params)
        if not initial_state.ok:
            return ExecutionResult(
                goal=goal,
                status=ExecutionStatus.FAILED,
                error=f"Initial perception failed: {initial_state.error}",
                elapsed=time.time() - self._start_time,
            )

        logger.info(
            "Initial state: %d elements, tier=%s",
            initial_state.summary.total_elements, initial_state.tier.tier,
        )

        # Step 1: Plan
        plan = self.planner.plan(goal, initial_state)
        logger.info("Plan generated: %d steps", len(plan.steps))

        if not plan.steps:
            return ExecutionResult(
                goal=goal,
                status=ExecutionStatus.FAILED,
                error="Planner returned no steps",
                elapsed=time.time() - self._start_time,
                step_results=[],
            )

        # Step 2: Execute loop
        current_state = initial_state
        for step in plan.steps:
            # Check elapsed time
            elapsed = time.time() - self._start_time
            if elapsed > self.config.max_wait_seconds:
                return ExecutionResult(
                    goal=goal,
                    status=ExecutionStatus.TIMEOUT,
                    steps_total=len(plan.steps),
                    steps_completed=len(self._step_results),
                    elapsed=elapsed,
                    step_results=list(self._step_results),
                    error=f"Timeout after {elapsed:.1f}s",
                )

            # Check step limit
            if len(self._step_results) >= self.config.max_steps:
                return ExecutionResult(
                    goal=goal,
                    status=ExecutionStatus.PARTIAL,
                    steps_total=len(plan.steps),
                    steps_completed=len(self._step_results),
                    elapsed=elapsed,
                    step_results=list(self._step_results),
                    error=f"Step limit ({self.config.max_steps}) reached",
                )

            # Execute step
            step_result = self._execute_step(step, current_state, target_params)
            self._step_results.append(step_result)

            if step_result.status == StepStatus.SUCCESS:
                logger.info("Step %d succeeded: %s", step.id, step.description)

                # Verification: re-perceive and check state
                if self.config.require_verification:
                    current_state = self._perceive(target_params)
                    if not current_state.ok:
                        step_result.verified = False
                        logger.warning("Verification perception failed: %s", current_state.error)
                    else:
                        step_result.verified = True
                else:
                    step_result.verified = True

                # Check if goal is already achieved
                if self.planner.check_goal(goal, current_state):
                    logger.info("Goal achieved after %d steps!", len(self._step_results))
                    return ExecutionResult(
                        goal=goal,
                        status=ExecutionStatus.SUCCESS,
                        steps_total=len(plan.steps),
                        steps_completed=len(self._step_results),
                        elapsed=time.time() - self._start_time,
                        step_results=list(self._step_results),
                        final_state={
                            "total_elements": current_state.summary.total_elements,
                            "tier": current_state.tier.tier,
                        } if current_state.ok else None,
                    )

            elif step_result.status == StepStatus.FAILED:
                # Try recovery
                recovery_action = self.recovery.classify_and_recover(
                    step_result.error or "unknown",
                    step.action_type,
                )
                if recovery_action.can_recover:
                    logger.info(
                        "Recovery strategy: %s (attempts %d/%d)",
                        recovery_action.recovery_type,
                        step_result.retries + 1,
                        self.config.retry_count,
                    )
                    step_result.retries += 1
                    step_result.status = StepStatus.RETRYING

                    time.sleep(self.config.retry_delay)

                    # Retry the step
                    retry_result = self._execute_step(step, current_state, target_params)
                    if retry_result.status == StepStatus.SUCCESS:
                        step_result = retry_result
                        self._step_results[-1] = step_result
                        logger.info("Step %d recovered successfully", step.id)
                        continue
                    else:
                        step_result.status = StepStatus.FAILED
                        step_result.error = retry_result.error
                        self._step_results[-1] = step_result

                # If unrecoverable, fail
                logger.error("Step %d failed and cannot recover: %s", step.id, step_result.error)
                return ExecutionResult(
                    goal=goal,
                    status=ExecutionStatus.FAILED,
                    steps_total=len(plan.steps),
                    steps_completed=len(self._step_results),
                    elapsed=time.time() - self._start_time,
                    step_results=list(self._step_results),
                    error=step_result.error,
                )

        # All steps executed
        final_elapsed = time.time() - self._start_time
        success_count = sum(1 for s in self._step_results if s.status == StepStatus.SUCCESS)
        total_count = len(self._step_results)

        if success_count == total_count:
            status = ExecutionStatus.SUCCESS
        elif success_count > 0:
            status = ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILED

        return ExecutionResult(
            goal=goal,
            status=status,
            steps_total=len(plan.steps),
            steps_completed=total_count,
            elapsed=final_elapsed,
            step_results=list(self._step_results),
            final_state={
                "total_elements": current_state.summary.total_elements,
                "tier": current_state.tier.tier,
            } if current_state.ok else None,
        )

    def _perceive(self, target_params: Dict) -> "PerceptionResult":
        """Run a perception pass on the target window."""
        from ..service.service import perceive_target

        return perceive_target(
            title=target_params.get("title"),
            process=target_params.get("process"),
            class_name=target_params.get("class_name"),
            depth=self.config.perception_depth,
        )

    def _execute_step(self, step, current_state, target_params: Dict) -> StepResult:
        """Execute a single planned step."""
        step_result = StepResult(
            id=step.id,
            action_type=step.action_type,
            description=step.description,
            status=StepStatus.RUNNING,
        )

        start = time.time()
        try:
            success = self.executor.execute(
                action=step,
                state=current_state,
                target_params=target_params,
            )
            duration = time.time() - start
            step_result.duration = duration
            step_result.status = StepStatus.SUCCESS if success else StepStatus.FAILED
            if not success:
                step_result.error = "Executor returned failure"

        except Exception as e:
            duration = time.time() - start
            step_result.duration = duration
            step_result.status = StepStatus.FAILED
            step_result.error = str(e)
            logger.exception("Step %d failed: %s", step.id, e)

        return step_result
