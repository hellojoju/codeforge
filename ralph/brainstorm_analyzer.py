"""Phase 3 关系分析 + Phase 4 独立审查"""

from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, RelationshipGraph, RelationshipEdge,
    ConflictRecord, FlowValidation, ReviewResult, ReviewFinding,
    TaskHandoffHint, SourceRef,
)


class BrainstormAnalyzer:
    """独立分析器，避免 Manager 超 800 行"""

    def __init__(self, config_manager: Any = None):
        self.config_manager = config_manager

    def analyze_relationships(self, record: BrainstormRecord) -> RelationshipGraph:
        """Phase 3: LLM 分析依赖/冲突/流验证"""
        from ralph.schema.brainstorm_record import _now_iso
        graph = RelationshipGraph()
        # TODO: 实现 LLM 调用分析
        graph.analyzed_at = _now_iso()
        record.relationship_graph = graph
        return graph

    def independent_review(self, record: BrainstormRecord) -> ReviewResult:
        """Phase 4: 独立 LLM 审查"""
        from ralph.schema.brainstorm_record import _now_iso
        # TODO: 实现 LLM 调用审查
        result = ReviewResult(passed=True, findings=[])
        result.reviewed_at = _now_iso()
        record.review_result = result
        return result

    def generate_task_handoff_hints(self, record: BrainstormRecord) -> list[TaskHandoffHint]:
        """从已确认 FeatureNode 生成下游任务拆解提示"""
        import uuid
        from ralph.schema.brainstorm_record import _now_iso

        hints: list[TaskHandoffHint] = []
        for node in record.feature_tree.nodes.values():
            if node.status != "confirmed":
                continue
            if node.level not in ("function", "sub_function"):
                continue
            hint = TaskHandoffHint(
                hint_id=f"hint-{uuid.uuid4().hex[:6]}",
                source_feature_id=node.node_id,
                suggested_task_boundaries=[node.name],
                likely_dependencies=list(node.dependencies),
                required_recon_questions=[f"功能 {node.name} 的具体技术实现方式？"],
                risk_notes=[f"功能 {node.name} 需要代码库侦察补齐技术上下文"],
                source_refs=list(node.source_refs),
            )
            hints.append(hint)
        record.task_handoff_hints = hints
        return hints
