"""Ralph API 端点测试。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from dashboard.api.routes import create_dashboard_app
from dashboard.event_bus import EventBus
from dashboard.state_repository import ProjectStateRepository
from ralph.repository import RalphRepository
from ralph.schema.blocker import Blocker
from ralph.schema.evidence import Evidence
from ralph.schema.review_result import CriterionResult, Issue, ReviewResult
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus


@pytest.fixture
def event_bus(tmp_path: Path) -> EventBus:
    return EventBus(log_file=tmp_path / "events.log")


@pytest.fixture
def repo(tmp_path: Path) -> ProjectStateRepository:
    return ProjectStateRepository(
        base_dir=tmp_path,
        project_id="test_proj",
        run_id="run_001",
    )


@pytest.fixture
def ralph_repo(tmp_path: Path) -> RalphRepository:
    ralph_dir = tmp_path / ".ralph"
    return RalphRepository(ralph_dir)


@pytest.fixture
def app(event_bus: EventBus, repo: ProjectStateRepository, ralph_repo: RalphRepository):
    return create_dashboard_app(
        event_bus=event_bus,
        repository=repo,
        ralph_repository=ralph_repo,
    )


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def test_client(app):
    return TestClient(app)


# --- GET /api/ralph/health ---


async def test_ralph_health(client):
    resp = await client.get("/api/ralph/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "work_units_count" in data
    assert "timestamp" in data


# --- GET /api/ralph/work-units ---


async def test_ralph_list_work_units_empty(client):
    resp = await client.get("/api/ralph/work-units")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


async def test_ralph_list_work_units_with_data(app, ralph_repo):
    # 创建测试 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
        status=WorkUnitStatus.READY,
    )
    ralph_repo.save_work_unit(unit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["work_id"] == "W-001"
        assert data[0]["status"] == "ready"


async def test_ralph_list_work_units_with_status_filter(app, ralph_repo):
    # 创建不同状态的 WorkUnit
    unit1 = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="任务1",
        status=WorkUnitStatus.ACCEPTED,
    )
    unit2 = WorkUnit(
        work_id="W-002",
        work_type="测试",
        producer_role="qa",
        reviewer_role="pm",
        expected_output="测试功能",
        title="任务2",
        status=WorkUnitStatus.BLOCKED,
    )
    ralph_repo.save_work_unit(unit1)
    ralph_repo.save_work_unit(unit2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 过滤 accepted
        resp = await client.get("/api/ralph/work-units", params={"status": "accepted"})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["work_id"] == "W-001"

        # 过滤 blocked
        resp = await client.get("/api/ralph/work-units", params={"status": "blocked"})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["work_id"] == "W-002"


async def test_ralph_list_work_units_invalid_status(client):
    resp = await client.get("/api/ralph/work-units", params={"status": "invalid_status"})
    assert resp.status_code == 400


# --- GET /api/ralph/work-units/{work_id} ---


async def test_ralph_get_work_unit_success(app, ralph_repo):
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
        status=WorkUnitStatus.READY,
    )
    ralph_repo.save_work_unit(unit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["work_id"] == "W-001"
        assert data["title"] == "测试任务"
        assert data["status"] == "ready"


async def test_ralph_get_work_unit_not_found(client):
    resp = await client.get("/api/ralph/work-units/NONEXISTENT")
    assert resp.status_code == 404


# --- GET /api/ralph/work-units/{work_id}/evidence ---


async def test_ralph_list_evidence_success(app, ralph_repo):
    # 先创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建证据
    evidence = Evidence(
        evidence_id="EV-001",
        work_id="W-001",
        evidence_type="diff",
        file_path="W-001/diff.txt",
        description="代码变更",
    )
    ralph_repo.save_evidence(evidence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["file_name"] == "diff.txt"


async def test_ralph_list_evidence_work_unit_not_found(client):
    resp = await client.get("/api/ralph/work-units/NONEXISTENT/evidence")
    assert resp.status_code == 404


# --- GET /api/ralph/work-units/{work_id}/evidence/{file_path} ---


async def test_ralph_get_evidence_file_success(app, ralph_repo, tmp_path):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建证据文件
    evidence_file = ralph_repo._evidence_dir / "W-001" / "diff.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text("diff content here")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/evidence/W-001/diff.txt")
        assert resp.status_code == 200
        assert resp.text == "diff content here"
        assert resp.headers["X-Truncated"] == "false"


async def test_ralph_get_evidence_file_path_traversal(app, ralph_repo, tmp_path):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 尝试路径遍历 - 使用 %2E 编码来绕过 Starlette 的路径规范化
        # %2E = . 所以 %2E%2E = ..
        resp = await client.get("/api/ralph/work-units/W-001/evidence/%2E%2E/%2E%2E/%2E%2E/etc/passwd")
        assert resp.status_code == 403


async def test_ralph_get_evidence_file_not_found(app, ralph_repo):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/evidence/nonexistent.txt")
        assert resp.status_code == 404


async def test_ralph_get_evidence_file_truncation(app, ralph_repo):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建大文件 (>100KB)
    evidence_file = ralph_repo._evidence_dir / "W-001" / "large.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    large_content = "x" * (100 * 1024 + 1000)  # 超过 100KB
    evidence_file.write_text(large_content)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/evidence/W-001/large.txt")
        assert resp.status_code == 200
        assert resp.headers["X-Truncated"] == "true"
        assert "TRUNCATED" in resp.text


async def test_ralph_get_evidence_file_redaction(app, ralph_repo):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建包含敏感信息的文件
    evidence_file = ralph_repo._evidence_dir / "W-001" / "config.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text('api_key = "sk-1234567890abcdef"\npassword = "secret123"')

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/evidence/W-001/config.txt")
        assert resp.status_code == 200
        assert "***REDACTED***" in resp.text
        assert "sk-1234567890abcdef" not in resp.text
        assert "secret123" not in resp.text


# --- GET /api/ralph/reviews/{work_id} ---


async def test_ralph_list_reviews_success(app, ralph_repo):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建 Review
    review = ReviewResult(
        work_id="W-001",
        reviewer_context_id="reviewer-1",
        review_type="功能完整性",
        conclusion="通过",
        recommended_action="接受",
        criteria_results=[CriterionResult(criterion="功能完整", passed=True)],
    )
    ralph_repo.save_review(review)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["conclusion"] == "通过"


async def test_ralph_list_reviews_work_unit_not_found(client):
    resp = await client.get("/api/ralph/work-units/NONEXISTENT/reviews")
    assert resp.status_code == 404


# --- GET /api/ralph/blockers ---


async def test_ralph_list_blockers(app, ralph_repo):
    # 创建 WorkUnit
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
    )
    ralph_repo.save_work_unit(unit)

    # 创建 Blocker
    blocker = Blocker(
        blocker_id="B-001",
        work_id="W-001",
        reason="依赖未完成",
        blocker_type="dependency",
        resolved=False,
    )
    ralph_repo.save_blocker(blocker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 列出所有 blockers
        resp = await client.get("/api/ralph/blockers")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["category"] == "dependency"
        assert data[0]["reason"] == "依赖未完成"

        # 按 work_id 过滤
        resp = await client.get("/api/ralph/blockers", params={"work_id": "W-001"})
        data = resp.json()
        assert len(data) == 1

        # 按 resolved 过滤
        resp = await client.get("/api/ralph/blockers", params={"resolved": "false"})
        data = resp.json()
        assert len(data) == 1


# --- GET /api/ralph/pending-actions ---


async def test_ralph_pending_actions(app, ralph_repo, repo):
    # 创建不同状态的 WorkUnit
    blocked_unit = WorkUnit(
        work_id="W-BLOCKED",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="阻塞任务",
        status=WorkUnitStatus.BLOCKED,
    )
    ralph_repo.save_work_unit(blocked_unit)

    # 创建 Blocker
    blocker = Blocker(
        blocker_id="B-001",
        work_id="W-BLOCKED",
        reason="权限不足",
        blocker_type="permission",
        resolved=False,
    )
    ralph_repo.save_blocker(blocker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/pending-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


# --- GET /api/ralph/transitions/{work_id} ---


async def test_ralph_get_transitions(app, ralph_repo):
    # 创建 WorkUnit 并进行状态转换
    unit = WorkUnit(
        work_id="W-001",
        work_type="开发",
        producer_role="backend",
        reviewer_role="qa",
        expected_output="实现功能",
        title="测试任务",
        status=WorkUnitStatus.DRAFT,
    )
    ralph_repo.save_work_unit(unit)

    # 执行状态转换
    ralph_repo.transition("W-001", WorkUnitStatus.READY, actor_role="scheduler", reason="准备就绪")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/work-units/W-001/transitions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


async def test_ralph_get_transitions_work_unit_not_found(client):
    resp = await client.get("/api/ralph/work-units/NONEXISTENT/transitions")
    assert resp.status_code == 404


# --- GET /api/ralph/summary ---


async def test_ralph_summary(app, ralph_repo):
    # 创建多个 WorkUnit
    for i, status in enumerate([WorkUnitStatus.ACCEPTED, WorkUnitStatus.ACCEPTED, WorkUnitStatus.FAILED]):
        unit = WorkUnit(
            work_id=f"W-{i:03d}",
            work_type="开发",
            producer_role="backend",
            reviewer_role="qa",
            expected_output="实现功能",
            title=f"任务{i}",
            status=status,
        )
        ralph_repo.save_work_unit(unit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ralph/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_work_units"] == 3
        assert data["status_counts"]["accepted"] == 2
        assert data["status_counts"]["failed"] == 1
        assert "success_rate_percent" in data
        assert "timestamp" in data


# --- POST /api/ralph/commands ---


async def test_ralph_create_command_success(client):
    resp = await client.post(
        "/api/ralph/commands",
        json={"command_type": "start_run", "payload": {"test": True}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "command_id" in data
    assert data["status"] == "pending"
    assert data["was_duplicate"] is False


async def test_ralph_create_command_missing_type(client):
    resp = await client.post("/api/ralph/commands", json={"payload": {}})
    assert resp.status_code == 422


async def test_ralph_create_command_idempotent(client, repo):
    key = "test-idempotency-key-001"

    # 第一次创建
    resp1 = await client.post(
        "/api/ralph/commands",
        json={"command_type": "execute_work_unit", "target_id": "W-001", "idempotency_key": key},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["was_duplicate"] is False
    cmd_id = data1["command_id"]

    # 重复创建（相同 idempotency_key）
    resp2 = await client.post(
        "/api/ralph/commands",
        json={"command_type": "execute_work_unit", "target_id": "W-001", "idempotency_key": key},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["command_id"] == cmd_id
    assert data2["was_duplicate"] is True


# --- GET /api/ralph/commands/{command_id} ---


async def test_ralph_get_command_success(client):
    # 先创建 Command
    create_resp = await client.post(
        "/api/ralph/commands",
        json={"command_type": "test_command"},
    )
    cmd_id = create_resp.json()["command_id"]

    # 查询 Command
    resp = await client.get(f"/api/ralph/commands/{cmd_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["command_id"] == cmd_id
    assert data["type"] == "test_command"


async def test_ralph_get_command_not_found(client):
    resp = await client.get("/api/ralph/commands/NONEXISTENT")
    assert resp.status_code == 404


# --- POST /api/ralph/commands/{command_id}/cancel ---


async def test_ralph_cancel_command_success(client):
    # 先创建 Command
    create_resp = await client.post(
        "/api/ralph/commands",
        json={"command_type": "test_command"},
    )
    cmd_id = create_resp.json()["command_id"]

    # 取消 Command
    resp = await client.post(f"/api/ralph/commands/{cmd_id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "cancelled"

    # 验证状态已更新
    get_resp = await client.get(f"/api/ralph/commands/{cmd_id}")
    assert get_resp.json()["status"] == "cancelled"


async def test_ralph_cancel_command_not_found(client):
    resp = await client.post("/api/ralph/commands/NONEXISTENT/cancel")
    assert resp.status_code == 404


async def test_ralph_cancel_command_wrong_status(client):
    # 先创建 Command
    create_resp = await client.post(
        "/api/ralph/commands",
        json={"command_type": "test_command"},
    )
    cmd_id = create_resp.json()["command_id"]

    # 手动修改状态为 applied
    # 注意：这里我们通过内部接口修改，实际测试中可能需要其他方式
    # 这里我们测试已经 cancelled 的 command 不能再取消
    await client.post(f"/api/ralph/commands/{cmd_id}/cancel")

    # 再次取消应该失败
    resp = await client.post(f"/api/ralph/commands/{cmd_id}/cancel")
    assert resp.status_code == 409


# --- GET /api/ralph/commands ---


async def test_ralph_list_commands_empty(client):
    """没有 Command 时返回空列表。"""
    resp = await client.get("/api/ralph/commands")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


async def test_ralph_list_commands_with_data(client):
    """创建多个 Command 后列出所有。"""
    # 创建几个不同状态的 Command
    await client.post(
        "/api/ralph/commands",
        json={"command_type": "start_run"},
    )
    await client.post(
        "/api/ralph/commands",
        json={"command_type": "execute_work_unit", "target_id": "W-001"},
    )

    resp = await client.get("/api/ralph/commands")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    assert all("command_id" in cmd for cmd in data)
    assert all("type" in cmd for cmd in data)
    assert all("status" in cmd for cmd in data)


async def test_ralph_list_commands_with_status_filter(client):
    """按 status 过滤 Command 列表。"""
    # 创建 pending 命令
    create_resp = await client.post(
        "/api/ralph/commands",
        json={"command_type": "execute_work_unit", "target_id": "W-001"},
    )
    cmd_id = create_resp.json()["command_id"]

    # 取消一个命令使其状态变为 cancelled
    await client.post(f"/api/ralph/commands/{cmd_id}/cancel")

    # 创建另一个 pending 命令
    await client.post(
        "/api/ralph/commands",
        json={"command_type": "start_run"},
    )

    # 只过滤 pending
    resp = await client.get("/api/ralph/commands", params={"status": "pending"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["status"] == "pending" for c in data)
    assert len(data) >= 1

    # 只过滤 cancelled
    resp = await client.get("/api/ralph/commands", params={"status": "cancelled"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["status"] == "cancelled" for c in data)
    assert len(data) >= 1


# --- GET /api/ralph/reports ---


async def test_ralph_list_reports_empty(client):
    """没有报告时返回空列表。"""
    resp = await client.get("/api/ralph/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


async def test_ralph_list_reports_after_generate(client):
    """生成报告后 list 应包含该报告。"""
    # 先生成报告
    gen_resp = await client.post(
        "/api/ralph/reports/generate",
        json={"title": "测试报告", "filename": "test_report.md"},
    )
    assert gen_resp.status_code == 200
    assert gen_resp.json()["success"] is True

    # 列出报告
    resp = await client.get("/api/ralph/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "test_report.md"
    assert "size_bytes" in data[0]


# --- POST /api/ralph/reports/generate ---


async def test_ralph_generate_report_default_title(client):
    """使用默认标题生成报告。"""
    resp = await client.post("/api/ralph/reports/generate", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["name"] == "report.md"
    assert "content" in data
    assert "# 研发报告" in data["content"]


async def test_ralph_generate_report_custom_title(client):
    """使用自定义标题生成报告。"""
    resp = await client.post(
        "/api/ralph/reports/generate",
        json={"title": "周报", "filename": "weekly.md"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["name"] == "weekly.md"
    assert "# 周报" in data["content"]


# --- GET /api/ralph/reports/{name} ---


async def test_ralph_get_report_success(client):
    """获取存在的报告。"""
    # 先生成报告
    gen_resp = await client.post(
        "/api/ralph/reports/generate",
        json={"title": "项目总结", "filename": "summary.md"},
    )
    assert gen_resp.status_code == 200

    # 获取报告
    resp = await client.get("/api/ralph/reports/summary.md")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "summary.md"
    assert "# 项目总结" in data["content"]
    assert "size_bytes" in data


async def test_ralph_get_report_not_found(client):
    """获取不存在的报告返回 404。"""
    resp = await client.get("/api/ralph/reports/nonexistent.md")
    assert resp.status_code == 404


async def test_ralph_get_report_path_traversal(client):
    """防止路径遍历攻击。"""
    # 使用 %2E%2E 编码绕过 Starlette 的路径规范化
    resp = await client.get("/api/ralph/reports/%2E%2E/%2E%2E/etc/passwd")
    assert resp.status_code == 403


# ==================== Events API Tests ====================


async def test_ralph_list_events_empty(client):
    """空事件列表返回空数组。"""
    resp = await client.get("/api/ralph/events")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_ralph_list_events_with_data(client, repo):
    """创建事件后可通过 API 查询。"""
    # 直接向 repository 写入事件
    repo.append_event(type="test_event", payload={"key": "value"})

    resp = await client.get("/api/ralph/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert "event_id" in events[0]
    assert "type" in events[0]
    assert "timestamp" in events[0]


async def test_ralph_list_events_with_limit(client):
    """limit 参数生效。"""
    resp = await client.get("/api/ralph/events?limit=3")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) <= 3


async def test_ralph_list_events_after_id(client, repo):
    """after_id 参数生效。"""
    repo.append_event(type="e1")
    repo.append_event(type="e2")
    repo.append_event(type="e3")

    resp_all = await client.get("/api/ralph/events")
    all_events = resp_all.json()

    if len(all_events) > 1:
        first_id = all_events[0]["event_id"]
        resp = await client.get(f"/api/ralph/events?after_id={first_id}")
        after_events = resp.json()
        ids = [e["event_id"] for e in after_events]
        assert first_id not in ids


# ==================== Settings API Tests ====================


async def test_ralph_list_providers_empty(client):
    """默认 Provider 列表为空。"""
    resp = await client.get("/api/ralph/settings/providers")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_ralph_create_provider(client):
    """创建 Provider。"""
    resp = await client.post(
        "/api/ralph/settings/providers",
        json={
            "id": "test-provider",
            "name": "Test Provider",
            "base_url": "https://api.test.com",
            "api_key": "sk-test",
            "default_model": "test-model",
            "models": ["test-model", "test-model-mini"],
            "enabled": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-provider"
    assert data["name"] == "Test Provider"
    assert "updated_at" in data


async def test_ralph_list_providers_after_create(client):
    """创建后列表包含该项目。"""
    await client.post(
        "/api/ralph/settings/providers",
        json={"id": "p1", "name": "P1", "base_url": "https://a.com"},
    )
    resp = await client.get("/api/ralph/settings/providers")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_ralph_update_provider(client):
    """更新 Provider。"""
    await client.post(
        "/api/ralph/settings/providers",
        json={"id": "update-me", "name": "Old", "base_url": "https://old.com"},
    )
    resp = await client.put(
        "/api/ralph/settings/providers/update-me",
        json={"name": "New", "base_url": "https://new.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New"
    assert data["base_url"] == "https://new.com"


async def test_ralph_delete_provider(client):
    """删除 Provider。"""
    await client.post(
        "/api/ralph/settings/providers",
        json={"id": "delete-me", "name": "Temp", "base_url": "https://temp.com"},
    )
    resp = await client.delete("/api/ralph/settings/providers/delete-me")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 确认已删除
    list_resp = await client.get("/api/ralph/settings/providers")
    ids = [p["id"] for p in list_resp.json()]
    assert "delete-me" not in ids


async def test_ralph_delete_provider_not_found(client):
    """删除不存在的 Provider 返回 404。"""
    resp = await client.delete("/api/ralph/settings/providers/nonexistent")
    assert resp.status_code == 404


async def test_ralph_test_provider(client):
    """测试 Provider 连通性。"""
    await client.post(
        "/api/ralph/settings/providers",
        json={"id": "conn-test", "name": "CT", "base_url": "https://api.test.com"},
    )
    resp = await client.post("/api/ralph/settings/providers/conn-test/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data


async def test_ralph_test_provider_not_found(client):
    """测试不存在的 Provider 返回错误。"""
    resp = await client.post("/api/ralph/settings/providers/nonexistent/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


# --- Model Assignments ---


async def test_ralph_list_assignments_empty(client):
    """默认路由规则为空。"""
    resp = await client.get("/api/ralph/settings/model-assignments")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_ralph_save_assignments(client):
    """保存模型路由规则。"""
    assignments = [
        {"task_type": "brainstorm", "provider_id": "claude", "model": "haiku"},
        {"task_type": "code_gen", "provider_id": "deepseek", "model": "v4"},
    ]
    resp = await client.put(
        "/api/ralph/settings/model-assignments",
        json=assignments,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 验证持久化
    get_resp = await client.get("/api/ralph/settings/model-assignments")
    assert len(get_resp.json()) == 2


# --- Toolchain ---


async def test_ralph_get_toolchain_default(client):
    """默认工具链配置。"""
    resp = await client.get("/api/ralph/settings/toolchain")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled_tools" in data
    assert "claude_code" in data["enabled_tools"]


async def test_ralph_save_toolchain(client):
    """保存工具链配置。"""
    config = {
        "enabled_tools": ["claude_code", "codex"],
        "priority": ["claude_code"],
        "fallback_strategy": "auto_switch",
    }
    resp = await client.put("/api/ralph/settings/toolchain", json=config)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled_tools"] == ["claude_code", "codex"]
    assert data["fallback_strategy"] == "auto_switch"


# --- Issue Policy ---


async def test_ralph_get_issue_policy_default(client):
    """默认 Issue 策略。"""
    resp = await client.get("/api/ralph/settings/issue-policy")
    assert resp.status_code == 200
    data = resp.json()
    assert "issue_sources" in data
    assert "local" in data["issue_sources"]


async def test_ralph_save_issue_policy(client):
    """保存 Issue 策略。"""
    policy = {
        "issue_sources": ["local", "github"],
        "classification_rules": {"bug": "auto_fix", "feature": "require_approval"},
        "pull_interval": "daily",
    }
    resp = await client.put("/api/ralph/settings/issue-policy", json=policy)
    assert resp.status_code == 200
    data = resp.json()
    assert data["classification_rules"]["bug"] == "auto_fix"
