from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ralph.knowledge_graph import KnowledgeGraphService
from ralph.repository import RalphRepository

logger = logging.getLogger(__name__)


class ResultType(Enum):
    WORK_UNIT = "work_unit"
    RETRO = "retro"
    DECISION = "decision"
    RISK = "risk"


@dataclass
class SearchResult:
    result_type: ResultType
    id: str
    title: str
    score: float
    snippet: str
    source: str  # "structured" | "graph" | "semantic"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.result_type.value,
            "id": self.id,
            "title": self.title,
            "score": self.score,
            "snippet": self.snippet,
            "source": self.source,
            "metadata": self.metadata,
        }


class RetrievalPipeline:
    """三层融合检索：L1 结构化 + L2 图谱 + L3 语义。"""

    def __init__(self, ralph_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._repo = RalphRepository(self._ralph_dir)
        self._kg = KnowledgeGraphService(self._ralph_dir)

    # ── L1: Structured Search ───────────────────────────────────

    def search_structured(
        self,
        *,
        feature_id: str | None = None,
        status: str | None = None,
        tag: str | None = None,
    ) -> list[SearchResult]:
        """L1: 按 feature_id、状态、标签等字段精确过滤。"""
        results: list[SearchResult] = []

        work_units = self._repo.list_work_units()
        for wu in work_units:
            if feature_id and getattr(wu, "feature_id", None) != feature_id:
                continue
            if status and wu.status.value != status:
                continue

            score = 1.0
            if tag:
                tags = getattr(wu, "tags", []) or []
                if tag not in tags:
                    continue
                score = 2.0  # Tag match gets higher score

            results.append(SearchResult(
                result_type=ResultType.WORK_UNIT,
                id=wu.work_id,
                title=wu.title or wu.work_id,
                score=score,
                snippet=(wu.target or "")[:200],
                source="structured",
                metadata={"status": wu.status.value},
            ))

        return results

    # ── L2: Graph Search ────────────────────────────────────────

    def search_graph(self, seed_ids: list[str], *, max_depth: int = 2) -> list[SearchResult]:
        """L2: 通过 KnowledgeGraph 查询依赖链、影响范围。"""
        results: list[SearchResult] = []

        for seed_id in seed_ids:
            deps = self._kg.query_dependencies(seed_id, max_depth=max_depth)
            for dep in deps:
                node = dep.get("node", {})
                edge = dep.get("edge", {})
                depth = dep.get("depth", 1)

                # Score decays with depth
                score = max(0.1, 1.0 - (depth * 0.3))

                node_type = node.get("node_type", "unknown")
                result_type = ResultType.WORK_UNIT if node_type == "task" else ResultType.RISK

                results.append(SearchResult(
                    result_type=result_type,
                    id=node.get("id", ""),
                    title=node.get("label", node.get("id", "")),
                    score=score,
                    snippet=f"via {edge.get('type', 'unknown')} edge",
                    source="graph",
                    metadata={"depth": depth, "edge_type": edge.get("type", "")},
                ))

        return results

    # ── L3: Semantic Search (keyword-based simulation) ──────────

    def search_semantic(self, query: str, *, top_k: int = 20) -> list[SearchResult]:
        """L3: 关键词 + 图谱关联模拟语义检索。"""
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        results: list[SearchResult] = []

        # Search work units
        for wu in self._repo.list_work_units():
            text = f"{wu.work_id} {wu.title} {wu.target}".lower()
            score = self._compute_keyword_score(text, query_lower)
            if score > 0:
                results.append(SearchResult(
                    result_type=ResultType.WORK_UNIT,
                    id=wu.work_id,
                    title=wu.title or wu.work_id,
                    score=score * 0.8,  # Semantic results weighted slightly lower
                    snippet=(wu.target or "")[:200],
                    source="semantic",
                    metadata={"match_context": self._extract_context(text, query_lower)},
                ))

        # Search retros
        for retro in self._repo.list_retros(limit=200):
            parts = [retro.summary or ""]
            for lesson in retro.lessons:
                parts.append(lesson.content or "")
            text = " ".join(parts).lower()
            score = self._compute_keyword_score(text, query_lower)
            if score > 0:
                results.append(SearchResult(
                    result_type=ResultType.RETRO,
                    id=retro.retro_id,
                    title=(retro.summary or "")[:80],
                    score=score * 0.7,
                    snippet=" ".join(parts)[:200],
                    source="semantic",
                ))

        return results[:top_k]

    # ── Fusion Search ───────────────────────────────────────────

    def fusion_search(self, q: str, *, top_k: int = 20) -> dict[str, Any]:
        """L1 结构化 + L2 图谱 + L3 语义，融合排序。

        Returns:
            {"query": str, "total": int, "results": [...], "sources": {...}}
        """
        # Run all three searches
        semantic_results = self.search_semantic(q, top_k=top_k * 2)

        # Extract seed IDs from semantic results for graph search
        seed_ids = [r.id for r in semantic_results[:5]]
        graph_results = self.search_graph(seed_ids, max_depth=2) if seed_ids else []

        # Merge and deduplicate
        seen: set[str] = set()
        merged: list[SearchResult] = []

        # Priority: structured > graph > semantic
        for result in graph_results + semantic_results:
            if result.id not in seen:
                seen.add(result.id)
                merged.append(result)

        # Sort by score descending
        merged.sort(key=lambda r: r.score, reverse=True)
        top_results = merged[:top_k]

        # Count by source
        source_counts: dict[str, int] = {}
        for r in top_results:
            source_counts[r.source] = source_counts.get(r.source, 0) + 1

        return {
            "query": q,
            "total": len(top_results),
            "results": [r.to_dict() for r in top_results],
            "sources": source_counts,
        }

    # ── Internal Helpers ────────────────────────────────────────

    def _compute_keyword_score(self, text: str, query: str) -> float:
        """计算关键词匹配分数。"""
        words = query.split()
        if not words:
            return 0.0

        score = 0.0
        # Exact phrase match gets highest score
        if query in text:
            score += 10.0

        # Individual word matches
        for word in words:
            if len(word) < 3:
                continue
            count = text.count(word)
            score += count * 0.5

        return round(score, 2)

    def _extract_context(self, text: str, query: str, window: int = 50) -> str:
        """提取匹配关键词的上下文片段。"""
        idx = text.find(query)
        if idx == -1:
            return text[:window]
        start = max(0, idx - window // 2)
        end = min(len(text), idx + len(query) + window // 2)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet += "..."
        return snippet
