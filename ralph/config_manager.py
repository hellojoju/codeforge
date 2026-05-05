"""RalphConfigManager — .ralph/config/ 目录下的配置持久化管理。

管理 LLM Provider、Toolchain、Issue Policy 的 CRUD。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


from core.ralph_paths import resolve_ralph_dir


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


_ENCRYPTION_KEY: bytes | None = None


def _get_encryption_key(ralph_dir: Path) -> bytes:
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY
    key_file = ralph_dir / "config" / ".key"
    if key_file.is_file():
        _ENCRYPTION_KEY = key_file.read_bytes().strip()
    else:
        _ENCRYPTION_KEY = os.urandom(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(_ENCRYPTION_KEY)
    return _ENCRYPTION_KEY


def _encrypt_api_key(plaintext: str, ralph_dir: Path) -> str:
    """加密 API Key。"""
    import base64
    import hashlib
    key = _get_encryption_key(ralph_dir)
    key_hash = hashlib.sha256(key).digest()
    data = plaintext.encode()
    encrypted = bytes(data[i] ^ key_hash[i % len(key_hash)] for i in range(len(data)))
    return base64.b64encode(encrypted).decode()


def _decrypt_api_key(ciphertext: str, ralph_dir: Path) -> str:
    """解密 API Key。"""
    import base64
    import hashlib
    try:
        key = _get_encryption_key(ralph_dir)
        key_hash = hashlib.sha256(key).digest()
        encrypted = base64.b64decode(ciphertext)
        decrypted = bytes(encrypted[i] ^ key_hash[i % len(key_hash)] for i in range(len(encrypted)))
        return decrypted.decode()
    except Exception:
        return ""


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
        providers = self._read_json("providers.json", [])
        # 返回时不暴露 api_key
        return [{k: v for k, v in p.items() if k != "api_key"} for p in providers]

    def get_provider(self, provider_id: str) -> dict | None:
        providers = self._read_json("providers.json", [])
        for p in providers:
            if p.get("id") == provider_id:
                return {k: v for k, v in p.items() if k != "api_key"}
        return None

    def get_provider_decrypted(self, provider_id: str) -> dict | None:
        """获取 Provider 配置（含解密后的 api_key），仅内部使用。"""
        providers = self._read_json("providers.json", [])
        for p in providers:
            if p.get("id") == provider_id:
                if p.get("api_key"):
                    p = dict(p)
                    p["api_key"] = _decrypt_api_key(p["api_key"], self._dir.parent)
                return p
        return None

    def save_provider(self, provider: dict) -> dict:
        provider["updated_at"] = _now_iso()
        # 加密 API Key
        if provider.get("api_key"):
            provider["api_key"] = _encrypt_api_key(provider["api_key"], self._dir.parent)
        providers = self.list_providers()

        for i, p in enumerate(providers):
            if p.get("id") == provider.get("id"):
                providers[i] = provider
                break
        else:
            providers.append(provider)

        self._write_json("providers.json", providers)
        # 返回时不包含 api_key（安全）
        safe = dict(provider)
        safe.pop("api_key", None)
        return safe

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

        provider = self.get_provider_decrypted(provider_id)
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
            "task_assignments": {},
            "max_parallel": 3,
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

    _BUILTIN_AGENT_DEFAULTS = [
        {"role": "architect", "display_name": "系统架构师", "prompt_file": "architect.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "backend", "display_name": "后端开发工程师", "prompt_file": "backend_dev.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "frontend", "display_name": "前端开发工程师", "prompt_file": "frontend_dev.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "qa", "display_name": "QA测试工程师", "prompt_file": "qa_tester.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "product", "display_name": "产品经理", "prompt_file": "product_manager.md", "agent_class": "product_manager", "max_instances": 1, "enabled": True},
        {"role": "ui_designer", "display_name": "UI/UX设计师", "prompt_file": "ui_designer.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "database", "display_name": "数据库专家", "prompt_file": "database_expert.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "security", "display_name": "安全工程师", "prompt_file": "security_reviewer.md", "agent_class": "base", "max_instances": 1, "enabled": True},
        {"role": "docs", "display_name": "技术文档工程师", "prompt_file": "docs_writer.md", "agent_class": "base", "max_instances": 1, "enabled": True},
    ]

    def _prompts_dir(self) -> Path:
        """获取 prompts 目录路径。"""
        return Path(__file__).parent.parent / "prompts"

    def list_agent_definitions(self) -> list[dict]:
        defs = self._read_json("agent-definitions.json", [])
        if not defs:
            self._write_json("agent-definitions.json", [dict(d) for d in self._BUILTIN_AGENT_DEFAULTS])
            defs = [dict(d) for d in self._BUILTIN_AGENT_DEFAULTS]
        # 附加 prompt_content
        prompts_dir = self._prompts_dir()
        for d in defs:
            pf = d.get("prompt_file", f"{d['role']}.md")
            if not pf.endswith(".md"):
                pf += ".md"
            prompt_path = prompts_dir / pf
            if prompt_path.exists():
                d["prompt_content"] = prompt_path.read_text(encoding="utf-8")
        return defs

    def save_agent_definition(self, agent_def: dict) -> dict:
        agent_def["updated_at"] = _now_iso()
        # 同步 prompt_content 到 prompts/ 文件
        prompt_content = agent_def.pop("prompt_content", None)
        if prompt_content:
            prompts_dir = self._prompts_dir()
            pf = agent_def.get("prompt_file", f"{agent_def.get('role', 'unknown')}.md")
            if not pf.endswith(".md"):
                pf += ".md"
            prompt_path = prompts_dir / pf
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt_content, encoding="utf-8")

        defs = self.list_agent_definitions_raw()
        for i, d in enumerate(defs):
            if d.get("role") == agent_def.get("role"):
                defs[i] = agent_def
                break
        else:
            defs.append(agent_def)
        self._write_json("agent-definitions.json", defs)
        return agent_def

    def list_agent_definitions_raw(self) -> list[dict]:
        """读取原始定义，不附加 prompt_content。"""
        return self._read_json("agent-definitions.json", [])

    def delete_agent_definition(self, role: str) -> bool:
        defs = self.list_agent_definitions_raw()
        new_defs = [d for d in defs if d.get("role") != role]
        if len(new_defs) == len(defs):
            return False
        self._write_json("agent-definitions.json", new_defs)
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

    # --- Issue Tracker Config ---

    def get_issue_tracker_config(self) -> dict:
        """获取 Issue Tracker 配置。"""
        return self._read_json("issue-tracker.json", {
            "repo": "",
            "token": "",
            "label_policy": {},
            "auto_sync": False,
            "webhook_secret": "",
        })

    def save_issue_tracker_config(self, config: dict) -> dict:
        """保存 Issue Tracker 配置（屏蔽 token 回显）。"""
        stored = self._read_json("issue-tracker.json", {})
        if config.get("token"):
            stored["token"] = config["token"]
        stored["repo"] = config.get("repo", stored.get("repo", ""))
        stored["label_policy"] = config.get("label_policy", stored.get("label_policy", {}))
        stored["auto_sync"] = config.get("auto_sync", stored.get("auto_sync", False))
        stored["webhook_secret"] = config.get("webhook_secret", stored.get("webhook_secret", ""))
        self._write_json("issue-tracker.json", stored)
        safe = dict(stored)
        safe.pop("token", None)
        safe.pop("webhook_secret", None)
        return safe

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

        # 今日用量
        today = _now_iso()[:10]
        today_log = [e for e in log if e.get("timestamp", "").startswith(today)]
        today_input = sum(e.get("input_tokens", 0) for e in today_log)
        today_output = sum(e.get("output_tokens", 0) for e in today_log)
        today_total = sum(e.get("total_tokens", 0) for e in today_log)

        return {
            "total_calls": len(log),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost": round(estimated_cost, 2),
            "today": {
                "calls": len(today_log),
                "input_tokens": today_input,
                "output_tokens": today_output,
                "total_tokens": today_total,
            },
            "recent": log[-20:],
        }

    def get_budget_config(self) -> dict:
        """获取预算配置。"""
        budget = self._read_json("budget-config.json",
                                 {"daily_token_limit": 1_000_000,
                                  "daily_cost_limit": 10.0,
                                  "enabled": False})
        stats = self.get_usage_stats()
        today_tokens = stats.get("today", {}).get("total_tokens",
                        stats.get("today", {}).get("input_tokens", 0) +
                        stats.get("today", {}).get("output_tokens", 0))
        return {
            **budget,
            "today_tokens_used": today_tokens,
            "today_cost_estimated": stats.get("today", {}).get("input_tokens", 0) / 1_000_000 * 3.0
                                  + stats.get("today", {}).get("output_tokens", 0) / 1_000_000 * 15.0,
            "over_budget": (
                (budget.get("daily_token_limit", 0) and today_tokens > budget["daily_token_limit"])
            ) if budget.get("enabled") else False,
        }

    # ── Review Matrix ──────────────────────────────────────

    def get_review_matrix_config(self) -> list[dict]:
        """获取评审矩阵配置。"""
        from ralph.review_matrix import _DEFAULT_DIMENSIONS
        return [asdict(d) for d in _DEFAULT_DIMENSIONS]

    def save_review_matrix_config(self, config: list[dict]) -> list[dict]:
        """保存评审矩阵配置。"""
        path = self._ralph_dir / "config" / "review-matrix.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        return config

    def check_budget(self) -> dict:
        """检查当前 token 用量是否超限。

        Returns:
            {"allowed": True/False, "reason": "", "today_tokens": N, "daily_limit": N}
        """
        budget = self.get_budget_config()
        if not budget.get("enabled"):
            return {"allowed": True, "reason": "budget_check_disabled"}

        over = budget.get("over_budget", False)
        reason_parts = []

        daily_limit = budget.get("daily_token_limit", 0)
        today_tokens = budget.get("today_tokens_used", 0)
        if daily_limit and today_tokens >= daily_limit:
            reason_parts.append(f"每日 token 限额 {daily_limit} 已达 ({today_tokens})")

        cost_limit = budget.get("daily_cost_limit", 0)
        today_cost = budget.get("today_cost_estimated", 0)
        if cost_limit and today_cost >= cost_limit:
            reason_parts.append(f"每日费用限额 ${cost_limit} 已达 (${today_cost:.2f})")

        return {
            "allowed": not over,
            "over_budget": over,
            "reason": "; ".join(reason_parts) if reason_parts else ("超限" if over else ""),
            "today_tokens": today_tokens,
            "daily_token_limit": daily_limit,
            "today_cost": today_cost,
            "daily_cost_limit": cost_limit,
        }
        current.update(config)
        self._write_json("budget-config.json", {k: v for k, v in current.items()
                         if k in ("daily_token_limit", "daily_cost_limit", "enabled")})
        return self.get_budget_config()

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

    # ── Auto-tuning ────────────────────────────────────────

    def save_tuning(self, adjustments: dict) -> None:
        """保存自动调参建议。"""
        from datetime import UTC, datetime

        tuning_path = self._dir / "tuning.json"
        existing = {}
        if tuning_path.is_file():
            try:
                existing = json.loads(tuning_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        existing.update(adjustments)
        existing["updated_at"] = datetime.now(UTC).isoformat()
        self._write_json("tuning.json", existing)

    def load_tuning(self) -> dict:
        """加载自动调参建议。"""
        return self._read_json("tuning.json", {})
