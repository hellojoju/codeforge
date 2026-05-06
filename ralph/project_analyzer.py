from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.ralph_paths import resolve_ralph_dir


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ProjectAnalyzer:
    def __init__(self, project_path: Path | str, progress: dict[str, Any] | None = None):
        self.project_path = Path(project_path).resolve()
        self.progress = progress
        self.ralph_dir = resolve_ralph_dir(self.project_path)
        self.ralph_dir.mkdir(parents=True, exist_ok=True)
        self.report_path = self.ralph_dir / "project-report.md"
        self.structured_path = self.ralph_dir / "project-structured.json"

    def _update(self, status: str, progress: int, phase: str, message: str) -> None:
        if self.progress is None:
            return
        self.progress.update({"status": status, "progress": progress, "phase": phase, "message": message})

    def _collect_stats(self) -> dict[str, Any]:
        ext_stats: dict[str, int] = {}
        key_files: list[str] = []
        total_files = 0
        skip_dirs = {".git", "node_modules", "__pycache__", ".next", "venv", ".venv"}

        for path in self.project_path.rglob("*"):
            if not path.is_file() or any(part in skip_dirs for part in path.parts):
                continue
            total_files += 1
            ext = path.suffix.lstrip(".") or "other"
            ext_stats[ext] = ext_stats.get(ext, 0) + 1
            rel = str(path.relative_to(self.project_path))
            if rel in {"README.md", "pyproject.toml", "package.json", "Makefile", "ARCHITECTURE.md"}:
                key_files.append(rel)

        git = {"branch": "unknown", "last_commit": ""}
        try:
            git["branch"] = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.project_path, text=True, timeout=5
            ).strip()
            git["last_commit"] = subprocess.check_output(
                ["git", "log", "-1", "--format=%s"], cwd=self.project_path, text=True, timeout=5
            ).strip()
        except Exception:
            pass

        return {
            "project_name": self.project_path.name,
            "total_files": total_files,
            "file_stats": dict(sorted(ext_stats.items(), key=lambda x: x[1], reverse=True)),
            "key_files": key_files,
            "git": git,
            "analyzed_at": _now_iso(),
        }

    def _to_markdown(self, data: dict[str, Any]) -> str:
        lines = [
            f"# 项目分析报告: {data['project_name']}",
            "",
            f"- 分析时间: {data['analyzed_at']}",
            f"- 文件总数: {data['total_files']}",
            f"- Git 分支: {data['git'].get('branch', 'unknown')}",
            f"- 最近提交: {data['git'].get('last_commit', '')}",
            "",
            "## 语言分布",
        ]
        for ext, count in list(data.get("file_stats", {}).items())[:20]:
            lines.append(f"- `{ext}`: {count}")
        lines.append("")
        lines.append("## 关键文件")
        lines.extend([f"- `{f}`" for f in data.get("key_files", [])] or ["- （未识别）"])
        return "\n".join(lines)

    def analyze(self) -> dict[str, Any]:
        if not self.project_path.is_dir():
            raise FileNotFoundError(f"project not found: {self.project_path}")
        self._update("running", 20, "采集统计", "正在采集代码统计...")
        data = self._collect_stats()
        self._update("running", 80, "生成报告", "正在生成分析报告...")
        report = self._to_markdown(data)
        self.report_path.write_text(report, encoding="utf-8")
        self.structured_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._update("complete", 100, "分析完成", "项目分析已完成")
        return {"report": report, "structured": data}

    def get_saved_report(self) -> str | None:
        if not self.report_path.is_file():
            return None
        return self.report_path.read_text(encoding="utf-8")

    def get_saved_report_summary(self) -> dict[str, Any]:
        if not self.structured_path.is_file():
            return {}
        try:
            data = json.loads(self.structured_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return {
            "project_name": data.get("project_name", ""),
            "total_files": data.get("total_files", 0),
            "top_languages": list(data.get("file_stats", {}).items())[:5],
        }
