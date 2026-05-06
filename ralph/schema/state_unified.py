"""Unified state schema for Ralph repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class FeatureStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    FAILED = "failed"
    BLOCKED = "blocked"


class BlockingStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BlockingType(str, Enum):
    MISSING_ENV = "missing_env"
    MISSING_CREDENTIALS = "missing_credentials"
    EXTERNAL_SERVICE_DOWN = "external_service_down"
    MANUAL_DECISION_REQUIRED = "manual_decision_required"
    TEST_UNAVAILABLE = "test_unavailable"
    UNEXPECTED_RUNTIME_ERROR = "unexpected_runtime_error"
    DEPENDENCY_NOT_MET = "dependency_not_met"
    CODE_ERROR = "code_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SCOPE_VIOLATION = "scope_violation"
    REVIEW_FAILED = "review_failed"


@dataclass
class UnifiedFeature:
    feature_id: str
    title: str = ""
    description: str = ""
    priority: str = "P1"
    status: str = FeatureStatus.PENDING.value
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedFeature":
        return cls(
            feature_id=data.get("feature_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=data.get("priority", "P1"),
            status=data.get("status", FeatureStatus.PENDING.value),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class UnifiedTask:
    task_id: str
    feature_id: str = ""
    title: str = ""
    owner_role: str = ""
    status: str = TaskStatus.PENDING.value
    blocking_reason: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "feature_id": self.feature_id,
            "title": self.title,
            "owner_role": self.owner_role,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "blocking_reason": self.blocking_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedTask":
        return cls(
            task_id=data.get("task_id", ""),
            feature_id=data.get("feature_id", ""),
            title=data.get("title", ""),
            owner_role=data.get("owner_role", ""),
            status=data.get("status", TaskStatus.PENDING.value),
            blocking_reason=data.get("blocking_reason", ""),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class UnifiedBlockingIssue:
    blocking_id: str
    type: str = BlockingType.UNEXPECTED_RUNTIME_ERROR.value
    title: str = ""
    details: str = ""
    required_human_action: str = ""
    status: str = BlockingStatus.OPEN.value
    related_feature_id: str = ""
    related_task_id: str = ""
    created_at: str = field(default_factory=_now_iso)
    resolved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocking_id": self.blocking_id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "title": self.title,
            "details": self.details,
            "required_human_action": self.required_human_action,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "related_feature_id": self.related_feature_id,
            "related_task_id": self.related_task_id,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedBlockingIssue":
        return cls(
            blocking_id=data.get("blocking_id", ""),
            type=data.get("type", BlockingType.UNEXPECTED_RUNTIME_ERROR.value),
            title=data.get("title", ""),
            details=data.get("details", ""),
            required_human_action=data.get("required_human_action", ""),
            status=data.get("status", BlockingStatus.OPEN.value),
            related_feature_id=data.get("related_feature_id", ""),
            related_task_id=data.get("related_task_id", ""),
            created_at=data.get("created_at", _now_iso()),
            resolved_at=data.get("resolved_at", ""),
        )


@dataclass
class UnifiedExecutionRun:
    run_id: str
    project_id: str = ""
    status: str = RunStatus.RUNNING.value
    started_at: str = field(default_factory=_now_iso)
    ended_at: str = ""
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedExecutionRun":
        return cls(
            run_id=data.get("run_id", ""),
            project_id=data.get("project_id", ""),
            status=data.get("status", RunStatus.RUNNING.value),
            started_at=data.get("started_at", _now_iso()),
            ended_at=data.get("ended_at", ""),
            summary=data.get("summary", {}),
        )


@dataclass
class UnifiedEvent:
    event_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)
    caused_by_command_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "caused_by_command_id": self.caused_by_command_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedEvent":
        return cls(
            event_id=data.get("event_id", ""),
            type=data.get("type", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", _now_iso()),
            caused_by_command_id=data.get("caused_by_command_id"),
        )
