"""ToolAdapter 单元测试。"""

from pathlib import Path
import pytest
from ralph.tool_adapter import (
    ClaudeCodeAdapter, ToolAdapterRegistry, ToolchainConfigLoader,
    ToolCapability,
)


@pytest.mark.asyncio
async def test_claude_not_available_gracefully():
    adapter = ClaudeCodeAdapter(claude_bin="nonexistent-claude-bin-xyz")
    result = await adapter.execute("hello")
    assert not result.success
    assert "not found" in result.error


def test_registry_register_and_get():
    registry = ToolAdapterRegistry()
    adapter = ClaudeCodeAdapter()
    registry.register(adapter)
    assert registry.get("claude_code") is not None


def test_registry_unregister():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter())
    assert registry.unregister("claude_code") is True
    assert registry.get("claude_code") is None


def test_registry_list_available_excludes_unavailable():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    assert registry.list_available() == []


def test_capabilities():
    adapter = ClaudeCodeAdapter()
    assert adapter.capabilities.streaming is True
    assert adapter.capabilities.mcp_support is True


def test_get_primary_returns_none_when_none_available():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    assert registry.get_primary() is None


def test_match_by_capability():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter())
    matched = registry.match(streaming=True, mcp=True)
    assert "claude_code" in matched


def test_match_skipped_when_not_available():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    matched = registry.match(streaming=True)
    assert len(matched) == 0


def test_health_check_all():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    results = registry.health_check_all()
    assert len(results) == 1
    assert "checked_at" in results[0]


def test_downgrade_returns_none_when_no_alternative():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    fallback = registry.downgrade("claude_code")
    assert fallback is None


def test_config_loader_defaults(tmp_path: Path):
    loader = ToolchainConfigLoader(tmp_path / ".ralph")
    config = loader.load()
    assert "claude_code" in config["enabled_tools"]


def test_config_loader_save_and_load(tmp_path: Path):
    loader = ToolchainConfigLoader(tmp_path / ".ralph")
    config = {"enabled_tools": ["claude_code", "codex"], "priority": ["codex"], "fallback_strategy": "auto_switch", "tools": {}}
    loader.save(config)
    loaded = loader.load()
    assert loaded["enabled_tools"] == ["claude_code", "codex"]
    assert loaded["fallback_strategy"] == "auto_switch"


def test_config_loader_getters(tmp_path: Path):
    loader = ToolchainConfigLoader(tmp_path / ".ralph")
    assert loader.get_enabled() == ["claude_code"]
    assert loader.get_fallback() == "manual"


def test_load_from_config(tmp_path: Path):
    registry = ToolAdapterRegistry(tmp_path / ".ralph")
    registry.register(ClaudeCodeAdapter())
    loader = ToolchainConfigLoader(tmp_path / ".ralph")
    loader.save({"enabled_tools": ["claude_code"], "priority": [], "fallback_strategy": "auto_switch", "tools": {}})
    registry.load_from_config(loader)
    assert "claude_code" in registry.list_registered()


def test_health_check_history():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    registry.health_check_all()
    registry.health_check_all()
    history = registry._health_history.get("claude_code", [])
    assert len(history) == 2
