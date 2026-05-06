"""AST-based file dependency extraction."""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# File extensions we can analyze
_SUPPORTED_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def extract_ast_graph(
    project_path: Path | str,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    """提取项目文件依赖图，返回 {nodes, edges}。"""
    project_path = Path(project_path)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()

    if changed_files:
        files_to_scan = [project_path / f for f in changed_files if (project_path / f).exists()]
    else:
        files_to_scan = _collect_source_files(project_path)

    for file_path in files_to_scan[:500]:
        rel_path = str(file_path.relative_to(project_path))
        if rel_path in seen:
            continue
        seen.add(rel_path)

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        ext = file_path.suffix.lower()
        if ext == ".py":
            parsed = _parse_python(content, file_path)
        elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            parsed = _parse_typescript(content, file_path)
        else:
            parsed = {"imports": [], "calls": [], "classes": [], "functions": []}

        nodes.append({
            "id": rel_path,
            "label": file_path.stem,
            "type": "file",
            "module": rel_path.replace("/", ".").replace("\\", ".").removesuffix(ext),
            "risk_score": _estimate_file_risk(content),
            "lines": content.count("\n"),
            "classes": parsed["classes"],
            "functions": parsed["functions"],
        })

        for imp in parsed["imports"]:
            target = _resolve_import_path(project_path, imp, file_path)
            if target and target != rel_path:
                edges.append({
                    "source": rel_path,
                    "target": target,
                    "type": "imports",
                    "confidence": "EXTRACTED",
                })

        for call_target in parsed["calls"]:
            target = _resolve_import_path(project_path, call_target, file_path)
            if target and target != rel_path:
                edges.append({
                    "source": rel_path,
                    "target": target,
                    "type": "calls",
                    "confidence": "INFERRED",
                })

    return {"nodes": nodes, "edges": edges}


def _collect_source_files(project_path: Path) -> list[Path]:
    files: list[Path] = []
    for ext in _SUPPORTED_EXTS:
        for f in project_path.rglob(f"*{ext}"):
            p = str(f)
            if any(skip in p for skip in ("node_modules", ".git", "__pycache__", ".next", "dist", "build")):
                continue
            files.append(f)
    return files


def _parse_python(content: str, _file_path: Path) -> dict:
    imports: list[str] = []
    calls: list[str] = []
    classes: list[str] = []
    functions: list[str] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Fallback to regex for files with syntax errors
        return _parse_python_regex(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(_get_attr_chain(node.func))
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)

    return {"imports": imports, "calls": calls, "classes": classes, "functions": functions}


def _parse_python_regex(content: str) -> dict:
    import re
    imports = re.findall(r'^(?:from\s+(\S+)\s+import|import\s+(\S+))', content, re.MULTILINE)
    flat_imports = [m[0] or m[1] for m in imports if m[0] or m[1]]
    # Clean up "import X as Y" — take X
    flat_imports = [i.split(" as ")[0].strip() for i in flat_imports]
    return {"imports": flat_imports, "calls": [], "classes": [], "functions": []}


def _parse_typescript(content: str, _file_path: Path) -> dict:
    import re
    imports = re.findall(
        r'(?:import\s+.*?\s+from\s+["\']([^"\']+)["\']|import\s+["\']([^"\']+)["\'])',
        content,
    )
    flat_imports = [m[0] or m[1] for m in imports if m[0] or m[1]]
    calls = re.findall(r'(?:require|import)\(["\']([^"\']+)["\']\)', content)
    return {"imports": flat_imports, "calls": calls, "classes": [], "functions": []}


def _get_attr_chain(node: ast.Attribute) -> str:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _resolve_import_path(project_path: Path, module: str, source_file: Path) -> str | None:
    module_path = module.replace(".", "/")
    candidates = [
        project_path / f"{module_path}.py",
        project_path / module_path / "__init__.py",
        source_file.parent / f"{module_path}.py",
        source_file.parent / module_path / "__init__.py",
    ]
    for c in candidates:
        if c.is_file():
            try:
                return str(c.relative_to(project_path))
            except ValueError:
                pass
    return None


def _estimate_file_risk(content: str) -> float:
    lines = content.count("\n")
    risk = min(lines / 500.0, 1.0)
    import_count = content.count("import ")
    risk += min(import_count / 20.0, 0.5)
    return round(min(risk, 1.0), 2)
