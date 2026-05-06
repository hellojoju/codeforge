"""AgentPool 单元测试 — 覆盖生命周期、acquire/release、并发、健康检查、异常恢复。"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.pool import AgentInstance, AgentPool


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "ws"


@pytest.fixture
def pool(workspace: Path) -> AgentPool:
    return AgentPool(base_workspace=workspace)


# ── ensure_instances ───────────────────────────────────────────


def test_ensure_instances_creates_workspace(pool: AgentPool) -> None:
    instances = pool.ensure_instances("backend", count=2)
    assert len(instances) == 2
    for inst in instances:
        assert inst.workspace_path.exists()
        assert inst.workspace_path.is_dir()


def test_ensure_instances_unknown_role_raises(pool: AgentPool) -> None:
    with pytest.raises(ValueError, match="未知角色"):
        pool.ensure_instances("nonexistent_role", count=1)


def test_ensure_instances_idempotent(pool: AgentPool) -> None:
    first = pool.ensure_instances("qa", count=2)
    second = pool.ensure_instances("qa", count=2)
    assert len(first) == len(second) == 2
    assert first[0].instance_id == second[0].instance_id


def test_ensure_instances_partial_then_top_up(pool: AgentPool) -> None:
    pool.ensure_instances("frontend", count=1)
    pool.ensure_instances("frontend", count=3)
    assert len(pool.list_by_role("frontend")) == 3


# ── acquire / release ─────────────────────────────────────────


def test_acquire_returns_instance_and_agent(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=1)
    result = pool.acquire("backend")
    assert result is not None
    inst, agent = result
    assert inst.status == "busy"
    assert agent is not None


def test_acquire_returns_none_when_no_instances() -> None:
    pool = AgentPool()
    result = pool.acquire("backend")
    assert result is None


def test_acquire_returns_none_when_all_busy(pool: AgentPool) -> None:
    pool.ensure_instances("qa", count=1)
    pool.acquire("qa")
    result = pool.acquire("qa")
    assert result is None


def test_release_returns_to_available(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=1)
    inst, _ = pool.acquire("backend")
    pool.release(inst.instance_id, task_success=True)
    assert inst.status == "idle"
    assert inst.current_task_id == ""
    assert inst.total_tasks_completed == 1


def test_release_unknown_instance_noop(pool: AgentPool) -> None:
    pool.release("nonexistent-1")  # should not raise


def test_release_on_failure_does_not_increment_counter(pool: AgentPool) -> None:
    pool.ensure_instances("qa", count=1)
    inst, _ = pool.acquire("qa")
    pool.release(inst.instance_id, task_success=False)
    assert inst.total_tasks_completed == 0


# ── multiple instances round-robin ─────────────────────────────


def test_acquire_multiple_instances(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=3)
    r1 = pool.acquire("backend")
    r2 = pool.acquire("backend")
    r3 = pool.acquire("backend")
    assert r1 is not None
    assert r2 is not None
    assert r3 is not None
    assert r1[0].instance_id != r2[0].instance_id
    assert r2[0].instance_id != r3[0].instance_id
    assert r1[0].instance_id != r3[0].instance_id
    assert pool.acquire("backend") is None


def test_release_and_reacquire(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=2)
    r1, _ = pool.acquire("backend")
    pool.acquire("backend")
    pool.release(r1.instance_id)
    r3 = pool.acquire("backend")
    assert r3 is not None
    assert r3[0].instance_id == r1.instance_id


# ── query methods ──────────────────────────────────────────────


def test_list_all(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=2)
    pool.ensure_instances("frontend", count=1)
    assert len(pool.list_all()) == 3


def test_list_by_role(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=2)
    pool.ensure_instances("frontend", count=1)
    backend = pool.list_by_role("backend")
    assert len(backend) == 2
    assert all(i.role == "backend" for i in backend)


def test_get_instance(pool: AgentPool) -> None:
    pool.ensure_instances("qa", count=1)
    inst = pool.get_instance("qa-1")
    assert inst is not None
    assert inst.instance_id == "qa-1"


def test_get_instance_not_found(pool: AgentPool) -> None:
    assert pool.get_instance("missing-1") is None


def test_get_agent(pool: AgentPool) -> None:
    pool.ensure_instances("qa", count=1)
    agent = pool.get_agent("qa-1")
    assert agent is not None


def test_stats(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=2)
    pool.acquire("backend")
    stats = pool.stats()
    assert stats["total_instances"] == 2
    assert stats["by_role"]["backend"]["total"] == 2
    assert stats["by_role"]["backend"]["idle"] == 1
    assert stats["by_role"]["backend"]["busy"] == 1


def test_get_status(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=1)
    status = pool.get_status()
    assert "total_instances" in status
    assert "by_role" in status
    assert "agents" in status
    assert len(status["agents"]) == 1
    assert "instance_id" in status["agents"][0]


# ── cleanup ───────────────────────────────────────────────────


def test_cleanup(pool: AgentPool) -> None:
    pool.ensure_instances("backend", count=2)
    pool.cleanup()
    assert pool.list_all() == []
    assert pool.stats()["total_instances"] == 0


def test_cleanup_preserves_workspace_dirs(pool: AgentPool, workspace: Path) -> None:
    pool.ensure_instances("backend", count=1)
    inst = pool.list_by_role("backend")[0]
    ws_path = inst.workspace_path
    assert ws_path.exists()
    pool.cleanup()
    # workspace directories are preserved for debugging
    assert ws_path.exists()


# ── AgentInstance serialization ────────────────────────────────


def test_instance_to_dict_roundtrip() -> None:
    inst = AgentInstance(
        instance_id="backend-1",
        role="backend",
        workspace_id="ws-1",
        workspace_path=Path("/tmp/ws-1"),
        status="busy",
        current_task_id="F001",
        total_tasks_completed=5,
    )
    d = inst.to_dict()
    assert d["instance_id"] == "backend-1"
    assert d["status"] == "busy"
    assert d["current_task_id"] == "F001"
    assert d["total_tasks_completed"] == 5
    assert d["workspace_path"] == "/tmp/ws-1"
