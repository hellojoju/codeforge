from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core.state_models import (
    AgentInstance,
    BlockingIssue,
    Command,
    Feature,
)
from dashboard.state_repository import ProjectStateRepository


def _repo(tmp_path: Path) -> ProjectStateRepository:
    return ProjectStateRepository(base_dir=tmp_path, project_id="p1", run_id="r1")


@pytest.fixture
def repo(tmp_path: Path) -> ProjectStateRepository:
    return ProjectStateRepository(
        base_dir=tmp_path / "data",
        project_id="test-project",
        run_id="run-001",
    )


# ── Single source of truth (legacy files eliminated) ──────────


def test_state_is_persisted_in_single_state_file(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_feature(Feature(id="F-1", category="backend", description="desc"))
    repo.append_event(type="feature_created", payload={"feature_id": "F-1"})

    state_file = tmp_path / "state.json"
    assert state_file.exists()
    assert not (tmp_path / "features.json").exists()
    assert not (tmp_path / "tasks.db").exists()

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(data["features"]) == 1
    assert len(data["events"]) == 1


def test_event_id_monotonic_across_reloads(tmp_path):
    repo = _repo(tmp_path)
    ev1 = repo.append_event(type="a", payload={})
    ev2 = repo.append_event(type="b", payload={})
    assert ev1.event_id == 1
    assert ev2.event_id == 2

    reloaded = _repo(tmp_path)
    ev3 = reloaded.append_event(type="c", payload={})
    assert ev3.event_id == 3


def test_execution_history_filters_by_feature_id(tmp_path):
    repo = _repo(tmp_path)
    repo.log_execution({"feature_id": "F-1", "agent_id": "a1", "status": "completed"})
    repo.log_execution({"feature_id": "F-2", "agent_id": "a2", "status": "failed"})

    all_items = repo.get_execution_history()
    f1_items = repo.get_execution_history(feature_id="F-1")
    assert len(all_items) == 2
    assert len(f1_items) == 1
    assert f1_items[0]["feature_id"] == "F-1"


# ── Deep copy isolation ──────────────────────────────────────


def test_upsert_feature_deep_copies(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature, event_type="feature_created")

    feature.status = "done"
    feature.description = "Modified"

    stored = repo.get_feature("F001")
    assert stored is not None
    assert stored.status == "pending"
    assert stored.description == "Test"


# ── Status change requires event ─────────────────────────────


def test_status_change_requires_event_type(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature)

    feature.status = "in_progress"
    with pytest.raises(ValueError, match="no event_type provided"):
        repo.upsert_feature(feature)


def test_status_change_with_event_type_succeeds(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature)
    feature.status = "in_progress"
    repo.upsert_feature(feature, event_type="feature_started")

    stored = repo.get_feature("F001")
    assert stored is not None
    assert stored.status == "in_progress"


# ── Disk atomicity ───────────────────────────────────────────


def test_no_temp_files_left_after_write(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature, event_type="feature_created")

    tmp_files = list(repo._base.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_disk_write_uses_atomic_replace(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature, event_type="feature_created")

    state_file = repo._base / "state.json"
    assert state_file.exists()

    with open(state_file) as f:
        data = json.load(f)
    assert len(data["features"]) == 1
    assert data["features"][0]["id"] == "F001"


# ── Workspace isolation ──────────────────────────────────────


def test_workspace_isolation_enforced_for_agents(repo: ProjectStateRepository) -> None:
    agent = AgentInstance(
        id="backend-1", role="backend", instance_number=1,
        workspace_id="ws-1", status="idle",
    )
    repo.upsert_agent(agent)

    agent2 = AgentInstance(
        id="backend-1", role="backend", instance_number=1,
        workspace_id="ws-2", status="busy",
    )
    with pytest.raises(ValueError, match="workspace"):
        repo.upsert_agent(agent2)


def test_workspace_isolation_enforced_for_features(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature)

    feature2 = Feature(
        id="F001", category="test", description="Test v2", status="in_progress",
        priority="P1", dependencies=[], workspace_id="ws-2",
    )
    with pytest.raises(ValueError, match="workspace"):
        repo.upsert_feature(feature2, event_type="feature_started")


# ── Single source of truth: memory == disk ───────────────────


def test_memory_and_disk_consistent_after_write(repo: ProjectStateRepository) -> None:
    feature = Feature(
        id="F001", category="test", description="Test", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(feature, event_type="feature_created")

    mem = repo.get_feature("F001")
    assert mem is not None

    snapshot = repo.load_snapshot()
    disk = next((f for f in snapshot.features if f.id == "F001"), None)
    assert disk is not None

    assert mem.status == disk.status
    assert mem.description == disk.description


# ── Blocking issue lifecycle ─────────────────────────────────


def test_blocking_issue_create_and_resolve(repo: ProjectStateRepository) -> None:
    issue = BlockingIssue(
        issue_id="", feature_id="F001", issue_type="missing_env",
        description="ANTHROPIC_API_KEY not set", resolved=False,
    )
    created = repo.create_blocking_issue(issue)
    assert created.issue_id is not None
    assert len(created.issue_id) > 0

    stored = repo.get_blocking_issue(created.issue_id)
    assert stored is not None
    assert stored.resolved is False

    result = repo.resolve_blocking_issue(created.issue_id, "已配置")
    assert result is True

    resolved = repo.get_blocking_issue(created.issue_id)
    assert resolved is not None
    assert resolved.resolved is True
    assert resolved.resolution == "已配置"


def test_resolve_nonexistent_issue_returns_false(repo: ProjectStateRepository) -> None:
    assert repo.resolve_blocking_issue("nonexistent", "ignored") is False


def test_create_issue_requires_fields(repo: ProjectStateRepository) -> None:
    with pytest.raises(ValueError, match="issue_type"):
        repo.create_blocking_issue(BlockingIssue(
            issue_id="", feature_id="F001", issue_type="",
            description="", resolved=False,
        ))
    with pytest.raises(ValueError, match="feature_id"):
        repo.create_blocking_issue(BlockingIssue(
            issue_id="", feature_id="", issue_type="missing_env",
            description="", resolved=False,
        ))


# ── Concurrent writes ────────────────────────────────────────


def test_concurrent_feature_writes(repo: ProjectStateRepository) -> None:
    errors: list[Exception] = []

    def write_feature(idx: int) -> None:
        try:
            f = Feature(
                id=f"F{idx:03d}", category="test", description=f"Feature {idx}",
                status="pending", priority=f"P{idx}",
                dependencies=[], workspace_id="ws-1",
            )
            repo.upsert_feature(f)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write_feature, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    snapshot = repo.load_snapshot()
    assert len(snapshot.features) == 20


def test_concurrent_event_appends(repo: ProjectStateRepository) -> None:
    errors: list[Exception] = []

    def append_event(idx: int) -> None:
        try:
            repo.append_event(type="test_event", payload={"idx": idx})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=append_event, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    events = repo.get_events_after(0)
    assert len(events) == 50


# ── State round-trip ─────────────────────────────────────────


def test_state_round_trip(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"

    repo1 = ProjectStateRepository(
        base_dir=data_dir, project_id="test-project", run_id="run-001",
    )
    feature = Feature(
        id="F001", category="test", description="Persist me", status="in_progress",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    repo1.upsert_feature(feature, event_type="feature_started")

    agent = AgentInstance(
        id="backend-1", role="backend", instance_number=1,
        workspace_id="ws-1", status="busy",
    )
    repo1.upsert_agent(agent)
    repo1.append_event(type="custom_event", payload={"msg": "hello"})

    repo2 = ProjectStateRepository(
        base_dir=data_dir, project_id="test-project", run_id="run-001",
    )
    snapshot = repo2.load_snapshot()

    assert len(snapshot.features) == 1
    assert snapshot.features[0].description == "Persist me"
    assert len(snapshot.agents) == 1
    assert snapshot.agents[0].role == "backend"

    events = repo2.get_events_after(0)
    assert len(events) >= 1


# ── Command idempotency ──────────────────────────────────────


def test_command_auto_generates_id(repo: ProjectStateRepository) -> None:
    cmd = Command(type="approve_decision", target_id="F001", payload={})
    saved = repo.save_command(cmd)
    assert saved.command_id is not None
    assert len(saved.command_id) > 0


def test_command_project_id_injected(repo: ProjectStateRepository) -> None:
    cmd = Command(type="approve_decision", target_id="F001", payload={})
    saved = repo.save_command(cmd)
    assert saved.project_id == "test-project"
    assert saved.run_id == "run-001"


# ── Feature dependency resolution ────────────────────────────


def test_get_next_ready_feature_respects_dependencies(repo: ProjectStateRepository) -> None:
    f1 = Feature(
        id="F001", category="test", description="Base", status="pending",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    f2 = Feature(
        id="F002", category="test", description="Dependent", status="pending",
        priority="P2", dependencies=["F001"], workspace_id="ws-1",
    )
    repo.upsert_feature(f1)
    repo.upsert_feature(f2)

    ready = repo.get_next_ready_feature()
    assert ready is not None
    assert ready.id == "F001"

    f1.status = "done"
    repo.upsert_feature(f1, event_type="feature_completed")

    ready = repo.get_next_ready_feature()
    assert ready is not None
    assert ready.id == "F002"


def test_all_features_done(repo: ProjectStateRepository) -> None:
    f1 = Feature(
        id="F001", category="test", description="A", status="done",
        priority="P1", dependencies=[], workspace_id="ws-1",
    )
    f2 = Feature(
        id="F002", category="test", description="B", status="done",
        priority="P2", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(f1)
    repo.upsert_feature(f2)
    assert repo.all_features_done() is True

    f3 = Feature(
        id="F003", category="test", description="C", status="pending",
        priority="P3", dependencies=[], workspace_id="ws-1",
    )
    repo.upsert_feature(f3)
    assert repo.all_features_done() is False
