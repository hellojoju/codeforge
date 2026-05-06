from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ralph.retrieval_pipeline import RetrievalPipeline


@dataclass
class PipelineContext:
    think_result: dict[str, Any]
    plan_result: dict[str, Any]
    retrieval_context: dict[str, Any]
    modules: list[dict[str, Any]]
    high_risk_modules: list[dict[str, Any]]
    suggested_contracts: list[dict[str, Any]]


class AnalysisPipeline:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)

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
    ) -> PipelineContext:
        _ = (recon_analyzer, contract_manager, task_decomposer)
        retrieval = RetrievalPipeline(self._ralph_dir).search(prd_text[:120], top_k=20)

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
        except Exception:
            modules = []

        high_risk = sorted(modules, key=lambda x: x.get("risk_score", 0), reverse=True)[:5]
        suggested_contracts = [
            {"module": m.get("name", ""), "reason": "high_risk", "priority": "high"} for m in high_risk
        ]

        _ = graphify_service.build_graph(modules)
        _ = knowledge_graph.get_status()

        think_result = {
            "project": project_analysis.get("project_name", project_path.name),
            "summary": f"识别到 {len(modules)} 个模块，{len(high_risk)} 个高风险模块",
        }
        plan_result = {"steps": ["完成高风险模块契约收口", "补齐关键路径验证", "按风险优先级拆分 WorkUnit"]}

        return PipelineContext(
            think_result=think_result,
            plan_result=plan_result,
            retrieval_context=retrieval,
            modules=modules,
            high_risk_modules=high_risk,
            suggested_contracts=suggested_contracts,
        )
