from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.context_engine import ContextEngine, ContextLayer
from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus


@dataclass
class AgentResult:
    action: str
    work_id: str
    success: bool
    summary: str
    decision_rationale: str = ""
    dependency_check: list[str] = field(default_factory=list)
    risk_assessment: str = ""
    next_actions: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "work_id": self.work_id,
            "success": self.success,
            "summary": self.summary,
            "decision_rationale": self.decision_rationale,
            "dependency_check": self.dependency_check,
            "risk_assessment": self.risk_assessment,
            "next_actions": self.next_actions,
            "timestamp": self.timestamp,
        }


class PMAgent:
    """PM 调度 Agent。

    支持两种模式：
    - empty_memory: 仅 L0+L1 上下文，不加载完整历史
    - full_context: L0+L1+L2+L3，用于复杂决策
    """

    def __init__(self, project_dir: Path | str, engine: Any):
        self._project_dir = Path(project_dir)
        self._engine = engine
        self._repo = RalphRepository(self._project_dir / ".ralph")
        self._context_engine = ContextEngine(self._project_dir)

    def get_status(self) -> dict[str, Any]:
        units = self._repo.list_work_units()
        return {
            "running_count": sum(1 for u in units if u.status == WorkUnitStatus.RUNNING),
            "ready_count": sum(1 for u in units if u.status == WorkUnitStatus.READY),
            "total_count": len(units),
            "project_dir": str(self._project_dir),
        }

    def get_context(self) -> dict[str, Any]:
        return {"status": self.get_status(), "snapshot": self._repo.snapshot()}

    # ── Single Scheduling (legacy) ──────────────────────────────

    async def schedule_once(self) -> list[AgentResult]:
        results = await self.schedule_batch(mode="empty_memory", max_dispatches=1)
        return results

    # ── Batch Scheduling ────────────────────────────────────────

    async def schedule_batch(
        self,
        mode: str = "empty_memory",
        max_dispatches: int = 3,
    ) -> list[AgentResult]:
        """批量调度。

        Args:
            mode: "empty_memory" 仅 L0+L1, "full_context" L0+L1+L2+L3
            max_dispatches: 最多调度数量
        """
        ready = self._repo.list_work_units(status=WorkUnitStatus.READY)
        if not ready:
            return [AgentResult(
                action="no_op",
                work_id="",
                success=True,
                summary="No ready work units available",
                decision_rationale="队列中没有状态为 ready 的任务",
            )]

        candidates = ready[:max_dispatches]
        results: list[AgentResult] = []

        for candidate in candidates:
            # Check dependencies
            blockers = self._check_dependencies(candidate)
            if blockers:
                results.append(AgentResult(
                    action="blocked",
                    work_id=candidate.work_id,
                    success=False,
                    summary=f"Blocked by: {', '.join(blockers)}",
                    decision_rationale="依赖项未完成，无法调度",
                    dependency_check=blockers,
                    risk_assessment="low",
                ))
                continue

            # Check if should continue
            should_continue = self._check_continuation(candidate)
            if not should_continue:
                results.append(AgentResult(
                    action="skipped",
                    work_id=candidate.work_id,
                    success=False,
                    summary="Continuation check failed",
                    decision_rationale="不满足继续执行条件",
                ))
                continue

            # Build context based on mode
            if mode == "empty_memory":
                ctx = self._context_engine.build_initial(
                    work_id=candidate.work_id,
                    layers={ContextLayer.L0, ContextLayer.L1},
                )
            else:
                ctx = self._context_engine.build_initial(
                    work_id=candidate.work_id,
                    layers={ContextLayer.L0, ContextLayer.L1, ContextLayer.L2, ContextLayer.L3},
                )

            # Execute
            try:
                result = await self._engine.execute(candidate.work_id, context=ctx)
            except Exception as e:
                results.append(AgentResult(
                    action="dispatch",
                    work_id=candidate.work_id,
                    success=False,
                    summary=f"Execution failed: {e}",
                    decision_rationale="执行过程中发生异常",
                    risk_assessment="high",
                    next_actions=["retry", "investigate_error"],
                ))
                continue

            ok = bool(result.get("success")) if isinstance(result, dict) else False
            summary = result.get("status", "unknown") if isinstance(result, dict) else "unknown"

            results.append(AgentResult(
                action="dispatch",
                work_id=candidate.work_id,
                success=ok,
                summary=summary,
                decision_rationale=f"调度成功，模式={mode}",
                dependency_check=[],
                risk_assessment="low" if ok else "medium",
                next_actions=["monitor_progress"] if ok else ["retry"],
            ))

        return results

    # ── Dependency Checking ─────────────────────────────────────

    def _check_dependencies(self, work_unit: Any) -> list[str]:
        """检查 WorkUnit 的依赖是否满足。"""
        blockers: list[str] = []

        # Check explicit dependencies from work unit
        depends_on = getattr(work_unit, "dependencies", []) or []
        for dep_id in depends_on:
            dep_wu = self._repo.get_work_unit(dep_id)
            if dep_wu is None:
                blockers.append(f"dependency {dep_id} not found")
            elif dep_wu.status not in (WorkUnitStatus.ACCEPTED,):
                blockers.append(f"dependency {dep_id} is {dep_wu.status.value}")

        # Check blockers
        all_blockers = self._repo.list_blockers(work_id=work_unit.work_id, resolved=False)
        for b in all_blockers:
            blockers.append(f"blocker: {b.blocker_id}")

        return blockers

    # ── Continuation Check ──────────────────────────────────────

    def _check_continuation(self, work_unit: Any) -> bool:
        """判断是否需要继续执行下一轮。"""
        # Check if max turns exceeded
        execution_status = None
        if hasattr(self._engine, "get_execution_status"):
            execution_status = self._engine.get_execution_status(work_unit.work_id)

        if execution_status:
            turns = execution_status.get("turns", [])
            max_turns = getattr(work_unit, "max_turns", 10)
            if len(turns) >= max_turns:
                return False

        # Check if already completed
        if work_unit.status in (WorkUnitStatus.ACCEPTED,):
            return False

        return True
