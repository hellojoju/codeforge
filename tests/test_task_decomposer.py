"""TaskDecomposer 单元测试。"""

from pathlib import Path

from ralph.task_decomposer import TaskDecomposer
from ralph.schema.prd_document import PRDDocument
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
from ralph.schema.task_harness import TaskHarness, RetryPolicy, TimeoutPolicy


def _make_harness() -> TaskHarness:
    return TaskHarness(
        harness_id="h1", task_goal="test", context_sources=["src"],
        context_budget="8k", allowed_tools=["claude"], denied_tools=[],
        scope_allow=["src"], scope_deny=[],
        preflight_checks=[], checkpoints=[],
        validation_gates=[], evidence_required=["diff"],
        retry_policy=RetryPolicy(), rollback_strategy="git reset",
        timeout_policy=TimeoutPolicy(), stop_conditions=[], reviewer_role="architect",
    )


def test_decompose_from_prd(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="prd-test", project_name="TestApp", core_features=[
        {"name": "user auth api", "description": "实现用户注册和登录 API"},
        {"name": "todo frontend page", "description": "Todo 列表页面 UI 组件"},
    ])
    stories, units = td.decompose(prd)
    assert len(units) >= 2
    assert all(u.status.value == "draft" for u in units)
    assert all(u.task_harness is not None for u in units)


def test_validate_granularity_passes(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="prd-test", project_name="Test", core_features=[
        {"name": "f1", "description": "desc"},
    ])
    stories, units = td.decompose(prd)
    failures = td.validate_granularity(units)
    assert len(failures) == 0, f"Unexpected failures: {failures}"


def test_validate_granularity_fails_on_empty(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    harness = _make_harness()
    bad_unit = WorkUnit(
        work_id="wu-bad", work_type="development", title="Bad",
        target="", status=WorkUnitStatus.DRAFT,
        expected_output="", acceptance_criteria=[], scope_allow=[],
        scope_deny=[], dependencies=[],
        task_harness=harness, producer_role="backend",
        reviewer_role="architect", test_command="", rollback_strategy="",
    )
    failures = td.validate_granularity([bad_unit])
    assert len(failures) == 1
    assert len(failures[0]["issues"]) >= 2  # target empty + acceptance_criteria empty


def test_build_dependency_dag(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    harness = _make_harness()
    wu1 = WorkUnit(
        work_id="wu-1", work_type="development", title="DB Schema",
        target="schema", status=WorkUnitStatus.DRAFT,
        expected_output="", acceptance_criteria=["ok"], scope_allow=["db"], scope_deny=[],
        dependencies=[], task_harness=harness,
        producer_role="database", reviewer_role="architect",
        test_command="", rollback_strategy="",
    )
    wu2 = WorkUnit(
        work_id="wu-2", work_type="development", title="API",
        target="api", status=WorkUnitStatus.DRAFT,
        expected_output="", acceptance_criteria=["ok"], scope_allow=["api"], scope_deny=[],
        dependencies=["wu-1"], task_harness=harness,
        producer_role="backend", reviewer_role="architect",
        test_command="", rollback_strategy="",
    )
    dag = td.build_dependency_dag([wu1, wu2])
    assert "wu-1" in dag
    assert "wu-2" in dag["wu-1"]
