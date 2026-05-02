"""PRDManager 单元测试。"""

from pathlib import Path

from ralph.prd_manager import PRDManager
from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import ConfirmedFact, UserPath
from ralph.schema.prd_document import PRDDocument


def test_generate_from_brainstorm(tmp_path: Path):
    ralph_dir = tmp_path / ".ralph"
    bm = BrainstormManager(ralph_dir)
    record = bm.start_session("TestProject", "做一个 todo app")
    record.confirmed_facts = [
        ConfirmedFact(topic="目标用户", fact="开发者", source_quote="dev"),
        ConfirmedFact(topic="核心功能", fact="增删改查 todo", source_quote="crud"),
        ConfirmedFact(topic="验收标准", fact="能跑通 CRUD", source_quote="works"),
    ]
    record.user_paths = [UserPath(name="main", steps=["add", "edit", "delete"], edge_cases=["empty list"])]
    record.open_assumptions = []
    bm._save(record)

    pm = PRDManager(ralph_dir)
    prd = pm.generate_from_brainstorm(record.record_id, ralph_dir)
    assert prd.project_name == "TestProject"
    assert len(prd.user_goals) >= 1
    assert len(prd.success_criteria) >= 1


def test_freeze_prd(tmp_path: Path):
    pm = PRDManager(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="test-prd", project_name="Test")
    pm._save(prd)

    frozen = pm.freeze("test-prd")
    assert frozen.status == "frozen"
    assert frozen.frozen_at != ""


def test_list_prds(tmp_path: Path):
    pm = PRDManager(tmp_path / ".ralph")
    pm._save(PRDDocument(prd_id="p1", project_name="P1"))
    pm._save(PRDDocument(prd_id="p2", project_name="P2"))
    assert len(pm.list_prds()) == 2


def test_to_markdown(tmp_path: Path):
    prd = PRDDocument(prd_id="test", project_name="TestApp")
    prd.background = "需要自动开发系统"
    prd.user_goals = ["自动化开发"]
    prd.core_features = [{"name": "auto dev", "description": "自动写代码"}]
    md = prd.to_markdown()
    assert "# TestApp PRD" in md
    assert "自动化开发" in md


def test_enrich_with_llm(tmp_path: Path):
    pm = PRDManager(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="test-enrich", project_name="Test")
    pm._save(prd)

    enriched = pm.enrich_with_llm(prd, {
        "background": "项目背景信息",
        "product_positioning": "产品定位描述",
        "risks": ["风险1", "风险2"],
    })
    assert enriched.background == "项目背景信息"
    assert enriched.product_positioning == "产品定位描述"
    assert len(enriched.risks) == 2
