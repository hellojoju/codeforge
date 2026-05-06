from __future__ import annotations

from pathlib import Path
from typing import Any


class GraphifyService:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)

    def build_graph(self, modules: list[dict[str, Any]]) -> dict[str, Any]:
        nodes = []
        edges = []
        for mod in modules:
            name = mod.get("name", "")
            nodes.append({"id": name, "label": name, "risk": mod.get("risk_score", 0)})
            deps = mod.get("dependents", [])
            if isinstance(deps, list):
                for dep in deps:
                    edges.append({"source": name, "target": dep})
        return {"nodes": nodes, "edges": edges}
