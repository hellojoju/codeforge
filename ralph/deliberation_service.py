"""DeliberationReviewService — 四维结构化功能审查。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, DeliberationFinding, DeliberationRound, FeatureNode,
    _now_iso,
)

logger = logging.getLogger(__name__)

# 四个审查维度的定义
DIMENSIONS = [
    {
        "role": "user_journey_analyst",
        "display_name": "用户行为路径分析",
        "prompt": "从用户行为路径角度审查：用户进入产品后的操作路径是否自然？是否漏掉了关键交互环节（如注册、登录、导航、退出）？路径转换是否顺畅？",
    },
    {
        "role": "feature_completeness_reviewer",
        "display_name": "功能完整性审查",
        "prompt": "从功能完整性角度审查：主流程是否完整？分支流程和异常情况的兜底功能是否缺失？除了基本 CRUD 之外，是否缺少必要的辅助功能（如搜索、筛选、批量操作、导入导出）？",
    },
    {
        "role": "industry_benchmark_analyst",
        "display_name": "竞品/行业经验对标",
        "prompt": "从竞品和行业经验角度审查：同类产品通常有哪些默认功能？我们是否缺少了行业标准能力？有哪些竞品已经验证过的功能模式可以借鉴？",
    },
    {
        "role": "scenario_combiner",
        "display_name": "场景组合分析",
        "prompt": "从场景组合角度审查：用户可能同时有多个需求，现有功能组合能否覆盖？是否需要新增组合功能？不同用户角色的需求是否有冲突？",
    },
]


class DeliberationReviewService:
    """执行四维结构化功能审查。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def run_review(self, record: BrainstormRecord) -> DeliberationRound:
        """执行一轮四维审查，返回汇总结果。"""
        spec_text = self._render_feature_tree(record)

        round_result = DeliberationRound(
            round_id=f"dr-{uuid.uuid4().hex[:8]}",
            created_at=_now_iso(),
        )

        all_findings: list[DeliberationFinding] = []

        for dim in DIMENSIONS:
            findings = self._review_dimension(spec_text, dim)
            all_findings.extend(findings)

        round_result.findings = all_findings
        round_result.pm_summary = self._summarize_findings(all_findings)
        round_result.completed_at = _now_iso()

        record.deliberation_rounds.append(round_result)
        return round_result

    def _render_feature_tree(self, record: BrainstormRecord) -> str:
        """将 FeatureTree 渲染为审查用文本。"""
        lines = [f"# {record.project_name} 功能清单", ""]
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            lines.append(f"## {node.name} ({node.node_id})")
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
            lines.append("")
        return "\n".join(lines)

    def _review_dimension(self, spec_text: str, dimension: dict) -> list[DeliberationFinding]:
        """对单个维度执行审查。"""
        prompt = f"""{dimension['prompt']}

以下是当前产品的功能清单：

{spec_text}

请列出具体的审查发现。每个发现应包含：
- 影响的功能 ID
- 具体发现
- 严重程度（low | medium | high）
- 建议的变更

请以 JSON 数组返回：
[
  {{
    "finding_id": "f-1",
    "affected_feature_ids": ["fn-001"],
    "finding": "具体发现",
    "severity": "high",
    "suggested_change": "建议变更",
    "evidence": "证据或理由"
  }}
]

如果没有发现，返回空数组 []。"""

        content = self._call_llm(f"deliberation_{dimension['role']}", [{"role": "user", "content": prompt}])

        if not content:
            return []

        try:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n", 1)
                if len(lines) > 1:
                    content = lines[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)
            if not isinstance(data, list):
                data = data.get("findings", data.get("items", []))
            findings = []
            for f in data:
                if not isinstance(f, dict):
                    logger.warning("DeliberationReviewService: skip non-object finding: %r", f)
                    continue
                raw_id = f.get("finding_id") or f"f-{uuid.uuid4().hex[:6]}"
                findings.append(DeliberationFinding(
                    finding_id=f"{dimension['role']}:{raw_id}",
                    dimension=dimension["role"],
                    affected_feature_ids=f.get("affected_feature_ids", []),
                    finding=f.get("finding", ""),
                    severity=f.get("severity", "medium"),
                    suggested_change=f.get("suggested_change", ""),
                    evidence=f.get("evidence", ""),
                ))
            return findings
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning("DeliberationReviewService: %s parse error: %s", dimension["role"], e)
            return []

    def _summarize_findings(self, findings: list[DeliberationFinding]) -> str:
        """汇总所有审查发现。"""
        high = [f for f in findings if f.severity == "high"]
        medium = [f for f in findings if f.severity == "medium"]
        parts = []
        if high:
            parts.append(f"高优先级 ({len(high)} 条)：")
            for f in high:
                parts.append(f"  - {f.finding}")
        if medium:
            parts.append(f"中优先级 ({len(medium)} 条)：")
            for f in medium[:5]:  # 最多展示 5 条
                parts.append(f"  - {f.finding}")
        if not parts:
            return "审查未发现重大问题。"
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
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("DeliberationReviewService: LLM 响应结构异常")
        return None

    def apply_pm_decisions(self, record: BrainstormRecord) -> None:
        """PM 对审查发现做裁决，accepted 的建议回写功能树。"""
        if not record.deliberation_rounds:
            return

        latest = record.deliberation_rounds[-1]
        for finding in latest.findings:
            if finding.pm_decision == "accept" and finding.suggested_change:
                for fid in finding.affected_feature_ids:
                    node = record.feature_tree.get_node(fid)
                    if node:
                        if finding.finding not in node.review_feedback:
                            node.review_feedback.append(f"[deliberation] {finding.finding}")

    def make_decision(self, record: BrainstormRecord, finding_id: str, decision: str, reason: str = "") -> None:
        """对指定审查发现做 PM 裁决。"""
        allowed = {"accept", "reject", "defer"}
        if decision not in allowed:
            raise ValueError(f"Invalid deliberation decision: {decision}")
        for rnd in record.deliberation_rounds:
            for finding in rnd.findings:
                if finding.finding_id == finding_id:
                    finding.pm_decision = decision
                    finding.pm_reason = reason
                    return
        raise ValueError(f"Finding not found: {finding_id}")
