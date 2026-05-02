"""SourceDocsCheck — 项目依赖版本检测 + 官方文档源管理。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class DependencyInfo:
    name: str
    version: str = ""
    category: str = "unknown"  # runtime | dev | build
    required_for: list[str] = field(default_factory=list)


@dataclass
class DocSource:
    """外部文档引用。"""
    topic: str
    url: str
    version: str = ""
    notes: str = ""


class SourceDocsCheck:
    """识别项目依赖版本，提供关键依赖的官方文档引用。"""

    DOC_PATTERNS: dict[str, list[str]] = {
        "next": [
            "https://nextjs.org/docs",
            "https://nextjs.org/docs/app/building-your-application",
        ],
        "fastapi": [
            "https://fastapi.tiangolo.com",
        ],
        "react": [
            "https://react.dev/reference/react",
        ],
        "claude_code": [
            "https://docs.anthropic.com/en/docs/claude-code/overview",
        ],
    }

    def __init__(self, project_dir: Path | None = None):
        self._project_dir = project_dir

    def scan_dependencies(self, project_dir: Path | None = None) -> list[DependencyInfo]:
        """扫描项目目录，提取依赖版本信息。"""
        base = project_dir or self._project_dir
        if not base:
            return []

        deps: list[DependencyInfo] = []

        # 检查 package.json (Node.js)
        pkg_json = base / "package.json"
        if pkg_json.is_file():
            try:
                pkg = json.loads(pkg_json.read_text())
                for dep_type, entries in [("runtime", pkg.get("dependencies", {})),
                                           ("dev", pkg.get("devDependencies", {}))]:
                    for name, version in entries.items():
                        deps.append(DependencyInfo(
                            name=name, version=version.replace("^", "").replace("~", ""),
                            category=dep_type,
                            required_for=self._guess_required_for(name),
                        ))
            except (json.JSONDecodeError, OSError):
                pass

        # 检查 pyproject.toml (Python)
        pyproject = base / "pyproject.toml"
        if pyproject.is_file():
            try:
                content = pyproject.read_text()
                for match in re.finditer(r'([\w-]+)\s*=\s*"[^"]*"', content):
                    name = match.group(1)
                    if name not in ("name", "requires-python"):
                        # 尝试找版本
                        ver_match = re.search(
                            rf'{re.escape(name)}\s*=\s*"([^"]*)"', content,
                        )
                        version = ver_match.group(1) if ver_match else ""
                        deps.append(DependencyInfo(
                            name=name, version=version,
                            category="runtime",
                            required_for=self._guess_required_for(name),
                        ))
            except OSError:
                pass

        return deps

    def get_docs(self, dep_name: str) -> list[DocSource]:
        """获取指定依赖的官方文档链接。"""
        dep_lower = dep_name.lower()
        results: list[DocSource] = []

        for pattern, urls in self.DOC_PATTERNS.items():
            if pattern in dep_lower or dep_lower in pattern:
                for url in urls:
                    results.append(DocSource(topic=pattern, url=url))

        # 通用的 PyPI 文档兜底
        if not results:
            results.append(DocSource(
                topic=dep_name,
                url=f"https://pypi.org/project/{dep_name.lower()}",
                notes="Auto-detected from package manager",
            ))

        return results

    def get_all_docs(self, deps: list[DependencyInfo] | None = None) -> list[DocSource]:
        """收集所有关键依赖的官方文档。"""
        if deps is None:
            deps = self.scan_dependencies()

        all_docs: list[DocSource] = []
        seen = set()

        for dep in deps:
            docs = self.get_docs(dep.name)
            for doc in docs:
                if doc.url not in seen:
                    seen.add(doc.url)
                    all_docs.append(doc)

        return all_docs

    def markdown_report(self, project_dir: Path | None = None) -> str:
        """生成文档检查报告 Markdown。"""
        deps = self.scan_dependencies(project_dir)
        docs = self.get_all_docs(deps)
        lines = [
            "# Source Docs Check 报告",
            "",
            "## 依赖概览",
            "",
        ]
        for dep in deps:
            lines.append(f"- **{dep.name}** ({dep.category}): {dep.version}")
        lines += ["", "## 官方文档引用", ""]
        for doc in docs:
            lines.append(f"- [{doc.topic}]({doc.url}) {doc.notes}")
        return "\n".join(lines)

    @staticmethod
    def _guess_required_for(name: str) -> list[str]:
        name_lower = name.lower()
        if name_lower in ("next", "react", "react-dom"):
            return ["frontend"]
        if name_lower in ("fastapi", "flask", "django"):
            return ["backend", "api"]
        if name_lower in ("playwright", "vitest", "jest", "pytest"):
            return ["test"]
        if name_lower in ("prisma", "sqlalchemy", "psycopg2", "typeorm"):
            return ["database"]
        return []
