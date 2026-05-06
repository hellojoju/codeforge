"""python -m ralph.graphify_core <command>

Commands:
    serve <graph_path>   Start MCP stdio server
    extract <path>       Extract AST graph and print JSON to stdout
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "serve":
        graph_path = sys.argv[2] if len(sys.argv) > 2 else ".ralph/graph_cache/ast_graph.json"
        from ralph.graphify_core.serve import serve
        serve(graph_path)
    elif command == "extract":
        import json
        from pathlib import Path
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        from ralph.graphify_core.extractor import extract_ast_graph
        graph = extract_ast_graph(Path(path))
        print(json.dumps(graph, ensure_ascii=False, indent=2))
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
