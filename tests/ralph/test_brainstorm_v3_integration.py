"""V3 API 集成测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def setup_v3_record():
    """辅助：设置一个包含 V3 数据的测试记录"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import (
        BrainstormPhase, BrainstormRecord, FeatureNode, FeatureTree,
        ProactiveAnalysis, ProactiveAnalysisItem, TechnicalRoute,
        DeliberationRound, DeliberationFinding,
    )

    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("集成测试项目", "做一个在线协作文档")
        yield mgr, record


def test_v3_schema_importable():
    """验证 V3 schema 可正常导入"""
    from ralph.schema.brainstorm_record import (
        ProactiveAnalysis, DeliberationFinding, TechnicalRoute,
        ToolDiscoveryResult, BrainstormPhase,
    )
    assert BrainstormPhase.PROACTIVE_ANALYSIS is not None
    assert TechnicalRoute is not None


def test_proactive_analysis_service_importable():
    """验证 ProactiveAnalysisService 可正常导入"""
    from ralph.proactive_service import ProactiveAnalysisService
    assert ProactiveAnalysisService is not None


def test_deliberation_service_importable():
    """验证 DeliberationReviewService 可正常导入"""
    from ralph.deliberation_service import DeliberationReviewService
    assert DeliberationReviewService is not None


def test_tool_discovery_importable():
    """验证 ToolDiscoveryService 可正常导入"""
    from ralph.tool_discovery import ToolDiscoveryService
    assert ToolDiscoveryService is not None


def test_technical_route_service_importable():
    """验证 TechnicalRouteService 可正常导入"""
    from ralph.technical_route_service import TechnicalRouteService
    assert TechnicalRouteService is not None


def test_v3_full_flow_schema(setup_v3_record):
    """V3 完整流程的 schema 层验证"""
    mgr, record = setup_v3_record
    from ralph.schema.brainstorm_record import BrainstormPhase

    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None

    # 模拟确认主动分析
    record.proactive_analysis.items[0].status = "accepted"


def test_deliberation_round_structure():
    """验证 DeliberationRound 数据结构"""
    from ralph.schema.brainstorm_record import DeliberationRound, DeliberationFinding

    rnd = DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少导航", severity="high",
                suggested_change="添加导航",
            )
        ],
        pm_summary="1 条高优先级发现",
    )
    assert len(rnd.findings) == 1
    assert rnd.findings[0].severity == "high"


def test_brainstorm_manager_has_v3_methods():
    """验证 BrainstormManager 具有 V3 公开方法"""
    from ralph.brainstorm_manager import BrainstormManager
    assert hasattr(BrainstormManager, "trigger_deliberation_review")
    assert hasattr(BrainstormManager, "generate_technical_route")
    assert hasattr(BrainstormManager, "confirm_technical_route")
    assert hasattr(BrainstormManager, "trigger_tool_discovery")
    assert hasattr(BrainstormManager, "_check_proactive_analysis_confirmed")
    assert hasattr(BrainstormManager, "_check_deliberation_resolved")


def test_routes_v3_endpoints_exist():
    """验证 routes.py 包含 V3 端点"""
    from pathlib import Path
    content = Path("dashboard/api/routes.py").read_text()
    assert "proactive-analysis" in content
    assert "proactive/confirm" in content
    assert "deliberation/decide" in content
    assert "deliberation/start" in content
    assert "deliberation/decision" in content
    assert "/api/ralph/specs/{spec_id}/technical-route" in content
    assert "/api/ralph/technical-routes/{route_id}/confirm" in content
    assert "technical-route/generate" in content
    assert "technical-route/confirm" in content
    assert "/api/ralph/technical-routes/{route_id}/tool-discovery" in content
    assert "tool-discovery/start" in content
    assert "tool-discovery" in content


def test_proactive_confirm_flow():
    """验证主动分析确认流程"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import (
        BrainstormPhase, ProactiveAnalysis, ProactiveAnalysisItem,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("确认测试", "描述")

        # 模拟确认一个条目
        record.proactive_analysis.items[0].status = "accepted"
        mgr._save(record)

        # 验证加载后状态正确
        loaded = mgr.load(record.record_id)
        assert loaded.proactive_analysis.items[0].status == "accepted"


def test_deliberation_decision_flow():
    """验证审查裁决流程"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import (
        DeliberationRound, DeliberationFinding,
    )
    from ralph.deliberation_service import DeliberationReviewService

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("裁决测试", "描述")

        # 添加 deliberation round
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

        # 做裁决
        service = DeliberationReviewService(mgr._config)
        service.make_decision(record, "f1", "accept", "接受这个建议")
        assert record.deliberation_rounds[-1].findings[0].pm_decision == "accept"


def test_technical_route_confirm_flow():
    """验证技术路线确认流程"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import (
        BrainstormPhase, TechnicalRoute,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("路线测试", "描述")

        # 设置技术路线
        record.technical_route = TechnicalRoute(
            route_id="tr-test", architecture_summary="前后端分离",
            status="pending",
        )

        # 确认接受
        mgr.confirm_technical_route(record, "accepted", "好的，就用这个")
        assert record.technical_route.status == "accepted"
        assert record.technical_route.user_feedback == "好的，就用这个"

        # 确认拒绝并要求修改
        mgr.confirm_technical_route(record, "revision_requested", "换成微服务")
        assert record.technical_route.status == "revision_requested"
        assert record.technical_route.user_feedback == "换成微服务"


def test_tool_discovery_requires_accepted_route():
    """验证工具发现需要已接受的技术路线"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import TechnicalRoute

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("工具测试", "描述")

        # 无技术路线时应返回空
        results = mgr.trigger_tool_discovery(record)
        assert results == []

        # 有技术路线但未接受时也应返回空
        record.technical_route = TechnicalRoute(
            route_id="tr-test", architecture_summary="SPA", status="pending",
        )
        results = mgr.trigger_tool_discovery(record)
        assert results == []
