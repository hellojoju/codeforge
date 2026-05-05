"""Claude Code Runner — 结构化 Claude CLI 执行器

职责：
  - 从 ContextPack + TaskHarness 构造结构化 prompt
  - 底层调用 ClaudeCodeAdapter（tool_adapter）执行
  - 执行后收集 git diff + 结构化结果（WorkUnit 级别逻辑）
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.ralph_paths import resolve_ralph_dir
from ralph.tool_adapter import ClaudeCodeAdapter, ExecOptions, Message, ToolAdapter

logger = logging.getLogger(__name__)


# ==================== 结构化执行结果（向后兼容 WorkUnitEngine）====================


@dataclass(frozen=True)
class ExecutionResult:
    """Claude Code 执行的结构化结果（对齐 AI 协议 §8.2）。"""
    work_id: str
    success: bool
    stdout: str
    stderr: str
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    scope_violations: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    evidence_files: list[str] = field(default_factory=list)
    harness_violations: list[str] = field(default_factory=list)
    risks_observed: str = ""
    error: str | None = None


# ==================== Prompt 构建 ====================


def _detect_project_structure(project_dir: Path) -> str:
    """自动探测项目目录结构，生成代码位置指引。"""
    parts = ["## 项目目录结构"]

    has_src = (project_dir / "src").is_dir()
    has_app = (project_dir / "app").is_dir()
    has_components = (project_dir / "components").is_dir()
    has_tests = (project_dir / "tests").is_dir()
    has_pyproject = (project_dir / "pyproject.toml").is_file()
    has_package = (project_dir / "package.json").is_file()

    if has_src:
        parts.append("- `src/` — 源码目录，所有业务代码请放入此处")
    elif has_app or has_components:
        parts.append("- `app/` / `components/` — Next.js 风格目录，页面和组件请放入对应目录")
    else:
        parts.append("- 请在项目根目录或合理的源码子目录下创建文件")

    if has_tests:
        parts.append("- `tests/` — 测试目录，所有测试文件放入此处")

    if has_pyproject:
        parts.append("- Python 项目（pyproject.toml）")
    if has_package:
        parts.append("- Node.js 项目（package.json）")

    parts.append("")
    parts.append("### 代码位置规则")
    parts.append("- 新模块请放入 `src/` 或对应的源码子目录，不要直接放在项目根目录")
    parts.append("- 测试文件请放入 `tests/`，与源码目录结构对应")
    parts.append("- 文档请放入 `docs/`")
    parts.append("")

    return "\n".join(parts)


def build_execution_prompt(
    work_id: str,
    context_pack_text: str,
    harness_text: str,
    scope_allow: list[str],
    scope_deny: list[str],
    acceptance_criteria: list[str],
    project_dir: Path | None = None,
) -> str:
    """从 ContextPack + TaskHarness 构造执行 prompt。

    结构：
    1. 项目目录结构 + 代码位置规则
    2. 任务目标
    3. 上下文包（最小必要信息）
    4. 任务 Harness 约束（允许/禁止的范围、工具、门禁）
    5. 验收标准
    6. 输出格式要求（结构化 JSON）
    """
    scope_allow_text = "\n".join(f"- {p}" for p in scope_allow) if scope_allow else "无限制"
    scope_deny_text = "\n".join(f"- {p}" for p in scope_deny) if scope_deny else "无限制"
    criteria_text = "\n".join(f"- {c}" for c in acceptance_criteria) if acceptance_criteria else "无"

    structure_text = ""
    if project_dir:
        structure_text = _detect_project_structure(Path(project_dir))

    return f"""# WorkUnit: {work_id}

{structure_text}
## 任务目标

{context_pack_text}

## 任务 Harness 约束

{harness_text}

## 修改范围

允许修改：
{scope_allow_text}

禁止修改：
{scope_deny_text}

## 验收标准

{criteria_text}

## 执行要求

1. 只修改允许范围内的文件
2. 不要修改禁止范围内的任何内容
3. **新代码请放入 `src/` 或对应的源码子目录，不要直接放在项目根目录**
4. 执行完成后，在修改的文件中写入一个 JSON 格式的总结，格式如下：
```json
{{
  "files_created": ["新建的文件路径"],
  "files_modified": ["修改的文件路径"],
  "files_deleted": ["删除的文件路径"],
  "scope_violations": ["如果有越界修改，列出路径"],
  "test_results": {{"test_name": "pass/fail"}},
  "risks_observed": "观察到的任何风险或注意事项"
}}
```
5. 将这个 JSON 总结写入 `.ralph/execution_results/{work_id}.json`
"""


# ==================== 安全规则提示 ====================

PERMISSION_RULES = """
## 安全规则

- 不要删除项目目录外的任何文件
- 不要修改 .env 文件或任何包含密钥的文件
- 不要执行数据库 DROP/TRUNCATE 操作
- 不要运行发布命令
- 如果需要对 5 个或更多文件执行批量删除，请停止并请求人工批准
"""


# ==================== Claude Code Runner ====================


class ClaudeCodeRunner:
    """Claude Code 结构化执行器。

    上层封装，处理 WorkUnit 级别的逻辑（prompt 构造、git diff、结果解析），
    底层使用 ClaudeCodeAdapter 执行。
    """

    def __init__(
        self,
        project_dir: Path,
        timeout: int = 600,
        claude_bin: str = "claude",
    ) -> None:
        self._project_dir = Path(project_dir)
        self._timeout = timeout
        self._adapter: ToolAdapter = ClaudeCodeAdapter(claude_bin=claude_bin)

    def execute(
        self,
        work_id: str,
        context_pack_text: str,
        harness_text: str,
        scope_allow: list[str],
        scope_deny: list[str],
        acceptance_criteria: list[str],
    ) -> ExecutionResult:
        """同步执行一个 WorkUnit（内部异步运行）。"""
        return asyncio.run(self.execute_streaming(
            work_id=work_id,
            context_pack_text=context_pack_text,
            harness_text=harness_text,
            scope_allow=scope_allow,
            scope_deny=scope_deny,
            acceptance_criteria=acceptance_criteria,
            stream_callback=None,
        ))

    async def execute_streaming(
        self,
        work_id: str,
        context_pack_text: str,
        harness_text: str,
        scope_allow: list[str],
        scope_deny: list[str],
        acceptance_criteria: list[str],
        stream_callback: Callable[[str, str], None] | None = None,
        cwd: Path | None = None,
    ) -> ExecutionResult:
        """异步执行一个 WorkUnit，支持流式输出。"""
        prompt = build_execution_prompt(
            work_id=work_id,
            context_pack_text=context_pack_text,
            harness_text=harness_text,
            scope_allow=scope_allow,
            scope_deny=scope_deny,
            acceptance_criteria=acceptance_criteria,
            project_dir=self._project_dir,
        )
        prompt += PERMISSION_RULES

        opts = ExecOptions(
            cwd=str(cwd or self._project_dir),
            timeout=self._timeout,
        )

        logger.info("Claude 流式执行: %s", work_id)

        session = await self._adapter.execute(prompt, opts)

        # 消费消息流，触发回调
        async for msg in session.messages():
            if stream_callback:
                stream_callback(msg.type, msg.content)

        result = await session.wait_result()

        if result.status != "completed":
            logger.error("Claude 执行失败: %s", result.error[:500] if result.error else "")
            return ExecutionResult(
                work_id=work_id,
                success=False,
                stdout=result.output,
                stderr=result.error or "",
                error=result.error,
            )

        logger.info("任务执行成功")

        files_created, files_modified, files_deleted = self._collect_git_diff()
        structured = self._read_structured_result(work_id)

        return ExecutionResult(
            work_id=work_id,
            success=True,
            stdout=result.output,
            stderr=result.error or "",
            files_created=files_created,
            files_modified=files_modified,
            files_deleted=files_deleted,
            test_results=structured.get("test_results", {}),
            scope_violations=structured.get("scope_violations", []),
            risks_observed=structured.get("risks_observed", ""),
        )

    def _collect_git_diff(self) -> tuple[list[str], list[str], list[str]]:
        """通过 git diff 收集文件变更。"""
        try:
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self._project_dir, capture_output=True, text=True, check=True,
            )
            files_created = [f for f in untracked.stdout.strip().split("\n") if f]

            modified_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self._project_dir, capture_output=True, text=True, check=True,
            )
            files_modified = [f for f in modified_result.stdout.strip().split("\n") if f]

            deleted_result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=D", "HEAD"],
                cwd=self._project_dir, capture_output=True, text=True, check=True,
            )
            files_deleted = [f for f in deleted_result.stdout.strip().split("\n") if f]

            return files_created, files_modified, files_deleted
        except subprocess.CalledProcessError:
            return [], [], []

    def _read_structured_result(self, work_id: str) -> dict[str, Any]:
        """读取 Claude 写入的结构化执行结果。"""
        result_path = resolve_ralph_dir(self._project_dir) / "execution_results" / f"{work_id}.json"
        if result_path.exists():
            try:
                content = result_path.read_text(encoding="utf-8")
                return json.loads(content)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("解析结构化结果失败: %s", e)
        return {}
