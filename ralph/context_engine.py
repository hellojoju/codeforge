from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository


class ContextEngine:
    def __init__(self, project_dir: Path | str):
        self._project_dir = Path(project_dir)
        self._ralph_dir = self._project_dir / ".ralph"
        self._repo = RalphRepository(self._ralph_dir)

    def build_pm_context(
        self,
        *,
        mode: str,
        active_work_units: list[dict[str, Any]],
        pending_decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "mode": mode,
            "project_dir": str(self._project_dir),
            "active_work_units": active_work_units,
            "pending_decisions": pending_decisions or [],
            "state_snapshot": self._repo.snapshot(),
        }

    def build_incremental(
        self,
        *,
        work_id: str,
        checkpoint: int | None = None,
        current_error: str = "",
        next_goal: str = "",
    ) -> dict[str, Any]:
        checkpoint_dir = self._ralph_dir / "checkpoints"
        matched = sorted(checkpoint_dir.glob(f"{work_id}.turn-*.json")) if checkpoint_dir.is_dir() else []
        checkpoint_file = None
        if checkpoint is not None:
            p = checkpoint_dir / f"{work_id}.turn-{checkpoint}.json"
            if p.is_file():
                checkpoint_file = p
        elif matched:
            checkpoint_file = matched[-1]

        checkpoint_data = None
        if checkpoint_file and checkpoint_file.is_file():
            try:
                checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                checkpoint_data = None

        return {
            "work_id": work_id,
            "checkpoint": checkpoint_data,
            "current_error": current_error,
            "next_goal": next_goal,
            "project_dir": str(self._project_dir),
        }
