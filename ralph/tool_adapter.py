"""ToolAdapter — 多编程工具抽象接口 + 能力匹配 + 生命周期管理。"""

from __future__ import annotations

import asyncio
import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ==================== Data Models ====================


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


# ==================== Abstract Adapter ====================


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

    def health_check(self) -> dict:
        """健康检查。默认只检查是否可用，子类可增强。"""
        available = self.is_available()
        return {"tool_id": self.tool_id, "available": available, "healthy": available}

    def version(self) -> str:
        return ""


# ==================== Concrete Adapters ====================


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


# ==================== YAML Config ====================


class ToolchainConfigLoader:
    """管理 .ralph/config/toolchain.yaml 配置。"""

    DEFAULT_CONFIG: dict[str, Any] = {
        "enabled_tools": ["claude_code"],
        "priority": ["claude_code"],
        "fallback_strategy": "manual",
        "tools": {},
    }

    def __init__(self, ralph_dir: Path):
        self._path = ralph_dir / "config" / "toolchain.json"

    def load(self) -> dict:
        if not self._path.is_file():
            return dict(self.DEFAULT_CONFIG)
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return dict(self.DEFAULT_CONFIG)

    def save(self, config: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    def get_enabled(self) -> list[str]:
        return self.load().get("enabled_tools", ["claude_code"])

    def get_priority(self) -> list[str]:
        return self.load().get("priority", [])

    def get_fallback(self) -> str:
        return self.load().get("fallback_strategy", "manual")


# ==================== Registry with Lifecycle ====================


class ToolAdapterRegistry:
    """工具适配器注册表，带能力匹配和生命周期管理。"""

    def __init__(self, ralph_dir: Path | None = None):
        self._adapters: dict[str, ToolAdapter] = {}
        self._priority: list[str] = []
        self._health_history: dict[str, list[dict]] = {}
        self._config = ToolchainConfigLoader(ralph_dir) if ralph_dir else None

    # --- Registration ---

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters[adapter.tool_id] = adapter
        if adapter.tool_id not in self._priority:
            self._priority.append(adapter.tool_id)

    def unregister(self, tool_id: str) -> bool:
        if tool_id not in self._adapters:
            return False
        del self._adapters[tool_id]
        self._priority = [t for t in self._priority if t != tool_id]
        self._health_history.pop(tool_id, None)
        return True

    def get(self, tool_id: str) -> ToolAdapter | None:
        return self._adapters.get(tool_id)

    def list_registered(self) -> list[str]:
        return list(self._priority)

    def list_available(self) -> list[str]:
        return [
            tid for tid in self._priority
            if self._adapters.get(tid) and self._adapters[tid].is_available()
        ]

    # --- Capability Matching ---

    def match(self, *, streaming: bool = False, mcp: bool = False,
              min_context: int = 0) -> list[str]:
        """按能力需求匹配工具，返回按优先级排序的匹配列表。"""
        scored: list[tuple[int, str]] = []
        priority_order = {
            t: i for i, t in enumerate(self._priority)
        }

        for tid in self._priority:
            adapter = self._adapters.get(tid)
            if not adapter or not adapter.is_available():
                continue
            cap = adapter.capabilities
            score = 0
            if streaming and cap.streaming:
                score += 1
            if mcp and cap.mcp_support:
                score += 1
            if min_context and cap.max_context_tokens >= min_context:
                score += 1

            if (streaming and not cap.streaming) or (mcp and not cap.mcp_support):
                continue  # 不满足必需能力

            # 用优先级做二次排序
            pri = priority_order.get(tid, 999)
            scored.append((score, pri, tid))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [s[2] for s in scored]

    def get_primary(self, *, streaming: bool = False, mcp: bool = False,
                    min_context: int = 0) -> ToolAdapter | None:
        """获取匹配能力的最佳工具。"""
        matched = self.match(streaming=streaming, mcp=mcp, min_context=min_context)
        if not matched:
            return None
        return self._adapters.get(matched[0])

    # --- Lifecycle ---

    def health_check_all(self) -> list[dict]:
        """对所有已注册适配器执行健康检查。"""
        results = []
        for tid in self._priority:
            adapter = self._adapters.get(tid)
            if not adapter:
                continue
            check = adapter.health_check()
            check["checked_at"] = _now_iso()
            self._health_history.setdefault(tid, []).append(check)
            # 只保留最近 10 条
            if len(self._health_history[tid]) > 10:
                self._health_history[tid] = self._health_history[tid][-10:]
            results.append(check)
        return results

    def get_healthy(self) -> list[str]:
        """返回当前健康适配器列表（最近一次检查通过）。"""
        healthy = []
        for tid in self._priority:
            history = self._health_history.get(tid, [])
            if history and history[-1].get("healthy"):
                healthy.append(tid)
        return healthy

    def downgrade(self, failed_tool_id: str) -> ToolAdapter | None:
        """当主工具失败时，自动切换到一个健康且能力相近的工具。"""
        primary = self.get_primary()
        if not primary or primary.tool_id != failed_tool_id:
            return None

        # 从注册表中移除"当前失败"的优先级
        remaining = [t for t in self._priority if t != failed_tool_id]
        for tid in remaining:
            adapter = self._adapters.get(tid)
            if adapter and adapter.is_available():
                return adapter
        return None

    # --- Config Persistence ---

    def load_from_config(self, config_loader: ToolchainConfigLoader) -> None:
        """从配置加载启用的适配器。"""
        config = config_loader.load()
        enabled = config.get("enabled_tools", [])
        # 只保留配置中的工具，按优先级排序
        priority = config.get("priority", [])
        ordered = priority + [t for t in enabled if t not in priority]
        self._priority = [t for t in ordered if t in self._adapters]
