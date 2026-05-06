"""DecisionLog / ADR 测试。

覆盖：
- create: 创建 ADR 并持久化
- get: 按 ID 获取
- list_all: 列出所有 ADR
- accept: 从 proposed → accepted
- supersede: 从 proposed/accepted → superseded
- deprecate: → deprecated
- 状态转换约束验证
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph.decision_log import DecisionLog
from ralph.schema.adr import ADR, Alternative


@pytest.fixture
def log(tmp_path: Path) -> DecisionLog:
    return DecisionLog(tmp_path)


class TestCreate:
    def test_create_minimal(self, log: DecisionLog) -> None:
        adr = log.create(title="使用 PostgreSQL 作为主数据库")
        assert adr.adr_id.startswith("adr-")
        assert adr.title == "使用 PostgreSQL 作为主数据库"
        assert adr.status == "proposed"

    def test_create_full(self, log: DecisionLog) -> None:
        adr = log.create(
            title="使用 Redis 做缓存层",
            context="需要低延迟缓存，减少数据库压力",
            decision="使用 Redis Cluster 6.x，Sentinel 模式",
            alternatives=[
                {"name": "Memcached", "description": "简单 K/V 缓存",
                 "rejected_reason": "不支持持久化和集群模式，功能不如 Redis"},
                {"name": "本地内存缓存", "rejected_reason": "多实例间无法共享"},
            ],
            consequences="需维护 Redis 集群；数据结构选择需培训团队",
        )
        assert len(adr.alternatives) == 2
        assert adr.alternatives[0].name == "Memcached"
        assert adr.alternatives[1].rejected_reason

    def test_creates_file(self, log: DecisionLog, tmp_path: Path) -> None:
        adr = log.create(title="测试决策")
        assert (tmp_path / "decisions" / f"{adr.adr_id}.json").is_file()


class TestGet:
    def test_get_existing(self, log: DecisionLog) -> None:
        created = log.create(title="使用 gRPC 做服务间通信")
        fetched = log.get(created.adr_id)
        assert fetched is not None
        assert fetched.title == created.title

    def test_get_missing(self, log: DecisionLog) -> None:
        assert log.get("adr-nonexistent") is None


class TestListAll:
    def test_empty(self, log: DecisionLog) -> None:
        assert log.list_all() == []

    def test_multiple_sorted(self, log: DecisionLog) -> None:
        log.create(title="ADR A")
        log.create(title="ADR B")
        log.create(title="ADR C")
        result = log.list_all()
        assert len(result) == 3
        assert all("title" in r and "status" in r for r in result)


class TestStateTransitions:
    def test_accept_from_proposed(self, log: DecisionLog) -> None:
        adr = log.create(title="使用 Poetry 管理依赖")
        accepted = log.accept(adr.adr_id)
        assert accepted.status == "accepted"
        assert accepted.decided_at

    def test_accept_fails_on_accepted(self, log: DecisionLog) -> None:
        adr = log.create(title="测试")
        log.accept(adr.adr_id)
        with pytest.raises(ValueError, match="Cannot accept"):
            log.accept(adr.adr_id)

    def test_supersede_from_accepted(self, log: DecisionLog) -> None:
        adr = log.create(title="旧决策")
        log.accept(adr.adr_id)
        superseded = log.supersede(adr.adr_id, superseded_by="adr-new")
        assert superseded.status == "superseded"
        assert superseded.superseded_by == "adr-new"

    def test_supersede_from_proposed(self, log: DecisionLog) -> None:
        adr = log.create(title="待定决策")
        result = log.supersede(adr.adr_id, superseded_by="adr-better")
        assert result.status == "superseded"

    def test_deprecate(self, log: DecisionLog) -> None:
        adr = log.create(title="过时决策")
        result = log.deprecate(adr.adr_id)
        assert result.status == "deprecated"

    def test_status_not_found(self, log: DecisionLog) -> None:
        with pytest.raises(ValueError, match="not found"):
            log.accept("adr-ghost")


class TestRoundtrip:
    def test_full_lifecycle(self, log: DecisionLog) -> None:
        # create → accept → supersede
        adr = log.create(
            title="使用 FastAPI 做 Web 框架",
            context="需要异步支持、自动 OpenAPI 生成",
            decision="采用 FastAPI 0.100+",
            alternatives=[
                {"name": "Flask", "rejected_reason": "不支持原生 async"},
            ],
            consequences="需配套 Pydantic v2 数据校验",
        )
        adr_id = adr.adr_id

        accepted = log.accept(adr_id)
        assert accepted.status == "accepted"

        superseded = log.supersede(adr_id, superseded_by="adr-litestar")
        assert superseded.status == "superseded"

        # 验证持久化一致
        fetched = log.get(adr_id)
        assert fetched is not None
        assert fetched.status == "superseded"
        assert fetched.superseded_by == "adr-litestar"
        assert len(fetched.alternatives) == 1
