import pytest
from ralph.schema.brainstorm_record import (
    dict_to_brainstorm, migrate_v1_to_v2, BrainstormRecord,
    brainstorm_to_dict, ConfirmedFact, UserPath,
)


def create_v1_data():
    return {
        "record_id": "v1-test-001",
        "project_name": "旧项目",
        "round_number": 3,
        "user_message": "我想做一个任务管理系统",
        "confirmed_facts": [
            {"topic": "目标用户", "fact": "项目经理", "source_quote": "给项目经理用的", "recorded_at": "2026-01-01"},
            {"topic": "核心功能", "fact": "创建和分配任务", "source_quote": "需要能创建和分配任务", "recorded_at": "2026-01-01"},
        ],
        "open_assumptions": [],
        "user_paths": [{"name": "任务创建流程", "steps": ["点击创建", "填写信息", "保存"], "edge_cases": []}],
        "system_questions": ["还有什么功能？"],
        "created_at": "2026-01-01T00:00:00",
    }


def test_v1_migration_adds_schema_version():
    v1 = create_v1_data()
    result = migrate_v1_to_v2(v1)
    assert result["schema_version"] == "v2"
    assert result["version"] == 1


def test_v1_migration_creates_feature_tree():
    v1 = create_v1_data()
    result = migrate_v1_to_v2(v1)
    assert "feature_tree" in result
    assert result["feature_tree"]["root_id"] == "fn-root"
    nodes = result["feature_tree"]["nodes"]
    assert "fn-root" in nodes


def test_v1_migration_maps_facts_to_nodes():
    v1 = create_v1_data()
    record = dict_to_brainstorm(v1)
    assert len(record.feature_tree.nodes) >= 3  # root + 2 topics


def test_v1_migration_preserves_facts():
    v1 = create_v1_data()
    record = dict_to_brainstorm(v1)
    assert len(record.confirmed_facts) == 2


def test_v1_migration_default_phase():
    v1 = create_v1_data()
    result = migrate_v1_to_v2(v1)
    assert result["current_phase"] == "feature_decompose"


def test_v2_data_no_migration():
    v2_data = brainstorm_to_dict(BrainstormRecord(record_id="v2-test", project_name="新项目"))
    record = dict_to_brainstorm(v2_data)
    assert record.schema_version == "v2"
    assert record.current_phase == "product_def"


def test_completeness_v1_fallback():
    v1 = create_v1_data()
    record = dict_to_brainstorm(v1)
    score = record.completeness_score()
    assert isinstance(score, float)


def test_roundtrip_v2():
    record = BrainstormRecord(record_id="rt-test", project_name="往返测试")
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.record_id == "rt-test"
    assert restored.project_name == "往返测试"
    assert restored.version == 2
