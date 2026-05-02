"""RalphConfigManager — .ralph/config/ 目录下的配置持久化管理。

管理 LLM Provider、Toolchain、Issue Policy 的 CRUD。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


# ==================== Models ====================


@dataclass
class LLMProvider:
    id: str
    name: str
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    last_tested_at: str | None = None
    last_test_result: str | None = None  # "ok" | "fail" | None


@dataclass
class ModelAssignment:
    task_type: str
    provider_id: str
    model: str


@dataclass
class ToolchainConfig:
    enabled_tools: list[str] = field(default_factory=lambda: ["claude_code"])
    priority: list[str] = field(default_factory=list)
    fallback_strategy: str = "manual"  # manual | auto_switch


@dataclass
class IssuePolicy:
    issue_sources: list[str] = field(default_factory=lambda: ["local"])
    classification_rules: dict[str, str] = field(default_factory=dict)  # type -> action
    pull_interval: str = "manual"  # manual | hourly | daily


# ==================== Manager ====================


class RalphConfigManager:
    """管理 .ralph/config/ 目录下的 JSON 配置文件。"""

    def __init__(self, ralph_dir: Path | str = ".ralph"):
        self._dir = Path(ralph_dir) / "config"
        self._dir.mkdir(parents=True, exist_ok=True)

    # --- Generic JSON I/O ---

    def _read_json(self, filename: str, default: Any = None) -> Any:
        path = self._dir / filename
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def _write_json(self, filename: str, data: Any) -> Path:
        path = self._dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    # --- Providers ---

    def list_providers(self) -> list[dict]:
        return self._read_json("providers.json", [])

    def get_provider(self, provider_id: str) -> dict | None:
        providers = self.list_providers()
        for p in providers:
            if p.get("id") == provider_id:
                return p
        return None

    def save_provider(self, provider: dict) -> dict:
        provider["updated_at"] = _now_iso()
        providers = self.list_providers()

        # Upsert
        for i, p in enumerate(providers):
            if p.get("id") == provider.get("id"):
                providers[i] = provider
                break
        else:
            providers.append(provider)

        self._write_json("providers.json", providers)
        return provider

    def delete_provider(self, provider_id: str) -> bool:
        providers = self.list_providers()
        new_providers = [p for p in providers if p.get("id") != provider_id]
        if len(new_providers) == len(providers):
            return False
        self._write_json("providers.json", new_providers)
        return True

    def test_provider_connection(self, provider_id: str) -> dict:
        """测试 Provider 连通性（通过后端代理发 HTTP 请求）。"""
        import urllib.request
        import urllib.error

        provider = self.get_provider(provider_id)
        if not provider:
            return {"ok": False, "error": f"Provider {provider_id} not found"}

        base_url = provider.get("base_url", "")
        api_key = provider.get("api_key", "")

        if not base_url:
            return {"ok": False, "error": "Base URL is empty"}

        # 尝试访问模型列表端点（OpenAI-compatible API）
        test_url = f"{base_url.rstrip('/')}/models"
        req = urllib.request.Request(test_url, method="GET")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            urllib.request.urlopen(req, timeout=10)
            # 更新最后测试结果
            provider["last_tested_at"] = _now_iso()
            provider["last_test_result"] = "ok"
            self.save_provider(provider)
            return {"ok": True}
        except urllib.error.HTTPError as e:
            # 401/403 说明能连通但认证失败（也算连通）
            provider["last_tested_at"] = _now_iso()
            if e.code in (401, 403):
                provider["last_test_result"] = "ok"
                self.save_provider(provider)
                return {"ok": True, "note": f"Connected (HTTP {e.code}, auth may need checking)"}
            provider["last_test_result"] = "fail"
            self.save_provider(provider)
            return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            provider["last_tested_at"] = _now_iso()
            provider["last_test_result"] = "fail"
            self.save_provider(provider)
            return {"ok": False, "error": str(e.reason)}
        except Exception as e:
            provider["last_tested_at"] = _now_iso()
            provider["last_test_result"] = "fail"
            self.save_provider(provider)
            return {"ok": False, "error": str(e)}

    # --- Model Assignments ---

    def list_assignments(self) -> list[dict]:
        return self._read_json("model-assignments.json", [])

    def save_assignments(self, assignments: list[dict]) -> list[dict]:
        self._write_json("model-assignments.json", assignments)
        return assignments

    # --- Toolchain ---

    def get_toolchain(self) -> dict:
        return self._read_json("toolchain.json", {
            "enabled_tools": ["claude_code"],
            "priority": [],
            "fallback_strategy": "manual",
        })

    def save_toolchain(self, config: dict) -> dict:
        self._write_json("toolchain.json", config)
        return config

    # --- Issue Policy ---

    def get_issue_policy(self) -> dict:
        return self._read_json("issue-policy.json", {
            "issue_sources": ["local"],
            "classification_rules": {},
            "pull_interval": "manual",
        })

    def save_issue_policy(self, policy: dict) -> dict:
        self._write_json("issue-policy.json", policy)
        return policy
