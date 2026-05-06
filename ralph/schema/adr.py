"""Architecture Decision Record — 架构决策记录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

ADR_STATUSES = ("proposed", "accepted", "superseded", "deprecated")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Alternative:
    """被考虑的替代方案及其被拒绝原因。"""

    name: str
    description: str = ""
    rejected_reason: str = ""


@dataclass
class ADR:
    """架构决策记录，持久化到 .ralph/decisions/。"""

    adr_id: str
    title: str
    context: str = ""
    decision: str = ""
    alternatives: list[Alternative] = field(default_factory=list)
    consequences: str = ""
    status: str = "proposed"  # proposed | accepted | superseded | deprecated
    superseded_by: str = ""
    created_at: str = field(default_factory=_now_iso)
    decided_at: str = ""

    def __post_init__(self) -> None:
        if self.status not in ADR_STATUSES:
            raise ValueError(f"Invalid ADR status: {self.status}")
