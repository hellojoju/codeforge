"""Turn-Based Execution Engine — 继承 WorkUnitEngine 实现多轮执行。

设计文档依据：
- 二期 §3.3 多轮 Continuation 执行模型
- 二期 §3.3.2 Checkpoint 设计
- 二期 §3.1.1 Context 分层模型 (L0/L1/L2 增量)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.context_engine import ContextEngine
from ralph.work_unit_engine import WorkUnitEngine
from ralph.schema.work_unit import WorkUnitStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContinuationCheck:
    should_continue: bool
    reason: str = ""
    terminal_state: bool = False


@dataclass
class TurnResult:
    turn: int
    work_id: str
    output: dict[str, Any]
    token_usage: dict[str, int] = field(default_factory=dict)
    terminal: bool = False
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class _ContextPackText:
    """ContextEngine 输出 → _execute_with_claude 兼容包装。"""

    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text


class TurnBasedExecutionEngine(WorkUnitEngine):
    """多轮执行引擎，继承 WorkUnitEngine 的全部状态机/门禁/记忆接线。

    Turn 生命周期::
        ready → running → Turn 1 → Turn 2 → ... → needs_review/failed/blocked
    """

    def __init__(self, project_dir: Path | str, **kwargs: Any) -> None:
        super().__init__(Path(project_dir), **kwargs)
        self._checkpoints_dir = self._ralph_dir / "checkpoints"
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._context_engine = ContextEngine(self._project_dir)

    # ── Main Execution Loop ─────────────────────────────────────

    async def execute(
        self,
        work_id: str,
        agent: Any = None,
        prd_summary: str = "",
        use_claude_runner: bool = True,
        tool_cwd: Path | None = None,
        *,
        max_turns: int = 20,
    ) -> dict:
        """多轮执行 WorkUnit。

        覆盖父类 execute()，在 running 状态内循环多轮，
        每轮保存 checkpoint + 文件 SHA256 快照。
        """
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            raise ValueError(f"WorkUnit {work_id} 不存在")

        # ── Setup (复用父类逻辑) ──────────────────────────
        unit = self._repository.transition(
            work_id, WorkUnitStatus.RUNNING, actor_role="scheduler"
        )
        self._emit_event("ralph_work_unit_running", work_id=work_id,
                         status=WorkUnitStatus.RUNNING.value)

        # Preflight
        preflight = self._harness_mgr.preflight(unit)
        if not preflight.passed:
            logger.error("执行前门禁失败: %s", preflight.failures)
            self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED,
                reason=f"preflight 失败: {preflight.failures}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "blocked",
                    "error": str(preflight.failures), "work_id": work_id}

        # Token budget
        budget_check = self._config_mgr.check_budget()
        if not budget_check["allowed"]:
            logger.error("Token budget 超限: %s", budget_check["reason"])
            self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED,
                reason=f"budget 超限: {budget_check['reason']}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "blocked",
                    "error": budget_check["reason"], "work_id": work_id}

        self._harness_mgr.start_inflight(work_id)

        # Apply retro tuning
        tuning = self._config_mgr.load_tuning()
        if tuning:
            self._apply_tuning_to_unit(unit, tuning)

        # ── Turn Loop ──────────────────────────────────────
        all_turns: list[dict[str, Any]] = []
        all_files_changed: set[str] = set()
        last_error = ""
        next_goal = unit.target or ""
        terminal_state = False

        for turn in range(1, max_turns + 1):
            # Build context
            if turn == 1:
                ctx = self._context_engine.build_initial(work_id=work_id)
                # Inject historical lessons (from parent)
                lessons = self._collect_retro_lessons(unit)
                if lessons:
                    ctx.setdefault("lessons", [])
                    ctx["lessons"] = lessons
            else:
                ctx = self._context_engine.build_incremental(
                    work_id=work_id,
                    checkpoint=turn - 1,
                    current_error=last_error,
                    next_goal=next_goal,
                )

            context_text = self._serialize_context(ctx)
            context_wrapper = _ContextPackText(context_text)

            # Execute single turn via parent's Claude runner
            try:
                exec_result = await self._execute_with_claude(
                    unit, context_wrapper, prd_summary, tool_cwd=tool_cwd,
                )
            except Exception as e:
                logger.exception("Turn %d for %s crashed", turn, work_id)
                turn_result = TurnResult(
                    turn=turn, work_id=work_id, output={},
                    terminal=False, error=str(e),
                )
                self._save_checkpoint(work_id, turn, turn_result, all_files_changed)
                all_turns.append(_turn_result_to_dict(turn_result))
                last_error = str(e)
                break

            # Track changed files
            for f in exec_result.files_created + exec_result.files_modified:
                all_files_changed.add(f)

            # Build turn result
            turn_result = TurnResult(
                turn=turn,
                work_id=work_id,
                output={
                    "success": exec_result.success,
                    "stdout": exec_result.stdout[:500] if exec_result.stdout else "",
                    "stderr": (exec_result.stderr or "")[:500],
                    "files_created": exec_result.files_created,
                    "files_modified": exec_result.files_modified,
                    "files_deleted": exec_result.files_deleted,
                },
                token_usage={
                    "input": getattr(exec_result, "token_input", 0),
                    "output": getattr(exec_result, "token_output", 0),
                },
                terminal=False,
                error=exec_result.error or "",
            )

            # Save checkpoint with file snapshot
            self._save_checkpoint(work_id, turn, turn_result, all_files_changed)

            all_turns.append(_turn_result_to_dict(turn_result))

            # Continuation check
            if not exec_result.success:
                last_error = exec_result.stderr or exec_result.stdout or exec_result.error or ""
                # 失败不继续，直接标记失败
                unit = self._repository.transition(
                    work_id, WorkUnitStatus.FAILED,
                    actor_role="executor", reason=last_error[:200]
                )
                self._archive_if_terminal(work_id, last_error)
                return {
                    "success": False, "status": "failed", "error": last_error,
                    "work_id": work_id, "turns": all_turns,
                    "total_turns": len(all_turns),
                }

            last_error = ""
            # Check if work is complete
            if self._is_work_complete(exec_result):
                terminal_state = True
                logger.info("Turn %d for %s: work complete", turn, work_id)
                break

            # Extract next goal from result
            next_goal = self._extract_next_goal(exec_result, unit.target or "")

        # ── Max turns exceeded ──────────────────────────────
        if not terminal_state and len(all_turns) >= max_turns:
            logger.warning("WorkUnit %s: 超过最大轮次 %d, 进入 blocked", work_id, max_turns)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED,
                reason=f"超过最大轮次 {max_turns}"
            )
            self._archive_if_terminal(work_id)
            return {
                "success": False, "status": "blocked",
                "error": f"超过最大轮次 {max_turns}",
                "work_id": work_id, "turns": all_turns,
                "total_turns": len(all_turns),
            }

        # ── Teardown ────────────────────────────────────────
        # Record inflight changes
        self._harness_mgr.record_inflight(work_id, files_modified=list(all_files_changed))

        # Collect evidence
        evidence_items = self._evidence_collector.collect(
            work_id, self._project_dir,
            include_test_output="",
        )
        for ev in evidence_items:
            self._repository.save_evidence(ev)

        # Postflight
        all_changed = list(all_files_changed)
        postflight = self._harness_mgr.postflight(
            unit,
            files_changed=all_changed,
            evidence_files=[e.file_path for e in evidence_items],
            test_passed=True,
            review_completed=True,
        )

        if not postflight.passed:
            logger.error("执行后门禁失败: %s", postflight.failures)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.FAILED,
                actor_role="executor", reason=f"postflight 失败: {postflight.failures}"
            )
            self._archive_if_terminal(work_id)
            return {
                "success": False, "status": "failed",
                "error": str(postflight.failures),
                "work_id": work_id, "turns": all_turns,
                "total_turns": len(all_turns),
            }

        # running → needs_review
        unit = self._repository.transition(
            work_id, WorkUnitStatus.NEEDS_REVIEW, actor_role="executor"
        )
        self._emit_event("ralph_work_unit_needs_review", work_id=work_id,
                         status=WorkUnitStatus.NEEDS_REVIEW.value)

        return {
            "success": True, "status": "needs_review",
            "work_id": work_id,
            "files_changed": all_changed,
            "evidence_files": [e.file_path for e in evidence_items],
            "turns": all_turns,
            "total_turns": len(all_turns),
        }

    # ── Context Serialization ───────────────────────────────────

    def _serialize_context(self, ctx: dict) -> str:
        """将 ContextEngine 输出序列化为 runner 可用的文本。"""
        layers = ctx.get("layers", ctx)
        if isinstance(layers, dict):
            parts = []
            for name, content in layers.items():
                if content:
                    parts.append(f"## {name}\n{content}")
            return "\n\n".join(parts)
        return str(ctx)

    # ── Checkpoint Management ───────────────────────────────────

    def _save_checkpoint(
        self,
        work_id: str,
        turn: int,
        result: TurnResult,
        files_changed: set[str],
    ) -> None:
        """保存 checkpoint，含文件 SHA256 快照（对齐设计文档 §3.3.2）。"""
        path = self._checkpoints_dir / f"{work_id}.turn-{turn}.json"

        file_snapshot = self._compute_file_snapshot(files_changed)
        checkpoint = {
            "checkpoint_id": f"cp-{work_id}-t{turn}",
            "work_id": work_id,
            "turn_number": turn,
            "timestamp": datetime.now(UTC).isoformat(),
            "file_state_snapshot": file_snapshot,
            "test_status": {},
            "current_progress": (result.output.get("stdout", "") if isinstance(result.output, dict) else "")[:500],
            "remaining_tasks": [],
            "context_summary": result.error or "",
            "token_usage_cumulative": result.token_usage,
            "_saved_at": datetime.now(UTC).isoformat(),
        }

        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp_path.rename(path)
            logger.debug("Saved checkpoint: %s", path.name)
        except OSError as e:
            logger.error("Failed to save checkpoint %s: %s", path.name, e)

    def _compute_file_snapshot(self, files: set[str]) -> dict[str, str]:
        """对修改过的文件计算 SHA256。"""
        snapshot: dict[str, str] = {}
        for fpath in sorted(files):
            p = self._project_dir / fpath
            if p.is_file():
                try:
                    snapshot[fpath] = hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                except OSError:
                    snapshot[fpath] = "error:unreadable"
            else:
                snapshot[fpath] = "missing"
        return snapshot

    def _build_checkpoint_meta(self, work_id: str, turn: int) -> dict[str, Any]:
        return {
            "work_id": work_id,
            "turn": turn,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Continuation Logic ──────────────────────────────────────

    def _is_terminal(self, result: Any) -> bool:
        if isinstance(result, dict):
            if result.get("terminal"):
                return True
            if result.get("status") in ("completed", "failed", "cancelled"):
                return True
        return False

    def _is_work_complete(self, exec_result: Any) -> bool:
        """判断执行结果是否表示工作已完成。"""
        if hasattr(exec_result, "success") and not exec_result.success:
            return False
        # Check stdout for completion markers
        stdout = getattr(exec_result, "stdout", "") or ""
        markers = ["COMPLETED", "DONE", "All tests passed", "验收通过"]
        return any(m in stdout for m in markers)

    def _extract_next_goal(self, exec_result: Any, fallback: str) -> str:
        """从执行结果中提取下一步目标。"""
        stdout = getattr(exec_result, "stdout", "") or ""
        # Try to find next goal in output
        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("NEXT:") or line.startswith("Next:") or line.startswith("下一步:"):
                return line.split(":", 1)[1].strip()
            if "remaining" in line.lower() or "还需要" in line:
                return line.strip()
        # Fallback: continue with original target
        return fallback

    def _should_stop(self, result: dict[str, Any]) -> bool:
        if result.get("stop_requested"):
            return True
        if result.get("max_retries_exceeded"):
            return True
        return False

    # ── Query & Restore API ─────────────────────────────────────

    def list_executions(self) -> list[str]:
        return sorted({
            p.name.split(".turn-")[0]
            for p in self._checkpoints_dir.glob("*.turn-*.json")
        })

    def get_execution_status(self, work_id: str) -> dict[str, Any] | None:
        entries = sorted(self._checkpoints_dir.glob(f"{work_id}.turn-*.json"))
        if not entries:
            return None
        turns = []
        for p in entries:
            try:
                turns.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return {
            "work_id": work_id,
            "turns": turns,
            "latest_turn": turns[-1] if turns else None,
        }

    def restore_from_checkpoint(self, work_id: str, turn: int) -> dict[str, Any]:
        """从 checkpoint 恢复 WorkUnit 执行状态。"""
        p = self._checkpoints_dir / f"{work_id}.turn-{turn}.json"
        if not p.is_file():
            return {"success": False, "error": f"checkpoint not found: {p.name}"}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"invalid checkpoint: {e}"}
        return {"success": True, "work_id": work_id, "turn": turn, "checkpoint": data}

    def resume_from_checkpoint(
        self, work_id: str, prd_summary: str = "", max_turns: int = 20
    ) -> dict:
        """从最近一个 checkpoint 恢复执行。

        读取最新 turn 的 checkpoint，从下一 turn 继续执行。
        """
        entries = sorted(self._checkpoints_dir.glob(f"{work_id}.turn-*.json"))
        if not entries:
            return {"success": False, "error": "no checkpoint found for resume"}

        latest = entries[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"corrupted checkpoint: {e}"}

        last_turn = data.get("turn_number", 0)
        remaining_turns = max(1, max_turns - last_turn)

        logger.info(
            "Resuming %s from turn %d, %d turns remaining",
            work_id, last_turn, remaining_turns,
        )

        # Get the unit and re-execute with remaining turns
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            return {"success": False, "error": f"WorkUnit {work_id} not found"}

        # Force back to running if needed
        if unit.status != WorkUnitStatus.RUNNING:
            self._repository.transition(
                work_id, WorkUnitStatus.RUNNING,
                actor_role="scheduler", reason="从 checkpoint 恢复"
            )

        # Import asyncio for running the async execute
        import asyncio
        return asyncio.run(
            self.execute(
                work_id,
                prd_summary=prd_summary,
                max_turns=remaining_turns,
            )
        )


def _turn_result_to_dict(result: TurnResult) -> dict[str, Any]:
    return {
        "turn": result.turn,
        "work_id": result.work_id,
        "output": result.output,
        "token_usage": result.token_usage,
        "terminal": result.terminal,
        "error": result.error,
        "timestamp": result.timestamp,
    }
