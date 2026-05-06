from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContinuationCheck:
    """判断是否继续下一轮的条件。"""
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


class TurnBasedExecutionEngine:
    def __init__(self, project_dir: Path | str):
        self._project_dir = Path(project_dir)
        self._checkpoints = self._project_dir / ".ralph" / "checkpoints"
        self._checkpoints.mkdir(parents=True, exist_ok=True)

    # ── Main Execution Loop ─────────────────────────────────────

    async def execute(
        self,
        work_id: str,
        *,
        max_turns: int = 10,
        runner: Any,
        context_engine: Any,
    ) -> dict[str, Any]:
        """执行多轮循环：runner → 收集结果 → 增量更新上下文 → checkpoint。

        Args:
            work_id: 工作单元 ID
            max_turns: 最大轮次
            runner: 具有 async run(work_id, context) 方法的执行器
            context_engine: ContextEngine 实例，提供 build_incremental()
        """
        all_turns: list[dict[str, Any]] = []

        for turn in range(1, max_turns + 1):
            checkpoint = self._build_checkpoint_meta(work_id, turn)
            incremental_ctx = context_engine.build_incremental(
                work_id=work_id,
                checkpoint=turn - 1,
            )

            try:
                result = await runner.run(work_id, context=incremental_ctx)
            except Exception as e:
                turn_result = TurnResult(
                    turn=turn,
                    work_id=work_id,
                    output={},
                    terminal=False,
                    error=str(e),
                )
                self._save_checkpoint(work_id, turn, turn_result)
                all_turns.append(self._turn_result_to_dict(turn_result))
                logger.warning("Turn %d for %s failed: %s", turn, work_id, e)
                break

            terminal = self._is_terminal(result)
            turn_result = TurnResult(
                turn=turn,
                work_id=work_id,
                output=result,
                token_usage=result.get("token_usage", {}) if isinstance(result, dict) else {},
                terminal=terminal,
            )
            self._save_checkpoint(work_id, turn, turn_result)
            all_turns.append(self._turn_result_to_dict(turn_result))

            if terminal:
                logger.info("Turn %d for %s reached terminal state", turn, work_id)
                break

        return {
            "work_id": work_id,
            "turns": all_turns,
            "total_turns": len(all_turns),
            "latest_turn": all_turns[-1] if all_turns else None,
            "completed": len(all_turns) > 0 and all_turns[-1].get("terminal", False),
        }

    # ── Checkpoint Management ───────────────────────────────────

    def _save_checkpoint(self, work_id: str, turn: int, result: TurnResult) -> None:
        """增量保存 checkpoint。"""
        path = self._checkpoints / f"{work_id}.turn-{turn}.json"
        data = self._turn_result_to_dict(result)
        data["_saved_at"] = datetime.now(UTC).isoformat()
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.rename(path)
            logger.debug("Saved checkpoint: %s", path.name)
        except OSError as e:
            logger.error("Failed to save checkpoint %s: %s", path.name, e)

    def _build_checkpoint_meta(self, work_id: str, turn: int) -> dict[str, Any]:
        return {
            "work_id": work_id,
            "turn": turn,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Terminal State Detection ────────────────────────────────

    def _is_terminal(self, result: Any) -> bool:
        """判断结果是否到达终端状态。"""
        if isinstance(result, dict):
            if result.get("terminal"):
                return True
            if result.get("status") in ("completed", "failed", "cancelled"):
                return True
        return False

    def _should_stop(self, result: dict[str, Any]) -> bool:
        """额外的停止条件检查。"""
        if result.get("stop_requested"):
            return True
        if result.get("max_retries_exceeded"):
            return True
        return False

    def _turn_result_to_dict(self, result: TurnResult) -> dict[str, Any]:
        return {
            "turn": result.turn,
            "work_id": result.work_id,
            "output": result.output,
            "token_usage": result.token_usage,
            "terminal": result.terminal,
            "error": result.error,
            "timestamp": result.timestamp,
        }

    # ── Query API (legacy) ──────────────────────────────────────

    def list_executions(self) -> list[str]:
        return sorted({p.name.split(".turn-")[0] for p in self._checkpoints.glob("*.turn-*.json")})

    def get_execution_status(self, work_id: str) -> dict[str, Any] | None:
        entries = sorted(self._checkpoints.glob(f"{work_id}.turn-*.json"))
        if not entries:
            return None
        turns = []
        for p in entries:
            try:
                turns.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return {"work_id": work_id, "turns": turns, "latest_turn": turns[-1] if turns else None}

    def restore_from_checkpoint(self, work_id: str, turn: int) -> dict[str, Any]:
        p = self._checkpoints / f"{work_id}.turn-{turn}.json"
        if not p.is_file():
            return {"success": False, "error": f"checkpoint not found: {p.name}"}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"invalid checkpoint: {e}"}
        return {"success": True, "work_id": work_id, "turn": turn, "checkpoint": data}
