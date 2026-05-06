from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ralph.schema.work_unit import WorkUnitStatus


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RecoveryReport:
    interrupted_count: int
    work_unit_ids: list[str]
    titles: list[str]
    created_at: str


class StartupRecover:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._report: RecoveryReport | None = None

    def run(self, repository) -> None:
        interrupted_ids: list[str] = []
        interrupted_titles: list[str] = []
        for unit in repository.list_work_units():
            if unit.status == WorkUnitStatus.RUNNING:
                try:
                    repository.transition(
                        unit.work_id,
                        WorkUnitStatus.INTERRUPTED,
                        actor_role="system",
                        reason="startup recovery",
                    )
                    interrupted_ids.append(unit.work_id)
                    interrupted_titles.append(unit.title)
                except Exception:
                    continue
        self._report = RecoveryReport(
            interrupted_count=len(interrupted_ids),
            work_unit_ids=interrupted_ids,
            titles=interrupted_titles,
            created_at=_now_iso(),
        )

    def get_report(self) -> RecoveryReport | None:
        return self._report
