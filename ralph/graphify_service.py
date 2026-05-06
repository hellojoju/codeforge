from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

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
        """尝试通过 graphify MCP skill 提取依赖图。"""
        try:
            # Check if Skill tool is available via subprocess approach
            # Since we're in a library context, we use a file-based protocol
            # Write a request file and check if graphify can process it
            request_file = self._ralph_dir / "graphify_request.json"
            request_data = {
                "action": "extract",
                "project_path": str(project_path),
                "changed_files": changed_files,
            }
            request_file.write_text(json.dumps(request_data), encoding="utf-8")

            # Try importing graphify module directly if available
            spec = importlib.util.find_spec("graphify")
            if spec is not None:
                module = importlib.import_module("graphify")
                if hasattr(module, "extract"):
                    result = module.extract(str(project_path))
                    return result
        except Exception as e:
            logger.debug("graphify MCP not available, falling back: %s", e)
        return None

    def _extract_fallback(
        self,
        project_path: Path,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """回退方案：基于文件扫描的依赖图提取。"""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Determine which files to scan
        if changed_files:
            files_to_scan = [project_path / f for f in changed_files if (project_path / f).exists()]
        else:
            files_to_scan = list(project_path.rglob("*.py"))
            files_to_scan = [f for f in files_to_scan if "node_modules" not in str(f) and ".git" not in str(f)]

        for file_path in files_to_scan[:200]:  # Limit to avoid excessive processing
            rel_path = str(file_path.relative_to(project_path))
            if rel_path in seen:
                continue
            seen.add(rel_path)

            nodes.append({
                "id": rel_path,
                "label": file_path.stem,
                "type": "file",
                "module": rel_path.replace("/", ".").removesuffix(".py"),
                "risk_score": self._estimate_file_risk(file_path),
            })

            # Extract import dependencies
            try:
                content = file_path.read_text(encoding="utf-8")
                imports = self._extract_imports(content)
                for imp in imports:
                    # Map import to local file if possible
                    target_file = self._resolve_import(project_path, imp, file_path)
                    if target_file and target_file != rel_path:
                        edges.append({
                            "source": rel_path,
                            "target": target_file,
                            "type": "imports",
                        })
            except (OSError, UnicodeDecodeError):
                continue

        # Save cache
        cache_file = self._graph_cache / "ast_graph.json"
        cache_file.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2), encoding="utf-8")

        return {"nodes": nodes, "edges": edges}

    def _extract_imports(self, content: str) -> list[str]:
        """提取 Python import 语句中的模块名。"""
        imports = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("from ") and " import " in stripped:
                module = stripped.split(" ", 2)[1]
                if module.startswith("."):
                    continue  # Skip relative imports
                imports.append(module)
            elif stripped.startswith("import "):
                parts = stripped[7:].split(",")
                for part in parts:
                    module = part.strip().split(" as ")[0].strip()
                    if not module.startswith("."):
                        imports.append(module)
        return imports

    def _resolve_import(self, project_path: Path, module: str, source_file: Path) -> str | None:
        """将模块名解析为相对文件路径。"""
        # Try direct path match: module.path -> module/path.py
        candidate = project_path / module.replace(".", "/")
        if candidate.with_suffix(".py").exists():
            return str(candidate.with_suffix(".py").relative_to(project_path))
        if (candidate / "__init__.py").exists():
            return str((candidate / "__init__.py").relative_to(project_path))

        # Try from source file's directory
        source_dir = source_file.parent
        parts = module.split(".")
        candidate2 = source_dir / "/".join(parts)
        if candidate2.with_suffix(".py").exists():
            return str(candidate2.with_suffix(".py").relative_to(project_path))

        return None

    def _estimate_file_risk(self, file_path: Path) -> float:
        """估算文件风险分数（基于大小和复杂度）。"""
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.count("\n")
            # Simple risk: more lines = higher risk
            risk = min(lines / 500.0, 1.0)
            # Increase risk for files with many imports
            import_count = content.count("import ")
            risk += min(import_count / 20.0, 0.5)
            return round(min(risk, 1.0), 2)
        except (OSError, UnicodeDecodeError):
            return 0.0
