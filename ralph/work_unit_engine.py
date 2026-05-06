"""WorkUnit Engine — 新编排器

文档依据：
- 实施方案 §4.2 Work Unit Engine
- AI 协议 §7.2 状态修改权限
- MVP 清单 §13 MVP 完成定义

职责：
- 替代 ProjectManager 的执行循环
- 流程：创建 WorkUnit → preflight check → 生成 Harness → 生成 ContextPack
  → 执行前门禁 → 调用 Claude Runner → 收集 Evidence → 执行后门禁
  → 独立 Review → 状态决策
- 和 PMCoordinator 共存，通过 feature flag 切换
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

from core.ralph_paths import resolve_ralph_dir
from ralph.claude_runner import ClaudeCodeRunner, ExecutionResult
from ralph.config_manager import RalphConfigManager
from ralph.context_pack_manager import ContextPackManager
from ralph.evidence_collector import EvidenceCollector
from ralph.guard_coordinator import GuardCoordinator
from ralph.harness_manager import HarnessManager
from ralph.memory_manager import MemoryManager
from ralph.memory_archiver import MemoryArchiver
from ralph.repository import RalphRepository
from ralph.review_manager import ReviewManager, ReviewRequest
from ralph.schema.review_result import ReviewResult
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
from ralph.schema.state_unified import BlockingType

logger = logging.getLogger(__name__)


class WorkUnitEngine:
    """WorkUnit 编排引擎。

    完整闭环：
    draft → ready → running → needs_review → accepted/failed/blocked
    """

    def __init__(self, project_dir: Path, event_bus: Any = None,
                 memory_manager: MemoryManager | None = None) -> None:
        self._project_dir = Path(project_dir)
        self._ralph_dir = resolve_ralph_dir(self._project_dir)
        self._repository = RalphRepository(self._ralph_dir)
        self._harness_mgr = HarnessManager()
        self._context_mgr = ContextPackManager(self._project_dir)
        self._evidence_collector = EvidenceCollector(self._ralph_dir)
        self._review_mgr = ReviewManager()
        self._runner = ClaudeCodeRunner(self._project_dir)
        self._guard = GuardCoordinator()
        self._config_mgr = RalphConfigManager(self._ralph_dir)
        self._event_bus = event_bus
        self._memory = memory_manager or MemoryManager(self._ralph_dir, project_dir=self._project_dir)
        self._archiver = MemoryArchiver(self._ralph_dir, config=self._config_mgr)
        # 知识图谱 — 用于查询历史教训
        try:
            from ralph.knowledge_graph import KnowledgeGraphService
            self._knowledge_graph = KnowledgeGraphService(self._ralph_dir)
        except ImportError:
            self._knowledge_graph = None

    def _emit_event(self, event_type: str, **kwargs: Any) -> None:
        """发送 Ralph 事件到 Dashboard（如果有 event_bus）。"""
        if self._event_bus is not None:
            self._event_bus.emit(event_type, **kwargs)

    def _archive_if_terminal(self, work_id: str, exec_log: str = "") -> None:
        """终态自动归档到记忆系统并触发反思回顾。"""
        unit = self._repository.get_work_unit(work_id)
        if unit and unit.status.value in ("accepted", "failed", "blocked"):
            from dataclasses import asdict

            unit_dict = asdict(unit)
            # asdict 不会把 Enum 转为 .value，手动转换
            unit_dict["status"] = unit.status.value

            self._memory.on_work_unit_completed(unit_dict, exec_log)
            # 触发 MemoryArchiver 自动压缩
            self._archiver.compact_on_terminal(work_id, unit_dict, full_log=exec_log)
            # 索引到知识图谱
            if self._knowledge_graph is not None:
                try:
                    self._knowledge_graph.index_work_unit(unit_dict, exec_log=exec_log)
                except Exception as e:
                    logger.warning("KnowledgeGraph index failed for %s: %s", work_id, e)
            # 触发反思回顾
            retro_result = self._memory.trigger_retro(unit_dict, exec_log)
            # 自动调参
            self._apply_retro_tuning(unit_dict, exec_log)

            # 阻塞时自动创建 UnifiedBlockingIssue
            if unit.status.value == "blocked":
                self._auto_create_blocking_issue(unit, exec_log)
            # 自动生成 follow-up WorkUnit
            self._create_retro_follow_ups(retro_result)

    def _auto_create_blocking_issue(self, unit: WorkUnit, exec_log: str = "") -> None:
        """WorkUnit 进入 blocked 时自动创建 UnifiedBlockingIssue。"""
        from ralph.schema.state_unified import UnifiedBlockingIssue

        error = unit.error or unit.blocking_reason or ""
        # 从 error 推断阻塞类型
        btype = BlockingType.UNEXPECTED_RUNTIME_ERROR
        error_lower = error.lower()
        if any(k in error_lower for k in ("api_key", "api key", "credentials", "secret")):
            btype = BlockingType.MISSING_CREDENTIALS
        elif any(k in error_lower for k in ("env", "environment")):
            btype = BlockingType.MISSING_ENV
        elif any(k in error_lower for k in ("timeout", "unavailable", "connection")):
            btype = BlockingType.EXTERNAL_SERVICE_DOWN
        elif any(k in error_lower for k in ("permission", "denied", "forbidden")):
            btype = BlockingType.SCOPE_VIOLATION
        elif any(k in error_lower for k in ("budget", "token", "limit", "rate")):
            btype = BlockingType.RESOURCE_EXHAUSTED

        issue = UnifiedBlockingIssue(
            blocking_id=f"auto_{unit.work_id}_{unit.updated_at[:10] if unit.updated_at else 'now'}",
            type=btype,
            title=f"WorkUnit {unit.work_id} 阻塞: {error[:80] if error else unit.title[:80]}",
            details=f"WorkUnit: {unit.work_id}\nTitle: {unit.title}\nError: {error}",
            required_human_action=f"查看 WorkUnit {unit.work_id} 日志后人工处理",
            related_task_id=unit.work_id,
            status="open",
        )
        self._repository.save_blocking_issue(issue)
        logger.info("自动创建阻塞项: %s type=%s", issue.blocking_id, btype)

    def create_work_unit(self, unit: WorkUnit) -> WorkUnit:
        """创建并保存 WorkUnit（初始状态 draft）。"""
        self._repository.save_work_unit(unit)
        logger.info("创建 WorkUnit: %s", unit.work_id)
        return unit

    def prepare(self, work_id: str) -> WorkUnit:
        """准备工作单元：draft → ready。

        检查：
        1. harness 校验通过
        2. ready 条件满足
        """
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            raise ValueError(f"WorkUnit {work_id} 不存在")

        # harness 校验
        if unit.task_harness:
            harness_errors = self._harness_mgr.validate_harness(unit.task_harness)
            if harness_errors:
                logger.error("harness 校验失败: %s", harness_errors)
                raise ValueError(f"harness 校验失败: {harness_errors}")

        # ready 条件
        ready_errors = unit.validate_ready()
        if ready_errors:
            logger.error("ready 条件不满足: %s", ready_errors)
            raise ValueError(f"ready 条件不满足: {ready_errors}")

        result = self._repository.transition(
            work_id, WorkUnitStatus.READY, actor_role="scheduler", reason="通过预检"
        )
        self._emit_event("ralph_work_unit_ready", work_id=work_id, status=WorkUnitStatus.READY.value)
        return result

    async def execute(
        self,
        work_id: str,
        agent: Any = None,
        prd_summary: str = "",
        use_claude_runner: bool = True,
        tool_cwd: Path | None = None,
    ) -> dict:
        """执行 WorkUnit：ready → running → needs_review/failed/blocked。

        Args:
            work_id: WorkUnit ID
            agent: 执行 agent（use_claude_runner=False 时使用旧接口）
            prd_summary: PRD 摘要
            use_claude_runner: 是否使用 Claude Code Runner 执行
            tool_cwd: 工具执行工作目录（用于 worktree 隔离），默认 project_dir

        Returns:
            执行结果 dict
        """
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            raise ValueError(f"WorkUnit {work_id} 不存在")

        # ready → running
        unit = self._repository.transition(
            work_id, WorkUnitStatus.RUNNING, actor_role="scheduler"
        )
        self._emit_event("ralph_work_unit_running", work_id=work_id, status=WorkUnitStatus.RUNNING.value)

        # 生成 ContextPack
        try:
            lessons = self._collect_retro_lessons(unit)
            context_pack = self._context_mgr.build(
                unit,
                prd_fragment=prd_summary,
                lessons_learned=lessons,
            )
        except ValueError as e:
            logger.error("上下文包超出 budget: %s", e)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED, reason=f"上下文包超出 budget: {e}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "blocked", "error": str(e), "work_id": work_id}

        # 执行前门禁
        preflight = self._harness_mgr.preflight(unit)
        if not preflight.passed:
            logger.error("执行前门禁失败: %s", preflight.failures)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED, reason=f"preflight 失败: {preflight.failures}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "blocked", "error": str(preflight.failures), "work_id": work_id}

        # Token budget 检查
        budget_check = self._config_mgr.check_budget()
        if not budget_check["allowed"]:
            logger.error("Token budget 超限: %s", budget_check["reason"])
            unit = self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED, reason=f"budget 超限: {budget_check['reason']}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "blocked", "error": budget_check["reason"], "work_id": work_id}

        # 开始执行中记录
        self._harness_mgr.start_inflight(work_id)

        # 加载并应用历史 Retro 调参建议
        tuning = self._config_mgr.load_tuning()
        if tuning:
            self._apply_tuning_to_unit(unit, tuning)

        # 调用执行器
        if use_claude_runner:
            exec_result = await self._execute_with_claude(unit, context_pack, prd_summary, tool_cwd=tool_cwd)
        else:
            exec_result = await self._execute_with_agent(agent, unit, context_pack, prd_summary)

        if not exec_result.success:
            logger.error("执行失败: %s", exec_result.error)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.FAILED, actor_role="executor", reason=exec_result.error
            )
            self._archive_if_terminal(work_id, exec_result.stderr or exec_result.stdout or "")
            return {
                "success": False,
                "status": "failed",
                "error": exec_result.error,
                "work_id": work_id,
                "stdout": exec_result.stdout,
                "stderr": exec_result.stderr,
            }

        # 记录执行中变更
        self._harness_mgr.record_inflight(
            work_id,
            files_modified=exec_result.files_modified + exec_result.files_created,
        )

        # 收集证据
        evidence_items = self._evidence_collector.collect(
            work_id,
            self._project_dir,
            include_test_output=str(exec_result.test_results),
        )
        for ev in evidence_items:
            self._repository.save_evidence(ev)

        # 执行后门禁
        all_changed = exec_result.files_created + exec_result.files_modified + exec_result.files_deleted
        postflight = self._harness_mgr.postflight(
            unit,
            files_changed=all_changed,
            evidence_files=[e.file_path for e in evidence_items],
            test_passed=bool(exec_result.test_results),
            review_completed=True,
        )

        if not postflight.passed:
            logger.error("执行后门禁失败: %s", postflight.failures)
            unit = self._repository.transition(
                work_id, WorkUnitStatus.FAILED, actor_role="executor", reason=f"postflight 失败: {postflight.failures}"
            )
            self._archive_if_terminal(work_id)
            return {"success": False, "status": "failed", "error": str(postflight.failures), "work_id": work_id}

        # running → needs_review
        unit = self._repository.transition(
            work_id, WorkUnitStatus.NEEDS_REVIEW, actor_role="executor"
        )
        self._emit_event("ralph_work_unit_needs_review", work_id=work_id, status=WorkUnitStatus.NEEDS_REVIEW.value)

        return {
            "success": True,
            "status": "needs_review",
            "work_id": work_id,
            "files_changed": all_changed,
            "evidence_files": [e.file_path for e in evidence_items],
            "exec_result": exec_result,
        }

    async def _execute_with_claude(
        self,
        unit: WorkUnit,
        context_pack: Any,
        prd_summary: str,
        tool_cwd: Path | None = None,
    ) -> ExecutionResult:
        """通过 Claude Code Runner 执行（流式模式）。"""
        harness = unit.task_harness
        harness_text = str(harness) if harness else ""

        scope_allow = unit.scope_allow or (harness.scope_allow if harness else [])
        scope_deny = unit.scope_deny or (harness.scope_deny if harness else [])
        acceptance_criteria = unit.acceptance_criteria or []

        # 4.1: 输入语义扫描 + 正则黑名单 + Canary Token
        context_text = str(context_pack)
        cleaned_context, ctx_violations = self._guard.check_input(context_text)
        cleaned_prd, prd_violations = self._guard.check_input(prd_summary)

        # 4.1b: 嵌入 Canary Token — 用于输出泄露检测
        cleaned_context = self._guard.embed_canary(cleaned_context)

        # 4.1c: Taste Memory 注入 — 将设计偏好注入到上下文
        taste_ctx = self._memory.get_taste_context() if self._memory else ""
        if taste_ctx:
            cleaned_context = f"{cleaned_context}\n{taste_ctx}"

        all_violations = ctx_violations + prd_violations
        if all_violations:
            logger.warning(
                "WorkUnit %s: 检测到 %d 条注入模式 → 已清理",
                unit.work_id,
                len(all_violations),
            )

        def _stream_cb(event_type: str, chunk: str) -> None:
            self._emit_event("ralph_stream_chunk", work_id=unit.work_id, chunk_type=event_type, text=chunk)

        result = await self._runner.execute_streaming(
            work_id=unit.work_id,
            context_pack_text=cleaned_context,
            harness_text=harness_text,
            scope_allow=scope_allow,
            scope_deny=scope_deny,
            acceptance_criteria=acceptance_criteria,
            stream_callback=_stream_cb,
            cwd=tool_cwd,
        )

        # 4.1: 输出验证 — canary 泄露 + 危险操作检测
        if result.stdout:
            is_safe, output_violations = self._guard.check_output(result.stdout)
            if not is_safe:
                logger.warning(
                    "WorkUnit %s: 输出验证失败 — %s",
                    unit.work_id,
                    [v.get("type") for v in output_violations],
                )
                result.stdout = "[输出被拦截：检测到安全风险]"

        return result

    async def _execute_with_agent(
        self,
        agent: Any,
        unit: WorkUnit,
        context_pack: Any,
        prd_summary: str,
    ) -> ExecutionResult:
        """通过旧版 agent 接口执行（兼容模式）。"""
        try:
            agent_result = await agent.execute(
                {
                    "feature_id": unit.work_id,
                    "description": unit.target,
                    "prd_summary": prd_summary,
                    "context_pack": str(context_pack),
                },
                workspace_dir=self._project_dir,
            )

            files_changed = agent_result.get("files_changed", [])
            return ExecutionResult(
                work_id=unit.work_id,
                success=agent_result.get("success", False),
                stdout="",
                stderr="",
                files_created=[f for f in files_changed if f],
                files_modified=[],
                files_deleted=[],
                test_results={"agent_test": "pass"} if agent_result.get("success") else {},
                error=agent_result.get("error"),
            )
        except Exception as e:
            return ExecutionResult(
                work_id=unit.work_id,
                success=False,
                stdout="",
                stderr="",
                error=str(e),
            )

    def review(self, work_id: str) -> ReviewResult:
        """独立审查：needs_review → accepted/needs_rework/blocked。

        由调度 agent 调用，根据审查结论做状态决策。
        集成 SkillBridge：根据 work_type 选择 skill + rules 混合审查。
        """
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            raise ValueError(f"WorkUnit {work_id} 不存在")
        if unit.status != WorkUnitStatus.NEEDS_REVIEW:
            raise ValueError(f"WorkUnit {work_id} 当前状态为 {unit.status.value}，不能执行 review")

        # 收集 diff 和 evidence
        evidence_list = self._repository.list_evidence(work_id)
        diff_stat = ""
        for ev in evidence_list:
            if ev.evidence_type == "diff":
                with contextlib.suppress(OSError):
                    diff_stat = Path(ev.file_path).read_text(encoding="utf-8")

        evidence_dict = {
            "files": [e.file_path for e in evidence_list],
            "diff_summary": diff_stat,
        }

        # SkillBridge 混合审查
        skill_result = None
        try:
            from ralph.skill_bridge import SkillBridge
            from ralph.rules_engine import RulesEngine
            from ralph.rules_engine import register_builtin_rules

            rules_engine = RulesEngine()
            register_builtin_rules(rules_engine)

            bridge = SkillBridge(rules_engine=rules_engine)
            skill_result = bridge.execute_review(
                work_id=work_id,
                work_type=unit.work_type.value if hasattr(unit.work_type, "value") else unit.work_type,
                evidence=evidence_dict,
                diff_summary=diff_stat,
            )
            logger.info(
                "SkillBridge 审查: work_id=%s skill=%s %s",
                work_id, skill_result.skill_name, skill_result.summary,
            )
        except ImportError as e:
            logger.debug("SkillBridge 不可用，使用基线审查: %s", e)

        # 多维度评审矩阵
        matrix_review = None
        try:
            from ralph.review_matrix import ReviewMatrixEngine
            config_mgr = RalphConfigManager(self._ralph_dir)
            matrix_engine = ReviewMatrixEngine(config_mgr=config_mgr, project_dir=self._project_dir)
            matrix_review = asyncio.run(matrix_engine.execute_review(
                work_id=work_id,
                evidence=evidence_dict,
                work_type=unit.work_type,
                acceptance_criteria=unit.acceptance_criteria,
                diff_summary=diff_stat,
            ))
            self._repository.save_review(matrix_review)
            logger.info("多维度评审完成: work_id=%s conclusion=%s", work_id, matrix_review.conclusion)
        except RuntimeError as e:
            # asyncio.run() 不能在已有事件循环中调用，使用基线审查
            logger.warning("多维度评审跳过(事件循环冲突): %s", e)
        except Exception as e:
            logger.warning("多维度评审失败，使用基线审查: %s", e)

        # 构建审查请求（基线审查）
        request = ReviewRequest(
            work_id=work_id,
            diff_summary=diff_stat,
            acceptance_criteria=unit.acceptance_criteria,
            evidence_files=[e.file_path for e in evidence_list],
            task_description=unit.target,
            scope_allow=unit.scope_allow,
            scope_deny=unit.scope_deny,
        )

        # 独立审查（基线）
        review = self._review_mgr.review(request)

        # 合并 SkillBridge 发现的问题
        if skill_result and skill_result.issues:
            review = ReviewResult(
                work_id=review.work_id,
                reviewer_context_id=review.reviewer_context_id,
                review_type=review.review_type,
                conclusion=review.conclusion,
                recommended_action=review.recommended_action,
                criteria_results=review.criteria_results,
                issues_found=review.issues_found + [
                    {"description": i.description, "severity": i.severity, "suggested_action": i.suggested_action}
                    for i in skill_result.issues
                ],
                evidence_checked=review.evidence_checked,
                harness_checked=review.harness_checked,
                skill_review={
                    "skill_name": skill_result.skill_name,
                    "summary": skill_result.summary,
                    "focus_checks": skill_result.focus_checks,
                },
                dimension_results=matrix_review.dimension_results if matrix_review else None,
                overall_confidence=matrix_review.overall_confidence if matrix_review else None,
            )

        # 如果多维度评审有更严格的结论，采用之
        if matrix_review is not None:
            if matrix_review.conclusion == "不通过" and review.conclusion == "通过":
                review.conclusion = "不通过"
            if matrix_review.issues_found:
                if not hasattr(review, "issues_found") or not review.issues_found:
                    review.issues_found = []
                review.issues_found.extend(matrix_review.issues_found)

        self._repository.save_review(review)

        # 状态决策
        if review.conclusion == "通过":
            self._repository.transition(
                work_id, WorkUnitStatus.ACCEPTED, actor_role="scheduler", reason="审查通过"
            )
            self._archive_if_terminal(work_id)
        elif review.recommended_action == "返工":
            self._repository.transition(
                work_id, WorkUnitStatus.NEEDS_REWORK, actor_role="scheduler", reason="审查不通过，需返工"
            )
            # MVP 第 25 项: review 问题转任务 — 保存返工请求到 evidence
            rework_request = self._review_mgr.create_rework_request(review)
            if rework_request:
                import json
                rework_path = self._repository._ralph_dir / "evidence" / work_id / "rework_request.json"
                rework_path.parent.mkdir(parents=True, exist_ok=True)
                rework_path.write_text(json.dumps(rework_request, indent=2, ensure_ascii=False))
        else:
            self._repository.transition(
                work_id, WorkUnitStatus.BLOCKED, actor_role="scheduler", reason=f"审查结论: {review.recommended_action}"
            )
            self._archive_if_terminal(work_id)

        return review

    def get_work_unit(self, work_id: str) -> WorkUnit | None:
        return self._repository.get_work_unit(work_id)

    def list_work_units(self, status: WorkUnitStatus | None = None) -> list[WorkUnit]:
        return self._repository.list_work_units(status)

    # ── Reflect 闭环 ─────────────────────────────────────────

    def _collect_retro_lessons(self, unit: WorkUnit) -> list[str]:
        """基于 WorkUnit 关键词查询相关历史教训。"""
        if self._knowledge_graph is None:
            return []

        lessons: list[str] = []

        # L2: 图谱影响面检索 — 如果 scope_allow 包含文件路径，查询影响面
        for file_path in (unit.scope_allow or []):
            impact = self._knowledge_graph.query_impact(file_path, max_depth=2)
            if impact.get("found"):
                for task in impact.get("direct_tasks", []):
                    if task.get("status") in ("failed", "needs_rework"):
                        lessons.append(
                            f"[图谱影响面] {task.get('label', '')} "
                            f"曾因修改 {file_path} 而{task.get('status', '')}"
                        )

        # L1: 关键词匹配历史教训
        text = f"{unit.title} {unit.target}".lower()
        topic_map: dict[str, list[str]] = {
            "timeout": ["超时", "timeout", "render", "加载"],
            "rework": ["返工", "重构", "修改"],
            "scope_violation": ["scope", "范围", "边界"],
            "test_failure": ["测试", "test", "验证"],
        }
        matched_topics: list[str] = []
        for topic, phrases in topic_map.items():
            if any(p in text for p in phrases):
                matched_topics.append(topic)
        matched_topics.append("rework")  # 通用防返工

        for topic in set(matched_topics):
            results = self._knowledge_graph.query_retros_by_topic(topic)
            for r in results:
                lesson = r.get("lesson", "")
                if lesson:
                    severity = r.get("severity", "")
                    lessons.append(
                        f"[历史教训:{topic}] {lesson}"
                        + (f" (级别:{severity})" if severity else "")
                    )

        if lessons:
            logger.info("WorkUnit %s: 注入 %d 条历史教训", unit.work_id, len(lessons))
        return lessons

    def _apply_retro_tuning(self, unit_dict: dict, exec_log: str) -> None:
        """Retro 完成后自动调参，保存调整建议。"""
        if self._memory is None or self._memory._retro_service is None:
            return

        keywords = [
            unit_dict.get("work_type", ""),
            unit_dict.get("title", "")[:20],
        ]
        adjustments = self._memory._retro_service.auto_tune_params(keywords)
        if adjustments:
            self._config_mgr.save_tuning(adjustments)
            logger.info("Retro 自动调参已保存: %s", adjustments)

    def _apply_tuning_to_unit(self, unit: Any, tuning: dict) -> None:
        """将历史调参建议应用到当前 WorkUnit 的执行配置。

        Args:
            unit: WorkUnit 实例
            tuning: load_tuning() 返回的调参 dict
        """
        # timeout 倍增 — 针对历史超时频发的任务类型
        timeout_multiplier = tuning.get("timeout_multiplier")
        if timeout_multiplier and timeout_multiplier > 1.0 and unit.task_harness:
            original_timeout = unit.task_harness.timeout or 300
            unit.task_harness.timeout = int(original_timeout * timeout_multiplier)
            logger.info("调参应用: timeout %d → %d (×%.1f)", original_timeout, unit.task_harness.timeout, timeout_multiplier)

        # 启用中间检查 — 针对历史频繁返工的任务
        if tuning.get("enable_intermediate_checks") and unit.task_harness:
            unit.task_harness.intermediate_checks = True
            logger.info("调参应用: 启用中间检查")

        # 严格 scope 限制 — 针对历史频繁越界
        if tuning.get("strict_scope_enforcement"):
            if unit.task_harness and unit.task_harness.scope_allow:
                # scope_allow 已有值时，不做额外收紧（避免过度约束）
                pass
            elif not unit.scope_allow:
                # 无显式 scope_allow 时，收紧为项目目录
                unit.scope_allow = [str(self._project_dir)]
                logger.info("调参应用: 启用严格 scope 限制")

    def _create_retro_follow_ups(self, retro_record: Any) -> None:
        """基于 Retro 自动生成 follow-up WorkUnit 并保存。"""
        if retro_record is None or self._memory is None:
            return

        retro_service = getattr(self._memory, "_retro_service", None)
        if retro_service is None:
            return

        if not hasattr(retro_service, "create_follow_up_work_units"):
            return

        follow_ups = retro_service.create_follow_up_work_units(retro_record)
        if follow_ups:
            import json
            follow_up_path = self._ralph_dir / "follow_ups"
            follow_up_path.mkdir(parents=True, exist_ok=True)

            for fu in follow_ups:
                work_id = fu.get("work_id", "")
                fu_path = follow_up_path / f"{work_id}.json"
                fu_path.write_text(json.dumps(fu, indent=2, ensure_ascii=False))
                logger.info("Retro follow-up WorkUnit 已保存: %s", work_id)
