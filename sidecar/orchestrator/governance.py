"""
Hermes Eats World — Governance Module
======================================
Tamper-evident audit trail and confirmation gates for safe automation.

Features:
- Tamper-evident trail: SHA-256 chained log entries
- Confirmation gates: Require approval for risky actions
- Action categorization: Safe vs risky actions
- Replay support: Full audit trail for debugging

Usage:
    from sidecar.orchestrator.governance import GovernanceTrail

    trail = GovernanceTrail()
    trail.log_action("click", target="Save button", details={"hwnd": 12345})

    # Check if an action needs confirmation
    if trail.needs_confirmation("set_value", target="password_field"):
        await user_approval()
        trail.record_approval("set_value", "password_field")
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ─── Risk Categories ───────────────────────────────────────────────

SAFE_ACTIONS: Set[str] = {
    "click", "invoke", "hover", "wait", "scroll",
    "capture_screenshot", "perceive", "list_windows",
}

RISKY_ACTIONS: Set[str] = {
    "type_text", "set_value", "drag", "right_click",
    "delete", "file_save", "file_open", "clipboard",
}

DESTRUCTIVE_ACTIONS: Set[str] = {
    "delete_file", "format_disk", "uninstall", "shutdown",
    "restart", "factory_reset", "clear_history",
}

# Fields that should trigger confirmation
SENSITIVE_TARGETS: Set[str] = {
    "password", "pin", "secret", "token", "key", "credential",
    "credit_card", "ssn", "social_security",
}


@dataclass
class AuditEntry:
    """A single tamper-evident audit log entry."""
    timestamp: float
    sequence: int
    action_type: str
    target: str
    details: Dict[str, Any]
    risk_level: str  # "safe", "risky", "destructive"
    approved: bool
    previous_hash: str
    entry_hash: str = ""  # Computed after creation

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry chained with previous."""
        data = json.dumps({
            "seq": self.sequence,
            "ts": self.timestamp,
            "action": self.action_type,
            "target": self.target,
            "details": self.details,
            "risk": self.risk_level,
            "approved": self.approved,
            "prev": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "action_type": self.action_type,
            "target": self.target,
            "details": self.details,
            "risk_level": self.risk_level,
            "approved": self.approved,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


@dataclass
class GovernanceConfig:
    """Configuration for governance behavior."""
    # Require confirmation for risky actions
    confirm_risky: bool = True
    # Block destructive actions entirely
    block_destructive: bool = True
    # Auto-approve safe actions
    auto_approve_safe: bool = True
    # Save audit trail to file
    audit_file: Optional[str] = None
    # Custom confirmation callback (returns bool)
    confirm_callback: Optional[Callable[[str, str, str], bool]] = None
    # Sensitive target patterns to watch
    sensitive_patterns: Set[str] = field(default_factory=lambda: set(SENSITIVE_TARGETS))


class GovernanceTrail:
    """Tamper-evident audit trail with confirmation gates.

    Every action is logged with a SHA-256 chain, making tampering detectable.
    Risky and destructive actions require confirmation before execution.
    """

    def __init__(self, config: Optional[GovernanceConfig] = None):
        self.config = config or GovernanceConfig()
        self._entries: List[AuditEntry] = []
        self._sequence = 0
        self._root_hash = "0" * 64  # Genesis hash

        # Load existing trail if file exists
        if self.config.audit_file:
            self._load_trail()

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        """Get the hash of the last entry (or root hash if empty)."""
        if self._entries:
            return self._entries[-1].entry_hash
        return self._root_hash

    def classify_action(self, action_type: str, target: str = "") -> str:
        """Classify an action's risk level.

        Returns:
            "safe", "risky", or "destructive"
        """
        action_lower = action_type.lower()
        target_lower = target.lower()

        # Check destructive first
        if action_lower in DESTRUCTIVE_ACTIONS:
            return "destructive"

        # Check if target is sensitive
        for pattern in self.config.sensitive_patterns:
            if pattern in target_lower:
                return "risky"

        # Check action type
        if action_lower in SAFE_ACTIONS:
            return "safe"
        if action_lower in RISKY_ACTIONS:
            return "risky"

        # Default: treat unknown actions as risky
        return "risky"

    def needs_confirmation(self, action_type: str, target: str = "",
                          details: Optional[Dict] = None) -> bool:
        """Check if an action needs user confirmation.

        Returns:
            True if the action should be held for confirmation.
        """
        risk = self.classify_action(action_type, target)

        if risk == "destructive" and self.config.block_destructive:
            logger.error("DESTRUCTIVE action blocked: %s on %s", action_type, target)
            raise PermissionError(
                f"Destructive action '{action_type}' on '{target}' is blocked by governance"
            )

        if risk == "safe" and self.config.auto_approve_safe:
            return False

        if risk == "risky" and self.config.confirm_risky:
            return True

        return False

    def request_confirmation(self, action_type: str, target: str = "",
                            details: Optional[Dict] = None) -> bool:
        """Request confirmation for an action.

        Returns:
            True if confirmed, False if rejected.
        """
        risk = self.classify_action(action_type, target)
        message = f"Confirm {risk} action: {action_type} on '{target}'"

        if self.config.confirm_callback:
            try:
                return self.config.confirm_callback(action_type, target, message)
            except Exception as e:
                logger.error("Confirmation callback failed: %s", e)
                return False

        # Default: log and auto-approve (override in production)
        logger.warning("GOVERNANCE: %s (auto-approved)", message)
        return True

    def log_action(self, action_type: str, target: str = "",
                   details: Optional[Dict] = None,
                   approved: bool = True) -> AuditEntry:
        """Log an action to the tamper-evident trail.

        Args:
            action_type: Type of action (e.g., "click", "type_text")
            target: Target element/window name
            details: Additional context
            approved: Whether the action was confirmed

        Returns:
            The created AuditEntry.
        """
        self._sequence += 1
        risk = self.classify_action(action_type, target)

        entry = AuditEntry(
            timestamp=time.time(),
            sequence=self._sequence,
            action_type=action_type,
            target=target,
            details=details or {},
            risk_level=risk,
            approved=approved,
            previous_hash=self.last_hash,
        )
        entry.entry_hash = entry.compute_hash()

        self._entries.append(entry)

        # Log to console
        level = logging.DEBUG if risk == "safe" else logging.INFO
        logger.log(level, "AUDIT[%d]: %s on '%s' (%s, approved=%s)",
                   entry.sequence, action_type, target, risk, approved)

        # Save to file if configured
        if self.config.audit_file:
            self._save_trail()

        return entry

    def verify_integrity(self) -> bool:
        """Verify the tamper-evident chain is intact.

        Returns:
            True if all hashes match, False if tampering detected.
        """
        prev_hash = self._root_hash

        for entry in self._entries:
            expected_hash = entry.compute_hash()
            if entry.entry_hash != expected_hash:
                logger.error("INTEGRITY VIOLATION at sequence %d", entry.sequence)
                return False
            if entry.previous_hash != prev_hash:
                logger.error("CHAIN BROKEN at sequence %d", entry.sequence)
                return False
            prev_hash = entry.entry_hash

        return True

    def get_entries(self, risk_level: Optional[str] = None,
                    action_type: Optional[str] = None) -> List[AuditEntry]:
        """Get audit entries, optionally filtered."""
        entries = self._entries
        if risk_level:
            entries = [e for e in entries if e.risk_level == risk_level]
        if action_type:
            entries = [e for e in entries if e.action_type == action_type]
        return entries

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the audit trail."""
        return {
            "total_entries": self._sequence,
            "last_hash": self.last_hash,
            "integrity_valid": self.verify_integrity(),
            "by_risk": {
                "safe": sum(1 for e in self._entries if e.risk_level == "safe"),
                "risky": sum(1 for e in self._entries if e.risk_level == "risky"),
                "destructive": sum(1 for e in self._entries if e.risk_level == "destructive"),
            },
            "by_action": self._count_by_action(),
        }

    def _count_by_action(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._entries:
            counts[entry.action_type] = counts.get(entry.action_type, 0) + 1
        return counts

    def _save_trail(self):
        """Save audit trail to JSON file."""
        if not self.config.audit_file:
            return
        path = Path(self.config.audit_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "root_hash": self._root_hash,
            "entries": [e.to_dict() for e in self._entries],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_trail(self):
        """Load audit trail from JSON file."""
        if not self.config.audit_file:
            return
        path = Path(self.config.audit_file)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._root_hash = data.get("root_hash", self._root_hash)
            for ed in data.get("entries", []):
                entry = AuditEntry(**ed)
                self._entries.append(entry)
                self._sequence = max(self._sequence, entry.sequence)
            logger.info("Loaded audit trail: %d entries", len(self._entries))
        except Exception as e:
            logger.error("Failed to load audit trail: %s", e)


# ─── Governance Middleware ─────────────────────────────────────────

class GovernanceMiddleware:
    """Middleware that wraps the executor with governance checks.

    Usage:
        trail = GovernanceTrail()
        middleware = GovernanceMiddleware(trail)

        # Before executing an action:
        middleware.before_action("type_text", target="password_field", details=...)

        # After executing an action:
        middleware.after_action("type_text", target="password_field", success=True)
    """

    def __init__(self, trail: GovernanceTrail):
        self.trail = trail

    def before_action(self, action_type: str, target: str = "",
                     details: Optional[Dict] = None) -> bool:
        """Called before executing an action. Returns True if allowed."""
        risk = self.trail.classify_action(action_type, target)

        if self.trail.needs_confirmation(action_type, target, details):
            confirmed = self.trail.request_confirmation(action_type, target, details)
            if not confirmed:
                logger.warning("Action REJECTED by governance: %s on '%s'", action_type, target)
                self.trail.log_action(action_type, target, details, approved=False)
                return False

        return True

    def after_action(self, action_type: str, target: str = "",
                    details: Optional[Dict] = None, success: bool = True):
        """Called after executing an action. Logs to audit trail."""
        if details is None:
            details = {}
        details["success"] = success
        self.trail.log_action(action_type, target, details, approved=True)
