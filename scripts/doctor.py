"""系统健康检查脚本 — 诊断开发环境是否就绪。"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check(name: str, condition: bool, detail: str = "") -> bool:
    icon = "✅" if condition else "❌"
    print(f"  {icon} {name}")
    if detail:
        print(f"     {detail}")
    return condition


def main() -> int:
    print("=" * 50)
    print("  System Health Check")
    print("=" * 50)

    ok = True

    # Python
    print(f"\n[Python] {sys.version.split()[0]}")
    ok &= check("Python >= 3.11", sys.version_info >= (3, 11), f"{sys.version_info.major}.{sys.version_info.minor}")

    # 核心依赖
    print("\n[Python Packages]")
    for pkg in ("typer", "rich", "fastapi", "uvicorn", "pydantic", "pytest"):
        found = importlib.util.find_spec(pkg) is not None
        ok &= check(pkg, found)

    # Claude CLI
    print("\n[Claude CLI]")
    claude_path = shutil.which("claude")
    ok &= check("claude CLI available", claude_path is not None, claude_path or "未找到")

    # Node.js
    print("\n[Node.js]")
    node_path = shutil.which("node")
    ok &= check("node available", node_path is not None)
    if node_path:
        result = subprocess.run([node_path, "--version"], capture_output=True, text=True)
        ok &= check("node version", True, result.stdout.strip())

    # npm
    print("\n[npm]")
    npm_path = shutil.which("npm")
    ok &= check("npm available", npm_path is not None)
    if npm_path:
        result = subprocess.run([npm_path, "--version"], capture_output=True, text=True)
        ok &= check("npm version", True, result.stdout.strip())

    # Playwright
    print("\n[Playwright]")
    pw = importlib.util.find_spec("playwright")
    ok &= check("playwright installed", pw is not None)

    # 环境变量
    print("\n[Environment Variables]")
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
        value = os.environ.get(var)
        masked = value[:8] + "..." if value and len(value) > 8 else ("未设置" if not value else "(已设置)")
        ok &= check(var, value is not None and len(value) > 0, masked)

    # 项目目录
    project_dir = Path.cwd()
    print(f"\n[Project] {project_dir}")
    ok &= check("project dir exists", project_dir.exists())
    ok &= check(".git exists", (project_dir / ".git").exists())

    # 数据目录
    data_dir = project_dir / "data"
    print("\n[Data Directory]")
    ok &= check("data/ exists", data_dir.exists())
    if data_dir.exists():
        for sub in ("prd.md", "features.json"):
            p = data_dir / sub
            ok &= check(sub, p.exists())

    # Dashboard 状态
    dash_dir = project_dir / "data" / "dashboard"
    print("\n[Dashboard State]")
    if dash_dir.exists():
        state_file = dash_dir / "state.json"
        ok &= check("state.json", state_file.exists())
        events_file = dash_dir / "events.jsonl"
        ok &= check("events.jsonl", events_file.exists())
    else:
        check("dashboard data dir", False, "尚未创建")

    print(f"\n{'=' * 50}")
    if ok:
        print("  ✅ All checks passed!")
    else:
        print("  ⚠️  Some checks failed. Review the details above.")
    print(f"{'=' * 50}\n")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
