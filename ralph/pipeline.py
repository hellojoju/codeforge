from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ralph.knowledge_graph import KnowledgeGraphService
from ralph.repository import RalphRepository
from ralph.retrieval_pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    think_result: dict[str, Any]
    plan_result: dict[str, Any]
    retrieval_context: dict[str, Any]
    modules: list[dict[str, Any]]
    high_risk_modules: list[dict[str, Any]]
    suggested_contracts: list[dict[str, Any]]
    created_work_units: list[str] = field(default_factory=list)
    frozen_contracts: list[dict[str, Any]] = field(default_factory=dict)


class AnalysisPipeline:
    """真正串联分析器：recon → coupling → contract → task_decompose。"""

    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._repo: RalphRepository | None = None

    def with_repository(self, repo: RalphRepository) -> "AnalysisPipeline":
        self._repo = repo
        return self

    def run(
        self,
        *,
        project_path: Path,
        project_analysis: dict[str, Any],
        recon_analyzer: Any,
        coupling_analyzer: Any,
        contract_manager: Any,
        task_decomposer: Any,
        prd_text: str,
        knowledge_graph: Any,
        graphify_service: Any,
        work_unit_engine: Any | None = None,
    ) -> PipelineContext:
        # Step 1: recon_analyzer 扫描项目结构
        logger.info("Step 1: Running recon analysis on %s", project_path)
        try:
            recon_result = recon_analyzer.analyze(project_path)
        except Exception as e:
            logger.warning("Recon analyzer failed: %s", e)
            recon_result = {"error": str(e), "findings": []}

        # Step 2: coupling_analyzer 分析耦合
        logger.info("Step 2: Running coupling analysis")
        modules: list[dict[str, Any]] = []
        try:
            raw_modules = coupling_analyzer.analyze(project_path)
            for m in raw_modules:
                modules.append(
                    {
                        "name": getattr(m, "name", ""),
                        "file_count": getattr(m, "file_count", 0),
                        "import_degree": getattr(m, "import_degree", 0),
                        "dependents": getattr(m, "dependents", []),
                        "risk_score": getattr(m, "risk_score", 0),
                    }
                )
        except Exception as e:
            logger.warning("Coupling analyzer failed: %s", e)
            modules = []

        # Identify high-risk modules
        high_risk = sorted(modules, key=lambda x: x.get("risk_score", 0), reverse=True)[:5]

        # Step 3: contract_manager 为高风险模块生成/验证契约
        logger.info("Step 3: Generating contracts for %d high-risk modules", len(high_risk))
        suggested_contracts: list[dict[str, Any]] = []
        for m in high_risk:
            try:
                contract = contract_manager.generate_from_coupling(
                    module=m,
                    project_path=project_path,
                    risk_score=m.get("risk_score", 0),
                )
                suggested_contracts.append({
                    "module": m.get("name", ""),
                    "reason": "high_risk",
                    "priority": "high",
                    "contract": contract,
                })
            except Exception as e:
                logger.warning("Failed to generate contract for %s: %s", m.get("name", ""), e)
                suggested_contracts.append({
                    "module": m.get("name", ""),
                    "reason": "high_risk",
                    "priority": "high",
                    "error": str(e),
                })

        # Step 4: task_decomposer 拆分 WorkUnit
        logger.info("Step 4: Decomposing tasks for high-risk modules")
        created_work_units: list[str] = []
        for m in high_risk:
            try:
                decomposed = task_decomposer.decompose(
                    module=m,
                    project_path=project_path,
                    max_units=5,
                )
                for unit in decomposed:
                    work_id = getattr(unit, "work_id", str(unit))
                    created_work_units.append(work_id)
                    if work_unit_engine:
                        work_unit_engine.register(unit)
            except Exception as e:
                logger.warning("Failed to decompose %s: %s", m.get("name", ""), e)

        # Step 5: graphify + knowledge graph sync
        logger.info("Step 5: Syncing with graphify and knowledge graph")
        try:
            ast_graph = graphify_service.build_graph(modules)
            if hasattr(knowledge_graph, "sync_with_graphify"):
                knowledge_graph.sync_with_graphify(ast_graph)
        except Exception as e:
            logger.warning("Graphify/KG sync failed: %s", e)

        # Step 6: Retrieval for context
        retrieval = RetrievalPipeline(self._ralph_dir).fusion_search(prd_text[:120], top_k=20)

        # Build result
        think_result = {
            "project": project_analysis.get("project_name", project_path.name),
            "summary": f"识别到 {len(modules)} 个模块，{len(high_risk)} 个高风险模块",
            "recon": recon_result,
        }
        plan_result = {
            "steps": [
                "完成高风险模块契约收口",
                "补齐关键路径验证",
                "按风险优先级拆分 WorkUnit",
            ],
            "created_work_units": created_work_units,
        }

        ctx = PipelineContext(
            think_result=think_result,
            plan_result=plan_result,
            retrieval_context=retrieval,
            modules=modules,
            high_risk_modules=high_risk,
            suggested_contracts=suggested_contracts,
            created_work_units=created_work_units,
        )

        if self._repo is not None:
            ctx_id = f"pipeline-{uuid.uuid4().hex[:8]}"
            self._repo.save_pipeline_context(ctx_id, asdict(ctx))

        return ctx
