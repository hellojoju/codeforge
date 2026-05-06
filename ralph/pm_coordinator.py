"""PMCoordinator — PM 调度编排层。

负责"空记忆调度"的完整编排：加载 L0+L1 → 决策下一步 → 调度执行 → 处理结果 → 更新状态。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.concurrency_controller import ConcurrencyController
from ralph.config_manager import RalphConfigManager
from ralph.schema.work_unit import WorkUnitStatus

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SchedulingDecision:
    """一次调度决策的结果。"""

    action: str  # "dispatch" | "wait" | "blocked" | "noop"
    work_id: str = ""
    reason: str = ""
    historical_context: list[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "work_id": self.work_id,
            "reason": self.reason,
            "historical_context": self.historical_context,
            "timestamp": self.timestamp,
        }


class PMCoordinator:
    """PM 调度编排器。

    整合 MemoryManager、RetrievalPipeline、KnowledgeGraphService、
    TurnBasedExecutionEngine，实现完整的调度周期。
    """

    def __init__(
        self,
        project_dir: Path | str,
        engine: Any,
        memory_manager: Any | None = None,
        retrieval_pipeline: Any | None = None,
        knowledge_graph: Any | None = None,
        issue_sync: Any | None = None,
        config_manager: RalphConfigManager | None = None,
        max_concurrent: int = 3,
        daily_token_limit: int = 1_000_000,
    ):
        self._project_dir = Path(project_dir)
        self._engine = engine
        self._memory_manager = memory_manager
        self._retrieval = retrieval_pipeline
        self._knowledge_graph = knowledge_graph
        self._issue_sync = issue_sync
        self._config = config_manager or RalphConfigManager(self._project_dir / ".ralph")
        self._concurrency = ConcurrencyController(
            max_concurrent=max_concurrent,
            daily_token_limit=daily_token_limit,
        )
        self._recent_decisions: list[SchedulingDecision] = []

    async def schedule_cycle(self, max_dispatches: int = 3) -> list[dict[str, Any]]:
        """完整调度周期：分析状态 → 决策 → 执行 → 处理结果。

        Returns:
            每个 WorkUnit 的处理结果列表
        """
        from ralph.pm_agent import PMAgent

        agent = PMAgent(self._project_dir, self._engine)
        results = await agent.schedule_batch(
            mode="empty_memory",
            max_dispatches=max_dispatches,
        )

        # 处理每个结果
        processed = []
        for result in results:
            processed_result = self._handle_result(result)
            processed.append(processed_result)

        # 记录调度事件
        self._config.append_scheduling_event({
            "type": "schedule_cycle",
            "dispatched": len(processed),
            "results": [r.to_dict() if hasattr(r, "to_dict") else r for r in processed],
        })

        return processed

    def _handle_result(self, result: Any) -> SchedulingDecision:
        """处理子 Agent 结构化返回。"""
        if hasattr(result, "to_dict"):
            r = result.to_dict()
        else:
            r = result

        success = r.get("success", False)
        work_id = r.get("work_id", "")
        action = r.get("action", "unknown")

        if success:
            decision = SchedulingDecision(
                action="dispatch",
                work_id=work_id,
                reason=r.get("summary", "Dispatched successfully"),
            )
        elif action == "blocked":
            decision = SchedulingDecision(
                action="blocked",
                work_id=work_id,
                reason=r.get("summary", "Blocked by dependencies"),
            )
        elif action == "no_op":
            decision = SchedulingDecision(
                action="noop",
                reason=r.get("summary", "No work available"),
            )
        else:
            decision = SchedulingDecision(
                action="wait",
                work_id=work_id,
                reason=r.get("summary", "Waiting"),
            )

        self._recent_decisions.append(decision)
        if len(self._recent_decisions) > 50:
            self._recent_decisions = self._recent_decisions[-50:]

        return decision

    def on_work_unit_status_change(
        self, work_id: str, new_status: WorkUnitStatus, issue_sync_id: str = ""
    ) -> None:
        """WorkUnit 状态变更时的回调。"""
        self._concurrency.release(work_id)

        if self._issue_sync is not None and issue_sync_id:
            try:
                self._issue_sync.on_ralph_status_change(work_id, new_status.value)
            except Exception as e:
                logger.warning("IssueSyncProtocol notification failed: %s", e)

    def get_status(self) -> dict[str, Any]:
        return {
            "concurrency": self._concurrency.status(),
            "recent_decisions": [d.to_dict() for d in self._recent_decisions[-10:]],
            "active_work_units": self._concurrency.active_count,
        }
