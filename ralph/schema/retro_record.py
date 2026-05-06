"""RetroRecord — 反思回顾记录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Lesson:
    """经验教训条目。"""

    category: str = ""
    content: str = ""
    severity: str = "medium"
    action_items: list[str] = field(default_factory=list)


@dataclass
class RetroRecord:
    """反思回顾记录，持久化到 .ralph/retros/。"""

    retro_id: str = ""
    work_id: str = ""
    summary: str = ""
    lessons: list[Lesson] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
