"""Dashboard REST API 路由和 WebSocket 端点 — 接入 ProjectStateRepository + CommandProcessor + CommandConsumer。"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import re
import tempfile
import threading
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.product_manager import ProductManager
    from dashboard.coordinator import PMCoordinator

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from dashboard.command_processor import CommandProcessor
from dashboard.consumer import CommandConsumer
from dashboard.event_bus import EventBus
from dashboard.api.ralph_extended_routes import register_ralph_extended_routes
from core.state_models import ChatMessage, Command, Event, ModuleAssignment
from dashboard.state_repository import ProjectStateRepository
from ralph.command_handler import RalphCommandHandler
from ralph.config_manager import RalphConfigManager
from ralph.report_generator import ReportGenerator
from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus

logger = logging.getLogger(__name__)

OPTIONAL_CAPABILITIES: dict[str, str] = {
    "project_analyzer": "ralph.project_analyzer",
    "taste_memory": "ralph.taste_memory",
    "memory_manager": "ralph.memory_manager",
    "context_engine": "ralph.context_engine",
    "pm_agent": "ralph.pm_agent",
    "turn_engine": "ralph.turn_engine",
    "knowledge_graph": "ralph.knowledge_graph",
    "retrieval_pipeline": "ralph.retrieval_pipeline",
    "pipeline": "ralph.pipeline",
    "graphify_service": "ralph.graphify_service",
    "issue_command_parser": "ralph.issue_command_parser",
    "issue_sync_protocol": "ralph.issue_sync_protocol",
    "ship_service": "ralph.ship_service",
    "recovery": "ralph.recovery",
}


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _build_capabilities() -> dict[str, dict[str, Any]]:
    return {
        name: {"module": module_name, "available": _module_available(module_name)}
        for name, module_name in OPTIONAL_CAPABILITIES.items()
    }


def _require_capability(app: FastAPI, capability: str) -> None:
    info = getattr(app.state, "ralph_capabilities", {}).get(capability, {})
    if info.get("available", False):
        return
    module_name = info.get("module", OPTIONAL_CAPABILITIES.get(capability, capability))
    raise HTTPException(
        status_code=501,
        detail=f"Feature not implemented: missing module `{module_name}`",
    )


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




def _write_pyproject(project_path: Path, name: str) -> None:
    """创建 pyproject.toml 模板。"""
    content = f'''[project]
name = "{name}"
version = "0.1.0"
description = ""
requires-python = ">=3.12"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff"]

[tool.ruff]
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
'''
    (project_path / "pyproject.toml").write_text(content, encoding="utf-8")


def _write_package_json(project_path: Path, name: str) -> None:
    """创建 package.json 模板。"""
    import json
    data = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
            "lint": "next lint",
            "test": "jest",
        },
    }
    (project_path / "package.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _write_gitignore(path: Path) -> None:
    """创建 .gitignore。"""
    content = """# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
*.egg-info/
dist/
build/
.eggs/

# Node
node_modules/
.next/
.nuxt/
.output/
dist/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
.env.*.local

# Ralph runtime data (managed externally at ~/.ralph/)
.ralph/

# State files
data/tasks.db
data/execution-plan.json

# Test results
coverage/
.coverage
test-results/
playwright-report/
"""
    path.write_text(content, encoding="utf-8")


def _write_claude_md(path: Path, name: str) -> None:
    """创建 CLAUDE.md 项目指令模板。"""
    content = f"""# {name}

## 项目简介
<!-- 在此填写项目定位 -->

## 技术栈
<!-- 编程语言、框架、数据库 -->

## 编码规范
- 遵循 PEP 8 / ESLint 规范
- 所有函数必须有类型注解
- 测试覆盖率 >= 80%

## 工作流程
- 修改前先读相关文件，理解现有代码
- 修改后运行测试确保不破坏已有功能
- 不修改和当前任务无关的代码
- 有疑问时优先查文档
"""
    path.write_text(content, encoding="utf-8")
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
    app.state.ralph_capabilities = _build_capabilities()

    # Resolve project_dir uniformly at function scope top
    project_dir = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

    @app.exception_handler(ModuleNotFoundError)
    async def _module_not_found_handler(_, exc: ModuleNotFoundError) -> JSONResponse:
        # 显式降级缺失能力，避免调用端点时抛 500。
        mod = exc.name or ""
        if mod.startswith("ralph."):
            return JSONResponse(
                status_code=501,
                content={
                    "detail": f"Feature not implemented: missing module `{mod}`",
                    "error_type": "module_not_available",
                },
            )
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # 统一解析项目目录（单一事实源）
    project_dir = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

    # 注入 RalphRepository
    if ralph_repository is None:
        from core.ralph_paths import resolve_ralph_dir
        ralph_dir = resolve_ralph_dir(project_dir)
        ralph_repository = RalphRepository(ralph_dir)
    app.state.ralph_repository = ralph_repository

    # 注入 WorkUnitEngine（如果未提供则从 project_dir 初始化）
    if ralph_engine is None:
        from ralph.work_unit_engine import WorkUnitEngine
        ralph_engine = WorkUnitEngine(project_dir)
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
    # 热重载保护：event_bus 在 reload 时可能异常
    if isinstance(event_bus, EventBus) and hasattr(event_bus, "emit") and callable(event_bus.emit):
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
    ralph_handler = RalphCommandHandler(
        ralph_repository._ralph_dir,
        engine=getattr(app.state, "ralph_engine", None),
    )
    app.state.consumer = CommandConsumer(
        repository=repository,
        processor=processor,
        event_bus=event_bus,
        ralph_handler=ralph_handler,
        ralph_engine=getattr(app.state, "ralph_engine", None),
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
    async def get_execution_ledger(
        feature_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        executions = app.state.repository.get_execution_history(feature_id=feature_id)
        if agent_id is not None:
            executions = [e for e in executions if e.get("agent_id") == agent_id]
        if status is not None:
            executions = [e for e in executions if e.get("status") == status]

        summary = {
            "total_executions": len(executions),
            "completed": sum(1 for e in executions if e.get("status") == "completed"),
            "failed": sum(1 for e in executions if e.get("status") == "failed"),
            "blocked": sum(1 for e in executions if e.get("status") == "blocked"),
            "retrying": sum(1 for e in executions if e.get("status") == "retrying"),
        }
        return {"executions": executions, "summary": summary}

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

        # Resolve project directory from request body, fallback to PM's default
        requested_dir = body.get("project_id") or body.get("project_dir")
        pm_dir = app.state.product_manager.project_dir if app.state.product_manager else None
        if requested_dir and requested_dir != "default":
            project_dir = Path(requested_dir).resolve()
            if not project_dir.exists():
                project_dir = pm_dir or Path(".")
        else:
            project_dir = pm_dir or Path(".")

        # 调用 PM 生成回复
        pm_msg, steps = _generate_pm_response(
            app.state.repository,
            app.state.broadcast_queue,
            app.state.product_manager,
            app.state.config_manager,
            project_dir=project_dir,
        )

        return {
            "success": True,
            "message_id": msg.id,
            "pm_response": pm_msg.to_dict() if pm_msg else None,
            "steps": steps,
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

    @app.get("/api/ralph/capabilities")
    async def ralph_capabilities() -> dict:
        return {"capabilities": app.state.ralph_capabilities}

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

    # ── Taste Memory ───────────────────────────────────────────

    @app.get("/api/ralph/tastes")
    async def ralph_list_tastes() -> dict:
        """获取所有设计偏好记忆。"""
        _require_capability(app, "taste_memory")
        from ralph.taste_memory import TasteMemory
        ralph_dir: Path = app.state.ralph_repository._ralph_dir
        tm = TasteMemory(storage_dir=str(ralph_dir))
        return {"tastes": tm.get_all()}

    @app.delete("/api/ralph/tastes/{taste_id}")
    async def ralph_delete_taste(taste_id: str) -> dict:
        """删除一条设计偏好记忆。"""
        _require_capability(app, "taste_memory")
        from ralph.taste_memory import TasteMemory
        ralph_dir: Path = app.state.ralph_repository._ralph_dir
        tm = TasteMemory(storage_dir=str(ralph_dir))
        deleted = tm.delete(taste_id)
        return {"success": deleted, "taste_id": taste_id}

    @app.post("/api/ralph/tastes")
    async def ralph_create_taste(body: dict) -> dict:
        """手动创建一条 taste 偏好。"""
        _require_capability(app, "memory_manager")
        from ralph.memory_manager import MemoryManager
        ralph_dir: Path = app.state.ralph_repository._ralph_dir
        mgr = MemoryManager(ralph_dir)
        taste_id = body.get("id", f"taste-{_now_iso().replace(':', '-').replace('.', '-')}")
        result = mgr.record_taste(
            taste_id=taste_id,
            preference_type=body.get("preference_type", "neutral"),
            category=body.get("category", "overall"),
            description=body.get("description", ""),
            source="manual",
            confidence=body.get("confidence", 1.0),
            metadata=body.get("metadata"),
        )
        mgr.close()
        if result is None:
            raise HTTPException(status_code=500, detail="TasteMemory 未初始化")
        return result

    # ── Prompt Injection Guard ─────────────────────────────────

    @app.get("/api/ralph/security/guard-status")
    async def ralph_guard_status() -> dict:
        """获取 Prompt Injection 防护状态。"""
        engine = getattr(app.state, "ralph_engine", None)
        if engine is None or not hasattr(engine, "_injection_guard"):
            raise HTTPException(status_code=503, detail="Ralph engine not configured")
        return engine._injection_guard.get_status()

    @app.post("/api/ralph/security/scan")
    async def ralph_scan_prompt(payload: dict) -> dict:
        """手动扫描文本的注入风险（调试用）。"""
        engine = getattr(app.state, "ralph_engine", None)
        if engine is None or not hasattr(engine, "_injection_guard"):
            raise HTTPException(status_code=503, detail="Ralph engine not configured")
        text = payload.get("text", "")
        severity = payload.get("severity_threshold", "中")
        cleaned, violations = engine._injection_guard.scan_input(text, severity)
        return {
            "cleaned": cleaned,
            "violations": [v.to_dict() for v in violations],
        }

    @app.get("/api/ralph/blockers")
    async def ralph_list_blockers(work_id: str | None = None, resolved: bool | None = None) -> list[dict]:
        """获取所有阻塞项，支持过滤。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        blockers = ralph_repo.list_blockers(work_id=work_id, resolved=resolved)
        return [_serialize_blocker(b) for b in blockers]

    @app.get("/api/ralph/state-snapshot")
    async def ralph_state_snapshot() -> dict:
        """统一状态快照（RalphRepository 新状态模型）。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        return ralph_repo.snapshot()

    @app.get("/api/ralph/blocking-issues")
    async def ralph_list_blocking_issues(status: str | None = None) -> dict:
        """列出统一阻塞项。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        issues = ralph_repo.list_blocking_issues(status=status)
        return {"issues": [i.to_dict() for i in issues], "total": len(issues)}

    @app.get("/api/ralph/execution-ledger")
    async def ralph_get_execution_ledger() -> dict:
        """执行账本。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        return ralph_repo.snapshot()

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

    @app.get("/api/ralph/work-units/{work_id}/checkpoints")
    async def ralph_list_checkpoints(work_id: str) -> list[dict]:
        """获取 WorkUnit 的 checkpoint 列表。"""
        ralph_repo: RalphRepository = app.state.ralph_repository
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")

        checkpoint_dir = ralph_repo._ralph_dir / "checkpoints"
        if not checkpoint_dir.is_dir():
            return []

        checkpoints: list[dict] = []
        for path in sorted(checkpoint_dir.glob(f"{work_id}.turn-*.json")):
            try:
                checkpoints.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return checkpoints

    @app.post("/api/ralph/work-units/{work_id}/checkpoints/{turn}/restore")
    async def ralph_restore_checkpoint(work_id: str, turn: int) -> dict:
        """从指定 checkpoint 恢复工作状态。"""
        _require_capability(app, "turn_engine")
        ralph_repo: RalphRepository = app.state.ralph_repository
        unit = ralph_repo.get_work_unit(work_id)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"WorkUnit {work_id} not found")

        try:
            from ralph.turn_engine import TurnBasedExecutionEngine
            project_dir = Path(os.environ.get("PROJECT_DIR", "."))
            engine = TurnBasedExecutionEngine(project_dir)
            return engine.restore_from_checkpoint(work_id, turn)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"恢复失败: {e}")

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
        from core.state_models import Command

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

    @app.get("/api/ralph/projects/recent")
    async def ralph_list_recent_projects() -> list[dict]:
        """列出最近打开的项目（轻量，用于侧边栏切换器）。"""
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.list_recent_projects()

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
        """初始化新项目。

        创建标准项目骨架：
        - 源码目录 (src/)
        - 测试目录 (tests/)
        - 文档目录 (docs/)
        - 数据目录 (data/)
        - .gitignore（含 .ralph/ 排除规则）
        - CLAUDE.md（项目指令模板）
        - .ralph/ 外部数据目录（通过 resolve_ralph_dir）
        - git init
        """
        path_str = body.get("path", "")
        name = body.get("name", "")
        tech_stack = body.get("tech_stack", "")  # 可选：python / nodejs / fullstack
        if not path_str:
            raise HTTPException(status_code=422, detail="path is required")

        project_path = Path(path_str).resolve()
        if (project_path / ".ralph").exists():
            raise HTTPException(status_code=400, detail=f"目录 {path_str} 已存在 Ralph 项目数据，请选择其他路径")
        project_path.mkdir(parents=True, exist_ok=True)

        # 1. 创建标准目录结构
        dirs_to_create = ["src", "tests", "docs", "data"]
        for d in dirs_to_create:
            (project_path / d).mkdir(exist_ok=True)

        # 根据技术栈创建额外目录
        if tech_stack in ("python", "fullstack"):
            (project_path / "src" / "__init__.py").touch()
            (project_path / "tests" / "__init__.py").touch()
            if not (project_path / "pyproject.toml").exists():
                _write_pyproject(project_path, name or project_path.name)
        if tech_stack in ("nodejs", "fullstack"):
            if not (project_path / "package.json").exists():
                _write_package_json(project_path, name or project_path.name)

        # 2. 创建 .gitignore（如果不存在）
        gitignore_path = project_path / ".gitignore"
        if not gitignore_path.exists():
            _write_gitignore(gitignore_path)

        # 3. 创建 CLAUDE.md 模板（如果不存在）
        claude_md_path = project_path / "CLAUDE.md"
        if not claude_md_path.exists():
            _write_claude_md(claude_md_path, name or project_path.name)

        # 4. 初始化外部 .ralph/ 数据目录
        from core.ralph_paths import resolve_ralph_dir
        ralph_dir = resolve_ralph_dir(project_path)
        for sub in ["config", "work_units", "evidence", "reviews", "blockers", "state", "memory", "reports", "retros"]:
            (ralph_dir / sub).mkdir(parents=True, exist_ok=True)

        # 5. 初始化 git
        import subprocess
        try:
            subprocess.run(["git", "init", "-b", "main"], cwd=project_path, capture_output=True, timeout=10)
            subprocess.run(["git", "config", "user.name", "CodeForge"], cwd=project_path, capture_output=True, timeout=5)
            subprocess.run(["git", "config", "user.email", "codeforge@local"], cwd=project_path, capture_output=True, timeout=5)
            # 首次提交骨架
            subprocess.run(["git", "add", "-A"], cwd=project_path, capture_output=True, timeout=5)
            subprocess.run(["git", "commit", "-m", "chore: initial project scaffold"], cwd=project_path, capture_output=True, timeout=10)
        except Exception:
            pass  # git 可能不可用或已初始化

        # 6. 注册到最近项目
        cfg: RalphConfigManager = app.state.config_manager
        cfg.add_recent_project(str(project_path), name or project_path.name)

        return {
            "success": True,
            "name": name or project_path.name,
            "path": str(project_path),
            "ralph_dir": str(ralph_dir),
            "dirs_created": dirs_to_create,
        }

    @app.get("/api/ralph/fs/list")
    async def ralph_fs_list(path: str = "/") -> dict:
        """列出指定目录下的子目录（用于前端目录选择器）。"""
        target = Path(path).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            raise HTTPException(status_code=400, detail=f"目录不存在: {path}")
        entries = []
        try:
            for child in sorted(target.iterdir()):
                if child.name.startswith("."):
                    continue
                if child.is_dir():
                    entries.append({"name": child.name, "path": str(child), "is_dir": True})
        except PermissionError:
            raise HTTPException(status_code=403, detail="无权限访问该目录")
        return {"path": str(target), "parent": str(target.parent) if target.parent != target else None, "entries": entries}

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

    def _get_brainstorm_manager() -> "BrainstormManager":
        """从 app.state 获取 config_manager 并创建 BrainstormManager。"""
        from ralph.brainstorm_manager import BrainstormManager
        from ralph.config_manager import RalphConfigManager
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        return BrainstormManager(ralph_dir, cfg)

    @app.get("/api/ralph/brainstorm/sessions")
    async def ralph_list_brainstorm_sessions() -> list[dict]:
        return _get_brainstorm_manager().list_sessions()

    @app.post("/api/ralph/brainstorm/start")
    async def ralph_start_brainstorm(body: dict[str, Any]) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.start_session(
            body.get("project_name", "Unnamed"),
            body.get("user_message", ""),
        )
        # V2: 走 explore_product 路径，_render_question_with_llm 会调用 LLM
        questions = mgr.explore_product(record)
        if not questions:
            questions = mgr.generate_questions(record, use_llm=True)
        summary = mgr.get_summary(record)
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "record_id": record.record_id,
            "phase": record.current_phase,
            "questions": questions,
            "summary": summary,
            "feature_tree": brainstorm_to_dict(record.feature_tree),
            "active_node": record.feature_tree.current_exploring_id,
        }

    @app.post("/api/ralph/brainstorm/respond")
    async def ralph_brainstorm_respond(body: dict[str, Any]) -> dict:
        record_id = body.get("record_id", "")
        if not record_id:
            raise HTTPException(status_code=422, detail="record_id required")
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        # V2: 走 process_response_v2 路径
        updated = mgr.process_response_v2(record, body.get("user_response", ""),
                                          body.get("extracted_facts"))
        # 根据当前 phase 生成问题
        phase_val = updated.current_phase.value if hasattr(updated.current_phase, "value") else str(updated.current_phase)
        if phase_val == "product_def":
            questions = mgr.explore_product(updated)
        elif phase_val == "feature_decompose":
            active = mgr.get_active_node(updated)
            if active:
                updated.feature_tree.question_plan = []
                mgr.build_question_plan(updated, active)
            questions = mgr.generate_questions(updated, use_llm=True)
        else:
            questions = mgr.generate_questions(updated, use_llm=True)
        if not questions:
            questions = ["请补充更多细节"]
        is_complete = mgr.is_complete_v2(updated)
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        current_q = None
        if updated.feature_tree.current_question_id:
            for t in updated.feature_tree.question_plan:
                if t.question_id == updated.feature_tree.current_question_id:
                    current_q = brainstorm_to_dict(t)
                    break
        granularity_missing = []
        active_node = mgr.get_active_node(updated)
        if active_node:
            granularity_missing = mgr._get_missing_items(active_node)
        return {
            "record_id": updated.record_id,
            "round": updated.round_number,
            "phase": str(updated.current_phase),
            "questions": questions,
            "is_complete": is_complete,
            "completeness": updated.completeness_score(),
            "summary": mgr.get_summary(updated),
            "feature_tree": brainstorm_to_dict(updated.feature_tree),
            "active_node": updated.feature_tree.current_exploring_id,
            "current_question": current_q,
            "granularity_status": granularity_missing,
            "spec_preview": "",
        }

    # --- Ralph API: Brainstorm V2 端点 ---

    @app.get("/api/ralph/brainstorm/{record_id}/tree")
    async def ralph_get_feature_tree(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {"feature_tree": brainstorm_to_dict(record.feature_tree)}

    @app.get("/api/ralph/brainstorm/{record_id}/spec")
    async def ralph_get_spec_document(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"spec": mgr.generate_spec_document(record)}

    @app.post("/api/ralph/brainstorm/{record_id}/resume")
    async def ralph_resume_session(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.resume_session(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "record_id": record.record_id,
            "phase": record.current_phase,
            "feature_tree": brainstorm_to_dict(record.feature_tree),
            "active_node": record.feature_tree.current_exploring_id,
        }

    @app.post("/api/ralph/brainstorm/{record_id}/advance")
    async def ralph_advance_phase(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        success = mgr.advance_phase(record)
        return {"success": success, "phase": record.current_phase}

    @app.get("/api/ralph/brainstorm/{record_id}/relationships")
    async def ralph_get_relationships(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return brainstorm_to_dict(record.relationship_graph)

    @app.post("/api/ralph/brainstorm/{record_id}/review")
    async def ralph_trigger_review(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.brainstorm_analyzer import BrainstormAnalyzer
        analyzer = BrainstormAnalyzer(mgr._config)
        result = analyzer.independent_review(record)
        return {
            "passed": result.passed,
            "findings": [
                {
                    "finding_type": f.finding_type,
                    "feature_id": f.feature_id,
                    "description": f.description,
                    "severity": f.severity,
                }
                for f in result.findings
            ],
        }

    @app.post("/api/ralph/brainstorm/{record_id}/decompose")
    async def ralph_trigger_decompose(record_id: str, body: dict[str, Any] | None = None) -> dict:
        """§7.2 触发功能节点分解"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        children_names = (body or {}).get("children_names", [])
        if not isinstance(children_names, list):
            children_names = [children_names] if children_names else []
        mgr.decompose_node(record, children_names)
        mgr._save(record)
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "feature_tree": brainstorm_to_dict(record.feature_tree),
            "current_phase": record.current_phase.value,
        }

    @app.get("/api/ralph/brainstorm/{record_id}/questions")
    async def ralph_get_question_plan(record_id: str) -> dict:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "question_plan": [brainstorm_to_dict(t) for t in record.feature_tree.question_plan],
            "current_question_id": record.feature_tree.current_question_id,
        }

    @app.get("/api/ralph/brainstorm/{record_id}/handoff")
    async def ralph_get_handoff_hints(record_id: str) -> list[dict]:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return [brainstorm_to_dict(h) for h in record.task_handoff_hints]

    @app.post("/api/ralph/brainstorm/{record_id}/handoff/generate")
    async def ralph_generate_handoff_hints(record_id: str) -> list[dict]:
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        from ralph.brainstorm_analyzer import BrainstormAnalyzer
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        analyzer = BrainstormAnalyzer(mgr._config)
        hints = analyzer.generate_task_handoff_hints(record)
        return [brainstorm_to_dict(h) for h in hints]

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

    # --- Ralph API: Decision Log (ADR) 端点 ---

    @app.get("/api/ralph/decisions")
    async def ralph_list_decisions() -> list[dict]:
        """列出所有架构决策记录。"""
        from ralph.decision_log import DecisionLog
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        return DecisionLog(ralph_dir).list_all()

    @app.post("/api/ralph/decisions")
    async def ralph_create_decision(body: dict[str, Any]) -> dict:
        """创建一条架构决策记录。"""
        from ralph.decision_log import DecisionLog
        from dataclasses import asdict
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        adr = DecisionLog(ralph_dir).create(
            title=body.get("title", ""),
            context=body.get("context", ""),
            decision=body.get("decision", ""),
            alternatives=body.get("alternatives"),
            consequences=body.get("consequences", ""),
        )
        return asdict(adr)

    @app.get("/api/ralph/decisions/{adr_id}")
    async def ralph_get_decision(adr_id: str) -> dict:
        """获取单条架构决策记录。"""
        from ralph.decision_log import DecisionLog
        from dataclasses import asdict
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        adr = DecisionLog(ralph_dir).get(adr_id)
        if adr is None:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")
        return asdict(adr)

    @app.post("/api/ralph/decisions/{adr_id}/accept")
    async def ralph_accept_decision(adr_id: str) -> dict:
        """接受一条架构决策。"""
        from ralph.decision_log import DecisionLog
        from dataclasses import asdict
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        try:
            adr = DecisionLog(ralph_dir).accept(adr_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return asdict(adr)

    @app.post("/api/ralph/decisions/{adr_id}/supersede")
    async def ralph_supersede_decision(adr_id: str, body: dict[str, Any]) -> dict:
        """用新决策取代一条架构决策。"""
        from ralph.decision_log import DecisionLog
        from dataclasses import asdict
        superseded_by = body.get("superseded_by", "")
        if not superseded_by:
            raise HTTPException(status_code=422, detail="superseded_by required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        try:
            adr = DecisionLog(ralph_dir).supersede(adr_id, superseded_by)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return asdict(adr)

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
    # 高级模块端点（确保已真实注册）
    @app.get("/api/ralph/memory/status")
    async def ralph_memory_status() -> dict:
        _require_capability(app, "memory_manager")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_manager import MemoryManager

        return MemoryManager(ralph_dir).get_status()

    @app.get("/api/ralph/knowledge-graph/status")
    async def ralph_kg_status() -> dict:
        _require_capability(app, "knowledge_graph")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.knowledge_graph import KnowledgeGraphService

        return KnowledgeGraphService(ralph_dir).get_status()

    @app.get("/api/ralph/executions")
    async def ralph_list_executions() -> list[str]:
        _require_capability(app, "turn_engine")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.turn_engine import TurnBasedExecutionEngine

        engine = TurnBasedExecutionEngine(ralph_dir.parent)
        return engine.list_executions()

    @app.get("/api/ralph/executions/{work_id}")
    async def ralph_get_execution(work_id: str) -> dict:
        _require_capability(app, "turn_engine")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.turn_engine import TurnBasedExecutionEngine

        engine = TurnBasedExecutionEngine(ralph_dir.parent)
        result = engine.get_execution_status(work_id)
        if result is None:
            return {"success": False, "error": f"执行记录 {work_id} 不存在"}
        return {"success": True, "execution": result}

    if app.state.ralph_capabilities["recovery"]["available"]:
        from ralph.recovery import StartupRecover

        startup_recover = StartupRecover(app.state.ralph_repository._ralph_dir)
        startup_recover.run(app.state.ralph_repository)
        app.state.startup_recover = startup_recover
    else:
        app.state.startup_recover = None

    @app.get("/api/recovery-report")
    async def get_recovery_report() -> dict:
        if app.state.startup_recover is None:
            raise HTTPException(status_code=501, detail="Feature not implemented: missing module `ralph.recovery`")
        report = app.state.startup_recover.get_report()
        if report is None:
            return {"success": True, "report": None}
        return {
            "success": True,
            "report": {
                "interrupted_count": report.interrupted_count,
                "work_unit_ids": report.work_unit_ids,
                "titles": report.titles,
                "created_at": report.created_at,
            },
        }

    try:
        from dashboard.api.feature_routes import router as feature_router
    except ModuleNotFoundError as err:
        logger.warning("feature_routes missing, dashboard starts without feature routes: %s", err)
        feature_router = APIRouter()
    app.include_router(feature_router)
    app.include_router(register_ralph_extended_routes(app))

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
        "size_bytes": Path(file_path).stat().st_size if file_path and Path(file_path).exists() else 0,
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
    from core.state_models import Command
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


_PM_QUERY_RULES = [
    ("project_info", ["介绍", "架构", "技术栈", "项目结构", "项目概况", "项目总结", "overview", "总结项目"]),
    ("risk", ["风险", "阻塞", "问题", "隐患", "bug", "缺陷", "有什么不好的", "需要关注"]),
    ("progress", ["进展", "完成", "进度", "做了什么", "work unit", "工作状态", "进度如何", "完成情况"]),
    ("code_search", ["在哪", "哪个文件", "哪个模块", "谁负责", "搜索", "查找", "find", "search"]),
]


def _classify_pm_query(user_message: str) -> str:
    """PM 对话意图分类：project_info / progress / risk / code_search / general。"""
    msg_lower = user_message.lower()
    for query_type, keywords in _PM_QUERY_RULES:
        for kw in keywords:
            if kw.lower() in msg_lower:
                return query_type
    return "general"


def _fallback_project_info(project_dir: Path, parts: list) -> None:
    """当 Claude Code 不可用时，使用 ProjectAnalyzer 做项目分析。"""
    try:
        from ralph.project_analyzer import ProjectAnalyzer
        analyzer = ProjectAnalyzer(project_dir)
        report = analyzer.get_saved_report()
        if report:
            parts.append(f"项目分析报告（已缓存）:\n{report[:3000]}")
        else:
            stats = analyzer.analyze()
            parts.append(f"项目统计:\n{analyzer._to_markdown(stats)}")
    except Exception as e:
        parts.append(f"项目分析失败: {e}")


def _gather_tool_context(
    query_type: str,
    user_message: str,
    project_dir: Path,
    repository: Any = None,
) -> str:
    """根据意图类型调用 Ralph 内部工具，返回结构化上下文文本。"""
    parts: list[str] = []

    if query_type == "project_info":
        # 调用 Claude CLI 扫描项目（非纯 LLM 猜测）
        try:
            import subprocess
            prompt = (
                f"请用 Bash 工具扫描 {project_dir.name} 目录结构，找出主要编程语言、"
                "关键目录和文件，然后总结：1) 项目用途和技术栈 2) 主要模块结构 3) 关键文件作用。"
                "控制在 300 字以内。"
            )
            proc = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", "-p", prompt],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                parts.append(f"Claude Code 分析结果:\n{proc.stdout.strip()[:3000]}")
            else:
                # fallback 到 ProjectAnalyzer
                _fallback_project_info(project_dir, parts)
        except Exception as e:
            parts.append(f"Claude Code 扫描失败: {e}")
            _fallback_project_info(project_dir, parts)

    elif query_type == "code_search":
        # 调用 Claude CLI 搜索代码
        try:
            import subprocess
            proc = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", "-p",
                 f"在 {project_dir.name} 目录中搜索与以下查询相关的代码: {user_message}\n"
                 "请找出相关文件并说明其作用。控制在 200 字以内。"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                parts.append(f"Claude Code 搜索结果:\n{proc.stdout.strip()[:3000]}")
            else:
                parts.append("未找到相关结果。")
        except Exception as e:
            parts.append(f"代码搜索失败: {e}")

    elif query_type == "progress":
        # 从 repository 拿 feature 进度
        if repository:
            try:
                features = repository.list_features()
                state_counts: dict[str, int] = {}
                for f in features:
                    s = getattr(f, "status", "unknown")
                    state_counts[s] = state_counts.get(s, 0) + 1
                total = len(features)
                done = state_counts.get("done", 0) + state_counts.get("approved", 0)
                pct = f"{done}/{total}" if total else "0/0"
                parts.append(f"功能状态汇总:\n{json.dumps(state_counts, ensure_ascii=False, indent=2)}\n已完成: {pct}")
                # 取最近几个 feature 的详情
                recent = [f.to_dict() for f in features[:5]]
                if recent:
                    parts.append(f"最近功能 (前5条):\n{json.dumps(recent, ensure_ascii=False, indent=2)[:2000]}")
                else:
                    parts.append("暂无 Feature 数据。")
            except Exception as e:
                parts.append(f"进度查询失败: {e}")

    elif query_type == "risk":
        # 从 repository 拿 blocking_issues
        if repository:
            try:
                issues = repository.list_blocking_issues(resolved=False)
                if issues:
                    parts.append(f"未解决的阻塞问题:\n{json.dumps([i.to_dict() for i in issues[:10]], ensure_ascii=False, indent=2)[:2000]}")
                else:
                    parts.append("当前无未解决的阻塞问题。")
            except Exception as e:
                parts.append(f"风险查询失败: {e}")

    elif query_type == "code_search":
        # 调用 retrieval_pipeline 做融合搜索
        try:
            from ralph.retrieval_pipeline import RetrievalPipeline
            from ralph.repositories import Repository
            repo = Repository(project_dir / ".ralph")
            pipeline = RetrievalPipeline(repo, project_dir=project_dir)
            results = pipeline.fusion_search(user_message, top_k=5)
            if results.get("results"):
                parts.append(f"搜索结果 (query='{user_message}'):\n{json.dumps(results, ensure_ascii=False, indent=2)[:3000]}")
            else:
                parts.append(f"未找到相关结果。")
        except Exception as e:
            parts.append(f"代码搜索失败: {e}")

    # general 不收集上下文

    return "\n\n".join(parts) if parts else ""


_QUERY_INTENT_LABELS = {
    "project_info": "项目分析",
    "progress": "进度查询",
    "risk": "风险评估",
    "code_search": "代码搜索",
    "general": "通用对话",
}


@dataclass
class ChatStep:
    """PM 对话执行步骤，用于前端实时展示工作进度。"""
    label: str
    status: str  # running / done / error
    detail: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.ended_at:
            return round((self.ended_at - self.started_at) * 1000, 0)
        return 0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "duration_ms": int(self.duration_ms),
        }


def _llm_chat_response(
    user_message: str,
    chat_history: list,
    config_manager: Any,
    project_dir: Path,
    repository: Any = None,
) -> tuple[str, list[dict]]:
    """通过 LLM 生成 PM 对话回复。

    流程：意图识别 → 调 Ralph 内部工具获取数据 → LLM 汇总工具结果。
    不直接把项目代码塞给 LLM，而是用工具返回的结构化数据作为上下文。

    返回: (回复内容, 执行步骤列表)
    """
    import time
    steps: list[ChatStep] = []

    if config_manager is None:
        return "我还没连接到大脑，请先在配置中心设置 LLM Provider。", [
            ChatStep("连接配置中心", "error", "未找到 LLM 配置").to_dict(),
        ]

    # Step 1: 意图分类
    step1 = ChatStep("意图识别", "running", started_at=time.perf_counter())
    steps.append(step1)
    query_type = _classify_pm_query(user_message)
    intent_label = _QUERY_INTENT_LABELS.get(query_type, query_type)
    step1.status = "done"
    step1.detail = f"识别为「{intent_label}」意图"
    step1.ended_at = time.perf_counter()

    # Step 2: 调工具收集上下文
    step2 = ChatStep("查询项目数据", "running", started_at=time.perf_counter())
    steps.append(step2)
    tool_context = _gather_tool_context(query_type, user_message, project_dir, repository)
    if tool_context:
        step2.status = "done"
        preview = tool_context.split("\n")[0][:80]
        step2.detail = f"已获取数据：{preview}..."
    else:
        step2.status = "done"
        step2.detail = "无相关数据"
    step2.ended_at = time.perf_counter()

    # Step 3: 构建 prompt
    project_name = project_dir.name
    system_parts = [
        f"你是 Ralph，一个 AI 项目经理。当前项目: {project_name}。",
        "请用简洁、专业的中文回复用户，使用 Markdown 格式。",
    ]

    if tool_context:
        system_parts.append(
            f"以下是工具返回的项目数据，请基于这些数据回答用户的问题：\n\n{tool_context}"
        )
        system_parts.append(
            "请严格基于上面的数据回答，不要编造数据。"
            "如果数据不足以完整回答，说明哪些信息还需要进一步查询。"
        )

    messages: list[dict] = [{"role": "system", "content": "\n\n".join(system_parts)}]

    # 添加最近对话历史
    recent = [m for m in chat_history if m.role in ("user", "pm")][-10:]
    for m in recent:
        messages.append({"role": "user" if m.role == "user" else "assistant", "content": m.content})

    messages.append({"role": "user", "content": user_message})

    # Step 4: 调用 LLM
    step3 = ChatStep("向 AI 发送请求", "running", started_at=time.perf_counter())
    steps.append(step3)
    try:
        provider = config_manager.resolve_agent_provider("product", "pm_chat")
    except Exception:
        provider = {"provider_id": "", "model": "", "source": "none"}

    if not provider.get("provider_id"):
        logger.warning("无可用 LLM Provider，PM 聊天降级为 fallback")
        step3.status = "error"
        step3.detail = "未配置 LLM Provider"
        step3.ended_at = time.perf_counter()
        return "还没有配置 LLM Provider，请在配置中心添加一个。", [s.to_dict() for s in steps]

    step3.detail = f"模型: {provider.get('model', '')}"
    result = config_manager.proxy_request(
        provider["provider_id"],
        "v1/chat/completions",
        {
            "model": provider.get("model", ""),
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        },
    )

    if result.get("ok"):
        try:
            choice = result["data"]["choices"][0]["message"]
            content = choice.get("content", "")
            # DeepSeek reasoning models may return content in reasoning_content
            if not content:
                content = choice.get("reasoning_content", "")
            if content:
                step3.status = "done"
                usage = result["data"].get("usage", {})
                tokens = usage.get("total_tokens", 0)
                step3.detail = f"模型: {provider.get('model', '')} · {tokens} tokens"
                step3.ended_at = time.perf_counter()
                return content, [s.to_dict() for s in steps]
        except (KeyError, IndexError, TypeError):
            logger.warning("LLM 响应结构异常")

    step3.status = "error"
    step3.detail = "AI 响应解析失败"
    step3.ended_at = time.perf_counter()
    return "抱歉，我暂时无法回答这个问题。", [s.to_dict() for s in steps]


def _generate_pm_response(
    repository: ProjectStateRepository,
    broadcast_queue: deque,
    product_manager: ProductManager | None = None,
    config_manager: Any = None,
    project_dir: Path | None = None,
) -> tuple[ChatMessage | None, list[dict]]:
    """调用 ProductManager agent 生成 PM 回复（含意图识别 + 动作执行）。

    返回: (PM 消息, 执行步骤列表)
    """
    from core.pm_actions import ActionResult, classify_intent, execute_action

    snapshot = repository.load_snapshot()
    chat_history = snapshot.chat_history
    user_message = chat_history[-1].content if chat_history else ""
    steps: list[dict] = []

    # Use provided project_dir, fallback to product_manager's dir
    active_dir = project_dir or (product_manager.project_dir if product_manager else None)

    if product_manager is None or not user_message:
        logger.warning("ProductManager 未配置或无消息，使用 fallback 回复")
        pm_content = "PM 暂未就绪，请重试。"
        pm_action = ""
    else:
        # 步骤 1：意图识别（关键词规则匹配）
        intent = classify_intent(
            user_message, active_dir, product_manager._initialized
        )
        action_name = intent.get("action", "chat")
        params = intent.get("params", {})

        # 步骤 2：路由到执行器
        if action_name == "chat":
            # 普通对话 → 意图识别 + 调工具 + LLM 总结
            pm_content, steps = _llm_chat_response(
                user_message, chat_history, config_manager, active_dir, repository,
            )
            pm_action = ""
        else:
            # 动作命令 → 直接执行
            result = execute_action(action_name, params, active_dir)
            pm_content = result.reply
            pm_action = action_name

    pm_msg = ChatMessage(
        id=f"pm_{_now_iso()}",
        role="pm",
        content=pm_content,
        action_triggered=pm_action,
    )

    # 持久化到 Repository
    repository.add_chat_message(pm_msg)

    # 广播给 WebSocket 客户端（包含步骤）
    event = repository.append_event(
        type="pm_response",
        pm_response={
            "id": pm_msg.id,
            "content": pm_content,
            "timestamp": pm_msg.timestamp,
            "action_triggered": pm_action,
            "steps": steps,
        },
    )
    _emit_to_ws(broadcast_queue, event)

    return pm_msg, steps
