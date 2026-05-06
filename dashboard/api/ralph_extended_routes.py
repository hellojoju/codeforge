from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException

from core.state_models import Command as CmdModel
from dashboard.state_repository import ProjectStateRepository
from ralph.config_manager import RalphConfigManager
from ralph.repository import RalphRepository


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _require_capability(app: FastAPI, capability: str) -> None:
    info = getattr(app.state, "ralph_capabilities", {}).get(capability, {})
    if info.get("available", False):
        return
    module_name = info.get("module", capability)
    raise HTTPException(status_code=501, detail=f"Feature not implemented: missing module `{module_name}`")


def register_ralph_extended_routes(app: FastAPI) -> APIRouter:
    router = APIRouter(tags=["ralph-extended"])

    analysis_jobs: dict[str, dict[str, Any]] = {}
    analysis_lock = threading.Lock()

    def run_analysis_background(path_str: str) -> None:
        from ralph.project_analyzer import ProjectAnalyzer

        project_path = Path(path_str).resolve()
        job_key = str(project_path)
        progress: dict[str, Any] = {
            "status": "running",
            "progress": 0,
            "phase": "初始化",
            "message": "准备开始分析...",
            "current_file": None,
            "report": None,
            "error": None,
        }
        with analysis_lock:
            analysis_jobs[job_key] = progress
        try:
            analyzer = ProjectAnalyzer(project_path, progress=progress)
            result = analyzer.analyze()
            report_text = result["report"] if isinstance(result, dict) else result
            with analysis_lock:
                analysis_jobs[job_key].update(
                    {
                        "status": "complete",
                        "progress": 100,
                        "phase": "分析完成",
                        "message": "项目分析已完成",
                        "report": report_text,
                    }
                )
        except Exception as e:
            with analysis_lock:
                analysis_jobs[job_key].update(
                    {
                        "status": "error",
                        "progress": 0,
                        "phase": "分析失败",
                        "message": f"分析失败: {e}",
                        "error": str(e),
                    }
                )

    @router.get("/api/ralph/memory/search")
    async def ralph_memory_search(q: str = "", top_k: int = 10) -> list[dict]:
        if not q:
            return []
        _require_capability(app, "memory_manager")
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.memory_manager import MemoryManager

        return MemoryManager(cfg._dir.parent).search(q, top_k)

    @router.get("/api/ralph/memory/config")
    async def ralph_memory_get_config() -> dict:
        _require_capability(app, "memory_manager")
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.memory_manager import MemoryManager

        return MemoryManager(cfg._dir.parent).thresholds

    @router.get("/api/ralph/memory/l1-snapshot")
    async def ralph_memory_l1_snapshot() -> dict:
        _require_capability(app, "memory_manager")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from dataclasses import asdict

        from ralph.memory_manager import MemoryManager
        from ralph.repository import RalphRepository

        mgr = MemoryManager(ralph_dir)
        repo = RalphRepository(ralph_dir)
        work_units = repo.list_work_units()
        active = [asdict(wu) for wu in work_units if wu.status.value not in ("draft", "ready", "accepted")]
        return mgr.get_l1_snapshot(active)

    @router.post("/api/ralph/memory/compact")
    async def ralph_memory_compact(body: dict[str, Any]) -> dict:
        _require_capability(app, "memory_manager")
        work_id = body.get("work_id", "")
        if not work_id:
            return {"success": False, "error": "缺少 work_id"}
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from dataclasses import asdict

        from ralph.memory_manager import MemoryManager
        from ralph.repository import RalphRepository

        mgr = MemoryManager(ralph_dir)
        repo = RalphRepository(ralph_dir)
        wu = repo.get_work_unit(work_id)
        if not wu:
            return {"success": False, "error": f"WorkUnit {work_id} 不存在"}
        result = mgr.on_work_unit_completed(asdict(wu))
        return {"success": True, **result}

    @router.put("/api/ralph/memory/config")
    async def ralph_memory_update_config(body: dict[str, Any]) -> dict:
        _require_capability(app, "memory_manager")
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.memory_manager import MemoryManager

        mgr = MemoryManager(cfg._dir.parent)
        mgr.update_thresholds(body)
        return {"success": True, "thresholds": mgr.thresholds}

    @router.get("/api/ralph/knowledge-graph/data")
    async def ralph_kg_data() -> dict:
        _require_capability(app, "knowledge_graph")
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.knowledge_graph import KnowledgeGraphService

        return KnowledgeGraphService(cfg._dir.parent).get_graph_data()

    @router.get("/api/ralph/knowledge-graph/impact")
    async def ralph_kg_impact(file_path: str = "") -> dict:
        _require_capability(app, "knowledge_graph")
        if not file_path:
            return {"success": False, "error": "缺少 file_path"}
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.knowledge_graph import KnowledgeGraphService

        return KnowledgeGraphService(cfg._dir.parent).query_impact(file_path)

    @router.post("/api/ralph/context/pm")
    async def ralph_context_pm(body: dict[str, Any]) -> dict:
        _require_capability(app, "context_engine")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        project_dir = ralph_dir.parent
        from dataclasses import asdict

        from ralph.context_engine import ContextEngine
        from ralph.repository import RalphRepository

        engine = ContextEngine(project_dir)
        repo = RalphRepository(ralph_dir)
        work_units = repo.list_work_units()
        active = [asdict(wu) for wu in work_units if wu.status.value not in ("draft", "ready", "accepted")]
        context = engine.build_pm_context(
            mode=body.get("mode", "schedule"),
            active_work_units=active,
            pending_decisions=body.get("pending_decisions"),
        )
        return {"success": True, "context": context}

    @router.post("/api/ralph/context/incremental")
    async def ralph_context_incremental(body: dict[str, Any]) -> dict:
        _require_capability(app, "context_engine")
        work_id = body.get("work_id", "")
        if not work_id:
            return {"success": False, "error": "缺少 work_id"}
        cfg: RalphConfigManager = app.state.config_manager
        project_dir = cfg._dir.parent.parent
        from ralph.context_engine import ContextEngine

        engine = ContextEngine(project_dir)
        context = engine.build_incremental(
            work_id=work_id,
            checkpoint=body.get("checkpoint"),
            current_error=body.get("current_error", ""),
            next_goal=body.get("next_goal", ""),
        )
        return {"success": True, "context": context, "work_id": work_id}

    @router.get("/api/ralph/pm/status")
    async def ralph_pm_status() -> dict:
        _require_capability(app, "pm_agent")
        cfg: RalphConfigManager = app.state.config_manager
        project_dir = cfg._dir.parent.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine

        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        return agent.get_status()

    @router.get("/api/ralph/pm/context")
    async def ralph_pm_context() -> dict:
        _require_capability(app, "pm_agent")
        cfg: RalphConfigManager = app.state.config_manager
        project_dir = cfg._dir.parent.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine

        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        return {"success": True, "context": agent.get_context()}

    @router.post("/api/ralph/pm/schedule")
    async def ralph_pm_schedule() -> dict:
        _require_capability(app, "pm_agent")
        cfg: RalphConfigManager = app.state.config_manager
        project_dir = cfg._dir.parent.parent
        from ralph.pm_agent import PMAgent
        from ralph.work_unit_engine import WorkUnitEngine

        engine = WorkUnitEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)
        results = await agent.schedule_once()
        return {
            "success": True,
            "actions": len(results),
            "results": [
                {"action": r.action, "work_id": r.work_id, "success": r.success, "summary": r.summary}
                for r in results
            ],
        }

    @router.get("/api/ralph/search")
    async def ralph_search(q: str = "", top_k: int = 20) -> dict:
        _require_capability(app, "retrieval_pipeline")
        if not q:
            return {"query": "", "total": 0, "combined": []}
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.retrieval_pipeline import RetrievalPipeline

        return RetrievalPipeline(cfg._dir.parent).search(q, top_k)

    @router.post("/api/ralph/projects/pipeline")
    async def ralph_run_pipeline(body: dict[str, Any] | None = None) -> dict:
        _require_capability(app, "project_analyzer")
        _require_capability(app, "pipeline")
        _require_capability(app, "knowledge_graph")
        _require_capability(app, "graphify_service")
        body = body or {}
        project_path = Path(body.get("path", os.environ.get("PROJECT_DIR", "."))).resolve()
        prd_text = body.get("prd_text", "")
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {project_path}")
        if not prd_text:
            raise HTTPException(status_code=422, detail="prd_text is required for pipeline")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent

        from ralph.contract_manager import ContractManager
        from ralph.coupling_analyzer import CouplingAnalyzer
        from ralph.graphify_service import GraphifyService
        from ralph.knowledge_graph import KnowledgeGraphService
        from ralph.pipeline import AnalysisPipeline
        from ralph.recon_analyzer import ReconAnalyzer
        from ralph.task_decomposer import TaskDecomposer

        project_analysis = {"project_name": project_path.name}
        recon = ReconAnalyzer()
        coupling = CouplingAnalyzer()
        contracts = ContractManager(ralph_dir)
        decomposer = TaskDecomposer(ralph_dir)
        kg = KnowledgeGraphService(ralph_dir)
        graphify = GraphifyService(ralph_dir)
        pipeline = AnalysisPipeline(ralph_dir)
        ctx = pipeline.run(
            project_path=project_path,
            project_analysis=project_analysis,
            recon_analyzer=recon,
            coupling_analyzer=coupling,
            contract_manager=contracts,
            task_decomposer=decomposer,
            prd_text=prd_text,
            knowledge_graph=kg,
            graphify_service=graphify,
        )
        return {
            "success": True,
            "think": ctx.think_result,
            "plan": ctx.plan_result,
            "retrieval": ctx.retrieval_context,
            "modules": ctx.modules,
            "high_risk_modules": ctx.high_risk_modules,
            "suggested_contracts": ctx.suggested_contracts,
        }

    @router.post("/api/ralph/projects/deep-analyze")
    async def ralph_deep_analyze_project(body: dict[str, Any]) -> dict:
        _require_capability(app, "project_analyzer")
        path_str = body.get("path", os.environ.get("PROJECT_DIR", "."))
        project_path = Path(path_str).resolve()
        if not project_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path_str}")
        job_key = str(project_path)
        with analysis_lock:
            existing = analysis_jobs.get(job_key)
            if existing and existing.get("status") == "running":
                return {"success": True, "job_key": job_key, "already_running": True}
            analysis_jobs[job_key] = {"status": "starting", "progress": 0, "phase": "启动中", "message": "正在启动分析..."}
        thread = threading.Thread(target=run_analysis_background, args=(path_str,), daemon=True)
        thread.start()
        return {"success": True, "job_key": job_key}

    @router.get("/api/ralph/projects/analysis-progress")
    async def ralph_analysis_progress(path: str = "") -> dict:
        if not path:
            raise HTTPException(status_code=400, detail="path 参数必填")
        project_path = Path(path).resolve()
        job_key = str(project_path)
        with analysis_lock:
            progress = analysis_jobs.get(job_key)
        if progress:
            return dict(progress)
        _require_capability(app, "project_analyzer")
        from ralph.project_analyzer import ProjectAnalyzer

        analyzer = ProjectAnalyzer(project_path)
        report = analyzer.get_saved_report()
        if report:
            return {"status": "complete", "progress": 100, "phase": "分析完成", "message": "项目分析已完成", "report": report}
        return {"status": "idle", "progress": 0, "phase": "未开始", "message": "尚未进行深度分析"}

    @router.get("/api/ralph/projects/report")
    async def ralph_get_project_report(path: str = "") -> dict:
        _require_capability(app, "project_analyzer")
        from ralph.project_analyzer import ProjectAnalyzer

        project_path = Path(path).resolve() if path else Path(os.environ.get("PROJECT_DIR", "."))
        analyzer = ProjectAnalyzer(project_path)
        report = analyzer.get_saved_report()
        if not report:
            raise HTTPException(status_code=404, detail="尚无分析报告，请先执行深度分析")
        return {"success": True, "report": report, "summary": analyzer.get_saved_report_summary(), "project_name": project_path.name}

    @router.get("/api/ralph/projects/report/structured")
    async def ralph_get_project_structured(path: str = "") -> dict:
        _require_capability(app, "project_analyzer")
        from ralph.project_analyzer import ProjectAnalyzer

        project_path = Path(path).resolve() if path else Path(os.environ.get("PROJECT_DIR", "."))
        analyzer = ProjectAnalyzer(project_path)
        structured_path = analyzer.ralph_dir / "project-structured.json"
        if not structured_path.is_file():
            raise HTTPException(status_code=404, detail="尚无结构化分析数据")
        return {"success": True, "structured": json.loads(structured_path.read_text(encoding="utf-8"))}

    @router.post("/api/ralph/issues/webhook")
    async def ralph_issues_webhook(body: dict[str, Any]) -> dict:
        _require_capability(app, "issue_command_parser")
        from ralph.issue_command_parser import comment_to_command

        action = body.get("action", "")
        issue_data = body.get("issue", {})
        comment_data = body.get("comment", {})
        issue_number = issue_data.get("number", 0)
        if action == "created" and comment_data:
            cmd = comment_to_command(comment_data, str(issue_number))
            if cmd:
                command = CmdModel(
                    command_id=f"issue_cmd_{_now_iso()}",
                    type=cmd["type"],
                    target_id=cmd.get("work_id", issue_data.get("title", "")),
                    payload=cmd,
                    issued_at=_now_iso(),
                )
                repo: ProjectStateRepository = app.state.repository
                repo.save_command(command)
                return {"webhook": "command_created", "issue": issue_number, "command": cmd["type"]}
        return {"webhook": "ignored", "action": action}

    @router.post("/api/ralph/issues/sync")
    async def ralph_issues_sync(body: dict[str, Any]) -> dict:
        _require_capability(app, "issue_sync_protocol")
        from ralph.issue_source_adapter import GitHubIssueSource, IssueClassifier, LocalFileIssueSource
        from ralph.issue_sync_protocol import IssueSyncProtocol

        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        policy = cfg.get_issue_policy()
        protocol = IssueSyncProtocol(ralph_dir)
        source_type = body.get("source", "local")
        if source_type == "github":
            tracker_cfg = cfg.get_issue_tracker_config()
            if not tracker_cfg.get("repo"):
                return {"error": "GitHub repo not configured", "synced": False}
            source = GitHubIssueSource(
                repo=tracker_cfg["repo"],
                token=tracker_cfg.get("token", ""),
                label=body.get("label", ""),
            )
        else:
            source = LocalFileIssueSource(ralph_dir / "issues")
        classifier = IssueClassifier()
        _ = [classifier.classify(i) for i in source.fetch()]
        requests = protocol.sync_from_tracker(source, policy)
        return {"synced_issues": len(requests), "commands_created": len(requests), "requests": requests}

    @router.get("/api/ralph/issues/config")
    async def ralph_issues_get_config() -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_issue_tracker_config()

    @router.put("/api/ralph/issues/config")
    async def ralph_issues_put_config(body: dict[str, Any]) -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.save_issue_tracker_config(body)

    @router.get("/api/ralph/issues/sync-status")
    async def ralph_issues_sync_status() -> dict:
        _require_capability(app, "issue_sync_protocol")
        from ralph.issue_sync_protocol import IssueSyncProtocol

        cfg: RalphConfigManager = app.state.config_manager
        protocol = IssueSyncProtocol(cfg._dir.parent)
        return protocol.get_sync_state()

    @router.get("/api/ralph/budget")
    async def ralph_get_budget() -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.get_budget_config()

    @router.put("/api/ralph/budget")
    async def ralph_update_budget(body: dict[str, Any]) -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        return cfg.update_budget_config(body)

    @router.get("/api/ralph/workspaces")
    async def ralph_list_workspaces() -> list[dict]:
        cfg: RalphConfigManager = app.state.config_manager
        from ralph.parallel_executor import WorktreeManager

        mgr = WorktreeManager(cfg._dir.parent.parent)
        trees = mgr.list_active()
        return [{"name": t.name, "path": str(t.path), "branch": t.branch, "status": t.status} for t in trees]

    @router.post("/api/ralph/ship/{work_id}")
    async def ralph_ship_work_unit(work_id: str, body: dict | None = None) -> dict:
        _require_capability(app, "ship_service")
        from ralph.ship_service import ShipService

        repo: RalphRepository = app.state.ralph_repository
        svc = ShipService(repo._ralph_dir, repo._ralph_dir.parent)
        body = body or {}
        if body.get("dry_run", False):
            blockers = svc.verify_pre_ship(work_id)
            return {"success": not blockers, "blockers": blockers}
        result = svc.ship_work_unit(work_id, strategy=body.get("strategy", "patch"))
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return {
            "success": True,
            "tag": result.tag,
            "branch": result.branch,
            "changelog_path": result.changelog_path,
            "message": result.message,
        }

    @router.get("/api/ralph/releases")
    async def ralph_list_releases() -> list[dict]:
        _require_capability(app, "ship_service")
        repo: RalphRepository = app.state.ralph_repository
        releases_dir = repo._ralph_dir / "releases"
        if not releases_dir.is_dir():
            return []
        releases = []
        for p in sorted(releases_dir.glob("*.md"), reverse=True):
            releases.append({"name": p.stem, "changelog": p.read_text(encoding="utf-8")[:500], "created_at": _now_iso()})
        return releases

    return router
