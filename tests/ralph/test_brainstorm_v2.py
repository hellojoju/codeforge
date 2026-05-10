import pytest
from ralph.schema.brainstorm_record import (
    FeatureNode, FeatureTree, BrainstormRecord, BrainstormPhase,
    SourceRef, ExplicitCheck, QuestionTask,
    RelationshipGraph, RelationshipEdge, ReviewResult, TaskHandoffHint,
    ConfirmedFact, OpenAssumption, UserPath, _now_iso,
)

def test_feature_node_defaults():
    node = FeatureNode(node_id="fn-001", name="测试", level="function")
    assert node.status == "exploring"
    assert node.depth == 0
    assert node.children == []

def test_feature_tree_add_child():
    tree = FeatureTree()
    root = FeatureNode(node_id="root", name="产品", level="product")
    tree.nodes["root"] = root
    child = FeatureNode(node_id="fn-001", name="功能A", level="function")
    tree.add_child("root", child)
    assert "fn-001" in tree.nodes
    assert child.depth == 1
    assert child.parent_id == "root"
    assert "fn-001" in root.children

def test_tree_all_confirmed_empty():
    tree = FeatureTree()
    assert tree.all_confirmed() == False

def test_tree_all_confirmed_true():
    tree = FeatureTree()
    node = FeatureNode(node_id="fn-001", name="A", level="function", status="confirmed")
    tree.nodes["fn-001"] = node
    assert tree.all_confirmed() == True

def test_completeness_score_v2():
    record = BrainstormRecord(record_id="test", project_name="P")
    n1 = FeatureNode(node_id="fn-001", name="A", level="function", status="confirmed")
    n2 = FeatureNode(node_id="fn-002", name="B", level="function", status="exploring")
    record.feature_tree.nodes = {"fn-001": n1, "fn-002": n2}
    assert record.completeness_score() == 0.5

def test_brainstorm_phase_enum():
    assert BrainstormPhase.PRODUCT_DEF == "product_def"
    assert BrainstormPhase.COMPLETE == "complete"

def test_v1_completeness_fallback():
    record = BrainstormRecord(
        record_id="test", project_name="P",
        confirmed_facts=[
            ConfirmedFact(topic="目标用户", fact="用户", source_quote="q"),
            ConfirmedFact(topic="核心功能", fact="功能", source_quote="q"),
            ConfirmedFact(topic="验收标准", fact="标准", source_quote="q"),
        ],
    )
    record.user_paths = [UserPath(name="test", steps=["a"])]
    score = record.completeness_score()
    assert score == 1.0

def test_source_ref_defaults():
    ref = SourceRef(turn_id="t1", quote="用户说...", field_name="target_user")
    assert ref.confidence == 1.0

def test_explicit_check_defaults():
    check = ExplicitCheck(field_name="target_user", state="unknown")
    assert check.reason == ""
    assert check.source_refs == []

def test_question_task_defaults():
    task = QuestionTask(
        question_id="q1", node_id="fn-001", field_name="roles",
        question="谁会用？", reason="缺少角色信息", expected_answer_shape="列举角色",
    )
    assert task.status == "pending"
    assert task.asked_at == ""

def test_relationship_graph_defaults():
    graph = RelationshipGraph()
    assert graph.edges == []
    assert graph.conflicts == []
    assert graph.analyzed_at == ""

def test_relationship_edge_creation():
    edge = RelationshipEdge(
        source_id="fn-001", target_id="fn-002",
        edge_type="depends_on", description="A依赖B",
    )
    assert edge.edge_type == "depends_on"

def test_review_result_defaults():
    result = ReviewResult(passed=True)
    assert result.findings == []
    assert result.reviewed_at == ""

def test_task_handoff_hint():
    hint = TaskHandoffHint(
        hint_id="h1", source_feature_id="fn-001",
        suggested_task_boundaries=["边界1"],
        likely_dependencies=["dep1"],
    )
    assert hint.risk_notes == []

def test_tree_unconfirmed_leaves():
    tree = FeatureTree()
    n1 = FeatureNode(node_id="fn-001", name="A", level="function", status="exploring")
    n2 = FeatureNode(node_id="fn-002", name="B", level="module", status="exploring", children=["fn-001"])
    tree.nodes["fn-001"] = n1
    tree.nodes["fn-002"] = n2
    leaves = tree.unconfirmed_leaves()
    assert len(leaves) == 1
    assert leaves[0].node_id == "fn-001"

def test_record_default_version():
    record = BrainstormRecord(record_id="r1", project_name="Test")
    assert record.version == 2
    assert record.schema_version == "v2"
    assert record.current_phase == "product_def"


# ── V2 BrainstormManager 会话生命周期测试 ──

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from ralph.brainstorm_manager import BrainstormManager


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BrainstormManager(Path(tmpdir))


def test_v2_start_session(manager):
    record = manager.start_session("测试项目", "我想做一个博客系统")
    assert record.record_id.startswith("bs-")
    assert record.current_phase == "product_def"
    assert "fn-root" in record.feature_tree.nodes
    assert record.feature_tree.current_exploring_id == "fn-root"
    root = record.feature_tree.get_node("fn-root")
    assert root.name == "测试项目"
    assert root.level == "product"


def test_v2_load_roundtrip(manager):
    record = manager.start_session("Roundtrip项目", "测试加载")
    loaded = manager.load(record.record_id)
    assert loaded is not None
    assert loaded.record_id == record.record_id
    assert len(loaded.feature_tree.nodes) == 1


def test_v2_resume_session(manager):
    record = manager.start_session("Resume项目", "测试恢复")
    resumed = manager.resume_session(record.record_id)
    assert resumed is not None
    assert resumed.current_phase == "product_def"


def test_v2_resume_nonexistent(manager):
    assert manager.resume_session("nonexistent") is None


def test_v2_list_sessions(manager):
    manager.start_session("项目A", "描述A")
    manager.start_session("项目B", "描述B")
    sessions = manager.list_sessions()
    assert len(sessions) == 2
    assert all("current_phase" in s for s in sessions)
    assert all("active_node_name" in s for s in sessions)
    assert all("completed_features" in s for s in sessions)


# ── Phase 1: 产品定义测试 ──

def test_phase1_build_question_plan(manager):
    record = manager.start_session("博客系统", "我想做一个个人博客")
    manager._build_product_question_plan(record)
    assert len(record.feature_tree.question_plan) > 0
    fields = [t.field_name for t in record.feature_tree.question_plan]
    assert all(
        f in ["vision", "target_users", "roles", "success_criteria", "mvp_scope", "out_of_scope"]
        for f in fields
    )


def test_phase1_explore_product(manager):
    record = manager.start_session("博客系统", "我想做一个个人博客")
    questions = manager.explore_product(record)
    assert len(questions) >= 1


def test_phase1_process_response(manager):
    record = manager.start_session("博客系统", "我想做一个个人博客")
    manager._build_product_question_plan(record)
    task = record.feature_tree.question_plan[0]
    record.feature_tree.current_question_id = task.question_id
    task.status = "asked"

    manager._process_product_response(record, "我的产品是一个面向开发者的技术博客平台")
    root = record.feature_tree.get_node("fn-root")
    assert root is not None
    assert len(root.conversation_turns) >= 1


def test_phase1_check_complete_incomplete(manager):
    record = manager.start_session("项目", "描述")
    root = record.feature_tree.get_node("fn-root")
    assert manager._check_product_complete(root) is False


def test_phase1_check_complete(manager):
    from ralph.schema.brainstorm_record import FeatureNode

    root = FeatureNode(
        node_id="fn-root", name="P", level="product", status="confirmed",
        vision="一个好产品", target_users=["用户"], roles=["管理员"],
        success_criteria=["成功"], mvp_scope=["核心功能"], out_of_scope=["不重要功能"],
    )
    mgr = BrainstormManager.__new__(BrainstormManager)
    assert mgr._check_product_complete(root) is True


# ── Phase 2: 功能分解测试 ──

def test_phase2_get_active_node(manager):
    record = manager.start_session("博客系统", "做一个博客")
    active = manager.get_active_node(record)
    assert active is not None
    assert active.node_id == "fn-root"


def test_phase2_decompose_node(manager):
    record = manager.start_session("博客系统", "做一个博客")
    children = manager.decompose_node(record, ["写文章", "评论系统", "标签管理"])
    assert len(children) == 3
    root = record.feature_tree.get_node("fn-root")
    assert root.children == [c.node_id for c in children]
    assert children[0].level == "function"


def test_phase2_decompose_sub_function(manager):
    record = manager.start_session("博客系统", "做一个博客")
    children = manager.decompose_node(record, ["模块A"])
    # 设置当前在模块A上
    record.feature_tree.current_exploring_id = children[0].node_id
    sub = manager.decompose_node(record, ["子功能1", "子功能2"])
    assert len(sub) == 2
    assert sub[0].level == "sub_function"


def test_phase2_check_granularity(manager):
    record = manager.start_session("博客系统", "做一个博客")
    manager.decompose_node(record, ["写文章"])
    record.feature_tree.current_exploring_id = record.feature_tree.get_node("fn-root").children[0]
    missing = manager.check_granularity(record)
    assert "user_stories" in missing
    assert "acceptance_criteria" in missing


def test_phase2_select_next_node(manager):
    record = manager.start_session("博客系统", "做一个博客")
    manager.decompose_node(record, ["写文章", "评论系统"])
    next_node = manager.select_next_node(record)
    assert next_node is not None
    assert next_node.name == "写文章"


def test_phase2_confirm_node_blocks_if_incomplete(manager):
    record = manager.start_session("博客系统", "做一个博客")
    manager.decompose_node(record, ["写文章"])
    record.feature_tree.current_exploring_id = record.feature_tree.get_node("fn-root").children[0]
    # 子节点缺少字段
    result = manager.confirm_node(record)
    assert result == False


def test_phase2_generate_node_questions(manager):
    record = manager.start_session("博客系统", "做一个博客")
    manager.decompose_node(record, ["写文章"])
    record.feature_tree.current_exploring_id = record.feature_tree.get_node("fn-root").children[0]
    questions = manager.generate_node_questions(record)
    assert len(questions) >= 1


# ── Task B4: 状态机推进与 process_response_v2 ──

def test_advance_phase_product_incomplete(manager):
    record = manager.start_session("项目", "描述")
    result = manager.advance_phase(record)
    assert result is False
    assert record.current_phase == "product_def"


def test_advance_phase_product_to_decompose(manager):
    record = manager.start_session("博客系统", "做一个博客")
    root = record.feature_tree.get_node("fn-root")
    root.vision = "技术博客"
    root.target_users = ["开发者"]
    root.roles = ["管理员"]
    root.success_criteria = ["好"]
    root.mvp_scope = ["写文章"]
    root.out_of_scope = ["评论"]

    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == "feature_decompose"
    # 自动拆分应该创建了子节点
    assert len(root.children) > 0


def test_process_response_v2_routes_to_phase(manager):
    record = manager.start_session("博客系统", "做一个博客")
    assert record.current_phase == "product_def"
    # Phase 1 回复处理不应该报错
    manager._process_product_response(record, "技术博客平台")
    assert len(record.feature_tree.nodes) > 0


def test_is_complete_v2(manager):
    record = manager.start_session("项目", "描述")
    assert manager.is_complete_v2(record) is False
    record.current_phase = BrainstormPhase.COMPLETE
    assert manager.is_complete_v2(record) is True


# ── Task B5: Spec 生成、导出与分析器测试 ──

def test_generate_spec_document(manager):
    record = manager.start_session("博客系统", "做一个博客")
    spec = manager.generate_spec_document(record)
    assert "博客系统" in spec
    assert "产品定义" in spec


def test_export_spec(manager, tmp_path):
    record = manager.start_session("导出测试", "测试导出")
    output = tmp_path / "spec.md"
    path = manager.export_spec(record.record_id, str(output))
    assert path.exists()
    assert "导出测试" in path.read_text()


def test_export_spec_nonexistent_record(manager, tmp_path):
    with pytest.raises(ValueError, match="not found"):
        manager.export_spec("nonexistent", str(tmp_path / "spec.md"))


def test_generate_task_handoff_hints():
    from ralph.brainstorm_analyzer import BrainstormAnalyzer

    analyzer = BrainstormAnalyzer()

    record = BrainstormRecord(record_id="test", project_name="P")
    node = FeatureNode(
        node_id="fn-001", name="用户登录", level="function", status="confirmed",
        dependencies=["fn-002"],
        source_refs=[SourceRef(turn_id="t1", quote="需要登录", field_name="name")],
    )
    record.feature_tree.nodes["fn-001"] = node

    hints = analyzer.generate_task_handoff_hints(record)
    assert len(hints) == 1
    assert hints[0].source_feature_id == "fn-001"
    assert "用户登录" in hints[0].suggested_task_boundaries


def test_generate_task_handoff_hints_skips_unconfirmed():
    from ralph.brainstorm_analyzer import BrainstormAnalyzer

    analyzer = BrainstormAnalyzer()
    record = BrainstormRecord(record_id="test", project_name="P")
    record.feature_tree.nodes["fn-001"] = FeatureNode(
        node_id="fn-001", name="未确认", level="function", status="exploring",
    )
    record.feature_tree.nodes["fn-002"] = FeatureNode(
        node_id="fn-002", name="产品级", level="product", status="confirmed",
    )
    hints = analyzer.generate_task_handoff_hints(record)
    assert len(hints) == 0


def test_analyze_relationships():
    from ralph.brainstorm_analyzer import BrainstormAnalyzer

    analyzer = BrainstormAnalyzer()
    record = BrainstormRecord(record_id="test", project_name="P")
    graph = analyzer.analyze_relationships(record)
    assert graph.analyzed_at != ""
    assert record.relationship_graph is graph


def test_independent_review():
    from ralph.brainstorm_analyzer import BrainstormAnalyzer

    analyzer = BrainstormAnalyzer()
    record = BrainstormRecord(record_id="test", project_name="P")
    result = analyzer.independent_review(record)
    assert result.passed is True
    assert record.review_result is result


# ── E2E: Phase 1-4 完整流程测试 ──

def _confirm_all_children(record):
    """辅助：将当前 active node 的所有兄弟节点标记为 confirmed"""
    root = record.feature_tree.get_node("fn-root")
    for child_id in root.children:
        child = record.feature_tree.get_node(child_id)
        if child and child.status != "confirmed":
            child.user_stories = ["As a 用户"]
            child.acceptance_criteria = ["Given/When/Then"]
            child.success_path = ["步骤1"]
            child.failure_path = ["失败"]
            child.edge_cases = ["边界"]
            child.data_requirements = ["数据"]
            child.explicit_checks["dependencies"] = ExplicitCheck(
                field_name="dependencies", state="yes", reason="无依赖",
            )
            child.explicit_checks["business_rules"] = ExplicitCheck(
                field_name="business_rules", state="no", reason="无业务规则",
            )
            child.explicit_checks["permission_rules"] = ExplicitCheck(
                field_name="permission_rules", state="yes", reason="仅管理员",
            )
            child.status = "confirmed"
            child.confirmed_at = _now_iso()


def test_e2e_full_brainstorm_flow(manager):
    """完整流程：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Complete"""
    # Phase 1: 产品定义
    record = manager.start_session("测试项目", "我想做一个任务管理系统")
    assert record.current_phase == "product_def"

    # 补齐产品定义所有字段
    root = record.feature_tree.get_node("fn-root")
    root.vision = "高效的团队协作任务管理"
    root.target_users = ["项目经理", "团队成员"]
    root.roles = ["管理员", "普通用户"]
    root.success_criteria = ["任务按时完成率提升30%"]
    root.mvp_scope = ["创建任务", "分配任务", "查看状态"]
    root.out_of_scope = ["甘特图", "时间追踪"]

    assert manager._check_product_complete(root) is True
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == "feature_decompose"

    # Phase 2: 自动拆分后应该有子节点
    assert len(root.children) > 0
    record.feature_tree.current_exploring_id = root.children[0]

    # 补全第一个子节点
    first_child = record.feature_tree.get_node(root.children[0])
    first_child.user_stories = [
        "As a 管理员, 我想创建任务, 以便分配工作",
    ]
    first_child.acceptance_criteria = [
        "Given 用户在任务页面 When 点击创建 Then 显示表单",
    ]
    first_child.success_path = ["打开任务页面", "填写标题", "点击保存"]
    first_child.failure_path = ["标题为空", "显示错误提示"]
    first_child.edge_cases = ["标题超长", "并发创建任务"]
    first_child.data_requirements = [
        "Task 表: id, title, status, assignee_id",
    ]
    first_child.explicit_checks["dependencies"] = ExplicitCheck(
        field_name="dependencies", state="yes", reason="无依赖",
    )
    first_child.explicit_checks["business_rules"] = ExplicitCheck(
        field_name="business_rules", state="no", reason="无业务规则",
    )
    first_child.explicit_checks["permission_rules"] = ExplicitCheck(
        field_name="permission_rules", state="yes", reason="仅管理员可创建",
    )
    first_child.status = "confirmed"
    first_child.confirmed_at = _now_iso()

    # 其他子节点也全部确认
    _confirm_all_children(record)

    # 推进到关系分析
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == "relationship"

    # Phase 3: 关系分析
    record.relationship_graph.analyzed_at = _now_iso()
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == "independent_review"

    # Phase 4: 独立审查
    from ralph.brainstorm_analyzer import BrainstormAnalyzer
    analyzer = BrainstormAnalyzer()
    analyzer.independent_review(record)
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == "complete"

    # 验证 Spec 生成
    spec = manager.generate_spec_document(record)
    assert "测试项目" in spec

    # 验证 Handoff 生成
    hints = analyzer.generate_task_handoff_hints(record)
    assert len(hints) >= 1


def test_e2e_process_response_v2_routing(manager):
    """测试 process_response_v2 的路由逻辑"""
    record = manager.start_session("路由项目", "描述")
    assert record.current_phase == "product_def"

    # Phase 1 回复处理
    manager._build_product_question_plan(record)
    task = record.feature_tree.question_plan[0]
    record.feature_tree.current_question_id = task.question_id
    task.status = "asked"

    manager.process_response_v2(record, "我的产品是任务管理系统")
    # 应该在 Phase 1 继续（产品定义未补齐，advance_phase 返回 False）
    assert record.current_phase == "product_def"

    # 补齐产品定义后再次调用，应该能推进到 feature_decompose
    root = record.feature_tree.get_node("fn-root")
    root.vision = "任务管理"
    root.target_users = ["用户"]
    root.roles = ["管理员"]
    root.success_criteria = ["高效"]
    root.mvp_scope = ["核心"]
    root.out_of_scope = ["其他"]

    manager.process_response_v2(record, "补充信息")
    assert record.current_phase == "feature_decompose"


def test_e2e_spec_export_roundtrip(manager, tmp_path):
    """Spec 导出往返测试"""
    record = manager.start_session("导出项目", "测试")
    root = record.feature_tree.get_node("fn-root")
    root.vision = "测试愿景"
    root.target_users = ["测试用户"]
    root.roles = ["角色"]
    root.success_criteria = ["标准"]
    root.mvp_scope = ["范围"]
    root.out_of_scope = ["不做"]

    manager.advance_phase(record)

    output = tmp_path / "spec.md"
    path = manager.export_spec(record.record_id, str(output))
    assert path.exists()
    content = path.read_text()
    assert "导出项目" in content
    assert "测试愿景" in content


def test_e2e_granularity_gate(manager):
    """粒度门控：缺少字段时不能确认节点"""
    record = manager.start_session("门控项目", "描述")
    manager.decompose_node(record, ["功能A"])
    root = record.feature_tree.get_node("fn-root")
    record.feature_tree.current_exploring_id = root.children[0]

    active = manager.get_active_node(record)
    assert active is not None

    # 缺少所有必填字段
    missing = manager._get_missing_items(active)
    assert len(missing) > 0

    # confirm_node 应该返回 False
    assert manager.confirm_node(record) is False

    # 补全所有字段
    active.user_stories = ["As a 用户"]
    active.acceptance_criteria = ["Given/When/Then"]
    active.success_path = ["步骤1"]
    active.failure_path = ["失败"]
    active.edge_cases = ["边界"]
    active.data_requirements = ["数据"]
    active.explicit_checks["dependencies"] = ExplicitCheck(field_name="dependencies", state="yes", reason="")
    active.explicit_checks["business_rules"] = ExplicitCheck(field_name="business_rules", state="yes", reason="")
    active.explicit_checks["permission_rules"] = ExplicitCheck(field_name="permission_rules", state="yes", reason="")

    # 现在应该能确认
    assert manager.confirm_node(record) is True
    assert active.status == "confirmed"
