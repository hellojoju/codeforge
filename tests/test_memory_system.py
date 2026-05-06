"""记忆系统集成测试 — 覆盖 compaction → 短期 → 中期 → 长期全链路。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph.compaction_agent import CompactionAgent, CompactedSummary
from ralph.memory_archiver import MemoryArchiver
from ralph.memory_manager import MemoryManager


@pytest.fixture
def ralph_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".ralph"
    d.mkdir()
    return d


@pytest.fixture
def archiver(ralph_dir: Path) -> MemoryArchiver:
    return MemoryArchiver(ralph_dir)


@pytest.fixture
def memory(ralph_dir: Path) -> MemoryManager:
    return MemoryManager(ralph_dir)


# --- CompactionAgent ---

class TestCompactionAgent:
    def test_fallback_compact_basic(self) -> None:
        agent = CompactionAgent(config=None)
        result = agent.compact(
            work_id="wu-test-1",
            full_log="Created: src/auth/login.ts\nModified: src/auth/jwt.ts\nError: missing secret",
            status="accepted",
            executor_summary="实现了登录接口",
        )
        assert isinstance(result, CompactedSummary)
        assert result.work_id == "wu-test-1"
        assert result.status == "accepted"
        assert "实现了登录接口" in result.summary

    def test_fallback_extracts_files(self) -> None:
        agent = CompactionAgent(config=None)
        result = agent.compact(
            work_id="wu-test-2",
            full_log="Created: src/main.py\nModified: tests/test_main.py\nDeleted: old_file.py",
            status="accepted",
        )
        assert len(result.files_changed) == 3
        paths = [f["path"] for f in result.files_changed]
        assert "src/main.py" in paths

    def test_fallback_extracts_errors(self) -> None:
        agent = CompactionAgent(config=None)
        result = agent.compact(
            work_id="wu-test-3",
            full_log="Error: connection refused\nException: timeout\nFailed: build step 3",
            status="failed",
        )
        assert len(result.risks_introduced) > 0
        assert any("connection" in r["risk"] for r in result.risks_introduced)


# --- MemoryArchiver ---

class TestMemoryArchiver:
    def test_short_term_append_and_get(self, archiver: MemoryArchiver) -> None:
        archiver.append_short_term({"work_id": "wu-1", "status": "accepted", "title": "测试任务"})
        short = archiver.get_short_term()
        assert len(short) == 1
        assert short[0]["work_id"] == "wu-1"

    def test_short_term_fifo(self, archiver: MemoryArchiver) -> None:
        for i in range(25):
            archiver.append_short_term({"work_id": f"wu-{i}", "status": "accepted"})
        short = archiver.get_short_term()
        assert len(short) <= 20
        # 最早的 5 条已被淘汰到中期
        medium = archiver.get_medium_term()
        promoted_ids = [e["work_id"] for e in medium if e.get("archived_from_short_term")]
        assert len(promoted_ids) >= 5

    def test_medium_term_decision(self, archiver: MemoryArchiver) -> None:
        archiver.record_decision("使用 Redis 做缓存", "需要低延迟缓存层")
        medium = archiver.get_medium_term()
        decisions = [e for e in medium if e.get("type") == "decision"]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "使用 Redis 做缓存"

    def test_compact_on_terminal(self, archiver: MemoryArchiver) -> None:
        final_state = {
            "work_id": "wu-compact",
            "status": "accepted",
            "target": "实现用户认证",
            "summary": "完成了 JWT 登录接口",
        }
        path = archiver.compact_on_terminal("wu-compact", final_state)
        assert path.endswith("wu-compact.summary.json")

        # 短期记忆应有条目
        short = archiver.get_short_term()
        assert any(e["work_id"] == "wu-compact" for e in short)

    def test_compact_on_terminal_with_log(self, archiver: MemoryArchiver) -> None:
        final_state = {
            "work_id": "wu-full",
            "status": "failed",
            "target": "重构数据库层",
        }
        full_log = "Created: src/db.py\nError: migration failed\nError: lock timeout"
        path = archiver.compact_on_terminal("wu-full", final_state, full_log=full_log)
        assert "wu-full" in path

        short = archiver.get_short_term()
        entry = next(e for e in short if e["work_id"] == "wu-full")
        assert entry["status"] == "failed"

    def test_long_term_archive(self, archiver: MemoryArchiver) -> None:
        archiver.archive_task_log("wu-log", "# 完整日志\n\n执行成功")
        status = archiver.get_status()
        assert status["long_term"]["count"] >= 1

    def test_search_across_tiers(self, archiver: MemoryArchiver) -> None:
        archiver.append_short_term({"work_id": "wu-search", "status": "accepted",
                                     "title": "Redis 缓存实现"})
        archiver.record_decision("使用 Redis Sentinel", "高可用缓存")
        results = archiver.search("Redis")
        assert len(results) >= 1

    def test_get_status(self, archiver: MemoryArchiver) -> None:
        status = archiver.get_status()
        assert "short_term" in status
        assert "medium_term" in status
        assert "long_term" in status
        assert status["short_term"]["max"] == 20


# --- MemoryManager L1 Snapshot ---

class TestMemoryManagerL1:
    def test_l1_snapshot_basic(self, memory: MemoryManager, archiver: MemoryArchiver) -> None:
        archiver.append_short_term({"work_id": "wu-l1", "status": "accepted",
                                     "summary": "完成认证模块"})
        archiver.record_decision("使用 JWT", "认证方案")

        snapshot = memory.get_l1_snapshot(
            [{"work_id": "wu-active", "status": "running"}],
            archiver=archiver,
        )
        assert snapshot["active_count"] == 1
        assert len(snapshot["recent_summaries"]) >= 1
        assert len(snapshot["key_decisions"]) >= 1
        assert "generated_at" in snapshot

    def test_l1_snapshot_with_blockers(self, memory: MemoryManager,
                                        archiver: MemoryArchiver) -> None:
        snapshot = memory.get_l1_snapshot([], archiver=archiver)
        assert "blockers" in snapshot
        assert isinstance(snapshot["blockers"], list)

    def test_l1_snapshot_no_archiver(self, memory: MemoryManager) -> None:
        snapshot = memory.get_l1_snapshot(
            [{"work_id": "wu-1", "status": "running"}],
        )
        assert snapshot["active_count"] == 1
        assert snapshot["recent_summaries"] == []
        assert snapshot["key_decisions"] == []


# --- Full Pipeline ---

class TestMemoryPipeline:
    def test_full_compaction_pipeline(self, ralph_dir: Path) -> None:
        """端到端：终态 → CompactionAgent 压缩 → 短期记忆 → L1 快照。"""
        archiver = MemoryArchiver(ralph_dir)
        memory_mgr = MemoryManager(ralph_dir)

        final_state = {
            "work_id": "wu-e2e",
            "status": "accepted",
            "target": "实现搜索功能",
            "summary": "Elasticsearch 集成完成",
        }
        exec_log = (
            "Created: src/search/engine.py\n"
            "Modified: src/api/routes.py\n"
            "Error: index mapping mismatch\n"
            "Error: connection pool exhausted"
        )

        # 1. 压缩
        path = archiver.compact_on_terminal("wu-e2e", final_state, full_log=exec_log)
        assert "wu-e2e" in path

        # 2. 短期记忆有摘要
        short = archiver.get_short_term()
        entry = next(e for e in short if e["work_id"] == "wu-e2e")
        assert entry["status"] == "accepted"
        assert len(entry.get("summary", "")) > 0

        # 3. L1 快照包含摘要
        snapshot = memory_mgr.get_l1_snapshot([], archiver=archiver)
        assert any(s["work_id"] == "wu-e2e" for s in snapshot["recent_summaries"])
