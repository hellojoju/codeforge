from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository

logger = logging.getLogger(__name__)


# ── Node Types ──────────────────────────────────────────────────

@dataclass(frozen=True)
class TaskNode:
    id: str
    label: str
    status: str
    feature_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "status": self.status, "feature_id": self.feature_id}


@dataclass(frozen=True)
class FileNode:
    id: str
    label: str
    module: str
    risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "module": self.module, "risk_score": self.risk_score}


@dataclass(frozen=True)
class InterfaceNode:
    id: str
    label: str
    module: str
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "module": self.module, "signature": self.signature}


@dataclass(frozen=True)
class DecisionNode:
    id: str
    label: str
    decision: str
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "decision": self.decision, "rationale": self.rationale}


@dataclass(frozen=True)
class RiskNode:
    id: str
    label: str
    severity: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "severity": self.severity, "description": self.description}


@dataclass(frozen=True)
class BlockerNode:
    id: str
    label: str
    blocker_type: str
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "blocker_type": self.blocker_type, "resolved": self.resolved}


@dataclass(frozen=True)
class MilestoneNode:
    id: str
    label: str
    target_date: str = ""
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "target_date": self.target_date, "completed": self.completed}


# ── Edge Types ──────────────────────────────────────────────────

@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str  # depends_on, modifies, implements, requires, introduced_by, blocks, supersedes, part_of
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "type": self.edge_type, "metadata": self.metadata}


NODE_TYPE_MAP: dict[str, type] = {
    "task": TaskNode,
    "file": FileNode,
    "interface": InterfaceNode,
    "decision": DecisionNode,
    "risk": RiskNode,
    "blocker": BlockerNode,
    "milestone": MilestoneNode,
}

VALID_EDGE_TYPES = {"depends_on", "modifies", "implements", "requires", "introduced_by", "blocks", "supersedes", "part_of"}


class KnowledgeGraphService:
    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._state_dir = self._ralph_dir / "state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._state_dir / "knowledge_graph.json"
        self._repo = RalphRepository(self._ralph_dir)
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._load()

    # ── Node Operations ─────────────────────────────────────────

    def add_node(self, node_id: str, *, label: str = "", node_type: str = "task", **kwargs: Any) -> None:
        """添加节点。如果已存在则更新。"""
        self._nodes[node_id] = {
            "id": node_id,
            "label": label or node_id,
            "node_type": node_type,
            **kwargs,
        }

    def remove_node(self, node_id: str) -> bool:
        """移除节点及其关联边。"""
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._edges = [e for e in self._edges if e["source"] != node_id and e["target"] != node_id]
        return True

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    # ── Edge Operations ─────────────────────────────────────────

    def add_edge(self, source: str, target: str, *, edge_type: str = "depends_on", **metadata: Any) -> None:
        """添加边。"""
        if edge_type not in VALID_EDGE_TYPES:
            logger.warning("Unknown edge type: %s, using depends_on", edge_type)
            edge_type = "depends_on"

        # Avoid duplicates
        for e in self._edges:
            if e["source"] == source and e["target"] == target and e["type"] == edge_type:
                return

        self._edges.append({
            "source": source,
            "target": target,
            "type": edge_type,
            "metadata": metadata,
        })

    def remove_edge(self, source: str, target: str, edge_type: str = "depends_on") -> bool:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e["source"] == source and e["target"] == target and e["type"] == edge_type)
        ]
        return len(self._edges) < before

    # ── Query Operations ────────────────────────────────────────

    def query_dependencies(self, node_id: str, *, max_depth: int = 3) -> list[dict[str, Any]]:
        """查询依赖链（BFS）。"""
        visited: set[str] = {node_id}
        queue: list[tuple[str, int]] = [(node_id, 0)]
        results: list[dict[str, Any]] = []

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for edge in self._edges:
                if edge["source"] == current:
                    target = edge["target"]
                    if target not in visited:
                        visited.add(target)
                        node_data = self._nodes.get(target, {"id": target})
                        results.append({
                            "node": node_data,
                            "edge": edge,
                            "depth": depth + 1,
                        })
                        queue.append((target, depth + 1))

        return results

    def query_risk_paths(self) -> list[dict[str, Any]]:
        """查询高风险路径：风险分数 > 0.7 的节点及其依赖链。"""
        risky_nodes = [
            nid for nid, n in self._nodes.items()
            if n.get("risk_score", 0) > 0.7
        ]
        paths = []
        for nid in risky_nodes:
            deps = self.query_dependencies(nid, max_depth=2)
            paths.append({
                "risky_node": self._nodes[nid],
                "dependency_chain": deps,
                "chain_length": len(deps),
            })
        return sorted(paths, key=lambda p: p["chain_length"], reverse=True)

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

    # ── WorkUnit Indexing ───────────────────────────────────────

    def index_work_unit(self, work_unit: Any, files: list[str]) -> None:
        """WorkUnit 完成时自动录入图谱。

        Args:
            work_unit: WorkUnit 实例
            files: 涉及的文件列表
        """
        work_id = work_unit.work_id if hasattr(work_unit, "work_id") else str(work_unit)
        title = work_unit.title if hasattr(work_unit, "title") else work_id
        status = work_unit.status.value if hasattr(work_unit, "status") else "unknown"

        # Add task node
        self.add_node(work_id, label=title, node_type="task", status=status)

        # Add file nodes and edges
        for file_path in files:
            self.add_node(file_path, label=file_path.split("/")[-1], node_type="file", module=file_path)
            self.add_edge(work_id, file_path, edge_type="modifies")

        # Add dependency edges between files
        for i, f1 in enumerate(files):
            for f2 in files[i + 1:]:
                self.add_edge(f1, f2, edge_type="part_of", metadata={"work_id": work_id})

    # ── Graphify Sync ───────────────────────────────────────────

    def sync_with_graphify(self, graphify_result: dict) -> int:
        """与 graphify_service 双向同步。

        Args:
            graphify_result: graphify 提取的依赖图 {"nodes": [...], "edges": [...]}

        Returns:
            同步的边数
        """
        count = 0

        for node in graphify_result.get("nodes", []):
            node_id = node.get("id", "")
            if not node_id:
                continue
            self.add_node(
                node_id,
                label=node.get("label", node_id),
                node_type=node.get("type", "file"),
                risk_score=node.get("risk_score", 0.0),
                module=node.get("module", ""),
            )
            count += 1

        for edge in graphify_result.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")
            edge_type = edge.get("type", "depends_on")
            if source and target:
                self.add_edge(source, target, edge_type=edge_type)
                count += 1

        self.save()
        return count

    # ── Persistence ─────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            nodes_list = data.get("nodes", [])
            for n in nodes_list:
                nid = n.get("id", "")
                if nid:
                    self._nodes[nid] = n
            self._edges = data.get("edges", [])
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load knowledge graph, starting fresh")

    def save(self) -> None:
        """保存图谱到磁盘（原子写入）。"""
        import tempfile
        import os

        data = {"nodes": list(self._nodes.values()), "edges": self._edges}
        fd, tmp_path = tempfile.mkstemp(dir=str(self._path.parent), prefix=".tmp_kg_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self._path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def get_status(self) -> dict[str, Any]:
        return {"nodes": len(self._nodes), "edges": len(self._edges), "available": True}

    def get_graph_data(self) -> dict[str, Any]:
        return {"nodes": list(self._nodes.values()), "edges": list(self._edges)}
