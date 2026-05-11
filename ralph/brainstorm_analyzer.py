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
        spec_text = self._render_spec_for_review(record)

        prompt = f"""你是独立需求质量审查员。你没有参与之前的需求共创对话。
以下是一份完整的产品需求规格草案：

{spec_text}

请从以下 6 个维度审查：
1. 粒度：每个功能点是否足够细，能直接拆成开发任务？
2. 逻辑：用户路径是否有死胡同？失败路径是否覆盖所有异常？
3. 一致性：功能之间是否有矛盾或重复？
4. 边界：是否遗漏了重要的边界场景？
5. 完整性：是否所有关键需求领域都已覆盖？
6. 追溯性：每条确定需求是否能追溯用户原话或用户确认？

请以 JSON 返回：
{{
  "passed": true/false,
  "findings": [
    {{
      "finding_type": "too_coarse | logical_gap | inconsistency | missing_edge_case | incomplete | traceability_gap",
      "feature_id": "...",
      "description": "具体问题描述",
      "severity": "critical | warning"
    }}
  ]
}}"""

        content = self._call_llm("independent_review", [{"role": "user", "content": prompt}])

        result = ReviewResult(passed=True, findings=[])
        if content:
            # 处理 markdown code fence
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n", 1)
                content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                if content.startswith("json"):
                    content = content[4:].strip()
            try:
                data = json.loads(content)
                result = ReviewResult(
                    passed=data.get("passed", True),
                    findings=[ReviewFinding(**f) for f in data.get("findings", [])],
                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning("BrainstormAnalyzer: LLM review parse error: %s", e)

        result.reviewed_at = _now_iso()
        record.review_result = result
        return result

    def _render_spec_for_review(self, record: BrainstormRecord) -> str:
        """生成用于审查的 Spec Document"""
        lines = [f"# {record.project_name} - 需求规格文档", ""]
        root = record.feature_tree.get_node("fn-root")
        if root:
            lines.extend([
                "## 产品定义", "",
                f"**愿景：** {root.vision}", "",
                f"**目标用户：** {', '.join(root.target_users) if root.target_users else '待明确'}", "",
                f"**用户角色：** {', '.join(root.roles) if root.roles else '待明确'}", "",
                f"**MVP 范围：** {', '.join(root.mvp_scope) if root.mvp_scope else '待明确'}", "",
                f"**明确不做：** {', '.join(root.out_of_scope) if root.out_of_scope else '无'}", "",
            ])
        lines.extend(["## 功能分解", ""])
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            status_icon = {"confirmed": "[x]", "exploring": "[~]", "pending": "[ ]"}.get(node.status, "[ ]")
            lines.append(f"### {status_icon} {node.name} ({node.node_id})")
            if node.user_stories:
                lines.append(f"- 用户故事: {'; '.join(node.user_stories)}")
            if node.acceptance_criteria:
                lines.append(f"- 验收标准: {'; '.join(node.acceptance_criteria)}")
            if node.success_path:
                lines.append(f"- 成功路径: {'; '.join(node.success_path)}")
            if node.failure_path:
                lines.append(f"- 失败路径: {'; '.join(node.failure_path)}")
            if node.edge_cases:
                lines.append(f"- 边界场景: {'; '.join(node.edge_cases)}")
            if node.data_requirements:
                lines.append(f"- 数据需求: {'; '.join(node.data_requirements)}")
            if node.dependencies:
                lines.append(f"- 依赖: {', '.join(node.dependencies)}")
            lines.append("")
        return "\n".join(lines)

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
