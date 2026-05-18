"""ExecutablePlanGenerator — 从 BrainstormRecord 生成可执行计划。

灵感来自 Archon 的 plan.md 模板：把需求规格转成执行 Agent 能直接消费的格式，
包含任务分解、文件变更预估、验证命令、参考模式等。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.config_manager import RalphConfigManager
from ralph.schema.brainstorm_record import (
    BrainstormRecord,
    BrainstormPhase,
    ExecutablePlan,
    ExecutionTask,
    FeatureNode,
    _now_iso,
)

logger = logging.getLogger(__name__)


class ExecutablePlanGenerator:
    """基于已完成的 BrainstormRecord 生成结构化可执行计划。"""

    def __init__(self, config_manager: RalphConfigManager | None = None):
        self._config = config_manager

    def generate(self, record: BrainstormRecord) -> ExecutablePlan:
        """从 BrainstormRecord 生成 ExecutablePlan。

        流程：
        1. 从 BrainstormRecord 提取静态上下文（产品定义、功能树、技术路线、工具发现）
        2. 调用 LLM 生成任务分解和执行细节
        3. 组装为 ExecutablePlan
        """
        if record.current_phase not in (
            BrainstormPhase.EXECUTION_PLAN_READY,
            BrainstormPhase.COMPLETE,
        ):
            logger.warning(
                "ExecutablePlanGenerator: record is in phase %s, expected EXECUTION_PLAN_READY or COMPLETE",
                record.current_phase,
            )

        context = self._build_context(record)
        llm_tasks = self._generate_tasks_via_llm(record, context)
        plan = self._assemble_plan(record, context, llm_tasks)
        record.executable_plan = plan
        return plan

    # ── Public ──

    def to_markdown(self, plan: ExecutablePlan) -> str:
        """将 ExecutablePlan 渲染为 Markdown（类似 Archon plan.md 格式）。"""
        lines: list[str] = []

        lines.append(f"# Feature: {plan.project_name}")
        lines.append("")
        lines.append("## Summary")
        lines.append(plan.summary)
        lines.append("")
        lines.append("## User Story")
        lines.append(plan.user_story)
        lines.append("")
        lines.append("## Problem Statement")
        lines.append(plan.problem_statement)
        lines.append("")
        lines.append("## Solution Statement")
        lines.append(plan.solution_statement)
        lines.append("")
        lines.append("## Metadata")
        lines.append(f"- **Type:** {plan.plan_type}")
        lines.append(f"- **Complexity:** {plan.complexity}")
        lines.append(f"- **Systems Affected:** {', '.join(plan.systems_affected)}")
        lines.append("")

        if plan.architecture_summary:
            lines.append("## Architecture Summary")
            lines.append(plan.architecture_summary)
            lines.append("")

        if plan.tech_stack:
            lines.append(f"## Tech Stack: {', '.join(plan.tech_stack)}")
            lines.append("")

        if plan.mandatory_reading:
            lines.append("## Mandatory Reading")
            for f in plan.mandatory_reading:
                lines.append(f"- {f}")
            lines.append("")

        if plan.patterns_to_mirror:
            lines.append("## Patterns to Mirror")
            for p in plan.patterns_to_mirror:
                lines.append(f"- {p}")
            lines.append("")

        lines.append("## Files to Change")
        for task in plan.tasks:
            if task.target_files:
                for f in task.target_files:
                    lines.append(f"- [{task.action}] {f}")
        lines.append("")

        lines.append("## Step-by-Step Tasks")
        for i, task in enumerate(plan.tasks, 1):
            lines.append(f"### Task {i}: {task.title}")
            lines.append(f"- **ID:** {task.task_id}")
            lines.append(f"- **Action:** {task.action}")
            lines.append(f"- **Source:** Feature `{task.source_feature_id}`")
            lines.append(f"- **Complexity:** {task.estimated_complexity}")
            if task.dependencies:
                lines.append(f"- **Dependencies:** {', '.join(task.dependencies)}")
            lines.append("")
            lines.append(task.description)
            lines.append("")
            if task.target_files:
                lines.append("**Target Files:**")
                for f in task.target_files:
                    lines.append(f"- `{f}`")
                lines.append("")
            if task.acceptance_criteria:
                lines.append("**Acceptance Criteria:**")
                for c in task.acceptance_criteria:
                    lines.append(f"- [ ] {c}")
                lines.append("")
            if task.validation_commands:
                lines.append("**Validation Commands:**")
                for cmd in task.validation_commands:
                    lines.append(f"```bash\n{cmd}\n```")
                lines.append("")

        lines.append("## Testing Strategy")
        lines.append(plan.testing_strategy)
        lines.append("")

        if plan.validation_commands:
            lines.append("## Validation Commands")
            for cmd in plan.validation_commands:
                lines.append(f"```bash\n{cmd}\n```")
            lines.append("")

        lines.append("## Acceptance Criteria")
        for c in plan.acceptance_criteria:
            lines.append(f"- [ ] {c}")
        lines.append("")

        if plan.risks:
            lines.append("## Risks and Mitigations")
            for r in plan.risks:
                lines.append(f"- ⚠️ {r}")
            lines.append("")

        return "\n".join(lines)

    # ── Internal ──

    def _build_context(self, record: BrainstormRecord) -> dict[str, str]:
        """从 BrainstormRecord 提取静态上下文字段。"""
        root = record.feature_tree.get_node("fn-root")

        vision = root.vision if root else ""
        target_users = root.target_users if root else []
        mvp_scope = root.mvp_scope if root else []

        # 功能列表摘要
        feature_lines: list[str] = []
        for node in record.feature_tree.nodes.values():
            if node.node_id == "fn-root" or node.level == "product":
                continue
            indent = "  " if node.level == "sub_function" else ""
            status_tag = f"[{node.status}]"
            feature_lines.append(f"{indent}- {status_tag} {node.name}: {node.user_stories[0] if node.user_stories else 'N/A'}")

        # 技术路线
        route = record.technical_route
        tech_summary = ""
        if route:
            tech_summary = f"""
架构: {route.architecture_summary}
前端: {', '.join(route.frontend_stack)}
后端: {', '.join(route.backend_stack)}
存储: {', '.join(route.data_storage)}
集成: {', '.join(route.integrations)}
"""

        # 工具发现摘要
        tool_summary = ""
        if record.tool_discovery_results:
            tool_items: list[str] = []
            for td in record.tool_discovery_results:
                for ev in td.evaluations:
                    if ev.recommendation == "adopt":
                        tool_items.append(f"- {td.tool_need}: adopt recommended tool")
            if tool_items:
                tool_summary = "\n".join(tool_items)

        # 审查发现
        review_summary = ""
        if record.review_result and record.review_result.findings:
            review_items = []
            for f in record.review_result.findings:
                review_items.append(f"- [{f.severity}] {f.description}")
            review_summary = "\n".join(review_items)

        return {
            "vision": vision,
            "target_users": ", ".join(target_users),
            "mvp_scope": ", ".join(mvp_scope),
            "feature_tree": "\n".join(feature_lines),
            "tech_route": tech_summary,
            "tool_recommendations": tool_summary,
            "review_findings": review_summary,
        }

    def _generate_tasks_via_llm(
        self, record: BrainstormRecord, context: dict[str, str]
    ) -> list[dict]:
        """调用 LLM 生成任务分解。"""
        prompt = f"""你是资深全栈开发工程师。基于以下已完成的需求规格和技术方案，生成详细的执行任务列表。

## 项目愿景
{context['vision']}

## 目标用户
{context['target_users']}

## MVP 范围
{context['mvp_scope']}

## 功能树
{context['feature_tree']}

## 技术路线
{context['tech_route']}

## 工具推荐
{context['tool_recommendations']}

## 审查发现
{context['review_findings']}

请生成详细的执行任务，每个任务必须包含：
1. title: 任务标题（简短描述）
2. description: 任务描述（具体做什么）
3. action: CREATE | UPDATE | DELETE
4. target_files: 需要创建或修改的文件路径（用相对路径，如 "src/api/users.py"）
5. dependencies: 依赖的任务 ID 列表（如果有前置任务）
6. acceptance_criteria: 验收标准列表
7. validation_commands: 验证命令列表（如 "pytest tests/test_users.py"）
8. estimated_complexity: low | medium | high

请以 JSON 数组返回，按执行顺序排列：
[
  {{
    "title": "...",
    "description": "...",
    "action": "CREATE",
    "target_files": ["src/api/users.py"],
    "dependencies": [],
    "acceptance_criteria": ["..."],
    "validation_commands": ["pytest tests/test_users.py"],
    "estimated_complexity": "medium"
  }}
]

注意：
- 任务按依赖顺序排列，不依赖的任务在前面
- 每个任务应该是原子性的，不超过半天工作量
- target_files 尽量具体，基于项目现有的目录结构推断
"""

        content = self._call_llm("executable_plan", [{"role": "user", "content": prompt}])

        if not content:
            logger.warning("ExecutablePlanGenerator: LLM returned empty content")
            return self._fallback_tasks(record, context)

        try:
            content = content.strip()
            if "```" in content:
                # 提取代码块中的 JSON
                start = content.index("```")
                # 找到语言标记后的第一个换行
                first_newline = content.index("\n", start)
                content = content[first_newline + 1:]
                end = content.index("```")
                content = content[:end].strip()

            tasks = json.loads(content)
            if isinstance(tasks, list) and tasks:
                return tasks
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.warning("ExecutablePlanGenerator: failed to parse LLM response: %s", e)

        return self._fallback_tasks(record, context)

    def _fallback_tasks(
        self, record: BrainstormRecord, context: dict[str, str]
    ) -> list[dict]:
        """LLM 失败时的兜底任务生成。"""
        tasks: list[dict] = []
        task_counter = 0

        for node in record.feature_tree.nodes.values():
            if node.level not in ("function", "sub_function"):
                continue
            if node.status != "confirmed":
                continue

            task_counter += 1
            task_id = f"task-{task_counter:03d}"
            tasks.append({
                "title": f"实现 {node.name}",
                "description": f"根据需求规格实现功能：{node.user_stories[0] if node.user_stories else node.name}",
                "action": "CREATE",
                "target_files": [],
                "dependencies": [],
                "acceptance_criteria": list(node.acceptance_criteria),
                "validation_commands": [],
                "estimated_complexity": "medium",
            })

        return tasks

    def _assemble_plan(
        self,
        record: BrainstormRecord,
        context: dict[str, str],
        llm_tasks: list[dict],
    ) -> ExecutablePlan:
        """将 LLM 输出组装为 ExecutablePlan。"""
        root = record.feature_tree.get_node("fn-root")
        route = record.technical_route

        tasks: list[ExecutionTask] = []
        for i, t in enumerate(llm_tasks):
            task_id = t.get("task_id", f"task-{i:03d}")
            # 关联到最匹配的 FeatureNode
            source_feature_id = self._find_source_feature(record, t.get("title", ""))

            tasks.append(ExecutionTask(
                task_id=task_id,
                title=t.get("title", ""),
                description=t.get("description", ""),
                source_feature_id=source_feature_id,
                action=t.get("action", "CREATE"),
                target_files=t.get("target_files", []),
                dependencies=t.get("dependencies", []),
                acceptance_criteria=t.get("acceptance_criteria", []),
                validation_commands=t.get("validation_commands", []),
                estimated_complexity=t.get("estimated_complexity", "medium"),
            ))

        # 判断项目类型
        is_new_project = not record.feature_tree.nodes.get("fn-root", FeatureNode(node_id="", name="", level="")).children
        plan_type = "new_project" if is_new_project else "feature"

        plan = ExecutablePlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            project_name=record.project_name,
            summary=context["vision"],
            user_story=f"作为 {context['target_users']}，我需要 {context['mvp_scope']}",
            problem_statement="",
            solution_statement=context["vision"],
            plan_type=plan_type,
            complexity=self._estimate_complexity(record, tasks),
            systems_affected=self._collect_systems_affected(record),
            architecture_summary=route.architecture_summary if route else "",
            tech_stack=(route.frontend_stack + route.backend_stack + route.data_storage) if route else [],
            tool_needs=route.tool_needs if route else [],
            mandatory_reading=self._suggest_mandatory_reading(record),
            patterns_to_mirror=[],
            tasks=tasks,
            testing_strategy=self._build_testing_strategy(record),
            validation_commands=self._collect_validation_commands(tasks),
            acceptance_criteria=self._collect_acceptance_criteria(record),
            risks=route.key_risks if route else [],
            created_at=_now_iso(),
            brainstorm_record_id=record.record_id,
        )

        return plan

    def _find_source_feature(self, record: BrainstormRecord, task_title: str) -> str:
        """根据任务标题匹配最相关的 FeatureNode。"""
        best_match: str | None = None
        best_score = 0

        task_words = set(task_title.lower().split())

        for node in record.feature_tree.nodes.values():
            if node.level not in ("function", "sub_function"):
                continue
            node_words = set(node.name.lower().split())
            overlap = len(task_words & node_words)
            if overlap > best_score:
                best_score = overlap
                best_match = node.node_id

        return best_match or "fn-root"

    def _estimate_complexity(
        self, record: BrainstormRecord, tasks: list[ExecutionTask]
    ) -> str:
        task_count = len(tasks)
        if task_count <= 3:
            return "small"
        if task_count <= 10:
            return "medium"
        return "large"

    def _collect_systems_affected(self, record: BrainstormRecord) -> list[str]:
        affected: set[str] = set()
        route = record.technical_route
        if route:
            for stack in (route.frontend_stack, route.backend_stack, route.data_storage):
                affected.update(stack)
        return sorted(affected)

    def _suggest_mandatory_reading(self, record: BrainstormRecord) -> list[str]:
        """建议实现者必读的文件。"""
        # 这里给一个基础列表，后续可以根据代码库分析细化
        reading = [".ralph/specs/README.md"]
        if record.technical_route:
            reading.append(".ralph/technical_route.json")
        return reading

    def _build_testing_strategy(self, record: BrainstormRecord) -> str:
        leaf_nodes = [
            n for n in record.feature_tree.nodes.values()
            if n.level in ("function", "sub_function") and n.status == "confirmed"
        ]
        if not leaf_nodes:
            return "为每个功能模块编写单元测试和集成测试。"
        return f"为 {len(leaf_nodes)} 个已确认功能编写单元测试和集成测试，确保验收标准全部覆盖。"

    def _collect_validation_commands(self, tasks: list[ExecutionTask]) -> list[str]:
        commands: list[str] = []
        for task in tasks:
            for cmd in task.validation_commands:
                if cmd not in commands:
                    commands.append(cmd)
        return commands

    def _collect_acceptance_criteria(self, record: BrainstormRecord) -> list[str]:
        criteria: list[str] = []
        for node in record.feature_tree.nodes.values():
            if node.level in ("function", "sub_function") and node.status == "confirmed":
                criteria.extend(node.acceptance_criteria)
        return criteria

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4000,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                return None
        return None
