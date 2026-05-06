#!/usr/bin/env python3
"""Minimal architecture import checker.

Rules:
1) core/* must not import dashboard/* or ralph/*
2) agents/* must not import dashboard/* or ralph/*
3) ralph/* must not import dashboard/*
4) imports under `if TYPE_CHECKING:` are ignored
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("core", "agents", "ralph", "dashboard")
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next"}


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for dirname in TARGET_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


def module_root_from_node(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        if not node.names:
            return None
        return node.names[0].name.split(".", 1)[0]
    if isinstance(node, ast.ImportFrom):
        if node.module:
            return node.module.split(".", 1)[0]
    return None


def is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return (
        isinstance(test, ast.Attribute)
        and isinstance(test.value, ast.Name)
        and test.value.id == "typing"
        and test.attr == "TYPE_CHECKING"
    )


def collect_runtime_imports(tree: ast.Module) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._skip_stack: list[bool] = []

        def _is_skipped(self) -> bool:
            return any(self._skip_stack)

        def visit_If(self, node: ast.If) -> None:  # noqa: N802
            guarded = is_type_checking_guard(node)
            self._skip_stack.append(guarded or self._is_skipped())
            for stmt in node.body:
                self.visit(stmt)
            self._skip_stack.pop()
            for stmt in node.orelse:
                self.visit(stmt)

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
            if self._is_skipped():
                return
            root = module_root_from_node(node)
            if root:
                imports.append((node.lineno, root))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if self._is_skipped():
                return
            root = module_root_from_node(node)
            if root:
                imports.append((node.lineno, root))

    Visitor().visit(tree)
    return imports


def source_group(path: Path) -> str:
    rel = path.relative_to(ROOT)
    return rel.parts[0]


def violates(group: str, imported_root: str) -> bool:
    if group == "core":
        return imported_root in {"dashboard", "ralph"}
    if group == "agents":
        return imported_root in {"dashboard", "ralph"}
    if group == "ralph":
        return imported_root == "dashboard"
    return False


def main() -> int:
    violations: list[str] = []
    for path in iter_python_files():
        group = source_group(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as err:
            violations.append(f"{path.relative_to(ROOT)}: parse error: {err}")
            continue

        for lineno, imported_root in collect_runtime_imports(tree):
            if violates(group, imported_root):
                violations.append(
                    f"{path.relative_to(ROOT)}:{lineno} -> {group} imports {imported_root}"
                )

    if violations:
        print("Architecture check failed:")
        for line in violations:
            print(f"- {line}")
        return 1

    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
