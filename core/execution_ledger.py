"""执行计划台账 — 审计文件，记录每次执行的完整生命周期"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from core.config import EXECUTION_LEDGER_FILE

if TYPE_CHECKING:
    from dashboard.state_repository import ProjectStateRepository


class ExecutionStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED = "blocked"


@dataclass
class ExecutionEntry:
    feature_id: str
    status: str
    agent_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    files_changed: list[str] = field(default_factory=list)
    retry_count: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExecutionLedger:
    """执行台账，记录每个 Feature 的执行历史。

    当提供 repository 时，写入和查询均委托给 Repository（唯一事实源）。
    否则回退到本地文件存储（向后兼容）。
    """

    def __init__(self, ledger_file: Path | None = None, *, repository: ProjectStateRepository | None = None) -> None:
        self._repository = repository
        self._ledger_file = ledger_file or EXECUTION_LEDGER_FILE
        self._entries: list[ExecutionEntry] = []
        self._load()

    def _load(self) -> None:
        if self._ledger_file.exists():
            data = json.loads(self._ledger_file.read_text(encoding="utf-8"))
            self._entries = [ExecutionEntry.from_dict(e) for e in data.get("executions", [])]

    def _save(self) -> None:
        self._ledger_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "executions": [e.to_dict() for e in self._entries],
            "summary": self.get_summary(),
        }
        self._ledger_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def log_execution(
        self,
        feature_id: str,
        status: ExecutionStatus,
        agent_id: str = "",
        files_changed: list[str] | None = None,
        error: str = "",
    ) -> ExecutionEntry:
        entry = ExecutionEntry(
            feature_id=feature_id,
            status=status.value,
            agent_id=agent_id,
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat() if status in (
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.BLOCKED
            ) else "",
            error=error,
            files_changed=files_changed or [],
        )
        if self._repository is not None:
            self._repository.log_execution(entry.to_dict())
        else:
            import warnings
            warnings.warn(
                "ExecutionLedger without a repository is deprecated; "
                "execution entries will only be saved to a local JSON file.",
                DeprecationWarning,
                stacklevel=2,
            )
            self._entries.append(entry)
            self._save()
        return entry

    def get_feature_history(self, feature_id: str) -> list[ExecutionEntry]:
        if self._repository is not None:
            raw = self._repository.get_execution_history(feature_id=feature_id)
            return [ExecutionEntry.from_dict(e) for e in raw]
        return [e for e in self._entries if e.feature_id == feature_id]

    def get_summary(self) -> dict:
        if self._repository is not None:
            return self._repository.get_execution_summary()
        total = len(self._entries)
        completed = sum(1 for e in self._entries if e.status == ExecutionStatus.COMPLETED.value)
        failed = sum(1 for e in self._entries if e.status == ExecutionStatus.FAILED.value)
        blocked = sum(1 for e in self._entries if e.status == ExecutionStatus.BLOCKED.value)
        retrying = sum(1 for e in self._entries if e.status == ExecutionStatus.RETRYING.value)
        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
            "retrying": retrying,
        }
