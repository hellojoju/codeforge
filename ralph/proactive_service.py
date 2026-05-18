"""ProactiveAnalysisService — 系统主动分析模糊需求，生成假设草案。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, ProactiveAnalysis, ProactiveAnalysisItem,
    SourceRef, _now_iso,
)

logger = logging.getLogger(__name__)


class ProactiveAnalysisService:
    """根据用户模糊需求，生成结构化的产品假设草案。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def analyze(self, record: BrainstormRecord) -> ProactiveAnalysis:
        """基于用户初始需求，生成假设草案。"""
        prompt = self._build_prompt(record)
        content = self._call_llm("proactive_analysis", [{"role": "user", "content": prompt}])

        analysis = ProactiveAnalysis(
            analysis_id=f"pa-{uuid.uuid4().hex[:8]}",
            created_at=_now_iso(),
        )

        if content:
            items = self._parse_items(content)
            analysis.items = items
            analysis.summary = self._build_summary(items)

        record.proactive_analysis = analysis
        return analysis

    def _build_prompt(self, record: BrainstormRecord) -> str:
        user_message = record.user_message or ""
        project_name = record.project_name or ""

        return f"""你是资深产品经理和系统架构师。用户提出了一个模糊需求，请你从大方向上主动分析这个产品应该怎么做。

项目名称：{project_name}
用户需求：{user_message}

请从以下维度分析：
1. 产品类型判断（这是什么类型的产品）
2. 目标用户猜测（谁会使用）
3. 核心场景推测（主要使用场景）
4. 关键功能模块推测（需要哪些核心功能）
5. 可能的技术方向（推荐的技术栈）
6. 主要风险点（潜在风险和挑战）
7. 需要用户优先确认的问题（3-5 个关键问题）

请以 JSON 返回，格式如下：
{{
  "items": [
    {{
      "item_id": "pa-1",
      "category": "product_type|target_user|core_scenario|module|tech_direction|risk|question",
      "content": "具体分析内容",
      "confidence": 0.7
    }}
  ]
}}

注意：
- 每个维度至少有一个 item
- confidence 范围 0.1-1.0，表示你对该判断的确定程度
- 要具体，不要泛泛而谈"""

    def _parse_items(self, content: str) -> list[ProactiveAnalysisItem]:
        try:
            content = content.strip()
            # Handle markdown code fences
            if content.startswith("```"):
                lines = content.split("\n", 1)
                if len(lines) > 1:
                    content = lines[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)
            # Support both {"items": [...]} and direct array
            if isinstance(data, list):
                items_data = data
            elif isinstance(data, dict):
                items_data = data.get("items", [])
            else:
                return []
            items = []
            for item in items_data:
                items.append(ProactiveAnalysisItem(
                    item_id=item.get("item_id", f"pa-{uuid.uuid4().hex[:6]}"),
                    category=item.get("category", "module"),
                    content=item.get("content", ""),
                    confidence=float(item.get("confidence", 0.5)),
                ))
            return items
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning("ProactiveAnalysisService: LLM 返回 parse error: %s", e)
            return []

    def _build_summary(self, items: list[ProactiveAnalysisItem]) -> str:
        modules = [i for i in items if i.category == "module"]
        risks = [i for i in items if i.category == "risk"]
        questions = [i for i in items if i.category == "question"]
        parts = []
        if modules:
            parts.append(f"建议的核心功能模块：{', '.join(i.content for i in modules)}")
        if risks:
            parts.append(f"主要风险：{', '.join(i.content for i in risks)}")
        if questions:
            parts.append(f"需要优先确认：{', '.join(i.content for i in questions)}")
        return "\n".join(parts) if parts else "分析完成，请查看详细条目。"

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
                logger.warning("ProactiveAnalysisService: LLM 响应结构异常")
        return None
