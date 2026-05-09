"""Ralph Command Handler — 处理 WorkUnit 相关的命令。

将审批中心的用户操作转换为 WorkUnit 状态转换。
支持命令：accept_review, request_rework, override_accept, expand_scope,
          resolve_blocker, retry_work_unit, cancel_work_unit,
          prepare_work_unit, execute_work_unit, dangerous_op_confirm。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from core.state_models import Command
from ralph.config_manager import RalphConfigManager
from ralph.parallel_executor import ParallelOrchestrator
from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus

logger = logging.getLogger(__name__)


class RalphCommandHandler:
    """处理 Ralph WorkUnit 相关命令。"""

    def __init__(self, ralph_dir: Path, engine: Any = None) -> None:
        self._ralph_dir = Path(ralph_dir)
        self._repository = RalphRepository(self._ralph_dir)
        self._engine = engine

    def handle(self, command: Command) -> dict[str, Any]:
        """处理 Ralph 命令，返回结果字典。

        Args:
            command: 包含 type, target_id, payload 的 Command

        Returns:
            {"success": bool, "message": str, "work_id": str, "new_status": str}
        """
        cmd_type = command.type
        work_id = command.target_id
        payload = command.payload or {}

        logger.info("处理 Ralph 命令: %s, work_id: %s", cmd_type, work_id)

        # 对于 prepare_work_unit 和管理类命令，work_id 可以为空或不校验
        if cmd_type not in ("prepare_work_unit", "retro", "ship", "register_rule"):
            unit = self._repository.get_work_unit(work_id)
            if unit is None:
                return {
                    "success": False,
                    "message": f"WorkUnit {work_id} 不存在",
                    "work_id": work_id,
                    "new_status": None,
                }

        try:
            handler_map = {
                "accept_review": self._handle_accept_review,
                "request_rework": self._handle_request_rework,
                "override_accept": self._handle_override_accept,
                "expand_scope": self._handle_expand_scope,
                "dangerous_op_confirm": self._handle_dangerous_op_confirm,
                "resolve_blocker": self._handle_resolve_blocker,
                "retry_work_unit": self._handle_retry_work_unit,
                "cancel_work_unit": self._handle_cancel_work_unit,
                "prepare_work_unit": self._handle_prepare_work_unit,
                "execute_work_unit": self._handle_execute_work_unit,
                "dispatch_parallel": self._handle_dispatch_parallel,
                "browse": self._handle_browse,
                "retro": self._handle_retro,
                "ship": self._handle_ship,
                "register_rule": self._handle_register_rule,
            }

            handler = handler_map.get(cmd_type)
            if handler is None:
                return {
                    "success": False,
                    "message": f"未知的 Ralph 命令类型: {cmd_type}",
                    "work_id": work_id,
                    "new_status": None,
                }

            # execute_work_unit 和 dispatch_parallel 需要 async 支持
            if cmd_type in ("execute_work_unit", "dispatch_parallel"):
                return self._run_async(handler, work_id, payload)
            return handler(work_id, payload)
        except Exception as e:
            logger.error("处理 Ralph 命令失败: %s", e)
            current = self._repository.get_work_unit(work_id)
            return {
                "success": False,
                "message": str(e),
                "work_id": work_id,
                "new_status": current.status.value if current else None,
            }

    @staticmethod
    def _run_async(handler, work_id: str, payload: dict) -> dict[str, Any]:
        """在子线程中运行 async handler，避免死锁。"""
        def _target():
            return asyncio.run(handler(work_id, payload))
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_target)
            return fut.result(timeout=300)

    # ------------------------------------------------------------------
    # 审查相关命令
    # ------------------------------------------------------------------

    def _handle_accept_review(self, work_id: str, payload: dict) -> dict[str, Any]:
        """接受审查结果：needs_review → accepted。"""
        unit = self._repository.get_work_unit(work_id)
        if unit.status != WorkUnitStatus.NEEDS_REVIEW:
            return {
                "success": False,
                "message": f"WorkUnit 当前状态为 {unit.status.value}，无法执行 accept_review",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        feedback = payload.get("feedback", "审查通过")
        new_unit = self._repository.transition(
            work_id, WorkUnitStatus.ACCEPTED, actor_role="scheduler", reason=feedback
        )

        return {
            "success": True,
            "message": "审查已接受",
            "work_id": work_id,
            "new_status": new_unit.status.value,
        }

    def _handle_request_rework(self, work_id: str, payload: dict) -> dict[str, Any]:
        """请求返工：needs_review → needs_rework。"""
        unit = self._repository.get_work_unit(work_id)
        if unit.status != WorkUnitStatus.NEEDS_REVIEW:
            return {
                "success": False,
                "message": f"WorkUnit 当前状态为 {unit.status.value}，无法执行 request_rework",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        reason = payload.get("reason", "需要返工")
        new_unit = self._repository.transition(
            work_id, WorkUnitStatus.NEEDS_REWORK, actor_role="scheduler", reason=reason
        )

        return {
            "success": True,
            "message": f"已请求返工: {reason}",
            "work_id": work_id,
            "new_status": new_unit.status.value,
        }

    def _handle_override_accept(self, work_id: str, payload: dict) -> dict[str, Any]:
        """强制接受（覆盖审查结果）：任意状态 → accepted。"""
        reason = payload.get("reason", "PM 强制接受")

        unit = self._repository.get_work_unit(work_id)
        new_unit = replace(unit, status=WorkUnitStatus.ACCEPTED)
        self._repository.save_work_unit(new_unit)

        logger.info("PM 强制接受 WorkUnit %s: %s", work_id, reason)

        return {
            "success": True,
            "message": f"已强制接受: {reason}",
            "work_id": work_id,
            "new_status": WorkUnitStatus.ACCEPTED.value,
        }

    # ------------------------------------------------------------------
    # 范围扩展命令
    # ------------------------------------------------------------------

    def _handle_expand_scope(self, work_id: str, payload: dict) -> dict[str, Any]:
        """扩展范围请求：记录扩展请求，等待确认。"""
        scope_additions = payload.get("scope_additions", [])
        reason = payload.get("reason", "")

        logger.info("WorkUnit %s 范围扩展请求: %s, 原因: %s", work_id, scope_additions, reason)

        from ralph.schema.blocker import Blocker

        blocker = Blocker(
            blocker_id=f"scope_expand_{work_id}_{int(time.time())}",
            work_id=work_id,
            blocker_type="scope_expansion_pending",
            reason=f"范围扩展请求: {reason}",
        )
        self._repository.save_blocker(blocker)

        return {
            "success": True,
            "message": "范围扩展请求已记录，等待确认",
            "work_id": work_id,
            "new_status": self._repository.get_work_unit(work_id).status.value,
            "blocker_id": blocker.blocker_id,
        }

    # ------------------------------------------------------------------
    # 危险操作确认
    # ------------------------------------------------------------------

    def _handle_dangerous_op_confirm(self, work_id: str, payload: dict) -> dict[str, Any]:
        """确认危险操作：解除 blocker 并继续执行。"""
        blocker_id = payload.get("blocker_id", "")
        confirmed = payload.get("confirmed", True)

        if blocker_id:
            blocker = self._repository.get_blocker(blocker_id)
            if blocker is not None:
                updated_blocker = replace(
                    blocker,
                    resolved=True,
                    resolution="confirmed" if confirmed else "cancelled",
                )
                self._repository.save_blocker(updated_blocker)

        if confirmed:
            unit = self._repository.get_work_unit(work_id)
            if unit.status == WorkUnitStatus.BLOCKED:
                new_unit = self._repository.transition(
                    work_id, WorkUnitStatus.READY, actor_role="scheduler", reason="危险操作已确认"
                )
                return {
                    "success": True,
                    "message": "危险操作已确认，继续执行",
                    "work_id": work_id,
                    "new_status": new_unit.status.value,
                }

        return {
            "success": True,
            "message": "危险操作已取消" if not confirmed else "危险操作已处理",
            "work_id": work_id,
            "new_status": self._repository.get_work_unit(work_id).status.value,
        }

    # ------------------------------------------------------------------
    # 阻塞解决（统一入口，替代旧的六个分散处理器）
    # ------------------------------------------------------------------

    def _handle_resolve_blocker(self, work_id: str, payload: dict) -> dict[str, Any]:
        """解决阻塞项 — 统一入口。

        支持 payload 字段：
        - blocker_id: 要解决的 blocker ID
        - resolution: 'approve' | 'reject' | 'retry' | 'skip' | 'abort' | 'resume'
        - reason: 解决原因说明
        - 其他类型特定字段
        """
        blocker_id = payload.get("blocker_id", "")
        resolution = payload.get("resolution", "approve")
        reason = payload.get("reason", "")

        unit = self._repository.get_work_unit(work_id)

        # 先标记 blocker 为已解决
        if blocker_id:
            blocker = self._repository.get_blocker(blocker_id)
            if blocker is not None:
                updated = replace(blocker, resolved=True, resolution=resolution)
                self._repository.save_blocker(updated)

        # 根据 resolution 执行状态转换
        if resolution == "approve":
            # 批准后续操作：解除阻塞 → ready
            if unit.status == WorkUnitStatus.BLOCKED:
                new_unit = self._repository.transition(
                    work_id, WorkUnitStatus.READY, actor_role="scheduler", reason=f"阻塞已批准: {reason}"
                )
                return {
                    "success": True,
                    "message": "阻塞已批准，继续执行",
                    "work_id": work_id,
                    "new_status": new_unit.status.value,
                }

        elif resolution == "reject":
            # 拒绝：保持当前状态或标记为 failed
            if unit.status == WorkUnitStatus.BLOCKED:
                new_unit = replace(unit, status=WorkUnitStatus.FAILED)
                self._repository.save_work_unit(new_unit)
                return {
                    "success": True,
                    "message": f"阻塞已拒绝: {reason}",
                    "work_id": work_id,
                    "new_status": WorkUnitStatus.FAILED.value,
                }

        elif resolution == "retry":
            # 重试：blocked → ready
            if unit.status in (WorkUnitStatus.BLOCKED, WorkUnitStatus.FAILED):
                new_unit = self._repository.transition(
                    work_id, WorkUnitStatus.READY, actor_role="scheduler", reason=f"重试: {reason}"
                )
                return {
                    "success": True,
                    "message": "已标记为重新执行",
                    "work_id": work_id,
                    "new_status": new_unit.status.value,
                }

        elif resolution == "skip":
            # 跳过阻塞：强制接受
            new_unit = replace(unit, status=WorkUnitStatus.ACCEPTED)
            self._repository.save_work_unit(new_unit)
            return {
                "success": True,
                "message": f"已跳过阻塞: {reason}",
                "work_id": work_id,
                "new_status": WorkUnitStatus.ACCEPTED.value,
            }

        elif resolution == "abort":
            # 中止执行
            new_unit = replace(unit, status=WorkUnitStatus.FAILED)
            self._repository.save_work_unit(new_unit)
            return {
                "success": True,
                "message": f"已中止执行: {reason}",
                "work_id": work_id,
                "new_status": WorkUnitStatus.FAILED.value,
            }

        elif resolution == "resume":
            # 恢复执行
            if unit.status == WorkUnitStatus.BLOCKED:
                new_unit = self._repository.transition(
                    work_id, WorkUnitStatus.READY, actor_role="scheduler", reason=f"恢复执行: {reason}"
                )
                return {
                    "success": True,
                    "message": "已恢复执行",
                    "work_id": work_id,
                    "new_status": new_unit.status.value,
                }

        return {
            "success": True,
            "message": f"阻塞已处理: {resolution}",
            "work_id": work_id,
            "new_status": unit.status.value,
        }

    # ------------------------------------------------------------------
    # 执行控制命令
    # ------------------------------------------------------------------

    def _handle_prepare_work_unit(self, work_id: str, payload: dict) -> dict[str, Any]:
        """准备 WorkUnit 执行：确保上下文和 harness 就绪。

        如果 work_id 为空但 payload 中有完整 WorkUnit 数据，则创建新的 WorkUnit。
        如果 work_id 已有对应的 draft WorkUnit，则调用引擎预检，将其置为 ready。
        """
        # 情况1: 从 payload 创建新 WorkUnit
        if not work_id and payload.get("title"):
            return self._create_work_unit_from_payload(payload)

        # 情况2: 将已有 draft 置为 ready
        unit = self._repository.get_work_unit(work_id)
        if unit is None:
            return {
                "success": False,
                "message": f"WorkUnit {work_id} 不存在",
                "work_id": work_id,
                "new_status": None,
            }

        if unit.status == WorkUnitStatus.DRAFT:
            if self._engine is not None:
                try:
                    self._engine.prepare(work_id)
                    new_unit = self._repository.get_work_unit(work_id)
                    return {
                        "success": True,
                        "message": "WorkUnit 通过预检，已标记为 ready",
                        "work_id": work_id,
                        "new_status": new_unit.status.value,
                    }
                except ValueError as e:
                    return {
                        "success": False,
                        "message": f"WorkUnit 预检失败: {e}",
                        "work_id": work_id,
                        "new_status": unit.status.value,
                    }

            new_unit = self._repository.transition(
                work_id, WorkUnitStatus.READY, actor_role="scheduler", reason="WorkUnit 已准备就绪"
            )
            return {
                "success": True,
                "message": "WorkUnit 已标记为 ready",
                "work_id": work_id,
                "new_status": new_unit.status.value,
            }

        if unit.status == WorkUnitStatus.READY:
            return {
                "success": True,
                "message": "WorkUnit 已处于 ready 状态",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        return {
            "success": False,
            "message": f"WorkUnit 当前状态为 {unit.status.value}，无法准备",
            "work_id": work_id,
            "new_status": unit.status.value,
        }

    def _create_work_unit_from_payload(self, payload: dict) -> dict[str, Any]:
        """从 payload 创建新的 WorkUnit。"""
        from ralph.schema.work_unit import WorkUnit

        work_id = payload.get("work_id", f"W_{int(time.time())}")
        new_unit = WorkUnit(
            work_id=work_id,
            work_type=payload.get("work_type", "development"),
            title=payload.get("title", "Untitled"),
            background=payload.get("background", ""),
            target=payload.get("target", ""),
            scope_allow=payload.get("scope_allow", []),
            scope_deny=payload.get("scope_deny", []),
            dependencies=payload.get("dependencies", []),
            input_files=payload.get("input_files", []),
            expected_output=payload.get("expected_output", ""),
            acceptance_criteria=payload.get("acceptance_criteria", []),
            test_command=payload.get("test_command", ""),
            rollback_strategy=payload.get("rollback_strategy", ""),
            task_harness=payload.get("task_harness"),
            context_pack=payload.get("context_pack"),
            assumptions=payload.get("assumptions", []),
            impact_if_wrong=payload.get("impact_if_wrong", ""),
            risk_notes=payload.get("risk_notes", ""),
            status=WorkUnitStatus.DRAFT,
            producer_role=payload.get("producer_role", ""),
            reviewer_role=payload.get("reviewer_role", ""),
        )
        self._repository.save_work_unit(new_unit)

        return {
            "success": True,
            "message": f"WorkUnit {work_id} 已创建",
            "work_id": work_id,
            "new_status": WorkUnitStatus.DRAFT.value,
        }

    async def _handle_execute_work_unit(self, work_id: str, payload: dict) -> dict[str, Any]:
        """执行 WorkUnit：ready → running → 实际执行。"""
        unit = self._repository.get_work_unit(work_id)

        if unit.status != WorkUnitStatus.READY:
            return {
                "success": False,
                "message": f"WorkUnit 当前状态为 {unit.status.value}，需要 ready 状态才能执行",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        if self._engine is None:
            # 无引擎时仅做状态转换（兼容旧模式）
            force = payload.get("force", False)
            reason = payload.get("reason", "开始执行" if not force else "强制执行")
            new_unit = self._repository.transition(
                work_id, WorkUnitStatus.RUNNING, actor_role="scheduler", reason=reason
            )
            logger.info("WorkUnit %s 已开始执行（无引擎）", work_id)
            return {
                "success": True,
                "message": "WorkUnit 已开始执行（未实际运行）",
                "work_id": work_id,
                "new_status": new_unit.status.value,
            }

        # 通过引擎执行：ready → running → needs_review
        try:
            result = await self._engine.execute(work_id)
            new_unit = self._repository.get_work_unit(work_id)
            logger.info("WorkUnit %s 执行完成: %s", work_id, result)
            return {
                "success": True,
                "message": "WorkUnit 执行完成",
                "work_id": work_id,
                "new_status": new_unit.status.value,
                "execution_result": result,
            }
        except Exception as e:
            logger.error("WorkUnit %s 执行失败: %s", work_id, e)
            return {
                "success": False,
                "message": f"WorkUnit 执行失败: {e}",
                "work_id": work_id,
                "new_status": WorkUnitStatus.FAILED.value,
            }

    def _handle_retry_work_unit(self, work_id: str, payload: dict) -> dict[str, Any]:
        """重试 WorkUnit：failed/needs_rework/blocked → ready。

        合并了旧的 execution_error_handle（retry 分支）逻辑。
        """
        unit = self._repository.get_work_unit(work_id)
        allowed_states = (WorkUnitStatus.FAILED, WorkUnitStatus.NEEDS_REWORK, WorkUnitStatus.BLOCKED)

        if unit.status not in allowed_states:
            return {
                "success": False,
                "message": f"WorkUnit 当前状态为 {unit.status.value}，无法重试（需为 failed/needs_rework/blocked）",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        reason = payload.get("reason", "重试任务")
        new_unit = self._repository.transition(
            work_id, WorkUnitStatus.READY, actor_role="scheduler", reason=f"重试: {reason}"
        )

        # 同时解决关联的 blocker
        blocker_id = payload.get("blocker_id", "")
        if blocker_id:
            blocker = self._repository.get_blocker(blocker_id)
            if blocker is not None:
                updated = replace(blocker, resolved=True, resolution="retry")
                self._repository.save_blocker(updated)

        return {
            "success": True,
            "message": "WorkUnit 已标记为重新执行",
            "work_id": work_id,
            "new_status": new_unit.status.value,
        }

    def _handle_cancel_work_unit(self, work_id: str, payload: dict) -> dict[str, Any]:
        """取消 WorkUnit：任意非终态 → failed。"""
        unit = self._repository.get_work_unit(work_id)
        terminal_states = (WorkUnitStatus.ACCEPTED, WorkUnitStatus.FAILED)

        if unit.status in terminal_states:
            return {
                "success": False,
                "message": f"WorkUnit 已处于终态 {unit.status.value}，无法取消",
                "work_id": work_id,
                "new_status": unit.status.value,
            }

        reason = payload.get("reason", "任务已取消")
        new_unit = replace(unit, status=WorkUnitStatus.FAILED)
        self._repository.save_work_unit(new_unit)

        logger.info("WorkUnit %s 已取消: %s", work_id, reason)

        return {
            "success": True,
            "message": f"WorkUnit 已取消: {reason}",
            "work_id": work_id,
            "new_status": WorkUnitStatus.FAILED.value,
        }

    async def _handle_dispatch_parallel(self, work_id: str, payload: dict) -> dict[str, Any]:
        """并行执行所有 ready 状态的 WorkUnit。"""
        ready_units = self._repository.list_work_units(WorkUnitStatus.READY)
        if not ready_units:
            return {"success": False, "message": "没有 ready 状态的 WorkUnit", "work_id": work_id}

        max_parallel = payload.get("max_parallel", 5)
        prd_summary = payload.get("prd_summary", "")

        # ParallelOrchestrator 需要 project_dir（repo 的父级）
        project_dir = self._ralph_dir.parent

        # 加载 Agent 定义（角色 max_instances 用于分配并发）
        cfg = RalphConfigManager(self._ralph_dir)
        agent_defs = cfg.list_agent_definitions_raw()

        orchestrator = ParallelOrchestrator(
            repo_dir=project_dir,
            max_parallel=max_parallel,
            work_unit_engine=self._engine,
            agent_definitions=agent_defs,
        )

        try:
            result = await orchestrator.dispatch_work_units(ready_units, prd_summary=prd_summary)
            return {
                "success": result.get("success", False),
                "message": f"并行执行完成: {result.get('tasks_completed', 0)} 个任务",
                "work_id": work_id,
                "result": result,
            }
        except Exception as e:
            logger.error("并行执行失败: %s", e)
            return {"success": False, "message": f"并行执行失败: {e}", "work_id": work_id}

    async def _handle_browse(self, work_id: str, payload: dict) -> dict[str, Any]:
        """通过 PersistentBrowser 执行前端页面浏览/截图/验证。

        payload 支持:
          - url: 要访问的页面 URL（必需）
          - action: browse | screenshot | click | fill（默认 browse）
          - selector: CSS 选择器（click/fill 时必需）
          - value: 表单填充值（fill 时必需）
          - baseline_name: 基线截图名称（用于对比）
          - compare: 是否与基线对比（默认 False）
        """
        from ralph.persistent_browser import PersistentBrowser

        url = payload.get("url", "")
        if not url:
            return {"success": False, "message": "缺少 url 参数", "work_id": work_id}

        action = payload.get("action", "browse")
        selector = payload.get("selector", "")
        value = payload.get("value", "")
        baseline_name = payload.get("baseline_name", "")
        compare = payload.get("compare", False)

        user_data_dir = str(self._ralph_dir / "browser-profile")
        browser = PersistentBrowser(user_data_dir=user_data_dir)

        try:
            await browser.start()
            await browser.start_health_monitor(interval_seconds=60, target_url=url)
            page = await browser.get_page()
            await page.goto(url, wait_until="networkidle")

            result: dict[str, Any] = {"url": url, "action": action}

            if action == "screenshot" or action == "browse":
                shot_path = await browser.take_screenshot(
                    baseline_name or f"work_{work_id}",
                    page=page,
                )
                result["screenshot"] = shot_path

                if compare and baseline_name:
                    diff = await browser.compare_screenshot(baseline_name, page=page)
                    result["diff"] = diff.to_dict()

            elif action == "click":
                if not selector:
                    return {"success": False, "message": "click 操作需要 selector", "work_id": work_id}
                await page.click(selector)
                result["clicked"] = selector
                shot_path = await browser.take_screenshot(f"click_{work_id}", page=page)
                result["screenshot"] = shot_path

            elif action == "fill":
                if not selector or not value:
                    return {"success": False, "message": "fill 操作需要 selector 和 value", "work_id": work_id}
                await page.fill(selector, value)
                result["filled"] = {"selector": selector, "value": value}
                shot_path = await browser.take_screenshot(f"fill_{work_id}", page=page)
                result["screenshot"] = shot_path

            elif action == "save_baseline":
                if not baseline_name:
                    return {"success": False, "message": "save_baseline 需要 baseline_name", "work_id": work_id}
                path = await browser.save_baseline(baseline_name, page=page)
                result["baseline"] = path

            else:
                return {"success": False, "message": f"不支持的操作: {action}", "work_id": work_id}

            return {"success": True, "message": f"浏览完成: {action} @ {url}", "work_id": work_id, "result": result}

        except Exception as e:
            logger.error("浏览操作失败: %s", e)
            return {"success": False, "message": f"浏览操作失败: {e}", "work_id": work_id}
        finally:
            await browser.close()

    # ------------------------------------------------------------------
    # 反思回顾命令
    # ------------------------------------------------------------------

    def _handle_retro(self, work_id: str, payload: dict) -> dict[str, Any]:
        """反思回顾管理：list / summary / detail。

        payload 支持:
          - action: list | summary | detail（默认 list）
          - limit: 返回数量限制（默认 10）
          - period: 汇总周期 week | month（默认 week）
          - work_id: 查看某条 retro（detail 模式）
        """
        from ralph.memory_manager import MemoryManager

        action = payload.get("action", "list")

        try:
            mgr = MemoryManager(self._ralph_dir)
        except Exception as e:
            return {"success": False, "message": f"MemoryManager 初始化失败: {e}", "work_id": work_id}

        if action == "list":
            limit = payload.get("limit", 10)
            retros = mgr.get_recent_retros(limit=limit)
            return {
                "success": True,
                "message": f"最近 {len(retros)} 条 retro 记录",
                "work_id": work_id,
                "data": retros,
            }

        if action == "summary":
            period = payload.get("period", "week")
            summary = mgr.get_retro_summary(period=period)
            return {
                "success": True,
                "message": f"{period} retro 汇总",
                "work_id": work_id,
                "data": summary,
            }

        if action == "detail":
            detail_work_id = payload.get("work_id", work_id)
            retro = self._repository.get_retro(detail_work_id)
            if retro is None:
                return {
                    "success": False,
                    "message": f"未找到 {detail_work_id} 的 retro 记录",
                    "work_id": work_id,
                }
            return {
                "success": True,
                "message": f"{detail_work_id} retro 详情",
                "work_id": work_id,
                "data": self._repository._serialize_retro(retro),
            }

        return {
            "success": False,
            "message": f"未知的 retro 操作: {action}",
            "work_id": work_id,
        }

    # ------------------------------------------------------------------
    # 发布命令
    # ------------------------------------------------------------------

    def _handle_ship(self, work_id: str, payload: dict) -> dict[str, Any]:
        """发布 WorkUnit：创建发布分支、打 tag、生成 changelog。

        payload 支持:
          - strategy: patch | minor | major（默认 patch）
          - tag_prefix: tag 前缀（默认 v）
        """
        from ralph.ship_service import ShipService

        strategy = payload.get("strategy", "patch")
        tag_prefix = payload.get("tag_prefix", "v")

        project_dir = self._ralph_dir.parent
        svc = ShipService(self._ralph_dir, project_dir)

        # 支持预验证模式
        dry_run = payload.get("dry_run", False)
        if dry_run:
            blockers = svc.verify_pre_ship(work_id)
            if blockers:
                return {
                    "success": False,
                    "message": "发布前验证未通过",
                    "work_id": work_id,
                    "blockers": blockers,
                }
            return {
                "success": True,
                "message": "发布前验证通过",
                "work_id": work_id,
            }

        result = svc.ship_work_unit(
            work_id,
            strategy=strategy,
            tag_prefix=tag_prefix,
            push_remote=payload.get("push_remote", False),
            create_pr_flag=payload.get("create_pr", False),
            pr_base=payload.get("pr_base", "main"),
        )

        return {
            "success": result.success,
            "message": result.message,
            "work_id": work_id,
            "tag": result.tag,
            "branch": result.branch,
            "changelog_path": result.changelog_path,
            "pr_url": result.pr_url,
            "pushed": result.pushed,
        }

    # ------------------------------------------------------------------
    # 规则注册命令
    # ------------------------------------------------------------------

    def _handle_register_rule(self, work_id: str, payload: dict) -> dict[str, Any]:
        """注册自定义规则到规则引擎。

        payload 支持:
          - rule_id: 规则唯一标识
          - dimension: 所属评审维度
          - rule_name: 规则名称
          - action: register | list | count
          - list_dimension: 列出指定维度的规则（list/count 模式）
        """
        from ralph.rules_engine import RulesEngine, register_builtin_rules

        action = payload.get("action", "list")
        engine = RulesEngine()
        register_builtin_rules(engine)

        if action == "register":
            return {
                "success": False,
                "message": "规则注册需要通过 Python API 完成，不支持命令行动态注册",
                "work_id": work_id,
            }

        if action == "list":
            dimension = payload.get("list_dimension")
            rules = engine.list_rules(dimension)
            return {
                "success": True,
                "message": f"已注册 {len(rules)} 条规则" + (f" [{dimension}]" if dimension else ""),
                "work_id": work_id,
                "rules": [{"id": r.id, "dimension": r.dimension, "name": r.name} for r in rules],
            }

        if action == "count":
            dimension = payload.get("list_dimension")
            count = engine.rule_count(dimension)
            return {
                "success": True,
                "message": f"已注册 {count} 条规则" + (f" [{dimension}]" if dimension else ""),
                "work_id": work_id,
                "count": count,
            }

        return {
            "success": False,
            "message": f"未知的 register_rule 操作: {action}",
            "work_id": work_id,
        }
