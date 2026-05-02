"""TaskDecomposer — PRD → WorkUnit 拆解引擎，带颗粒度门禁。"""

from __future__ import annotations

import json
from pathlib import Path

from dataclasses import dataclass, field
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
from ralph.schema.task_harness import TaskHarness, RetryPolicy, TimeoutPolicy
from ralph.schema.prd_document import PRDDocument


@dataclass
class Story:
    """用户故事：一个垂直切片功能，拆解为多个 WorkUnit。"""
    story_id: str
    title: str
    description: str
    work_units: list[str] = field(default_factory=list)  # work_ids
    acceptance_criteria: list[str] = field(default_factory=list)
    estimated_complexity: str = "M"  # XS | S | M | L | XL
    status: str = "draft"  # draft | in_progress | done
    dependencies: list[str] = field(default_factory=list)  # story_ids


class TaskDecomposer:
    """将 PRD + 代码库分析拆解为细粒度 WorkUnit 列表。"""

    SIZE_LIMITS = {
        "XS": {"max_files": 1, "max_lines": 50},
        "S": {"max_files": 3, "max_lines": 150},
        "M": {"max_files": 5, "max_lines": 300},
    }

    ROLE_KEYWORDS = {
        "schema": "database", "model": "database", "table": "database",
        "api": "backend", "endpoint": "backend", "service": "backend",
        "frontend": "frontend", "ui": "frontend", "page": "frontend", "component": "frontend",
        "test": "qa", "doc": "docs", "deploy": "backend",
    }

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "tasks"
        self._dir.mkdir(parents=True, exist_ok=True)

    def decompose(self, prd: PRDDocument,
                  codebase_analysis: dict | None = None) -> tuple[list[Story], list[WorkUnit]]:
        """从 PRD 拆解为 Story 列表 + WorkUnit 列表。"""
        stories: list[Story] = []
        work_units: list[WorkUnit] = []

        for i, feature in enumerate(prd.core_features):
            feature_name = feature.get("name", f"feature-{i}")
            feature_desc = feature.get("description", "")
            story = Story(
                story_id=f"story-{prd.prd_id}-{i:02d}",
                title=feature_name,
                description=feature_desc,
                acceptance_criteria=feature.get("acceptance_criteria", []),
            )
            sub_tasks = self._break_down_feature(feature_name, feature_desc)
            work_ids: list[str] = []

            for j, sub in enumerate(sub_tasks):
                wu_id = f"wu-{prd.prd_id}-{i:02d}-{j:02d}"
                harness = self._create_default_harness(wu_id, sub["scope"])
                # scope_deny: 转换为 list
                raw_deny = sub.get("scope_deny", [])
                if isinstance(raw_deny, str):
                    raw_deny = [raw_deny]
                work_ids.append(wu_id)
                wu = WorkUnit(
                    work_id=wu_id,
                    work_type="development",
                    title=sub["title"],
                    target=sub["description"] or sub["title"],
                    status=WorkUnitStatus.DRAFT,
                    expected_output=sub.get("expected_output", ""),
                    acceptance_criteria=sub.get("acceptance_criteria", []),
                    scope_allow=sub["scope"],
                    scope_deny=list(raw_deny),
                    dependencies=sub.get("dependencies", []),
                    task_harness=harness,
                    producer_role=sub.get("producer_role", "backend"),
                    reviewer_role=sub.get("reviewer_role", "architect"),
                    test_command=sub.get("test_command", ""),
                    rollback_strategy=sub.get("rollback_strategy", "git checkout -- ."),
                )
                work_units.append(wu)

            story.work_units = work_ids
            stories.append(story)

        self._resolve_dependencies(work_units)
        self._save(work_units)
        return stories, work_units

    def validate_granularity(self, work_units: list[WorkUnit]) -> list[dict]:
        """颗粒度门禁检查。"""
        failures = []
        for wu in work_units:
            issues = []
            if not wu.target:
                issues.append("目标为空")
            if not wu.acceptance_criteria:
                issues.append("缺少验收标准")
            if not wu.scope_allow:
                issues.append("scope_allow 为空")
            if wu.task_harness is None:
                issues.append("缺少 task_harness")
            if len(wu.scope_allow) > self.SIZE_LIMITS["M"]["max_files"]:
                issues.append(f"scope_allow 过大 ({len(wu.scope_allow)} 文件)")
            if issues:
                failures.append({"work_id": wu.work_id, "issues": issues})
        return failures

    def build_dependency_dag(self, work_units: list[WorkUnit]) -> dict[str, list[str]]:
        """构建依赖 DAG: {work_id: [dependent_work_ids]}"""
        dag: dict[str, list[str]] = {}
        wu_map = {wu.work_id: wu for wu in work_units}

        for wu in work_units:
            dag.setdefault(wu.work_id, [])
            for dep_id in wu.dependencies:
                if dep_id in wu_map:
                    dag.setdefault(dep_id, []).append(wu.work_id)

        return dag

    def _break_down_feature(self, name: str, description: str) -> list[dict]:
        desc_lower = description.lower()
        matched_role = "backend"
        for kw, role in self.ROLE_KEYWORDS.items():
            if kw in desc_lower or kw in name.lower():
                matched_role = role
                break

        reviewer_role = "architect"
        if matched_role == "frontend":
            reviewer_role = "ui_designer"
        elif matched_role == "qa":
            reviewer_role = "backend"
        elif matched_role == "docs":
            reviewer_role = "product"

        return [{
            "title": name,
            "description": description or name,
            "scope": [name.lower().replace(" ", "_")],
            "acceptance_criteria": [f"验收: {description}"],
            "producer_role": matched_role,
            "reviewer_role": reviewer_role,
            "dependencies": [],
            "scope_deny": [".env", "credentials.*", "*.pem", "*.key"],
            "test_command": "pytest",
            "rollback_strategy": "git checkout -- .",
        }]

    def _create_default_harness(self, work_id: str, scope: list[str]) -> TaskHarness:
        return TaskHarness(
            harness_id=f"h-{work_id}",
            task_goal=f"实现 {work_id}",
            context_sources=list(scope),
            context_budget="8k tokens",
            allowed_tools=["claude_code", "git", "pytest"],
            denied_tools=["publish", "deploy"],
            scope_allow=list(scope),
            scope_deny=[".env", "credentials.*"],
            preflight_checks=["harness 校验通过", "scope 可读"],
            checkpoints=["测试通过"],
            validation_gates=["验收标准检查", "diff 审查"],
            evidence_required=["diff", "test_output"],
            retry_policy=RetryPolicy(),
            rollback_strategy="git checkout -- .",
            timeout_policy=TimeoutPolicy(),
            stop_conditions=["连续失败 3 次"],
            reviewer_role="architect",
        )

    def _resolve_dependencies(self, work_units: list[WorkUnit]) -> None:
        for wu in work_units:
            resolved = []
            for dep in wu.dependencies:
                for other in work_units:
                    if dep.lower() in other.title.lower() or dep in other.work_id:
                        resolved.append(other.work_id)
                        break
            if resolved:
                object.__setattr__(wu, "dependencies", resolved)

    def _save(self, work_units: list[WorkUnit]) -> None:
        data = []
        for wu in work_units:
            d = {k: v for k, v in wu.__dict__.items() if not k.startswith("_")}
            d["status"] = wu.status.value if hasattr(wu.status, "value") else str(wu.status)
            data.append(d)
        path = self._dir / "decomposed_tasks.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
