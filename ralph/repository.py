"""Ralph State Repository — .ralph/ 状态持久化

文档依据：
- 实施方案 §4.1 State Repository — 唯一事实来源、原子写入、拒绝非法状态流转
- 实施方案 §6 "保留和加强: 状态仓库升级为系统唯一事实来源"
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.schema.blocker import Blocker
from ralph.schema.evidence import Evidence
from ralph.schema.retro_record import RetroRecord
from ralph.schema.review_result import ReviewResult
from ralph.schema.state_unified import (
    BlockingStatus,
    FeatureStatus,
    RunStatus,
    TaskStatus,
    UnifiedBlockingIssue,
    UnifiedEvent,
    UnifiedExecutionRun,
    UnifiedFeature,
    UnifiedTask,
)
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
from ralph.state_machine import InvalidTransitionError, StateMachine

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RalphRepository:
    """Ralph 状态仓库。

    - 唯一事实来源
    - 原子写入（tmpfile + rename）
    - WorkUnit CRUD + 状态转换
    - Evidence、ReviewResult、Blocker 持久化
    - 和现有 ProjectStateRepository 共存
    """

    def __init__(self, ralph_dir: Path) -> None:
        self._ralph_dir = Path(ralph_dir)
        self._ralph_dir.mkdir(parents=True, exist_ok=True)
        self._state_machine = StateMachine(self._ralph_dir / "state")

        # 子目录
        self._work_units_dir = self._ralph_dir / "work_units"
        self._evidence_dir = self._ralph_dir / "evidence"
        self._reviews_dir = self._ralph_dir / "reviews"
        self._blockers_dir = self._ralph_dir / "blockers"
        self._retros_dir = self._ralph_dir / "retros"
        for d in [self._work_units_dir, self._evidence_dir, self._reviews_dir, self._blockers_dir, self._retros_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 统一状态存储（JSON Lines）
        self._state_dir = self._ralph_dir / "state_unified"
        self._state_dir.mkdir(parents=True, exist_ok=True)

        # 懒加载子仓库
        self._feature_repo: object | None = None

    @property
    def feature_repo(self) -> object:
        """FeatureRepository 懒加载."""
        if self._feature_repo is None:
            from ralph.repositories import FeatureRepository
            self._feature_repo = FeatureRepository(self._ralph_dir)
        return self._feature_repo

    # ── WorkUnit CRUD ─────────────────────────────────────────

    def save_work_unit(self, unit: WorkUnit) -> None:
        """保存 WorkUnit（原子写入）。"""
        path = self._work_units_dir / f"{unit.work_id}.json"
        self._atomic_write(path, self._serialize_work_unit(unit))
        logger.info("保存 WorkUnit: %s", unit.work_id)

    def get_work_unit(self, work_id: str) -> WorkUnit | None:
        """读取 WorkUnit。"""
        path = self._work_units_dir / f"{work_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize_work_unit(data)

    def list_work_units(self, status: WorkUnitStatus | None = None) -> list[WorkUnit]:
        """列出所有 WorkUnit，可按状态过滤。"""
        units = []
        for path in sorted(self._work_units_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            unit = self._deserialize_work_unit(data)
            if status is None or unit.status == status:
                units.append(unit)
        return units

    def delete_work_unit(self, work_id: str) -> bool:
        """删除 WorkUnit。"""
        path = self._work_units_dir / f"{work_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除 WorkUnit: %s", work_id)
            return True
        return False

    # ── 状态转换 ──────────────────────────────────────────────

    def transition(
        self,
        work_id: str,
        new_status: WorkUnitStatus,
        actor_role: str = "",
        reason: str = "",
    ) -> WorkUnit:
        """执行状态转换并持久化。

        对齐实施方案 §4.1：拒绝非法状态流转。
        """
        unit = self.get_work_unit(work_id)
        if unit is None:
            raise ValueError(f"WorkUnit {work_id} 不存在")

        new_unit = self._state_machine.transition(unit, new_status, actor_role, reason)
        self.save_work_unit(new_unit)
        return new_unit

    # ── Evidence ──────────────────────────────────────────────

    def save_evidence(self, evidence: Evidence) -> None:
        """保存证据。"""
        path = self._evidence_dir / f"{evidence.evidence_id}.json"
        self._atomic_write(path, asdict(evidence))

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        """读取证据。"""
        path = self._evidence_dir / f"{evidence_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Evidence(**data)

    def list_evidence(self, work_id: str | None = None) -> list[Evidence]:
        """列出证据，可按 work_id 过滤。"""
        items = []
        for path in sorted(self._evidence_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if work_id is None or data.get("work_id") == work_id:
                items.append(Evidence(**data))
        return items

    # ── ReviewResult ──────────────────────────────────────────

    def save_review(self, review: ReviewResult) -> None:
        """保存审查结论。"""
        path = self._reviews_dir / f"{review.work_id}_{review.reviewer_context_id}.json"
        self._atomic_write(path, self._serialize_review(review))

    def get_review(self, work_id: str, reviewer_context_id: str) -> ReviewResult | None:
        """读取审查结论。"""
        path = self._reviews_dir / f"{work_id}_{reviewer_context_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize_review(data)

    def list_reviews(self, work_id: str | None = None) -> list[ReviewResult]:
        """列出审查结论。"""
        items = []
        for path in sorted(self._reviews_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if work_id is None or data.get("work_id") == work_id:
                items.append(self._deserialize_review(data))
        return items

    # ── Blocker ───────────────────────────────────────────────

    def save_blocker(self, blocker: Blocker) -> None:
        """保存阻塞项。"""
        path = self._blockers_dir / f"{blocker.blocker_id}.json"
        self._atomic_write(path, asdict(blocker))

    def get_blocker(self, blocker_id: str) -> Blocker | None:
        """读取阻塞项。"""
        path = self._blockers_dir / f"{blocker_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Blocker(**data)

    def list_blockers(self, work_id: str | None = None, resolved: bool | None = None) -> list[Blocker]:
        """列出阻塞项。"""
        items = []
        for path in sorted(self._blockers_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if work_id is not None and data.get("work_id") != work_id:
                continue
            if resolved is not None and data.get("resolved") != resolved:
                continue
            items.append(Blocker(**data))
        return items

    # ── RetroRecord ───────────────────────────────────────────

    def save_retro(self, retro: RetroRecord) -> None:
        """保存反思回顾记录。"""
        path = self._retros_dir / f"{retro.retro_id}.json"
        self._atomic_write(path, self._serialize_retro(retro))

    def get_retro(self, retro_id: str) -> RetroRecord | None:
        """读取反思回顾记录。"""
        path = self._retros_dir / f"{retro_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize_retro(data)

    def list_retros(self, work_id: str | None = None, limit: int = 50) -> list[RetroRecord]:
        """列出反思回顾记录，按创建时间倒序。"""
        items = []
        for path in sorted(self._retros_dir.glob("*.json"), reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            if work_id is not None and data.get("work_id") != work_id:
                continue
            items.append(self._deserialize_retro(data))
            if len(items) >= limit:
                break
        return items

    # ── 转换日志 ──────────────────────────────────────────────

    def get_transitions(self, work_id: str | None = None) -> list[dict]:
        """读取转换日志。"""
        return self._state_machine.get_transitions(work_id)

    # ── 统一状态 CRUD ─────────────────────────────────────────

    def save_feature(self, feature: UnifiedFeature) -> None:
        """保存 Feature（统一事实源）。"""
        self._write_jsonl("features", feature.to_dict(), key="feature_id")

    def get_feature(self, feature_id: str) -> UnifiedFeature | None:
        """读取 Feature。"""
        data = self._read_jsonl("features", key="feature_id", value=feature_id)
        return UnifiedFeature.from_dict(data) if data else None

    def list_features(self, status: str | None = None) -> list[UnifiedFeature]:
        """列出所有 Feature，可按状态过滤。"""
        items = self._read_all_jsonl("features")
        features = [UnifiedFeature.from_dict(d) for d in items]
        if status:
            features = [f for f in features if f.status == status]
        return sorted(features, key=lambda f: f.created_at, reverse=True)

    def save_task(self, task: UnifiedTask) -> None:
        """保存 Task（统一事实源）。"""
        self._write_jsonl("tasks", task.to_dict(), key="task_id")

    def get_task(self, task_id: str) -> UnifiedTask | None:
        """读取 Task。"""
        data = self._read_jsonl("tasks", key="task_id", value=task_id)
        return UnifiedTask.from_dict(data) if data else None

    def list_tasks(self, feature_id: str | None = None, status: str | None = None) -> list[UnifiedTask]:
        """列出 Task，可按 Feature/状态过滤。"""
        items = self._read_all_jsonl("tasks")
        tasks = [UnifiedTask.from_dict(d) for d in items]
        if feature_id:
            tasks = [t for t in tasks if t.feature_id == feature_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda f: f.created_at, reverse=True)

    def save_blocking_issue(self, issue: UnifiedBlockingIssue) -> None:
        """保存阻塞项。"""
        self._write_jsonl("blocking_issues", issue.to_dict(), key="blocking_id")

    def get_blocking_issue(self, blocking_id: str) -> UnifiedBlockingIssue | None:
        """读取阻塞项。"""
        data = self._read_jsonl("blocking_issues", key="blocking_id", value=blocking_id)
        return UnifiedBlockingIssue.from_dict(data) if data else None

    def list_blocking_issues(self, status: str | None = None) -> list[UnifiedBlockingIssue]:
        """列出阻塞项，可按状态过滤。"""
        items = self._read_all_jsonl("blocking_issues")
        issues = [UnifiedBlockingIssue.from_dict(d) for d in items]
        if status:
            issues = [i for i in issues if i.status == status]
        return sorted(issues, key=lambda i: i.created_at, reverse=True)

    def resolve_blocking_issue(self, blocking_id: str, resolution: str = "") -> UnifiedBlockingIssue | None:
        """解除阻塞。"""
        issue = self.get_blocking_issue(blocking_id)
        if issue is None:
            return None
        from datetime import UTC, datetime
        resolved = UnifiedBlockingIssue(
            blocking_id=issue.blocking_id,
            type=issue.type,
            title=issue.title,
            details=issue.details,
            required_human_action=issue.required_human_action,
            status=BlockingStatus.RESOLVED,
            related_feature_id=issue.related_feature_id,
            related_task_id=issue.related_task_id,
            created_at=issue.created_at,
            resolved_at=datetime.now(UTC).isoformat(),
        )
        self.save_blocking_issue(resolved)
        return resolved

    def save_run(self, run: UnifiedExecutionRun) -> None:
        """保存执行轮次。"""
        self._write_jsonl("execution_runs", run.to_dict(), key="run_id")

    def get_current_run(self) -> UnifiedExecutionRun | None:
        """获取当前运行中的执行轮次。"""
        items = self._read_all_jsonl("execution_runs")
        runs = [UnifiedExecutionRun.from_dict(d) for d in items]
        running = [r for r in runs if r.status == RunStatus.RUNNING]
        return running[-1] if running else None

    # ── 事件溯源 ──────────────────────────────────────────────

    def append_event(self, event: UnifiedEvent) -> None:
        """追加事件（不可变日志）。"""
        path = self._state_dir / "events.jsonl"
        self._atomic_append(path, event.to_dict())

    def replay_events(self, since_event_id: str | None = None, limit: int = 500) -> list[UnifiedEvent]:
        """回放事件。"""
        events = self._read_all_events()
        if since_event_id:
            idx = next((i for i, e in enumerate(events) if e.event_id == since_event_id), -1)
            if idx >= 0:
                events = events[idx + 1:]
        return events[-limit:]

    # ── 快照 ──────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """返回当前完整状态快照。"""
        return {
            "features": [f.to_dict() for f in self.list_features()],
            "tasks": [t.to_dict() for t in self.list_tasks()],
            "blocking_issues": [i.to_dict() for i in self.list_blocking_issues()],
            "current_run": self.get_current_run().to_dict() if self.get_current_run() else None,
            "generated_at": _now_iso(),
        }

    # ── JSON Lines 读写 ───────────────────────────────────────

    def _write_jsonl(self, name: str, entry: dict, key: str) -> None:
        """写入 JSON Lines 文件（读全部→更新→全写回）。"""
        path = self._state_dir / f"{name}.jsonl"
        entries: list[dict] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    entries.append(json.loads(line))
        # 去重：移除同 key 的旧条目，追加新条目
        entries = [e for e in entries if e.get(key) != entry.get(key)]
        entries.append(entry)
        self._atomic_write_str(path, "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n")

    _ID_KEYS = {
        "features": "feature_id",
        "tasks": "task_id",
        "blocking_issues": "blocking_id",
        "execution_runs": "run_id",
        "events": "event_id",
    }

    def _read_jsonl(self, name: str, key: str, value: str) -> dict | None:
        """从 JSON Lines 文件中读取单条记录。"""
        path = self._state_dir / f"{name}.jsonl"
        if not path.is_file():
            return None
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                data = json.loads(line)
                if data.get(key) == value:
                    return data
        return None

    def _read_all_jsonl(self, name: str) -> list[dict]:
        """从 JSON Lines 文件中读取全部记录（去重后）。"""
        id_key = self._ID_KEYS.get(name, "id")
        path = self._state_dir / f"{name}.jsonl"
        if not path.is_file():
            return []
        seen: dict[str, dict] = {}
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                data = json.loads(line)
                id_value = data.get(id_key)
                if id_value:
                    seen[str(id_value)] = data
        return list(seen.values())
        return list(seen.values())

    def _read_all_events(self) -> list[UnifiedEvent]:
        """读取所有事件（追加模式，不需去重）。"""
        path = self._state_dir / "events.jsonl"
        if not path.is_file():
            return []
        events: list[UnifiedEvent] = []
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                events.append(UnifiedEvent.from_dict(json.loads(line)))
        return events

    @staticmethod
    def _atomic_write_str(path: Path, content: str) -> None:
        """原子写入字符串内容。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".tmp_",
            suffix=".jsonl",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _atomic_append(path: Path, data: dict) -> None:
        """原子追加一行到 JSON Lines 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # ── 原子写入 ──────────────────────────────────────────────

    @staticmethod
    def _atomic_write(path: Path, data: dict) -> None:
        """原子写入：先写临时文件，再 rename。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(path))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ── 序列化辅助 ────────────────────────────────────────────

    @staticmethod
    def _serialize_work_unit(unit: WorkUnit) -> dict:
        """WorkUnit → dict（处理 Enum 和嵌套对象）。"""
        data = asdict(unit)
        data["status"] = unit.status.value
        if unit.task_harness:
            data["task_harness"] = asdict(unit.task_harness)
        if unit.context_pack:
            data["context_pack"] = asdict(unit.context_pack)
        if unit.evidence:
            data["evidence"] = [asdict(e) for e in unit.evidence]
        if unit.review_result:
            data["review_result"] = RalphRepository._serialize_review(unit.review_result)
        return data

    @staticmethod
    def _deserialize_work_unit(data: dict) -> WorkUnit:
        """dict → WorkUnit。"""
        from ralph.schema.context_pack import ContextPack
        from ralph.schema.task_harness import RetryPolicy, TaskHarness, TimeoutPolicy

        # 处理 status enum
        data["status"] = WorkUnitStatus(data["status"])

        # 处理嵌套 TaskHarness
        if data.get("task_harness"):
            th_data = data["task_harness"]
            if "retry_policy" in th_data and isinstance(th_data["retry_policy"], dict):
                th_data["retry_policy"] = RetryPolicy(**th_data["retry_policy"])
            if "timeout_policy" in th_data and isinstance(th_data["timeout_policy"], dict):
                th_data["timeout_policy"] = TimeoutPolicy(**th_data["timeout_policy"])
            data["task_harness"] = TaskHarness(**th_data)

        # 处理嵌套 ContextPack
        if data.get("context_pack"):
            data["context_pack"] = ContextPack(**data["context_pack"])

        # 处理 Evidence 列表
        if data.get("evidence"):
            data["evidence"] = [Evidence(**e) for e in data["evidence"]]

        # 处理 ReviewResult
        if data.get("review_result"):
            data["review_result"] = RalphRepository._deserialize_review(data["review_result"])

        return WorkUnit(**data)

    @staticmethod
    def _serialize_review(review: ReviewResult) -> dict:
        data = asdict(review)
        return data

    @staticmethod
    def _deserialize_review(data: dict) -> ReviewResult:
        from ralph.schema.review_result import CriterionResult, Issue

        if data.get("criteria_results"):
            data["criteria_results"] = [CriterionResult(**c) for c in data["criteria_results"]]
        if data.get("issues_found"):
            data["issues_found"] = [Issue(**i) for i in data["issues_found"]]
        if data.get("dimension_results"):
            from ralph.schema.review_dimension import DimensionResult
            data["dimension_results"] = [DimensionResult(**d) for d in data["dimension_results"]]
        return ReviewResult(**data)

    @staticmethod
    def _serialize_retro(retro: RetroRecord) -> dict:
        data = asdict(retro)
        data["lessons"] = [asdict(l) for l in retro.lessons]
        return data

    @staticmethod
    def _deserialize_retro(data: dict) -> RetroRecord:
        from ralph.schema.retro_record import Lesson

        if data.get("lessons"):
            data["lessons"] = [Lesson(**l) for l in data["lessons"]]
        return RetroRecord(**data)
