"""图查询引擎 — BFS/DFS 遍历、节点查询、最短路径。"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class GraphQueryEngine:
    """代码知识图谱查询引擎，支持 6 个查询工具。"""

    def __init__(self, graph: dict[str, Any]) -> None:
        self._nodes: dict[str, dict] = {
            n["id"]: n for n in graph.get("nodes", [])
        }
        self._edges: list[dict] = graph.get("edges", [])
        self._adjacency: dict[str, list[tuple[str, str]]] = self._build_adjacency()

    def _build_adjacency(self) -> dict[str, list[tuple[str, str]]]:
        adj: dict[str, list[tuple[str, str]]] = {nid: [] for nid in self._nodes}
        for edge in self._edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            etype = edge.get("type", "depends_on")
            if src in adj:
                adj[src].append((tgt, etype))
            if tgt in adj:
                adj[tgt].append((src, f"rev_{etype}"))
        return adj

    # ── Tool: query_graph ──────────────────────────────────────

    def query_graph(self, question: str, mode: str = "bfs", budget: int = 1500) -> dict:
        """BFS/DFS 图遍历查询。"""
        # Extract node name hints from question
        matched_node = self._find_best_match(question)
        if not matched_node:
            return {"found": False, "hint": "no matching node found", "results": []}

        if mode == "bfs":
            results = self._bfs_traverse(matched_node, max_nodes=budget // 100)
        elif mode == "dfs":
            results = self._dfs_traverse(matched_node, max_nodes=budget // 100)
        else:
            results = []

        return {
            "found": True,
            "start_node": matched_node,
            "mode": mode,
            "results": results,
            "total_relations": len(results),
        }

    def _find_best_match(self, query: str) -> str | None:
        query_lower = query.lower()
        best_node = None
        best_score = 0

        for nid, node in self._nodes.items():
            label = (node.get("label", "") or "").lower()
            score = 0
            # Exact match
            if label and label in query_lower:
                score = 100
            # Partial keyword match
            elif any(part in query_lower for part in label.split("_") if len(part) > 2):
                score = 50
            # Path contains query keyword
            elif any(part in nid.lower() for part in query_lower.split() if len(part) > 2):
                score = 30

            if score > best_score:
                best_score = score
                best_node = nid

        return best_node

    def _bfs_traverse(self, start: str, max_nodes: int = 15) -> list[dict]:
        visited: set[str] = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        results: list[dict] = []

        while queue and len(visited) <= max_nodes:
            current, depth = queue.popleft()
            node = self._nodes.get(current, {})
            results.append({
                "node": current,
                "label": node.get("label", current),
                "depth": depth,
                "type": node.get("type", "unknown"),
                "neighbor_count": len(self._adjacency.get(current, [])),
            })
            for neighbor, etype in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return results

    def _dfs_traverse(self, start: str, max_nodes: int = 15) -> list[dict]:
        visited: set[str] = {start}
        stack: list[tuple[str, int, list[str]]] = [(start, 0, [])]
        results: list[dict] = []

        while stack and len(visited) <= max_nodes:
            current, depth, path = stack.pop()
            node = self._nodes.get(current, {})
            results.append({
                "node": current,
                "label": node.get("label", current),
                "depth": depth,
                "type": node.get("type", "unknown"),
                "path": path + [current],
            })
            for neighbor, etype in reversed(self._adjacency.get(current, [])):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append((neighbor, depth + 1, path + [current]))

        return results

    # ── Tool: get_node ─────────────────────────────────────────

    def get_node(self, node_id: str) -> dict:
        node = self._nodes.get(node_id)
        if node is None:
            return {"found": False, "node_id": node_id}
        return {"found": True, "node": node}

    # ── Tool: get_neighbors ────────────────────────────────────

    def get_neighbors(self, node_id: str, max_depth: int = 1) -> dict:
        if node_id not in self._nodes:
            return {"found": False, "node_id": node_id}

        visited: set[str] = {node_id}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        neighbors: list[dict] = []

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor, etype in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    nnode = self._nodes.get(neighbor, {})
                    neighbors.append({
                        "node": neighbor,
                        "label": nnode.get("label", neighbor),
                        "relation": etype,
                        "depth": depth + 1,
                    })
                    queue.append((neighbor, depth + 1))

        return {"found": True, "node_id": node_id, "neighbors": neighbors}

    # ── Tool: get_community ────────────────────────────────────

    def get_community(self, node_id: str) -> dict:
        """获取节点所属社区的全部成员。"""
        if node_id not in self._nodes:
            return {"found": False, "node_id": node_id}

        # Run community detection locally
        from ralph.graphify_core.community import detect_communities

        communities = detect_communities({
            "nodes": list(self._nodes.values()),
            "edges": self._edges,
        })

        for comm in communities:
            if node_id in comm.get("members", []):
                return {"found": True, "node_id": node_id, "community": comm}

        return {"found": True, "node_id": node_id, "community": None,
                "hint": "node not in any detected community"}

    # ── Tool: shortest_path ────────────────────────────────────

    def shortest_path(self, source: str, target: str) -> dict:
        if source not in self._nodes:
            return {"found": False, "error": f"source '{source}' not in graph"}
        if target not in self._nodes:
            return {"found": False, "error": f"target '{target}' not in graph"}

        # BFS
        queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
        visited: set[str] = {source}

        while queue:
            current, path = queue.popleft()
            if current == target:
                return {"found": True, "source": source, "target": target,
                        "path": path, "length": len(path) - 1}

            for neighbor, _etype in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return {"found": False, "source": source, "target": target,
                "error": "no path exists between nodes"}

    # ── Tool: god_nodes ────────────────────────────────────────

    def god_nodes(self, min_degree: int = 5) -> dict:
        """返回高连接度枢纽节点。"""
        degrees = [(nid, len(neighbors)) for nid, neighbors in self._adjacency.items()]
        degrees.sort(key=lambda x: -x[1])

        hubs = [
            {
                "node": nid,
                "label": self._nodes.get(nid, {}).get("label", nid),
                "degree": deg,
                "type": self._nodes.get(nid, {}).get("type", "unknown"),
            }
            for nid, deg in degrees
            if deg >= min_degree
        ]

        return {"found": len(hubs) > 0, "god_nodes": hubs, "total_nodes": len(self._nodes)}
