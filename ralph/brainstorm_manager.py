"""BrainstormManager — 多轮需求共创管理器，支持 LLM 增强追问和事实提取。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, ConfirmedFact, OpenAssumption, UserPath, _now_iso,
    dict_to_brainstorm,
)

logger = logging.getLogger(__name__)


class BrainstormManager:
    """多轮需求共创管理器。每轮对话产出 BrainstormRecord，持久化到 .ralph/brainstorm/"""

    TOPICS_TO_COVER = [
        "目标用户", "用户角色", "核心功能", "暂不做的功能",
        "成功路径", "失败路径", "边界状态", "验收标准",
        "数据模型概要", "权限规则",
    ]

    def __init__(self, ralph_dir: Path, config_manager: Any = None) -> None:
        self._dir = ralph_dir / "brainstorm"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config = config_manager

    # ---- 会话生命周期 ---------------------------------------------------

    def start_session(self, project_name: str, user_message: str) -> BrainstormRecord:
        record = BrainstormRecord(
            record_id=f"bs-{_now_iso().replace(':', '-')}",
            project_name=project_name,
            round_number=1,
            user_message=user_message,
        )
        self._save(record)
        return record

    def load(self, record_id: str) -> BrainstormRecord | None:
        path = self._dir / f"{record_id}.json"
        if not path.is_file():
            return None
        return dict_to_brainstorm(json.loads(path.read_text()))

    def list_sessions(self) -> list[dict]:
        records: list[dict] = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                record = dict_to_brainstorm(data)
                records.append({
                    "record_id": data.get("record_id", f.stem),
                    "project_name": data.get("project_name", ""),
                    "round_number": data.get("round_number", 0),
                    "completeness": record.completeness_score(),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return records

    # ---- 问题生成 -------------------------------------------------------

    def generate_questions(self, record: BrainstormRecord, use_llm: bool = False) -> list[str]:
        """生成下一轮追问。use_llm=True 且 config_manager 可用时走 LLM 增强路径。"""
        if use_llm and self._config is not None:
            llm_questions = self._enrich_questions_with_llm(record)
            if llm_questions:
                return llm_questions
        return self._static_questions(record)

    def _static_questions(self, record: BrainstormRecord) -> list[str]:
        """静态模板追问（不依赖 LLM 的 fallback）。"""
        questions: list[str] = []
        covered = {f.topic for f in record.confirmed_facts}

        for topic in self.TOPICS_TO_COVER:
            if topic not in covered:
                questions.append(self._question_for_topic(topic))

        if not questions:
            for assumption in record.open_assumptions:
                if assumption.status == "open":
                    questions.append(f"关于「{assumption.question}」，你的判断是？")

        return questions[:5]

    def _enrich_questions_with_llm(self, record: BrainstormRecord) -> list[str]:
        """用 LLM 根据已确认事实/未确认假设生成上下文感知追问。"""
        context = self._build_question_context(record)
        uncovered = [t for t in self.TOPICS_TO_COVER
                     if t not in {f.topic for f in record.confirmed_facts}]

        prompt = (
            "你是资深需求分析师。根据以下需求共创对话，生成 3-5 个有针对性的下一轮追问。\n"
            "要求：\n"
            "- 优先覆盖尚未明确的主题\n"
            "- 问题要具体，不要泛泛而问\n"
            "- 每个问题应引导用户给出可验证的回答\n\n"
            f"{context}\n\n"
            f"尚未覆盖的主题: {', '.join(uncovered) if uncovered else '已基本覆盖'}\n\n"
            '请严格以 JSON 数组返回: ["问题1", "问题2", ...]'
        )

        content = self._call_llm(
            task_type="brainstorm",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        if content is None:
            return []

        try:
            questions = json.loads(content)
            if isinstance(questions, list):
                return [str(q) for q in questions[:5]]
        except (json.JSONDecodeError, TypeError):
            logger.warning("BrainstormManager: LLM 返回的问题 JSON 解析失败")

        return []

    # ---- 回复处理 -------------------------------------------------------

    def process_response(
        self,
        record: BrainstormRecord,
        user_response: str,
        extracted_facts: list[dict] | None = None,
    ) -> BrainstormRecord:
        """处理用户回复，提取事实/假设/用户路径。"""
        record.round_number += 1
        record.user_message = user_response

        if extracted_facts:
            self._apply_extracted_facts(record, extracted_facts, user_response)
        elif self._config is not None:
            auto_facts = self._auto_extract_facts(record, user_response)
            if auto_facts:
                self._apply_extracted_facts(record, auto_facts, user_response)

        record.system_questions = self._static_questions(record)
        self._save(record)
        return record

    def _apply_extracted_facts(
        self, record: BrainstormRecord, facts: list[dict], source: str,
    ) -> None:
        for item in facts:
            item_type = item.get("type", "")
            if item_type == "confirmed":
                record.confirmed_facts.append(ConfirmedFact(
                    topic=item.get("topic", ""),
                    fact=item.get("fact", ""),
                    source_quote=item.get("source_quote", source),
                ))
            elif item_type == "assumption":
                record.open_assumptions.append(OpenAssumption(
                    question=item.get("question", ""),
                    context=item.get("context", ""),
                ))
            elif item_type == "user_path":
                record.user_paths.append(UserPath(
                    name=item.get("name", ""),
                    steps=item.get("steps", []),
                    edge_cases=item.get("edge_cases", []),
                ))

    def _auto_extract_facts(
        self, record: BrainstormRecord, user_response: str,
    ) -> list[dict]:
        """用 LLM 自动从用户回复中提取结构化事实。"""
        facts_text = "\n".join(
            f"- [{f.topic}] {f.fact}" for f in record.confirmed_facts[-5:]
        )
        prompt = (
            "从以下用户需求回复中提取结构化信息。\n\n"
            f"项目: {record.project_name}\n"
            f"已确认事实（最近）:\n{facts_text or '(无)'}\n"
            f"用户回复: {user_response}\n\n"
            "请以 JSON 数组返回: [{\"type\":\"confirmed\"|\"assumption\"|\"user_path\", ...}]\n"
            "- confirmed: {\"type\":\"confirmed\",\"topic\":\"主题\",\"fact\":\"事实\",\"source_quote\":\"原文\"}\n"
            "- assumption: {\"type\":\"assumption\",\"question\":\"问题\",\"context\":\"为何重要\"}\n"
            "- user_path: {\"type\":\"user_path\",\"name\":\"路径名\",\"steps\":[\"步骤\"],\"edge_cases\":[\"边界\"]}"
        )

        content = self._call_llm(
            task_type="brainstorm",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1000,
        )
        if content is None:
            return []

        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, TypeError):
            logger.warning("BrainstormManager: LLM 事实提取 JSON 解析失败")

        return []

    # ---- 查询 / 状态 ----------------------------------------------------

    def is_complete(self, record: BrainstormRecord) -> bool:
        return (record.completeness_score() >= 0.8
                and len(record.open_assumptions) == 0)

    def get_summary(self, record: BrainstormRecord) -> dict:
        return {
            "project_name": record.project_name,
            "total_rounds": record.round_number,
            "completeness": record.completeness_score(),
            "confirmed_facts": [
                {"topic": f.topic, "fact": f.fact} for f in record.confirmed_facts
            ],
            "open_assumptions": [
                {"question": a.question, "status": a.status}
                for a in record.open_assumptions
            ],
            "user_paths": [
                {"name": p.name, "steps": p.steps, "edge_cases": p.edge_cases}
                for p in record.user_paths
            ],
        }

    # ---- LLM 调用 -------------------------------------------------------

    def _call_llm(
        self,
        task_type: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str | None:
        """统一 LLM 调用入口：resolve provider → proxy_request → extract content。"""
        if self._config is None:
            return None

        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}

        if not provider.get("provider_id"):
            return None

        result = self._config.proxy_request(
            provider["provider_id"],
            "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        if result.get("ok"):
            try:
                return result["data"]["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                logger.warning("BrainstormManager: LLM 响应结构异常")

        return None

    # ---- 内部 -----------------------------------------------------------

    def _save(self, record: BrainstormRecord) -> None:
        from dataclasses import asdict
        path = self._dir / f"{record.record_id}.json"
        path.write_text(json.dumps(
            asdict(record),
            indent=2, ensure_ascii=False,
        ))

    def _build_question_context(self, record: BrainstormRecord) -> str:
        facts_text = "\n".join(
            f"- [{f.topic}] {f.fact}" for f in record.confirmed_facts
        )
        assumptions_text = "\n".join(
            f"- {a.question} ({a.status})" for a in record.open_assumptions
        )
        paths_text = "\n".join(
            f"- {p.name}: {' → '.join(p.steps)}" for p in record.user_paths
        )
        return (
            f"项目: {record.project_name}\n"
            f"轮次: 第{record.round_number}轮\n"
            f"用户最新输入: {record.user_message}\n\n"
            f"已确认事实:\n{facts_text or '(暂无)'}\n\n"
            f"待确认假设:\n{assumptions_text or '(暂无)'}\n\n"
            f"用户路径:\n{paths_text or '(暂无)'}"
        )

    @staticmethod
    def _question_for_topic(topic: str) -> str:
        questions = {
            "目标用户": "这个产品给谁用？请描述目标用户画像。",
            "用户角色": "有哪些不同的用户角色？每个角色能做什么？",
            "核心功能": "第一版必须有哪些功能？按重要性排序。",
            "暂不做的功能": "有哪些功能明确不做（至少第一版不做）？",
            "成功路径": "用户最常见的成功使用流程是什么？",
            "失败路径": "当用户操作失败时，系统应该如何响应？",
            "边界状态": "极端或异常状态下系统应该如何表现？",
            "验收标准": "你怎么判断这个产品'真的可以用了'？",
            "数据模型概要": "系统需要存储哪些核心数据？",
            "权限规则": "有哪些权限控制需求？",
        }
        return questions.get(topic, f"请详细说明「{topic}」方面的需求。")
