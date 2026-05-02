"""ToolAdapter — 多编程工具抽象接口 + Claude Code 适配器。"""

from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    evidence_files: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ToolCapability:
    streaming: bool = False
    session_resume: bool = False
    tool_use: bool = False
    mcp_support: bool = False
    max_context_tokens: int = 100000


class ToolAdapter(ABC):
    """编程工具抽象接口。"""

    tool_id: str = ""
    capabilities: ToolCapability = field(default_factory=ToolCapability)

    @abstractmethod
    async def execute(
        self, prompt: str, *, cwd: str = ".", timeout: int = 600,
        allowed_tools: list[str] | None = None,
    ) -> ExecutionResult: ...

    @abstractmethod
    async def execute_streaming(
        self, prompt: str, *, cwd: str = ".", timeout: int = 600,
        stream_callback=None, **kwargs,
    ) -> ExecutionResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class ClaudeCodeAdapter(ToolAdapter):
    """Claude Code CLI 适配器。"""

    tool_id = "claude_code"
    capabilities = ToolCapability(
        streaming=True, session_resume=True, tool_use=True, mcp_support=True,
    )

    def __init__(self, claude_bin: str = "claude", permission_mode: str = "acceptEdits"):
        self._bin = claude_bin
        self._permission_mode = permission_mode

    async def execute(
        self, prompt: str, *, cwd: str = ".", timeout: int = 600,
        allowed_tools: list[str] | None = None,
    ) -> ExecutionResult:
        cmd = [self._bin, "-p", prompt, "--permission-mode", self._permission_mode,
               "--output-format", "text"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            return ExecutionResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode or 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
            )
        except asyncio.TimeoutError:
            return ExecutionResult(success=False, error="Timeout")
        except FileNotFoundError:
            return ExecutionResult(success=False, error=f"{self._bin} not found")

    async def execute_streaming(
        self, prompt: str, *, cwd: str = ".", timeout: int = 600,
        stream_callback=None, **kwargs,
    ) -> ExecutionResult:
        return await self.execute(prompt, cwd=cwd, timeout=timeout)

    def is_available(self) -> bool:
        return shutil.which(self._bin) is not None


class ToolAdapterRegistry:
    """工具适配器注册表。"""

    def __init__(self):
        self._adapters: dict[str, ToolAdapter] = {}
        self._priority: list[str] = []

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters[adapter.tool_id] = adapter
        if adapter.tool_id not in self._priority:
            self._priority.append(adapter.tool_id)

    def get(self, tool_id: str) -> ToolAdapter | None:
        return self._adapters.get(tool_id)

    def list_available(self) -> list[str]:
        return [
            tid for tid in self._priority
            if self._adapters.get(tid) and self._adapters[tid].is_available()
        ]

    def get_primary(self) -> ToolAdapter | None:
        for tid in self._priority:
            adapter = self._adapters.get(tid)
            if adapter and adapter.is_available():
                return adapter
        return None
