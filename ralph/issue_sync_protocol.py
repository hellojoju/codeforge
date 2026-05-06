from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ralph.issue_source_adapter import issues_to_work_units


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class IssueSyncProtocol:
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
