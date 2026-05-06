"""MCP stdio server — 暴露 graphify 查询工具给外部 Agent。

用法:
    python3 -m ralph.graphify_core serve <graph_path.json>
    python3 -m ralph.graphify_core serve .ralph/graph_cache/ast_graph.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from ralph.graphify_core.extractor import extract_ast_graph
from ralph.graphify_core.query import GraphQueryEngine

logger = logging.getLogger(__name__)


def serve(graph_path: Path | str) -> None:
    """启动 MCP stdio server 循环。"""
    graph_path = Path(graph_path)
    engine = _load_engine(graph_path)

    logger.info("graphify_core MCP server started, %d nodes loaded", len(engine._nodes))
    sys.stderr.write(f"[graphify_core] serving {len(engine._nodes)} nodes\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _write_error(None, f"invalid JSON: {e}")
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "tools/list":
            _write_response(req_id, _list_tools())
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            _handle_tool_call(req_id, tool_name, arguments, engine, graph_path)
        elif method == "initialize":
            _write_response(req_id, {
                "protocolVersion": "0.1.0",
                "serverInfo": {"name": "graphify_core", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            })
        elif method == "notifications/initialized":
            pass  # No response needed
        else:
            _write_error(req_id, f"unknown method: {method}")


def _load_engine(graph_path: Path) -> GraphQueryEngine:
    if graph_path.is_file():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load graph from %s: %s", graph_path, e)
            graph = {"nodes": [], "edges": []}
    else:
        logger.info("Graph file not found, loading from project")
        graph = extract_ast_graph(Path.cwd())
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
    return GraphQueryEngine(graph)


def _list_tools() -> dict:
    return {
        "tools": [
            {
                "name": "query_graph",
                "description": "Query the code knowledge graph using BFS or DFS traversal.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Natural language query"},
                        "mode": {"type": "string", "enum": ["bfs", "dfs"], "default": "bfs"},
                        "budget": {"type": "integer", "default": 1500, "description": "Token budget"},
                    },
                    "required": ["question"],
                },
            },
            {
                "name": "get_node",
                "description": "Get details of a single graph node.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "Node identifier"},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "get_neighbors",
                "description": "Get neighbors of a node.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "max_depth": {"type": "integer", "default": 1},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "get_community",
                "description": "Get the community a node belongs to.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "shortest_path",
                "description": "Find the shortest path between two nodes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "required": ["source", "target"],
                },
            },
            {
                "name": "god_nodes",
                "description": "List high-connectivity hub nodes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min_degree": {"type": "integer", "default": 5},
                    },
                },
            },
        ]
    }


def _handle_tool_call(
    req_id: Any,
    name: str,
    args: dict,
    engine: GraphQueryEngine,
    graph_path: Path,
) -> None:
    try:
        if name == "query_graph":
            result = engine.query_graph(
                args.get("question", ""),
                mode=args.get("mode", "bfs"),
                budget=args.get("budget", 1500),
            )
        elif name == "get_node":
            result = engine.get_node(args["node_id"])
        elif name == "get_neighbors":
            result = engine.get_neighbors(
                args["node_id"],
                max_depth=args.get("max_depth", 1),
            )
        elif name == "get_community":
            result = engine.get_community(args["node_id"])
        elif name == "shortest_path":
            result = engine.shortest_path(
                args["source"], args["target"],
            )
        elif name == "god_nodes":
            result = engine.god_nodes(
                min_degree=args.get("min_degree", 5),
            )
        else:
            _write_error(req_id, f"unknown tool: {name}")
            return

        _write_response(req_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        })
    except Exception as e:
        _write_error(req_id, str(e))


def _write_response(req_id: Any, result: dict) -> None:
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _write_error(req_id: Any, message: str) -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -1, "message": message},
    }
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()
