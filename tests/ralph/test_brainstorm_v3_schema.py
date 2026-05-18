"""V3 Schema 数据结构、默认值与序列化往返测试"""
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    EvidenceRef, FeatureNode, FeatureTree, ProactiveAnalysis, ProactiveAnalysisItem,
    SourceRef, TechnicalRoute, ToolCandidate, ToolDiscoveryResult, ToolEvaluation,
    brainstorm_to_dict, dict_to_brainstorm,
)


# ── 枚举测试 ──

def test_brainstorm_phase_v3_values():
    """验证 V3 新增 phase 枚举值"""
    assert BrainstormPhase.PROACTIVE_ANALYSIS == "proactive_analysis"
    assert BrainstormPhase.DELIBERATION_REVIEW == "deliberation_review"
    assert BrainstormPhase.TECHNICAL_ROUTE_DRAFT == "technical_route_draft"
    assert BrainstormPhase.TOOL_DISCOVERY == "tool_discovery"
    assert BrainstormPhase.REQUIREMENTS_READY == "requirements_ready"
    assert BrainstormPhase.EXECUTION_PLAN_READY == "execution_plan_ready"


# ── 默认值测试 ──

def test_proactive_analysis_item_defaults():
    item = ProactiveAnalysisItem(
        item_id="pa-1", category="product_type",
        content="这是一个 SaaS 产品", confidence=0.7,
    )
    assert item.status == "pending"
    assert item.user_revision == ""
    assert item.source_refs == []


def test_proactive_analysis_defaults():
    analysis = ProactiveAnalysis(analysis_id="pa-root")
    assert analysis.items == []
    assert analysis.summary == ""
    assert analysis.confirmed_at == ""


def test_deliberation_finding_defaults():
    finding = DeliberationFinding(
        finding_id="df-1", dimension="user_journey",
        affected_feature_ids=["fn-001"],
        finding="缺少退出按钮", severity="high",
        suggested_change="在导航栏添加退出按钮",
    )
    assert finding.evidence == ""
    assert finding.pm_decision == "pending"
    assert finding.pm_reason == ""


def test_deliberation_round_defaults():
    rnd = DeliberationRound(round_id="dr-1")
    assert rnd.findings == []
    assert rnd.pm_summary == ""


def test_technical_route_defaults():
    route = TechnicalRoute(
        route_id="tr-1", architecture_summary="前后端分离",
    )
    assert route.status == "pending"
    assert route.frontend_stack == []
    assert route.tool_needs == []
    assert route.user_feedback == ""


def test_tool_candidate_defaults():
    candidate = ToolCandidate(
        candidate_id="tc-1", name="Express",
        source="github", url="https://github.com/expressjs/express",
        description="Fast web framework",
    )
    assert candidate.stars is None
    assert candidate.evidence_urls == []
    assert candidate.evidence_refs == []


def test_evidence_ref_defaults():
    ref = EvidenceRef(source_type="github", title="FastAPI", url="https://github.com/fastapi/fastapi")
    assert ref.quote_or_summary == ""
    assert ref.confidence == 1.0


def test_tool_evaluation_defaults():
    ev = ToolEvaluation(
        candidate_id="tc-1", functional_fit=5, maintenance_health=4,
        license_fit=5, stack_compatibility=5,
        security_risk="low", integration_cost="low",
        summary="成熟稳定", recommendation="adopt",
    )
    assert ev.recommendation == "adopt"


def test_tool_discovery_result_defaults():
    result = ToolDiscoveryResult(
        discovery_id="td-1", tool_need="Web 框架",
    )
    assert result.candidates == []
    assert result.selected_candidate_ids == []


def test_brainstorm_record_v3_fields():
    """验证 BrainstormRecord 包含 V3 新字段"""
    record = BrainstormRecord(record_id="bs-v3", project_name="Test")
    assert record.proactive_analysis is None
    assert record.deliberation_rounds == []
    assert record.technical_route is None
    assert record.tool_discovery_results == []


# ── 序列化往返测试 ──

def test_proactive_analysis_roundtrip():
    record = BrainstormRecord(record_id="bs-rt", project_name="RT")
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-1",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="SaaS 产品", confidence=0.8,
            )
        ],
        summary="分析摘要",
    )
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.proactive_analysis is not None
    assert restored.proactive_analysis.analysis_id == "pa-1"
    assert len(restored.proactive_analysis.items) == 1
    assert restored.proactive_analysis.items[0].content == "SaaS 产品"


def test_proactive_analysis_with_source_refs_roundtrip():
    record = BrainstormRecord(record_id="bs-rt-sr", project_name="RT")
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-sr",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="SaaS 产品", confidence=0.8,
                source_refs=[SourceRef(turn_id="t1", quote="原话", field_name="category")],
            )
        ],
    )
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.proactive_analysis.items[0].source_refs) == 1
    assert restored.proactive_analysis.items[0].source_refs[0].turn_id == "t1"


def test_deliberation_rounds_roundtrip():
    record = BrainstormRecord(record_id="bs-rt2", project_name="RT2")
    record.deliberation_rounds = [
        DeliberationRound(
            round_id="dr-1",
            findings=[
                DeliberationFinding(
                    finding_id="f1", dimension="user_journey",
                    affected_feature_ids=["fn-001"],
                    finding="缺少退出", severity="high",
                    suggested_change="添加退出",
                )
            ],
            pm_summary="采纳",
        )
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.deliberation_rounds) == 1
    assert restored.deliberation_rounds[0].findings[0].finding == "缺少退出"


def test_technical_route_roundtrip():
    record = BrainstormRecord(record_id="bs-rt3", project_name="RT3")
    record.technical_route = TechnicalRoute(
        route_id="tr-1", architecture_summary="SPA + REST API",
        frontend_stack=["React", "TypeScript"],
        backend_stack=["Node.js", "FastAPI"],
        tool_needs=["Web 框架", "ORM"],
    )
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.technical_route is not None
    assert restored.technical_route.frontend_stack == ["React", "TypeScript"]
    assert restored.technical_route.tool_needs == ["Web 框架", "ORM"]


def test_tool_discovery_roundtrip():
    record = BrainstormRecord(record_id="bs-rt4", project_name="RT4")
    record.tool_discovery_results = [
        ToolDiscoveryResult(
            discovery_id="td-1", tool_need="Web 框架",
            queries=["best python web framework 2026"],
            candidates=[
                ToolCandidate(
                    candidate_id="tc-1", name="FastAPI",
                    source="github", url="https://github.com/tiangolo/fastapi",
                    description="Modern fast web framework",
                    stars=70000,
                )
            ],
            evaluations=[
                ToolEvaluation(
                    candidate_id="tc-1", functional_fit=5,
                    maintenance_health=5, license_fit=5, stack_compatibility=5,
                    security_risk="low", integration_cost="low",
                    summary="推荐", recommendation="adopt",
                )
            ],
            selected_candidate_ids=["tc-1"],
        )
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.tool_discovery_results) == 1
    td = restored.tool_discovery_results[0]
    assert td.candidates[0].name == "FastAPI"
    assert td.selected_candidate_ids == ["tc-1"]


def test_full_v3_record_roundtrip():
    """包含所有 V3 字段的完整往返测试"""
    record = BrainstormRecord(record_id="bs-full", project_name="FullV3")
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-full",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="协作工具", confidence=0.9, status="accepted",
            ),
        ],
        summary="完整摘要",
    )
    record.deliberation_rounds = [
        DeliberationRound(
            round_id="dr-full",
            findings=[
                DeliberationFinding(
                    finding_id="f1", dimension="user_journey_analyst",
                    affected_feature_ids=["fn-001"],
                    finding="缺少撤销", severity="high",
                    suggested_change="添加撤销",
                    pm_decision="accept", pm_reason="必要功能",
                ),
            ],
            pm_summary="1条高优先级",
        ),
    ]
    record.technical_route = TechnicalRoute(
        route_id="tr-full", architecture_summary="微服务",
        frontend_stack=["React"], backend_stack=["Go"],
        tool_needs=["消息队列"], status="accepted",
    )
    record.tool_discovery_results = [
        ToolDiscoveryResult(
            discovery_id="td-full", tool_need="消息队列",
            queries=["redis pubsub"],
            candidates=[
                ToolCandidate(
                    candidate_id="tc-full", name="Redis",
                    source="github", url="https://github.com/redis/redis",
                    description="In-memory datastore", license="BSD", stars=65000,
                    evidence_refs=[
                        EvidenceRef(
                            source_type="github",
                            title="Redis",
                            url="https://github.com/redis/redis",
                            quote_or_summary="In-memory datastore",
                        )
                    ],
                ),
            ],
            evaluations=[
                ToolEvaluation(
                    candidate_id="tc-full", functional_fit=4, maintenance_health=5,
                    license_fit=5, stack_compatibility=4,
                    security_risk="low", integration_cost="low",
                    summary="成熟方案", recommendation="adopt",
                ),
            ],
            selected_candidate_ids=["tc-full"],
        ),
    ]

    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)

    assert restored.proactive_analysis.analysis_id == "pa-full"
    assert restored.proactive_analysis.items[0].status == "accepted"
    assert len(restored.deliberation_rounds) == 1
    assert restored.deliberation_rounds[0].findings[0].pm_decision == "accept"
    assert restored.technical_route.architecture_summary == "微服务"
    assert restored.tool_discovery_results[0].candidates[0].name == "Redis"
    assert restored.tool_discovery_results[0].candidates[0].evidence_refs[0].source_type == "github"


def test_empty_v3_fields_roundtrip():
    """V3 字段为空时的往返测试"""
    record = BrainstormRecord(record_id="bs-empty-v3", project_name="EmptyV3")
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.proactive_analysis is None
    assert restored.deliberation_rounds == []
    assert restored.technical_route is None
    assert restored.technical_route_history == []
    assert restored.tool_discovery_results == []


def test_multiple_deliberation_rounds_roundtrip():
    """多轮审查往返测试"""
    record = BrainstormRecord(record_id="bs-multi", project_name="Multi")
    record.deliberation_rounds = [
        DeliberationRound(round_id="dr-1", pm_summary="第一轮"),
        DeliberationRound(round_id="dr-2", pm_summary="第二轮"),
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.deliberation_rounds) == 2
    assert restored.deliberation_rounds[0].pm_summary == "第一轮"
    assert restored.deliberation_rounds[1].pm_summary == "第二轮"


def test_technical_route_history_roundtrip():
    """技术路线修订历史往返测试"""
    record = BrainstormRecord(record_id="bs-route-history", project_name="RouteHistory")
    record.technical_route_history = [
        TechnicalRoute(route_id="tr-old", architecture_summary="单体应用", status="revision_requested")
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.technical_route_history) == 1
    assert restored.technical_route_history[0].architecture_summary == "单体应用"
