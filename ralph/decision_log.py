"""DecisionLog — 架构决策记录管理器。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ralph.schema.adr import ADR, Alternative, _now_iso


class DecisionLog:
    """ADR CRUD 管理器，持久化到 .ralph/decisions/。"""

    def __init__(self, ralph_dir: Path) -> None:
        self._dir = ralph_dir / "decisions"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ---- CRUD ------------------------------------------------------------

    def create(self, title: str, context: str = "", decision: str = "",
               alternatives: list[dict] | None = None,
               consequences: str = "") -> ADR:
        adr_id = f"adr-{_now_iso().replace(':', '-')}"
        alts = [Alternative(**a) for a in (alternatives or [])]
        adr = ADR(
            adr_id=adr_id,
            title=title,
            context=context,
            decision=decision,
            alternatives=alts,
            consequences=consequences,
        )
        self._save(adr)
        return adr

    def get(self, adr_id: str) -> ADR | None:
        path = self._dir / f"{adr_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        alts = [Alternative(**a) for a in data.pop("alternatives", [])]
        return ADR(**data, alternatives=alts)

    def list_all(self) -> list[dict]:
        records: list[dict] = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                records.append({
                    "adr_id": data.get("adr_id", f.stem),
                    "title": data.get("title", ""),
                    "status": data.get("status", "proposed"),
                    "created_at": data.get("created_at", ""),
                    "decided_at": data.get("decided_at", ""),
                })
            except Exception:
                continue
        return records

    # ---- 状态转换 --------------------------------------------------------

    def accept(self, adr_id: str) -> ADR:
        adr = self._require(adr_id)
        if adr.status != "proposed":
            raise ValueError(f"Cannot accept ADR with status: {adr.status}")
        adr.status = "accepted"
        adr.decided_at = _now_iso()
        self._save(adr)
        return adr

    def supersede(self, adr_id: str, superseded_by: str) -> ADR:
        adr = self._require(adr_id)
        if adr.status not in ("proposed", "accepted"):
            raise ValueError(f"Cannot supersede ADR with status: {adr.status}")
        adr.status = "superseded"
        adr.superseded_by = superseded_by
        self._save(adr)
        return adr

    def deprecate(self, adr_id: str) -> ADR:
        adr = self._require(adr_id)
        adr.status = "deprecated"
        self._save(adr)
        return adr

    # ---- 内部 ------------------------------------------------------------

    def _require(self, adr_id: str) -> ADR:
        adr = self.get(adr_id)
        if adr is None:
            raise ValueError(f"ADR {adr_id} not found")
        return adr

    def _save(self, adr: ADR) -> None:
        path = self._dir / f"{adr.adr_id}.json"
        data = asdict(adr)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
