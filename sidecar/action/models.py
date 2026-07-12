"""Typed contracts for proposed desktop actions and their audit receipts."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionKind(str, Enum):
    INVOKE = "invoke"
    SET_VALUE = "set_value"
    TOGGLE = "toggle"
    SELECT = "select"
    EXPAND = "expand"
    COLLAPSE = "collapse"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    EXECUTED = "executed"
    FAILED = "failed"


class ActionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    target_hwnd: int = Field(gt=0)
    target_element_id: str = Field(min_length=1)
    action: ActionKind
    risk: RiskLevel
    value: str | None = None
    dry_run: bool = True
    reason: str = Field(min_length=1, max_length=500)
    snapshot_schema_version: str
    expected_before: dict[str, Any] = Field(default_factory=dict)
    expected_after: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_value_shape(self):
        if self.action is ActionKind.SET_VALUE and self.value is None:
            raise ValueError("set_value actions require value")
        if self.action is not ActionKind.SET_VALUE and self.value is not None:
            raise ValueError("value is only valid for set_value actions")
        return self

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"request_id"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class ActionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    request_id: str
    request_fingerprint: str
    status: ActionStatus
    action: ActionKind
    risk: RiskLevel
    target_hwnd: int
    target_element_id: str
    dry_run: bool
    policy_version: str
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verification: dict[str, Any] = Field(default_factory=dict)
