"""V3 端到端流程测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree, ProactiveAnalysis,
    ProactiveAnalysisItem, TechnicalRoute, _now_iso,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "在线协作文档 SaaS", "confidence": 0.8}, {"item_id": "pa-2", "category": "target_user", "content": "开发团队", "confidence": 0.7}, {"item_id": "pa-3", "category": "core_scenario", "content": "多人协作编辑", "confidence": 0.7}]}'}}]}}
        yield BrainstormManager(Path(tmpdir), config_manager=mock_config)


def test_e2e_v3_proactive_to_product_def(manager):
    """V3: PROACTIVE_ANALYSIS → 确认条目 → PRODUCT_DEF"""
    record = manager.start_session("E2E项目", "我想做一个在线协作文档系统")
    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None

    # 模拟用户确认核心条目
    for item in record.proactive_analysis.items:
        if item.category in ("product_type", "target_user", "core_scenario"):
            item.status = "accepted"

    # 推进到 PRODUCT_DEF
    result = manager.advance_phase(record)
    assert result is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.PRODUCT_DEF


def test_e2e_v3_deliberation_gate(manager):
    """V3: DELIBERATION_REVIEW 需要 high findings 被处理才能推进"""
    record = manager.start_session("Gate项目", "描述")
    # 快进到 DELIBERATION_REVIEW
    record.current_phase = BrainstormPhase.DELIBERATION_REVIEW

    # 添加一个未裁决的 high finding
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-gate",
        findings=[
            DeliberationFinding(
                finding_id="f-high", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少退出路径", severity="high",
                suggested_change="添加退出按钮",
                pm_decision="pending",
            )
        ],
    ))

    # 不应推进
    assert manager.advance_phase(record) is False

    # 裁决后应推进
    record.deliberation_rounds[-1].findings[0].pm_decision = "accept"
    assert manager.advance_phase(record) is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.RELATIONSHIP


def test_e2e_v3_technical_route_to_tool_discovery(manager):
    """V3: TECHNICAL_ROUTE_DRAFT → 确认 → TOOL_DISCOVERY"""
    record = manager.start_session("Route项目", "描述")

    # 直接设置技术路线
    record.technical_route = TechnicalRoute(
        route_id="tr-e2e",
        architecture_summary="SPA + REST",
        frontend_stack=["React"],
        backend_stack=["FastAPI"],
        tool_needs=["Web 框架"],
        status="accepted",
        confirmed_at=_now_iso(),
    )
    record.current_phase = BrainstormPhase.TECHNICAL_ROUTE_DRAFT

    # 推进到 TOOL_DISCOVERY
    assert manager.advance_phase(record) is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.TOOL_DISCOVERY


def test_e2e_v3_trigger_deliberation_review(manager):
    """V3: 触发 deliberation review 并检查结果"""
    record = manager.start_session("Delib项目", "描述")
    # 添加一个已确认的功能节点
    fn = FeatureNode(
        node_id="fn-001", name="用户登录", level="function", status="confirmed",
        user_stories=["作为用户可以登录系统"],
        acceptance_criteria=["用户名密码正确则登录成功"],
        success_path=["输入用户名密码", "点击登录"],
        failure_path=["密码错误提示"],
        edge_cases=["连续错误锁定"],
    )
    record.feature_tree.nodes["fn-001"] = fn

    # 触发审查
    rnd = manager.trigger_deliberation_review(record)
    assert rnd is not None
    assert len(record.deliberation_rounds) == 1


def test_e2e_v3_execution_plan_ready(manager):
    """V3: TOOL_DISCOVERY → EXECUTION_PLAN_READY → COMPLETE"""
    record = manager.start_session("Exec项目", "描述")
    record.current_phase = BrainstormPhase.TOOL_DISCOVERY

    assert manager.advance_phase(record) is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.EXECUTION_PLAN_READY

    assert manager.advance_phase(record) is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.COMPLETE
    assert record.completed_at != ""


def test_e2e_v3_requirements_ready(manager):
    """V3: REQUIREMENTS_READY → COMPLETE"""
    record = manager.start_session("Req项目", "描述")
    record.current_phase = BrainstormPhase.REQUIREMENTS_READY

    assert manager.advance_phase(record) is True
    manager.confirm_phase(record)
    assert record.current_phase == BrainstormPhase.COMPLETE


def test_e2e_v3_technical_route_not_accepted_blocks(manager):
    """V3: 技术路线未确认时不能推进"""
    record = manager.start_session("Block项目", "描述")
    record.technical_route = TechnicalRoute(
        route_id="tr-block", architecture_summary="SPA",
        status="pending",
    )
    record.current_phase = BrainstormPhase.TECHNICAL_ROUTE_DRAFT

    result = manager.advance_phase(record)
    assert result is False
    assert record.current_phase == BrainstormPhase.TECHNICAL_ROUTE_DRAFT
