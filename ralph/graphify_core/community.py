"""社区检测 — 标签传播算法识别高内聚模块群。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def detect_communities(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """对图节点运行标签传播算法，返回社区列表。"""
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])

    if not nodes:
        return []

    # Build adjacency
    adjacency: dict[str, set[str]] = {nid: set() for nid in nodes}
    for edge in edges:
        src, tgt = edge.get("source", ""), edge.get("target", "")
        if src in adjacency and tgt in adjacency:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)

    # Label propagation
    labels: dict[str, str] = {nid: nid for nid in nodes}
    node_list = list(nodes.keys())

    for _iteration in range(30):
        changed = False
        for nid in node_list:
            neighbors = adjacency.get(nid, set())
            if not neighbors:
                continue
            label_counts: dict[str, int] = {}
            for nb in neighbors:
                lbl = labels.get(nb, nb)
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
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

    member_set = {m for members in communities.values() for m in members}

    return [
        {
            "community_id": f"c{i}",
            "members": members,
            "size": len(members),
            "internal_edges": sum(
                1 for e in edges
                if e.get("source") in member_set and e.get("target") in member_set
            ),
        }
        for i, (_, members) in enumerate(
            sorted(communities.items(), key=lambda x: -len(x[1]))
        )
    ]
