"""OpenSpec-style 规格文档数据结构。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SpecDocument:
    spec_id: str
    capability: str         # e.g. "auth-login"
    title: str
    content: str            # markdown
    version: str = "1.0"
    status: str = "current"  # current | draft | archived
    dependencies: list[str] = field(default_factory=list)
    interfaces: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class SpecChange:
    change_id: str
    title: str
    proposal: str           # markdown - why this change
    design: str = ""        # markdown - how to implement
    tasks: list[str] = field(default_factory=list)
    spec_deltas: list[dict] = field(default_factory=list)
    status: str = "proposed"  # proposed | approved | rejected | applied
    created_at: str = field(default_factory=_now_iso)
