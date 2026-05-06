from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TasteMemory:
    def __init__(self, storage_dir: str | Path):
        self._dir = Path(storage_dir) / "memory"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "tastes.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_all(self) -> list[dict[str, Any]]:
        return sorted(self._load(), key=lambda x: x.get("updated_at", ""), reverse=True)

    def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        items = self._load()
        taste_id = item.get("id") or f"taste-{_now_iso().replace(':', '-').replace('.', '-')}"
        item["id"] = taste_id
        item.setdefault("created_at", _now_iso())
        item["updated_at"] = _now_iso()

        for i, old in enumerate(items):
            if old.get("id") == taste_id:
                items[i] = {**old, **item}
                self._save(items)
                return items[i]

        items.append(item)
        self._save(items)
        return item

    def delete(self, taste_id: str) -> bool:
        items = self._load()
        new_items = [x for x in items if x.get("id") != taste_id]
        if len(new_items) == len(items):
            return False
        self._save(new_items)
        return True
