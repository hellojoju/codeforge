"""BrainstormManager — 多轮需求共创管理器，支持 LLM 增强追问和事实提取。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, ConfirmedFact, FeatureNode, FeatureTree,
    OpenAssumption, QuestionTask, UserPath, _now_iso, brainstorm_to_dict, dict_to_brainstorm,
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
        """V2: 创建 session，初始化 product 根节点，进入 Phase 1"""
        record_id = f"bs-{_now_iso().replace(':', '-')}"

        # 创建 product 根节点
        root_node = FeatureNode(
            node_id="fn-root",
            name=project_name,
            level="product",
            status="exploring",
            depth=0,
        )

        feature_tree = FeatureTree(
            root_id="fn-root",
            nodes={"fn-root": root_node},
            current_exploring_id="fn-root",
            question_plan=[],
            current_question_id=None,
        )

        record = BrainstormRecord(
            record_id=record_id,
            project_name=project_name,
            user_message=user_message,
            current_phase=BrainstormPhase.PRODUCT_DEF,
            feature_tree=feature_tree,
            round_number=1,
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
                    "current_phase": data.get("current_phase", "product_def"),
                    "active_node_name": self._get_active_node_name(data),
                    "completed_features": self._count_confirmed_features(data),
                })
            except Exception:
                continue
        return records

    def resume_session(self, record_id: str) -> BrainstormRecord | None:
        """恢复 session，恢复 phase + active_node"""
        return self.load(record_id)

    def _get_active_node_name(self, data: dict) -> str:
        """从数据中获取当前活跃节点名称"""
        ft = data.get("feature_tree", {})
        exploring_id = ft.get("current_exploring_id")
        if exploring_id and exploring_id in ft.get("nodes", {}):
            return ft["nodes"][exploring_id].get("name", "")
        return ""

    def _count_confirmed_features(self, data: dict) -> int:
        """统计已确认的功能节点数"""
        ft = data.get("feature_tree", {})
        nodes = ft.get("nodes", {})
        return sum(1 for n in nodes.values() if n.get("status") == "confirmed")

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

    # ---- Phase 1: 产品定义 ---------------------------------------------------

    def explore_product(self, record: BrainstormRecord) -> list[str]:
        """Phase 1: 生成产品定义追问"""
        root = record.feature_tree.get_node("fn-root")
        if not root:
            return ["请描述你的产品愿景"]

        if not record.feature_tree.question_plan:
            self._build_product_question_plan(record)

        return self._generate_questions_from_plan(record)

    def _build_product_question_plan(self, record: BrainstormRecord) -> None:
        """为 Phase 1 构建追问计划"""
        root = record.feature_tree.get_node("fn-root")
        if not root:
            return

        product_fields = [
            ("vision", "产品愿景", "这个产品要解决什么核心问题？"),
            ("target_users", "目标用户", "谁会使用这个产品？"),
            ("roles", "用户角色", "有几种用户角色？"),
            ("success_criteria", "成功标准", "怎么判断这个产品是成功的？"),
            ("mvp_scope", "MVP 范围", "第一版必须包含哪些功能？"),
            ("out_of_scope", "明确不做", "第一版明确不包含什么？"),
        ]

        for field_name, label, reason in product_fields:
            existing = getattr(root, field_name)
            if existing and (
                isinstance(existing, str) and existing.strip()
                or isinstance(existing, list) and existing
            ):
                continue

            task = QuestionTask(
                question_id=f"qt-product-{field_name}",
                node_id="fn-root",
                field_name=field_name,
                question="",
                reason=reason,
                expected_answer_shape="请用 1-3 句话描述",
                status="pending",
            )
            record.feature_tree.question_plan.append(task)

    def _generate_questions_from_plan(self, record: BrainstormRecord) -> list[str]:
        """从 question_plan 中选择 pending 任务，生成问题"""
        pending = [t for t in record.feature_tree.question_plan if t.status == "pending"]
        if not pending:
            return []

        task = pending[0]
        record.feature_tree.current_question_id = task.question_id
        task.status = "asked"

        question = self._render_question_with_llm(record, task)
        if question:
            return [question]

        return [task.reason]

    def _render_question_with_llm(self, record: BrainstormRecord, task: QuestionTask) -> str | None:
        """用 LLM 将 QuestionTask 渲染为用户友好的问题"""
        if self._config is None:
            return None

        root = record.feature_tree.get_node("fn-root")
        source_refs = root.source_refs if root else []

        prompt = f"""你是资深产品需求分析师。
项目：{record.project_name}
当前节点：{root.name if root else '产品定义'}
字段：{task.field_name}
追问原因：{task.reason}
期望回答形态：{task.expected_answer_shape}
相关用户原话：{[r.quote for r in source_refs]}

请将以上信息改写为 1-2 个具体的追问。要求：
1. 不要泛泛而问，必须点明当前产品。
2. 引用用户的原话（如果有）。
3. 如果用户可能不确定，提供"可以先标记为不确定"的出口。
4. 只返回 JSON 数组格式的问题列表。"""

        try:
            result = self._call_llm("product_question", [{"role": "user", "content": prompt}])
            if result:
                questions = json.loads(result)
                if isinstance(questions, list) and questions:
                    return questions[0]
        except Exception:
            pass
        return None

    def _process_product_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Phase 1 用户回复"""
        from datetime import UTC, datetime

        task_id = record.feature_tree.current_question_id
        task = next(
            (t for t in record.feature_tree.question_plan if t.question_id == task_id), None
        )

        root = record.feature_tree.get_node("fn-root")
        if not root:
            return

        facts = self._auto_extract_facts(record, user_response)

        if facts:
            self._apply_extracted_facts_to_node(record, root, facts)

        if task:
            task.status = "answered"
            task.answered_at = datetime.now(UTC).isoformat()

        root.conversation_turns.append({
            "question": task.reason if task else "",
            "response": user_response,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        record.feature_tree.question_plan = []
        self._build_product_question_plan(record)

    def _check_product_complete(self, root: FeatureNode) -> bool:
        """检查产品定义是否完整"""
        required = [
            "vision", "target_users", "roles", "success_criteria",
            "mvp_scope", "out_of_scope",
        ]
        for fld in required:
            value = getattr(root, fld, None)
            if not value or (
                isinstance(value, str) and not value.strip()
            ) or (
                isinstance(value, list) and not value
            ):
                return False
        return True

    def _apply_extracted_facts_to_node(
        self, record: BrainstormRecord, node: FeatureNode, facts: dict,
    ) -> None:
        """将 LLM 提取的事实写入节点"""
        for field_name in [
            "user_stories", "acceptance_criteria", "success_path", "failure_path",
            "edge_cases", "data_requirements", "dependencies", "business_rules",
            "permission_rules", "vision", "target_users", "roles", "success_criteria",
            "mvp_scope", "out_of_scope", "assumptions",
        ]:
            if field_name in facts and facts[field_name]:
                value = facts[field_name]
                existing = getattr(node, field_name)
                if isinstance(existing, list) and isinstance(value, list):
                    for item in value:
                        if item not in existing:
                            existing.append(item)
                    setattr(node, field_name, existing)
                elif isinstance(existing, str) and isinstance(value, str):
                    if not existing:
                        setattr(node, field_name, value)

        if "explicit_checks" in facts:
            from ralph.schema.brainstorm_record import ExplicitCheck
            for check in facts["explicit_checks"]:
                ec = ExplicitCheck(
                    field_name=check.get("field_name", ""),
                    state=check.get("state", "unknown"),
                    reason=check.get("reason", ""),
                )
                node.explicit_checks[ec.field_name] = ec

    # ---- Phase 2: 功能分解 ---------------------------------------------------

    def get_active_node(self, record: BrainstormRecord) -> FeatureNode | None:
        """返回当前正在探索的节点"""
        return record.feature_tree.get_node(record.feature_tree.current_exploring_id)

    def decompose_node(self, record: BrainstormRecord, children_names: list[str]) -> list[FeatureNode]:
        """将当前节点拆分为子功能"""
        active = self.get_active_node(record)
        if not active:
            return []

        children: list[FeatureNode] = []
        for name in children_names:
            child = FeatureNode(
                node_id=f"fn-{len(record.feature_tree.nodes):03d}",
                name=name,
                level="function" if active.level == "product" else "sub_function",
                status="exploring",
                parent_id=active.node_id,
            )
            record.feature_tree.add_child(active.node_id, child)
            children.append(child)

        active.status = "exploring"
        return children

    def build_question_plan(self, record: BrainstormRecord, node: FeatureNode) -> list[QuestionTask]:
        """基于缺失项生成追问计划"""
        tasks: list[QuestionTask] = []
        missing = self._get_missing_items(node)

        field_priority = [
            ("user_stories", "用户故事", "As a X, I want Y, so that Z"),
            ("mvp_scope", "MVP 范围", "第一版必须做什么"),
            ("success_path", "成功路径", "操作步骤"),
            ("failure_path", "失败路径", "失败场景和系统响应"),
            ("edge_cases", "边界场景", "极端情况下的处理"),
            ("data_requirements", "数据需求", "需要存储的数据"),
            ("permission_rules", "权限规则", "谁可以做什么"),
            ("business_rules", "业务规则", "业务约束"),
            ("dependencies", "依赖关系", "依赖其他什么功能"),
            ("acceptance_criteria", "验收标准", "Given/When/Then"),
        ]

        for field_name, label, shape in field_priority:
            if field_name not in missing:
                continue
            tasks.append(QuestionTask(
                question_id=f"qt-{node.node_id}-{field_name}",
                node_id=node.node_id,
                field_name=field_name,
                question="",
                reason=f"需要明确{label}，否则无法确认该功能的需求",
                expected_answer_shape=shape,
                status="pending",
            ))

        record.feature_tree.question_plan.extend(tasks)
        return tasks

    def check_granularity(self, record: BrainstormRecord) -> list[str]:
        """检查粒度门控，返回缺失项"""
        active = self.get_active_node(record)
        if not active:
            return ["no_active_node"]
        return self._get_missing_items(active)

    def _get_missing_items(self, node: FeatureNode) -> list[str]:
        """返回节点未满足的字段"""
        missing: list[str] = []
        required = [
            ("user_stories", lambda v: isinstance(v, list) and len(v) >= 1),
            ("acceptance_criteria", lambda v: isinstance(v, list) and len(v) >= 1),
            ("success_path", lambda v: isinstance(v, list) and len(v) >= 1),
            ("failure_path", lambda v: isinstance(v, list) and len(v) >= 1),
            ("edge_cases", lambda v: isinstance(v, list) and len(v) >= 1),
            ("data_requirements", lambda v: isinstance(v, list) and len(v) >= 1),
        ]

        for field_name, check in required:
            value = getattr(node, field_name, None)
            if not check(value):
                missing.append(field_name)

        # 依赖、业务规则、权限规则需要显式评估记录
        if "dependencies" not in node.explicit_checks:
            missing.append("dependencies (未评估)")
        if "business_rules" not in node.explicit_checks:
            missing.append("business_rules (未评估)")
        if "permission_rules" not in node.explicit_checks:
            missing.append("permission_rules (未评估)")

        return missing

    def confirm_node(self, record: BrainstormRecord) -> bool:
        """标记当前节点 confirmed，推进下一节点"""
        active = self.get_active_node(record)
        if not active:
            return False

        missing = self._get_missing_items(active)
        if missing:
            return False

        active.status = "confirmed"
        active.confirmed_at = _now_iso()

        next_node = self.select_next_node(record)
        return next_node is not None or record.feature_tree.all_confirmed()

    def select_next_node(self, record: BrainstormRecord) -> FeatureNode | None:
        """DFS 策略选下一个待探索节点"""
        tree = record.feature_tree

        active = tree.get_node(tree.current_exploring_id)
        if active:
            # 优先：当前节点的未探索子节点
            for child_id in active.children:
                child = tree.get_node(child_id)
                if child and child.status in ("exploring", "pending"):
                    tree.current_exploring_id = child_id
                    tree.recursion_stack.append(child_id)
                    return child

            # 同级下一个
            if active.parent_id:
                parent = tree.get_node(active.parent_id)
                if parent:
                    idx = parent.children.index(active.node_id)
                    for sibling_id in parent.children[idx + 1:]:
                        sibling = tree.get_node(sibling_id)
                        if sibling and sibling.status in ("exploring", "pending"):
                            tree.current_exploring_id = sibling_id
                            return sibling

            # 回溯到父节点
            if active.parent_id:
                parent = tree.get_node(active.parent_id)
                if parent and parent.status == "exploring":
                    tree.current_exploring_id = parent.parent_id or parent.node_id
                    if tree.recursion_stack:
                        tree.recursion_stack.pop()
                    return self.select_next_node(record)

        # 其他未确认叶子
        leaves = tree.unconfirmed_leaves()
        if leaves:
            tree.current_exploring_id = leaves[0].node_id
            return leaves[0]

        return None

    def generate_node_questions(self, record: BrainstormRecord) -> list[str]:
        """针对 active_node 生成追问"""
        active = self.get_active_node(record)
        if not active:
            return []

        missing = self._get_missing_items(active)
        if not missing:
            return []

        # 重建追问计划
        record.feature_tree.question_plan = []
        self.build_question_plan(record, active)

        return self._generate_questions_from_plan(record)

    # ---- 内部 -----------------------------------------------------------

    def _save(self, record: BrainstormRecord) -> None:
        path = self._dir / f"{record.record_id}.json"
        path.write_text(json.dumps(
            brainstorm_to_dict(record),
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

    # ---- Task B4: 状态机推进与 V2 路由 ---------------------------------------------------

    def advance_phase(self, record: BrainstormRecord) -> bool:
        """检查守卫条件，推进 phase"""
        current = record.current_phase
        now = _now_iso()

        if current == BrainstormPhase.PRODUCT_DEF:
            root = record.feature_tree.get_node("fn-root")
            if not root or not self._check_product_complete(root):
                return False
            record.current_phase = BrainstormPhase.FEATURE_DECOMPOSE
            # 自动拆分 product 节点
            if not root.children:
                self._auto_decompose_product(record)

        elif current == BrainstormPhase.FEATURE_DECOMPOSE:
            if not record.feature_tree.all_confirmed():
                return False
            record.current_phase = BrainstormPhase.RELATIONSHIP

        elif current == BrainstormPhase.RELATIONSHIP:
            if not record.relationship_graph.analyzed_at:
                return False
            record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW

        elif current == BrainstormPhase.INDEPENDENT_REVIEW:
            if not record.review_result:
                return False
            if record.review_result.passed:
                record.current_phase = BrainstormPhase.COMPLETE
                record.completed_at = now
            else:
                record.current_phase = BrainstormPhase.CLARIFICATION

        elif current == BrainstormPhase.CLARIFICATION:
            clarifying = [n for n in record.feature_tree.nodes.values() if n.status == "needs_clarification"]
            if not clarifying or all(n.status == "confirmed" for n in clarifying):
                record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW
                record.review_result = None  # 重新审查

        record.phase_history.append({"phase": record.current_phase, "at": now})
        self._save(record)
        return True

    def _auto_decompose_product(self, record: BrainstormRecord) -> None:
        """Phase 1 完成后自动拆分 product 为功能模块"""
        root = record.feature_tree.get_node("fn-root")
        if not root or root.children:
            return

        # 尝试 LLM 拆分
        children_names = self._llm_decompose_node(record, root)
        if not children_names:
            # Fallback: 创建默认模块
            children_names = ["核心功能", "用户管理"]

        for name in children_names:
            child = FeatureNode(
                node_id=f"fn-{len(record.feature_tree.nodes):03d}",
                name=name,
                level="function",
                status="exploring",
            )
            record.feature_tree.add_child(root.node_id, child)

        record.feature_tree.current_exploring_id = root.children[0]

    def _llm_decompose_node(self, record: BrainstormRecord, node: FeatureNode) -> list[str] | None:
        """用 LLM 拆分功能节点"""
        if self._config is None:
            return None

        prompt = f"""你是资深系统架构师。
请将以下功能节点拆分为若干子功能：

功能：{node.name}
描述：{node.user_stories}

拆分原则：
1. 每个子功能应该是独立可开发、可测试的最小单元
2. 子功能之间应该边界清晰
3. 拆分粒度应该合理

请以 JSON 数组返回子功能名称列表：["子功能1", "子功能2", ...]"""

        try:
            result = self._call_llm("decompose", [{"role": "user", "content": prompt}])
            if result:
                names = json.loads(result)
                if isinstance(names, list) and names:
                    return names
        except Exception:
            pass
        return None

    def process_response_v2(
        self,
        record: BrainstormRecord,
        user_response: str,
        extracted_facts: list[dict] | None = None,
    ) -> BrainstormRecord:
        """V2: 按 phase 路由处理用户回复"""
        phase = record.current_phase

        if phase == BrainstormPhase.PRODUCT_DEF:
            self._process_product_response(record, user_response)

        elif phase == BrainstormPhase.FEATURE_DECOMPOSE:
            self._process_decompose_response(record, user_response, extracted_facts)

        elif phase == BrainstormPhase.RELATIONSHIP:
            self._process_relationship_response(record, user_response)

        elif phase == BrainstormPhase.CLARIFICATION:
            self._process_clarification_response(record, user_response)

        # 尝试推进 phase
        self.advance_phase(record)

        # 保存
        self._save(record)
        return record

    def _process_decompose_response(
        self, record: BrainstormRecord, user_response: str, extracted_facts: list[dict] | None = None,
    ) -> None:
        """处理 Phase 2 回答"""
        active = self.get_active_node(record)
        if not active:
            return

        facts = extracted_facts or self._auto_extract_facts(record, user_response)
        if facts:
            self._apply_extracted_facts_to_node(record, active, facts)

        # 检查粒度
        missing = self._get_missing_items(active)
        if missing:
            # 继续追问
            record.feature_tree.question_plan = []
            self.build_question_plan(record, active)
        else:
            # 节点确认
            self.confirm_node(record)
            next_node = self.select_next_node(record)
            if next_node:
                record.feature_tree.current_exploring_id = next_node.node_id
                self.build_question_plan(record, next_node)

    def _process_relationship_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Phase 3 回答"""
        record.relationship_graph.analyzed_at = _now_iso()

    def _process_clarification_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Clarification 回答"""
        clarifying = [n for n in record.feature_tree.nodes.values() if n.status == "needs_clarification"]
        for node in clarifying:
            node.status = "exploring"
            node.review_feedback = []

    def is_complete_v2(self, record: BrainstormRecord) -> bool:
        """V2: current_phase == COMPLETE"""
        return record.current_phase == BrainstormPhase.COMPLETE
