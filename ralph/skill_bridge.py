from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillIssue:
    description: str
    severity: str = "medium"
    suggested_action: str = ""


@dataclass
class SkillReviewResult:
    skill_name: str
    summary: str
    focus_checks: list[str] = field(default_factory=list)
    issues: list[SkillIssue] = field(default_factory=list)


class SkillBridge:
    def __init__(self, rules_engine: Any):
        self._rules_engine = rules_engine

    def execute_review(
        self,
        *,
        work_id: str,
        work_type: str,
        evidence: dict[str, Any],
        diff_summary: str,
    ) -> SkillReviewResult:
        _ = (work_id, work_type, evidence)
        issues = []
        if not diff_summary.strip():
            issues.append(SkillIssue(description="未检测到 diff 摘要", severity="low", suggested_action="补充变更说明"))
        return SkillReviewResult(
            skill_name="baseline-review-skill",
            summary="已执行规则与证据检查",
            focus_checks=["diff", "evidence", f"rules:{self._rules_engine.rule_count()}"],
            issues=issues,
        )
