"""TechnicalRouteService — 基于已确认需求生成技术路线草案。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import BrainstormRecord, TechnicalRoute, _now_iso

logger = logging.getLogger(__name__)


class TechnicalRouteService:
    """根据冻结后的 PRD / Spec 生成技术路线草案。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def generate_route(self, record: BrainstormRecord) -> TechnicalRoute:
        """生成技术路线草案。"""
        spec_text = self._render_spec_text(record)

        prompt = f"""你是资深系统架构师。基于以下需求规格，生成技术路线草案。

{spec_text}

请从以下维度生成技术路线：
1. 架构摘要：整体架构描述（如前后端分离、微服务等）
2. 前端技术栈：推荐的前端框架和库
3. 后端技术栈：推荐的后端框架和语言
4. 数据存储：数据库和存储方案
5. 外部集成：需要对接的第三方服务
6. 非功能需求：性能、安全、可用性要求
7. 关键风险：技术风险点
8. 工具需求：需要哪些第三方工具/库/引擎支持（用于后续工具发现）

请以 JSON 返回：
{{
  "architecture_summary": "...",
  "frontend_stack": ["React", "TypeScript"],
  "backend_stack": ["Python", "FastAPI"],
  "data_storage": ["PostgreSQL"],
  "integrations": ["Stripe"],
  "non_functional_requirements": ["响应时间 < 200ms"],
  "key_risks": ["高并发场景"],
  "tool_needs": ["支付 SDK", "消息队列"]
}}"""

        content = self._call_llm("technical_route", [{"role": "user", "content": prompt}])

        route = TechnicalRoute(
            route_id=f"tr-{uuid.uuid4().hex[:8]}",
            architecture_summary="待分析",
            created_at=_now_iso(),
        )

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
                route = TechnicalRoute(
                    route_id=route.route_id,
                    architecture_summary=data.get("architecture_summary", "待分析"),
                    frontend_stack=data.get("frontend_stack", []),
                    backend_stack=data.get("backend_stack", []),
                    data_storage=data.get("data_storage", []),
                    integrations=data.get("integrations", []),
                    non_functional_requirements=data.get("non_functional_requirements", []),
                    key_risks=data.get("key_risks", []),
                    tool_needs=data.get("tool_needs", []),
                    created_at=_now_iso(),
                )
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("TechnicalRouteService: LLM parse error: %s", e)

        return route

    def _render_spec_text(self, record: BrainstormRecord) -> str:
        """将 BrainstormRecord 渲染为 Spec 文本供技术路线生成。"""
        lines = [f"# {record.project_name} 需求规格", ""]
        root = record.feature_tree.get_node("fn-root")
        if root:
            if root.vision:
                lines.extend(["## 产品愿景", f"- {root.vision}", ""])
            if root.target_users:
                lines.extend(["## 目标用户", f"- {', '.join(root.target_users)}", ""])
            if root.roles:
                lines.extend(["## 用户角色", f"- {', '.join(root.roles)}", ""])

        lines.extend(["## 功能列表", ""])
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            if node.status != "confirmed":
                continue
            lines.append(f"### {node.name} ({node.node_id})")
            if node.user_stories:
                for s in node.user_stories:
                    lines.append(f"- {s}")
            lines.append("")

        return "\n".join(lines)

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
                logger.warning("TechnicalRouteService: LLM 响应结构异常")
        return None
