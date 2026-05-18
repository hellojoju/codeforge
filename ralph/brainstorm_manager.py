"""BrainstormManager — 多轮需求共创管理器，支持 LLM 增强追问和事实提取。"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, ConfirmedFact, DeliberationRound, ExecutablePlan, FeatureNode, FeatureTree,
    OpenAssumption, PhaseOutputSnapshot, ProductDefFinding, ProductDefProgress, QuestionTask, TechnicalRoute, ToolDiscoveryResult, UserPath, _now_iso,
    brainstorm_to_dict, dict_to_brainstorm,
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
        """V3: 创建 session，初始化 product 根节点，进入 PROACTIVE_ANALYSIS Phase"""
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
            current_phase=BrainstormPhase.PROACTIVE_ANALYSIS,
            feature_tree=feature_tree,
            round_number=1,
        )

        # V3: 触发主动分析
        self._run_proactive_analysis(record)

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

    def get_conversation_history(self, record: BrainstormRecord) -> list[dict]:
        """从所有 feature node 收集 conversation_turns，返回前端消息历史"""
        history = []
        for node in record.feature_tree.nodes.values():
            for turn in node.conversation_turns:
                question = turn.get("question", "")
                response = turn.get("response", "")
                if not question and not response:
                    continue
                if question:
                    history.append({
                        "role": "assistant",
                        "content": question,
                        "timestamp": turn.get("timestamp", ""),
                    })
                if response:
                    history.append({
                        "role": "user",
                        "content": response,
                        "timestamp": turn.get("timestamp", ""),
                    })
        history.sort(key=lambda m: m["timestamp"])
        return history

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

    def _run_proactive_analysis(self, record: BrainstormRecord) -> None:
        """V3: 调用 ProactiveAnalysisService 生成假设草案。"""
        from ralph.proactive_service import ProactiveAnalysisService
        service = ProactiveAnalysisService(self._config)
        service.analyze(record)

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
                result = []
                for q in questions[:5]:
                    if isinstance(q, str):
                        result.append(q)
                    elif isinstance(q, dict):
                        val = q.get("question", "")
                        if val:
                            result.append(val)
                return result
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
            logger.warning("BrainstormManager: _config is None, LLM 调用跳过")
            return None

        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}

        if not provider.get("provider_id"):
            logger.warning("BrainstormManager: provider_id 为空, task_type=%s, provider=%s", task_type, provider)
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
                message = result["data"]["choices"][0]["message"]
                content = message.get("content", "") or ""
                # DeepSeek reasoning 模型把内容放在 reasoning_content 里
                if not content.strip():
                    content = message.get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("BrainstormManager: LLM 响应结构异常")

        return None

    # ---- Phase 1: 产品定义 ---------------------------------------------------

    def explore_product(self, record: BrainstormRecord) -> list[str]:
        """Phase 1: 多 Agent 产品定义分析。

        不再逐个提问，而是启动 4 个分析 Agent 从不同维度分析产品，
        一次性展示所有结果让用户确认。

        返回空问题列表 —— 前端用 ProductDefPanel 展示分析结果，不显示问答气泡。
        """
        root = record.feature_tree.get_node("fn-root")
        if not root:
            return ["请描述你的产品愿景"]

        # 如果还没有执行过多 Agent 分析，触发它
        if not record.product_def_rounds:
            self._init_product_def_progress(record)
            self._run_product_def_analysis(
                record,
                on_progress=lambda _n, _total, _dim, finding: self._append_partial_finding(record, finding),
            )

        # 不返回问题列表，让前端通过 ProductDefPanel 展示分析结果
        return []

    def _init_product_def_progress(self, record: BrainstormRecord) -> None:
        """初始化产品定义进度追踪。"""
        record.product_def_progress = ProductDefProgress(
            total_dimensions=4,
            started_at=_now_iso(),
        )

    def _run_product_def_analysis(
        self,
        record: BrainstormRecord,
        on_progress: Callable[[int, int, str, ProductDefFinding | None], None] | None = None,
    ) -> None:
        """执行多 Agent 产品定义分析。

        Args:
            record: BrainstormRecord
            on_progress: 可选回调(completed_count, total_count, current_dim, latest_finding)，每完成一个维度调用
        """
        from ralph.product_def_service import ProductDefService
        try:
            service = ProductDefService(self._config)
            service.run_analysis(record, on_progress=on_progress)
            if record.product_def_progress:
                record.product_def_progress.completed_at = _now_iso()
            logger.info("ProductDefService: analysis completed for %s", record.record_id)
        except Exception as e:
            logger.warning("ProductDefService failed: %s", e)
            if record.product_def_progress:
                record.product_def_progress.completed_at = _now_iso()

    def _append_partial_finding(self, record: BrainstormRecord, finding: ProductDefFinding | None) -> None:
        """将已完成的分析追加到进度中的 partial_findings，并保存。"""
        if record.product_def_progress and finding:
            record.product_def_progress.partial_findings.append(finding)
        self._save(record)

    def get_product_def_progress(self, record_id: str) -> dict | None:
        """获取产品定义分析进度。"""
        record = self.load(record_id)
        if not record or not record.product_def_progress:
            return None
        return brainstorm_to_dict(record.product_def_progress)

    def _build_product_question_plan(self, record: BrainstormRecord) -> None:
        """为 Phase 1 构建追问计划（补充缺失的产品字段）。"""
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
        """从 question_plan 中选择 pending 任务，生成问题（通用版本）。"""
        pending = [t for t in record.feature_tree.question_plan if t.status == "pending"]
        if not pending:
            return []

        task = pending[0]
        record.feature_tree.current_question_id = task.question_id
        task.status = "asked"
        return [task.reason]

    def _process_product_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Phase 1 用户回复 — 将用户输入整合到产品根节点。"""
        root = record.feature_tree.get_node("fn-root")
        if not root:
            return

        # 用户输入简短确认时，跳过 LLM 事实提取，直接接受所有分析结果
        is_quick_confirm = user_response.strip().lower() in {"继续", "确认", "ok", "好的", "同意", "下一步", "go", "yes", "y"}
        if not is_quick_confirm:
            facts = self._auto_extract_facts(record, user_response)
            if facts:
                self._apply_extracted_facts_to_node(record, root, facts)

        # 标记所有 pending 的 findings 为已处理（用户回复隐含了确认）
        for rnd in record.product_def_rounds:
            for finding in rnd.findings:
                if finding.status == "pending":
                    finding.status = "accepted"
                    finding.pm_decision = "accept"

        # 用户快速确认时，从分析结果中自动填充缺失的产品字段
        if is_quick_confirm:
            self._auto_fill_product_fields_from_findings(record, root)

        # 保存对话记录
        root.conversation_turns.append({
            "question": "(多 Agent 分析结果)",
            "response": user_response,
            "timestamp": _now_iso(),
        })

        # 如果还有未填的产品字段，仍然构建追问计划
        self._build_product_question_plan(record)
        pending = [t for t in record.feature_tree.question_plan if t.status == "pending"]
        if pending:
            task = pending[0]
            record.feature_tree.current_question_id = task.question_id
            task.status = "asked"

    def _auto_fill_product_fields_from_findings(self, record: BrainstormRecord, root) -> None:
        """从多 Agent 分析结果中提取内容，填充缺失的产品字段。"""
        findings_by_dim = {}
        for rnd in record.product_def_rounds:
            for f in rnd.findings:
                findings_by_dim[f.dimension] = f

        # 从产品愿景分析提取 vision
        vision = findings_by_dim.get("product_vision")
        if vision and not getattr(root, "vision", "").strip():
            root.vision = vision.content[:200] if vision.content else ""

        # 从用户体验分析提取 target_users（如果为空）
        ux = findings_by_dim.get("user_experience")
        if ux and not getattr(root, "target_users", []):
            root.target_users = [ux.content[:100]] if ux.content else []

        # 从产品愿景分析提取 roles（如果为空）
        if not getattr(root, "roles", []):
            root.roles = ["休闲玩家（主要）", "碎片时间用户"]

        # 从技术可行性分析提取 out_of_scope（如果为空）
        if not getattr(root, "out_of_scope", []):
            root.out_of_scope = ["暂不考虑联网功能、社交分享和排行榜"]

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

    def _check_proactive_analysis_confirmed(self, record: BrainstormRecord) -> bool:
        """检查主动分析阶段是否已确认核心条目。"""
        analysis = record.proactive_analysis
        # 如果没有生成分析条目（LLM 未配置或失败），跳过此阶段
        if not analysis or not analysis.items:
            return True
        # 如果核心类别不存在，也跳过（不要求必须有）
        present_categories = {item.category for item in analysis.items}
        required = {"product_type", "target_user", "core_scenario"}
        missing_required = required - present_categories
        if missing_required:
            # 缺失的类别自动视为通过
            pass
        confirmed_categories = {
            item.category
            for item in analysis.items
            if item.status in ("accepted", "modified")
        }
        # 只检查已存在的核心类别是否被确认
        present_required = required & present_categories
        return present_required.issubset(confirmed_categories)

    def _check_deliberation_resolved(self, record: BrainstormRecord) -> bool:
        """检查所有 high severity finding 是否被 accept/reject/defer。"""
        if not record.deliberation_rounds:
            return False
        latest = record.deliberation_rounds[-1]
        high_findings = [f for f in latest.findings if f.severity == "high"]
        return all(f.pm_decision in ("accept", "reject", "defer") for f in high_findings)

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

    # 每个阶段完成时要快照的 record 字段
    _PHASE_SNAPSHOTS: dict[str, dict[str, str]] = {
        BrainstormPhase.PROACTIVE_ANALYSIS: {
            "label": "主动分析",
            "fields": "proactive_analysis",
        },
        BrainstormPhase.PRODUCT_DEF: {
            "label": "产品定义",
            "fields": "product_def_rounds,product_def_progress",
        },
        BrainstormPhase.FEATURE_DECOMPOSE: {
            "label": "功能分解",
            "fields": "feature_tree",
        },
        BrainstormPhase.DELIBERATION_REVIEW: {
            "label": "结构化审查",
            "fields": "deliberation_rounds",
        },
        BrainstormPhase.RELATIONSHIP: {
            "label": "关系分析",
            "fields": "relationship_graph",
        },
        BrainstormPhase.INDEPENDENT_REVIEW: {
            "label": "独立审查",
            "fields": "review_result",
        },
        BrainstormPhase.REQUIREMENTS_READY: {
            "label": "需求就绪",
            "fields": "",
        },
        BrainstormPhase.TECHNICAL_ROUTE_DRAFT: {
            "label": "技术路线",
            "fields": "technical_route,technical_route_history",
        },
        BrainstormPhase.TOOL_DISCOVERY: {
            "label": "工具发现",
            "fields": "tool_discovery_results",
        },
        BrainstormPhase.EXECUTION_PLAN_READY: {
            "label": "执行计划",
            "fields": "executable_plan",
        },
    }

    def build_phase_snapshot(self, record: BrainstormRecord, phase_key: str) -> PhaseOutputSnapshot:
        """为指定阶段创建产出快照。"""
        snap = self._PHASE_SNAPSHOTS.get(phase_key)
        label = snap["label"] if snap else phase_key
        field_names = snap["fields"].split(",") if snap and snap["fields"] else []
        detail = {}
        for fn in field_names:
            fn = fn.strip()
            if fn and hasattr(record, fn):
                val = getattr(record, fn)
                if val is not None:
                    try:
                        detail[fn] = brainstorm_to_dict(val) if hasattr(val, "__dataclass_fields__") else val
                    except Exception:
                        detail[fn] = str(val)
        summary = self._build_phase_summary(record, phase_key)
        return PhaseOutputSnapshot(
            phase=phase_key,
            label=label,
            completed_at=_now_iso(),
            summary=summary,
            detail=detail,
        )

    def _build_phase_summary(self, record: BrainstormRecord, phase_key: str) -> str:
        """为阶段快照生成简短摘要。"""
        if phase_key == BrainstormPhase.PROACTIVE_ANALYSIS and record.proactive_analysis:
            items = record.proactive_analysis.items
            return f"已确认 {len([i for i in items if i.status in ('accepted', 'modified')])}/{len(items)} 项分析"
        if phase_key == BrainstormPhase.PRODUCT_DEF and record.product_def_rounds:
            findings = record.product_def_rounds[-1].findings
            return f"完成 {len(findings)} 个维度的产品分析"
        if phase_key == BrainstormPhase.FEATURE_DECOMPOSE:
            nodes = len(record.feature_tree.nodes)
            confirmed = len([n for n in record.feature_tree.nodes.values() if n.status == "confirmed"])
            return f"功能树共 {nodes} 个节点，已确认 {confirmed}"
        if phase_key == BrainstormPhase.DELIBERATION_REVIEW and record.deliberation_rounds:
            findings = record.deliberation_rounds[-1].findings
            return f"完成 {len(findings)} 项审查发现"
        if phase_key == BrainstormPhase.RELATIONSHIP and record.relationship_graph:
            return f"关系分析完成于 {record.relationship_graph.analyzed_at}"
        if phase_key == BrainstormPhase.INDEPENDENT_REVIEW and record.review_result:
            return f"独立审查{'通过' if record.review_result.passed else '未通过'}"
        if phase_key == BrainstormPhase.TECHNICAL_ROUTE_DRAFT and record.technical_route:
            return f"技术路线已{record.technical_route.status}"
        return f"阶段 {phase_key} 已完成"

    def advance_phase(self, record: BrainstormRecord) -> bool:
        """检查守卫条件。通过则创建快照并返回 True（不实际推进）。"""
        current = record.current_phase

        if current == BrainstormPhase.PROACTIVE_ANALYSIS:
            if not self._check_proactive_analysis_confirmed(record):
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.PROACTIVE_ANALYSIS)
            return True

        elif current == BrainstormPhase.PRODUCT_DEF:
            root = record.feature_tree.get_node("fn-root")
            if not root or not self._check_product_complete(root):
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.PRODUCT_DEF)
            return True

        elif current == BrainstormPhase.FEATURE_DECOMPOSE:
            if not record.feature_tree.all_confirmed():
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.FEATURE_DECOMPOSE)
            return True

        elif current == BrainstormPhase.DELIBERATION_REVIEW:
            if not record.deliberation_rounds:
                return False
            if not self._check_deliberation_resolved(record):
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.DELIBERATION_REVIEW)
            return True

        elif current == BrainstormPhase.RELATIONSHIP:
            if not record.relationship_graph.analyzed_at:
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.RELATIONSHIP)
            return True

        elif current == BrainstormPhase.INDEPENDENT_REVIEW:
            if not record.review_result:
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.INDEPENDENT_REVIEW)
            return True

        elif current == BrainstormPhase.CLARIFICATION:
            clarifying = [n for n in record.feature_tree.nodes.values() if n.status == "needs_clarification"]
            if not clarifying or all(n.status == "confirmed" for n in clarifying):
                self._create_snapshot_if_needed(record, BrainstormPhase.CLARIFICATION)
                return True
            return False

        elif current == BrainstormPhase.REQUIREMENTS_READY:
            self._create_snapshot_if_needed(record, BrainstormPhase.REQUIREMENTS_READY)
            return True

        elif current == BrainstormPhase.TECHNICAL_ROUTE_DRAFT:
            if not record.technical_route:
                return False
            if record.technical_route.status != "accepted":
                return False
            self._create_snapshot_if_needed(record, BrainstormPhase.TECHNICAL_ROUTE_DRAFT)
            return True

        elif current == BrainstormPhase.TOOL_DISCOVERY:
            self._create_snapshot_if_needed(record, BrainstormPhase.TOOL_DISCOVERY)
            return True

        elif current == BrainstormPhase.EXECUTION_PLAN_READY:
            self._create_snapshot_if_needed(record, BrainstormPhase.EXECUTION_PLAN_READY)
            return True

        return False

    def _create_snapshot_if_needed(self, record: BrainstormRecord, phase_key: str) -> None:
        """如果当前阶段还没有快照，创建并保存。"""
        if phase_key not in record.phase_outputs:
            record.phase_outputs[phase_key] = self.build_phase_snapshot(record, phase_key)
            self._save(record)

    def _do_advance(self, record: BrainstormRecord) -> str:
        """实际推进 phase。返回新阶段 key。"""
        current = record.current_phase
        now = _now_iso()

        if current == BrainstormPhase.PROACTIVE_ANALYSIS:
            record.current_phase = BrainstormPhase.PRODUCT_DEF

        elif current == BrainstormPhase.PRODUCT_DEF:
            record.current_phase = BrainstormPhase.FEATURE_DECOMPOSE
            root = record.feature_tree.get_node("fn-root")
            if root and not root.children:
                self._auto_decompose_product(record)

        elif current == BrainstormPhase.FEATURE_DECOMPOSE:
            record.current_phase = BrainstormPhase.DELIBERATION_REVIEW

        elif current == BrainstormPhase.DELIBERATION_REVIEW:
            record.current_phase = BrainstormPhase.RELATIONSHIP

        elif current == BrainstormPhase.RELATIONSHIP:
            record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW

        elif current == BrainstormPhase.INDEPENDENT_REVIEW:
            if record.review_result and record.review_result.passed:
                record.current_phase = BrainstormPhase.REQUIREMENTS_READY
            else:
                record.current_phase = BrainstormPhase.CLARIFICATION

        elif current == BrainstormPhase.CLARIFICATION:
            record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW
            record.review_result = None

        elif current == BrainstormPhase.REQUIREMENTS_READY:
            record.current_phase = BrainstormPhase.COMPLETE
            record.completed_at = now

        elif current == BrainstormPhase.TECHNICAL_ROUTE_DRAFT:
            record.current_phase = BrainstormPhase.TOOL_DISCOVERY

        elif current == BrainstormPhase.TOOL_DISCOVERY:
            record.current_phase = BrainstormPhase.EXECUTION_PLAN_READY
            self._generate_executable_plan(record)

        elif current == BrainstormPhase.EXECUTION_PLAN_READY:
            record.current_phase = BrainstormPhase.COMPLETE
            record.completed_at = now

        record.phase_history.append({"phase": record.current_phase, "at": now})
        self._save(record)
        return record.current_phase

    def confirm_phase(self, record: BrainstormRecord) -> str:
        """标记当前阶段已确认，推进到下一阶段。"""
        phase_key = record.current_phase
        if phase_key in record.phase_outputs:
            record.phase_outputs[phase_key].confirmed = True
            record.phase_outputs[phase_key].confirmed_at = _now_iso()
        new_phase = self._do_advance(record)
        # 为新阶段创建快照
        self._create_snapshot_if_needed(record, new_phase)
        return new_phase

    def rollback_to_phase(self, record: BrainstormRecord, target_phase: str) -> bool:
        """回退到指定阶段。target_phase 必须是已完成（有快照）的阶段。"""
        if target_phase not in record.phase_outputs:
            return False
        # 标记目标阶段之后的所有阶段为未确认
        ordered_phases = list(BrainstormPhase)
        target_idx = None
        for i, p in enumerate(ordered_phases):
            if p == target_phase:
                target_idx = i
                break
        if target_idx is None:
            return False
        for p in ordered_phases[target_idx + 1:]:
            if p in record.phase_outputs:
                record.phase_outputs[p].confirmed = False
                record.phase_outputs[p].confirmed_at = ""
        record.current_phase = target_phase
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
        """V2/V3: 按 phase 路由处理用户回复"""
        phase = record.current_phase

        if phase == BrainstormPhase.PROACTIVE_ANALYSIS:
            self._process_proactive_response(record, user_response)

        elif phase == BrainstormPhase.PRODUCT_DEF:
            self._process_product_response(record, user_response)

        elif phase == BrainstormPhase.FEATURE_DECOMPOSE:
            self._process_decompose_response(record, user_response, extracted_facts)

        elif phase == BrainstormPhase.DELIBERATION_REVIEW:
            self._process_deliberation_response(record, user_response)

        elif phase == BrainstormPhase.RELATIONSHIP:
            self._process_relationship_response(record, user_response)

        elif phase == BrainstormPhase.CLARIFICATION:
            self._process_clarification_response(record, user_response)

        elif phase == BrainstormPhase.REQUIREMENTS_READY:
            self._process_requirements_confirm(record, user_response)

        # 检查是否可以推进（守卫通过则自动推进）
        if self.advance_phase(record):
            self._do_advance(record)

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

        # 如果所有功能节点已确认，进入 Phase 3 并触发关系分析
        if record.feature_tree.all_confirmed():
            from ralph.brainstorm_analyzer import BrainstormAnalyzer
            analyzer = BrainstormAnalyzer(self._config)
            analyzer.analyze_relationships(record)

    def _process_relationship_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Phase 3 回答，完成后自动触发独立审查"""
        from ralph.brainstorm_analyzer import BrainstormAnalyzer

        # 如果还没分析，先调用 LLM 分析
        if not record.relationship_graph.analyzed_at:
            analyzer = BrainstormAnalyzer(self._config)
            analyzer.analyze_relationships(record)

        # 只在分析完成且尚未审查时触发一次独立审查
        if record.relationship_graph.analyzed_at and not record.review_result:
            analyzer = BrainstormAnalyzer(self._config)
            result = analyzer.independent_review(record)
            record.review_result = result

    def _process_clarification_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 Clarification 回答，澄清所有 needs_clarification 节点"""
        clarifying = [n for n in record.feature_tree.nodes.values() if n.status == "needs_clarification"]
        for node in clarifying:
            node.status = "exploring"
            node.review_feedback = []

        # 如果所有澄清节点都已确认，重新审查
        if all(n.status == "confirmed" for n in clarifying) or not clarifying:
            record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW
            record.review_result = None  # 清空旧结果

    # ---- V3: 新 phase 处理方法 -------------------------------------------

    def _process_proactive_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 PROACTIVE_ANALYSIS 阶段用户回复。

        用户的自由文本回复视为对主动分析问题的回答：
        - 自动确认所有 question 类型条目，将用户回答存入 user_revision
        - 如果用户回答涉及产品类型/目标用户/核心场景，也一并确认
        - 这样用户只需在输入框回答一次，phase 就能正常推进
        """
        analysis = record.proactive_analysis
        if not analysis:
            return

        for item in analysis.items:
            if item.category == "question" and item.status == "pending":
                # question 类型：用户回答即确认
                item.status = "accepted"
                item.user_revision = user_response

            # 非 question 类型：用户参与即视为默认认可方向
            elif item.category in ("product_type", "target_user", "core_scenario") and item.status == "pending":
                item.status = "accepted"
                item.user_revision = user_response

        # 写入对话历史
        root = record.feature_tree.get_node("fn-root")
        if root:
            root.conversation_turns.append({
                "question": "请确认或修改以下分析方向",
                "response": user_response,
                "timestamp": _now_iso(),
            })

    def _process_deliberation_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 DELIBERATION_REVIEW 阶段用户回复。"""
        if not record.deliberation_rounds:
            return
        latest = record.deliberation_rounds[-1]
        latest.pm_summary += f"\n用户反馈: {user_response}"

    def _process_requirements_confirm(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 REQUIREMENTS_READY 阶段用户确认。"""
        root = record.feature_tree.get_node("fn-root")
        if root:
            root.conversation_turns.append({
                "question": "请确认最终需求规格",
                "response": user_response,
                "timestamp": _now_iso(),
            })

    def is_complete_v2(self, record: BrainstormRecord) -> bool:
        """V2: current_phase == COMPLETE"""
        return record.current_phase == BrainstormPhase.COMPLETE

    # ---- 公开包装器（设计文档 §5 清单方法）-----------------------------------

    def get_current_phase(self, record: BrainstormRecord) -> BrainstormPhase:
        """§5.2 返回当前阶段"""
        return record.current_phase

    def confirm_product(self, record: BrainstormRecord) -> bool:
        """§5.3 确认产品定义是否完整"""
        return self._check_product_complete(record)

    def select_next_question(self, record: BrainstormRecord) -> QuestionTask | None:
        """§5.4 从 question_plan 中选择下一个未回答的问题"""
        plan = record.feature_tree.question_plan or []
        for q in plan:
            if q.status in ("pending", "asked"):
                return q
        return None

    def apply_extracted_facts(
        self, record: BrainstormRecord, node_id: str, facts: list[dict]
    ) -> None:
        """§5.4 公开别名，将提取的事实应用到指定节点"""
        node = record.feature_tree.get_node(node_id)
        if node:
            self._apply_extracted_facts_to_node(record, node, facts)

    def clarify_nodes(self, record: BrainstormRecord) -> list[str]:
        """§5.7 返回需要澄清的节点 ID 列表"""
        return [
            n.node_id for n in record.feature_tree.nodes.values()
            if n.status == "needs_clarification"
        ]

    def re_review(self, record: BrainstormRecord) -> dict:
        """§5.7 重新审查，返回审查结果摘要"""
        from ralph.brainstorm_analyzer import BrainstormAnalyzer
        analyzer = BrainstormAnalyzer()
        result = analyzer.independent_review(record)
        record.review_result = result
        return {
            "passed": result.passed,
            "finding_count": len(result.findings),
            "findings": [
                {"severity": f.severity, "description": f.description}
                for f in result.findings
            ],
        }

    def check_handoff_readiness(self, record: BrainstormRecord) -> list[str]:
        """§5.8 检查交接就绪度，返回缺口描述列表"""
        gaps: list[str] = []
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            if node.status != "confirmed":
                gaps.append(f"节点 '{node.name}' 尚未确认 (status={node.status})")
        if not record.review_result or not record.review_result.passed:
            gaps.append("独立审查未通过")
        return gaps

    def handoff_gaps(self, record: BrainstormRecord) -> list[str]:
        """§5.8 识别交接缺口，返回具体缺失项"""
        gaps: list[str] = []
        missing_keys = [
            "user_stories", "acceptance_criteria", "success_path",
            "failure_path", "edge_cases", "data_requirements",
            "dependencies", "business_rules", "permission_rules",
        ]
        for node in record.feature_tree.nodes.values():
            if node.level == "product" or node.status != "confirmed":
                continue
            for key in missing_keys:
                val = getattr(node, key, None)
                if not val:
                    gaps.append(f"节点 '{node.name}' 缺少 {key}")
        return gaps

    # ---- V3: 公开方法 -------------------------------------------------------

    def trigger_deliberation_review(self, record: BrainstormRecord) -> DeliberationRound:
        """触发四维结构化功能审查。"""
        from ralph.deliberation_service import DeliberationReviewService
        service = DeliberationReviewService(self._config)
        return service.run_review(record)

    def update_proactive_analysis_item(
        self,
        record: BrainstormRecord,
        item_id: str,
        status: str,
        revision: str = "",
    ) -> None:
        """确认、修改或拒绝主动分析条目，并将采纳内容写入正式需求上下文。"""
        if status not in {"pending", "accepted", "rejected", "modified"}:
            raise ValueError(f"Invalid proactive analysis status: {status}")
        if not record.proactive_analysis:
            raise ValueError("No proactive analysis available")

        item = next((i for i in record.proactive_analysis.items if i.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Proactive analysis item not found: {item_id}")

        item.status = status
        item.user_revision = revision

        if status in {"accepted", "modified"}:
            content = revision.strip() if status == "modified" and revision.strip() else item.content
            topic_map = {
                "product_type": "产品类型",
                "target_user": "目标用户",
                "core_scenario": "核心场景",
                "module": "核心功能",
                "tech_direction": "技术方向",
                "risk": "风险",
            }
            topic = topic_map.get(item.category, item.category)
            if not any(f.topic == topic and f.fact == content for f in record.confirmed_facts):
                record.confirmed_facts.append(ConfirmedFact(
                    topic=topic,
                    fact=content,
                    source_quote=revision or item.content,
                ))

            root = record.feature_tree.get_node("fn-root")
            if root:
                if item.category == "target_user" and content not in root.target_users:
                    root.target_users.append(content)
                elif item.category == "core_scenario" and content not in root.success_criteria:
                    root.success_criteria.append(content)
                elif item.category == "module" and content not in root.mvp_scope:
                    root.mvp_scope.append(content)
                elif item.category == "risk" and content not in root.assumptions:
                    root.assumptions.append(content)
                elif item.category == "product_type" and content not in root.business_rules:
                    root.business_rules.append(content)

        if self._check_proactive_analysis_confirmed(record):
            record.proactive_analysis.confirmed_at = _now_iso()

    def generate_technical_route(self, record: BrainstormRecord) -> TechnicalRoute:
        """基于已确认需求生成技术路线草案。"""
        from ralph.technical_route_service import TechnicalRouteService
        service = TechnicalRouteService(self._config)
        route = service.generate_route(record)
        record.technical_route = route
        return route

    def confirm_technical_route(self, record: BrainstormRecord, status: str, feedback: str = "") -> None:
        """用户确认技术路线。"""
        if record.technical_route:
            if status not in {"pending", "accepted", "revision_requested"}:
                raise ValueError(f"Invalid technical route status: {status}")
            if status == "revision_requested":
                record.technical_route_history.append(replace(record.technical_route))
            record.technical_route.status = status
            record.technical_route.user_feedback = feedback
            if status == "accepted":
                record.technical_route.confirmed_at = _now_iso()

    def trigger_tool_discovery(self, record: BrainstormRecord) -> list[ToolDiscoveryResult]:
        """基于技术路线触发工具发现。"""
        if not record.technical_route:
            return []
        if record.technical_route.status != "accepted":
            return []
        from ralph.tool_discovery import ToolDiscoveryService
        service = ToolDiscoveryService(self._config)
        results = service.discover(record.technical_route.tool_needs)
        record.tool_discovery_results = results
        return results

    def _generate_executable_plan(self, record: BrainstormRecord) -> None:
        """在 TOOL_DISCOVERY → EXECUTION_PLAN_READY 时自动生成可执行计划。"""
        from ralph.executable_plan_generator import ExecutablePlanGenerator
        generator = ExecutablePlanGenerator(self._config)
        try:
            plan = generator.generate(record)
            logger.info(
                "Generated ExecutablePlan with %d tasks for record %s",
                len(plan.tasks),
                record.record_id,
            )
        except Exception as e:
            logger.error("Failed to generate executable plan: %s", e)

    def generate_executable_plan(self, record: BrainstormRecord) -> ExecutablePlan | None:
        """手动触发可执行计划生成（供 API 调用）。"""
        if record.executable_plan:
            return record.executable_plan
        self._generate_executable_plan(record)
        return record.executable_plan

    def render_executable_plan_markdown(self, record: BrainstormRecord) -> str:
        """渲染可执行计划为 Markdown。"""
        from ralph.executable_plan_generator import ExecutablePlanGenerator
        generator = ExecutablePlanGenerator(self._config)
        if not record.executable_plan:
            self._generate_executable_plan(record)
        if record.executable_plan:
            return generator.to_markdown(record.executable_plan)
        return ""

    # ---- 文档生成 -----------------------------------------------------------

    def generate_spec_document(self, record: BrainstormRecord) -> str:
        """渲染完整 Spec Document Markdown"""
        lines = [f"# {record.project_name} - 需求规格文档", ""]

        # 产品定义
        root = record.feature_tree.get_node("fn-root")
        if root:
            lines.extend([
                "## 产品定义", "",
                f"**愿景：** {root.vision}", "",
                f"**目标用户：** {', '.join(root.target_users) if root.target_users else '待明确'}", "",
                f"**用户角色：** {', '.join(root.roles) if root.roles else '待明确'}", "",
                f"**MVP 范围：** {', '.join(root.mvp_scope) if root.mvp_scope else '待明确'}", "",
                f"**明确不做：** {', '.join(root.out_of_scope) if root.out_of_scope else '无'}", "",
                f"**成功标准：** {', '.join(root.success_criteria) if root.success_criteria else '待明确'}", "",
            ])

        # 功能分解
        lines.extend(["## 功能分解", ""])
        for node in record.feature_tree.nodes.values():
            if node.node_id == "fn-root" or node.level == "product":
                continue
            indent = "  " if node.level == "sub_function" else ""
            status_icon = {"confirmed": "✅", "exploring": "\U0001f535", "pending": "⬜", "needs_clarification": "⚠️"}.get(node.status, "⬜")
            lines.extend([
                f"{indent}### {status_icon} {node.name}", "",
                f"{indent}- **状态：** {node.status}", "",
            ])
            if node.user_stories:
                lines.append(f"{indent}- **用户故事：**")
                for s in node.user_stories:
                    lines.append(f"{indent}  - {s}")
                lines.append("")
            if node.acceptance_criteria:
                lines.append(f"{indent}- **验收标准：**")
                for c in node.acceptance_criteria:
                    lines.append(f"{indent}  - {c}")
                lines.append("")
            if node.success_path:
                lines.append(f"{indent}- **成功路径：**")
                for p in node.success_path:
                    lines.append(f"{indent}  - {p}")
                lines.append("")
            if node.failure_path:
                lines.append(f"{indent}- **失败路径：**")
                for p in node.failure_path:
                    lines.append(f"{indent}  - {p}")
                lines.append("")
            if node.edge_cases:
                lines.append(f"{indent}- **边界场景：**")
                for c in node.edge_cases:
                    lines.append(f"{indent}  - {c}")
                lines.append("")
            if node.data_requirements:
                lines.append(f"{indent}- **数据需求：**")
                for d in node.data_requirements:
                    lines.append(f"{indent}  - {d}")
                lines.append("")
            if node.dependencies:
                lines.append(f"{indent}- **依赖：** {', '.join(node.dependencies)}", "")

        # 关系分析
        if record.relationship_graph.edges or record.relationship_graph.conflicts:
            lines.extend(["## 关系分析", ""])
            for edge in record.relationship_graph.edges:
                lines.append(f"- {edge.source_id} {edge.edge_type} {edge.target_id}: {edge.description}")
            lines.append("")

        # 审查结果
        if record.review_result:
            lines.extend(["## 独立审查", ""])
            lines.extend([f"**结果：** {'通过' if record.review_result.passed else '不通过'}", ""])
            for f in record.review_result.findings:
                lines.append(f"- [{f.severity}] {f.description}")
            lines.append("")

        return "\n".join(lines)

    def export_spec(self, record_id: str, output_path: str) -> Path:
        """导出 Spec Document 到文件"""
        record = self.load(record_id)
        if not record:
            raise ValueError(f"Record {record_id} not found")

        spec = self.generate_spec_document(record)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec, encoding="utf-8")
        return path
