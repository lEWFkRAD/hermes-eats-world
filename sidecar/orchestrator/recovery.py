"""
Hermes Eats World — Recovery Strategy
======================================
Handles failures during orchestration with retry policies,
fallback strategies, and error classification.

Usage:
    from sidecar.orchestrator import RecoveryStrategy, RetryPolicy

    strategy = RecoveryStrategy(policy=RetryPolicy(max_retries=3))
    action = strategy.classify_and_handle(error, step, state)
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .orchestrator import StepResult, StepStatus
from .planner import ActionStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error Classification
# ---------------------------------------------------------------------------

class ErrorType(Enum):
    """Classification of execution errors."""
    TRANSIENT = "transient"        # Temporary, retry likely to succeed
    PERMANENT = "permanent"        # Will not succeed on retry
    TIMEOUT = "timeout"           # Operation timed out
    ELEMENT_NOT_FOUND = "element_not_found"  # Target element missing
    PERMISSION_DENIED = "permission_denied"  # Access denied
    UNKNOWN = "unknown"           # Unclassified


class RecoveryAction(Enum):
    """What to do when a step fails."""
    RETRY = "retry"              # Retry the same step
    FALLBACK = "fallback"        # Try an alternative approach
    SKIP = "skip"                # Skip this step and continue
    ABORT = "abort"              # Stop the entire orchestration
    REPERCEIVE = "reperceive"    # Re-perceive the UI and retry


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------

@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 2
    base_delay: float = 1.0          # Base delay between retries
    max_delay: float = 30.0          # Max delay (exponential backoff cap)
    exponential: bool = True         # Use exponential backoff
    jitter: bool = True              # Add random jitter to delays

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt."""
        import random

        if self.exponential:
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            delay += random.uniform(0, delay * 0.25)

        return delay


# ---------------------------------------------------------------------------
# Recovery Strategy
# ---------------------------------------------------------------------------

@dataclass
class RecoveryResult:
    """Result of classify_and_recover call."""
    can_recover: bool
    recovery_type: str
    error_type: ErrorType
    action: RecoveryAction


class RecoveryStrategy:
    """Classify errors and determine recovery actions.

    Error classification rules:
    - Timeout errors → RETRY (with increased timeout)
    - Element not found → REPERCEIVE → RETRY → FALLBACK
    - Permission denied → ABORT
    - Transient errors → RETRY
    - Permanent errors → FALLBACK or SKIP
    """

    # Error patterns that indicate transient failures
    TRANSIENT_PATTERNS = [
        "timeout",
        "timed out",
        "busy",
        "retry",
        "temporary",
        "connection",
        "race condition",
    ]

    # Error patterns that indicate permanent failures
    PERMANENT_PATTERNS = [
        "not supported",
        "does not support",
        "read-only",
        "permission denied",
        "access denied",
        "invalid operation",
    ]

    # Error patterns for element not found
    ELEMENT_PATTERNS = [
        "not found",
        "no matching",
        "element missing",
        "control not found",
        "could not find",
    ]

    def __init__(self, policy: Optional[RetryPolicy] = None):
        self.policy = policy or RetryPolicy()

    def classify_and_recover(self, error: str, action_type: str) -> RecoveryResult:
        """Classify an error and decide if recovery is possible.

        This is the interface the Orchestrator uses directly.

        Args:
            error: Error message string.
            action_type: The action type that failed (e.g. "invoke", "type_text").

        Returns:
            RecoveryResult with can_recover flag and recovery_type.
        """
        dummy_step = ActionStep(id=0, action_type=action_type, description="")
        error_type, recovery_action = self.classify_error(error, dummy_step)

        can_recover = recovery_action in (
            RecoveryAction.RETRY,
            RecoveryAction.FALLBACK,
            RecoveryAction.REPERCEIVE,
        )

        return RecoveryResult(
            can_recover=can_recover,
            recovery_type=recovery_action.value,
            error_type=error_type,
            action=recovery_action,
        )

    def classify_error(self, error: str, step) -> Tuple[ErrorType, RecoveryAction]:
        """Classify an error and determine the recovery action.

        Args:
            error: Error message string.
            step: Either an ActionStep or an action_type string.

        Returns:
            Tuple of (ErrorType, RecoveryAction).
        """
        error_lower = error.lower()

        # Check for element not found
        for pattern in self.ELEMENT_PATTERNS:
            if pattern in error_lower:
                return (ErrorType.ELEMENT_NOT_FOUND, RecoveryAction.REPERCEIVE)

        # Check for timeout
        if "timeout" in error_lower or "timed out" in error_lower:
            return (ErrorType.TIMEOUT, RecoveryAction.RETRY)

        # Check for permission denied
        if "permission denied" in error_lower or "access denied" in error_lower:
            return (ErrorType.PERMISSION_DENIED, RecoveryAction.ABORT)

        # Check for transient errors
        for pattern in self.TRANSIENT_PATTERNS:
            if pattern in error_lower:
                return (ErrorType.TRANSIENT, RecoveryAction.RETRY)

        # Check for permanent errors
        for pattern in self.PERMANENT_PATTERNS:
            if pattern in error_lower:
                return (ErrorType.PERMANENT, RecoveryAction.FALLBACK)

        # Default: treat as transient, retry
        return (ErrorType.UNKNOWN, RecoveryAction.RETRY)

    def handle_failure(
        self,
        error: str,
        step: ActionStep,
        state: Dict[str, Any],
        attempt: int,
    ) -> Tuple[RecoveryAction, Dict[str, Any]]:
        """Handle a step failure with appropriate recovery.

        Args:
            error: Error message.
            step: The failed step.
            state: Current UI state.
            attempt: Current attempt number (0-based).

        Returns:
            Tuple of (RecoveryAction, context dict for the action).
        """
        error_type, action = self.classify_error(error, step)

        logger.info(
            "RECOVERY: Step %d failed with %s → %s (attempt %d/%d)",
            step.id, error_type.value, action.value, attempt, self.policy.max_retries,
        )

        context: Dict[str, Any] = {
            "error_type": error_type.value,
            "attempt": attempt,
            "max_retries": self.policy.max_retries,
        }

        if action == RecoveryAction.RETRY:
            delay = self.policy.get_delay(attempt)
            context["delay"] = delay
            context["next_attempt"] = attempt + 1
            logger.info("RECOVERY: Retrying in %.1fs", delay)
            return (action, context)

        elif action == RecoveryAction.REPERCEIVE:
            context["reperceive"] = True
            return (action, context)

        elif action == RecoveryAction.FALLBACK:
            # Generate a fallback step
            fallback_step = self._generate_fallback(step)
            context["fallback_step"] = fallback_step
            return (action, context)

        elif action == RecoveryAction.SKIP:
            logger.warning("RECOVERY: Skipping step %d", step.id)
            return (action, context)

        elif action == RecoveryAction.ABORT:
            logger.error("RECOVERY: Aborting due to %s", error_type.value)
            return (action, context)

        return (action, context)

    def _generate_fallback(self, step: ActionStep) -> Optional[ActionStep]:
        """Generate a fallback step when the original approach fails.

        Common fallbacks:
        - T1 click failed → T2 click at bounding box
        - T1 type failed → T2 SendInput type
        - Element not found → Re-perceive and search again
        """
        if step.action_type == "click":
            return ActionStep(
                id=step.id,
                description=f"FALLBACK: Click '{step.description}' using T2",
                action_type="click",
                target_name=step.target_name,
                target_automation_id=step.target_automation_id,
                parameters=step.parameters,
            )
        elif step.action_type in ("type_text", "set_value"):
            return ActionStep(
                id=step.id,
                description=f"FALLBACK: Type text using T2 SendInput",
                action_type="type_text",
                target_name=step.target_name,
                target_automation_id=step.target_automation_id,
                value=step.value,
                parameters=step.parameters,
            )

        return None
