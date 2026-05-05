#!/usr/bin/env python3
"""状态迁移脚本 — 将旧格式 features.json / tasks.db 合并到统一 state.json。

用法:
    python scripts/migrate_state.py                          # 默认 project 目录
    python scripts/migrate_state.py --project-dir ./demo     # 指定项目目录
    python scripts/migrate_state.py --dry-run                # 预览不写入
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def load_old_features(project_dir: Path) -> list[dict]:
    """读取旧格式 data/features.json。"""
    path = project_dir / "data" / "features.json"
    if not path.exists():
        print(f"[SKIP] features.json 不存在: {path}")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    print(f"[OK] features.json: {len(features)} 个 feature")
    return features


def load_tasks_db(project_dir: Path) -> list[dict]:
    """读取 data/tasks.db SQLite 中的 task 记录。"""
    path = project_dir / "data" / "tasks.db"
    if not path.exists():
        print(f"[SKIP] tasks.db 不存在: {path}")
        return []
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM tasks")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        print(f"[OK] tasks.db: {len(rows)} 条 task 记录")
        return rows
    except sqlite3.OperationalError as e:
        print(f"[WARN] tasks.db 读取失败: {e}")
        return []


def load_execution_ledger(project_dir: Path) -> list[dict]:
    """读取 data/execution-plan.json。"""
    path = project_dir / "data" / "execution-plan.json"
    if not path.exists():
        print(f"[SKIP] execution-plan.json 不存在: {path}")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    executions = data.get("executions", [])
    print(f"[OK] execution-plan.json: {len(executions)} 条执行记录")
    return executions


def merge_into_state(
    old_features: list[dict],
    tasks: list[dict],
    executions: list[dict],
) -> dict:
    """合并旧数据为 state.json 格式。"""
    now = datetime.now(UTC).isoformat()

    # 转换旧 feature 格式（兼容新旧字段差异）
    features = []
    for f in old_features:
        features.append({
            "id": f.get("id", ""),
            "category": f.get("category", "未知"),
            "description": f.get("description", ""),
            "priority": f.get("priority", "P2"),
            "assigned_to": f.get("assigned_to", ""),
            "assigned_instance": f.get("assigned_instance", ""),
            "status": f.get("status", "pending"),
            "passes": f.get("passes", False),
            "test_steps": f.get("test_steps", []),
            "dependencies": f.get("dependencies", []),
            "workspace_id": f.get("workspace_id", ""),
            "files_changed": f.get("files_changed", []),
            "started_at": f.get("started_at", ""),
            "completed_at": f.get("completed_at", ""),
            "error_log": f.get("error_log", []),
            "blocking_issues": f.get("blocking_issues", []),
        })

    # tasks 转 command 兼容格式
    commands = []
    for t in tasks:
        commands.append({
            "command_id": t.get("id", ""),
            "type": t.get("type", "task"),
            "status": t.get("status", "pending"),
            "target_id": t.get("feature_id", ""),
            "created_at": t.get("created_at", now),
            "completed_at": t.get("completed_at", ""),
            "result": t.get("result", ""),
        })

    state = {
        "agents": [],
        "features": features,
        "commands": commands,
        "events": [],
        "chat_history": [],
        "module_assignments": [],
        "blocking_issues": [],
        "next_event_id": 0,
    }

    print(f"\n[合并结果] features={len(features)}, commands={len(commands)}, executions={len(executions)}")
    return state


def write_state(state: dict, project_dir: Path, dry_run: bool) -> None:
    """写入 data/dashboard/state.json。"""
    state_file = project_dir / "data" / "dashboard" / "state.json"

    if dry_run:
        print(f"[DRY-RUN] 将写入 {state_file}")
        print(json.dumps(state, ensure_ascii=False, indent=2)[:500] + "...")
        return

    if state_file.exists():
        answer = input(f"  {state_file} 已存在，覆盖？[y/N] ").strip().lower()
        if answer != "y":
            print("[SKIP] 用户取消")
            return

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 已写入 {state_file} ({len(json.dumps(state))} 字节)")


def main() -> None:
    parser = argparse.ArgumentParser(description="合并旧状态文件到统一 state.json")
    parser.add_argument("--project-dir", default="project", help="项目目录 (默认: project)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入文件")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        print(f"[ERROR] 项目目录不存在: {project_dir}")
        sys.exit(1)

    print(f"=== 状态迁移: {project_dir} ===\n")

    old_features = load_old_features(project_dir)
    tasks = load_tasks_db(project_dir)
    executions = load_execution_ledger(project_dir)

    if not old_features and not tasks:
        print("\n[WARN] 未找到 features.json 或 tasks.db，没有可迁移的数据")
        return

    state = merge_into_state(old_features, tasks, executions)
    write_state(state, project_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
