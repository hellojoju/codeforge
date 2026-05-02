"""ToolAdapter 单元测试。"""

import pytest
from ralph.tool_adapter import ClaudeCodeAdapter, ToolAdapterRegistry


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
