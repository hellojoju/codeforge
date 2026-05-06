from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus


@dataclass
class PMActionResult:
    action: str
    work_id: str
    success: bool
    summary: str


class PMAgent:
    def __init__(self, project_dir: Path | str, engine: Any):
        self._project_dir = Path(project_dir)
        self._engine = engine
        self._repo = RalphRepository(self._project_dir / ".ralph")

    def get_status(self) -> dict[str, Any]:
        units = self._repo.list_work_units()
        return {
            "running_count": sum(1 for u in units if u.status == WorkUnitStatus.RUNNING),
            "ready_count": sum(1 for u in units if u.status == WorkUnitStatus.READY),
            "total_count": len(units),
            "project_dir": str(self._project_dir),
        }

    def get_context(self) -> dict[str, Any]:
        return {"status": self.get_status(), "snapshot": self._repo.snapshot()}

    async def schedule_once(self) -> list[PMActionResult]:
        ready = self._repo.list_work_units(status=WorkUnitStatus.READY)
        if not ready:
            return []
        target = ready[0]
        result = await self._engine.execute(target.work_id)
        ok = bool(result.get("success")) if isinstance(result, dict) else False
        summary = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
        return [PMActionResult(action="dispatch", work_id=target.work_id, success=ok, summary=summary)]
