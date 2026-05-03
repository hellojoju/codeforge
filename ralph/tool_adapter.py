"""ToolAdapter — 多编程工具抽象接口。

接口形态借鉴 multica provider abstraction:
    /auto-coding/multica/server/pkg/agent/agent.go

核心模式:
    ExecOptions 配置对象 → execute() 统一入口 → Session (messages 流 + result 最终结果)
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncIterator


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ==================== 数据模型（借鉴 multica ExecOptions / Message / Result）====================


@dataclass
class ExecOptions:
    """执行配置对象（借鉴 multica ExecOptions 结构体）。

    集中管理所有可选项，避免散落 kwargs。
    新增选项只需加字段，不需要改接口签名。
    """
    cwd: str = "."
    model: str = ""
    system_prompt: str = ""
    max_turns: int = 0
    timeout: int = 600
    resume_session_id: str = ""
    custom_args: list[str] = field(default_factory=list)
    mcp_config: dict | None = None
    allowed_tools: list[str] | None = None


@dataclass
class Message:
    """流式消息单元（借鉴 multica Message 类型区分）。

    type 取值为: text, thinking, tool-use, tool-result, status, error, log
    """
    type: str
    content: str = ""
    tool: str = ""
    call_id: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    status: str = ""
    level: str = ""


@dataclass
class TokenUsage:
    """Token 用量。"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class Result:
    """最终执行结果（借鉴 multica Result）。

    不再混用"成功标志+输出文本+错误信息"的扁平结构，
     而是按语义分离: status / output / error / usage / duration。
    """
    status: str = "completed"  # completed, failed, aborted, timeout
    output: str = ""
    error: str = ""
    duration_ms: int = 0
    session_id: str = ""
    usage: dict[str, TokenUsage] = field(default_factory=dict)


@dataclass
class ToolCapability:
    """工具能力声明。"""
    streaming: bool = False
    session_resume: bool = False
    tool_use: bool = False
    mcp_support: bool = False
    max_context_tokens: int = 100000


# ==================== Session（借鉴 multica Session 模式）====================


class Session:
    """执行会话 — messages 流 + result 最终结果（借鉴 multica Session 双通道）。

    用法:
        session = await adapter.execute(prompt, opts)
        async for msg in session.messages():
            ...   # 实时处理流式消息
        result = await session.wait_result()
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Message | None] = asyncio.Queue()
        self._result: Result | None = None
        self._done = asyncio.Event()

    async def messages(self) -> AsyncIterator[Message]:
        """异步迭代消息流，直到会话结束。"""
        while True:
            msg = await self._queue.get()
            if msg is None:
                break
            yield msg

    async def wait_result(self) -> Result:
        """等待最终结果。"""
        await self._done.wait()
        assert self._result is not None
        return self._result

    @property
    def result_sync(self) -> Result | None:
        """同步获取结果（仅用于已完成会话）。"""
        return self._result

    def emit(self, msg: Message) -> None:
        """生产者：写入一条消息。"""
        self._queue.put_nowait(msg)

    def finish(self, result: Result) -> None:
        """生产者：设置最终结果并关闭消息流。"""
        self._result = result
        self._queue.put_nowait(None)
        self._done.set()


# ==================== 抽象适配器（借鉴 multica Backend interface）====================


class ToolAdapter(ABC):
    """编程工具抽象接口（借鉴 multica Backend interface — 单方法 + 配置对象 + Session）。"""

    tool_id: str = ""
    capabilities: ToolCapability = ToolCapability()

    @abstractmethod
    async def execute(self, prompt: str, opts: ExecOptions | None = None) -> Session:
        """执行 prompt，返回流式 Session。

        调用方:
            session = await adapter.execute(prompt)
            async for msg in session.messages(): ...
            result = await session.wait_result()
        """
        ...

    @abstractmethod
    def is_available(self) -> bool: ...

    def health_check(self) -> dict:
        available = self.is_available()
        return {"tool_id": self.tool_id, "available": available, "healthy": available}

    def version(self) -> str:
        return ""


# ==================== 具体适配器 ====================


class ClaudeCodeAdapter(ToolAdapter):
    """Claude Code CLI 适配器 — 支持流式 stream-json 解析。"""

    tool_id = "claude_code"
    capabilities = ToolCapability(
        streaming=True, session_resume=True, tool_use=True, mcp_support=True,
    )

    def __init__(self, claude_bin: str = "claude", permission_mode: str = "acceptEdits"):
        self._bin = claude_bin
        self._permission_mode = permission_mode

    async def execute(self, prompt: str, opts: ExecOptions | None = None) -> Session:
        opts = opts or ExecOptions()
        session = Session()
        asyncio.ensure_future(self._run(prompt, opts, session))
        return session

    async def _run(self, prompt: str, opts: ExecOptions, session: Session) -> None:
        """后台执行任务，持续发送 Message 到 Session。"""
        start = time.monotonic()
        cmd = self._build_cmd(prompt, opts)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=opts.cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )

            stdout_parts: list[str] = []
            stderr_parts: list[str] = []

            async def _read_stdout() -> None:
                assert proc.stdout is not None
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace")
                    stdout_parts.append(line)
                    self._feed_line(line, session)

            async def _read_stderr() -> None:
                assert proc.stderr is not None
                async for raw_line in proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace")
                    stderr_parts.append(line)
                    session.emit(Message(type="log", content=line, level="error"))

            await asyncio.wait_for(
                asyncio.gather(_read_stdout(), _read_stderr()),
                timeout=opts.timeout,
            )
            return_code = await proc.wait()
            duration = int((time.monotonic() - start) * 1000)

            session.emit(Message(type="status", content="completed" if return_code == 0 else "failed"))
            session.finish(Result(
                status="completed" if return_code == 0 else "failed",
                output="".join(stdout_parts),
                error="".join(stderr_parts) if return_code != 0 else "",
                duration_ms=duration,
            ))

        except asyncio.TimeoutError:
            session.finish(Result(status="timeout", error=f"超时 ({opts.timeout}s)"))
        except FileNotFoundError:
            session.finish(Result(status="failed", error=f"{self._bin} 未找到，请先安装"))

    def _build_cmd(self, prompt: str, opts: ExecOptions) -> list[str]:
        cmd = [self._bin, "-p", prompt, "--permission-mode", self._permission_mode]
        if opts.model:
            cmd += ["--model", opts.model]
        if opts.resume_session_id:
            cmd += ["--resume", opts.resume_session_id]
        if opts.custom_args:
            cmd.extend(opts.custom_args)
        if opts.mcp_config:
            tmp = Path(tempfile.mktemp(suffix=".json"))
            tmp.write_text(json.dumps(opts.mcp_config))
            cmd += ["--mcp-config", str(tmp)]
        return cmd

    def _feed_line(self, line: str, session: Session) -> None:
        """解析一行输出，发送结构化 Message。"""
        stripped = line.strip()
        if not stripped:
            return
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
                self._emit_parsed(obj, session)
                return
            except json.JSONDecodeError:
                pass
        session.emit(Message(type="text", content=line))

    def _emit_parsed(self, obj: dict, session: Session) -> None:
        """解析 Claude stream-json 事件。"""
        event_type = obj.get("type", "")
        if event_type == "assistant":
            text = obj.get("result", "")
            if text:
                session.emit(Message(type="text", content=text))
        elif event_type == "tool_use":
            session.emit(Message(
                type="tool-use", tool=obj.get("tool_name", ""),
                call_id=obj.get("call_id", ""), input=obj.get("input", {}),
            ))
        elif event_type == "tool_result":
            session.emit(Message(
                type="tool-result", tool=obj.get("tool_name", ""),
                output=obj.get("output", ""),
            ))
        elif event_type == "error":
            session.emit(Message(type="error", content=obj.get("error", "")))

    def is_available(self) -> bool:
        return shutil.which(self._bin) is not None

    def version(self) -> str:
        try:
            result = subprocess.run(
                [self._bin, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""


# ==================== YAML 配置 ====================


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


# ==================== 注册表与生命周期 ====================


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
        scored: list[tuple[int, int, str]] = []
        priority_order = {t: i for i, t in enumerate(self._priority)}

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
                continue

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
            if len(self._health_history[tid]) > 10:
                self._health_history[tid] = self._health_history[tid][-10:]
            results.append(check)
        return results

    def get_healthy(self) -> list[str]:
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
        priority = config.get("priority", [])
        ordered = priority + [t for t in enabled if t not in priority]
        self._priority = [t for t in ordered if t in self._adapters]
