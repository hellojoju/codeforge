"""CompactionAgent — LLM 驱动的任务压缩器，将完整执行日志压缩为结构化摘要。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ralph.config_manager import RalphConfigManager

logger = logging.getLogger(__name__)

COMPACTION_PROMPT = """你是一个任务摘要生成器。请根据任务的完整执行日志，生成一份结构化的 JSON 摘要。

要求：
1. 摘要必须客观、准确，不遗漏关键信息
2. 文件路径使用相对于项目根目录的路径
3. 如果某个字段没有信息，使用空数组/空字符串

返回严格的 JSON 格式（不要包含 markdown 代码块标记）：
{
  "summary": "一句话总结任务做了什么",
  "status": "accepted/failed/blocked",
  "key_decisions": ["决策1及理由", "决策2及理由"],
  "files_changed": [{"path": "相对路径", "change_type": "created/modified/deleted", "summary": "变更简述"}],
  "interfaces_modified": ["被修改的接口签名"],
  "risks_introduced": [{"risk": "风险描述", "severity": "high/medium/low", "suggested_action": "建议"}],
  "downstream_impact": "对下游任务/模块的影响",
  "evidence_refs": [".ralph/evidence/xxx"],
  "lessons_learned": ["经验教训"]
}"""


@dataclass
class CompactedSummary:
    work_id: str
    summary: str = ""
    status: str = ""
    key_decisions: list[str] = field(default_factory=list)
    files_changed: list[dict] = field(default_factory=list)
    interfaces_modified: list[str] = field(default_factory=list)
    risks_introduced: list[dict] = field(default_factory=list)
    downstream_impact: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    compressed_at: str = ""


class CompactionAgent:
    """使用 LLM 将 WorkUnit 完整日志压缩为结构化摘要。"""

    def __init__(self, config: RalphConfigManager | None = None):
        self._config = config

    def compact(self, work_id: str, full_log: str,
                status: str = "", executor_summary: str = "") -> CompactedSummary:
        """将完整日志压缩为结构化摘要。"""
        # 构建输入
        input_text = self._build_input(work_id, status, executor_summary, full_log)

        # 尝试 LLM 压缩
        llm_result = self._call_llm(input_text)
        if llm_result:
            return self._parse_result(work_id, llm_result)

        # LLM 不可用时降级为规则压缩
        logger.info("CompactionAgent: LLM 不可用，使用规则压缩")
        return self._fallback_compact(work_id, full_log, status, executor_summary)

    def _build_input(self, work_id: str, status: str,
                     executor_summary: str, full_log: str) -> str:
        parts = [f"Work ID: {work_id}"]
        if status:
            parts.append(f"终态: {status}")
        if executor_summary:
            parts.append(f"执行摘要: {executor_summary}")
        # 截断过长日志到 ~8000 字符，保留关键部分
        truncated = full_log[:8000] if len(full_log) > 8000 else full_log
        parts.append(f"执行日志:\n{truncated}")
        return "\n\n".join(parts)

    def _call_llm(self, input_text: str) -> dict | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("compaction", "summarize")
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        messages = [
            {"role": "system", "content": COMPACTION_PROMPT},
            {"role": "user", "content": input_text},
        ]
        result = self._config.proxy_request(
            provider["provider_id"],
            "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        )
        if result.get("ok"):
            try:
                raw = result["data"]["choices"][0]["message"]["content"]
                return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                logger.warning("CompactionAgent: LLM 响应解析失败")
        return None

    def _parse_result(self, work_id: str, data: dict) -> CompactedSummary:
        from datetime import UTC, datetime

        return CompactedSummary(
            work_id=work_id,
            summary=data.get("summary", ""),
            status=data.get("status", ""),
            key_decisions=data.get("key_decisions", []),
            files_changed=data.get("files_changed", []),
            interfaces_modified=data.get("interfaces_modified", []),
            risks_introduced=data.get("risks_introduced", []),
            downstream_impact=data.get("downstream_impact", ""),
            evidence_refs=data.get("evidence_refs", []),
            lessons_learned=data.get("lessons_learned", []),
            compressed_at=datetime.now(UTC).isoformat(),
        )

    def _fallback_compact(self, work_id: str, full_log: str,
                          status: str, executor_summary: str) -> CompactedSummary:
        """规则降级压缩 — 从日志中提取关键信息。"""
        from datetime import UTC, datetime

        # 检测文件变更
        files: list[dict] = []
        for line in full_log.split("\n"):
            for marker in ("Created:", "Modified:", "Deleted:", "创建:", "修改:", "删除:"):
                if marker in line:
                    path = line.split(marker, 1)[-1].strip().rstrip(".")
                    if path and len(path) < 200:
                        change_type = {
                            "Created:": "created", "创建:": "created",
                            "Modified:": "modified", "修改:": "modified",
                            "Deleted:": "deleted", "删除:": "deleted",
                        }.get(marker, "modified")
                        files.append({"path": path, "change_type": change_type, "summary": ""})

        # 检测错误
        errors = []
        for line in full_log.split("\n"):
            if any(kw in line.lower() for kw in ("error", "fail", "exception", "错误", "失败")):
                errors.append(line.strip()[:200])
                if len(errors) >= 5:
                    break

        return CompactedSummary(
            work_id=work_id,
            summary=executor_summary or f"任务 {work_id} 已完成，状态: {status}",
            status=status,
            key_decisions=[],
            files_changed=files[:20],
            interfaces_modified=[],
            risks_introduced=[{"risk": e, "severity": "medium", "suggested_action": "需要人工审查"} for e in errors[:3]],
            downstream_impact="",
            evidence_refs=[],
            lessons_learned=[],
            compressed_at=datetime.now(UTC).isoformat(),
        )
