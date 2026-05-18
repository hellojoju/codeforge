"""ToolDiscoveryService — 基于技术路线进行第三方工具发现与评估。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.search_provider import SearchProviderManager
from ralph.schema.brainstorm_record import (
    EvidenceRef, ToolCandidate, ToolDiscoveryResult, ToolEvaluation, _now_iso,
)

logger = logging.getLogger(__name__)


class ToolDiscoveryService:
    """根据技术路线中的工具需求，搜索、评估、推荐第三方工具。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager
        self._search = SearchProviderManager(config_manager)

    def discover(self, tool_needs: list[str]) -> list[ToolDiscoveryResult]:
        """对每个工具需求执行发现流程。"""
        results: list[ToolDiscoveryResult] = []
        for need in tool_needs:
            result = self._discover_for_need(need)
            results.append(result)
        return results

    def _discover_for_need(self, tool_need: str) -> ToolDiscoveryResult:
        """对单个工具需求执行搜索和评估。"""
        result = ToolDiscoveryResult(
            discovery_id=f"td-{uuid.uuid4().hex[:8]}",
            tool_need=tool_need,
            created_at=_now_iso(),
        )

        # Step 1: 生成搜索 query
        queries = self._generate_queries(tool_need)
        result.queries = queries

        # Step 2: 对每个 query 搜索候选
        for query in queries:
            candidates = self._search_candidate(query)
            for c in candidates:
                if c.candidate_id not in {x.candidate_id for x in result.candidates}:
                    result.candidates.append(c)

        # Step 3: 评估候选（最多评估前 5 个）
        for candidate in result.candidates[:5]:
            evaluation = self._evaluate_candidate(candidate, tool_need)
            result.evaluations.append(evaluation)

        # Step 4: 选择推荐
        adoptable = [e for e in result.evaluations if e.recommendation == "adopt"]
        if adoptable:
            result.selected_candidate_ids = [adoptable[0].candidate_id]

        return result

    def _generate_queries(self, tool_need: str) -> list[str]:
        """基于工具需求生成搜索 query。"""
        if self._config is None:
            return [f"{tool_need} github open source", f"best {tool_need} library python"]

        prompt = f"""用户需要一个{tool_need}的第三方工具/库。
请生成 3 个搜索 query，用于在 GitHub 和互联网上搜索相关工具。

要求：
- query 要具体，包含技术关键词
- 至少一个 query 包含 "github" 关键词

以 JSON 数组返回: ["query1", "query2", "query3"]"""

        content = self._call_llm("tool_discovery_queries", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    if len(lines) > 1:
                        content = lines[1].rsplit("```", 1)[0].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
                queries = json.loads(content)
                if isinstance(queries, list) and queries:
                    return queries[:3]
            except (json.JSONDecodeError, TypeError):
                logger.warning("ToolDiscoveryService: query generation parse error")

        return [f"{tool_need} github open source", f"best {tool_need} library python"]

    def _search_candidate(self, query: str) -> list[ToolCandidate]:
        """搜索候选工具。"""
        provider_results = self._search.search(query, limit=5)
        if provider_results:
            candidates: list[ToolCandidate] = []
            for result in provider_results:
                candidates.append(ToolCandidate(
                    candidate_id=f"tc-{uuid.uuid4().hex[:6]}",
                    name=result.title,
                    source=result.source_type,
                    url=result.url,
                    description=result.snippet,
                    evidence_urls=[result.url] if result.url else [],
                    evidence_snapshot=result.snippet,
                    evidence_refs=[result.evidence_ref()],
                ))
            return candidates

        if self._config is None:
            return []

        prompt = f"""基于搜索 query "{query}"，返回 2-3 个最相关的开源工具/库。

请以 JSON 数组返回：
[
  {{
    "candidate_id": "tc-1",
    "name": "工具名称",
    "source": "github",
    "url": "https://github.com/...",
    "description": "简短描述",
    "license": "MIT",
    "stars": 10000,
    "last_updated": "2026-01-15",
    "package_name": "package-name"
  }}
]"""

        content = self._call_llm("tool_discovery_search", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    if len(lines) > 1:
                        content = lines[1].rsplit("```", 1)[0].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                if isinstance(data, dict):
                    data = data.get("candidates", data.get("results", []))
                if not isinstance(data, list):
                    return []
                candidates = []
                for c in data:
                    if not isinstance(c, dict):
                        logger.warning("ToolDiscoveryService: skip non-object candidate: %r", c)
                        continue
                    evidence_url = c.get("url", "")
                    evidence_snapshot = c.get("evidence_snapshot", c.get("description", ""))
                    candidates.append(ToolCandidate(
                        candidate_id=c.get("candidate_id", f"tc-{uuid.uuid4().hex[:6]}"),
                        name=c.get("name", ""),
                        source=c.get("source", "web"),
                        url=c.get("url", ""),
                        description=c.get("description", ""),
                        license=c.get("license", ""),
                        stars=c.get("stars"),
                        last_updated=c.get("last_updated", ""),
                        package_name=c.get("package_name", ""),
                        evidence_urls=c.get("evidence_urls", [evidence_url] if evidence_url else []),
                        evidence_snapshot=evidence_snapshot,
                        evidence_refs=[
                            EvidenceRef(
                                source_type=c.get("source", "llm_inference"),
                                title=c.get("name", "工具候选"),
                                url=evidence_url,
                                quote_or_summary=evidence_snapshot,
                                captured_at=_now_iso(),
                                confidence=float(c.get("confidence", 0.6)),
                            )
                        ] if evidence_snapshot or evidence_url else [],
                    ))
                return candidates
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("ToolDiscoveryService: search parse error: %s", e)

        return []

    def _evaluate_candidate(self, candidate: ToolCandidate, tool_need: str) -> ToolEvaluation:
        """评估候选工具。"""
        if self._config is None:
            return ToolEvaluation(
                candidate_id=candidate.candidate_id,
                functional_fit=3, maintenance_health=3, license_fit=3,
                stack_compatibility=3, security_risk="unknown",
                integration_cost="medium", summary="无法评估（LLM 不可用）",
                recommendation="compare",
            )

        prompt = f"""请评估以下工具是否满足需求：

需求：{tool_need}
工具：{candidate.name}
描述：{candidate.description}
许可证：{candidate.license}
Stars：{candidate.stars or '未知'}
最近更新：{candidate.last_updated or '未知'}

请从以下维度评分：
- functional_fit (1-5)：功能匹配度
- maintenance_health (1-5)：维护健康度
- license_fit (1-5)：许可证兼容性
- stack_compatibility (1-5)：技术栈兼容性
- security_risk (low/medium/high/unknown)：安全风险
- integration_cost (low/medium/high)：集成成本

以 JSON 返回：
{{
  "functional_fit": 4,
  "maintenance_health": 4,
  "license_fit": 5,
  "stack_compatibility": 4,
  "security_risk": "low",
  "integration_cost": "low",
  "summary": "评估摘要",
  "recommendation": "adopt|compare|avoid"
}}"""

        content = self._call_llm("tool_discovery_evaluation", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    if len(lines) > 1:
                        content = lines[1].rsplit("```", 1)[0].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                return ToolEvaluation(
                    candidate_id=candidate.candidate_id,
                    functional_fit=int(data.get("functional_fit", 3)),
                    maintenance_health=int(data.get("maintenance_health", 3)),
                    license_fit=int(data.get("license_fit", 3)),
                    stack_compatibility=int(data.get("stack_compatibility", 3)),
                    security_risk=data.get("security_risk", "unknown"),
                    integration_cost=data.get("integration_cost", "medium"),
                    summary=data.get("summary", ""),
                    recommendation=data.get("recommendation", "compare"),
                )
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("ToolDiscoveryService: evaluation parse error: %s", e)

        return ToolEvaluation(
            candidate_id=candidate.candidate_id,
            functional_fit=3, maintenance_health=3, license_fit=3,
            stack_compatibility=3, security_risk="unknown",
            integration_cost="medium", summary="评估失败",
            recommendation="compare",
        )

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
                "temperature": 0.5,
                "max_tokens": 1500,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("ToolDiscoveryService: LLM 响应结构异常")
        return None
