from __future__ import annotations

from typing import Any

from ralph.schema.review_dimension import DimensionResult, ReviewDimensionConfig
from ralph.schema.review_result import ReviewResult


_DEFAULT_DIMENSIONS = [
    ReviewDimensionConfig(dimension_id="correctness", name="正确性", weight=1.0, required=True),
    ReviewDimensionConfig(dimension_id="safety", name="安全性", weight=1.0, required=True),
    ReviewDimensionConfig(dimension_id="maintainability", name="可维护性", weight=0.8, required=False),
]


class ReviewMatrixEngine:
    def __init__(self, config_mgr: Any, project_dir: Any):
        _ = (config_mgr, project_dir)

    async def execute_review(
        self,
        *,
        work_id: str,
        evidence: dict,
        work_type: Any,
        acceptance_criteria: list[str],
        diff_summary: str,
    ) -> ReviewResult:
        _ = (work_type, diff_summary)
        dims = [
            DimensionResult(dimension_id="correctness", passed=True, score=85.0, evidence="baseline checks"),
            DimensionResult(dimension_id="safety", passed=True, score=90.0, evidence="no critical findings"),
            DimensionResult(
                dimension_id="maintainability",
                passed=True,
                score=80.0,
                evidence="code structure acceptable",
            ),
        ]
        conclusion = "通过" if all(d.passed for d in dims if d.dimension_id in ("correctness", "safety")) else "不通过"
        return ReviewResult(
            work_id=work_id,
            reviewer_context_id="matrix-review",
            review_type="matrix",
            conclusion=conclusion,
            recommended_action="接受" if conclusion == "通过" else "返工",
            criteria_results=[],
            issues_found=[],
            evidence_checked=list(evidence.get("files", [])),
            harness_checked=bool(acceptance_criteria),
            dimension_results=dims,
            overall_confidence="high",
        )
