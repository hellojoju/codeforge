"""Dashboard REST API 路由和 WebSocket 端点 — 接入 ProjectStateRepository + CommandProcessor + CommandConsumer。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import threading
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.product_manager import ProductManager
    from dashboard.coordinator import PMCoordinator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from dashboard.command_processor import CommandProcessor
from dashboard.consumer import CommandConsumer
from dashboard.event_bus import EventBus
from dashboard.models import ChatMessage, Command, Event, ModuleAssignment
from dashboard.state_repository import ProjectStateRepository
from ralph.config_manager import RalphConfigManager
from ralph.report_generator import ReportGenerator
from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class _DashboardAppState:
    """存储在 app.state 中的 WebSocket 连接和广播队列。"""

    def __init__(self) -> None:
        self.connected_ws: set[WebSocket] = set()
        self.broadcast_queue: deque[dict] = deque()


def _emit_to_ws(broadcast_queue: deque, event: Event) -> None:
    """将 Repository 事件推入 WebSocket 广播队列。"""
    payload = {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "project_id": event.project_id,
        "run_id": event.run_id,
        "type": event.type,
        "payload": event.payload,
        "timestamp": event.timestamp or _now_iso(),
        "caused_by_command_id": event.caused_by_command_id,
    }
    broadcast_queue.append(payload)


def _event_to_stream_item(event: Event) -> dict[str, Any]:
    payload = event.payload or {}
    event_agent_id = payload.get("agent_id") or payload.get("assigned_agent_id")
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        if event.type == "blocking_issue_created":
            message = payload.get("description", "阻塞问题已创建")
        elif event.type == "feature_updated":
            message = f"Feature {payload.get('feature_id', '')} -> {payload.get('status', '')}".strip()
        else:
            message = event.type
    severity = "info"
    if "blocked" in event.type or "failed" in event.type or "error" in event.type:
        severity = "error"
    elif "warning" in event.type or "reject" in event.type:
        severity = "warning"
    return {
        "id": str(event.event_id),
        "timestamp": event.timestamp,
        "type": event.type,
        "agent_id": event_agent_id,
        "feature_id": payload.get("feature_id"),
        "message": message,
        "severity": severity,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 CommandConsumer 后台轮询循环。"""
    consumer: CommandConsumer = app.state.consumer
    stop_event = asyncio.Event()

    async def consumer_loop() -> None:
        while not stop_event.is_set():
            try:
                n = consumer.process_once()
                if n > 0:
                    logger.info(f"CommandConsumer processed {n} command(s)")
            except Exception:
                logger.exception("CommandConsumer error")
            await asyncio.sleep(0.5)

    task = asyncio.create_task(consumer_loop())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_dashboard_app(
    event_bus: EventBus,
    repository: ProjectStateRepository | None = None,
    coordinator: "PMCoordinator | None" = None,  # noqa: UP037
    product_manager: "ProductManager | None" = None,  # noqa: UP037
    ralph_repository: RalphRepository | None = None,
    ralph_engine: Any = None,  # WorkUnitEngine | None
) -> FastAPI:
    app = FastAPI(title="CodeForge", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app_state = _DashboardAppState()
    app.state.connected_ws = app_state.connected_ws
    app.state.broadcast_queue = app_state.broadcast_queue
    app.state.event_bus = event_bus

    # 注入 RalphRepository
    if ralph_repository is None:
        ralph_dir = Path(os.environ.get("RALPH_DIR", ".ralph"))
        ralph_repository = RalphRepository(ralph_dir)
    app.state.ralph_repository = ralph_repository

    # 注入 WorkUnitEngine（如果未提供则从 project_dir 初始化）
    if ralph_engine is None:
        project_dir_env = os.environ.get("PROJECT_DIR")
        if project_dir_env:
            from ralph.work_unit_engine import WorkUnitEngine

            ralph_engine = WorkUnitEngine(Path(project_dir_env))
    app.state.ralph_engine = ralph_engine

    # 注入 ReportGenerator
    report_generator = ReportGenerator(ralph_repository._ralph_dir)
    app.state.report_generator = report_generator

    # 注入 ConfigManager
    config_manager = RalphConfigManager(ralph_repository._ralph_dir)
    app.state.config_manager = config_manager

    # 注入 Repository
    if repository is None:
        _tmp_dir = tempfile.mkdtemp(prefix="dashboard_state_")
        repository = ProjectStateRepository(
            base_dir=Path(_tmp_dir),
            project_id="default",
            run_id="",
        )
    app.state.repository = repository

    # 桥接 EventBus → WebSocket broadcast_queue
    # EventBus 只负责内存队列（保持向后兼容），Repository 持久化在桥接层显式完成
    _original_emit = event_bus.emit
    def _wrapped_emit(event_type: str, **kwargs: Any) -> None:
        _original_emit(event_type, **kwargs)
        stored_event = repository.append_event(type=event_type, payload=kwargs)
        _emit_to_ws(app.state.broadcast_queue, stored_event)
    event_bus.emit = _wrapped_emit

    # 注入 CommandProcessor — 事件统一通过 Repository 追加
    def on_event(event: Event) -> None:
        stored_event = repository.append_event(type=event.type, payload=event.payload)
        _emit_to_ws(app.state.broadcast_queue, stored_event)

    processor = CommandProcessor(on_event=on_event)
    app.state.command_processor = processor

    # 注入 CommandConsumer
    app.state.consumer = CommandConsumer(
        repository=repository,
        processor=processor,
        event_bus=event_bus,
    )

    # 注入 PMCoordinator（可选）
    app.state.coordinator = coordinator

    # 注入 ProductManager（可选，用于对话回复）
    app.state.product_manager = product_manager

    # --- REST: 状态快照 ---

    @app.get("/api/state")
    async def get_state() -> dict:
        """从 Repository 加载统一状态快照。"""
        snapshot = app.state.repository.load_snapshot()
        return {
            "project_name": snapshot.project_name,
            "agents": [a.to_dict() for a in snapshot.agents],
            "features": [f.to_dict() for f in snapshot.features],
            "events": [e.to_dict() for e in app.state.repository.get_events_after(0, limit=200)],
            "chat_history": [m.to_dict() for m in snapshot.chat_history],
        }

    @app.get("/api/dashboard/state")
    async def get_dashboard_state() -> dict:
        """从 Repository 加载统一快照。"""
        snapshot = app.state.repository.load_snapshot()
        return snapshot.to_dict()

    # --- REST: 事件列表 ---

    @app.get("/api/events")
    async def get_events(
        agent_id: str | None = None,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[dict] | dict:
        if agent_id is None and after_id == 0:
            return app.state.event_bus.get_events()

        events = app.state.repository.get_events_after(after_id, limit=max(limit * 5, limit))
        items: list[dict] = []
        for event in events:
            item = _event_to_stream_item(event)
            if agent_id and item.get("agent_id") != agent_id:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"events": items}

    @app.get("/api/dashboard/events")
    async def get_dashboard_events(after_event_id: int = 0, limit: int = 200) -> dict:
        events = app.state.repository.get_events_after(after_event_id, limit)
        return {
            "project_id": app.state.repository._project_id,
            "events": [e.to_dict() for e in events],
        }

    @app.get("/api/blocking-issues")
    async def list_blocking_issues(feature_id: str | None = None, resolved: bool | None = None) -> dict:
        issues = app.state.repository.list_blocking_issues(feature_id=feature_id, resolved=resolved)
        return {
            "issues": [issue.to_dict() for issue in issues],
            "total": len(issues),
        }

    @app.post("/api/blocking-issues/{issue_id}/resolve")
    async def resolve_blocking_issue(issue_id: str, body: dict[str, Any]) -> dict:
        resolution = (body.get("resolution") or "").strip()
        if not resolution:
            raise HTTPException(status_code=422, detail="resolution is required")
        ok = app.state.repository.resolve_blocking_issue(issue_id, resolution)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Blocking issue {issue_id} not found")
        app.state.event_bus.emit("blocking_issue_resolved", issue_id=issue_id, resolution=resolution)
        return {"success": True, "issue_id": issue_id}

    @app.get("/api/execution-ledger")
    async def get_execution_ledger() -> dict:
        ledger_file = app.state.repository._base.parent / "execution-plan.json"
        if not ledger_file.exists():
            return {
                "executions": [],
                "summary": {
                    "total_executions": 0, "completed": 0,
                    "failed": 0, "blocked": 0, "retrying": 0,
                },
            }
        return json.loads(ledger_file.read_text(encoding="utf-8"))

    # --- REST: 用户对话 ---

    @app.post("/api/chat")
    async def post_chat(body: dict[str, Any]) -> dict:
        content = body.get("content", "").strip()
        if not content:
            raise HTTPException(status_code=422, detail="content is required")
        msg = ChatMessage(id=f"chat_{_now_iso()}", role="user", content=content)
        app.state.repository.add_chat_message(msg)
        event = app.state.repository.append_event(
            type="pm_decision", message=f"用户消息: {content}",
        )
        _emit_to_ws(app.state.broadcast_queue, event)

        # 调用 PM 生成回复
        pm_response = _generate_pm_response(
            app.state.repository,
            app.state.broadcast_queue,
            app.state.product_manager,
        )

        return {
            "success": True,
            "message_id": msg.id,
            "pm_response": pm_response.to_dict() if pm_response else None,
        }

    # --- REST: 批准（写为 pending，由 CommandConsumer 消费）---

    @app.post("/api/approve")
    async def post_approve(body: dict[str, Any] | None = None) -> dict:
        body = body or {}
        cmd = _create_command("approve_decision", body)
        cmd.status = "pending"
        app.state.repository.save_command(cmd)
        app.state.repository.append_event(
            type="command_created", command_id=cmd.command_id, cmd_type="approve",
        )
        return {"success": True, "command_id": cmd.command_id, "status": "pending"}

    # --- REST: 驳回（写为 pending，由 CommandConsumer 消费）---

    @app.post("/api/reject")
    async def post_reject(body: dict[str, Any] | None = None) -> dict:
        body = body or {}
        cmd = _create_command("reject_decision", body)
        cmd.status = "pending"
        app.state.repository.save_command(cmd)
        app.state.repository.append_event(
            type="command_created", command_id=cmd.command_id, cmd_type="reject",
        )
        return {"success": True, "command_id": cmd.command_id, "status": "pending"}

    # --- REST: 暂停 ---

    @app.post("/api/pause")
    async def post_pause(body: dict[str, Any]) -> dict:
        agent_id = body.get("agent_id", "")
        repo = app.state.repository
        snapshot = repo.load_snapshot()
        for agent in snapshot.agents:
            if agent.id == agent_id:
                agent.status = "paused"
                repo.upsert_agent(agent)
                event = repo.append_event(
                    type="agent_status_changed", agent_id=agent_id, message="paused",
                )
                _emit_to_ws(app.state.broadcast_queue, event)
                return {"success": True}
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # --- REST: 恢复 ---

    @app.post("/api/resume")
    async def post_resume(body: dict[str, Any]) -> dict:
        agent_id = body.get("agent_id", "")
        repo = app.state.repository
        snapshot = repo.load_snapshot()
        for agent in snapshot.agents:
            if agent.id == agent_id:
                agent.status = "idle"
                repo.upsert_agent(agent)
                event = repo.append_event(
                    type="agent_status_changed", agent_id=agent_id, message="idle",
                )
                _emit_to_ws(app.state.broadcast_queue, event)
                return {"success": True}
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # --- REST: 重试 ---

    @app.post("/api/retry")
    async def post_retry(body: dict[str, Any]) -> dict:
        feature_id = body.get("feature_id", "")
        event = app.state.repository.append_event(type="retry_feature", feature_id=feature_id)
        _emit_to_ws(app.state.broadcast_queue, event)
        return {"success": True}

    # --- REST: 跳过 ---

    @app.post("/api/skip")
    async def post_skip(body: dict[str, Any]) -> dict:
        feature_id = body.get("feature_id", "")
        event = app.state.repository.append_event(type="skip_feature", feature_id=feature_id)
        _emit_to_ws(app.state.broadcast_queue, event)
        return {"success": True}

    # --- REST: 命令创建（新接口）---

    @app.post("/api/dashboard/commands", status_code=202)
    async def create_command_endpoint(body: dict[str, Any]) -> dict:
        idempotency_key = body.get("idempotency_key", "")
        if idempotency_key:
            existing = app.state.repository.get_command_by_idempotency_key(idempotency_key)
            if existing:
                return {
                    "schema_version": 1,
                    "command_id": existing.command_id,
                    "status": existing.status,
                    "was_duplicate": True,
                }

        cmd = _create_command(body.get("type", ""), body)
        cmd.status = "pending"
        app.state.repository.save_command(cmd)
        return {
            "schema_version": 1,
            "command_id": cmd.command_id,
            "status": cmd.status,
            "was_duplicate": False,
        }

    @app.get("/api/dashboard/commands/{command_id}")
    async def get_command(command_id: str) -> dict:
        cmd = app.state.repository.get_command(command_id)
        if not cmd:
            raise HTTPException(status_code=404, detail="Command not found")
        return cmd.to_dict()

    # --- REST: 模块分配 ---

    @app.get("/api/dashboard/modules")
    async def list_modules(role: str | None = None) -> dict:
        """列出所有模块分配，可按角色过滤。"""
        assignments = app.state.repository.list_module_assignments(role=role)
        return {
            "modules": [a.to_dict() for a in assignments],
            "total": len(assignments),
        }

    @app.post("/api/dashboard/modules", status_code=201)
    async def upsert_module(body: dict[str, Any]) -> dict:
        """创建或更新模块分配。"""
        required = ("module_id", "role")
        for field in required:
            if field not in body:
                raise HTTPException(status_code=422, detail=f"Missing required field: {field}")

        assignment = ModuleAssignment(
            module_id=body["module_id"],
            role=body["role"],
            assigned_agent_id=body.get("assigned_agent_id", ""),
            module_name=body.get("module_name", ""),
            description=body.get("description", ""),
            dependencies=body.get("dependencies", []),
            status=body.get("status", "pending"),
            interface_contract=body.get("interface_contract", {}),
        )
        saved = app.state.repository.upsert_module_assignment(assignment)
        return {"success": True, "assignment": saved.to_dict()}

    @app.delete("/api/dashboard/modules/{module_id}")
    async def delete_module(module_id: str) -> dict:
        """删除模块分配。"""
        repo = app.state.repository
        if not repo.get_module_assignment(module_id):
            raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
        with repo._lock:
            repo._module_assignments.pop(module_id, None)
            repo._save()
        return {"success": True, "module_id": module_id}

    # --- REST: 执行控制 ---

    @app.post("/api/execution/start")
    async def start_execution() -> dict:
        """启动 PMCoordinator 执行循环。"""
        coordinator = getattr(app.state, "coordinator", None)
        if not coordinator:
            raise HTTPException(status_code=503, detail="PMCoordinator 未配置")
        result = coordinator.start_execution()
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result.get("error", "无法启动"))
        return result

    @app.post("/api/execution/stop")
    async def stop_execution() -> dict:
        """停止 PMCoordinator 执行循环。"""
        coordinator = getattr(app.state, "coordinator", None)
        if not coordinator:
            raise HTTPException(status_code=503, detail="PMCoordinator 未配置")
        return coordinator.stop_execution()

    @app.get("/api/execution/status")
    async def get_execution_status() -> dict:
        """获取当前执行状态。"""
        coordinator = getattr(app.state, "coordinator", None)
        if not coordinator:
            return {"status": "idle", "thread_alive": False, "error": None, "available": False}
        return coordinator.get_execution_status()

    # --- REST: Agent 管理 ---

    @app.get("/api/agents")
    async def list_agents() -> dict:
        """列出所有 Agent 实例及其状态（含静默检测）。"""
        coordinator = getattr(app.state, "coordinator", None)
        repo = app.state.repository

        # 从 Repository 加载已注册的 Agent
        snapshot = repo.load_snapshot()
        agents = [a.to_dict() for a in snapshot.agents]

        # 补充静默检测状态
        silence_status = {}
        if coordinator:
            silence_status = coordinator.get_all_silence_status()

        for agent in agents:
            agent["silence_status"] = silence_status.get(agent.get("id", ""), {})

        # 从 Coordinator 补充执行中的 Agent 信息
        if coordinator:
            pm = coordinator._process_manager
            for agent_id, proc_info in pm.get_all_agents().items():
                for agent in agents:
                    if agent["id"] == agent_id:
                        agent["process_status"] = proc_info.get("status", "unknown")
                        agent["pid"] = proc_info.get("pid")
                        break

        return {"agents": agents, "total": len(agents)}

    @app.get("/api/agents/{agent_id}/status")
    async def get_agent_status(agent_id: str) -> dict:
        """获取单个 Agent 的详细状态，包括静默检测。"""
        coordinator = getattr(app.state, "coordinator", None)
        repo = app.state.repository

        snapshot = repo.load_snapshot()
        agent = None
        for a in snapshot.agents:
            if a.id == agent_id:
                agent = a.to_dict()
                break

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        result = dict(agent)
        if coordinator:
            silence = coordinator.get_all_silence_status().get(agent_id)
            if silence:
                result["silence_status"] = silence

            pm = coordinator._process_manager
            proc_status = pm.get_agent_status(agent_id)
            if proc_status:
                result["process_status"] = proc_status

        return result

    @app.post("/api/agents/{agent_id}/message")
    async def send_agent_message(agent_id: str, body: dict[str, Any]) -> dict:
        """向 Agent 发送消息（通过 stdin）。"""
        coordinator = getattr(app.state, "coordinator", None)
        if not coordinator:
            raise HTTPException(status_code=503, detail="PMCoordinator 未配置")

        message = body.get("message", "")
        if not message:
            raise HTTPException(status_code=422, detail="message is required")

        pm = coordinator._process_manager
        success = pm.send_message_to_agent(agent_id, message)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found or has no stdin",
            )

        app.state.repository.append_event(
            type="agent_message_sent",
            agent_id=agent_id,
            message=message[:200],
        )
        return {"success": True, "agent_id": agent_id}

    @app.post("/api/agents/{agent_id}/interrupt")
    async def interrupt_agent(agent_id: str, body: dict[str, Any] | None = None) -> dict:
        """中断 Agent 进程（默认 SIGINT，可 force=true 强制 kill）。"""
        body = body or {}
        force = body.get("force", False)

        coordinator = getattr(app.state, "coordinator", None)
        if not coordinator:
            raise HTTPException(status_code=503, detail="PMCoordinator 未配置")

        pm = coordinator._process_manager

        if force:
            pm.force_kill(agent_id)
        else:
            pm.graceful_interrupt(agent_id)

        app.state.repository.append_event(
            type="agent_interrupted",
            agent_id=agent_id,
            force=force,
        )
        return {"success": True, "agent_id": agent_id, "force": force}

    # --- REST: 待审批列表 ---

    @app.get("/api/dashboard/pending-approvals")
    async def list_pending_approvals() -> dict:
        """返回所有等待用户审批的命令。"""
        approvals = app.state.repository.list_pending_approvals()
        return {
            "approvals": approvals,
            "total": len(approvals),
        }

    # --- WebSocket: 实时推送 ---

    @app.websocket("/ws/dashboard")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        app.state.connected_ws.add(ws)
        try:
            snapshot = app.state.repository.load_snapshot()
            await ws.send_json({
                "type": "hello",
                "schema_version": 1,
                "project_id": app.state.repository._project_id,
                "last_event_id": snapshot.last_event_id,
                "agents": [a.to_dict() for a in snapshot.agents],
                "features": [f.to_dict() for f in snapshot.features],
                "chat_history": [m.to_dict() for m in snapshot.chat_history],
                "module_assignments": [m.to_dict() for m in snapshot.module_assignments],
                "blocking_issues": [i.to_dict() for i in snapshot.blocking_issues],
            })
            while True:
                try:
                    while app.state.broadcast_queue:
                        payload = app.state.broadcast_queue.popleft()
                        await ws.send_json(payload)
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=0.1)  # noqa: F841
                except TimeoutError:
                    continue
        except WebSocketDisconnect:
            app.state.connected_ws.discard(ws)

    # --- Ralph API: 只读端点 ---

    @app.get("/api/ralph/health")
    async def ralph_health() -> dict:
        """Ralph 系统健康检查。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        work_units = ralph_repo.list_work_units()
        return {
            "status": "healthy",
            "work_units_count": len(work_units),
            "timestamp": _now_iso(),
        }

    @app.get("/api/ralph/work-units")
    async def ralph_list_work_units(status: str | None = None) -> list[dict]:
        """列出所有 WorkUnit，支持状态过滤。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        filter_status = None
        if status:
            try:
                filter_status = WorkUnitStatus(status)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from err
        units = ralph_repo.list_work_units(status=filter_status)
        return [_serialize_work_unit(u) for u in units]

    @app.get("/api/ralph/work-units/{work_id}")
    async def ralph_get_work_unit(work_id: str) -> dict:
        """获取单个 WorkUnit 详情。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")
        return _serialize_work_unit(unit)

    @app.get("/api/ralph/work-units/{work_id}/evidence")
    async def ralph_list_evidence(work_id: str) -> list[dict]:
        """获取指定 WorkUnit 的证据列表。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        # 验证 work_id 存在
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")
        evidence_list = ralph_repo.list_evidence(work_id=work_id)
        return [_serialize_evidence(e) for e in evidence_list]

    @app.get("/api/ralph/work-units/{work_id}/evidence/{file_path:path}")
    async def ralph_get_evidence_file(work_id: str, file_path: str) -> PlainTextResponse:
        """获取证据文件内容（带安全验证）。"""
        ralph_repo: RalphRepository = app.state.ralph_repository

        # 验证 work_id 存在
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")

        # 安全验证：防止路径遍历攻击
        # 1. 拒绝包含 .. 的路径（在解析前检查原始路径）
        if ".." in file_path:
            raise HTTPException(status_code=403, detail="Invalid file path: path traversal detected")

        # 2. 拒绝绝对路径
        if file_path.startswith("/"):
            raise HTTPException(status_code=403, detail="Invalid file path: absolute paths not allowed")

        # 3. 构建完整路径并解析为绝对路径
        evidence_dir = ralph_repo._evidence_dir
        try:
            requested_path = (evidence_dir / file_path).resolve()
        except (ValueError, OSError) as err:
            raise HTTPException(status_code=403, detail="Invalid file path") from err

        evidence_dir_resolved = evidence_dir.resolve()

        # 4. 确保文件在 evidence 目录内
        try:
            requested_path.relative_to(evidence_dir_resolved)
        except ValueError as err:
            raise HTTPException(status_code=403, detail="Access denied: path outside evidence directory") from err

        # 4. 检查文件是否存在
        if not requested_path.exists() or not requested_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        # 5. 读取文件内容，大文件截断
        content = requested_path.read_text(encoding="utf-8", errors="replace")
        truncated = False
        max_size = 100 * 1024  # 100KB
        if len(content) > max_size:
            content = content[:max_size] + "\n\n[TRUNCATED: file exceeds 100KB limit]"
            truncated = True

        # 6. 敏感信息 redaction
        content = _redact_sensitive_content(content)

        headers = {"X-Truncated": "true" if truncated else "false"}
        return PlainTextResponse(content, headers=headers)

    @app.get("/api/ralph/work-units/{work_id}/reviews")
    async def ralph_list_reviews(work_id: str) -> list[dict]:
        """获取指定 WorkUnit 的审查结果。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        # 验证 work_id 存在
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")
        reviews = ralph_repo.list_reviews(work_id=work_id)
        return [ralph_repo._serialize_review(r) for r in reviews]

    @app.get("/api/ralph/blockers")
    async def ralph_list_blockers(work_id: str | None = None, resolved: bool | None = None) -> list[dict]:
        """获取所有阻塞项，支持过滤。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        blockers = ralph_repo.list_blockers(work_id=work_id, resolved=resolved)
        return [_serialize_blocker(b) for b in blockers]

    @app.get("/api/ralph/pending-actions")
    async def ralph_pending_actions() -> list[dict]:
        """获取待处理审批/干预项汇总。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        repo: ProjectStateRepository = app.state.repository

        # 获取需要人工干预的 WorkUnit（blocked 状态）
        blocked_units = ralph_repo.list_work_units(status=WorkUnitStatus.BLOCKED)
        needs_rework_units = ralph_repo.list_work_units(status=WorkUnitStatus.NEEDS_REWORK)
        needs_review_units = ralph_repo.list_work_units(status=WorkUnitStatus.NEEDS_REVIEW)

        # 获取失败的 Command
        failed_commands = [c for c in repo.list_all_commands() if c.status == "failed"]

        actions = []

        # 添加 blocked WorkUnit 为待处理项
        for unit in blocked_units:
            blockers = ralph_repo.list_blockers(work_id=unit.work_id, resolved=False)
            for blocker in blockers:
                actions.append({
                    "action_id": f"blocker_{blocker.blocker_id}",
                    "action_type": "missing_dep",
                    "work_id": unit.work_id,
                    "description": blocker.reason,
                    "context": {"blocker_type": blocker.blocker_type},
                    "created_at": "",  # Blocker 没有 created_at 字段
                })

        # 添加 needs_rework 为待处理项
        for unit in needs_rework_units:
            actions.append({
                "action_id": f"rework_{unit.work_id}",
                "action_type": "execution_error",
                "work_id": unit.work_id,
                "description": f"WorkUnit {unit.work_id} 需要返工",
                "context": {},
                "created_at": "",
            })

        # 添加 needs_review 为待处理项（人工可以干预）
        for unit in needs_review_units:
            actions.append({
                "action_id": f"review_{unit.work_id}",
                "action_type": "review_dispute",
                "work_id": unit.work_id,
                "description": f"WorkUnit {unit.work_id} 等待审查",
                "context": {},
                "created_at": "",
            })

        # 添加失败的 Command
        for cmd in failed_commands:
            actions.append({
                "action_id": f"cmd_failed_{cmd.command_id}",
                "action_type": "execution_error",
                "work_id": cmd.target_id,
                "description": cmd.result.get("error", "Command execution failed"),
                "context": {"command_id": cmd.command_id},
                "created_at": cmd.issued_at,
            })

        return actions

    @app.get("/api/ralph/work-units/{work_id}/transitions")
    async def ralph_get_transitions(work_id: str) -> list[dict]:
        """获取 WorkUnit 状态转换历史。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        # 验证 work_id 存在
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")
        transitions = ralph_repo.get_transitions(work_id=work_id)
        return transitions

    @app.get("/api/ralph/summary")
    async def ralph_summary() -> dict:
        """获取 Ralph 运行概览统计。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        all_units = ralph_repo.list_work_units()

        status_counts = {status.value: 0 for status in WorkUnitStatus}
        for unit in all_units:
            status_counts[unit.status.value] += 1

        # 计算成功率（accepted / (accepted + failed + needs_rework)）
        terminal_count = status_counts["accepted"] + status_counts["failed"] + status_counts["needs_rework"]
        success_rate = 0.0
        if terminal_count > 0:
            success_rate = status_counts["accepted"] / terminal_count * 100

        # 获取未解决的 blockers
        unresolved_blockers = ralph_repo.list_blockers(resolved=False)

        return {
            "total_work_units": len(all_units),
            "status_counts": status_counts,
            "success_rate_percent": round(success_rate, 1),
            "unresolved_blockers": len(unresolved_blockers),
            "timestamp": _now_iso(),
        }

    # --- Ralph API: Command 端点 ---

    @app.post("/api/ralph/commands")
    async def ralph_create_command(body: dict[str, Any]) -> dict:
        """创建 Ralph Command（带幂等键）。"""
        repo: ProjectStateRepository = app.state.repository

        # 检查幂等键
        idempotency_key = body.get("idempotency_key", "")
        if idempotency_key:
            existing = repo.get_command_by_idempotency_key(idempotency_key)
            if existing:
                return {
                    "success": True,
                    "command_id": existing.command_id,
                    "status": existing.status,
                    "was_duplicate": True,
                }

        # 验证必需字段 (前端使用 command_type 而非 type)
        cmd_type = body.get("command_type", "")
        if not cmd_type:
            raise HTTPException(status_code=422, detail="command_type is required")

        # 创建 Command (前端使用 target_id 而非 work_id)
        cmd = Command(
            command_id=f"ralph_cmd_{_now_iso()}",
            type=cmd_type,
            target_id=body.get("target_id", ""),
            payload=body.get("payload", {}),
            project_id=body.get("project_id", ""),
            run_id=body.get("run_id", ""),
            issued_at=_now_iso(),
            idempotency_key=idempotency_key,
            status="pending",
        )

        repo.save_command(cmd)

        return {
            "success": True,
            "command_id": cmd.command_id,
            "status": cmd.status,
            "was_duplicate": False,
        }

    @app.get("/api/ralph/commands/{command_id}")
    async def ralph_get_command(command_id: str) -> dict:
        """查询 Command 状态。"""
        repo: ProjectStateRepository = app.state.repository
        cmd = repo.get_command(command_id)
        if cmd is None:
            raise HTTPException(status_code=404, detail=f"Command {command_id} not found")
        return cmd.to_dict()

    @app.post("/api/ralph/commands/{command_id}/cancel")
    async def ralph_cancel_command(command_id: str) -> dict:
        """取消待处理的 Command。"""
        repo: ProjectStateRepository = app.state.repository
        cmd = repo.get_command(command_id)
        if cmd is None:
            raise HTTPException(status_code=404, detail=f"Command {command_id} not found")

        # 只能取消 pending 状态的 Command
        if cmd.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel command with status: {cmd.status}",
            )

        cmd.status = "cancelled"
        cmd.updated_at = _now_iso()
        repo.save_command(cmd)

        return {
            "success": True,
            "command_id": cmd.command_id,
            "status": cmd.status,
        }

    @app.get("/api/ralph/commands")
    async def ralph_list_commands(status: str | None = None) -> list[dict]:
        """列出所有 Command，支持 status 过滤。"""
        repo: ProjectStateRepository = app.state.repository
        commands = repo.list_all_commands()
        if status:
            commands = [c for c in commands if c.status == status]
        return [c.to_dict() for c in commands]

    # --- Ralph API: 报告端点 ---

    @app.get("/api/ralph/reports")
    async def ralph_list_reports() -> list[dict]:
        """列出所有已生成的报告。"""
        gen: ReportGenerator = app.state.report_generator
        reports = gen.list_reports()
        return [
            {
                "name": r.name,
                "size_bytes": r.stat().st_size,
                "created_at": _now_iso(),
            }
            for r in reports
        ]

    @app.post("/api/ralph/reports/generate")
    async def ralph_generate_report(body: dict[str, Any] | None = None) -> dict:
        """生成中文研发报告。"""
        body = body or {}
        title = body.get("title", "研发报告")
        filename = body.get("filename", "report.md")

        gen: ReportGenerator = app.state.report_generator
        content = gen.generate(title=title)
        path = gen.save(content, filename)

        return {
            "success": True,
            "name": path.name,
            "path": str(path),
            "content": content,
        }

    @app.get("/api/ralph/reports/{name:path}")
    async def ralph_get_report(name: str) -> dict:
        """获取单个报告内容。"""
        gen: ReportGenerator = app.state.report_generator
        reports_dir = gen._ralph_dir / "reports"

        # 安全验证：防止路径遍历
        if ".." in name or name.startswith("/"):
            raise HTTPException(status_code=403, detail="Invalid report name")

        report_path = (reports_dir / name).resolve()
        try:
            report_path.relative_to(reports_dir.resolve())
        except ValueError as err:
            raise HTTPException(status_code=403, detail="Access denied: path outside reports directory") from err

        if not report_path.is_file():
            raise HTTPException(status_code=404, detail=f"Report {name} not found")

        content = report_path.read_text(encoding="utf-8")
        return {
            "name": report_path.name,
            "content": content,
            "size_bytes": report_path.stat().st_size,
        }

    # --- Ralph API: 事件历史端点 ---

    @app.get("/api/ralph/events")
    async def ralph_list_events(limit: int = 50, after_id: int = 0) -> list[dict]:
        """查询事件历史（用于前端恢复/翻历史日志）。"""
        repo: ProjectStateRepository = app.state.repository
        events = repo.get_events_after(after_id, limit=limit)
        return [e.to_dict() for e in events]

    # --- Ralph API: 配置端点 ---

    # Providers

    @app.get("/api/ralph/settings/providers")
    async def ralph_list_providers() -> list[dict]:
        """列出所有 LLM Provider。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.list_providers()

    @app.post("/api/ralph/settings/providers")
    async def ralph_create_provider(body: dict[str, Any]) -> dict:
        """创建/更新 LLM Provider。"""
        cfg: RalphConfigManager = app.state.config_manager
        provider_id = body.get("id", "")
        if not provider_id:
            raise HTTPException(status_code=422, detail="provider id is required")
        return cfg.save_provider(body)

    @app.put("/api/ralph/settings/providers/{provider_id}")
    async def ralph_update_provider(provider_id: str, body: dict[str, Any]) -> dict:
        """更新指定 LLM Provider。"""
        cfg: RalphConfigManager = app.state.config_manager
        body["id"] = provider_id
        return cfg.save_provider(body)

    @app.delete("/api/ralph/settings/providers/{provider_id}")
    async def ralph_delete_provider(provider_id: str) -> dict:
        """删除指定 LLM Provider。"""
        cfg: RalphConfigManager = app.state.config_manager
        ok = cfg.delete_provider(provider_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        return {"success": True}

    @app.post("/api/ralph/settings/providers/{provider_id}/test")
    async def ralph_test_provider(provider_id: str) -> dict:
        """测试指定 Provider 的连通性。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.test_provider_connection(provider_id)

    # Model Assignments

    @app.get("/api/ralph/settings/model-assignments")
    async def ralph_list_assignments() -> list[dict]:
        """列出模型路由规则。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.list_assignments()

    @app.put("/api/ralph/settings/model-assignments")
    async def ralph_save_assignments(body: list[dict]) -> list[dict]:
        """保存模型路由规则。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_assignments(body)

    # Toolchain

    @app.get("/api/ralph/settings/toolchain")
    async def ralph_get_toolchain() -> dict:
        """获取工具链配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_toolchain()

    @app.put("/api/ralph/settings/toolchain")
    async def ralph_save_toolchain(body: dict[str, Any]) -> dict:
        """保存工具链配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_toolchain(body)

    @app.post("/api/ralph/settings/toolchain/dispatch-parallel")
    async def ralph_dispatch_parallel(body: dict[str, Any]) -> dict:
        """并行执行所有 ready 的 WorkUnit。"""
        from ralph.command_handler import RalphCommandHandler
        from ralph.work_unit_engine import WorkUnitEngine
        from dashboard.models import Command

        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent

        engine = WorkUnitEngine(ralph_dir.parent)
        handler = RalphCommandHandler(ralph_dir, engine=engine)
        cmd = Command(
            command_id="dispatch-parallel",
            type="dispatch_parallel",
            target_id="",
            payload={
                "max_parallel": body.get("max_parallel", 3),
                "prd_summary": body.get("prd_summary", ""),
            },
        )
        return handler.handle(cmd)

    # Issue Policy

    @app.get("/api/ralph/settings/issue-policy")
    async def ralph_get_issue_policy() -> dict:
        """获取 Issue 治理策略。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_issue_policy()

    @app.put("/api/ralph/settings/issue-policy")
    async def ralph_save_issue_policy(body: dict[str, Any]) -> dict:
        """保存 Issue 治理策略。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_issue_policy(body)

    # --- Ralph API: 项目管理端点 ---

    @app.get("/api/ralph/projects")
    async def ralph_list_projects() -> list[dict]:
        """列出已知项目（最近打开 + 扫描发现）。"""
        cfg: RalphConfigManager = app.state.config_manager
        recent = cfg.list_recent_projects()

        # 扫描默认项目目录
        base_dir = Path(os.environ.get("RALPH_PROJECTS_DIR", str(Path.home() / "ralph-projects")))
        discovered = []
        if base_dir.is_dir():
            for d in sorted(base_dir.iterdir()):
                if d.is_dir() and (d / ".ralph").is_dir():
                    discovered.append({
                        "name": d.name,
                        "path": str(d.resolve()),
                        "has_ralph": True,
                    })

        # 合并去重
        seen = set()
        result = []
        for p in recent:
            key = p["path"]
            if key not in seen:
                seen.add(key)
                result.append({**p, "has_ralph": Path(p["path"]).is_dir()})

        for p in discovered:
            if p["path"] not in seen:
                seen.add(p["path"])
                result.append({**p, "last_opened_at": None})

        return result

    @app.post("/api/ralph/projects/open")
    async def ralph_open_project(body: dict[str, Any]) -> dict:
        """打开/选择当前项目。"""
        path_str = body.get("path", "")
        if not path_str:
            raise HTTPException(status_code=422, detail="path is required")

        project_path = Path(path_str).resolve()
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path_str}")

        cfg: RalphConfigManager = app.state.config_manager
        cfg.add_recent_project(str(project_path), project_path.name)

        # 检查项目状态
        ralph_repo: RalphRepository = app.state.ralph_repository
        work_units = ralph_repo.list_work_units()

        return {
            "success": True,
            "name": project_path.name,
            "path": str(project_path),
            "work_unit_count": len(work_units),
            "has_analysis": cfg.get_analysis() is not None,
        }

    @app.post("/api/ralph/projects/analyze")
    async def ralph_analyze_project(body: dict[str, Any] | None = None) -> dict:
        """运行代码库侦察分析。"""
        body = body or {}
        project_path_str = body.get("path", os.environ.get("PROJECT_DIR", "."))
        project_path = Path(project_path_str).resolve()

        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {project_path_str}")

        # 运行分析
        analysis = _analyze_project(project_path)
        cfg: RalphConfigManager = app.state.config_manager
        cfg.save_analysis(str(project_path), analysis)

        return {"success": True, "analysis": analysis}

    @app.get("/api/ralph/projects/analysis")
    async def ralph_get_analysis() -> dict:
        """获取缓存的项目分析结果。"""
        cfg: RalphConfigManager = app.state.config_manager
        analysis = cfg.get_analysis()
        if not analysis:
            raise HTTPException(status_code=404, detail="No analysis found. Run analyze first.")
        return analysis

    @app.post("/api/ralph/projects/init")
    async def ralph_init_project(body: dict[str, Any]) -> dict:
        """初始化新项目。"""
        path_str = body.get("path", "")
        name = body.get("name", "")
        if not path_str:
            raise HTTPException(status_code=422, detail="path is required")

        project_path = Path(path_str).resolve()
        project_path.mkdir(parents=True, exist_ok=True)

        # 创建 .ralph/ 目录结构
        ralph_dir = project_path / ".ralph"
        for sub in ["config", "work_units", "evidence", "reviews", "blockers", "state", "memory", "reports"]:
            (ralph_dir / sub).mkdir(parents=True, exist_ok=True)

        # 初始化 git
        import subprocess
        try:
            subprocess.run(["git", "init", "-b", "main"], cwd=project_path, capture_output=True, timeout=10)
        except Exception:
            pass  # git 可能不可用

        cfg: RalphConfigManager = app.state.config_manager
        cfg.add_recent_project(str(project_path), name or project_path.name)

        return {
            "success": True,
            "name": name or project_path.name,
            "path": str(project_path),
        }

    # --- Ralph API: 项目管理端点 ---

    # AI 深度分析后台任务进度追踪
    _analysis_jobs: dict[str, dict] = {}
    _analysis_lock = threading.Lock()

    def _run_analysis_background(path_str: str):
        """后台线程执行深度分析，更新进度字典。"""
        from ralph.project_analyzer import ProjectAnalyzer
        project_path = Path(path_str).resolve()
        job_key = str(project_path)

        progress = {
            "status": "running",
            "progress": 0,
            "phase": "初始化",
            "message": "准备开始分析...",
            "current_file": None,
            "report": None,
            "error": None,
        }
        with _analysis_lock:
            _analysis_jobs[job_key] = progress

        try:
            analyzer = ProjectAnalyzer(project_path, progress=progress)
            result = analyzer.analyze()
            report_text = result["report"] if isinstance(result, dict) else result
            with _analysis_lock:
                _analysis_jobs[job_key].update({
                    "status": "complete",
                    "progress": 100,
                    "phase": "分析完成",
                    "message": "项目分析已完成",
                    "report": report_text,
                })
        except Exception as e:
            with _analysis_lock:
                _analysis_jobs[job_key].update({
                    "status": "error",
                    "progress": 0,
                    "phase": "分析失败",
                    "message": f"分析失败: {e}",
                    "error": str(e),
                })

    @app.post("/api/ralph/projects/deep-analyze")
    async def ralph_deep_analyze_project(body: dict[str, Any]) -> dict:
        """启动 AI 深度分析（异步后台执行）。"""
        path_str = body.get("path", os.environ.get("PROJECT_DIR", "."))
        project_path = Path(path_str).resolve()
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path_str}")

        job_key = str(project_path)
        with _analysis_lock:
            existing = _analysis_jobs.get(job_key)
            if existing and existing.get("status") == "running":
                return {"success": True, "job_key": job_key, "already_running": True}
            _analysis_jobs[job_key] = {
                "status": "starting", "progress": 0,
                "phase": "启动中", "message": "正在启动分析...",
                "current_file": None, "report": None, "error": None,
            }

        thread = threading.Thread(target=_run_analysis_background, args=(path_str,), daemon=True)
        thread.start()
        return {"success": True, "job_key": job_key}

    @app.get("/api/ralph/projects/analysis-progress")
    async def ralph_analysis_progress(path: str = "") -> dict:
        """获取 AI 深度分析的实时进度。"""
        if not path:
            raise HTTPException(status_code=400, detail="path 参数必填")
        project_path = Path(path).resolve()
        job_key = str(project_path)

        with _analysis_lock:
            progress = _analysis_jobs.get(job_key)

        if not progress:
            from ralph.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer(project_path)
            report = analyzer.get_saved_report()
            if report:
                return {"status": "complete", "progress": 100, "phase": "分析完成",
                        "message": "项目分析已完成", "report": report,
                        "summary": analyzer.get_saved_report_summary()}
            return {"status": "idle", "progress": 0, "phase": "未开始",
                    "message": "尚未进行深度分析"}

        result = dict(progress)
        if progress.get("status") == "complete" and progress.get("report"):
            from ralph.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer(project_path)
            result["summary"] = analyzer.get_saved_report_summary()
        return result

    @app.get("/api/ralph/projects/report")
    async def ralph_get_project_report(path: str = "") -> dict:
        """获取已保存的项目分析报告。"""
        from ralph.project_analyzer import ProjectAnalyzer
        project_path = Path(path).resolve() if path else Path(os.environ.get("PROJECT_DIR", "."))
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
        analyzer = ProjectAnalyzer(project_path)
        report = analyzer.get_saved_report()
        if not report:
            raise HTTPException(status_code=404, detail="尚无分析报告，请先执行深度分析")
        return {
            "success": True,
            "report": report,
            "summary": analyzer.get_saved_report_summary(),
            "project_name": project_path.name,
        }

    @app.get("/api/ralph/projects/report/structured")
    async def ralph_get_project_structured(path: str = "") -> dict:
        """获取结构化的项目分析数据（供管道下游消费）。"""
        project_path = Path(path).resolve() if path else Path(os.environ.get("PROJECT_DIR", "."))
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
        from ralph.project_analyzer import ProjectAnalyzer
        analyzer = ProjectAnalyzer(project_path)
        structured_path = analyzer.ralph_dir / "project-structured.json"
        if not structured_path.is_file():
            raise HTTPException(status_code=404, detail="尚无结构化分析数据")
        data = json.loads(structured_path.read_text(encoding="utf-8"))
        return {"success": True, "structured": data}

    @app.post("/api/ralph/projects/browse-directory")
    async def ralph_browse_directory(body: dict[str, Any]) -> dict:
        """浏览文件系统目录（用于前端目录选择器）。"""
        path_str = body.get("path", "")
        base_path = Path(path_str).resolve() if path_str else Path.home()

        if not base_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path_str}")

        # 安全检查：限定在用户目录范围内
        home = Path.home().resolve()
        try:
            base_path.relative_to(home)
        except ValueError:
            # 允许访问 / 和 /Users 等根级目录
            if base_path != Path("/") and base_path != Path("/Users"):
                pass  # 宽限处理，不做死限制

        # 列出子目录
        entries = []
        try:
            for entry in sorted(base_path.iterdir(), key=lambda e: e.name.lower()):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir() and not entry.is_symlink():
                    # 检测是否看起来像项目
                    has_ralph = (entry / ".ralph").is_dir()
                    has_git = (entry / ".git").is_dir()
                    has_package_json = (entry / "package.json").is_file()
                    has_pyproject = (entry / "pyproject.toml").is_file()
                    entries.append({
                        "name": entry.name,
                        "path": str(entry.resolve()),
                        "has_ralph": has_ralph,
                        "has_git": has_git,
                        "is_project": has_ralph or has_git or has_package_json or has_pyproject,
                    })
        except PermissionError:
            pass  # 跳过无权限目录

        return {
            "path": str(base_path),
            "parent": str(base_path.parent) if base_path != base_path.parent else None,
            "entries": entries,
        }

    # --- Ralph API: 文件浏览端点 ---

    @app.get("/api/ralph/files")
    async def ralph_list_files(path: str = "") -> list[dict]:
        """列出目录内容（相对于当前项目根目录）。"""
        project_dir = Path(os.environ.get("PROJECT_DIR", ".")).resolve()
        target = (project_dir / path).resolve() if path else project_dir

        # 安全检查
        try:
            target.relative_to(project_dir)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: path outside project")

        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

        entries = []
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith(".") and entry.name not in (".ralph", ".gitignore"):
                continue
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "path": str(entry.relative_to(project_dir)),
                "size": entry.stat().st_size if entry.is_file() else None,
            })

        return entries

    @app.get("/api/ralph/files/content")
    async def ralph_get_file_content(path: str = "") -> dict:
        """获取文件内容（纯文本，最大 500KB）。"""
        project_dir = Path(os.environ.get("PROJECT_DIR", ".")).resolve()
        file_path = (project_dir / path).resolve()

        try:
            file_path.relative_to(project_dir)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: path outside project")

        if not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        size = file_path.stat().st_size
        if size > 500 * 1024:
            raise HTTPException(status_code=413, detail="File too large (>500KB)")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = f"[Binary file: {size} bytes]"

        return {
            "name": file_path.name,
            "path": path,
            "size": size,
            "content": content,
        }

    @app.get("/api/ralph/files/tree")
    async def ralph_get_file_tree(depth: int = 3) -> dict:
        """递归获取目录树（最大深度 5）。"""
        project_dir = Path(os.environ.get("PROJECT_DIR", ".")).resolve()
        depth = min(depth, 5)

        def build_tree(dir_path: Path, current_depth: int) -> list[dict]:
            if current_depth > depth:
                return []
            result = []
            for entry in sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith(".") and entry.name not in (".ralph",):
                    continue
                if entry.name in ("node_modules", "__pycache__", ".git", ".next", "venv", ".venv"):
                    continue
                node = {
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "path": str(entry.relative_to(project_dir)),
                }
                if entry.is_dir() and current_depth < depth:
                    node["children"] = build_tree(entry, current_depth + 1)
                result.append(node)
            return result

        return {"tree": build_tree(project_dir, 1)}

    # --- Ralph API: Brainstorm 端点 ---

    @app.get("/api/ralph/brainstorm/sessions")
    async def ralph_list_brainstorm_sessions() -> list[dict]:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        return BrainstormManager(ralph_dir).list_sessions()

    @app.post("/api/ralph/brainstorm/start")
    async def ralph_start_brainstorm(body: dict[str, Any]) -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        mgr = BrainstormManager(ralph_dir)
        record = mgr.start_session(
            body.get("project_name", "Unnamed"),
            body.get("user_message", ""),
        )
        questions = mgr.generate_questions(record)
        summary = mgr.get_summary(record)
        return {"record_id": record.record_id, "questions": questions, "summary": summary}

    @app.post("/api/ralph/brainstorm/respond")
    async def ralph_brainstorm_respond(body: dict[str, Any]) -> dict:
        record_id = body.get("record_id", "")
        if not record_id:
            raise HTTPException(status_code=422, detail="record_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        mgr = BrainstormManager(ralph_dir)
        record = mgr.load(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        updated = mgr.process_response(record, body.get("user_response", ""),
                                        body.get("extracted_facts"))
        questions = mgr.generate_questions(updated)
        is_complete = mgr.is_complete(updated)
        return {
            "record_id": updated.record_id, "round": updated.round_number,
            "questions": questions, "is_complete": is_complete,
            "completeness": updated.completeness_score(),
            "summary": mgr.get_summary(updated),
        }

    # --- Ralph API: PRD 端点 ---

    @app.get("/api/ralph/prd/list")
    async def ralph_list_prds() -> list[dict]:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        return PRDManager(ralph_dir).list_prds()

    @app.post("/api/ralph/prd/generate")
    async def ralph_generate_prd(body: dict[str, Any]) -> dict:
        brainstorm_id = body.get("brainstorm_record_id", "")
        if not brainstorm_id:
            raise HTTPException(status_code=422, detail="brainstorm_record_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        pm = PRDManager(ralph_dir)
        prd = pm.generate_from_brainstorm(brainstorm_id, ralph_dir)
        return {"prd_id": prd.prd_id, "status": prd.status, "markdown": prd.to_markdown()}

    @app.post("/api/ralph/prd/freeze")
    async def ralph_freeze_prd(body: dict[str, Any]) -> dict:
        prd_id = body.get("prd_id", "")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        prd = PRDManager(ralph_dir).freeze(prd_id)
        return {"prd_id": prd.prd_id, "status": prd.status, "frozen_at": prd.frozen_at}

    # --- Ralph API: Task Decomposition 端点 ---

    @app.post("/api/ralph/tasks/decompose")
    async def ralph_decompose_tasks(body: dict[str, Any]) -> dict:
        prd_id = body.get("prd_id", "")
        if not prd_id:
            raise HTTPException(status_code=422, detail="prd_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        from ralph.task_decomposer import TaskDecomposer
        pm = PRDManager(ralph_dir)
        prd = pm.load(prd_id)
        if prd is None:
            raise HTTPException(status_code=404, detail="PRD not found")
        td = TaskDecomposer(ralph_dir)
        stories, units = td.decompose(prd)
        failures = td.validate_granularity(units)
        dag = td.build_dependency_dag(units)
        return {
            "work_units": [_serialize_work_unit(u) for u in units],
            "granularity_failures": failures,
            "dependency_dag": dag,
            "total": len(units),
        }

    # --- Ralph API: Scheduling 端点 ---

    @app.get("/api/ralph/scheduling/status")
    async def ralph_scheduling_status() -> dict:
        """返回当前调度状态。"""
        repo: ProjectStateRepository = app.state.repository
        features = repo.list_features()
        statuses = {}
        for f in features:
            s = getattr(f, "status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "active_work_units": statuses.get("in_progress", 0),
            "pending_features": statuses.get("pending", 0),
            "completed_features": statuses.get("done", 0),
            "blocked_features": statuses.get("blocked", 0),
        }

    @app.get("/api/ralph/scheduling/timeline")
    async def ralph_scheduling_timeline() -> list[dict]:
        """返回调度事件时间线。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_scheduling_timeline(limit=50)

    # --- Ralph API: Agent Definitions 端点 ---

    @app.get("/api/ralph/agents/definitions")
    async def ralph_list_agent_definitions() -> list[dict]:
        """列出所有 Agent 定义。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.list_agent_definitions()

    @app.post("/api/ralph/agents/definitions")
    async def ralph_save_agent_definition(body: dict[str, Any]) -> dict:
        """创建/更新 Agent 定义。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_agent_definition(body)

    @app.delete("/api/ralph/agents/definitions/{role}")
    async def ralph_delete_agent_definition(role: str) -> dict:
        """删除 Agent 定义。"""
        cfg: RalphConfigManager = app.state.config_manager
        ok = cfg.delete_agent_definition(role)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Agent {role} not found")
        return {"success": True}

    # --- Ralph API: Agent Provider 端点 (per-agent LLM config) ---

    @app.get("/api/ralph/settings/agent-providers")
    async def ralph_list_agent_providers() -> dict:
        """列出所有 Agent 级 Provider 配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.list_agent_providers()

    @app.get("/api/ralph/settings/agent-providers/{agent_id}")
    async def ralph_get_agent_provider(agent_id: str) -> dict:
        """获取指定 Agent 的 Provider 配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        config = cfg.get_agent_provider(agent_id)
        if config is None:
            return {}
        return config

    @app.put("/api/ralph/settings/agent-providers/{agent_id}")
    async def ralph_save_agent_provider(agent_id: str, body: dict[str, Any]) -> dict:
        """保存 Agent 级 Provider 配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_agent_provider(agent_id, body)

    @app.post("/api/ralph/settings/resolve-provider")
    async def ralph_resolve_provider(body: dict[str, Any]) -> dict:
        """解析 agent 最终使用的 provider。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.resolve_agent_provider(
            body.get("agent_role", ""), body.get("task_type", ""),
        )

    # --- Ralph API: Memory 端点 ---

    @app.get("/api/ralph/memory/status")
    async def ralph_memory_status() -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager
        return MemoryManager(ralph_dir).get_status()

    @app.get("/api/ralph/memory/search")
    async def ralph_memory_search(q: str = "", top_k: int = 10) -> list[dict]:
        if not q:
            return []
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager
        return MemoryManager(ralph_dir).search(q, top_k)

    @app.get("/api/ralph/memory/l1-snapshot")
    async def ralph_memory_l1_snapshot() -> dict:
        """L1 状态快照 — 为 PM Agent 调度提供当前上下文。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager
        from ralph.repository import RalphRepository
        mgr = MemoryManager(ralph_dir)
        repo = RalphRepository(ralph_dir)
        work_units = repo.list_work_units()
        from dataclasses import asdict
        active = [asdict(wu) for wu in work_units if wu.status.value not in ("draft", "ready", "accepted")]
        return mgr.get_l1_snapshot(active)

    @app.post("/api/ralph/memory/compact")
    async def ralph_memory_compact(body: dict[str, Any]) -> dict:
        """压缩指定 WorkUnit 的记忆。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        work_id = body.get("work_id", "")
        if not work_id:
            return {"success": False, "error": "缺少 work_id"}
        from ralph.memory_manager import MemoryManager
        from ralph.repository import RalphRepository
        mgr = MemoryManager(ralph_dir)
        repo = RalphRepository(ralph_dir)
        wu = repo.get_work_unit(work_id)
        if not wu:
            return {"success": False, "error": f"WorkUnit {work_id} 不存在"}
        from dataclasses import asdict
        result = mgr.on_work_unit_completed(asdict(wu))
        return {"success": True, **result}

    @app.get("/api/ralph/memory/config")
    async def ralph_memory_get_config() -> dict:
        """获取记忆系统配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager
        return MemoryManager(ralph_dir).thresholds

    @app.put("/api/ralph/memory/config")
    async def ralph_memory_update_config(body: dict[str, Any]) -> dict:
        """更新记忆系统配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager
        mgr = MemoryManager(ralph_dir)
        mgr.update_thresholds(body)
        return {"success": True, "thresholds": mgr.thresholds}

    # --- Ralph API: Context Engine 端点 ---

    @app.post("/api/ralph/context/pm")
    async def ralph_context_pm(body: dict[str, Any]) -> dict:
        """构建 PM Agent 上下文。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        mode = body.get("mode", "schedule")
        from ralph.context_engine import ContextEngine
        from ralph.repository import RalphRepository
        engine = ContextEngine(project_dir)
        repo = RalphRepository(ralph_dir)
        work_units = repo.list_work_units()
        from dataclasses import asdict
        active = [asdict(wu) for wu in work_units if wu.status.value not in ("draft", "ready", "accepted")]
        pending = body.get("pending_decisions")
        context = engine.build_pm_context(
            mode=mode,
            active_work_units=active,
            pending_decisions=pending,
        )
        return {"success": True, "context": context, "mode": mode}

    @app.post("/api/ralph/context/incremental")
    async def ralph_context_incremental(body: dict[str, Any]) -> dict:
        """构建增量上下文（Continuation 场景）。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        work_id = body.get("work_id", "")
        if not work_id:
            return {"success": False, "error": "缺少 work_id"}
        from ralph.context_engine import ContextEngine
        engine = ContextEngine(project_dir)
        context = engine.build_incremental(
            work_id=work_id,
            checkpoint=body.get("checkpoint"),
            current_error=body.get("current_error", ""),
            next_goal=body.get("next_goal", ""),
        )
        return {"success": True, "context": context, "work_id": work_id}

    # --- Ralph API: PM Agent 端点 ---

    @app.get("/api/ralph/pm/status")
    async def ralph_pm_status() -> dict:
        """PM Agent 调度状态。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine
        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        return agent.get_status()

    @app.get("/api/ralph/pm/context")
    async def ralph_pm_context() -> dict:
        """PM Agent 上下文（L0 + L1）。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine
        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        context = agent.get_context()
        return {"success": True, "context": context}

    @app.post("/api/ralph/pm/schedule")
    async def ralph_pm_schedule() -> dict:
        """执行一次 PM Agent 调度。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine
        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        results = agent.schedule_once()
        return {
            "success": True,
            "actions": len(results),
            "results": [
                {"action": r.action, "work_id": r.work_id, "success": r.success, "summary": r.summary}
                for r in results
            ],
        }

    # --- Ralph API: Turn Engine 端点 ---

    @app.get("/api/ralph/executions")
    async def ralph_list_executions() -> list[str]:
        """列出所有多轮执行记录。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(ralph_dir.parent)
        return engine.list_executions()

    @app.get("/api/ralph/executions/{work_id}")
    async def ralph_get_execution(work_id: str) -> dict:
        """获取多轮执行状态。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(ralph_dir.parent)
        result = engine.get_execution_status(work_id)
        if result is None:
            return {"success": False, "error": f"执行记录 {work_id} 不存在"}
        return {"success": True, "execution": result}

    # --- Ralph API: Budget 端点 ---

    @app.get("/api/ralph/budget")
    async def ralph_get_budget() -> dict:
        """获取预算配置和当前用量。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_budget_config()

    @app.put("/api/ralph/budget")
    async def ralph_update_budget(body: dict[str, Any]) -> dict:
        """更新预算配置。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.update_budget_config(body)

    # --- Ralph API: Workspace 端点 ---

    @app.get("/api/ralph/workspaces")
    async def ralph_list_workspaces() -> list[dict]:
        """列出活跃 worktree。"""
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.parallel_executor import WorktreeManager
        from pathlib import Path
        mgr = WorktreeManager(cfg._dir.parent.parent)
        trees = mgr.list_active()
        return [{"name": t.name, "path": str(t.path), "branch": t.branch, "status": t.status}
                for t in trees]

    # --- Ralph API: Knowledge Graph 端点 ---

    @app.get("/api/ralph/knowledge-graph/status")
    async def ralph_kg_status() -> dict:
        """知识图谱状态统计。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(ralph_dir)
        return kg.get_status()

    @app.get("/api/ralph/knowledge-graph/data")
    async def ralph_kg_data() -> dict:
        """知识图谱完整数据（前端可视化）。"""
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(ralph_dir)
        return kg.get_graph_data()

    @app.get("/api/ralph/knowledge-graph/impact")
    async def ralph_kg_impact(file_path: str = "") -> dict:
        """查询文件影响面。"""
        if not file_path:
            return {"success": False, "error": "缺少 file_path"}
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(ralph_dir)
        return kg.query_impact(file_path)

    # --- Ralph API: Retrieval 端点 ---

    @app.get("/api/ralph/search")
    async def ralph_search(q: str = "", top_k: int = 20) -> dict:
        """全量检索（三层管道）。"""
        if not q:
            return {"query": "", "total": 0, "combined": []}
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.retrieval_pipeline import RetrievalPipeline
        pipeline = RetrievalPipeline(ralph_dir)
        return pipeline.search(q, top_k)

    # --- Ralph API: Phase 4 端点 ---

    @app.get("/api/ralph/usage/stats")
    async def ralph_usage_stats() -> dict:
        """获取 API 用量和成本统计。"""
        cfg: RalphConfigManager = app.state.config_manager
        stats = cfg.get_usage_stats()
        # 按 provider 汇总
        log = cfg._read_json("usage-log.json", [])
        by_provider: dict[str, int] = {}
        for entry in log:
            pid = entry.get("provider_id", "unknown")
            by_provider[pid] = by_provider.get(pid, 0) + 1
        stats["by_provider"] = by_provider
        return stats

    @app.get("/api/ralph/projects/history")
    async def ralph_project_history() -> list[dict]:
        """列出历史项目记录。"""
        cfg: RalphConfigManager = app.state.config_manager
        recent = cfg.list_recent_projects()
        history = []
        for p in recent:
            path = Path(p["path"])
            has_ralph = (path / ".ralph").is_dir()
            work_units = len(list((path / ".ralph" / "work_units").glob("*.json"))) if has_ralph else 0
            history.append({
                "name": p.get("name", path.name),
                "path": p["path"],
                "last_opened_at": p.get("last_opened_at", ""),
                "has_ralph": has_ralph,
                "work_unit_count": work_units,
                "status": "completed" if work_units > 0 else "empty",
            })
        return history

    @app.get("/api/ralph/providers/health")
    async def ralph_providers_health() -> list[dict]:
        """获取所有 Provider 的健康状态。"""
        cfg: RalphConfigManager = app.state.config_manager
        results = []
        for p in cfg.list_providers():
            # 简单连通性检查
            import urllib.request
            healthy = False
            base_url = p.get("base_url", "")
            if base_url:
                try:
                    urllib.request.urlopen(f"{base_url.rstrip('/')}/models", timeout=5)
                    healthy = True
                except Exception:
                    healthy = False
            results.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "enabled": p.get("enabled", False),
                "healthy": healthy,
                "last_tested_at": p.get("last_tested_at"),
                "last_test_result": p.get("last_test_result"),
            })
        return results

    # --- Ralph API: Specs + Contracts + Recon + Verification 端点 ---

    @app.get("/api/ralph/specs")
    async def ralph_list_specs() -> list[dict]:
        from ralph.spec_change_manager import SpecChangeManager
        cfg: RalphConfigManager = app.state.config_manager
        return SpecChangeManager(cfg._dir.parent).list_specs()

    @app.post("/api/ralph/specs/changes")
    async def ralph_create_change(body: dict[str, Any]) -> dict:
        from ralph.spec_change_manager import SpecChangeManager
        from ralph.schema.spec_document import SpecChange
        cfg: RalphConfigManager = app.state.config_manager
        mgr = SpecChangeManager(cfg._dir.parent)
        change = mgr.create_change(SpecChange(**body))
        return {"change_id": change.change_id, "status": change.status}

    @app.post("/api/ralph/specs/changes/{change_id}/approve")
    async def ralph_approve_change(change_id: str) -> dict:
        from ralph.spec_change_manager import SpecChangeManager
        cfg: RalphConfigManager = app.state.config_manager
        change = SpecChangeManager(cfg._dir.parent).approve_change(change_id)
        if not change:
            raise HTTPException(status_code=404, detail="Change not found")
        return {"change_id": change.change_id, "status": change.status}

    @app.get("/api/ralph/contracts")
    async def ralph_list_contracts() -> list[dict]:
        from ralph.contract_manager import ContractManager
        cfg: RalphConfigManager = app.state.config_manager
        return ContractManager(cfg._dir.parent).list_contracts()

    @app.post("/api/ralph/contracts")
    async def ralph_create_contract(body: dict[str, Any]) -> dict:
        from ralph.contract_manager import ContractManager
        from ralph.schema.contract import InterfaceContract
        cfg: RalphConfigManager = app.state.config_manager
        contract = ContractManager(cfg._dir.parent).save(InterfaceContract(**body))
        return {"contract_id": contract.contract_id, "status": contract.status}

    @app.post("/api/ralph/projects/recon")
    async def ralph_recon_analyze(body: dict[str, Any]) -> dict:
        from ralph.recon_analyzer import ReconAnalyzer
        project_path = Path(body.get("path", os.environ.get("PROJECT_DIR", ".")))
        analyzer = ReconAnalyzer()
        return {"success": True, "analysis": analyzer.analyze(project_path.resolve())}

    @app.post("/api/ralph/verification/checklist")
    async def ralph_build_checklist(body: dict[str, Any]) -> dict:
        from ralph.verification_manager import VerificationManager
        cfg: RalphConfigManager = app.state.config_manager
        vm = VerificationManager(cfg._dir.parent)
        checklist = vm.build_checklist(body.get("work_id", ""))
        vm.save_checklist(checklist)
        return {"work_id": checklist.work_id, "checks": len(checklist.checks)}

    @app.get("/api/ralph/toolchain/available")
    async def ralph_toolchain_available() -> list[dict]:
        from ralph.tool_adapter import ToolAdapterRegistry, ClaudeCodeAdapter
        registry = ToolAdapterRegistry()
        registry.register(ClaudeCodeAdapter())
        available = registry.list_available()
        return [{"tool_id": tid, "available": tid in available} for tid in registry._priority]

    @app.get("/api/ralph/issues")
    async def ralph_list_issues() -> list[dict]:
        from ralph.issue_source_adapter import LocalFileIssueSource, IssueClassifier
        cfg: RalphConfigManager = app.state.config_manager
        issues_dir = cfg._dir.parent / "issues"
        source = LocalFileIssueSource(issues_dir)
        classifier = IssueClassifier()
        issues = source.fetch()
        return [{
            "issue_id": i.issue_id, "title": i.title,
            "issue_type": classifier.classify(i).issue_type,
            "source": i.source, "status": i.status,
        } for i in issues]

    @app.post("/api/ralph/issues/auto-create")
    async def ralph_issues_auto_create() -> dict:
        """将未处理的 Issue 按策略自动生成为 WorkUnit。"""
        from ralph.issue_source_adapter import (
            LocalFileIssueSource, IssueClassifier, issues_to_work_units,
        )
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        issues_dir = ralph_dir / "issues"
        source = LocalFileIssueSource(issues_dir)
        classifier = IssueClassifier()
        policy = cfg.get_issue_policy()
        issues = source.fetch()
        classified = [classifier.classify(i) for i in issues]
        units = issues_to_work_units(classified, policy)
        # 写入 tasks 目录，供后续处理
        tasks_dir = ralph_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        import json as _json
        (tasks_dir / "auto_created_tasks.json").write_text(
            _json.dumps(units, indent=2, ensure_ascii=False),
        )
        return {"total_issues": len(issues), "auto_created": len(units), "tasks": units}

    # --- Ralph API: Source Docs Check + Coupling Analyzer 端点 ---

    @app.post("/api/ralph/source-docs/scan")
    async def ralph_source_docs_scan(body: dict[str, Any]) -> dict:
        from ralph.source_docs_check import SourceDocsCheck
        project_path = Path(body.get("path", os.environ.get("PROJECT_DIR", ".")))
        checker = SourceDocsCheck()
        deps = [{"name": d.name, "version": d.version, "category": d.category}
                for d in checker.scan_dependencies(project_path)]
        docs = [{"topic": d.topic, "url": d.url, "notes": d.notes}
                for d in checker.get_all_docs(deps)]
        return {"dependencies": deps, "docs_sources": docs,
                "report": checker.markdown_report(project_path)}

    @app.post("/api/ralph/coupling/analyze")
    async def ralph_coupling_analyze(body: dict[str, Any]) -> dict:
        from ralph.coupling_analyzer import CouplingAnalyzer
        project_path = Path(body.get("path", os.environ.get("PROJECT_DIR", ".")))
        analyzer = CouplingAnalyzer()
        modules = analyzer.analyze(project_path)
        return {
            "modules": [
                {"name": m.name, "file_count": m.file_count,
                 "import_degree": m.import_degree, "dependents": m.dependents,
                 "risk_score": m.risk_score}
                for m in modules
            ],
            "parallelization": analyzer.suggest_parallelization(modules),
        }

    # ── Issue Tracker Webhook + Config ─────────────────────

    @app.post("/api/ralph/issues/webhook")
    async def ralph_issues_webhook(body: dict[str, Any]) -> dict:
        """接收 GitHub Issue webhook。

        支持:
        - issue_comment: /ralph 命令解析 → 创建 Command
        - issues: opened/reopened → 自动同步
        """
        from ralph.issue_command_parser import comment_to_command

        action = body.get("action", "")
        issue_data = body.get("issue", {})
        comment_data = body.get("comment", {})
        issue_number = issue_data.get("number", 0)

        # Issue 评论命令
        if action == "created" and comment_data:
            cmd = comment_to_command(comment_data, str(issue_number))
            if cmd:
                from dashboard.models import Command as CmdModel
                command = CmdModel(
                    command_id=f"issue_cmd_{_now_iso()}",
                    type=cmd["type"],
                    target_id=cmd.get("work_id", issue_data.get("title", "")),
                    payload=cmd,
                    issued_at=_now_iso(),
                )
                repo: ProjectStateRepository = app.state.repository
                repo.save_command(command)
                logger.info("Issue #%s 命令已创建: %s", issue_number, cmd["type"])
                return {"webhook": "command_created", "issue": issue_number, "command": cmd["type"]}

        # Issue 打开/关闭 → 同步状态
        if action in ("opened", "reopened", "closed"):
            labels = [l.get("name", "") for l in issue_data.get("labels", [])]
            return {
                "webhook": "issue_sync",
                "issue": issue_number,
                "action": action,
                "labels": labels,
            }

        return {"webhook": "ignored", "action": action}

    @app.post("/api/ralph/issues/sync")
    async def ralph_issues_sync(body: dict[str, Any]) -> dict:
        """手动触发 Issue ↔ WorkUnit 同步。"""
        from ralph.issue_source_adapter import (
            GitHubIssueSource, LocalFileIssueSource, IssueClassifier,
        )
        from ralph.issue_sync_protocol import IssueSyncProtocol

        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        policy = cfg.get_issue_policy()
        protocol = IssueSyncProtocol(ralph_dir)

        # 从配置的 source 拉取
        source_type = body.get("source", "local")
        results: dict[str, Any] = {"synced_issues": 0, "commands_created": 0}

        if source_type == "github":
            tracker_cfg = cfg.get_issue_tracker_config()
            if tracker_cfg.get("repo"):
                source = GitHubIssueSource(
                    repo=tracker_cfg["repo"],
                    token=tracker_cfg.get("token", ""),
                    label=body.get("label", ""),
                )
            else:
                return {"error": "GitHub repo not configured", "synced": False}
        else:
            issues_dir = ralph_dir / "issues"
            source = LocalFileIssueSource(issues_dir)

        classifier = IssueClassifier()
        issues = source.fetch()
        classified = [classifier.classify(i) for i in issues]
        requests = protocol.sync_from_tracker(source, policy)
        results["synced_issues"] = len(requests)

        # 如果有需要自动创建的，写入 tasks 目录
        if requests:
            tasks_dir = ralph_dir / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)
            import json as _json
            (tasks_dir / "synced_tasks.json").write_text(
                _json.dumps(requests, indent=2, ensure_ascii=False),
            )
            results["commands_created"] = len(requests)
            results["requests"] = requests

        return results

    @app.get("/api/ralph/issues/config")
    async def ralph_issues_get_config() -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_issue_tracker_config()

    @app.put("/api/ralph/issues/config")
    async def ralph_issues_put_config(body: dict[str, Any]) -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_issue_tracker_config(body)

    @app.get("/api/ralph/issues/sync-status")
    async def ralph_issues_sync_status() -> dict:
        """获取同步状态。"""
        from ralph.issue_sync_protocol import IssueSyncProtocol
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        protocol = IssueSyncProtocol(ralph_dir)
        return protocol.get_sync_state()

    return app
def _analyze_project(project_path: Path) -> dict:
    """轻量级代码库侦察。"""
    import json as _json

    stats: dict[str, int] = {}
    key_files: dict[str, bool] = {}
    total_files = 0

    for ext in ["py", "ts", "tsx", "js", "jsx", "css", "html", "md", "json", "yaml", "yml", "sql", "go", "rs", "java"]:
        stats[ext] = 0

    key_patterns = [
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
        "tsconfig.json", "next.config.ts", "vite.config.ts",
        "README.md", "ARCHITECTURE.md", "Makefile", "Dockerfile",
        ".github/workflows",
    ]

    for f in project_path.rglob("*"):
        if f.is_file() and not any(p in f.parts for p in [".git", "node_modules", "__pycache__", ".next", "venv"]):
            total_files += 1
            ext = f.suffix.lstrip(".") or "other"
            stats[ext] = stats.get(ext, 0) + 1

            for kp in key_patterns:
                if str(f.relative_to(project_path)).endswith(kp) or kp in str(f):
                    key_files[str(f.relative_to(project_path))] = True

    # git info
    git_info = {}
    import subprocess
    try:
        git_info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path, text=True, timeout=5,
        ).strip()
        git_info["last_commit"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"],
            cwd=project_path, text=True, timeout=5,
        ).strip()
    except Exception:
        git_info = {"branch": "unknown", "last_commit": ""}

    return {
        "project_name": project_path.name,
        "total_files": total_files,
        "file_stats": {k: v for k, v in stats.items() if v > 0},
        "key_files": list(key_files.keys()),
        "git": git_info,
    }


def _serialize_work_unit(unit: Any) -> dict:
    """序列化 WorkUnit 为字典。"""
    from dataclasses import asdict

    from ralph.schema.work_unit import WorkUnit

    if not isinstance(unit, WorkUnit):
        return {}

    data = asdict(unit)
    data["status"] = unit.status.value

    # 序列化嵌套对象
    if unit.task_harness:
        data["task_harness"] = asdict(unit.task_harness)
    if unit.context_pack:
        data["context_pack"] = asdict(unit.context_pack)
    if unit.evidence:
        data["evidence"] = [asdict(e) for e in unit.evidence]
    if unit.review_result:
        data["review_result"] = _serialize_review_result(unit.review_result)

    return data


def _serialize_review_result(review: Any) -> dict:
    """序列化 ReviewResult 为字典。"""
    from dataclasses import asdict

    return asdict(review)


def _serialize_evidence(evidence: Any) -> dict:
    """序列化 Evidence 为前端期望的格式。

    前端期望字段: evidence_id, work_id, file_name, file_type, size_bytes, created_at
    后端存储字段: evidence_id, work_id, evidence_type, file_path, description, created_at
    """
    from pathlib import Path

    file_path = evidence.file_path
    file_name = Path(file_path).name if file_path else ""

    # 从 file_path 推断 file_type（对齐前端 Evidence.file_type 枚举）
    file_type = "other"
    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext in (".diff", ".patch"):
            file_type = "diff"
        elif ext in (".log"):
            file_type = "log"
        elif ext in (".txt", ".md", ".rst"):
            file_type = "test_output"
        elif ext in (".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c", ".h"):
            file_type = "other"
        elif ext in (".json", ".yaml", ".yml", ".xml"):
            file_type = "other"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            file_type = "screenshot"

    return {
        "evidence_id": evidence.evidence_id,
        "work_id": evidence.work_id,
        "file_name": file_name,
        "file_type": file_type,
        "size_bytes": 0,  # 暂时无法获取，设为 0
        "created_at": evidence.created_at,
    }


def _serialize_blocker(blocker: Any) -> dict:
    """序列化 Blocker 为前端期望的格式。

    前端期望字段: blocker_id, work_id, reason, category, created_at, resolved
    """
    return {
        "blocker_id": blocker.blocker_id,
        "work_id": blocker.work_id,
        "category": blocker.blocker_type,
        "reason": blocker.reason,
        "created_at": "",  # Blocker 没有 created_at 字段
        "resolved": blocker.resolved,
    }


def _redact_sensitive_content(content: str) -> str:
    """Redact 敏感信息如 API keys、密码等。"""
    # Redact API keys
    content = re.sub(
        r'(api[_-]?key["\']?\s*[:=]\s*)["\']?[a-zA-Z0-9_\-]{16,}["\']?',
        r'\1***REDACTED***',
        content,
        flags=re.IGNORECASE,
    )
    # Redact passwords
    content = re.sub(
        r'(password["\']?\s*[:=]\s*)["\'][^"\']+["\']',
        r'\1"***REDACTED***"',
        content,
        flags=re.IGNORECASE,
    )
    # Redact secrets
    content = re.sub(
        r'(secret["\']?\s*[:=]\s*)["\'][^"\']+["\']',
        r'\1"***REDACTED***"',
        content,
        flags=re.IGNORECASE,
    )
    # Redact tokens
    content = re.sub(
        r'(token["\']?\s*[:=]\s*)["\'][^"\']+["\']',
        r'\1"***REDACTED***"',
        content,
        flags=re.IGNORECASE,
    )
    return content


def _create_command(cmd_type: str, body: dict[str, Any]) -> Command:
    """从请求体创建 Command 对象，支持幂等键。"""
    from dashboard.models import Command
    return Command(
        command_id=f"cmd_{_now_iso()}",
        type=cmd_type,
        target_id=body.get("target_id", ""),
        payload=body.get("payload", {}),
        project_id=body.get("project_id", ""),
        run_id=body.get("run_id", ""),
        issued_at=_now_iso(),
        idempotency_key=body.get("idempotency_key", ""),
    )


def _generate_pm_response(
    repository: ProjectStateRepository,
    broadcast_queue: deque,
    product_manager: ProductManager | None = None,
) -> ChatMessage | None:
    """调用 ProductManager agent 生成 PM 回复。"""
    # 从 Repository 获取 chat history
    snapshot = repository.load_snapshot()
    chat_history = snapshot.chat_history

    if product_manager is None:
        logger.warning("ProductManager 未配置，使用 fallback 回复")
        pm_content = "PM 暂未就绪，请重试。"
    else:
        user_message = chat_history[-1].content if chat_history else ""
        pm_content = product_manager.chat_response(user_message, chat_history, repository)
        if not pm_content:
            logger.error("ProductManager.chat_response 返回空结果")
            pm_content = "PM 处理消息时出错，请重试。"

    pm_msg = ChatMessage(
        id=f"pm_{_now_iso()}",
        role="pm",
        content=pm_content,
    )

    # 持久化到 Repository
    repository.add_chat_message(pm_msg)

    # 广播给 WebSocket 客户端
    event = repository.append_event(
        type="pm_response",
        pm_response={
            "id": pm_msg.id,
            "content": pm_content,
            "timestamp": pm_msg.timestamp,
            "action_triggered": "",
        },
    )
    _emit_to_ws(broadcast_queue, event)

    return pm_msg
