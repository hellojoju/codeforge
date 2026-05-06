"""Ralph 目录解析工具。"""

from __future__ import annotations

from pathlib import Path


def resolve_ralph_dir(project_dir: Path | None = None) -> Path:
    """解析 .ralph 目录的绝对路径。

    Args:
        project_dir: 项目根目录，默认当前工作目录。

    Returns:
        .ralph 目录的 Path 对象（不检查是否存在）。
    """
    base = project_dir or Path.cwd()
    return base / ".ralph"
