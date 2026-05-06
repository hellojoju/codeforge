"""PMCoordinator 测试 — 调度编排、SchedulingDecision、集成。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph.concurrency_controller import ConcurrencyController
from ralph.pm_coordinator import PMCoordinator, SchedulingDecision


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    (d / ".ralph").mkdir()
    (d / ".ralph" / "state").mkdir(exist_ok=True)
    (d / ".ralph" / "work_units").mkdir(exist_ok=True)
    return d


class FakeEngine:
    """Minimal engine stand-in."""
    pass


class TestSchedulingDecision:
    """SchedulingDecision 数据结构。"""

    def test_dispatch_action(self) -> None:
        sd = SchedulingDecision(action="dispatch", work_id="wu-1", reason="ready")
        assert sd.action == "dispatch"
        assert sd.work_id == "wu-1"
        assert sd.reason == "ready"

    def test_wait_action(self) -> None:
        sd = SchedulingDecision(action="wait", reason="no work available")
        assert sd.action == "wait"
        assert sd.work_id == ""

    def test_blocked_action(self) -> None:
        sd = SchedulingDecision(
            action="blocked",
            reason="token budget exhausted",
            historical_context=[{"type": "budget", "remaining": 0}],
        )
        assert sd.action == "blocked"
        assert len(sd.historical_context) == 1

    def test_noop_action(self) -> None:
        sd = SchedulingDecision(action="noop", reason="idle")
        assert sd.action == "noop"

    def test_to_dict(self) -> None:
        sd = SchedulingDecision(action="dispatch", work_id="wu-1", reason="test")
        d = sd.to_dict()
        assert d == {
            "action": "dispatch",
            "work_id": "wu-1",
            "reason": "test",
            "historical_context": [],
            "timestamp": sd.timestamp,
        }

    def test_timestamp_auto_generated(self) -> None:
        sd1 = SchedulingDecision(action="noop")
        sd2 = SchedulingDecision(action="noop")
        assert sd1.timestamp != ""
        assert sd2.timestamp != ""


class TestPMCoordinator:
    """PMCoordinator 调度编排层。"""

    def test_init_defaults(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
        )
        assert pm._project_dir == project_dir
        assert pm._concurrency is not None
        assert isinstance(pm._concurrency, ConcurrencyController)

    def test_init_with_all_services(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
            memory_manager=None,
            retrieval_pipeline=None,
            knowledge_graph=None,
            issue_sync=None,
            max_concurrent=5,
        )
        assert pm._concurrency._max_concurrent == 5

    def test_init_custom_concurrency(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
            max_concurrent=10,
            daily_token_limit=5000,
        )
        assert pm._concurrency._max_concurrent == 10

    def test_get_status(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
        )
        status = pm.get_status()
        assert "concurrency" in status
        assert "active_work_units" in status
        assert status["concurrency"]["max_concurrent"] == 3

    def test_on_work_unit_status_change_no_sync(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
        )
        # Should not raise when issue_sync is None
        from ralph.schema.work_unit import WorkUnitStatus
        pm.on_work_unit_status_change("wu-1", WorkUnitStatus.ACCEPTED)

    def test_on_work_unit_status_change_no_issue_id(self, project_dir: Path) -> None:
        pm = PMCoordinator(
            project_dir=project_dir,
            engine=FakeEngine(),
        )
        from ralph.schema.work_unit import WorkUnitStatus
        # Empty issue_sync_id means no notification
        pm.on_work_unit_status_change("wu-1", WorkUnitStatus.ACCEPTED, issue_sync_id="")
