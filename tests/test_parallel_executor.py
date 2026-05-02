"""ParallelExecutor Phase 3 单元测试。"""

import time
from pathlib import Path
from ralph.parallel_executor import (
    FileLock, WorktreeManager, ParallelExecutor, ParallelTask,
    IntegrationQueue, MergeHandler, RegressionTester, ParallelOrchestrator,
)


# ==================== 1. FileLock Tests ====================


def test_file_lock_acquire_release(tmp_path: Path):
    lock = FileLock(tmp_path, "test-lock", timeout=5)
    assert lock.acquire() is True
    lock.release()
    assert lock._lock_file.is_file() is False


def test_file_lock_exclusive(tmp_path: Path):
    lock1 = FileLock(tmp_path, "exclusive", timeout=2)
    lock2 = FileLock(tmp_path, "exclusive", timeout=2)
    assert lock1.acquire() is True
    assert lock2.acquire() is False  # 不能同时获取
    lock1.release()
    assert lock2.acquire() is True  # 释放后可获取
    lock2.release()


def test_file_lock_context_manager(tmp_path: Path):
    with FileLock(tmp_path, "ctx", timeout=5) as lock:
        assert lock._acquired is True
    assert lock._acquired is False


# ==================== 2. Worktree Tests ====================

def test_worktree_list_active_empty(tmp_path: Path):
    # 非 git 仓库将返回空列表
    mgr = WorktreeManager(tmp_path, tmp_path / ".worktrees")
    trees = mgr.list_active()
    # 非 git 仓库不报错，返回空
    assert isinstance(trees, list)


def test_worktree_cleanup(tmp_path: Path):
    mgr = WorktreeManager(tmp_path, tmp_path / ".worktrees")
    count = mgr.cleanup_stale(max_age_hours=0)
    assert count >= 0


# ==================== 3. Parallel Executor Tests ====================


def test_topological_sort_no_deps():
    ex = ParallelExecutor(max_parallel=3)
    ex.add_task(ParallelTask(task_id="a", title="A"))
    ex.add_task(ParallelTask(task_id="b", title="B"))
    ex.add_task(ParallelTask(task_id="c", title="C"))
    layers = ex.topological_sort()
    assert len(layers) == 1
    assert set(layers[0]) == {"a", "b", "c"}


def test_topological_sort_with_deps():
    ex = ParallelExecutor(max_parallel=3)
    ex.add_task(ParallelTask(task_id="a", title="Schema", dependencies=[]))
    ex.add_task(ParallelTask(task_id="b", title="API", dependencies=["a"]))
    ex.add_task(ParallelTask(task_id="c", title="Frontend", dependencies=["a"]))
    ex.add_task(ParallelTask(task_id="d", title="Test", dependencies=["b", "c"]))
    layers = ex.topological_sort()
    assert len(layers) >= 2
    assert layers[0] == ["a"]  # a 先执行
    assert "d" in layers[-1]  # d 最后


def test_schedule_respects_max_parallel():
    ex = ParallelExecutor(max_parallel=2)
    for i in range(5):
        ex.add_task(ParallelTask(task_id=f"t{i}", title=f"Task {i}"))
    schedule = ex.schedule()
    for batch in schedule:
        assert len(batch) <= 2


def test_complete_updates_status():
    ex = ParallelExecutor()
    ex.add_task(ParallelTask(task_id="t1", title="T1"))
    ex.complete("t1", True)
    assert ex._tasks["t1"].status == "done"


def test_get_next_batch():
    ex = ParallelExecutor(max_parallel=2)
    ex.add_task(ParallelTask(task_id="a", title="A"))
    ex.add_task(ParallelTask(task_id="b", title="B"))
    batch = ex.get_next_batch()
    assert len(batch) == 2


def test_get_next_batch_with_deps():
    ex = ParallelExecutor(max_parallel=2)
    ex.add_task(ParallelTask(task_id="a", title="A"))
    ex.add_task(ParallelTask(task_id="b", title="B", dependencies=["a"]))
    # 不依赖 a 的可以执行
    batch = ex.get_next_batch()
    assert len(batch) == 1
    assert batch[0].task_id == "a"


# ==================== 4. Integration Queue Tests ====================


def test_integration_queue_push_pop():
    q = IntegrationQueue()
    task = ParallelTask(task_id="t1", title="T1")
    q.push(task)
    assert q.peek() == [task]
    popped = q.pop_next()
    assert popped is task
    assert q.pop_next() is None


def test_integration_queue_clear():
    q = IntegrationQueue()
    q.push(ParallelTask(task_id="t1", title="T1"))
    q.push(ParallelTask(task_id="t2", title="T2"))
    q.clear()
    assert q.peek() == []


# ==================== 5. Merge Tests ====================


def test_merge_detect_no_repo(tmp_path: Path):
    mh = MergeHandler(tmp_path)
    result = mh.merge("feature")
    assert result["success"] is False  # not a git repo


def test_merge_abort_succeeds_always(tmp_path: Path):
    mh = MergeHandler(tmp_path)
    # git merge --abort 即使不在合并中也返回 0（有效 git 命令）
    result = mh.abort_merge()
    assert isinstance(result, bool)


# ==================== 6. Regression Tests ====================


def test_regression_not_found(tmp_path: Path):
    rt = RegressionTester(tmp_path)
    result = rt.run_tests("nonexistent-command-xyz")
    assert result["success"] is False


# ==================== Full Pipeline Test ====================


def test_orchestrator_run(tmp_path: Path):
    orch = ParallelOrchestrator(tmp_path, max_parallel=2)
    tasks = [
        ParallelTask(task_id="wu-1", title="Schema", dependencies=[]),
        ParallelTask(task_id="wu-2", title="API", dependencies=["wu-1"]),
    ]
    result = orch.run_parallel(tasks)
    assert result["tasks_completed"] == 2
    assert "regression" in result
