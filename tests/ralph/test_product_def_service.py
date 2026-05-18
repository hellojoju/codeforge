"""ProductDefService 测试"""
import pytest
from unittest.mock import MagicMock

from ralph.product_def_service import ProductDefService, DIMENSIONS
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, FeatureNode, FeatureTree,
    ProactiveAnalysis, ProactiveAnalysisItem,
)


@pytest.fixture
def record():
    root = FeatureNode(
        node_id="fn-root",
        name="测试项目",
        level="product",
        status="exploring",
        vision="做一个在线协作工具",
        target_users=["开发者", "产品经理"],
        mvp_scope=["文档编辑", "实时同步"],
    )
    tree = FeatureTree(
        root_id="fn-root",
        nodes={"fn-root": root},
    )
    return BrainstormRecord(
        record_id="test-pd",
        project_name="测试项目",
        current_phase=BrainstormPhase.PRODUCT_DEF,
        feature_tree=tree,
        user_message="我想做一个类似 Google Docs 的在线协作工具",
    )


def test_dimensions_defined():
    """四个分析维度必须存在。"""
    assert len(DIMENSIONS) == 4
    roles = {d["role"] for d in DIMENSIONS}
    assert roles == {"product_vision", "user_experience", "technical_feasibility", "business_value"}


def test_run_analysis_llm_fallback(record):
    """LLM 不可用时，不抛异常，返回空结果。"""
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "", "model": "", "source": "none"}

    service = ProductDefService(mock_config)
    result = service.run_analysis(record)

    assert result.round_id.startswith("pd-")
    # LLM 不可用时 findings 为空
    assert result.findings == []


def test_run_analysis_with_proactive_context(record):
    """如果有已确认的主动分析，应包含在上下文中。"""
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-1",
        items=[
            ProactiveAnalysisItem(
                item_id="pa-1", category="product_type",
                content="在线协作文档 SaaS", confidence=0.8,
                status="accepted",
            ),
        ],
        summary="用户想做在线协作工具",
    )

    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "", "model": "", "source": "none"}

    service = ProductDefService(mock_config)
    result = service.run_analysis(record)

    assert result.round_id.startswith("pd-")


def test_confirm_finding(record):
    """确认分析结果。"""
    mock_config = MagicMock()
    service = ProductDefService(mock_config)

    # 手动添加一个 finding
    from ralph.schema.brainstorm_record import ProductDefRound, ProductDefFinding
    round = ProductDefRound(
        round_id="pd-test",
        findings=[
            ProductDefFinding(
                finding_id="pdf-test",
                dimension="product_vision",
                dimension_name="产品愿景",
                content="测试分析",
                suggestions=["建议1"],
                questions=["问题1"],
            )
        ],
    )
    record.product_def_rounds.append(round)

    service.confirm_finding(record, "pdf-test", "accept")
    assert round.findings[0].pm_decision == "accept"
    assert round.findings[0].status == "accepted"

    service.confirm_finding(record, "pdf-test", "reject", reason="不需要")
    assert round.findings[0].pm_decision == "reject"
    assert round.findings[0].status == "rejected"


def test_confirm_finding_invalid(record):
    """无效裁决应抛异常。"""
    mock_config = MagicMock()
    service = ProductDefService(mock_config)

    with pytest.raises(ValueError, match="Invalid decision"):
        service.confirm_finding(record, "fake-id", "invalid")


def test_confirm_finding_not_found(record):
    """不存在的 finding 应抛异常。"""
    mock_config = MagicMock()
    service = ProductDefService(mock_config)

    with pytest.raises(ValueError, match="Finding not found"):
        service.confirm_finding(record, "nonexistent", "accept")
