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

    # --- Recent Projects ---

    def list_recent_projects(self) -> list[dict]:
        return self._read_json("recent-projects.json", [])

    def add_recent_project(self, project_path: str, name: str = "") -> None:
        projects = self.list_recent_projects()
        # 去重 + 移到最前
        projects = [p for p in projects if p.get("path") != project_path]
        projects.insert(0, {
            "name": name or Path(project_path).name,
            "path": project_path,
            "last_opened_at": _now_iso(),
        })
        # 最多保留 20 个
        self._write_json("recent-projects.json", projects[:20])

    def remove_recent_project(self, project_path: str) -> None:
        projects = [p for p in self.list_recent_projects() if p.get("path") != project_path]
        self._write_json("recent-projects.json", projects)

    # --- Project Analysis ---

    def save_analysis(self, project_path: str, analysis: dict) -> dict:
        data = {"project_path": project_path, "analysis": analysis, "analyzed_at": _now_iso()}
        self._write_json("analysis.json", data)
        return data

    def get_analysis(self) -> dict | None:
        return self._read_json("analysis.json")

    # --- Agent Definitions ---

    def list_agent_definitions(self) -> list[dict]:
        return self._read_json("agent-definitions.json", [])

    def save_agent_definition(self, agent_def: dict) -> dict:
        agent_def["updated_at"] = _now_iso()
        defs = self.list_agent_definitions()
        for i, d in enumerate(defs):
            if d.get("role") == agent_def.get("role"):
                defs[i] = agent_def
                break
        else:
            defs.append(agent_def)
        self._write_json("agent-definitions.json", defs)
        return agent_def

    def delete_agent_definition(self, role: str) -> bool:
        defs = [d for d in self.list_agent_definitions() if d.get("role") != role]
        if len(defs) == len(self.list_agent_definitions()):
            return False
        self._write_json("agent-definitions.json", defs)
        return True

    # --- Agent-Level Provider Config ---

    def list_agent_providers(self) -> dict:
        return self._read_json("agent-providers.json", {})

    def get_agent_provider(self, agent_id: str) -> dict | None:
        providers = self.list_agent_providers()
        return providers.get(agent_id)

    def save_agent_provider(self, agent_id: str, config: dict) -> dict:
        providers = self.list_agent_providers()
        config["updated_at"] = _now_iso()
        providers[agent_id] = config
        self._write_json("agent-providers.json", providers)
        return config

    def resolve_agent_provider(self, agent_role: str, task_type: str = "") -> dict:
        """解析 agent 的 LLM provider：agent 级覆盖 > ModelAssignment > 第一个启用的 provider。"""
        # 1. Agent 级覆盖
        agent_config = self.get_agent_provider(agent_role)
        if agent_config and agent_config.get("enabled"):
            return {
                "provider_id": agent_config.get("provider_id", ""),
                "model": agent_config.get("model", ""),
                "base_url": agent_config.get("overrides", {}).get("base_url", ""),
                "source": "agent_override",
            }

        # 2. ModelAssignment
        if task_type:
            assignments = self.list_assignments()
            for a in assignments:
                if a.get("task_type") == task_type:
                    return {
                        "provider_id": a.get("provider_id", ""),
                        "model": a.get("model", ""),
                        "source": "model_assignment",
                    }

        # 3. 第一个启用的 provider
        providers = self.list_providers()
        for p in providers:
            if p.get("enabled"):
                return {
                    "provider_id": p.get("id", ""),
                    "model": p.get("default_model", ""),
                    "source": "default_provider",
                }

        return {"provider_id": "", "model": "", "source": "none"}

    # --- Scheduling Timeline ---

    def append_scheduling_event(self, event: dict) -> None:
        import json as _json
        event["timestamp"] = _now_iso()
        path = self._dir / "scheduling-timeline.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(event, ensure_ascii=False) + "\n")

    def get_scheduling_timeline(self, limit: int = 100) -> list[dict]:
        import json as _json
        path = self._dir / "scheduling-timeline.jsonl"
        if not path.is_file():
            return []
        events = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(_json.loads(line.strip()))
                except _json.JSONDecodeError:
                    continue
        return events[-limit:]

    # --- Provider Proxy & Cost Tracking ---

    def proxy_request(self, provider_id: str, endpoint: str, body: dict) -> dict:
        """通过后端代理转发请求到 LLM Provider（前端不走 Provider API）。"""
        provider = self.get_provider(provider_id)
        if not provider:
            return {"ok": False, "error": "Provider not found"}

        import urllib.request
        import json as _json

        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")
        url = f"{base_url}/{endpoint.lstrip('/')}"

        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.data = _json.dumps(body).encode()

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_data = _json.loads(resp.read().decode())
            # 记录 token 用量
            usage = response_data.get("usage", {})
            self._record_usage(provider_id, usage)
            return {"ok": True, "data": response_data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _record_usage(self, provider_id: str, usage: dict) -> None:
        """记录一次 API 调用的 token 用量。"""
        try:
            log = self._read_json("usage-log.json", [])
            log.append({
                "provider_id": provider_id,
                "timestamp": _now_iso(),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            })
            # 保留最近 10000 条
            if len(log) > 10000:
                log = log[-10000:]
            self._write_json("usage-log.json", log)
        except Exception:
            pass

    def get_usage_stats(self) -> dict:
        """获取 token 用量统计。"""
        log = self._read_json("usage-log.json", [])
        if not log:
            return {"total_calls": 0, "total_input_tokens": 0,
                    "total_output_tokens": 0, "total_cost": 0.0}

        total_input = sum(e.get("input_tokens", 0) for e in log)
        total_output = sum(e.get("output_tokens", 0) for e in log)
        # 粗略估算：输入 $3/M, 输出 $15/M (以 Claude Opus 4.5 为参考)
        estimated_cost = (total_input / 1_000_000 * 3.0) + (total_output / 1_000_000 * 15.0)

        return {
            "total_calls": len(log),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost": round(estimated_cost, 2),
            "recent": log[-20:],
        }

    def auto_downgrade(self, provider_id: str) -> dict | None:
        """当主 Provider 失败时，自动切换到下一个启用的 Provider。"""
        providers = self.list_providers()
        enabled = [p for p in providers if p.get("enabled")]

        # 找到失败 Provider 的位置
        current_idx = -1
        for i, p in enumerate(enabled):
            if p.get("id") == provider_id:
                current_idx = i
                break

        if current_idx < 0:
            return None

        # 切换到下一个
        for i in range(current_idx + 1, len(enabled)):
            candidate = enabled[i]
            # 快速连通性检查
            try:
                import urllib.request
                test_url = candidate.get("base_url", "").rstrip("/")
                if test_url:
                    urllib.request.urlopen(f"{test_url}/models", timeout=5)
                    return candidate
            except Exception:
                continue

        return None
