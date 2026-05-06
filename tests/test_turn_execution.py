"""Turn 执行测试 — 覆盖多 turn 执行、checkpoint、ContinuationCheck、中断恢复。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ralph.turn_engine import (
    ContinuationCheck,
    TurnBasedExecutionEngine,
    TurnResult,
)
from ralph.work_unit_engine import WorkUnitEngine


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    (d / ".ralph").mkdir()
    # Minimal repo file to satisfy RalphRepository
    (d / ".ralph" / "state").mkdir(exist_ok=True)
    (d / ".ralph" / "work_units").mkdir(exist_ok=True)
    (d / ".ralph" / "checkpoints").mkdir(exist_ok=True)
    return d


class TestTurnBasedExecutionEngine:
    """T1.1: TurnEngine 继承 WorkUnitEngine。"""

    def test_inherits_work_unit_engine(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert isinstance(engine, WorkUnitEngine)
        assert engine._project_dir == project_dir

    def test_checkpoint_dir_created(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert (project_dir / ".ralph" / "checkpoints").is_dir()

    def test_has_context_engine(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine._context_engine is not None

    def test_inherits_parent_services(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine._repository is not None
        assert engine._harness_mgr is not None
        assert engine._guard is not None
        assert engine._config_mgr is not None


class TestCheckpoint:
    """T1.2: Checkpoint 文件 SHA256 快照。"""

    def test_save_checkpoint_creates_file(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        result = TurnResult(turn=1, work_id="wu-1", output={})
        engine._save_checkpoint("wu-1", 1, result, set())
        cps = list(engine._checkpoints_dir.glob("wu-1.turn-*.json"))
        assert len(cps) == 1

    def test_save_checkpoint_schema(self, project_dir: Path) -> None:
        import json
        engine = TurnBasedExecutionEngine(project_dir)
        result = TurnResult(turn=1, work_id="wu-1", output={"stdout": "test"})
        engine._save_checkpoint("wu-1", 1, result, {"test.py"})
        data = json.loads(
            (engine._checkpoints_dir / "wu-1.turn-1.json").read_text(encoding="utf-8")
        )
        assert data["checkpoint_id"] == "cp-wu-1-t1"
        assert data["work_id"] == "wu-1"
        assert data["turn_number"] == 1
        assert "file_state_snapshot" in data
        assert "token_usage_cumulative" in data
        assert "_saved_at" in data

    def test_file_sha256_snapshot(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        # Create a test file
        test_file = project_dir / "test.py"
        test_file.write_text("print('hello')")
        engine._save_checkpoint("wu-2", 1,
                                TurnResult(turn=1, work_id="wu-2", output={}),
                                {"test.py"})
        import json
        data = json.loads(
            (engine._checkpoints_dir / "wu-2.turn-1.json").read_text(encoding="utf-8")
        )
        assert "test.py" in data["file_state_snapshot"]
        assert len(data["file_state_snapshot"]["test.py"]) == 64  # SHA256 hex

    def test_missing_file_in_snapshot(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        engine._save_checkpoint("wu-3", 1,
                                TurnResult(turn=1, work_id="wu-3", output={}),
                                {"nonexistent.py"})
        import json
        data = json.loads(
            (engine._checkpoints_dir / "wu-3.turn-1.json").read_text(encoding="utf-8")
        )
        assert data["file_state_snapshot"]["nonexistent.py"] == "missing"

    def test_get_execution_status(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        engine._save_checkpoint("wu-4", 1,
                                TurnResult(turn=1, work_id="wu-4", output={}), set())
        engine._save_checkpoint("wu-4", 2,
                                TurnResult(turn=2, work_id="wu-4", output={}), set())
        status = engine.get_execution_status("wu-4")
        assert status is not None
        assert status["work_id"] == "wu-4"
        assert len(status["turns"]) == 2

    def test_get_execution_status_none(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine.get_execution_status("nonexistent") is None

    def test_restore_from_checkpoint(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        engine._save_checkpoint("wu-5", 3,
                                TurnResult(turn=3, work_id="wu-5", output={}), set())
        result = engine.restore_from_checkpoint("wu-5", 3)
        assert result["success"] is True
        assert result["work_id"] == "wu-5"
        assert result["turn"] == 3

    def test_restore_missing_checkpoint(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        result = engine.restore_from_checkpoint("wu-6", 99)
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_list_executions(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        engine._save_checkpoint("wu-a", 1,
                                TurnResult(turn=1, work_id="wu-a", output={}), set())
        engine._save_checkpoint("wu-b", 1,
                                TurnResult(turn=1, work_id="wu-b", output={}), set())
        executions = engine.list_executions()
        assert "wu-a" in executions
        assert "wu-b" in executions


class TestContinuationCheck:
    """ContinuationCheck 逻辑。"""

    def test_should_continue(self) -> None:
        check = ContinuationCheck(should_continue=True, reason="more work")
        assert check.should_continue is True
        assert check.reason == "more work"

    def test_terminal_state(self) -> None:
        check = ContinuationCheck(should_continue=False, terminal_state=True)
        assert check.terminal_state is True

    def test_is_terminal_from_dict(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine._is_terminal({"terminal": True}) is True
        assert engine._is_terminal({"status": "completed"}) is True
        assert engine._is_terminal({"status": "failed"}) is True
        assert engine._is_terminal({"status": "running"}) is False
        assert engine._is_terminal("not a dict") is False

    def test_should_stop(self, project_dir: Path) -> None:
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine._should_stop({"stop_requested": True}) is True
        assert engine._should_stop({"max_retries_exceeded": True}) is True
        assert engine._should_stop({}) is False


class TestTurnResult:
    """TurnResult 数据结构。"""

    def test_turn_result_defaults(self) -> None:
        tr = TurnResult(turn=1, work_id="wu-1", output={})
        assert tr.turn == 1
        assert tr.work_id == "wu-1"
        assert tr.output == {}
        assert tr.token_usage == {}
        assert tr.terminal is False
        assert tr.error == ""
        assert tr.timestamp != ""

    def test_turn_result_error(self) -> None:
        tr = TurnResult(turn=2, work_id="wu-2", output={},
                       token_usage={"input": 100}, error="crash")
        assert tr.turn == 2
        assert tr.token_usage == {"input": 100}
        assert tr.error == "crash"
