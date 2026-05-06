from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TurnBasedExecutionEngine:
    def __init__(self, project_dir: Path | str):
        self._project_dir = Path(project_dir)
        self._checkpoints = self._project_dir / ".ralph" / "checkpoints"
        self._checkpoints.mkdir(parents=True, exist_ok=True)

    def list_executions(self) -> list[str]:
        return sorted({p.name.split(".turn-")[0] for p in self._checkpoints.glob("*.turn-*.json")})

    def get_execution_status(self, work_id: str) -> dict[str, Any] | None:
        entries = sorted(self._checkpoints.glob(f"{work_id}.turn-*.json"))
        if not entries:
            return None
        turns = []
        for p in entries:
            try:
                turns.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return {"work_id": work_id, "turns": turns, "latest_turn": turns[-1] if turns else None}

    def restore_from_checkpoint(self, work_id: str, turn: int) -> dict[str, Any]:
        p = self._checkpoints / f"{work_id}.turn-{turn}.json"
        if not p.is_file():
            return {"success": False, "error": f"checkpoint not found: {p.name}"}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"invalid checkpoint: {e}"}
        return {"success": True, "work_id": work_id, "turn": turn, "checkpoint": data}
