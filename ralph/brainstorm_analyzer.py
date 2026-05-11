"""Phase 3 关系分析 + Phase 4 独立审查"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from ralph.schema.brainstorm_record import (
    BrainstormRecord, RelationshipGraph, RelationshipEdge,
    ConflictRecord, FlowValidation, ReviewResult, ReviewFinding,
    TaskHandoffHint, SourceRef,
)
from ralph.schema.brainstorm_record import _now_iso


class BrainstormAnalyzer:
    """独立分析器，避免 Manager 超 800 行"""

    def __init__(self, config_manager: Any = None):
        self.config_manager = config_manager

    def analyze_relationships(self, record: BrainstormRecord) -> RelationshipGraph:
        """Phase 3: LLM 分析依赖/冲突/流验证"""
        confirmed = [
            n for n in record.feature_tree.nodes.values()
            if n.status == "confirmed" and n.level in ("function", "sub_function")
        ]

        if not confirmed:
            graph = RelationshipGraph()
            graph.analyzed_at = _now_iso()
            record.relationship_graph = graph
            return graph

        nodes_text = "\n".join(
            f"- {n.node_id}: {n.name}\n"
            f"  用户故事: {n.user_stories}\n"
            f"  成功路径: {n.success_path}\n"
            f"  失败路径: {n.failure_path}\n"
            f"  依赖: {n.dependencies}\n"
            f"  业务规则: {n.business_rules}\n"
            f"  权限规则: {n.permission_rules}"
            for n in confirmed
        )

        prompt = f"""你是资深系统架构师。
以下是一个产品的所有已确认功能节点：

{nodes_text}

请分析：
1. 依赖关系：哪些功能依赖其他功能？（depends_on / enables）
2. 功能冲突：哪些功能之间存在互斥或冲突？（conflicts_with / mutually_exclusive）
3. 流程验证：哪些用户路径存在死胡同？哪些缺少错误分支？是否有循环依赖？

请以 JSON 返回：
{{
  "edges": [{{"source_id": "...", "target_id": "...", "edge_type": "...", "description": "..."}}],
  "conflicts": [{{"feature_a": "...", "feature_b": "...", "description": "...", "severity": "..."}}],
  "flow_validations": [{{"feature_id": "...", "issue_type": "...", "description": "..."}}]
}}

即使没有发现任何关系，也必须返回空数组。"""

        graph = RelationshipGraph()

        content = self._call_llm("relationship_analysis", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                graph.edges = [
                    RelationshipEdge(**e) for e in data.get("edges", [])
                ]
                graph.conflicts = [
                    ConflictRecord(**c) for c in data.get("conflicts", [])
                ]
                graph.flow_validations = [
                    FlowValidation(**f) for f in data.get("flow_validations", [])
                ]
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning("BrainstormAnalyzer: LLM relationship analysis parse error: %s", e)

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

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        """统一 LLM 调用入口"""
        if self.config_manager is None:
            return None
        try:
            provider = self.config_manager.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self.config_manager.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )
        if result.get("ok"):
            try:
                return result["data"]["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                logger.warning("BrainstormAnalyzer: LLM response structure error: %s", e)
        return None
