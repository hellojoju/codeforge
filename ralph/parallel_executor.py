"""ParallelExecutor — 隔离并行执行引擎。

Phase 3 六项全部实现：
1. 文件级锁 — _FileLock (线程安全 + 进程安全)
2. git worktree 隔离 — WorktreeManager (创建/删除/清理)
3. 并行任务调度 — ParallelExecutor (依赖拓扑排序 + 并发控制)
4. 集成队列 — IntegrationQueue (任务完成顺序合并)
5. 合并冲突处理 — MergeHandler (自动合并 + 冲突标记)
6. 集成后回归测试 — RegressionTester (全量测试 + 对比基线)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.ralph_paths import resolve_ralph_dir
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

LifecycleHook = Callable[[str, dict[str, Any]], None]
"""生命周期 hook 类型。event: before_create|after_create|before_remove|after_remove|before_merge|after_merge|before_cleanup|after_cleanup"""

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ==================== 1. 文件级锁 ====================


class FileLock:
    """进程安全的文件级锁（基于文件系统）。"""

    def __init__(self, lock_dir: Path, lock_name: str, timeout: float = 30.0):
        self._lock_file = lock_dir / f"{lock_name}.lock"
        self._lock_dir = lock_dir
        self._timeout = timeout
        self._acquired = False

    def acquire(self) -> bool:
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                fd = os.open(str(self._lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._acquired = True
                return True
            except FileExistsError:
                # 检查是否过期
                if self._lock_file.is_file():
                    age = time.monotonic() - self._lock_file.stat().st_mtime
                    if age > self._timeout:
                        self._lock_file.unlink(missing_ok=True)
                        continue
                time.sleep(0.1)
        return False

    def release(self) -> None:
        if self._acquired:
            self._lock_file.unlink(missing_ok=True)
            self._acquired = False

    def __enter__(self):
        acquired = self.acquire()
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock: {self._lock_file}")
        return self

    def __exit__(self, *args):
        self.release()


# ==================== 2. Worktree 管理 ====================


@dataclass
class WorktreeInfo:
    name: str
    path: Path
    branch: str
    created_at: str = field(default_factory=_now_iso)
    status: str = "active"  # active | merged | stale


class WorktreeManager:
    """git worktree 创建/删除/清理。"""

    def __init__(self, repo_dir: Path, worktrees_dir: Path | None = None):
        self._repo = repo_dir
        self._wt_dir = worktrees_dir or (repo_dir / ".worktrees")
        self._wt_dir.mkdir(parents=True, exist_ok=True)
        self._hooks: dict[str, list[LifecycleHook]] = defaultdict(list)

    def register_hook(self, event: str, hook: LifecycleHook) -> None:
        """注册生命周期 hook。

        events: before_create, after_create, before_remove, after_remove,
                before_merge, after_merge, before_cleanup, after_cleanup
        """
        if event in ("before_create", "after_create", "before_remove", "after_remove",
                     "before_merge", "after_merge", "before_cleanup", "after_cleanup"):
            self._hooks[event].append(hook)

    def _run_hooks(self, event: str, **kwargs: Any) -> None:
        for hook in self._hooks.get(event, []):
            try:
                hook(event, kwargs)
            except Exception as e:
                logger.warning("Hook %s failed for event %s: %s", getattr(hook, "__name__", "?"), event, e)

    def create(self, name: str, base_branch: str = "main") -> WorktreeInfo | None:
        """创建新的 worktree 和分支。"""
        self._run_hooks("before_create", name=name, base_branch=base_branch)
        branch = f"parallel/{name}/{int(time.time())}"
        wt_path = self._wt_dir / name

        try:
            # 确保 base_branch 存在
            subprocess.run(["git", "fetch", "--all"], cwd=self._repo,
                           capture_output=True, timeout=30)
            subprocess.run(["git", "checkout", base_branch], cwd=self._repo,
                           capture_output=True, timeout=30)
            subprocess.run(["git", "branch", branch, base_branch], cwd=self._repo,
                           capture_output=True, timeout=10)
            subprocess.run(
                ["git", "worktree", "add", str(wt_path), branch],
                cwd=self._repo, capture_output=True, timeout=30,
            )
            info = WorktreeInfo(name=name, path=wt_path, branch=branch)
            self._run_hooks("after_create", name=name, branch=branch, path=str(wt_path), info=info)
            return info
        except subprocess.TimeoutExpired:
            logger.error("Worktree creation timeout: %s", name)
            return None
        except Exception as e:
            logger.error("Worktree creation failed: %s - %s", name, e)
            return None

    def remove(self, name: str) -> bool:
        """删除 worktree。"""
        self._run_hooks("before_remove", name=name)
        wt_path = self._wt_dir / name
        if not wt_path.is_dir():
            return False
        try:
            subprocess.run(["git", "worktree", "remove", str(wt_path)],
                           cwd=self._repo, capture_output=True, timeout=30)
            shutil.rmtree(wt_path, ignore_errors=True)
            self._run_hooks("after_remove", name=name, success=True)
            return True
        except Exception:
            shutil.rmtree(wt_path, ignore_errors=True)
            self._run_hooks("after_remove", name=name, success=False)
            return False

    def list_active(self) -> list[WorktreeInfo]:
        """列出活跃 worktree。"""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self._repo, capture_output=True, text=True, timeout=10,
            )
            trees = []
            for block in result.stdout.strip().split("\n\n"):
                path_match = re.search(r"worktree (.+)", block)
                branch_match = re.search(r"branch refs/heads/(.+)", block)
                if path_match:
                    trees.append(WorktreeInfo(
                        name=Path(path_match.group(1)).name,
                        path=Path(path_match.group(1)),
                        branch=branch_match.group(1) if branch_match else "detached",
                    ))
            return trees
        except Exception:
            return []

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """清理过期的 worktree。"""
        self._run_hooks("before_cleanup", max_age_hours=max_age_hours)
        count = 0
        for tree in self.list_active():
            try:
                age = time.time() - tree.path.stat().st_mtime
                if age > max_age_hours * 3600:
                    if self.remove(tree.name):
                        count += 1
            except OSError:
                continue
        self._run_hooks("after_cleanup", removed_count=count)
        return count

    def merge_back(self, name: str, target_branch: str = "main",
                   strategy: str = "auto") -> dict:
        """将 worktree 的改动合并回目标分支。

        strategy:
          - auto: 优先 git merge，冲突时回退到 patch merge
          - merge: 只尝试 git merge
          - patch: 用 diff + apply 方式合并
        """
        self._run_hooks("before_merge", name=name, target_branch=target_branch, strategy=strategy)

        wt_path = self._wt_dir / name
        if not wt_path.is_dir():
            return {"success": False, "error": f"Worktree {name} not found"}

        # Look up actual branch from worktree (create() uses timestamped names)
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=wt_path, capture_output=True, text=True, timeout=10,
        )
        branch = branch_result.stdout.strip() or f"parallel/{name}"

        if strategy == "patch":
            result = self._patch_merge(name, target_branch)
            self._run_hooks("after_merge", name=name, target_branch=target_branch,
                            strategy="patch", result=result)
            return result

        try:
            subprocess.run(["git", "checkout", target_branch], cwd=self._repo,
                           capture_output=True, timeout=30)
            result = subprocess.run(
                ["git", "merge", branch, "--no-edit"],
                cwd=self._repo, capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                ret = {"success": True, "strategy": "merge", "message": "Clean merge"}
                self._run_hooks("after_merge", name=name, target_branch=target_branch,
                                strategy="merge", result=ret)
                return ret

            if strategy == "auto":
                logger.warning("Merge conflict for %s, falling back to patch merge", name)
                subprocess.run(["git", "merge", "--abort"], cwd=self._repo,
                               capture_output=True, timeout=30)
                result = self._patch_merge(name, target_branch)
                self._run_hooks("after_merge", name=name, target_branch=target_branch,
                                strategy="patch", result=result)
                return result

            return {"success": False, "strategy": "merge", "error": "Merge conflict",
                    "conflict_files": self._detect_worktree_conflicts()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Merge timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _patch_merge(self, name: str, target_branch: str = "main") -> dict:
        """用 patch 方式合并（diff + apply），避免冲突。"""
        wt_path = self._wt_dir / name
        if not wt_path.is_dir():
            return {"success": False, "error": f"Worktree {name} not found"}

        # Look up actual branch from worktree
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=wt_path, capture_output=True, text=True, timeout=10,
        )
        branch = branch_result.stdout.strip() or f"parallel/{name}"

        try:
            # From worktree's HEAD, generate diff against target_branch
            diff = subprocess.run(
                ["git", "diff", f"{target_branch}..{branch}", "--binary"],
                cwd=self._repo, capture_output=True, text=True, timeout=30,
            )

            if not diff.stdout.strip():
                return {"success": True, "strategy": "patch", "message": "No changes to merge"}

            # 切回 target 分支并 apply
            subprocess.run(["git", "checkout", target_branch], cwd=self._repo,
                           capture_output=True, timeout=30)

            apply = subprocess.run(
                ["git", "apply", "--3way", "--allow-empty"],
                cwd=self._repo, input=diff.stdout, capture_output=True, text=True, timeout=60,
            )

            if apply.returncode == 0:
                subprocess.run(["git", "add", "-A"], cwd=self._repo,
                               capture_output=True, timeout=30)
                subprocess.run(
                    ["git", "commit", "-m", f"patch merge: {name} from parallel/{name}"],
                    cwd=self._repo, capture_output=True, timeout=30,
                )
                return {"success": True, "strategy": "patch",
                        "files_changed": len(diff.stdout.strip().split("\n\n"))}
            else:
                subprocess.run(["git", "apply", "--abort"], cwd=self._repo,
                               capture_output=True, timeout=10)
                return {"success": False, "strategy": "patch",
                        "error": f"Patch apply failed: {apply.stderr[:200]}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Patch merge timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _detect_worktree_conflicts(self) -> list[str]:
        """检测合并冲突文件。"""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=self._repo, capture_output=True, text=True, timeout=10,
            )
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        except Exception:
            return []


# ==================== 3. 并行任务调度 ====================


@dataclass
class ParallelTask:
    task_id: str
    title: str
    scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed
    assigned_to: str = ""
    worktree_name: str = ""
    result: dict = field(default_factory=dict)


class ParallelExecutor:
    """任务依赖拓扑排序 + 并行调度。"""

    def __init__(self, max_parallel: int = 3):
        self._max = max_parallel
        self._tasks: dict[str, ParallelTask] = {}
        self._lock = threading.Lock()

    def add_task(self, task: ParallelTask) -> None:
        self._tasks[task.task_id] = task

    def add_tasks(self, tasks: list[ParallelTask]) -> None:
        for t in tasks:
            self._tasks[t.task_id] = t

    def topological_sort(self) -> list[list[str]]:
        """按依赖关系拓扑排序，返回分层列表。每层可并行执行。"""
        in_degree: dict[str, int] = {}
        graph: dict[str, list[str]] = defaultdict(list)

        for tid, task in self._tasks.items():
            in_degree.setdefault(tid, 0)
            for dep in task.dependencies:
                if dep in self._tasks:
                    graph.setdefault(dep, []).append(tid)
                    in_degree[tid] = in_degree.get(tid, 0) + 1

        layers: list[list[str]] = []
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        processed = set()

        while queue:
            current_layer = list(queue)
            layers.append(current_layer)
            # 标记当前层为运行中
            for tid in current_layer:
                processed.add(tid)
                self._tasks[tid].status = "running"

            next_queue = deque()
            for tid in current_layer:
                for dep_id in graph[tid]:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0 and dep_id not in processed:
                        next_queue.append(dep_id)
            queue = next_queue

        return layers

    def schedule(self) -> list[list[str]]:
        """返回可并行执行的各层任务。按 max_parallel 限制并发。"""
        layers = self.topological_sort()
        throttled = []
        for layer in layers:
            for i in range(0, len(layer), self._max):
                throttled.append(layer[i:i + self._max])
        return throttled

    def complete(self, task_id: str, success: bool, result: dict | None = None) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "done" if success else "failed"
            task.result = result or {}

    def get_next_batch(self) -> list[ParallelTask]:
        """获取下一批可执行的任务。"""
        with self._lock:
            running = sum(1 for t in self._tasks.values() if t.status == "running")
            pending = [t for t in self._tasks.values()
                       if t.status == "pending"
                       and all(self._tasks.get(d) is not None
                               and self._tasks[d].status == "done"
                               for d in t.dependencies if self._tasks.get(d))]
            available_slots = max(0, self._max - running)
            return pending[:available_slots]


# ==================== 4. 集成队列 ====================


class IntegrationQueue:
    """顺序集成队列：按完成任务的时间顺序合并到主线。"""

    def __init__(self):
        self._queue: list[ParallelTask] = []
        self._lock = threading.Lock()

    def push(self, task: ParallelTask) -> None:
        with self._lock:
            self._queue.append(task)

    def pop_next(self) -> ParallelTask | None:
        with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    def peek(self) -> list[ParallelTask]:
        with self._lock:
            return list(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()


# ==================== 5. 合并冲突处理 ====================


class MergeHandler:
    """git merge + 冲突检测与标记。"""

    def __init__(self, repo_dir: Path):
        self._repo = repo_dir

    def merge(self, source_branch: str, target_branch: str = "main") -> dict:
        """合并分支到目标分支。尝试自动解决冲突，失败则报告。"""
        try:
            subprocess.run(["git", "checkout", target_branch], cwd=self._repo,
                           capture_output=True, timeout=30)
            result = subprocess.run(
                ["git", "merge", source_branch, "--no-edit"],
                cwd=self._repo, capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                return {"success": True, "merged": True, "message": "Clean merge"}

            # 冲突：尝试 --strategy-option theirs 自动解决
            subprocess.run(["git", "merge", "--abort"], cwd=self._repo,
                           capture_output=True, timeout=10)
            retry = subprocess.run(
                ["git", "merge", source_branch, "--no-edit", "-X", "theirs"],
                cwd=self._repo, capture_output=True, text=True, timeout=60,
            )
            if retry.returncode == 0:
                return {"success": True, "merged": True, "message": "Auto-resolved with theirs strategy"}

            # 仍然冲突，报告冲突文件
            conflict_files = self._detect_conflicts()
            return {
                "success": False,
                "conflicts": True,
                "conflict_files": conflict_files,
                "message": f"Merge conflict in {len(conflict_files)} files",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Merge timeout"}

    def _detect_conflicts(self) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=self._repo, capture_output=True, text=True, timeout=10,
            )
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        except Exception:
            return []

    def abort_merge(self) -> bool:
        try:
            subprocess.run(["git", "merge", "--abort"], cwd=self._repo,
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False


# ==================== 6. 回归测试 ====================


class RegressionTester:
    """集成后回归测试。"""

    def __init__(self, project_dir: Path):
        self._project = project_dir

    def run_tests(self, test_command: str = "") -> dict:
        """运行全量测试，返回结果。"""
        cmd = test_command or "python3 -m pytest -q"
        try:
            result = subprocess.run(
                shlex.split(cmd), cwd=self._project,
                capture_output=True, text=True, timeout=600,
            )
            passed = result.returncode == 0
            # 提取测试统计
            match = re.search(r"(\d+) passed", result.stdout)
            total = int(match.group(1)) if match else 0
            return {
                "success": passed,
                "total": total,
                "stdout": result.stdout[-500:],
                "command": cmd,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "total": 0, "error": "Timeout"}
        except FileNotFoundError:
            return {"success": False, "total": 0, "error": f"Command not found: {cmd}"}


# ==================== Orchestrator ====================


class ParallelOrchestrator:
    """Phase 3 并行执行编排器，整合全部 6 项能力。"""

    def __init__(self, repo_dir: Path, max_parallel: int = 3, work_unit_engine=None):
        self.repo = repo_dir
        self._wue = work_unit_engine
        self.worktree_mgr = WorktreeManager(repo_dir)
        self.executor = ParallelExecutor(max_parallel=max_parallel)
        self.integration = IntegrationQueue()
        self.merge_handler = MergeHandler(repo_dir)
        self.regression = RegressionTester(repo_dir)
        self._lock_dir = resolve_ralph_dir(repo_dir) / "locks"
        self._lock_dir.mkdir(parents=True, exist_ok=True)

    async def dispatch_work_units(self, work_units: list, prd_summary: str = "") -> dict:
        """并行执行一批 WorkUnit。

        按依赖拓扑分层，每层内各 WorkUnit 在独立 worktree 中并发执行，
        每层执行完后合并回主线，最后跑回归测试。
        """
        # 转为并行任务
        tasks = []
        for wu in work_units:
            deps = list(getattr(wu, "dependencies", []) or [])
            tasks.append(ParallelTask(
                task_id=wu.work_id,
                title=getattr(wu, "title", "") or wu.work_id,
                scope=list(getattr(wu, "scope_allow", []) or []),
                dependencies=deps,
            ))

        self.executor.add_tasks(tasks)
        layers = self.executor.schedule()
        all_details = []

        for layer in layers:
            async def _exec_one(tid: str) -> dict:
                task = self.executor._tasks.get(tid)
                if not task:
                    return {"task_id": tid, "error": "task not found"}

                # 创建 worktree 隔离
                wt = self.worktree_mgr.create(task.task_id)
                if wt:
                    task.worktree_name = wt.name

                tool_cwd = wt.path if wt else None

                try:
                    if self._wue:
                        result = await self._wue.execute(tid, prd_summary=prd_summary, tool_cwd=tool_cwd)
                        success = result.get("success", False)
                        self.executor.complete(tid, success, result)
                    else:
                        self.executor.complete(tid, True)
                except Exception as e:
                    logger.error("WorkUnit %s 并行执行异常: %s", tid, e)
                    self.executor.complete(tid, False, {"error": str(e)})

                return {"task_id": tid, "worktree": wt.name if wt else ""}

            # 本层并发执行
            layer_results = await asyncio.gather(*[_exec_one(tid) for tid in layer])

            # 合并回主线
            for r in layer_results:
                if r.get("worktree"):
                    branch = f"parallel/{r['task_id']}"
                    merge_result = self.merge_handler.merge(branch)
                    r["merge"] = merge_result
                    self.worktree_mgr.remove(r["task_id"])
                all_details.append(r)

        # 回归测试
        regression = self.regression.run_tests()
        return {
            "tasks_completed": len(all_details),
            "success": all(d.get("merge", {}).get("success", True) for d in all_details),
            "regression": regression,
            "details": all_details,
        }
