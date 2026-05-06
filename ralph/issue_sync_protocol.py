from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.issue_source_adapter import issues_to_work_units

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class IssueSyncProtocol:
    """双向同步协议：Ralph 状态 ↔ 外部 Issue Tracker。"""

    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._state_path = self._ralph_dir / "state" / "issue-sync.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.is_file():
            return {"last_sync_at": None, "last_source": "", "synced_issues": 0, "generated_requests": 0}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def sync_from_tracker(self, source: Any, policy: dict[str, Any]) -> list[dict[str, Any]]:
        issues = source.fetch()
        requests = issues_to_work_units(issues, policy)
        self._save_state(
            {
                "last_sync_at": _now_iso(),
                "last_source": source.source_type() if hasattr(source, "source_type") else "unknown",
                "synced_issues": len(issues),
                "generated_requests": len(requests),
            }
        )
        return requests

    def get_sync_state(self) -> dict[str, Any]:
        state = self._load_state()
        state.setdefault("last_sync_at", None)
        state.setdefault("last_source", "")
        state.setdefault("synced_issues", 0)
        state.setdefault("generated_requests", 0)
        return state

    # ── Reverse Sync: Ralph → External Tracker ──────────────────

    def on_ralph_status_change(
        self,
        work_id: str,
        new_status: str,
        adapter: Any,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ralph 状态变更时反向同步到外部 tracker。

        Args:
            work_id: 工作单元 ID
            new_status: 新状态
            adapter: IssueSourceAdapter 实例
            metadata: 额外元数据

        Returns:
            {"synced": bool, "external_id": str, "status": str}
        """
        try:
            result = adapter.sync_status(
                work_id=work_id,
                status=new_status,
                metadata=metadata or {},
            )
            logger.info("Synced status for %s → %s (external: %s)", work_id, new_status, result)
            return {"synced": True, "external_id": str(result), "status": new_status}
        except Exception as e:
            logger.error("Failed to sync status for %s: %s", work_id, e)
            return {"synced": False, "error": str(e), "status": new_status}

    # ── Comment Command Parsing ─────────────────────────────────

    def parse_comment_command(self, comment_body: str) -> dict[str, Any] | None:
        """从 GitHub Issue 评论中解析 /ralph 指令。

        支持的指令格式：
        - /ralph approve [reason]
        - /ralph reject [reason]
        - /ralph retry [work_id]
        - /ralph status [work_id]
        - /ralph pause
        - /ralph resume

        Args:
            comment_body: 评论正文

        Returns:
            {"command": str, "args": dict} 或 None
        """
        if not comment_body:
            return None

        # Match /ralph command pattern
        pattern = r"/ralph\s+(\w+)(.*)$"
        match = re.search(pattern, comment_body, re.MULTILINE | re.IGNORECASE)
        if not match:
            return None

        command = match.group(1).lower()
        rest = match.group(2).strip()

        commands = {
            "approve": self._parse_approve,
            "reject": self._parse_reject,
            "retry": self._parse_retry,
            "status": self._parse_status,
            "pause": lambda _: {"action": "pause"},
            "resume": lambda _: {"action": "resume"},
        }

        parser = commands.get(command)
        if parser is None:
            return {"command": command, "args": {"raw": rest}, "valid": False}

        try:
            args = parser(rest)
            return {"command": command, "args": args, "valid": True}
        except ValueError as e:
            return {"command": command, "args": {}, "valid": False, "error": str(e)}

    def _parse_approve(self, rest: str) -> dict[str, Any]:
        reason = rest.strip() or "approved via comment"
        return {"action": "approve", "reason": reason}

    def _parse_reject(self, rest: str) -> dict[str, Any]:
        reason = rest.strip() or "rejected via comment"
        return {"action": "reject", "reason": reason}

    def _parse_retry(self, rest: str) -> dict[str, Any]:
        if not rest:
            raise ValueError("retry requires work_id: /ralph retry <work_id>")
        return {"action": "retry", "work_id": rest.split()[0]}

    def _parse_status(self, rest: str) -> dict[str, Any]:
        work_id = rest.split()[0] if rest else ""
        return {"action": "status", "work_id": work_id}

    # ── Webhook Payload Processing ──────────────────────────────

    def process_webhook_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """处理外部 tracker 的 webhook 推送。

        从 payload 中提取可识别的事件并转换为 Ralph 内部事件。

        Args:
            payload: webhook 原始数据

        Returns:
            解析出的事件列表
        """
        events: list[dict[str, Any]] = []

        event_type = payload.get("action", "")
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})

        # Check for command in comment
        if comment and comment.get("body"):
            cmd = self.parse_comment_command(comment["body"])
            if cmd:
                events.append({
                    "type": "comment_command",
                    "command": cmd.get("command"),
                    "args": cmd.get("args", {}),
                    "issue_id": issue.get("id"),
                    "author": comment.get("user", {}).get("login", ""),
                })

        # Track issue state changes
        if event_type in ("opened", "closed", "reopened", "labeled"):
            events.append({
                "type": "issue_state_change",
                "action": event_type,
                "issue_id": issue.get("id"),
                "title": issue.get("title", ""),
                "labels": [lbl.get("name", "") for lbl in issue.get("labels", [])],
            })

        return events

    def get_sync_state(self) -> dict[str, Any]:
        state = self._load_state()
        state.setdefault("last_sync_at", None)
        state.setdefault("last_source", "")
        state.setdefault("synced_issues", 0)
        state.setdefault("generated_requests", 0)
        return state
