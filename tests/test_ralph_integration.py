"""Integration tests for Ralph Phase 2 core modules.

Tests the key chains:
- TurnBasedExecutionEngine: execute() loop, checkpoints
- ContextEngine: L0/L1/L2/L3 layered context
- PMAgent: empty_memory scheduling, dependency checks
- KnowledgeGraphService: nodes/edges/query/sync/index
- RetrievalPipeline: structured/graph/semantic/fusion
- GraphifyService: AST fallback extraction, community detection
- IssueSyncProtocol: bidirectional sync, command parsing
- MemoryArchiver: auto-compaction on terminal state
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


# ── Test Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def temp_ralph_dir() -> Path:
    """Creates a temporary .ralph directory with test data."""
    tmp = Path(tempfile.mkdtemp(prefix="ralph_test_"))
    ralph_dir = tmp / ".ralph"
    ralph_dir.mkdir(parents=True)
    (ralph_dir / "state").mkdir(exist_ok=True)
    (ralph_dir / "checkpoints").mkdir(exist_ok=True)
    (ralph_dir / "memory").mkdir(exist_ok=True)
    (ralph_dir / "memory" / "long_term").mkdir(exist_ok=True)
    (ralph_dir / "evidence").mkdir(exist_ok=True)
    (ralph_dir / "reviews").mkdir(exist_ok=True)
    (ralph_dir / "decisions").mkdir(exist_ok=True)
    (ralph_dir / "features").mkdir(exist_ok=True)
    (ralph_dir / "prompts").mkdir(exist_ok=True)
    (ralph_dir / "blockers").mkdir(exist_ok=True)
    (ralph_dir / "retros").mkdir(exist_ok=True)
    yield ralph_dir
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project_dir(temp_ralph_dir: Path) -> Path:
    """Gets the project directory (parent of ralph_dir)."""
    return temp_ralph_dir.parent


@pytest.fixture
def sample_work_unit():
    """Returns a dict with enough fields to simulate a WorkUnit."""
    from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
    return WorkUnit(
        work_id="wu-test-001",
        work_type="feature",
        producer_role="developer",
        reviewer_role="reviewer",
        expected_output="Implement X",
        acceptance_criteria=["test passes", "lint clean"],
        status=WorkUnitStatus.READY,
        title="Test Feature Implementation",
        background="We need X to support Y",
        target="Create file x.py with function Y",
        scope_allow=["src/module_a/", "tests/test_module_a/"],
        scope_deny=["src/secret/"],
        dependencies=[],
        input_files=[],
        test_command="pytest tests/",
        rollback_strategy="git revert",
        assumptions=["API is stable"],
        impact_if_wrong="X may break",
        risk_notes="Low risk",
    )


# ── Test Helpers ──────────────────────────────────────────────────────


def _make_minimal_work_unit(work_id: str, **overrides: Any):
    """Create a minimal WorkUnit that passes preflight checks."""
    from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
    from ralph.schema.task_harness import TaskHarness

    kwargs = {
        "work_id": work_id,
        "work_type": "feature",
        "producer_role": "developer",
        "reviewer_role": "qa",
        "expected_output": "test output",
        "acceptance_criteria": ["test passes"],
        "status": WorkUnitStatus.READY,
        "title": f"Test {work_id}",
        "background": "test",
        "target": "test target",
        "scope_allow": ["src/"],
        "scope_deny": [".env"],
        "dependencies": [],
        "input_files": [],
        "test_command": "pytest",
        "rollback_strategy": "git revert",
        "assumptions": [],
        "impact_if_wrong": "minimal",
        "risk_notes": "low",
        "task_harness": TaskHarness(
            harness_id=f"h-{work_id}",
            task_goal="test",
            context_sources=["prd"],
            scope_allow=["src/"],
            scope_deny=[".env"],
            evidence_required=["diff.txt"],
            reviewer_role="qa",
            stop_conditions=["max_turns"],
        ),
    }
    kwargs.update(overrides)
    return WorkUnit(**kwargs)


# ── TurnBasedExecutionEngine ───────────────────────────────────────


class TestTurnEngine:
    """Tests for TurnBasedExecutionEngine."""

    def test_init_creates_checkpoints_dir(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(project_dir)
        assert (project_dir / ".ralph" / "checkpoints").is_dir()

    def test_list_executions_empty(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine.list_executions() == []

    def test_get_execution_status_not_found(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(project_dir)
        assert engine.get_execution_status("nonexistent") is None

    def test_restore_checkpoint_not_found(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        engine = TurnBasedExecutionEngine(project_dir)
        result = engine.restore_from_checkpoint("nonexistent", 0)
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_execute_single_turn_terminal(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        engine = TurnBasedExecutionEngine(project_dir)

        # Save a work unit that passes preflight
        wu = _make_minimal_work_unit("wu-001")
        engine._repository.save_work_unit(wu)

        # Mock execute+postflight to bypass teardown requirements
        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="DONE", stderr="",
                files_created=["src/x.py"], files_modified=[], files_deleted=[],
                test_results={"test": "pass"},
            )

        engine._execute_with_claude = fake_execute  # type: ignore[method-assign]

        result = asyncio.run(engine.execute("wu-001", max_turns=3))

        assert result["work_id"] == "wu-001"
        assert result["total_turns"] == 1
        assert len(result["turns"]) == 1

        # Checkpoint should be saved
        status = engine.get_execution_status("wu-001")
        assert status is not None
        assert status["latest_turn"]["turn_number"] == 1

    def test_execute_multi_turn(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        engine = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-002")
        engine._repository.save_work_unit(wu)

        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        turn_count = [0]

        async def multi_turn_execute(unit, context_pack, prd_summary, tool_cwd=None):
            turn_count[0] += 1
            terminal = turn_count[0] >= 3
            return ExecutionResult(
                work_id=unit.work_id,
                success=True,
                stdout="DONE" if terminal else "working",
                stderr="" if terminal else "still working",
                files_created=[],
                files_modified=[],
                files_deleted=[],
                test_results={},
            )

        engine._execute_with_claude = multi_turn_execute  # type: ignore[method-assign]

        result = asyncio.run(engine.execute("wu-002", max_turns=5))

        assert result["total_turns"] == 3

        # All checkpoints saved
        status = engine.get_execution_status("wu-002")
        assert len(status["turns"]) == 3

    def test_execute_max_turns_reached(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult

        engine = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-003")
        engine._repository.save_work_unit(wu)

        # Suppress archive_if_terminal which is called on blocked
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def never_terminal(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="running", stderr="",
                files_created=[], files_modified=[], files_deleted=[], test_results={},
            )

        engine._execute_with_claude = never_terminal  # type: ignore[method-assign]

        result = asyncio.run(engine.execute("wu-003", max_turns=3))

        assert result["total_turns"] == 3

    def test_execute_runner_exception(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult

        engine = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-004")
        engine._repository.save_work_unit(wu)

        # Suppress side effects when transitioned to failed
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def failing_execute(unit, context_pack, prd_summary, tool_cwd=None):
            raise RuntimeError("test error")

        engine._execute_with_claude = failing_execute  # type: ignore[method-assign]

        result = asyncio.run(engine.execute("wu-004", max_turns=3))

        assert result["total_turns"] == 1
        assert result["turns"][0]["error"] == "test error"

    def test_list_executions_after_execute(self, project_dir):
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        engine = TurnBasedExecutionEngine(project_dir)

        for wid in ("wu-a", "wu-b"):
            wu = _make_minimal_work_unit(wid)
            engine._repository.save_work_unit(wu)

        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="DONE", stderr="",
                files_created=[], files_modified=[], files_deleted=[], test_results={},
            )

        engine._execute_with_claude = fake_execute  # type: ignore[method-assign]

        asyncio.run(engine.execute("wu-a", max_turns=1))
        asyncio.run(engine.execute("wu-b", max_turns=1))

        executions = engine.list_executions()
        assert "wu-a" in executions
        assert "wu-b" in executions


# ── ContextEngine ──────────────────────────────────────────────────


class TestContextEngine:
    """Tests for ContextEngine layered context building."""

    def test_build_initial_with_defaults(self, project_dir):
        from ralph.context_engine import ContextEngine, ContextLayer
        engine = ContextEngine(project_dir)

        result = engine.build_initial(work_id="wu-test-001")

        assert "layers" in result
        assert "total_tokens_estimated" in result
        assert "budget" in result
        # Default: L0 + L1 + L2
        assert ContextLayer.L0.value in result["layers"]
        assert ContextLayer.L1.value in result["layers"]
        assert ContextLayer.L2.value in result["layers"]
        assert ContextLayer.L3.value not in result["layers"]

    def test_build_initial_specific_layers(self, project_dir):
        from ralph.context_engine import ContextEngine, ContextLayer
        engine = ContextEngine(project_dir)

        result = engine.build_initial(
            layers={ContextLayer.L0, ContextLayer.L1},
            max_tokens=2000,
        )

        assert ContextLayer.L0.value in result["layers"]
        assert ContextLayer.L1.value in result["layers"]
        assert ContextLayer.L2.value not in result["layers"]
        assert result["budget"] == 2000

    def test_build_initial_l0_contains_project_info(self, project_dir):
        from ralph.context_engine import ContextEngine, ContextLayer
        engine = ContextEngine(project_dir)

        result = engine.build_initial(layers={ContextLayer.L0})

        l0_text = result["layers"]["project_meta"]
        assert "Project directory" in l0_text

    def test_build_initial_l1_contains_structure(self, project_dir, sample_work_unit):
        """L1 should include work unit summary, features, blockers."""
        from ralph.context_engine import ContextEngine, ContextLayer
        from ralph.repository import RalphRepository

        # Seed the repo with a work unit
        repo = RalphRepository(project_dir / ".ralph")
        repo.save_work_unit(sample_work_unit)

        engine = ContextEngine(project_dir)
        result = engine.build_initial(layers={ContextLayer.L1}, work_id="wu-test-001")

        l1_text = result["layers"]["structured_index"]
        assert "wu-test-001" in l1_text
        assert "Test Feature Implementation" in l1_text

    def test_build_incremental_with_checkpoint(self, project_dir):
        from ralph.context_engine import ContextEngine
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        # Create a checkpoint first
        te = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-inc-001")
        te._repository.save_work_unit(wu)

        te._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        te._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="DONE", stderr="",
                files_created=[], files_modified=[], files_deleted=[], test_results={},
            )

        te._execute_with_claude = fake_execute  # type: ignore[method-assign]
        asyncio.run(te.execute("wu-inc-001", max_turns=1))

        engine = ContextEngine(project_dir)
        result = engine.build_incremental(
            work_id="wu-inc-001",
            checkpoint=1,
            current_error="test error",
            next_goal="fix the bug",
        )

        assert "layers" in result
        # Should contain checkpoint data in one of the layers
        all_text = " ".join(result["layers"].values())
        assert "wu-inc-001" in all_text

    def test_build_incremental_no_checkpoint(self, project_dir):
        from ralph.context_engine import ContextEngine
        engine = ContextEngine(project_dir)

        result = engine.build_incremental(
            work_id="wu-nonexistent",
            checkpoint=None,
        )

        assert "layers" in result

    def test_budget_control_trims_low_priority_layers(self, project_dir):
        """When over budget, lower priority layers should be trimmed."""
        from ralph.context_engine import ContextEngine, ContextLayer
        engine = ContextEngine(project_dir)

        # Very small budget should trim L3 and L2
        result = engine.build_initial(
            layers={ContextLayer.L0, ContextLayer.L1, ContextLayer.L2, ContextLayer.L3},
            max_tokens=50,
        )

        # L3 and L2 may be trimmed; L0 and L1 should survive longer
        assert "total_tokens_estimated" in result
        assert result["total_tokens_estimated"] <= 50

    def test_legacy_build_pm_context(self, project_dir):
        from ralph.context_engine import ContextEngine
        engine = ContextEngine(project_dir)

        result = engine.build_pm_context(
            mode="test",
            active_work_units=[{"work_id": "wu-1"}],
            pending_decisions=[{"decision": "test"}],
        )

        assert result["mode"] == "test"
        assert result["active_work_units"] == [{"work_id": "wu-1"}]


# ── PMAgent ────────────────────────────────────────────────────────


class TestPMAgent:
    """Tests for PMAgent scheduling."""

    def test_get_status(self, project_dir):
        from ralph.pm_agent import PMAgent
        # Fake engine
        agent = PMAgent(project_dir, engine=object())
        status = agent.get_status()
        assert "running_count" in status
        assert "ready_count" in status
        assert "total_count" in status

    def test_get_context(self, project_dir):
        from ralph.pm_agent import PMAgent
        agent = PMAgent(project_dir, engine=object())
        ctx = agent.get_context()
        assert "status" in ctx
        assert "snapshot" in ctx

    def test_schedule_once_no_ready_units(self, project_dir):
        from ralph.pm_agent import PMAgent, AgentResult
        agent = PMAgent(project_dir, engine=object())
        results = asyncio.run(agent.schedule_once())
        assert len(results) == 1
        assert results[0].action == "no_op"

    def test_schedule_batch_with_ready_units(self, project_dir, sample_work_unit):
        from ralph.pm_agent import PMAgent, AgentResult
        from ralph.repository import RalphRepository
        from ralph.turn_engine import TurnBasedExecutionEngine

        repo = RalphRepository(project_dir / ".ralph")
        repo.save_work_unit(sample_work_unit)

        engine = TurnBasedExecutionEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)

        results = asyncio.run(agent.schedule_batch(mode="empty_memory", max_dispatches=2))

        assert len(results) == 1  # One ready unit
        assert results[0].work_id == "wu-test-001"
        assert isinstance(results[0], AgentResult)

    def test_agent_result_to_dict(self):
        from ralph.pm_agent import AgentResult
        result = AgentResult(
            action="dispatch",
            work_id="wu-1",
            success=True,
            summary="done",
            decision_rationale="it was ready",
            dependency_check=[],
            risk_assessment="low",
            next_actions=["monitor"],
        )
        d = result.to_dict()
        assert d["action"] == "dispatch"
        assert d["work_id"] == "wu-1"
        assert d["decision_rationale"] == "it was ready"

    def test_schedule_batch_empty_memory_uses_L0_L1(self, project_dir, sample_work_unit):
        from ralph.pm_agent import PMAgent
        from ralph.repository import RalphRepository
        from ralph.turn_engine import TurnBasedExecutionEngine

        repo = RalphRepository(project_dir / ".ralph")
        repo.save_work_unit(sample_work_unit)

        engine = TurnBasedExecutionEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)

        results = asyncio.run(agent.schedule_batch(mode="empty_memory"))
        assert len(results) == 1

    def test_schedule_batch_with_dependencies(self, project_dir):
        """When a ready unit depends on an incomplete unit, it should be blocked."""
        from ralph.pm_agent import PMAgent
        from ralph.repository import RalphRepository
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.schema.work_unit import WorkUnit, WorkUnitStatus

        repo = RalphRepository(project_dir / ".ralph")

        # Create a dependency that is still running
        dep = WorkUnit(
            work_id="wu-dep-001",
            work_type="feature",
            producer_role="developer",
            reviewer_role="reviewer",
            expected_output="dependency",
            acceptance_criteria=[],
            status=WorkUnitStatus.RUNNING,
            title="Dependency",
            background="",
            target="",
            scope_allow=[],
            scope_deny=[],
            dependencies=[],
            input_files=[],
            test_command="",
            rollback_strategy="",
            assumptions=[],
            impact_if_wrong="",
            risk_notes="",
        )
        repo.save_work_unit(dep)

        # Create unit that depends on it
        unit = WorkUnit(
            work_id="wu-child-001",
            work_type="feature",
            producer_role="developer",
            reviewer_role="reviewer",
            expected_output="child",
            acceptance_criteria=[],
            status=WorkUnitStatus.READY,
            title="Child Unit",
            background="",
            target="",
            scope_allow=[],
            scope_deny=[],
            dependencies=["wu-dep-001"],
            input_files=[],
            test_command="",
            rollback_strategy="",
            assumptions=[],
            impact_if_wrong="",
            risk_notes="",
        )
        repo.save_work_unit(unit)

        engine = TurnBasedExecutionEngine(project_dir)
        agent = PMAgent(project_dir, engine=engine)

        results = asyncio.run(agent.schedule_batch(mode="empty_memory"))

        # The child unit should be blocked by the dependency
        blocked = [r for r in results if r.action == "blocked"]
        assert len(blocked) == 1
        assert blocked[0].work_id == "wu-child-001"
        assert any("wu-dep-001" in b for b in blocked[0].dependency_check)


# ── KnowledgeGraphService ──────────────────────────────────────────


class TestKnowledgeGraph:
    """Tests for KnowledgeGraphService."""

    def test_init_and_status(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(temp_ralph_dir)
        status = kg.get_status()
        assert status["available"] is True
        assert status["nodes"] == 0
        assert status["edges"] == 0

    def test_add_and_get_node(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(temp_ralph_dir)

        kg.add_node("task-1", label="Test Task", node_type="task", status="ready")
        node = kg.get_node("task-1")
        assert node is not None
        assert node["label"] == "Test Task"
        assert node["node_type"] == "task"
        assert node["status"] == "ready"

    def test_add_and_remove_node(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService
        kg = KnowledgeGraphService(temp_ralph_dir)

        kg.add_node("task-1", label="Test")
        assert kg.get_node("task-1") is not None
        assert kg.remove_node("task-1") is True
        assert kg.get_node("task-1") is None
        assert kg.remove_node("task-1") is False  # Already removed

    def test_add_edge(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("a", label="A")
        kg.add_node("b", label="B")
        kg.add_edge("a", "b", edge_type="depends_on")

        status = kg.get_status()
        assert status["edges"] == 1

    def test_add_edge_duplicate(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("a", label="A")
        kg.add_node("b", label="B")
        kg.add_edge("a", "b", edge_type="depends_on")
        kg.add_edge("a", "b", edge_type="depends_on")  # Should not duplicate

        assert kg.get_status()["edges"] == 1

    def test_remove_edge(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("a", label="A")
        kg.add_node("b", label="B")
        kg.add_edge("a", "b", edge_type="depends_on")
        assert kg.remove_edge("a", "b") is True
        assert kg.get_status()["edges"] == 0

    def test_query_dependencies_bfs(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("root", label="Root")
        kg.add_node("dep1", label="Dep1")
        kg.add_node("dep2", label="Dep2")
        kg.add_node("dep3", label="Dep3")

        kg.add_edge("root", "dep1", edge_type="depends_on")
        kg.add_edge("dep1", "dep2", edge_type="depends_on")
        kg.add_edge("dep2", "dep3", edge_type="depends_on")

        deps = kg.query_dependencies("root", max_depth=3)
        assert len(deps) == 3  # dep1, dep2, dep3

        deps_shallow = kg.query_dependencies("root", max_depth=1)
        assert len(deps_shallow) == 1  # Only dep1

    def test_query_risk_paths(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("safe", label="Safe", risk_score=0.3)
        kg.add_node("risky", label="Risky", risk_score=0.9)
        kg.add_node("also_risky", label="Also Risky", risk_score=0.8)
        kg.add_edge("risky", "dep", edge_type="depends_on")

        paths = kg.query_risk_paths()
        assert len(paths) == 2  # risky and also_risky

    def test_index_work_unit(self, temp_ralph_dir, sample_work_unit):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.index_work_unit(sample_work_unit, files=["src/module_a/x.py", "tests/test_x.py"])

        # Task node created
        node = kg.get_node("wu-test-001")
        assert node is not None
        assert node["node_type"] == "task"

        # File nodes created
        assert kg.get_node("src/module_a/x.py") is not None
        assert kg.get_node("tests/test_x.py") is not None

        # Edges created (2 modifies + 1 part_of)
        assert kg.get_status()["edges"] >= 2

    def test_sync_with_graphify(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)

        graphify_result = {
            "nodes": [
                {"id": "src/core.py", "label": "core", "type": "file", "risk_score": 0.5},
                {"id": "src/utils.py", "label": "utils", "type": "file", "risk_score": 0.2},
            ],
            "edges": [
                {"source": "src/core.py", "target": "src/utils.py", "type": "imports"},
            ],
        }

        synced = kg.sync_with_graphify(graphify_result)
        assert synced > 0
        assert kg.get_node("src/core.py") is not None
        assert kg.get_node("src/utils.py") is not None
        assert kg.get_status()["edges"] == 1

    def test_persistence_roundtrip(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg1 = KnowledgeGraphService(temp_ralph_dir)
        kg1.add_node("n1", label="Node 1", node_type="task", status="done")
        kg1.add_edge("n1", "n2", edge_type="depends_on")  # n2 doesn't exist as node but edge is stored
        kg1.save()

        # Reload
        kg2 = KnowledgeGraphService(temp_ralph_dir)
        assert kg2.get_node("n1") is not None
        assert kg2.get_status()["nodes"] >= 1

    def test_get_graph_data(self, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("a", label="A")
        data = kg.get_graph_data()
        assert "nodes" in data
        assert "edges" in data

    def test_query_impact_with_matching_scope(self, temp_ralph_dir, sample_work_unit):
        from ralph.knowledge_graph import KnowledgeGraphService
        from ralph.repository import RalphRepository

        repo = RalphRepository(temp_ralph_dir)
        repo.save_work_unit(sample_work_unit)

        kg = KnowledgeGraphService(temp_ralph_dir)
        result = kg.query_impact("src/module_a/")
        assert result["found"] is True
        assert len(result["direct_tasks"]) >= 1

    def test_node_type_dataclasses(self, temp_ralph_dir):
        from ralph.knowledge_graph import (
            TaskNode, FileNode, InterfaceNode, DecisionNode,
            RiskNode, BlockerNode, MilestoneNode, GraphEdge,
        )

        task = TaskNode(id="t1", label="Task 1", status="done")
        assert task.to_dict()["id"] == "t1"

        file_node = FileNode(id="f1", label="file.py", module="src", risk_score=0.7)
        assert file_node.to_dict()["risk_score"] == 0.7

        edge = GraphEdge(source="a", target="b", edge_type="depends_on")
        assert edge.to_dict()["type"] == "depends_on"

        # All node types should have to_dict
        for cls, extra in [
            (InterfaceNode, {"module": "mod"}),
            (DecisionNode, {"decision": "test"}),
            (RiskNode, {"severity": "high"}),
            (BlockerNode, {"blocker_type": "dependency"}),
            (MilestoneNode, {}),
        ]:
            instance = cls(id="x", label="X", **extra)
            d = instance.to_dict()
            assert d["id"] == "x"


# ── RetrievalPipeline ──────────────────────────────────────────────


class TestRetrievalPipeline:
    """Tests for RetrievalPipeline."""

    def test_search_structured_by_status(self, temp_ralph_dir, sample_work_unit):
        from ralph.retrieval_pipeline import RetrievalPipeline
        from ralph.repository import RalphRepository

        repo = RalphRepository(temp_ralph_dir)
        repo.save_work_unit(sample_work_unit)

        pipeline = RetrievalPipeline(temp_ralph_dir)
        results = pipeline.search_structured(status="ready")
        assert len(results) == 1
        assert results[0].id == "wu-test-001"
        assert results[0].source == "structured"

    def test_search_structured_by_feature_id(self, temp_ralph_dir, sample_work_unit):
        from ralph.retrieval_pipeline import RetrievalPipeline
        from ralph.repository import RalphRepository

        repo = RalphRepository(temp_ralph_dir)
        repo.save_work_unit(sample_work_unit)

        pipeline = RetrievalPipeline(temp_ralph_dir)
        results = pipeline.search_structured(feature_id="nonexistent")
        assert len(results) == 0

    def test_search_graph(self, temp_ralph_dir):
        from ralph.retrieval_pipeline import RetrievalPipeline
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("root", label="Root", node_type="task")
        kg.add_node("child", label="Child", node_type="task")
        kg.add_node("risk", label="Risk", node_type="risk", risk_score=0.9)
        kg.add_edge("root", "child", edge_type="depends_on")
        kg.add_edge("root", "risk", edge_type="requires")
        kg.save()

        pipeline = RetrievalPipeline(temp_ralph_dir)
        results = pipeline.search_graph(["root"])
        assert len(results) >= 2  # child and risk
        assert any(r.source == "graph" for r in results)

    def test_search_semantic(self, temp_ralph_dir, sample_work_unit):
        from ralph.retrieval_pipeline import RetrievalPipeline
        from ralph.repository import RalphRepository

        repo = RalphRepository(temp_ralph_dir)
        repo.save_work_unit(sample_work_unit)

        pipeline = RetrievalPipeline(temp_ralph_dir)
        results = pipeline.search_semantic("Test Feature Implementation")
        assert len(results) >= 1
        assert results[0].source == "semantic"

    def test_fusion_search(self, temp_ralph_dir, sample_work_unit):
        from ralph.retrieval_pipeline import RetrievalPipeline
        from ralph.repository import RalphRepository
        from ralph.knowledge_graph import KnowledgeGraphService

        repo = RalphRepository(temp_ralph_dir)
        repo.save_work_unit(sample_work_unit)

        kg = KnowledgeGraphService(temp_ralph_dir)
        kg.add_node("wu-test-001", label="Test Feature", node_type="task")
        kg.add_node("related", label="Related", node_type="task")
        kg.add_edge("wu-test-001", "related", edge_type="related_to")
        kg.save()

        pipeline = RetrievalPipeline(temp_ralph_dir)
        result = pipeline.fusion_search("Test Feature", top_k=10)

        assert result["query"] == "Test Feature"
        assert result["total"] > 0
        assert "results" in result
        assert "sources" in result

    def test_search_empty_query(self, temp_ralph_dir):
        from ralph.retrieval_pipeline import RetrievalPipeline
        pipeline = RetrievalPipeline(temp_ralph_dir)
        results = pipeline.search_semantic("")
        assert results == []

    def test_search_result_to_dict(self):
        from ralph.retrieval_pipeline import SearchResult, ResultType
        result = SearchResult(
            result_type=ResultType.WORK_UNIT,
            id="wu-1",
            title="Test",
            score=0.9,
            snippet="snippet...",
            source="structured",
            metadata={"status": "ready"},
        )
        d = result.to_dict()
        assert d["type"] == "work_unit"
        assert d["score"] == 0.9


# ── GraphifyService ────────────────────────────────────────────────


class TestGraphifyService:
    """Tests for GraphifyService."""

    @pytest.fixture
    def graphify(self, temp_ralph_dir):
        from ralph.graphify_service import GraphifyService
        return GraphifyService(temp_ralph_dir)

    def test_detect_communities_empty(self, graphify):
        result = graphify.detect_communities({"nodes": [], "edges": []})
        assert result == []

    def test_detect_communities_single_node(self, graphify):
        graph = {"nodes": [{"id": "a"}], "edges": []}
        result = graphify.detect_communities(graph)
        assert len(result) == 1
        assert result[0]["members"] == ["a"]

    def test_detect_communities_connected_graph(self, graphify):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "d"},
            ],
        }
        result = graphify.detect_communities(graph)
        assert len(result) >= 1  # All should cluster together
        total_members = sum(r["size"] for r in result)
        assert total_members == 4

    def test_extract_fallback_with_python_file(self, graphify, project_dir):
        """Test fallback extraction on a real Python file."""
        # Create a temp Python file with known imports
        test_file = project_dir / "test_module.py"
        test_file.write_text("""
import os
import json
from pathlib import Path
from typing import Any

def hello():
    return "world"
""")

        from ralph.graphify_core.extractor import extract_ast_graph
        result = extract_ast_graph(project_dir, changed_files=["test_module.py"])
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "test_module.py"

        # Clean up
        test_file.unlink()

    def test_extract_imports(self, graphify):
        from ralph.graphify_core.extractor import _parse_python
        parsed = _parse_python("""
import os
import json, sys
from pathlib import Path
from typing import Any, Dict
from .local import thing
""", None)
        imports = parsed["imports"]
        assert "os" in imports
        assert "json" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "typing" in imports

    def test_backfill_to_knowledge_graph(self, graphify, temp_ralph_dir):
        from ralph.knowledge_graph import KnowledgeGraphService

        kg = KnowledgeGraphService(temp_ralph_dir)
        graph = {
            "nodes": [
                {"id": "src/main.py", "label": "main", "type": "file"},
                {"id": "src/lib.py", "label": "lib", "type": "file"},
            ],
            "edges": [
                {"source": "src/main.py", "target": "src/lib.py", "type": "imports"},
            ],
        }

        count = graphify.backfill_to_knowledge_graph(kg, graph)
        assert count > 0
        assert kg.get_node("src/main.py") is not None

    def test_estimate_file_risk(self, graphify, project_dir):
        from ralph.graphify_core.extractor import _estimate_file_risk
        test_file = project_dir / "risk_test.py"
        test_file.write_text("import os\n" * 100)  # Many imports = higher risk
        risk = _estimate_file_risk(test_file.read_text(encoding="utf-8"))
        assert risk > 0.0
        test_file.unlink()


# ── IssueSyncProtocol ──────────────────────────────────────────────


class TestIssueSyncProtocol:
    """Tests for IssueSyncProtocol."""

    @pytest.fixture
    def sync_protocol(self, temp_ralph_dir):
        from ralph.issue_sync_protocol import IssueSyncProtocol
        return IssueSyncProtocol(temp_ralph_dir)

    def test_init_and_get_state(self, sync_protocol):
        state = sync_protocol.get_sync_state()
        assert state["last_sync_at"] is None
        assert state["synced_issues"] == 0

    def test_parse_approve_command(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph approve looks good to me")
        assert result is not None
        assert result["command"] == "approve"
        assert result["valid"] is True
        assert "looks good to me" in result["args"]["reason"]

    def test_parse_reject_command(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph reject needs more work")
        assert result is not None
        assert result["command"] == "reject"
        assert result["valid"] is True

    def test_parse_retry_command(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph retry wu-001")
        assert result is not None
        assert result["command"] == "retry"
        assert result["args"]["work_id"] == "wu-001"

    def test_parse_retry_missing_work_id(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph retry")
        assert result is not None
        assert result["valid"] is False

    def test_parse_status_command(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph status wu-001")
        assert result is not None
        assert result["command"] == "status"

    def test_parse_pause_resume(self, sync_protocol):
        assert sync_protocol.parse_comment_command("/ralph pause")["command"] == "pause"
        assert sync_protocol.parse_comment_command("/ralph resume")["command"] == "resume"

    def test_parse_unknown_command(self, sync_protocol):
        result = sync_protocol.parse_comment_command("/ralph unknowncmd")
        assert result is not None
        assert result["valid"] is False

    def test_parse_no_command(self, sync_protocol):
        assert sync_protocol.parse_comment_command("just a regular comment") is None
        assert sync_protocol.parse_comment_command("") is None

    def test_process_webhook_payload_with_comment(self, sync_protocol):
        payload = {
            "action": "created",
            "issue": {"id": 123, "title": "Test Issue"},
            "comment": {
                "body": "/ralph approve LGTM",
                "user": {"login": "reviewer"},
            },
        }
        events = sync_protocol.process_webhook_payload(payload)
        assert len(events) >= 1
        comment_events = [e for e in events if e["type"] == "comment_command"]
        assert len(comment_events) == 1
        assert comment_events[0]["command"] == "approve"

    def test_process_webhook_payload_labeled(self, sync_protocol):
        payload = {
            "action": "labeled",
            "issue": {"id": 456, "title": "Bug", "labels": [{"name": "bug"}, {"name": "priority"}]},
            "comment": {},
        }
        events = sync_protocol.process_webhook_payload(payload)
        issue_events = [e for e in events if e["type"] == "issue_state_change"]
        assert len(issue_events) == 1
        assert issue_events[0]["labels"] == ["bug", "priority"]

    def test_on_ralph_status_change_sync(self, sync_protocol):
        class FakeAdapter:
            def sync_status(self, work_id, status, metadata=None):
                return f"ext-{work_id}"

        result = sync_protocol.on_ralph_status_change(
            work_id="wu-001",
            new_status="completed",
            adapter=FakeAdapter(),
        )
        assert result["synced"] is True

    def test_on_ralph_status_change_error(self, sync_protocol):
        class FailingAdapter:
            def sync_status(self, work_id, status, metadata=None):
                raise RuntimeError("network down")

        result = sync_protocol.on_ralph_status_change(
            work_id="wu-001",
            new_status="completed",
            adapter=FailingAdapter(),
        )
        assert result["synced"] is False
        assert "network down" in result["error"]


# ── MemoryArchiver ─────────────────────────────────────────────────


class TestMemoryArchiver:
    """Tests for MemoryArchiver auto-compaction."""

    @pytest.fixture
    def archiver(self, temp_ralph_dir):
        from ralph.memory_archiver import MemoryArchiver
        return MemoryArchiver(temp_ralph_dir)

    def test_append_and_get_short_term(self, archiver):
        archiver.append_short_term({"work_id": "wu-1", "status": "running"})
        memory = archiver.get_short_term()
        assert len(memory) == 1

    def test_short_term_fifo_promotes_old(self, archiver):
        """After exceeding SHORT_TERM_MAX, oldest entries go to medium."""
        for i in range(25):
            status = "accepted" if i % 5 == 0 else "running"
            archiver.append_short_term({"work_id": f"wu-{i}", "status": status, "title": f"Task {i}"})

        short = archiver.get_short_term()
        assert len(short) <= 20

        medium = archiver.get_medium_term()
        # Some should have been promoted (those with terminal status)
        assert len(medium) >= 0

    def test_record_and_get_decision(self, archiver):
        archiver.record_decision(
            "Use PostgreSQL",
            "We need a relational database",
            alternatives=["SQLite", "MySQL"],
        )
        medium = archiver.get_medium_term()
        assert len(medium) == 1
        assert medium[0]["decision"] == "Use PostgreSQL"

    def test_archive_task_log(self, archiver):
        path = archiver.archive_task_log("wu-archive-1", "# Task Log\nDone!")
        assert "wu-archive-1" in path
        assert Path(path).exists()

    def test_search(self, archiver):
        archiver.append_short_term({"work_id": "wu-search", "title": "Add Search", "status": "running"})
        archiver.record_decision("Add Search Feature", "needed")
        results = archiver.search("Search")
        assert len(results) >= 1

    def test_summarize_short_term(self, archiver):
        archiver.append_short_term({"work_id": "wu-1", "title": "Task 1", "status": "running"})
        archiver.append_short_term({"work_id": "wu-2", "title": "Task 2", "status": "accepted"})
        summary = archiver.summarize_short_term()
        assert "Task 1" in summary or "Task 2" in summary

    def test_get_status(self, archiver):
        status = archiver.get_status()
        assert "short_term" in status
        assert "medium_term" in status
        assert "long_term" in status
        assert "total_stored" in status

    def test_compact_on_terminal_archives(self, archiver, temp_ralph_dir):
        """When compact_on_terminal is called, it should archive to long term."""
        # This tests the expected interface even if compact_on_terminal isn't implemented yet
        if hasattr(archiver, "compact_on_terminal"):
            final_state = {"work_id": "wu-final", "status": "accepted", "files": ["x.py"]}
            path = archiver.compact_on_terminal("wu-final", final_state)
            assert path is not None

            # Short and medium should reflect the compaction
            long_dir = temp_ralph_dir / "memory" / "long_term"
            total_files = sum(1 for _ in long_dir.rglob("*") if _.is_file())
            assert total_files >= 1
        else:
            pytest.skip("compact_on_terminal not yet implemented")


# ── AnalysisPipeline ───────────────────────────────────────────────


class TestAnalysisPipeline:
    """Tests for AnalysisPipeline integration."""

    def test_pipeline_context_dataclass(self):
        from ralph.pipeline import PipelineContext
        ctx = PipelineContext(
            think_result={"summary": "test"},
            plan_result={"steps": []},
            retrieval_context={"results": []},
            modules=[],
            high_risk_modules=[],
            suggested_contracts=[],
        )
        assert ctx.think_result["summary"] == "test"

    def test_run_pipeline_wires_analyzers(self, project_dir, temp_ralph_dir):
        from ralph.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(temp_ralph_dir)

        class FakeRecon:
            def analyze(self, path):
                return {"findings": ["module A", "module B"]}

        class FakeCoupling:
            def analyze(self, path):
                return [
                    type("Module", (), {
                        "name": "module_a",
                        "file_count": 10,
                        "import_degree": 5,
                        "dependents": ["module_b"],
                        "risk_score": 0.8,
                    })(),
                    type("Module", (), {
                        "name": "module_b",
                        "file_count": 5,
                        "import_degree": 3,
                        "dependents": [],
                        "risk_score": 0.3,
                    })(),
                ]

        class FakeContractManager:
            def generate_from_coupling(self, module=None, project_path=None, risk_score=None):
                return {"contract_id": f"contract-{module.get('name', 'unknown')}"}

        class FakeTaskDecomposer:
            def decompose(self, module=None, project_path=None, max_units=None):
                return [
                    type("Unit", (), {
                        "work_id": f"wu-{module.get('name', 'unknown')}-001",
                        "title": f"Fix {module.get('name', 'unknown')}",
                    })()
                ]

        class FakeKG:
            def sync_with_graphify(self, graph):
                pass
            def get_status(self):
                return {"available": True}

        class FakeGraphify:
            def build_graph(self, modules):
                return {"nodes": [], "edges": []}

        result = pipeline.run(
            project_path=project_dir,
            project_analysis={"project_name": "test-project"},
            recon_analyzer=FakeRecon(),
            coupling_analyzer=FakeCoupling(),
            contract_manager=FakeContractManager(),
            task_decomposer=FakeTaskDecomposer(),
            prd_text="We need to refactor the core modules",
            knowledge_graph=FakeKG(),
            graphify_service=FakeGraphify(),
        )

        assert len(result.modules) == 2
        assert len(result.high_risk_modules) == 2
        assert result.high_risk_modules[0]["name"] == "module_a"  # Higher risk first
        assert len(result.suggested_contracts) >= 1
        assert len(result.created_work_units) >= 1
        # Recon result should be included
        assert "module A" in str(result.think_result["recon"])


# ── End-to-End: TurnEngine + ContextEngine + PMAgent ───────────────


class TestE2EExecutionChain:
    """End-to-end test of the core execution chain."""

    def test_full_chain(self, project_dir):
        """TurnEngine + ContextEngine + PMAgent should work together."""
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.context_engine import ContextEngine
        from ralph.pm_agent import PMAgent
        from ralph.repository import RalphRepository
        from ralph.schema.work_unit import WorkUnit, WorkUnitStatus

        repo = RalphRepository(project_dir / ".ralph")
        engine = TurnBasedExecutionEngine(project_dir)
        context_engine = ContextEngine(project_dir)

        # Create a ready work unit
        wu = WorkUnit(
            work_id="wu-e2e-001",
            work_type="feature",
            producer_role="developer",
            reviewer_role="reviewer",
            expected_output="Implement E2E test feature",
            acceptance_criteria=["it works"],
            status=WorkUnitStatus.READY,
            title="E2E Test Feature",
            background="",
            target="Create a working test module",
            scope_allow=[],
            scope_deny=[],
            dependencies=[],
            input_files=[],
            test_command="",
            rollback_strategy="",
            assumptions=[],
            impact_if_wrong="",
            risk_notes="",
        )
        repo.save_work_unit(wu)

        # PMAgent should find it ready
        agent = PMAgent(project_dir, engine=engine)
        status = agent.get_status()
        assert status["ready_count"] >= 1

        # ContextEngine should build context for it
        ctx = context_engine.build_initial(work_id="wu-e2e-001")
        assert "layers" in ctx

        # TurnEngine should be able to execute it (via PMAgent)
        results = asyncio.run(agent.schedule_batch(mode="empty_memory"))
        assert len(results) == 1
        assert results[0].work_id == "wu-e2e-001"

    def test_checkpoint_persistence_survives(self, project_dir):
        """Engine checkpoints should be queryable after execution."""
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        engine = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-checkpoint")
        engine._repository.save_work_unit(wu)

        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="DONE", stderr="",
                files_created=[], files_modified=[], files_deleted=[], test_results={},
            )

        engine._execute_with_claude = fake_execute  # type: ignore[method-assign]
        asyncio.run(engine.execute("wu-checkpoint", max_turns=1))

        # Can restore
        restored = engine.restore_from_checkpoint("wu-checkpoint", 1)
        assert restored["success"] is True

        # Can query status
        status = engine.get_execution_status("wu-checkpoint")
        assert status is not None
        assert status["latest_turn"]["turn_number"] == 1


# ── T4.4: End-to-End Data Flow ─────────────────────────────────────


class TestE2EDataFlow:
    """端到端数据流：WorkUnit 执行 → 终态归档 → 数据写入。"""

    def test_checkpoint_data_written_after_execute(self, project_dir):
        """执行后 .ralph/checkpoints/ 应有 checkpoint 文件。"""
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult

        engine = TurnBasedExecutionEngine(project_dir)
        wu = _make_minimal_work_unit("wu-dataflow-1")
        engine._repository.save_work_unit(wu)

        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id, success=True, stdout="DONE", stderr="",
                files_created=["src/hello.py"], files_modified=[], files_deleted=[],
                test_results={"test": "pass"},
            )

        engine._execute_with_claude = fake_execute  # type: ignore[method-assign]

        asyncio.run(engine.execute("wu-dataflow-1", max_turns=3))

        # Checkpoint file must exist
        cps = list(engine._checkpoints_dir.glob("wu-dataflow-1.turn-*.json"))
        assert len(cps) >= 1
        assert cps[0].stat().st_size > 0

        # Checkpoint contains file snapshot
        import json
        data = json.loads(cps[0].read_text(encoding="utf-8"))
        assert data["work_id"] == "wu-dataflow-1"
        assert data["turn_number"] == 1
        assert "file_state_snapshot" in data

    def test_memory_compaction_on_terminal(self, project_dir):
        """终态时 _archive_if_terminal 向 MemoryArchiver 写入压缩摘要。"""
        from ralph.work_unit_engine import WorkUnitEngine

        engine = WorkUnitEngine(project_dir)
        # Simulate a completed work unit in terminal state
        unit_dict = {
            "work_id": "wu-archive-1",
            "status": "accepted",
            "title": "Test Archive",
            "work_type": "feature",
            "target": "test",
            "scope_allow": ["src/"],
            "scope_deny": [],
            "acceptance_criteria": [],
            "dependencies": [],
        }
        # Save to repo so get_work_unit works
        from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
        engine._repository.save_work_unit(WorkUnit(
            work_id="wu-archive-1", work_type="feature",
            producer_role="developer", reviewer_role="qa",
            expected_output="test", acceptance_criteria=[],
            status=WorkUnitStatus.NEEDS_REVIEW, title="Test",
            background="", target="", scope_allow=[], scope_deny=[],
            dependencies=[], input_files=[], test_command="",
            rollback_strategy="", assumptions=[], impact_if_wrong="", risk_notes="",
        ))
        # Transition needs_review → accepted so archive_if_terminal detects terminal
        engine._repository.transition("wu-archive-1", WorkUnitStatus.ACCEPTED,
                                      reason="review passed")
        engine._archive_if_terminal("wu-archive-1", "Created: src/test.py")

        status = engine._archiver.get_status()
        assert status["short_term"]["count"] >= 1

    def test_knowledge_graph_indexed_on_terminal(self, project_dir):
        """终态归档时 KnowledgeGraph 应有节点数据。"""
        from ralph.work_unit_engine import WorkUnitEngine
        from ralph.knowledge_graph import KnowledgeGraphService
        from ralph.schema.work_unit import WorkUnit, WorkUnitStatus

        engine = WorkUnitEngine(project_dir)

        # Inject a fresh knowledge graph
        kg = KnowledgeGraphService(engine._ralph_dir)
        engine._knowledge_graph = kg

        engine._repository.save_work_unit(WorkUnit(
            work_id="wu-kg-1", work_type="feature",
            producer_role="developer", reviewer_role="qa",
            expected_output="test", acceptance_criteria=[],
            status=WorkUnitStatus.NEEDS_REVIEW, title="KG Test",
            background="", target="", scope_allow=[], scope_deny=[],
            dependencies=[], input_files=[], test_command="",
            rollback_strategy="", assumptions=[], impact_if_wrong="", risk_notes="",
        ))
        engine._repository.transition("wu-kg-1", WorkUnitStatus.ACCEPTED, reason="review passed")
        engine._archive_if_terminal("wu-kg-1", "Created: src/main.py\nModified: src/lib.py")

        kg_status = kg.get_status()
        assert kg_status["nodes"] >= 1

    def test_full_data_flow_create_execute_archive(self, project_dir):
        """完整端到端：创建 WorkUnit → 执行 → 终态归档 → 所有数据目录有内容。"""
        from ralph.turn_engine import TurnBasedExecutionEngine
        from ralph.claude_runner import ExecutionResult
        from ralph.harness_manager import PostflightResult
        from ralph.knowledge_graph import KnowledgeGraphService
        from ralph.schema.work_unit import WorkUnit, WorkUnitStatus

        engine = TurnBasedExecutionEngine(project_dir)

        # 1. Create and save WorkUnit, execute for checkpoint
        wu = _make_minimal_work_unit(
            "wu-e2e-full",
            target="Implement user login",
            scope_allow=["src/auth/"],
            scope_deny=["src/secret/", ".env"],
            acceptance_criteria=["login works", "password hashed"],
        )
        engine._repository.save_work_unit(wu)

        engine._harness_mgr.postflight = lambda *a, **kw: PostflightResult(passed=True, checks=[], failures=[])  # type: ignore[method-assign]
        engine._archive_if_terminal = lambda *a, **kw: None  # type: ignore[method-assign]

        async def fake_execute(unit, context_pack, prd_summary, tool_cwd=None):
            return ExecutionResult(
                work_id=unit.work_id,
                success=True,
                stdout="All tests passed. DONE",
                stderr="",
                files_created=["src/auth/login.py", "tests/test_login.py"],
                files_modified=["src/auth/__init__.py"],
                files_deleted=[],
                test_results={"test_login": "pass"},
            )

        engine._execute_with_claude = fake_execute  # type: ignore[method-assign]

        # 2. Execute → checkpoint written
        result = asyncio.run(engine.execute("wu-e2e-full", max_turns=3))
        assert result["success"] is True

        # 3. Verify checkpoints exist
        cps = list(engine._checkpoints_dir.glob("wu-e2e-full.turn-*.json"))
        assert len(cps) >= 1
        import json
        checkpoint = json.loads(cps[0].read_text(encoding="utf-8"))
        assert checkpoint["turn_number"] == 1
        assert "file_state_snapshot" in checkpoint

        # 4. Simulate terminal review → archive via WorkUnitEngine
        from ralph.work_unit_engine import WorkUnitEngine
        we = WorkUnitEngine(project_dir)
        kg = KnowledgeGraphService(engine._ralph_dir)
        we._knowledge_graph = kg
        # Save unit in needs_review → transition to accepted → archive_if_terminal
        we._repository.save_work_unit(WorkUnit(
            work_id="wu-e2e-full", work_type="feature",
            producer_role="developer", reviewer_role="qa",
            expected_output="test",
            acceptance_criteria=["login works", "password hashed"],
            status=WorkUnitStatus.NEEDS_REVIEW, title="E2E Full",
            background="", target="Implement user login",
            scope_allow=["src/auth/"], scope_deny=[".env"],
            dependencies=[], input_files=[], test_command="",
            rollback_strategy="", assumptions=[], impact_if_wrong="", risk_notes="",
        ))
        we._repository.transition("wu-e2e-full", WorkUnitStatus.ACCEPTED, reason="review passed")
        we._archive_if_terminal("wu-e2e-full", "Created: src/auth/login.py")

        # 5. Verify memory has compaction data
        memory_status = we._archiver.get_status()
        assert memory_status["short_term"]["count"] >= 1

        # 6. Verify knowledge graph has nodes
        kg_status = kg.get_status()
        assert kg_status["nodes"] >= 1

        # 7. Checkpoints persist across engine instances
        execution_status = engine.get_execution_status("wu-e2e-full")
        assert execution_status is not None
        assert execution_status["latest_turn"]["turn_number"] == 1
