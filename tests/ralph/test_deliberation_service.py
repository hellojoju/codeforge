"""DeliberationReviewService 测试"""
import pytest
from unittest.mock import MagicMock

from ralph.deliberation_service import DeliberationReviewService, DIMENSIONS
from ralph.schema.brainstorm_record import (
    BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree,
)


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": "[]"}}]}}
    yield DeliberationReviewService(config_manager=mock_config)


@pytest.fixture
def record_with_features():
    record = BrainstormRecord(record_id="bs-delib", project_name="协作系统")
    root = FeatureNode(node_id="fn-root", name="协作系统", level="product")
    fn1 = FeatureNode(
        node_id="fn-001", name="文档编辑", level="function", status="confirmed",
        user_stories=["作为用户可以编辑文档"],
        acceptance_criteria=["保存成功"],
        success_path=["打开文档", "编辑", "保存"],
        failure_path=["网络断开"],
        edge_cases=["同时编辑"],
    )
    fn2 = FeatureNode(
        node_id="fn-002", name="评论功能", level="function", status="confirmed",
        user_stories=["作为用户可以添加评论"],
        acceptance_criteria=["评论显示在文档侧边"],
        success_path=["选中内容", "添加评论"],
        failure_path=["评论失败提示重试"],
        edge_cases=["评论超长"],
    )
    record.feature_tree = FeatureTree(
        root_id="fn-root",
        nodes={"fn-root": root, "fn-001": fn1, "fn-002": fn2},
        current_exploring_id="fn-001",
    )
    return record


def test_dimensions_defined():
    """验证四个审查维度已定义"""
    assert len(DIMENSIONS) == 4
    roles = [d["role"] for d in DIMENSIONS]
    assert "user_journey_analyst" in roles
    assert "feature_completeness_reviewer" in roles
    assert "industry_benchmark_analyst" in roles
    assert "scenario_combiner" in roles


def test_run_review_returns_round(service, record_with_features):
    """测试审查执行返回结果"""
    rnd = service.run_review(record_with_features)
    assert rnd.round_id.startswith("dr-")
    assert rnd.created_at != ""
    assert len(record_with_features.deliberation_rounds) == 1
    assert record_with_features.deliberation_rounds[0] is rnd


def test_review_no_config():
    """测试无 config 时 graceful 降级"""
    svc = DeliberationReviewService(config_manager=None)
    record = BrainstormRecord(record_id="bs-noconfig", project_name="Test")
    root = FeatureNode(node_id="fn-root", name="Test", level="product")
    record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root})
    rnd = svc.run_review(record)
    assert rnd is not None
    assert rnd.findings == []


def test_apply_pm_decisions_updates_nodes(service, record_with_features):
    """测试 PM 裁决回写功能树"""
    rnd = DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少撤销功能", severity="high",
                suggested_change="添加撤销/重做功能",
            )
        ],
        pm_summary="测试",
    )
    record_with_features.deliberation_rounds.append(rnd)
    rnd.findings[0].pm_decision = "accept"

    service.apply_pm_decisions(record_with_features)
    node = record_with_features.feature_tree.get_node("fn-001")
    assert any("撤销" in fb for fb in node.review_feedback)


def test_make_decision(service, record_with_features):
    """测试对审查发现做裁决"""
    rnd = DeliberationRound(
        round_id="dr-decision",
        findings=[
            DeliberationFinding(
                finding_id="f-dec", dimension="feature_completeness_reviewer",
                affected_feature_ids=["fn-001"],
                finding="缺少搜索", severity="medium",
                suggested_change="添加全文搜索",
            )
        ],
    )
    record_with_features.deliberation_rounds.append(rnd)

    service.make_decision(record_with_features, "f-dec", "reject", "MVP 不做搜索")
    assert rnd.findings[0].pm_decision == "reject"
    assert rnd.findings[0].pm_reason == "MVP 不做搜索"


def test_summarize_findings(service):
    """测试审查发现摘要生成"""
    findings = [
        DeliberationFinding(finding_id="1", dimension="a", affected_feature_ids=[], finding="问题A", severity="high", suggested_change=""),
        DeliberationFinding(finding_id="2", dimension="a", affected_feature_ids=[], finding="问题B", severity="medium", suggested_change=""),
    ]
    summary = service._summarize_findings(findings)
    assert "高优先级" in summary
    assert "问题A" in summary


def test_summarize_findings_no_issues(service):
    """测试无问题时的摘要"""
    summary = service._summarize_findings([])
    assert "未发现重大问题" in summary


def test_render_feature_tree(service, record_with_features):
    """测试功能树渲染"""
    spec = service._render_feature_tree(record_with_features)
    assert "协作系统" in spec
    assert "文档编辑" in spec
    assert "评论功能" in spec


def test_apply_pm_decisions_no_rounds(service, record_with_features):
    """测试无审查轮次时的安全降级"""
    service.apply_pm_decisions(record_with_features)
    # 不应报错


def test_make_decision_not_found(service, record_with_features):
    """测试裁决不存在的 finding"""
    with pytest.raises(ValueError):
        service.make_decision(record_with_features, "nonexistent", "accept", "")
