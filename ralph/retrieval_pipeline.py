from __future__ import annotations

from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository


class RetrievalPipeline:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._repo = RalphRepository(self._ralph_dir)

    def search(self, q: str, top_k: int = 20) -> dict[str, Any]:
        query = q.strip().lower()
        if not query:
            return {"query": "", "total": 0, "combined": []}

        combined: list[dict[str, Any]] = []
        for wu in self._repo.list_work_units():
            text = f"{wu.work_id} {wu.title} {wu.target}".lower()
            score = text.count(query)
            if score > 0:
                combined.append(
                    {
                        "type": "work_unit",
                        "id": wu.work_id,
                        "title": wu.title,
                        "score": score,
                        "snippet": wu.target[:200],
                    }
                )

        for retro in self._repo.list_retros(limit=200):
            text = f"{retro.summary} {' '.join(retro.improvements)}".lower()
            score = text.count(query)
            if score > 0:
                combined.append(
                    {
                        "type": "retro",
                        "id": retro.retro_id,
                        "title": retro.summary[:80],
                        "score": score,
                        "snippet": " ".join(retro.improvements)[:200],
                    }
                )

        combined.sort(key=lambda x: x["score"], reverse=True)
        combined = combined[: max(1, top_k)]
        return {"query": q, "total": len(combined), "combined": combined}
