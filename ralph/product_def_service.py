"""ProductDefService — 多 Agent 产品定义分析。

在 PRODUCT_DEF 阶段，从 4 个维度同时分析产品想法，
让用户一次性看到所有视角的分析结果并确认。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable

from ralph.schema.brainstorm_record import (
    BrainstormRecord, ProductDefFinding, ProductDefRound, _now_iso,
)

logger = logging.getLogger(__name__)

DIMENSIONS = [
    {
        "role": "product_vision",
        "display_name": "产品愿景分析",
        "prompt": (
            "你是资深产品策略师。从产品愿景角度分析：\n"
            "- 这个产品的核心价值是什么？\n"
            "- 目标市场定位是否清晰？\n"
            "- 与同类产品的差异化在哪里？\n"
            "- 产品成功的关键因素是什么？\n"
            "请给出具体的分析和建议。"
        ),
    },
    {
        "role": "user_experience",
        "display_name": "用户体验分析",
        "prompt": (
            "你是资深 UX 设计师。从用户体验角度分析：\n"
            "- 目标用户的核心痛点是什么？\n"
            "- 用户使用场景和路径是怎样的？\n"
            "- 有哪些容易被忽略的体验细节？\n"
            "- 如何降低用户的学习成本？\n"
            "请给出具体的分析和建议。"
        ),
    },
    {
        "role": "technical_feasibility",
        "display_name": "技术可行性分析",
        "prompt": (
            "你是资深技术架构师。从技术可行性角度分析：\n"
            "- 实现这个产品需要哪些核心技术能力？\n"
            "- 有哪些技术风险或技术难点？\n"
            "- 推荐的初步技术方向是什么？\n"
            "- 有哪些可以复用的开源方案？\n"
            "请给出具体的分析和建议。"
        ),
    },
    {
        "role": "business_value",
        "display_name": "商业价值分析",
        "prompt": (
            "你是资深商业分析师。从商业价值角度分析：\n"
            "- 这个产品的商业模式/变现路径是什么？\n"
            "- 市场规模和增长潜力如何？\n"
            "- 进入壁垒和竞争格局是怎样的？\n"
            "- 有哪些商业风险需要关注？\n"
            "请给出具体的分析和建议。"
        ),
    },
]


class ProductDefService:
    """执行四维多 Agent 产品定义分析。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def run_analysis(
        self,
        record: BrainstormRecord,
        on_progress: Callable[[int, int, str, ProductDefFinding | None], None] | None = None,
    ) -> ProductDefRound:
        """执行多 Agent 产品分析，返回汇总结果。

        Args:
            record: BrainstormRecord
            on_progress: 回调函数(completed_count, total_count, current_dim, latest_finding)，每完成一个维度调用
        """
        root = record.feature_tree.get_node("fn-root")
        project_context = self._build_project_context(record, root)

        round_result = ProductDefRound(
            round_id=f"pd-{uuid.uuid4().hex[:8]}",
            created_at=_now_iso(),
        )

        all_findings: list[ProductDefFinding] = []

        for dim in DIMENSIONS:
            finding = self._analyze_dimension(project_context, dim)
            if finding:
                all_findings.append(finding)
                if on_progress:
                    analyzed = [f.dimension for f in all_findings]
                    on_progress(len(analyzed), len(DIMENSIONS), dim["role"], finding)

        round_result.findings = all_findings
        round_result.summary = self._summarize_findings(all_findings)

        record.product_def_rounds.append(round_result)
        return round_result

    def _build_project_context(
        self, record: BrainstormRecord, root
    ) -> str:
        """构建产品上下文文本。"""
        parts = [f"# {record.project_name}"]

        if root:
            if root.vision:
                parts.append(f"愿景: {root.vision}")
            if root.target_users:
                parts.append(f"目标用户: {', '.join(root.target_users)}")
            if root.roles:
                parts.append(f"用户角色: {', '.join(root.roles)}")
            if root.mvp_scope:
                parts.append(f"MVP 范围: {', '.join(root.mvp_scope)}")
            if root.success_criteria:
                parts.append(f"成功标准: {', '.join(root.success_criteria)}")

        # 加入用户的初始描述和已确认的主动分析
        if record.user_message:
            parts.append(f"\n用户原始描述: {record.user_message}")

        if record.proactive_analysis and record.proactive_analysis.items:
            accepted = [
                item for item in record.proactive_analysis.items
                if item.status in ("accepted", "modified")
            ]
            if accepted:
                parts.append("\n已确认的初步分析:")
                for item in accepted:
                    content = item.user_revision if item.status == "modified" else item.content
                    parts.append(f"- {content}")

        return "\n".join(parts)

    def _analyze_dimension(
        self, context: str, dimension: dict
    ) -> ProductDefFinding | None:
        """对单个维度执行分析。"""
        prompt = f"""{dimension['prompt']}

以下是产品上下文：

{context}

请以 JSON 格式返回分析结果：
{{
  "finding": "整体分析总结（2-3 句话）",
  "suggestions": ["具体建议 1", "具体建议 2"],
  "questions": ["需要用户确认的问题 1", "问题 2"],
  "confidence": 0.8
}}

如果没有具体发现，suggestions 和 questions 可以为空数组。"""

        content = self._call_llm(f"product_def_{dimension['role']}", [{"role": "user", "content": prompt}])

        if not content:
            logger.warning("ProductDefService: %s returned empty", dimension["role"])
            return None

        try:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n", 1)
                if len(lines) > 1:
                    content = lines[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content[4:].strip()

            data = json.loads(content)
            if not isinstance(data, dict):
                logger.warning("ProductDefService: expected dict, got %s", type(data))
                return None

            return ProductDefFinding(
                finding_id=f"pdf-{uuid.uuid4().hex[:8]}",
                dimension=dimension["role"],
                dimension_name=dimension["display_name"],
                content=data.get("finding", ""),
                suggestions=data.get("suggestions", []),
                questions=data.get("questions", []),
                confidence=data.get("confidence", 0.8),
            )
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning("ProductDefService: %s parse error: %s", dimension["role"], e)
            return None

    def _summarize_findings(self, findings: list[ProductDefFinding]) -> str:
        """汇总所有分析发现。"""
        if not findings:
            return "多 Agent 分析未能生成有效结果，请补充更多产品描述。"

        parts = []
        for f in findings:
            if f.content:
                parts.append(f"**{f.dimension_name}**: {f.content}")
            if f.questions:
                parts.append(f"  待确认: {'; '.join(f.questions[:3])}")

        if not parts:
            return "分析已生成，但缺少具体发现。请查看各维度的详细建议。"

        return "\n".join(parts)

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
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
                content = result["data"]["choices"][0]["message"]["content"]
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("ProductDefService: LLM 响应结构异常")
        return None

    def confirm_finding(
        self, record: BrainstormRecord, finding_id: str,
        decision: str, reason: str = "", revision: str = "",
    ) -> None:
        """对指定分析发现做用户裁决。"""
        allowed = {"accept", "reject", "defer"}
        if decision not in allowed:
            raise ValueError(f"Invalid decision: {decision}")

        for rnd in record.product_def_rounds:
            for finding in rnd.findings:
                if finding.finding_id == finding_id:
                    finding.pm_decision = decision
                    finding.pm_reason = reason
                    finding.user_revision = revision
                    finding.status = "accepted" if decision == "accept" else (
                        "modified" if decision == "defer" and revision else "rejected"
                    )
                    return
        raise ValueError(f"Finding not found: {finding_id}")
