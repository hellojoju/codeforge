"""BrainstormManager V3 phase 路由测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree, ProactiveAnalysis, ProactiveAnalysisItem,
    TechnicalRoute, ToolEvaluation,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BrainstormManager(Path(tmpdir))


@pytest.fixture
def manager_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS 产品", "confidence": 0.8}]}'}}]}}
        yield BrainstormManager(Path(tmpdir), config_manager=mock_config)


def test_v3_start_session_starts_at_proactive_analysis(manager_with_config):
    """V3: start_session 应从 PROACTIVE_ANALYSIS 开始"""
    record = manager_with_config.start_session("测试项目", "我想做一个在线文档系统")
    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None
    assert len(record.proactive_analysis.items) >= 1


def test_check_proactive_analysis_confirmed(manager):
    """验证 _check_proactive_analysis_confirmed 逻辑"""
    record = manager.start_session("P", "描述")
    # 无 config 时 proactive_analysis 为空 → 跳过此阶段
    assert manager._check_proactive_analysis_confirmed(record) is True

    # 只有 product_type 存在且已确认 → 缺少类别视为不需要确认 → 通过
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-test",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="SaaS 产品", confidence=0.8, status="accepted",
            )
        ],
    )
    assert manager._check_proactive_analysis_confirmed(record) is True

    # 三个类别都存在，但只确认了两个 → 不能推进
    record.proactive_analysis.items.append(ProactiveAnalysisItem(
        item_id="i2", category="target_user",
        content="团队用户", confidence=0.8, status="accepted",
    ))
    record.proactive_analysis.items.append(ProactiveAnalysisItem(
        item_id="i3", category="core_scenario",
        content="多人协作编辑", confidence=0.8, status="pending",
    ))
    assert manager._check_proactive_analysis_confirmed(record) is False

    # 三个类别全部确认 → 通过
    record.proactive_analysis.items[-1].status = "modified"
    assert manager._check_proactive_analysis_confirmed(record) is True


def test_check_deliberation_resolved(manager):
    """验证 _check_deliberation_resolved 逻辑"""
    record = manager.start_session("P", "描述")
    assert manager._check_deliberation_resolved(record) is False

    # 添加一个 high severity 但未裁决的 finding
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少功能", severity="high",
                suggested_change="添加",
                pm_decision="pending",
            )
        ],
    ))
    assert manager._check_deliberation_resolved(record) is False

    # 裁决后应为 True
    record.deliberation_rounds[-1].findings[0].pm_decision = "accept"
    assert manager._check_deliberation_resolved(record) is True


def test_process_response_v2_proactive_phase(manager):
    """测试 process_response_v2 在 PROACTIVE_ANALYSIS phase 的路由"""
    record = manager.start_session("P", "描述")
    record.current_phase = BrainstormPhase.PROACTIVE_ANALYSIS
    # 不应该报错
    manager.process_response_v2(record, "看起来差不多，继续吧")
    root = record.feature_tree.get_node("fn-root")
    assert len(root.conversation_turns) >= 1


def test_process_response_v2_deliberation_phase(manager):
    """测试 process_response_v2 在 DELIBERATION_REVIEW phase 的路由"""
    record = manager.start_session("P", "描述")
    record.current_phase = BrainstormPhase.DELIBERATION_REVIEW
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-test", findings=[], pm_summary="初始摘要",
    ))
    manager.process_response_v2(record, "接受所有建议")
    assert "用户反馈" in record.deliberation_rounds[-1].pm_summary


def test_confirm_technical_route(manager):
    """测试技术路线确认"""
    record = manager.start_session("P", "描述")
    record.technical_route = TechnicalRoute(
        route_id="tr-test", architecture_summary="前后端分离",
    )
    manager.confirm_technical_route(record, "accepted", "好的")
    assert record.technical_route.status == "accepted"
    assert record.technical_route.user_feedback == "好的"
    assert record.technical_route.confirmed_at != ""


def test_confirm_technical_route_revision(manager):
    """测试技术路线要求修改"""
    record = manager.start_session("P", "描述")
    record.technical_route = TechnicalRoute(
        route_id="tr-test", architecture_summary="前后端分离",
    )
    manager.confirm_technical_route(record, "revision_requested", "需要改成微服务")
    assert record.technical_route.status == "revision_requested"
    assert record.technical_route.user_feedback == "需要改成微服务"
    assert len(record.technical_route_history) == 1
    assert record.technical_route_history[0].architecture_summary == "前后端分离"


def test_update_proactive_analysis_item_writes_formal_context(manager):
    """主动分析确认后应进入正式需求上下文。"""
    record = manager.start_session("P", "描述")
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-test",
        items=[
            ProactiveAnalysisItem("i1", "product_type", "知识库", 0.8),
            ProactiveAnalysisItem("i2", "target_user", "研发团队", 0.8),
            ProactiveAnalysisItem("i3", "core_scenario", "沉淀项目知识", 0.8),
        ],
    )

    manager.update_proactive_analysis_item(record, "i1", "accepted")
    manager.update_proactive_analysis_item(record, "i2", "accepted")
    manager.update_proactive_analysis_item(record, "i3", "modified", "检索项目知识")

    root = record.feature_tree.get_node("fn-root")
    assert any(f.topic == "产品类型" and f.fact == "知识库" for f in record.confirmed_facts)
    assert "研发团队" in root.target_users
    assert "检索项目知识" in root.success_criteria
    assert record.proactive_analysis.confirmed_at


def test_trigger_tool_discovery_no_route(manager):
    """测试无技术路线时工具发现返回空"""
    record = manager.start_session("P", "描述")
    results = manager.trigger_tool_discovery(record)
    assert results == []


def test_trigger_tool_discovery_with_config():
    """测试带 config 的工具发现"""
    from unittest.mock import patch
    from ralph.schema.brainstorm_record import ToolCandidate, ToolEvaluation, ToolDiscoveryResult
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("P", "描述")
        record.technical_route = TechnicalRoute(
            route_id="tr-test", architecture_summary="SPA + REST",
            tool_needs=["Web 框架"], status="accepted",
        )

        # Patch the ToolDiscoveryService.discover method to avoid LLM calls
        with patch("ralph.tool_discovery.ToolDiscoveryService.discover", return_value=[
            ToolDiscoveryResult(
                discovery_id="td-1", tool_need="Web 框架",
                queries=["fastapi github"],
                candidates=[
                    ToolCandidate(candidate_id="tc-1", name="FastAPI", source="github", url="https://example.com", description="Test"),
                ],
                evaluations=[
                    ToolEvaluation(candidate_id="tc-1", functional_fit=5, maintenance_health=5, license_fit=5, stack_compatibility=5, security_risk="low", integration_cost="low", summary="好", recommendation="adopt"),
                ],
                selected_candidate_ids=["tc-1"],
            ),
        ]):
            results = mgr.trigger_tool_discovery(record)
            assert len(results) == 1
            assert results[0].tool_need == "Web 框架"


def test_start_session_without_config():
    """测试无 config 时 start_session 创建空 proactive_analysis"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = BrainstormManager(Path(tmpdir))
        record = mgr.start_session("P", "描述")
        assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
        # 无 config 时 analysis 创建但 items 为空
        assert record.proactive_analysis is not None
        assert record.proactive_analysis.items == []


def test_process_proactive_response_auto_confirms_questions():
    """用户回复时自动确认 question 类型条目"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = BrainstormManager(Path(tmpdir))
        record = mgr.start_session("P", "描述")
        record.proactive_analysis = ProactiveAnalysis(
            analysis_id="pa-test",
            items=[
                ProactiveAnalysisItem(
                    item_id="q1", category="question",
                    content="目标平台是什么？", confidence=0.8, status="pending",
                ),
                ProactiveAnalysisItem(
                    item_id="p1", category="product_type",
                    content="SaaS 工具", confidence=0.7, status="pending",
                ),
            ],
        )

        mgr._process_proactive_response(record, "主要是 Web 端，给小企业用")

        # question 类型自动确认，user_revision 为用户回答
        q1 = record.proactive_analysis.items[0]
        assert q1.status == "accepted"
        assert "Web 端" in q1.user_revision

        # 核心类别也自动确认
        p1 = record.proactive_analysis.items[1]
        assert p1.status == "accepted"


def test_process_proactive_response_advances_phase():
    """用户回复后 phase 能从 PROACTIVE_ANALYSIS 推进到 PRODUCT_DEF"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = BrainstormManager(Path(tmpdir))
        record = mgr.start_session("P", "描述")
        # 模拟 LLM 生成的完整分析
        record.proactive_analysis = ProactiveAnalysis(
            analysis_id="pa-test",
            items=[
                ProactiveAnalysisItem(
                    item_id="pt1", category="product_type",
                    content="SaaS 工具", confidence=0.7, status="pending",
                ),
                ProactiveAnalysisItem(
                    item_id="tu1", category="target_user",
                    content="小企业", confidence=0.6, status="pending",
                ),
                ProactiveAnalysisItem(
                    item_id="cs1", category="core_scenario",
                    content="团队协作", confidence=0.7, status="pending",
                ),
                ProactiveAnalysisItem(
                    item_id="q1", category="question",
                    content="目标平台？", confidence=0.5, status="pending",
                ),
            ],
        )

        mgr._process_proactive_response(record, "Web 端为主")
        mgr.advance_phase(record)

        assert record.current_phase == BrainstormPhase.PRODUCT_DEF
        # 核心类别已被自动确认
        confirmed = {i.category for i in record.proactive_analysis.items if i.status == "accepted"}
        assert "product_type" in confirmed
        assert "target_user" in confirmed
        assert "core_scenario" in confirmed
