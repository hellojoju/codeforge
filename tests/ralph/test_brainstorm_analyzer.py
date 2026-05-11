"""BrainstormAnalyzer 测试 — analyze_relationships + independent_review 骨架"""
import json

from ralph.brainstorm_analyzer import BrainstormAnalyzer
from ralph.schema.brainstorm_record import (
    BrainstormPhase,
    BrainstormRecord,
    FeatureNode,
    FeatureTree,
)


def _make_record_with_nodes(nodes: list[FeatureNode]) -> BrainstormRecord:
    """创建包含指定功能节点的测试 record"""
    root = FeatureNode(node_id="fn-root", name="TestProject", level="product", status="confirmed")
    tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
    for node in nodes:
        tree.add_child("fn-root", node)
    record = BrainstormRecord(
        record_id="bs-test", project_name="TestProject",
        current_phase=BrainstormPhase.FEATURE_DECOMPOSE,
        feature_tree=tree,
    )
    return record


class TestAnalyzeRelationships:
    """analyze_relationships 测试"""

    def test_empty_nodes_returns_empty_graph(self):
        """没有功能节点时返回空图"""
        record = _make_record_with_nodes([])
        analyzer = BrainstormAnalyzer()
        graph = analyzer.analyze_relationships(record)
        assert graph.analyzed_at != ""
        assert graph.edges == []
        assert graph.conflicts == []
        assert graph.flow_validations == []

    def test_no_config_returns_empty_graph(self):
        """没有 config_manager 时降级到空图"""
        node = FeatureNode(node_id="fn-001", name="登录", level="function", status="confirmed")
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()  # no config
        graph = analyzer.analyze_relationships(record)
        assert graph.analyzed_at != ""
        assert isinstance(graph.edges, list)

    def test_llm_returns_parses_edges(self, monkeypatch):
        """LLM 返回数据正确解析为 edges"""
        node_a = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        node_b = FeatureNode(
            node_id="fn-002", name="权限管理", level="function", status="confirmed",
            user_stories=["As an admin, I want to manage permissions"],
            dependencies=["fn-001"],
        )
        record = _make_record_with_nodes([node_a, node_b])
        analyzer = BrainstormAnalyzer()

        fake_content = json.dumps({
            "edges": [
                {"source_id": "fn-002", "target_id": "fn-001", "edge_type": "depends_on", "description": "权限管理依赖登录"}
            ],
            "conflicts": [],
            "flow_validations": []
        })
        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: fake_content)

        graph = analyzer.analyze_relationships(record)
        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == "depends_on"
        assert graph.edges[0].source_id == "fn-002"
        assert graph.edges[0].target_id == "fn-001"
        assert graph.analyzed_at != ""

    def test_llm_returns_parses_conflicts(self, monkeypatch):
        """LLM 返回的冲突正确解析"""
        node_a = FeatureNode(
            node_id="fn-001", name="实时编辑", level="function", status="confirmed",
            user_stories=["As a user, I want real-time editing"],
        )
        node_b = FeatureNode(
            node_id="fn-002", name="离线编辑", level="function", status="confirmed",
            user_stories=["As a user, I want offline editing"],
        )
        record = _make_record_with_nodes([node_a, node_b])
        analyzer = BrainstormAnalyzer()

        fake_content = json.dumps({
            "edges": [],
            "conflicts": [
                {"feature_a": "fn-001", "feature_b": "fn-002", "description": "实时和离线编辑冲突", "severity": "critical"}
            ],
            "flow_validations": []
        })
        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: fake_content)

        graph = analyzer.analyze_relationships(record)
        assert len(graph.conflicts) == 1
        assert graph.conflicts[0].severity == "critical"

    def test_llm_failure_falls_back_to_empty_graph(self, monkeypatch):
        """LLM 返回无效 JSON 时降级到空图"""
        node = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()

        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: "not valid json {{{")

        graph = analyzer.analyze_relationships(record)
        assert graph.analyzed_at != ""
        assert graph.edges == []


class TestIndependentReview:
    """independent_review 测试"""

    def test_review_passes_with_good_spec(self, monkeypatch):
        """LLM 返回通过审查时正确返回"""
        node = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
            acceptance_criteria=["Given valid credentials When submit Then login"],
            success_path=["用户输入账号密码", "系统验证成功"],
            failure_path=["密码错误，提示重试"],
            edge_cases=["连续失败锁定"],
            data_requirements=["存储用户账号密码哈希"],
        )
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()

        fake_content = json.dumps({"passed": True, "findings": []})
        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: fake_content)

        result = analyzer.independent_review(record)
        assert result.passed is True
        assert result.reviewed_at != ""
        assert result.findings == []

    def test_review_finds_issues(self, monkeypatch):
        """LLM 发现问题时正确返回"""
        node = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        # 缺少 acceptance_criteria, paths, edge_cases 等
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()

        fake_content = json.dumps({
            "passed": False,
            "findings": [
                {
                    "finding_type": "incomplete",
                    "feature_id": "fn-001",
                    "description": "缺少验收标准和路径",
                    "severity": "critical"
                }
            ]
        })
        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: fake_content)

        result = analyzer.independent_review(record)
        assert result.passed is False
        assert len(result.findings) == 1
        assert result.findings[0].severity == "critical"
        assert result.findings[0].finding_type == "incomplete"

    def test_review_falls_back_to_pass_on_llm_failure(self, monkeypatch):
        """LLM 失败时降级为通过"""
        node = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()

        monkeypatch.setattr(analyzer, "_call_llm", lambda *a, **kw: "not valid json")

        result = analyzer.independent_review(record)
        assert result.passed is True
        assert result.reviewed_at != ""

    def test_review_includes_spec_content(self, monkeypatch):
        """审查 prompt 包含功能节点信息"""
        node = FeatureNode(
            node_id="fn-001", name="登录功能", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        record = _make_record_with_nodes([node])
        analyzer = BrainstormAnalyzer()

        captured = {}

        def capture_call(*args, **kw):
            captured["task_type"] = args[0] if args else kw.get("task_type")
            captured["messages"] = args[1] if len(args) > 1 else kw.get("messages", [])
            return json.dumps({"passed": True, "findings": []})

        monkeypatch.setattr(analyzer, "_call_llm", capture_call)
        analyzer.independent_review(record)

        assert captured.get("messages")
        prompt_text = captured["messages"][0]["content"]
        assert "登录功能" in prompt_text
        assert "用户故事" in prompt_text
