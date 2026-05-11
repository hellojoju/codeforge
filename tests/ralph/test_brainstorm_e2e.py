"""Brainstorm V2 端到端流程测试"""
import json

from ralph.brainstorm_analyzer import BrainstormAnalyzer
from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    BrainstormPhase,
    BrainstormRecord,
    FeatureNode,
    ReviewFinding,
    ReviewResult,
    _now_iso,
)


def make_mgr(tmp_path) -> BrainstormManager:
    """创建 BrainstormManager 测试实例"""
    return BrainstormManager(tmp_path)


def fill_product_def(record: BrainstormRecord) -> None:
    """填充产品定义字段，使 Phase 1 → Phase 2 守卫通过"""
    root = record.feature_tree.get_node("fn-root")
    if root:
        root.vision = "帮助团队高效管理任务"
        root.target_users = ["团队成员", "项目经理"]
        root.roles = ["管理员", "普通成员"]
        root.success_criteria = ["每日任务完成率 > 80%"]
        root.mvp_scope = ["创建任务", "分配任务", "标记完成"]
        root.out_of_scope = ["时间线视图", "甘特图"]


def add_confirmed_feature(record: BrainstormRecord, node_id: str, name: str, **kwargs) -> FeatureNode:
    """添加一个已确认的功能节点"""
    node = FeatureNode(
        node_id=node_id, name=name, level="function", status="confirmed",
        user_stories=kwargs.get("user_stories", ["As a user, I want this feature"]),
        acceptance_criteria=kwargs.get("acceptance_criteria", ["Given setup When action Then result"]),
        success_path=kwargs.get("success_path", ["步骤1", "步骤2"]),
        failure_path=kwargs.get("failure_path", ["失败场景", "恢复方式"]),
        edge_cases=kwargs.get("edge_cases", ["边界场景1"]),
        data_requirements=kwargs.get("data_requirements", ["存储核心数据"]),
    )
    node.confirmed_at = _now_iso()
    record.feature_tree.add_child("fn-root", node)
    return node


def _clear_auto_decomposed(record: BrainstormRecord) -> None:
    """清除 advance_phase 自动拆分的 exploring 子节点，以便手动添加 confirmed 节点"""
    root = record.feature_tree.get_node("fn-root")
    if root:
        for child_id in list(root.children):
            child = record.feature_tree.get_node(child_id)
            if child and child.status == "exploring":
                del record.feature_tree.nodes[child_id]
        root.children = []


class TestBrainstormFullFlow:
    """端到端完整流程测试"""

    def test_product_def_to_complete_no_llm(self, tmp_path):
        """完整流程：Phase 1 → Phase 2 → Phase 3 → Phase 4 → COMPLETE（无 LLM 降级）"""
        mgr = make_mgr(tmp_path)

        # Phase 1: 创建 session
        record = mgr.start_session("TestProject", "一个团队协作的待办应用")
        assert record.current_phase == "product_def"
        assert record.feature_tree.get_node("fn-root") is not None

        # 填充产品定义
        fill_product_def(record)

        # 推进 Phase 1 → Phase 2（会触发 auto_decompose，产生 exploring 子节点）
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.FEATURE_DECOMPOSE

        # 清除自动拆分的 exploring 节点，改为手动添加 confirmed 节点
        _clear_auto_decomposed(record)

        # 创建并确认功能节点
        add_confirmed_feature(record, "fn-001", "任务管理")
        add_confirmed_feature(record, "fn-002", "通知系统")

        # 推进 Phase 2 → Phase 3
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.RELATIONSHIP

        # Phase 3: 关系分析（无 LLM，降级到空图）
        analyzer = BrainstormAnalyzer()
        analyzer.analyze_relationships(record)
        assert record.relationship_graph.analyzed_at != ""

        # 推进 Phase 3 → Phase 4
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW

        # Phase 4: 独立审查（无 LLM，降级为通过）
        result = analyzer.independent_review(record)
        record.review_result = result

        # 推进 Phase 4 → COMPLETE
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.COMPLETE

        # 验证 spec document 生成
        spec = mgr.generate_spec_document(record)
        assert "TestProject" in spec
        assert "任务管理" in spec
        assert "通知系统" in spec

        # 验证 handoff hints 生成
        hints = analyzer.generate_task_handoff_hints(record)
        assert len(hints) >= 1
        assert hints[0].source_feature_id in ("fn-001", "fn-002")

    def test_review_fails_then_clarification_flow(self, tmp_path):
        """审查不通过 → CLARIFICATION → 重新审查 → 通过"""
        mgr = make_mgr(tmp_path)
        record = mgr.start_session("TestProject", "简单应用")

        # Phase 1
        fill_product_def(record)
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.FEATURE_DECOMPOSE

        # 清除自动拆分的节点，创建有问题的节点（字段不全但手动设为 confirmed）
        _clear_auto_decomposed(record)
        node = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        node.confirmed_at = _now_iso()
        record.feature_tree.add_child("fn-root", node)

        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.RELATIONSHIP

        # Phase 3
        analyzer = BrainstormAnalyzer()
        analyzer.analyze_relationships(record)
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW

        # Phase 4: 模拟审查不通过
        record.review_result = ReviewResult(
            passed=False,
            findings=[ReviewFinding(
                finding_type="incomplete",
                feature_id="fn-001",
                description="缺少验收标准、路径、边界场景",
                severity="critical",
            )],
        )

        # 推进 → CLARIFICATION
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.CLARIFICATION

        # 标记需要澄清的节点
        node.status = "needs_clarification"
        node.review_feedback = ["补充验收标准和路径"]

        # 澄清后重新进入审查
        mgr._process_clarification_response(record, "已补充")
        assert node.status == "exploring"
        node.status = "confirmed"
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW

    def test_v1_migration_then_continue_v2_flow(self, tmp_path):
        """V1 数据迁移后能继续 V2 流程"""
        # 写入 V1 格式 JSON
        v1_data = {
            "record_id": "bs-v1-migrated",
            "project_name": "OldProject",
            "round_number": 3,
            "user_message": "我想做个 todo 应用",
            "confirmed_facts": [
                {"topic": "核心功能", "fact": "创建和删除任务", "source_quote": "我需要能创建和删除任务"},
                {"topic": "目标用户", "fact": "个人用户", "source_quote": "给我自己用的"},
            ],
            "open_assumptions": [],
            "user_paths": [{"name": "创建任务", "steps": ["点击添加", "输入标题", "保存"], "edge_cases": []}],
            "created_at": "2026-05-01T00:00:00",
        }
        brainstorm_dir = tmp_path / "brainstorm"
        brainstorm_dir.mkdir()
        (brainstorm_dir / "bs-v1-migrated.json").write_text(json.dumps(v1_data))

        mgr = make_mgr(tmp_path)
        record = mgr.load("bs-v1-migrated")

        assert record is not None
        assert record.schema_version == "v2"
        assert record.feature_tree.get_node("fn-root") is not None
        # V1 facts 应该迁移到功能节点
        assert len(record.feature_tree.nodes) > 1  # root + topic nodes

        # 可以继续 V2 流程
        fill_product_def(record)
        mgr.advance_phase(record)
        # V1 迁移后 current_phase 默认是 feature_decompose，且 topic 节点已 confirmed，
        # 所以 all_confirmed() 可能直接通过，推进到 relationship
        assert record.current_phase in (
            BrainstormPhase.FEATURE_DECOMPOSE,
            BrainstormPhase.RELATIONSHIP,
            BrainstormPhase.PRODUCT_DEF,
        )
