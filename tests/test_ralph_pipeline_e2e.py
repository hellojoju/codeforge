"""Ralph 核心引擎端到端管道测试。

覆盖: Brainstorm → PRD → TaskDecomposer → MemoryArchiver
"""

from pathlib import Path

from ralph.brainstorm_manager import BrainstormManager
from ralph.prd_manager import PRDManager
from ralph.task_decomposer import TaskDecomposer
from ralph.memory_archiver import MemoryArchiver
from ralph.schema.brainstorm_record import ConfirmedFact, OpenAssumption, UserPath


def test_full_pipeline_brainstorm_to_workunits(tmp_path: Path):
    """端到端：需求共创 → PRD → 拆解 → 记忆归档。"""
    ralph_dir = tmp_path / ".ralph"

    # 1. Brainstorm
    bm = BrainstormManager(ralph_dir)
    record = bm.start_session("TestApp", "做一个 CLI todo 工具")
    record.confirmed_facts = [
        ConfirmedFact(topic="目标用户", fact="终端用户", source_quote="给开发者用"),
        ConfirmedFact(topic="核心功能", fact="add/list/delete todo", source_quote="增删查"),
        ConfirmedFact(topic="验收标准", fact="命令行可交互", source_quote="cli 能跑"),
    ]
    record.user_paths = [
        UserPath(name="main", steps=["todo add", "todo list", "todo delete"],
                 edge_cases=["empty list"]),
    ]
    record.open_assumptions = []
    bm._save(record)
    assert bm.is_complete(record)

    # 2. PRD
    pm = PRDManager(ralph_dir)
    prd = pm.generate_from_brainstorm(record.record_id, ralph_dir)
    assert prd.status == "draft"
    frozen = pm.freeze(prd.prd_id)
    assert frozen.status == "frozen"
    assert len(frozen.core_features) >= 1

    # 3. Task Decomposition
    td = TaskDecomposer(ralph_dir)
    units = td.decompose(prd)
    assert len(units) >= 1
    failures = td.validate_granularity(units)
    assert len(failures) == 0, f"Granularity failures: {failures}"

    # Verify DAG
    dag = td.build_dependency_dag(units)
    assert len(dag) == len(units)

    # 4. Memory
    ma = MemoryArchiver(ralph_dir)
    for u in units:
        ma.append_short_term({
            "work_id": u.work_id, "status": "ready", "title": u.title,
            "producer_role": u.producer_role, "reviewer_role": u.reviewer_role,
        })
    assert len(ma.get_short_term()) > 0
    status = ma.get_status()
    assert status["total_stored"] > 0
    assert status["short_term"]["count"] > 0

    # 5. Record a decision
    ma.record_decision("使用 Python CLI", "用户要求命令行工具", ["Go CLI", "Rust CLI"])
    assert len(ma.get_medium_term()) > 0

    # 6. Search
    results = ma.search("CLI")
    assert len(results) >= 1


def test_prd_enrichment_flow(tmp_path: Path):
    """PRD 丰富流程：生成 → LLM 增强 → 冻结。"""
    ralph_dir = tmp_path / ".ralph"

    bm = BrainstormManager(ralph_dir)
    record = bm.start_session("EnrichApp", "做一个天气查询 API")
    record.confirmed_facts = [
        ConfirmedFact(topic="目标用户", fact="移动开发者", source_quote="mobile dev"),
        ConfirmedFact(topic="核心功能", fact="REST API 返回天气", source_quote="weather api"),
        ConfirmedFact(topic="验收标准", fact="200 OK with JSON", source_quote="json response"),
    ]
    record.user_paths = [UserPath(name="query", steps=["GET /weather?city=shanghai"], edge_cases=["invalid city"])]
    record.open_assumptions = []
    bm._save(record)

    pm = PRDManager(ralph_dir)
    prd = pm.generate_from_brainstorm(record.record_id, ralph_dir)

    # Enrich with LLM response
    enriched = pm.enrich_with_llm(prd, {
        "background": "移动端天气查询需求",
        "product_positioning": "轻量级天气 API 服务",
        "core_workflow": "客户端发送城市名 → API 返回温度/湿度/天气描述",
        "risks": ["第三方天气数据源不可用", "API Key 泄露"],
        "non_functional": {"可用性": "99.9%", "响应时间": "<200ms"},
    })
    assert enriched.background == "移动端天气查询需求"
    assert len(enriched.risks) == 2

    frozen = pm.freeze(enriched.prd_id)
    assert frozen.is_frozen()

    # Decompose the enriched PRD
    td = TaskDecomposer(ralph_dir)
    units = td.decompose(frozen)
    assert len(units) >= 1
    assert all(u.acceptance_criteria for u in units)
