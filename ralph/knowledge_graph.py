from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository


class KnowledgeGraphService:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._state_dir = self._ralph_dir / "state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._state_dir / "knowledge_graph.json"
        self._repo = RalphRepository(self._ralph_dir)

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"nodes": [], "edges": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("nodes", [])
                data.setdefault("edges", [])
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"nodes": [], "edges": []}

    def get_status(self) -> dict[str, Any]:
        data = self._load()
        return {"nodes": len(data.get("nodes", [])), "edges": len(data.get("edges", [])), "available": True}

    def get_graph_data(self) -> dict[str, Any]:
        return self._load()

    def query_impact(self, file_path: str, max_depth: int = 2) -> dict[str, Any]:
        tasks = []
        for wu in self._repo.list_work_units():
            scope = [str(p) for p in (wu.scope_allow or [])]
            if any(file_path in p or p in file_path for p in scope):
                tasks.append({"work_id": wu.work_id, "label": wu.title or wu.work_id, "status": wu.status.value})
        return {"found": bool(tasks), "file_path": file_path, "max_depth": max_depth, "direct_tasks": tasks}

    def query_retros_by_topic(self, topic: str) -> list[dict[str, Any]]:
        topic_lower = topic.lower()
        matches = []
        for retro in self._repo.list_retros(limit=200):
            for lesson in retro.lessons:
                if topic_lower in (lesson.content or "").lower():
                    matches.append(
                        {
                            "retro_id": retro.retro_id,
                            "feature_id": retro.feature_id,
                            "lesson": lesson.content,
                            "severity": lesson.severity,
                        }
                    )
        return matches[:50]
