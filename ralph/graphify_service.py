from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ralph.graphify_core.extractor import extract_ast_graph
from ralph.graphify_core.query import GraphQueryEngine

logger = logging.getLogger(__name__)


class GraphifyService:
    """graphify MCP 集成服务：提取 AST 级依赖图、社区检测、增量更新。"""

    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._graph_cache = self._ralph_dir / "graph_cache"
        self._graph_cache.mkdir(parents=True, exist_ok=True)

    async def extract_ast_graph(
        self,
        project_path: Path | str,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """调用 graphify 提取代码级依赖图。

        如果 graphify MCP skill 不可用，回退到基于文件扫描的简单依赖提取。
        """
        project_path = Path(project_path)

        # Try graphify MCP first
        mcp_result = await self._try_graphify_mcp(project_path, changed_files)
        if mcp_result:
            return mcp_result

        # Fallback: simple file-scan based dependency extraction
        return self._extract_fallback(project_path, changed_files)

    def detect_communities(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        """社区检测：基于连通度和聚类识别高内聚模块群。

        使用简单的标签传播算法，不依赖 networkx。
        """
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        edges = graph.get("edges", [])

        # Build adjacency
        adjacency: dict[str, set[str]] = {nid: set() for nid in nodes}
        for edge in edges:
            src, tgt = edge.get("source", ""), edge.get("target", "")
            if src in adjacency and tgt in adjacency:
                adjacency[src].add(tgt)
                adjacency[tgt].add(src)

        if not nodes:
            return []

        # Label propagation (simple)
        labels: dict[str, str] = {nid: nid for nid in nodes}
        node_list = list(nodes.keys())

        for _iteration in range(20):
            changed = False
            for nid in node_list:
                neighbors = adjacency[nid]
                if not neighbors:
                    continue
                # Count neighbor labels
                label_counts: dict[str, int] = {}
                for nb in neighbors:
                    lbl = labels[nb]
                    label_counts[lbl] = label_counts.get(lbl, 0) + 1
                # Pick most common label
                best_label = max(label_counts, key=label_counts.get)
                if labels[nid] != best_label:
                    labels[nid] = best_label
                    changed = True
            if not changed:
                break

        # Group by community
        communities: dict[str, list[str]] = {}
        for nid, label in labels.items():
            communities.setdefault(label, []).append(nid)

        return [
            {
                "community_id": cid,
                "members": members,
                "size": len(members),
                "internal_edges": sum(
                    1 for e in edges
                    if e.get("source") in set(members) and e.get("target") in set(members)
                ),
            }
            for cid, members in sorted(communities.items(), key=lambda x: -len(x[1]))
        ]

    def backfill_to_knowledge_graph(
        self,
        kg: Any,  # KnowledgeGraphService instance
        graph: dict[str, Any],
    ) -> int:
        """将 graphify 结果回填到 KnowledgeGraph。"""
        count = 0
        for node in graph.get("nodes", []):
            node_id = node.get("id", "")
            if not node_id:
                continue
            # Avoid duplicate keys: extract known keys, pass rest as metadata
            node_kwargs = {
                k: v for k, v in node.items()
                if k not in ("id", "label", "type")
            }
            kg.add_node(node_id, label=node.get("label", node_id), node_type="file", **node_kwargs)
            count += 1

        for edge in graph.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")
            edge_type = edge.get("type", "depends_on")
            if source and target:
                kg.add_edge(source, target, edge_type=edge_type)
                count += 1

        # Save to disk
        kg.save()
        return count

    # ── Internal Methods ────────────────────────────────────────

    async def _try_graphify_mcp(
        self,
        project_path: Path,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """通过 graphify_core 提取依赖图（本地调用，无外部依赖）。"""
        try:
            graph = extract_ast_graph(project_path, changed_files=changed_files)
            cache_file = self._graph_cache / "ast_graph.json"
            cache_file.write_text(
                json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return graph
        except Exception as e:
            logger.debug("graphify_core extraction failed: %s", e)
        return None

    def query(self, question: str, mode: str = "bfs", budget: int = 1500) -> dict:
        """查询代码知识图谱。"""
        cache_file = self._graph_cache / "ast_graph.json"
        if cache_file.is_file():
            graph = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            return {"found": False, "error": "no cached graph, run extract first"}
        engine = GraphQueryEngine(graph)
        return engine.query_graph(question, mode=mode, budget=budget)
