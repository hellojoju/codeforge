"""ConfigManager 单元测试。"""

from pathlib import Path
from ralph.config_manager import RalphConfigManager


def test_usage_stats_empty(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    stats = cfg.get_usage_stats()
    assert stats["total_calls"] == 0


def test_record_usage(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    cfg._record_usage("claude", {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150})
    stats = cfg.get_usage_stats()
    assert stats["total_calls"] == 1
    assert stats["total_input_tokens"] == 100


def test_record_usage_multiple(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    for _ in range(5):
        cfg._record_usage("claude", {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    stats = cfg.get_usage_stats()
    assert stats["total_calls"] == 5
    assert stats["total_input_tokens"] == 50


def test_auto_downgrade_no_enabled(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    result = cfg.auto_downgrade("nonexistent")
    assert result is None


def test_auto_downgrade_no_alternatives(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    cfg.save_provider({"id": "only-one", "name": "Only", "base_url": "", "enabled": True})
    result = cfg.auto_downgrade("only-one")
    assert result is None


def test_auto_downgrade_skips_current(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    cfg.save_provider({"id": "p1", "name": "P1", "base_url": "", "enabled": True})
    cfg.save_provider({"id": "p2", "name": "P2", "base_url": "", "enabled": True})
    # p2 没有 base_url，连通性检查返回 None
    result = cfg.auto_downgrade("p1")
    assert result is None or result["id"] == "p2"


def test_list_providers_after_save(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    cfg.save_provider({"id": "test", "name": "Test", "base_url": "https://test.com"})
    providers = cfg.list_providers()
    assert len(providers) == 1
    assert providers[0]["name"] == "Test"


def test_delete_provider(tmp_path: Path):
    cfg = RalphConfigManager(tmp_path / ".ralph")
    cfg.save_provider({"id": "del-me", "name": "Del"})
    assert cfg.delete_provider("del-me") is True
    assert cfg.delete_provider("del-me") is False
