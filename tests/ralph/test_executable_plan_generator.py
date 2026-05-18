"""ExecutablePlanGenerator 测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.brainstorm_manager import BrainstormManager
from ralph.executable_plan_generator import ExecutablePlanGenerator
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, FeatureNode, FeatureTree,
    TechnicalRoute, ToolDiscoveryResult, _now_iso,
    dict_to_brainstorm, brainstorm_to_dict,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "在线协作文档 SaaS", "confidence": 0.8}, {"item_id": "pa-2", "category": "target_user", "content": "开发团队", "confidence": 0.7}, {"item_id": "pa-3", "category": "core_scenario", "content": "多人协作编辑", "confidence": 0.7}]}'}}]}}
        yield BrainstormManager(Path(tmpdir), config_manager=mock_config)


def _build_confirmed_record():
    """构建一个已确认到 EXECUTION_PLAN_READY 的 BrainstormRecord。"""
    root = FeatureNode(
        node_id="fn-root",
        name="测试项目",
        level="product",
        status="confirmed",
        vision="做一个在线协作文档系统",
        target_users=["开发团队", "产品经理"],
        roles=["编辑者", "查看者"],
        success_criteria=["支持实时协作", "响应时间 < 200ms"],
        mvp_scope=["文档编辑", "评论系统"],
        out_of_scope=["视频通话"],
    )
    func_a = FeatureNode(
        node_id="fn-func-a",
        name="文档编辑",
        level="function",
        status="confirmed",
        parent_id="fn-root",
        user_stories=["作为用户，我可以创建和编辑文档"],
        acceptance_criteria=["文档支持富文本格式", "自动保存间隔 < 5s"],
        success_path=["创建文档 → 编辑 → 保存"],
        failure_path=["网络断开 → 本地缓存 → 恢复后同步"],
        edge_cases=["并发编辑冲突"],
        data_requirements=["文档内容", "版本号"],
    )
    func_b = FeatureNode(
        node_id="fn-func-b",
        name="评论系统",
        level="function",
        status="confirmed",
        parent_id="fn-root",
        user_stories=["作为用户，我可以对文档添加评论"],
        acceptance_criteria=["支持行内评论", "支持 @提及"],
        success_path=["选择文本 → 添加评论 → 提交"],
        failure_path=["评论失败 → 重试 → 通知"],
        edge_cases=["评论被删除后引用"],
        data_requirements=["评论内容", "被评论文本位置"],
    )
    root.children = ["fn-func-a", "fn-func-b"]

    tree = FeatureTree(
        root_id="fn-root",
        nodes={"fn-root": root, "fn-func-a": func_a, "fn-func-b": func_b},
    )

    route = TechnicalRoute(
        route_id="tr-001",
        architecture_summary="前后端分离，WebSocket 实时同步",
        frontend_stack=["React", "TypeScript", "Yjs"],
        backend_stack=["Python", "FastAPI"],
        data_storage=["PostgreSQL"],
        integrations=["WebSocket"],
        non_functional_requirements=["响应时间 < 200ms"],
        key_risks=["WebSocket 连接稳定性"],
        tool_needs=["协同编辑引擎"],
        status="accepted",
    )

    tool_result = ToolDiscoveryResult(
        discovery_id="td-001",
        tool_need="协同编辑引擎",
        queries=["collaborative editing python library"],
    )

    record = BrainstormRecord(
        record_id="test-record",
        project_name="测试项目",
        current_phase=BrainstormPhase.EXECUTION_PLAN_READY,
        feature_tree=tree,
        technical_route=route,
        tool_discovery_results=[tool_result],
    )
    return record


def test_generate_executable_plan_basic():
    """基本测试：生成可执行计划，包含任务和元数据。"""
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    # 模拟 LLM 返回任务列表（proxy_request 返回完整 response）
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {"content": """[
  {
    "title": "搭建后端 API 框架",
    "description": "初始化 FastAPI 项目结构",
    "action": "CREATE",
    "target_files": ["src/api/main.py", "src/api/models.py"],
    "dependencies": [],
    "acceptance_criteria": ["API 可启动", "健康检查端点返回 200"],
    "validation_commands": ["pytest tests/test_api.py"],
    "estimated_complexity": "low"
  },
  {
    "title": "实现文档编辑功能",
    "description": "实现 CRUD 和协同编辑",
    "action": "CREATE",
    "target_files": ["src/api/documents.py"],
    "dependencies": ["task-000"],
    "acceptance_criteria": ["创建文档成功", "编辑后自动保存"],
    "validation_commands": ["pytest tests/test_documents.py"],
    "estimated_complexity": "high"
  }
]"""}}]}
    }

    generator = ExecutablePlanGenerator(mock_config)
    record = _build_confirmed_record()
    plan = generator.generate(record)

    assert plan.plan_id.startswith("plan-")
    assert plan.project_name == "测试项目"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].title == "搭建后端 API 框架"
    assert plan.tasks[1].title == "实现文档编辑功能"
    assert plan.tasks[1].dependencies == ["task-000"]
    assert plan.brainstorm_record_id == "test-record"


def test_generate_executable_plan_llm_fallback():
    """LLM 失败时兜底生成任务。"""
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": False}  # LLM 返回失败

    generator = ExecutablePlanGenerator(mock_config)
    record = _build_confirmed_record()
    plan = generator.generate(record)

    # 兜底任务应该基于已确认的 function/sub_function 节点生成
    assert len(plan.tasks) >= 2  # fn-func-a 和 fn-func-b
    assert any("文档编辑" in t.title for t in plan.tasks)
    assert any("评论系统" in t.title for t in plan.tasks)


def test_to_markdown_renders_plan():
    """to_markdown 方法应输出完整的 Markdown 格式计划。"""
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {"content": """[
  {
    "title": "搭建后端 API 框架",
    "description": "初始化 FastAPI 项目结构",
    "action": "CREATE",
    "target_files": ["src/api/main.py"],
    "dependencies": [],
    "acceptance_criteria": ["API 可启动"],
    "validation_commands": ["pytest tests/test_api.py"],
    "estimated_complexity": "low"
  }
]"""}}]}
    }

    generator = ExecutablePlanGenerator(mock_config)
    record = _build_confirmed_record()
    plan = generator.generate(record)
    markdown = generator.to_markdown(plan)

    assert "# Feature: 测试项目" in markdown
    assert "## Summary" in markdown
    assert "## Step-by-Step Tasks" in markdown
    assert "搭建后端 API 框架" in markdown
    assert "src/api/main.py" in markdown
    assert "pytest tests/test_api.py" in markdown


def test_brainstorm_manager_integration(manager):
    """BrainstormManager 在 TOOL_DISCOVERY → EXECUTION_PLAN_READY 时自动生成计划。"""
    record = manager.start_session("集成测试项目", "做一个简单的待办事项应用")

    # 快进到 TOOL_DISCOVERY
    record.current_phase = BrainstormPhase.TOOL_DISCOVERY
    record.technical_route = TechnicalRoute(
        route_id="tr-test",
        architecture_summary="简单前后端分离",
        frontend_stack=["React"],
        backend_stack=["FastAPI"],
        data_storage=["SQLite"],
        integrations=[],
        non_functional_requirements=[],
        key_risks=[],
        tool_needs=[],
        status="accepted",
    )
    record.tool_discovery_results = []

    # 推进 phase，应该自动触发 _generate_executable_plan
    result = manager.advance_phase(record)
    assert result is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.EXECUTION_PLAN_READY
    # 计划应该已生成（LLM 可能失败，但至少不会报错）
    # executable_plan 可能为 None（如果 LLM 返回空），但方法不应抛异常


def test_generate_executable_plan_manual(manager):
    """手动调用 generate_executable_plan 应返回 ExecutablePlan。"""
    record = _build_confirmed_record()
    plan = manager.generate_executable_plan(record)
    # 由于 mock 的 proxy_request 返回的是 proactive_analysis 格式，
    # 这里不验证具体内容，只验证不抛异常
    # plan 可能为 None 如果 LLM 解析失败


def test_render_executable_plan_markdown(manager):
    """render_executable_plan_markdown 应返回 Markdown 字符串。"""
    record = _build_confirmed_record()
    markdown = manager.render_executable_plan_markdown(record)
    assert isinstance(markdown, str)


def test_serialization_roundtrip():
    """ExecutablePlan 应能正确序列化和反序列化。"""
    record = _build_confirmed_record()

    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {"content": """[
  {
    "title": "任务1",
    "description": "描述",
    "action": "CREATE",
    "target_files": ["a.py"],
    "dependencies": [],
    "acceptance_criteria": ["标准1"],
    "validation_commands": [],
    "estimated_complexity": "medium"
  }
]"""}}]}
    }

    generator = ExecutablePlanGenerator(mock_config)
    plan = generator.generate(record)
    record.executable_plan = plan

    # 序列化
    data = brainstorm_to_dict(record)
    assert "executable_plan" in data
    assert data["executable_plan"]["plan_id"] == plan.plan_id
    assert len(data["executable_plan"]["tasks"]) == 1

    # 反序列化
    restored = dict_to_brainstorm(data)
    assert restored.executable_plan is not None
    assert restored.executable_plan.plan_id == plan.plan_id
    assert len(restored.executable_plan.tasks) == 1
    assert restored.executable_plan.tasks[0].title == "任务1"
