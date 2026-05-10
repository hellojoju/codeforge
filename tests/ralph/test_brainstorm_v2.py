import pytest
from ralph.schema.brainstorm_record import (
    FeatureNode, FeatureTree, BrainstormRecord, BrainstormPhase,
    SourceRef, ExplicitCheck, QuestionTask,
    RelationshipGraph, RelationshipEdge, ReviewResult, TaskHandoffHint,
    ConfirmedFact, OpenAssumption, UserPath,
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
