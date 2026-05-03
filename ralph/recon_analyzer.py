"""ReconAnalyzer — 深度代码库侦察分析。

消费 ProjectAnalyzer 的结构化输出，避免重复扫描。
当无上游数据时（独立运行场景），回退到自行扫描。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class ReconAnalyzer:
    """深度代码库侦察：技术栈、模块边界、关键文件、Git 摘要。

    优先接收 ProjectAnalyzer 的 structured 输出作为基础数据，
    再补充自身扫描的结果（模块检测、文件计数等）。
    """

    COMMON_DIRS = [
        "src", "app", "components", "lib", "ralph", "dashboard", "agents",
        "core", "tests", "pages", "api",
    ]

    def __init__(self):
        pass

    def analyze(self, project_path: Path,
                project_analysis: dict | None = None) -> dict:
        """分析项目代码库。

        project_analysis: ProjectAnalyzer.analyze() 返回的 structured 数据。
                         传入后作为基础数据，减少重复扫描。
        """
        if project_analysis:
            return self._from_project_analysis(project_path, project_analysis)
        return self._from_scratch(project_path)

    def _from_project_analysis(self, project_path: Path,
                                project_analysis: dict) -> dict:
        """基于 ProjectAnalyzer 的结构化输出生成侦察报告。"""
        return {
            "project_name": project_analysis.get("project_name", project_path.name),
            "tech_stack": project_analysis.get("tech_stack", {}),
            "modules": self._detect_modules(project_path),
            "key_files": [f["path"] for f in project_analysis.get("key_files", [])],
            "git_summary": self._git_summary(project_path),
            "file_count": self._count_files(project_path),
            "entry_points": project_analysis.get("entry_points", []),
        }

    def _from_scratch(self, project_path: Path) -> dict:
        """无上游数据时自行扫描。"""
        return {
            "project_name": project_path.name,
            "tech_stack": self._detect_tech_stack(project_path),
            "modules": self._detect_modules(project_path),
            "key_files": self._detect_key_files(project_path),
            "git_summary": self._git_summary(project_path),
            "file_count": self._count_files(project_path),
            "entry_points": [],
        }

    def _detect_tech_stack(self, path: Path) -> dict:
        stack: dict[str, str] = {}
        pkg_json = path / "package.json"
        if pkg_json.is_file():
            try:
                pkg = json.loads(pkg_json.read_text())
                deps = str(pkg.get("dependencies", {}))
                stack["runtime"] = "node"
                if "next" in deps:
                    stack["framework"] = "next"
                elif "react" in deps:
                    stack["framework"] = "react"
                else:
                    stack["framework"] = "node"
            except (json.JSONDecodeError, OSError):
                pass

        pyproject = path / "pyproject.toml"
        if pyproject.is_file():
            try:
                content = pyproject.read_text()
                stack["runtime"] = "python"
                if "fastapi" in content:
                    stack["framework"] = "fastapi"
                elif "django" in content:
                    stack["framework"] = "django"
                elif "flask" in content:
                    stack["framework"] = "flask"
                else:
                    stack["framework"] = "python"
            except OSError:
                pass

        go_mod = path / "go.mod"
        if go_mod.is_file():
            stack["runtime"] = "go"
            stack.setdefault("framework", "go")

        return stack

    def _detect_modules(self, path: Path) -> list[dict]:
        modules = []
        for d in self.COMMON_DIRS:
            full = path / d
            if full.is_dir():
                py_files = len(list(full.rglob("*.py")))
                ts_files = len(list(full.rglob("*.ts"))) + len(list(full.rglob("*.tsx")))
                modules.append({
                    "name": d,
                    "python_files": py_files,
                    "typescript_files": ts_files,
                })
        return modules

    def _detect_key_files(self, path: Path) -> list[str]:
        patterns = [
            "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
            "README.md", "ARCHITECTURE.md", "Makefile", "Dockerfile",
        ]
        key_files = []
        for pattern in patterns:
            matched = list(path.glob(pattern))
            for f in matched:
                if ".git" not in f.parts and "node_modules" not in f.parts:
                    key_files.append(str(f.relative_to(path)))
        return sorted(key_files)

    def _git_summary(self, path: Path) -> dict:
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path, text=True, timeout=5,
            ).strip()
            log = subprocess.check_output(
                ["git", "log", "--oneline", "-10"],
                cwd=path, text=True, timeout=5,
            ).strip()
            return {"branch": branch, "recent_commits": log}
        except Exception:
            return {"branch": "unknown", "recent_commits": ""}

    def _count_files(self, path: Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ext in ["py", "ts", "tsx", "js", "css", "html", "md", "json", "yaml", "sql"]:
            n = len(list(path.rglob(f"*.{ext}")))
            if n > 0:
                counts[ext] = n
        return counts
