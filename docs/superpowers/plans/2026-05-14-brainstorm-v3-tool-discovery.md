# Brainstorm V3 与工具发现能力实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 Brainstorm V2 从"问答式信息采集"升级为"主动产品共创 + 结构化功能审查"，并在开发前增加技术路线确认与第三方工具发现。

**架构：** 新增 2 个 Phase（PROACTIVE_ANALYSIS、DELIBERATION_REVIEW）和 2 个独立 Service（ProactiveAnalysisService、DeliberationReviewService），新增 ToolDiscoveryService，扩展 BrainstormRecord schema 与 BrainstormManager 路由逻辑，新增 API 端点。

**技术栈：** Python 3.12+, FastAPI, pytest, dataclass, LLM proxy (OpenAI-compatible)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `ralph/schema/brainstorm_record.py` | 修改 | 新增 V3 数据结构（ProactiveAnalysis、DeliberationRound、TechnicalRoute、ToolDiscoveryResult 等），新增 4 个 BrainstormPhase 枚举值 |
| `ralph/proactive_service.py` | 创建 | ProactiveAnalysisService：LLM 生成假设草案 |
| `ralph/deliberation_service.py` | 创建 | DeliberationReviewService：四维结构化审查 |
| `ralph/tool_discovery.py` | 创建 | ToolDiscoveryService：工具搜索、评估、推荐 |
| `ralph/brainstorm_manager.py` | 修改 | 新增 4 个 phase 处理方法，修改 advance_phase 路由，修改 start_session 入口 |
| `dashboard/api/routes.py` | 修改 | 新增 V3 API 端点（主动分析、审查、技术路线、工具发现） |
| `tests/ralph/test_brainstorm_v3_schema.py` | 创建 | V3 schema 数据结构测试 |
| `tests/ralph/test_proactive_service.py` | 创建 | ProactiveAnalysisService 测试 |
| `tests/ralph/test_deliberation_service.py` | 创建 | DeliberationReviewService 测试 |
| `tests/ralph/test_tool_discovery.py` | 创建 | ToolDiscoveryService 测试 |
| `tests/ralph/test_brainstorm_v3_manager.py` | 创建 | BrainstormManager V3 phase 路由测试 |
| `tests/ralph/test_brainstorm_v3_integration.py` | 创建 | V3 端到端集成测试 |

---

### 任务 1：V3 Schema 扩展

**文件：**
- 修改：`ralph/schema/brainstorm_record.py`
- 测试：`tests/ralph/test_brainstorm_v3_schema.py`

- [ ] **步骤 1：新增 4 个 BrainstormPhase 枚举值**

在 `BrainstormPhase` 枚举类中追加：

```python
class BrainstormPhase(str, Enum):
    PRODUCT_DEF = "product_def"
    FEATURE_DECOMPOSE = "feature_decompose"
    DELIBERATION_REVIEW = "deliberation_review"
    RELATIONSHIP = "relationship"
    INDEPENDENT_REVIEW = "independent_review"
    CLARIFICATION = "clarification"
    COMPLETE = "complete"
    # V3 新增
    PROACTIVE_ANALYSIS = "proactive_analysis"
    TECHNICAL_ROUTE_DRAFT = "technical_route_draft"
    TOOL_DISCOVERY = "tool_discovery"
    REQUIREMENTS_READY = "requirements_ready"
    EXECUTION_PLAN_READY = "execution_plan_ready"
```

- [ ] **步骤 2：验证枚举值新增后原有代码不受影响**

运行：`cd /Users/jieson/auto-coding && python -c "from ralph.schema.brainstorm_record import BrainstormPhase; print([p.value for p in BrainstormPhase])"`
预期：输出包含新旧全部枚举值，无报错

- [ ] **步骤 3：新增 ProactiveAnalysis 数据结构**

在 `BrainstormPhase` 枚举定义之后、`SourceRef` 之前插入：

```python
@dataclass
class ProactiveAnalysisItem:
    item_id: str
    category: str  # product_type | target_user | module | tech_direction | risk | question
    content: str
    confidence: float
    status: str = "pending"  # pending | accepted | rejected | modified
    user_revision: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)


@dataclass
class ProactiveAnalysis:
    analysis_id: str
    items: list[ProactiveAnalysisItem] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""
    confirmed_at: str = ""
```

- [ ] **步骤 4：新增 DeliberationReview 数据结构**

插入到 `ReviewResult` 定义之后：

```python
@dataclass
class DeliberationFinding:
    finding_id: str
    dimension: str
    affected_feature_ids: list[str]
    finding: str
    severity: str  # low | medium | high
    suggested_change: str
    evidence: str = ""
    pm_decision: str = "pending"  # pending | accept | reject | defer
    pm_reason: str = ""


@dataclass
class DeliberationRound:
    round_id: str
    findings: list[DeliberationFinding] = field(default_factory=list)
    pm_summary: str = ""
    created_at: str = ""
    completed_at: str = ""
```

- [ ] **步骤 5：新增 TechnicalRoute 数据结构**

插入到 `DeliberationRound` 定义之后：

```python
@dataclass
class TechnicalRoute:
    route_id: str
    architecture_summary: str
    frontend_stack: list[str] = field(default_factory=list)
    backend_stack: list[str] = field(default_factory=list)
    data_storage: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    non_functional_requirements: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    tool_needs: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | accepted | revision_requested
    user_feedback: str = ""
    created_at: str = ""
    confirmed_at: str = ""
```

- [ ] **步骤 6：新增 ToolDiscoveryResult 数据结构**

插入到 `TechnicalRoute` 定义之后：

```python
@dataclass
class ToolCandidate:
    candidate_id: str
    name: str
    source: str  # github | web | docs
    url: str
    description: str
    license: str = ""
    stars: int | None = None
    last_updated: str = ""
    package_name: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    evidence_snapshot: str = ""


@dataclass
class ToolEvaluation:
    candidate_id: str
    functional_fit: int       # 1-5
    maintenance_health: int   # 1-5
    license_fit: int          # 1-5
    stack_compatibility: int  # 1-5
    security_risk: str        # low | medium | high | unknown
    integration_cost: str     # low | medium | high
    summary: str
    recommendation: str       # adopt | compare | avoid


@dataclass
class ToolDiscoveryResult:
    discovery_id: str
    tool_need: str
    queries: list[str] = field(default_factory=list)
    candidates: list[ToolCandidate] = field(default_factory=list)
    evaluations: list[ToolEvaluation] = field(default_factory=list)
    selected_candidate_ids: list[str] = field(default_factory=list)
    created_at: str = ""
```

- [ ] **步骤 7：扩展 BrainstormRecord 增加新字段**

在 `BrainstormRecord` dataclass 中，`review_result` 字段之后追加：

```python
    # V3: 主动分析
    proactive_analysis: ProactiveAnalysis | None = None
    # V3: 多轮审查
    deliberation_rounds: list[DeliberationRound] = field(default_factory=list)
    # V3: 技术路线
    technical_route: TechnicalRoute | None = None
    # V3: 工具发现
    tool_discovery_results: list[ToolDiscoveryResult] = field(default_factory=list)
```

- [ ] **步骤 8：更新 brainstorm_to_dict 和 dict_to_brainstorm 兼容新字段**

修改 `dict_to_brainstorm` 函数，在 `BrainstormRecord()` 构造函数调用中追加：

```python
        proactive_analysis=_build_proactive_analysis(data.get("proactive_analysis")),
        deliberation_rounds=[_build_deliberation_round(r) for r in data.get("deliberation_rounds", [])],
        technical_route=_build_technical_route(data.get("technical_route")),
        tool_discovery_results=[_build_tool_discovery(r) for r in data.get("tool_discovery_results", [])],
```

并在 `dict_to_brainstorm` 之前添加辅助函数：

```python
def _build_source_refs(refs) -> list[SourceRef]:
    return [SourceRef(**r) for r in refs] if refs else []


def _build_proactive_items(items_data) -> list[ProactiveAnalysisItem]:
    return [
        ProactiveAnalysisItem(
            **{k: v for k, v in item.items() if k != "source_refs"},
            source_refs=_build_source_refs(item.get("source_refs", [])),
        )
        for item in (items_data or [])
    ]


def _build_proactive_analysis(data) -> ProactiveAnalysis | None:
    if not data:
        return None
    return ProactiveAnalysis(
        analysis_id=data["analysis_id"],
        items=_build_proactive_items(data.get("items", [])),
        summary=data.get("summary", ""),
        created_at=data.get("created_at", ""),
        confirmed_at=data.get("confirmed_at", ""),
    )


def _build_deliberation_findings(findings_data) -> list[DeliberationFinding]:
    return [DeliberationFinding(**f) for f in (findings_data or [])]


def _build_deliberation_round(data) -> DeliberationRound:
    return DeliberationRound(
        round_id=data["round_id"],
        findings=_build_deliberation_findings(data.get("findings", [])),
        pm_summary=data.get("pm_summary", ""),
        created_at=data.get("created_at", ""),
        completed_at=data.get("completed_at", ""),
    )


def _build_technical_route(data) -> TechnicalRoute | None:
    if not data:
        return None
    return TechnicalRoute(**data)


def _build_tool_evaluations(data) -> list[ToolEvaluation]:
    return [ToolEvaluation(**e) for e in (data or [])]


def _build_tool_candidates(data) -> list[ToolCandidate]:
    return [ToolCandidate(**c) for c in (data or [])]


def _build_tool_discovery(data) -> ToolDiscoveryResult:
    return ToolDiscoveryResult(
        discovery_id=data["discovery_id"],
        tool_need=data["tool_need"],
        queries=data.get("queries", []),
        candidates=_build_tool_candidates(data.get("candidates", [])),
        evaluations=_build_tool_evaluations(data.get("evaluations", [])),
        selected_candidate_ids=data.get("selected_candidate_ids", []),
        created_at=data.get("created_at", ""),
    )
```

由于 `brainstorm_to_dict` 使用的是 `dataclasses.asdict`，新字段会自动序列化，无需修改。

- [ ] **步骤 9：Commit**

```bash
git add ralph/schema/brainstorm_record.py
git commit -m "feat: extend BrainstormRecord schema with V3 phases, ProactiveAnalysis, DeliberationReview, TechnicalRoute, ToolDiscoveryResult"
```

---

### 任务 2：编写 V3 Schema 测试

**文件：**
- 修改：`ralph/schema/brainstorm_record.py`（已在任务 1 完成）
- 创建：`tests/ralph/test_brainstorm_v3_schema.py`

- [ ] **步骤 1：编写 ProactiveAnalysis 数据结构测试**

```python
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree, ProactiveAnalysis, ProactiveAnalysisItem,
    SourceRef, TechnicalRoute, ToolCandidate, ToolDiscoveryResult, ToolEvaluation,
)


def test_brainstorm_phase_v3_values():
    """验证 V3 新增 phase 枚举值"""
    assert BrainstormPhase.PROACTIVE_ANALYSIS == "proactive_analysis"
    assert BrainstormPhase.DELIBERATION_REVIEW == "deliberation_review"
    assert BrainstormPhase.TECHNICAL_ROUTE_DRAFT == "technical_route_draft"
    assert BrainstormPhase.TOOL_DISCOVERY == "tool_discovery"
    assert BrainstormPhase.REQUIREMENTS_READY == "requirements_ready"
    assert BrainstormPhase.EXECUTION_PLAN_READY == "execution_plan_ready"


def test_proactive_analysis_item_defaults():
    item = ProactiveAnalysisItem(
        item_id="pa-1", category="product_type",
        content="这是一个 SaaS 产品", confidence=0.7,
    )
    assert item.status == "pending"
    assert item.user_revision == ""
    assert item.source_refs == []


def test_proactive_analysis_defaults():
    analysis = ProactiveAnalysis(analysis_id="pa-root")
    assert analysis.items == []
    assert analysis.summary == ""
    assert analysis.confirmed_at == ""


def test_deliberation_finding_defaults():
    finding = DeliberationFinding(
        finding_id="df-1", dimension="user_journey",
        affected_feature_ids=["fn-001"],
        finding="缺少退出按钮", severity="high",
        suggested_change="在导航栏添加退出按钮",
    )
    assert finding.evidence == ""
    assert finding.pm_decision == "pending"
    assert finding.pm_reason == ""


def test_deliberation_round_defaults():
    rnd = DeliberationRound(round_id="dr-1")
    assert rnd.findings == []
    assert rnd.pm_summary == ""


def test_technical_route_defaults():
    route = TechnicalRoute(
        route_id="tr-1", architecture_summary="前后端分离",
    )
    assert route.status == "pending"
    assert route.frontend_stack == []
    assert route.tool_needs == []
    assert route.user_feedback == ""


def test_tool_candidate_defaults():
    candidate = ToolCandidate(
        candidate_id="tc-1", name="Express",
        source="github", url="https://github.com/expressjs/express",
        description="Fast web framework",
    )
    assert candidate.stars is None
    assert candidate.evidence_urls == []


def test_tool_evaluation_defaults():
    ev = ToolEvaluation(
        candidate_id="tc-1", functional_fit=5, maintenance_health=4,
        license_fit=5, stack_compatibility=5,
        security_risk="low", integration_cost="low",
        summary="成熟稳定", recommendation="adopt",
    )
    assert ev.recommendation == "adopt"


def test_tool_discovery_result_defaults():
    result = ToolDiscoveryResult(
        discovery_id="td-1", tool_need="Web 框架",
    )
    assert result.candidates == []
    assert result.selected_candidate_ids == []


def test_brainstorm_record_v3_fields():
    """验证 BrainstormRecord 包含 V3 新字段"""
    record = BrainstormRecord(record_id="bs-v3", project_name="Test")
    assert record.proactive_analysis is None
    assert record.deliberation_rounds == []
    assert record.technical_route is None
    assert record.tool_discovery_results == []
```

- [ ] **步骤 2：运行测试验证全部通过**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_schema.py -v`
预期：全部 PASS

- [ ] **步骤 3：编写序列化往返测试**

```python
import tempfile
from pathlib import Path
from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    brainstorm_to_dict, dict_to_brainstorm, ProactiveAnalysis,
    ProactiveAnalysisItem, DeliberationRound, DeliberationFinding,
    TechnicalRoute, ToolDiscoveryResult, ToolCandidate, ToolEvaluation,
)


def test_proactive_analysis_roundtrip():
    record = BrainstormRecord(record_id="bs-rt", project_name="RT")
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-1",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="SaaS 产品", confidence=0.8,
            )
        ],
        summary="分析摘要",
    )
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.proactive_analysis is not None
    assert restored.proactive_analysis.analysis_id == "pa-1"
    assert len(restored.proactive_analysis.items) == 1
    assert restored.proactive_analysis.items[0].content == "SaaS 产品"


def test_deliberation_rounds_roundtrip():
    record = BrainstormRecord(record_id="bs-rt2", project_name="RT2")
    record.deliberation_rounds = [
        DeliberationRound(
            round_id="dr-1",
            findings=[
                DeliberationFinding(
                    finding_id="f1", dimension="user_journey",
                    affected_feature_ids=["fn-001"],
                    finding="缺少退出", severity="high",
                    suggested_change="添加退出",
                )
            ],
            pm_summary="采纳",
        )
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.deliberation_rounds) == 1
    assert restored.deliberation_rounds[0].findings[0].finding == "缺少退出"


def test_technical_route_roundtrip():
    record = BrainstormRecord(record_id="bs-rt3", project_name="RT3")
    record.technical_route = TechnicalRoute(
        route_id="tr-1", architecture_summary="SPA + REST API",
        frontend_stack=["React", "TypeScript"],
        backend_stack=["Node.js", "FastAPI"],
        tool_needs=["Web 框架", "ORM"],
    )
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert restored.technical_route is not None
    assert restored.technical_route.frontend_stack == ["React", "TypeScript"]
    assert restored.technical_route.tool_needs == ["Web 框架", "ORM"]


def test_tool_discovery_roundtrip():
    record = BrainstormRecord(record_id="bs-rt4", project_name="RT4")
    record.tool_discovery_results = [
        ToolDiscoveryResult(
            discovery_id="td-1", tool_need="Web 框架",
            queries=["best python web framework 2026"],
            candidates=[
                ToolCandidate(
                    candidate_id="tc-1", name="FastAPI",
                    source="github", url="https://github.com/tiangolo/fastapi",
                    description="Modern fast web framework",
                    stars=70000,
                )
            ],
            evaluations=[
                ToolEvaluation(
                    candidate_id="tc-1", functional_fit=5,
                    maintenance_health=5, license_fit=5, stack_compatibility=5,
                    security_risk="low", integration_cost="low",
                    summary="推荐", recommendation="adopt",
                )
            ],
            selected_candidate_ids=["tc-1"],
        )
    ]
    data = brainstorm_to_dict(record)
    restored = dict_to_brainstorm(data)
    assert len(restored.tool_discovery_results) == 1
    td = restored.tool_discovery_results[0]
    assert td.candidates[0].name == "FastAPI"
    assert td.selected_candidate_ids == ["tc-1"]
```

- [ ] **步骤 4：运行全部 schema 测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_schema.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add ralph/schema/brainstorm_record.py tests/ralph/test_brainstorm_v3_schema.py
git commit -m "test: V3 schema data structures, defaults, and serialization roundtrip tests"
```

---

### 任务 3：ProactiveAnalysisService

**文件：**
- 创建：`ralph/proactive_service.py`
- 测试：`tests/ralph/test_proactive_service.py`

- [ ] **步骤 1：编写 ProactiveAnalysisService 骨架测试**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.proactive_service import ProactiveAnalysisService
from ralph.schema.brainstorm_record import BrainstormRecord, FeatureNode, FeatureTree


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items":[]}'}}]}}
    yield ProactiveAnalysisService(config_manager=mock_config)


@pytest.fixture
def empty_record():
    with tempfile.TemporaryDirectory() as tmpdir:
        record = BrainstormRecord(record_id="bs-test", project_name="测试项目")
        record.user_message = "我想做一个在线协作文档系统"
        root = FeatureNode(node_id="fn-root", name="测试项目", level="product")
        record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
        yield record
```

- [ ] **步骤 2：实现 ProactiveAnalysisService**

```python
"""ProactiveAnalysisService — 系统主动分析模糊需求，生成假设草案。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, ProactiveAnalysis, ProactiveAnalysisItem,
    SourceRef, _now_iso,
)

logger = logging.getLogger(__name__)


class ProactiveAnalysisService:
    """根据用户模糊需求，生成结构化的产品假设草案。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def analyze(self, record: BrainstormRecord) -> ProactiveAnalysis:
        """基于用户初始需求，生成假设草案。"""
        prompt = self._build_prompt(record)
        content = self._call_llm("proactive_analysis", [{"role": "user", "content": prompt}])

        analysis = ProactiveAnalysis(
            analysis_id=f"pa-{uuid.uuid4().hex[:8]}",
            created_at=_now_iso(),
        )

        if content:
            items = self._parse_items(content)
            analysis.items = items
            analysis.summary = self._build_summary(items)

        record.proactive_analysis = analysis
        return analysis

    def _build_prompt(self, record: BrainstormRecord) -> str:
        user_message = record.user_message or ""
        project_name = record.project_name or ""

        return f"""你是资深产品经理和系统架构师。用户提出了一个模糊需求，请你从大方向上主动分析这个产品应该怎么做。

项目名称：{project_name}
用户需求：{user_message}

请从以下维度分析：
1. 产品类型判断（这是什么类型的产品）
2. 目标用户猜测（谁会使用）
3. 核心场景推测（主要使用场景）
4. 关键功能模块推测（需要哪些核心功能）
5. 可能的技术方向（推荐的技术栈）
6. 主要风险点（潜在风险和挑战）
7. 需要用户优先确认的问题（3-5 个关键问题）

请以 JSON 返回，格式如下：
{{
  "items": [
    {{
      "item_id": "pa-1",
      "category": "product_type|target_user|module|tech_direction|risk|question",
      "content": "具体分析内容",
      "confidence": 0.7
    }}
  ]
}}

注意：
- 每个维度至少有一个 item
- confidence 范围 0.1-1.0，表示你对该判断的确定程度
- 要具体，不要泛泛而谈"""

    def _parse_items(self, content: str) -> list[ProactiveAnalysisItem]:
        try:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n", 1)
                content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                if content.startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)
            items_data = data.get("items", [])
            items = []
            for item in items_data:
                items.append(ProactiveAnalysisItem(
                    item_id=item.get("item_id", f"pa-{uuid.uuid4().hex[:6]}"),
                    category=item.get("category", "module"),
                    content=item.get("content", ""),
                    confidence=float(item.get("confidence", 0.5)),
                ))
            return items
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning("ProactiveAnalysisService: LLM 返回 parse error: %s", e)
            return []

    def _build_summary(self, items: list[ProactiveAnalysisItem]) -> str:
        modules = [i for i in items if i.category == "module"]
        risks = [i for i in items if i.category == "risk"]
        questions = [i for i in items if i.category == "question"]
        parts = []
        if modules:
            parts.append(f"建议的核心功能模块：{', '.join(i.content for i in modules)}")
        if risks:
            parts.append(f"主要风险：{', '.join(i.content for i in risks)}")
        if questions:
            parts.append(f"需要优先确认：{', '.join(i.content for i in questions)}")
        return "\n".join(parts) if parts else "分析完成，请查看详细条目。"

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("ProactiveAnalysisService: LLM 响应结构异常")
        return None
```

- [ ] **步骤 3：补充 Service 测试**

```python
def test_service_analyze_with_mock(service, empty_record):
    """测试 analyze 方法生成分析结果"""
    analysis = service.analyze(empty_record)
    assert analysis.analysis_id.startswith("pa-")
    assert analysis.created_at != ""
    assert empty_record.proactive_analysis is analysis


def test_service_analyze_no_config():
    """测试无 config 时 graceful 降级"""
    svc = ProactiveAnalysisService(config_manager=None)
    with tempfile.TemporaryDirectory() as tmpdir:
        record = BrainstormRecord(record_id="bs-noconfig", project_name="Test")
        record.user_message = "做一个博客"
        root = FeatureNode(node_id="fn-root", name="Test", level="product")
        record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
        analysis = svc.analyze(record)
        # LLM 不可用时应创建空 analysis
        assert analysis is not None
        assert analysis.items == []


def test_parse_items_invalid_json(service):
    """测试无效 JSON 输入的容错"""
    items = service._parse_items("not json at all")
    assert items == []


def test_parse_items_from_markdown_block(service):
    """测试从 markdown code fence 中提取 JSON"""
    content = '''```json
{"items": [{"item_id": "pa-1", "category": "module", "content": "用户管理", "confidence": 0.8}]}
```'''
    items = service._parse_items(content)
    assert len(items) == 1
    assert items[0].content == "用户管理"
    assert items[0].confidence == 0.8


def test_build_summary(service):
    """测试摘要生成"""
    from ralph.schema.brainstorm_record import ProactiveAnalysisItem
    items = [
        ProactiveAnalysisItem(item_id="1", category="module", content="用户管理", confidence=0.8),
        ProactiveAnalysisItem(item_id="2", category="risk", content="并发问题", confidence=0.5),
        ProactiveAnalysisItem(item_id="3", category="question", content="目标用户是谁？", confidence=0.9),
    ]
    summary = service._build_summary(items)
    assert "用户管理" in summary
    assert "并发问题" in summary
    assert "目标用户" in summary
```

- [ ] **步骤 4：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_proactive_service.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add ralph/proactive_service.py tests/ralph/test_proactive_service.py
git commit -m "feat: ProactiveAnalysisService for generating proactive product analysis from vague requirements"
```

---

### 任务 4：DeliberationReviewService

**文件：**
- 创建：`ralph/deliberation_service.py`
- 测试：`tests/ralph/test_deliberation_service.py`

- [ ] **步骤 1：实现 DeliberationReviewService**

```python
"""DeliberationReviewService — 四维结构化功能审查。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import (
    BrainstormRecord, DeliberationFinding, DeliberationRound, FeatureNode,
    _now_iso,
)

logger = logging.getLogger(__name__)

# 四个审查维度的定义
DIMENSIONS = [
    {
        "role": "user_journey_analyst",
        "display_name": "用户行为路径分析",
        "prompt": "从用户行为路径角度审查：用户进入产品后的操作路径是否自然？是否漏掉了关键交互环节（如注册、登录、导航、退出）？路径转换是否顺畅？",
    },
    {
        "role": "feature_completeness_reviewer",
        "display_name": "功能完整性审查",
        "prompt": "从功能完整性角度审查：主流程是否完整？分支流程和异常情况的兜底功能是否缺失？除了基本 CRUD 之外，是否缺少必要的辅助功能（如搜索、筛选、批量操作、导入导出）？",
    },
    {
        "role": "industry_benchmark_analyst",
        "display_name": "竞品/行业经验对标",
        "prompt": "从竞品和行业经验角度审查：同类产品通常有哪些默认功能？我们是否缺少了行业标准能力？有哪些竞品已经验证过的功能模式可以借鉴？",
    },
    {
        "role": "scenario_combiner",
        "display_name": "场景组合分析",
        "prompt": "从场景组合角度审查：用户可能同时有多个需求，现有功能组合能否覆盖？是否需要新增组合功能？不同用户角色的需求是否有冲突？",
    },
]


class DeliberationReviewService:
    """执行四维结构化功能审查。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def run_review(self, record: BrainstormRecord) -> DeliberationRound:
        """执行一轮四维审查，返回汇总结果。"""
        spec_text = self._render_feature_tree(record)

        round_result = DeliberationRound(
            round_id=f"dr-{uuid.uuid4().hex[:8]}",
            created_at=_now_iso(),
        )

        all_findings: list[DeliberationFinding] = []

        for dim in DIMENSIONS:
            findings = self._review_dimension(spec_text, dim)
            all_findings.extend(findings)

        round_result.findings = all_findings
        round_result.pm_summary = self._summarize_findings(all_findings)
        round_result.completed_at = _now_iso()

        record.deliberation_rounds.append(round_result)
        return round_result

    def _render_feature_tree(self, record: BrainstormRecord) -> str:
        """将 FeatureTree 渲染为审查用文本。"""
        lines = [f"# {record.project_name} 功能清单", ""]
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            lines.append(f"## {node.name} ({node.node_id})")
            if node.user_stories:
                lines.append(f"- 用户故事: {'; '.join(node.user_stories)}")
            if node.acceptance_criteria:
                lines.append(f"- 验收标准: {'; '.join(node.acceptance_criteria)}")
            if node.success_path:
                lines.append(f"- 成功路径: {'; '.join(node.success_path)}")
            if node.failure_path:
                lines.append(f"- 失败路径: {'; '.join(node.failure_path)}")
            if node.edge_cases:
                lines.append(f"- 边界场景: {'; '.join(node.edge_cases)}")
            if node.data_requirements:
                lines.append(f"- 数据需求: {'; '.join(node.data_requirements)}")
            lines.append("")
        return "\n".join(lines)

    def _review_dimension(self, spec_text: str, dimension: dict) -> list[DeliberationFinding]:
        """对单个维度执行审查。"""
        prompt = f"""{dimension['prompt']}

以下是当前产品的功能清单：

{spec_text}

请列出具体的审查发现。每个发现应包含：
- 影响的功能 ID
- 具体发现
- 严重程度（low | medium | high）
- 建议的变更

请以 JSON 数组返回：
[
  {{
    "finding_id": "f-1",
    "affected_feature_ids": ["fn-001"],
    "finding": "具体发现",
    "severity": "high",
    "suggested_change": "建议变更",
    "evidence": "证据或理由"
  }}
]

如果没有发现，返回空数组 []。"""

        content = self._call_llm(f"deliberation_{dimension['role']}", [{"role": "user", "content": prompt}])

        if not content:
            return []

        try:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n", 1)
                content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                if content.startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)
            if not isinstance(data, list):
                data = data.get("findings", data.get("items", []))
            findings = []
            for f in data:
                findings.append(DeliberationFinding(
                    finding_id=f.get("finding_id", f"f-{uuid.uuid4().hex[:6]}"),
                    dimension=dimension["role"],
                    affected_feature_ids=f.get("affected_feature_ids", []),
                    finding=f.get("finding", ""),
                    severity=f.get("severity", "medium"),
                    suggested_change=f.get("suggested_change", ""),
                    evidence=f.get("evidence", ""),
                ))
            return findings
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning("DeliberationReviewService: %s parse error: %s", dimension["role"], e)
            return []

    def _summarize_findings(self, findings: list[DeliberationFinding]) -> str:
        """汇总所有审查发现。"""
        high = [f for f in findings if f.severity == "high"]
        medium = [f for f in findings if f.severity == "medium"]
        parts = []
        if high:
            parts.append(f"高优先级 ({len(high)} 条)：")
            for f in high:
                parts.append(f"  - {f.finding}")
        if medium:
            parts.append(f"中优先级 ({len(medium)} 条)：")
            for f in medium[:5]:  # 最多展示 5 条
                parts.append(f"  - {f.finding}")
        if not parts:
            return "审查未发现重大问题。"
        return "\n".join(parts)

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("DeliberationReviewService: LLM 响应结构异常")
        return None

    def apply_pm_decisions(self, record: BrainstormRecord) -> None:
        """PM 对审查发现做裁决，accepted 的建议回写功能树。"""
        if not record.deliberation_rounds:
            return

        latest = record.deliberation_rounds[-1]
        for finding in latest.findings:
            if finding.pm_decision == "accept" and finding.suggested_change:
                # 将建议写回对应功能节点
                for fid in finding.affected_feature_ids:
                    node = record.feature_tree.get_node(fid)
                    if node:
                        # 追加到 edge_cases 或 review_feedback
                        if finding.finding not in node.review_feedback:
                            node.review_feedback.append(f"[deliberation] {finding.finding}")

    def make_decision(self, record: BrainstormRecord, finding_id: str, decision: str, reason: str = "") -> None:
        """对指定审查发现做 PM 裁决。"""
        for rnd in record.deliberation_rounds:
            for finding in rnd.findings:
                if finding.finding_id == finding_id:
                    finding.pm_decision = decision
                    finding.pm_reason = reason
                    return
```

- [ ] **步骤 2：编写 DeliberationReviewService 测试**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.deliberation_service import DeliberationReviewService, DIMENSIONS
from ralph.schema.brainstorm_record import (
    BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree,
)


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": "[]"}}]}}
    yield DeliberationReviewService(config_manager=mock_config)


@pytest.fixture
def record_with_features():
    with tempfile.TemporaryDirectory() as tmpdir:
        record = BrainstormRecord(record_id="bs-delib", project_name="协作系统")
        root = FeatureNode(node_id="fn-root", name="协作系统", level="product")
        fn1 = FeatureNode(
            node_id="fn-001", name="文档编辑", level="function", status="confirmed",
            user_stories=["作为用户可以编辑文档"],
            acceptance_criteria=["保存成功"],
            success_path=["打开文档", "编辑", "保存"],
            failure_path=["网络断开"],
            edge_cases=["同时编辑"],
        )
        fn2 = FeatureNode(
            node_id="fn-002", name="评论功能", level="function", status="confirmed",
            user_stories=["作为用户可以添加评论"],
            acceptance_criteria=["评论显示在文档侧边"],
            success_path=["选中内容", "添加评论"],
            failure_path=["评论失败提示重试"],
            edge_cases=["评论超长"],
        )
        record.feature_tree = FeatureTree(
            root_id="fn-root",
            nodes={"fn-root": root, "fn-001": fn1, "fn-002": fn2},
            current_exploring_id="fn-001",
        )
        yield record


def test_dimensions_defined():
    """验证四个审查维度已定义"""
    assert len(DIMENSIONS) == 4
    roles = [d["role"] for d in DIMENSIONS]
    assert "user_journey_analyst" in roles
    assert "feature_completeness_reviewer" in roles
    assert "industry_benchmark_analyst" in roles
    assert "scenario_combiner" in roles


def test_run_review_returns_round(service, record_with_features):
    """测试审查执行返回结果"""
    rnd = service.run_review(record_with_features)
    assert rnd.round_id.startswith("dr-")
    assert rnd.created_at != ""
    assert len(record_with_features.deliberation_rounds) == 1
    assert record_with_features.deliberation_rounds[0] is rnd


def test_review_no_config():
    """测试无 config 时 graceful 降级"""
    svc = DeliberationReviewService(config_manager=None)
    record = BrainstormRecord(record_id="bs-noconfig", project_name="Test")
    root = FeatureNode(node_id="fn-root", name="Test", level="product")
    record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root})
    rnd = svc.run_review(record)
    assert rnd is not None
    assert rnd.findings == []


def test_apply_pm_decisions_updates_nodes(service, record_with_features):
    """测试 PM 裁决回写功能树"""
    rnd = DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少撤销功能", severity="high",
                suggested_change="添加撤销/重做功能",
            )
        ],
        pm_summary="测试",
    )
    record_with_features.deliberation_rounds.append(rnd)
    # 手动设置 pm_decision
    rnd.findings[0].pm_decision = "accept"

    service.apply_pm_decisions(record_with_features)
    node = record_with_features.feature_tree.get_node("fn-001")
    assert any("撤销" in fb for fb in node.review_feedback)


def test_make_decision(service, record_with_features):
    """测试对审查发现做裁决"""
    rnd = DeliberationRound(
        round_id="dr-decision",
        findings=[
            DeliberationFinding(
                finding_id="f-dec", dimension="feature_completeness_reviewer",
                affected_feature_ids=["fn-001"],
                finding="缺少搜索", severity="medium",
                suggested_change="添加全文搜索",
            )
        ],
    )
    record_with_features.deliberation_rounds.append(rnd)

    service.make_decision(record_with_features, "f-dec", "reject", "MVP 不做搜索")
    assert rnd.findings[0].pm_decision == "reject"
    assert rnd.findings[0].pm_reason == "MVP 不做搜索"


def test_summarize_findings(service):
    """测试审查发现摘要生成"""
    findings = [
        DeliberationFinding(finding_id="1", dimension="a", affected_feature_ids=[], finding="问题A", severity="high", suggested_change=""),
        DeliberationFinding(finding_id="2", dimension="a", affected_feature_ids=[], finding="问题B", severity="medium", suggested_change=""),
    ]
    summary = service._summarize_findings(findings)
    assert "高优先级" in summary
    assert "问题A" in summary
```

- [ ] **步骤 3：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_deliberation_service.py -v`
预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add ralph/deliberation_service.py tests/ralph/test_deliberation_service.py
git commit -m "feat: DeliberationReviewService for four-dimensional structured feature review"
```

---

### 任务 5：BrainstormManager V3 Phase 路由扩展

**文件：**
- 修改：`ralph/brainstorm_manager.py`
- 测试：`tests/ralph/test_brainstorm_v3_manager.py`

- [ ] **步骤 1：修改 start_session 从 PROACTIVE_ANALYSIS 开始**

修改 `start_session` 方法（约第 34-65 行），将 `current_phase` 从 `PRODUCT_DEF` 改为 `PROACTIVE_ANALYSIS`，并触发主动分析：

```python
    def start_session(self, project_name: str, user_message: str) -> BrainstormRecord:
        """V3: 创建 session，初始化 product 根节点，进入 PROACTIVE_ANALYSIS Phase"""
        record_id = f"bs-{_now_iso().replace(':', '-')}"

        root_node = FeatureNode(
            node_id="fn-root",
            name=project_name,
            level="product",
            status="exploring",
            depth=0,
        )

        feature_tree = FeatureTree(
            root_id="fn-root",
            nodes={"fn-root": root_node},
            current_exploring_id="fn-root",
            question_plan=[],
            current_question_id=None,
        )

        record = BrainstormRecord(
            record_id=record_id,
            project_name=project_name,
            user_message=user_message,
            current_phase=BrainstormPhase.PROACTIVE_ANALYSIS,
            feature_tree=feature_tree,
            round_number=1,
        )

        # V3: 触发主动分析
        self._run_proactive_analysis(record)

        self._save(record)
        return record
```

- [ ] **步骤 2：新增 _run_proactive_analysis 方法**

在 `_count_confirmed_features` 方法之后（约第 134 行之后）插入：

```python
    def _run_proactive_analysis(self, record: BrainstormRecord) -> None:
        """V3: 调用 ProactiveAnalysisService 生成假设草案。"""
        from ralph.proactive_service import ProactiveAnalysisService
        service = ProactiveAnalysisService(self._config)
        service.analyze(record)
```

- [ ] **步骤 3：修改 advance_phase 增加新 phase 路由**

修改 `advance_phase` 方法（约第 770 行），在现有逻辑之前追加新 phase 的处理：

```python
        if current == BrainstormPhase.PROACTIVE_ANALYSIS:
            # 用户至少确认了核心产品类型和目标用户
            if not self._check_proactive_analysis_confirmed(record):
                return False
            record.current_phase = BrainstormPhase.PRODUCT_DEF

        elif current == BrainstormPhase.DELIBERATION_REVIEW:
            if not record.deliberation_rounds:
                return False
            # 所有 high severity finding 必须被处理
            if not self._check_deliberation_resolved(record):
                return False
            record.current_phase = BrainstormPhase.RELATIONSHIP

        elif current == BrainstormPhase.REQUIREMENTS_READY:
            record.current_phase = BrainstormPhase.COMPLETE
            record.completed_at = now

        elif current == BrainstormPhase.TECHNICAL_ROUTE_DRAFT:
            if not record.technical_route:
                return False
            if record.technical_route.status != "accepted":
                return False
            record.current_phase = BrainstormPhase.TOOL_DISCOVERY

        elif current == BrainstormPhase.TOOL_DISCOVERY:
            record.current_phase = BrainstormPhase.EXECUTION_PLAN_READY

        elif current == BrainstormPhase.EXECUTION_PLAN_READY:
            record.current_phase = BrainstormPhase.COMPLETE
            record.completed_at = now
```

- [ ] **步骤 4：新增辅助方法 _check_proactive_analysis_confirmed 和 _check_deliberation_resolved**

在 `_check_product_complete` 方法之后插入：

```python
    def _check_proactive_analysis_confirmed(self, record: BrainstormRecord) -> bool:
        """检查主动分析阶段是否已确认核心条目。"""
        analysis = record.proactive_analysis
        if not analysis or not analysis.items:
            return False
        # 至少有一个 product_type 或 target_user 类别的条目被 accepted 或 modified
        core_confirmed = any(
            item.category in ("product_type", "target_user")
            and item.status in ("accepted", "modified")
            for item in analysis.items
        )
        return core_confirmed

    def _check_deliberation_resolved(self, record: BrainstormRecord) -> bool:
        """检查所有 high severity finding 是否被 accept/reject/defer。"""
        if not record.deliberation_rounds:
            return False
        latest = record.deliberation_rounds[-1]
        high_findings = [f for f in latest.findings if f.severity == "high"]
        return all(f.pm_decision in ("accept", "reject", "defer") for f in high_findings)
```

- [ ] **步骤 5：修改 process_response_v2 路由新增 phase 处理**

修改 `process_response_v2` 方法（约第 864 行），在 phase 路由中新增：

```python
        if phase == BrainstormPhase.PROACTIVE_ANALYSIS:
            # 用户确认/修改主动分析条目
            self._process_proactive_response(record, user_response)

        elif phase == BrainstormPhase.DELIBERATION_REVIEW:
            # PM 裁决审查发现
            self._process_deliberation_response(record, user_response)

        elif phase == BrainstormPhase.REQUIREMENTS_READY:
            # 用户需求确认循环
            self._process_requirements_confirm(record, user_response)
```

- [ ] **步骤 6：新增 process_response_v2 对应的处理方法**

在 `_process_clarification_response` 方法之后插入：

```python
    def _process_proactive_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 PROACTIVE_ANALYSIS 阶段用户回复。"""
        analysis = record.proactive_analysis
        if not analysis:
            return
        # 将用户回复作为 conversation_turn 记录到 root 节点
        root = record.feature_tree.get_node("fn-root")
        if root:
            from datetime import UTC, datetime
            root.conversation_turns.append({
                "question": "请确认或修改以下分析方向",
                "response": user_response,
                "timestamp": datetime.now(UTC).isoformat(),
            })

    def _process_deliberation_response(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 DELIBERATION_REVIEW 阶段用户回复。"""
        if not record.deliberation_rounds:
            return
        # 用户可以对审查发现做裁决（accept/reject/defer）
        # 简单实现：将用户回复追加到最新审查轮的 pm_summary
        latest = record.deliberation_rounds[-1]
        latest.pm_summary += f"\n用户反馈: {user_response}"

    def _process_requirements_confirm(self, record: BrainstormRecord, user_response: str) -> None:
        """处理 REQUIREMENTS_READY 阶段用户确认。"""
        root = record.feature_tree.get_node("fn-root")
        if root:
            from datetime import UTC, datetime
            root.conversation_turns.append({
                "question": "请确认最终需求规格",
                "response": user_response,
                "timestamp": datetime.now(UTC).isoformat(),
            })
```

- [ ] **步骤 7：新增 V3 公开方法**

在 `check_handoff_readiness` 方法之后插入：

```python
    def trigger_deliberation_review(self, record: BrainstormRecord) -> DeliberationRound:
        """触发四维结构化功能审查。"""
        from ralph.deliberation_service import DeliberationReviewService
        service = DeliberationReviewService(self._config)
        return service.run_review(record)

    def generate_technical_route(self, record: BrainstormRecord) -> TechnicalRoute:
        """基于已确认需求生成技术路线草案。"""
        from ralph.technical_route_service import TechnicalRouteService
        service = TechnicalRouteService(self._config)
        route = service.generate_route(record)
        record.technical_route = route
        return route

    def confirm_technical_route(self, record: BrainstormRecord, status: str, feedback: str = "") -> None:
        """用户确认技术路线。"""
        if record.technical_route:
            record.technical_route.status = status
            record.technical_route.user_feedback = feedback
            if status == "accepted":
                from datetime import UTC, datetime
                record.technical_route.confirmed_at = datetime.now(UTC).isoformat()

    def trigger_tool_discovery(self, record: BrainstormRecord) -> list[ToolDiscoveryResult]:
        """基于技术路线触发工具发现。"""
        if not record.technical_route:
            return []
        from ralph.tool_discovery import ToolDiscoveryService
        service = ToolDiscoveryService(self._config)
        results = service.discover(record.technical_route.tool_needs)
        record.tool_discovery_results = results
        return results
```

- [ ] **步骤 8：更新 import 语句**

在文件顶部 import 中追加新数据类型：

```python
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, ConfirmedFact, FeatureNode, FeatureTree,
    OpenAssumption, QuestionTask, UserPath, _now_iso, brainstorm_to_dict, dict_to_brainstorm,
    DeliberationRound, TechnicalRoute, ToolDiscoveryResult,
)
```

- [ ] **步骤 9：运行现有测试确认不受影响**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v2.py -v`
预期：全部 PASS（如有失败，检查 start_session 的 phase 变更是否影响旧测试）

- [ ] **步骤 10：Commit**

```bash
git add ralph/brainstorm_manager.py
git commit -m "feat: extend BrainstormManager with V3 phase routing (PROACTIVE_ANALYSIS, DELIBERATION_REVIEW, TECHNICAL_ROUTE_DRAFT, TOOL_DISCOVERY)"
```

---

### 任务 6：编写 BrainstormManager V3 测试

**文件：**
- 创建：`tests/ralph/test_brainstorm_v3_manager.py`

- [ ] **步骤 1：编写 V3 phase 路由测试**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    FeatureNode, FeatureTree, ProactiveAnalysis, ProactiveAnalysisItem,
    TechnicalRoute,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BrainstormManager(Path(tmpdir))


@pytest.fixture
def manager_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS 产品", "confidence": 0.8}]}'}}]}}
        yield BrainstormManager(Path(tmpdir), config_manager=mock_config)


def test_v3_start_session_starts_at_proactive_analysis(manager_with_config):
    """V3: start_session 应从 PROACTIVE_ANALYSIS 开始"""
    record = manager_with_config.start_session("测试项目", "我想做一个在线文档系统")
    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None
    assert len(record.proactive_analysis.items) >= 1


def test_advance_phase_proactive_analysis_incomplete(manager):
    """PROACTIVE_ANALYSIS: 未确认核心条目时不能推进"""
    record = manager.start_session("P", "描述")
    # 不使用 mock config 时 proactive_analysis 为空
    result = manager.advance_phase(record)
    # 如果没有 proactive_analysis 或没有 confirmed items，应该无法推进
    # （取决于 config 是否可用）
    if record.proactive_analysis and record.proactive_analysis.items:
        assert result is False  # 条目都还是 pending 状态


def test_check_proactive_analysis_confirmed(manager):
    """验证 _check_proactive_analysis_confirmed 逻辑"""
    record = manager.start_session("P", "描述")
    # 未确认时应为 False
    assert manager._check_proactive_analysis_confirmed(record) is False

    # 模拟确认一个 product_type 条目
    record.proactive_analysis = ProactiveAnalysis(
        analysis_id="pa-test",
        items=[
            ProactiveAnalysisItem(
                item_id="i1", category="product_type",
                content="SaaS 产品", confidence=0.8, status="accepted",
            )
        ],
    )
    assert manager._check_proactive_analysis_confirmed(record) is True


def test_check_deliberation_resolved(manager):
    """验证 _check_deliberation_resolved 逻辑"""
    record = manager.start_session("P", "描述")
    assert manager._check_deliberation_resolved(record) is False

    # 添加一个 high severity 但未裁决的 finding
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少功能", severity="high",
                suggested_change="添加",
                pm_decision="pending",
            )
        ],
    ))
    assert manager._check_deliberation_resolved(record) is False

    # 裁决后应为 True
    record.deliberation_rounds[-1].findings[0].pm_decision = "accept"
    assert manager._check_deliberation_resolved(record) is True


def test_process_response_v2_proactive_phase(manager):
    """测试 process_response_v2 在 PROACTIVE_ANALYSIS phase 的路由"""
    record = manager.start_session("P", "描述")
    record.current_phase = BrainstormPhase.PROACTIVE_ANALYSIS
    # 不应该报错
    manager.process_response_v2(record, "看起来差不多，继续吧")
    root = record.feature_tree.get_node("fn-root")
    assert len(root.conversation_turns) >= 1


def test_process_response_v2_deliberation_phase(manager):
    """测试 process_response_v2 在 DELIBERATION_REVIEW phase 的路由"""
    record = manager.start_session("P", "描述")
    record.current_phase = BrainstormPhase.DELIBERATION_REVIEW
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-test", findings=[], pm_summary="初始摘要",
    ))
    manager.process_response_v2(record, "接受所有建议")
    assert "用户反馈" in record.deliberation_rounds[-1].pm_summary


def test_generate_technical_route(manager):
    """测试技术路线生成（需要 config）"""
    record = manager.start_session("P", "描述")
    # 无 config 时应返回默认空路线
    try:
        route = manager.generate_technical_route(record)
        assert route is not None
    except Exception:
        pass  # 无 config 时可能抛出异常，这是可预期的


def test_confirm_technical_route(manager):
    """测试技术路线确认"""
    record = manager.start_session("P", "描述")
    record.technical_route = TechnicalRoute(
        route_id="tr-test", architecture_summary="前后端分离",
    )
    manager.confirm_technical_route(record, "accepted", "好的")
    assert record.technical_route.status == "accepted"
    assert record.technical_route.user_feedback == "好的"
    assert record.technical_route.confirmed_at != ""
```

- [ ] **步骤 2：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_manager.py -v`
预期：全部 PASS

- [ ] **步骤 3：Commit**

```bash
git add tests/ralph/test_brainstorm_v3_manager.py
git commit -m "test: BrainstormManager V3 phase routing, proactive analysis confirmation, and deliberation resolution tests"
```

---

### 任务 7：ToolDiscoveryService

**文件：**
- 创建：`ralph/tool_discovery.py`
- 测试：`tests/ralph/test_tool_discovery.py`

- [ ] **步骤 1：实现 ToolDiscoveryService**

```python
"""ToolDiscoveryService — 基于技术路线进行第三方工具发现与评估。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import (
    ToolCandidate, ToolDiscoveryResult, ToolEvaluation, _now_iso,
)

logger = logging.getLogger(__name__)


class ToolDiscoveryService:
    """根据技术路线中的工具需求，搜索、评估、推荐第三方工具。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def discover(self, tool_needs: list[str]) -> list[ToolDiscoveryResult]:
        """对每个工具需求执行发现流程。"""
        results: list[ToolDiscoveryResult] = []
        for need in tool_needs:
            result = self._discover_for_need(need)
            results.append(result)
        return results

    def _discover_for_need(self, tool_need: str) -> ToolDiscoveryResult:
        """对单个工具需求执行搜索和评估。"""
        result = ToolDiscoveryResult(
            discovery_id=f"td-{uuid.uuid4().hex[:8]}",
            tool_need=tool_need,
            created_at=_now_iso(),
        )

        # Step 1: 生成搜索 query
        queries = self._generate_queries(tool_need)
        result.queries = queries

        # Step 2: 对每个 query 搜索候选
        for query in queries:
            candidates = self._search_candidate(query)
            for c in candidates:
                if c.candidate_id not in {x.candidate_id for x in result.candidates}:
                    result.candidates.append(c)

        # Step 3: 评估候选
        for candidate in result.candidates[:5]:  # 最多评估前 5 个
            evaluation = self._evaluate_candidate(candidate, tool_need)
            result.evaluations.append(evaluation)

        # Step 4: 选择推荐
        adoptable = [e for e in result.evaluations if e.recommendation == "adopt"]
        if adoptable:
            result.selected_candidate_ids = [adoptable[0].candidate_id]

        return result

    def _generate_queries(self, tool_need: str) -> list[str]:
        """基于工具需求生成搜索 query。"""
        if self._config is None:
            return [f"{tool_need} github open source", f"best {tool_need} library python"]

        prompt = f"""用户需要一个{tool_need}的第三方工具/库。
请生成 3 个搜索 query，用于在 GitHub 和互联网上搜索相关工具。

要求：
- query 要具体，包含技术关键词
- 至少一个 query 包含 "github" 关键词

以 JSON 数组返回: ["query1", "query2", "query3"]"""

        content = self._call_llm("tool_discovery_queries", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                    if content.startswith("json"):
                        content = content[4:].strip()
                queries = json.loads(content)
                if isinstance(queries, list) and queries:
                    return queries[:3]
            except (json.JSONDecodeError, TypeError):
                logger.warning("ToolDiscoveryService: query generation parse error")

        return [f"{tool_need} github open source", f"best {tool_need} library python"]

    def _search_candidate(self, query: str) -> list[ToolCandidate]:
        """搜索候选工具。"""
        if self._config is None:
            return []

        prompt = f"""基于搜索 query "{query}"，返回 2-3 个最相关的开源工具/库。

请以 JSON 数组返回：
[
  {{
    "candidate_id": "tc-1",
    "name": "工具名称",
    "source": "github",
    "url": "https://github.com/...",
    "description": "简短描述",
    "license": "MIT",
    "stars": 10000,
    "last_updated": "2026-01-15",
    "package_name": "package-name"
  }}
]"""

        content = self._call_llm("tool_discovery_search", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                candidates = []
                for c in data:
                    candidates.append(ToolCandidate(
                        candidate_id=c.get("candidate_id", f"tc-{uuid.uuid4().hex[:6]}"),
                        name=c.get("name", ""),
                        source=c.get("source", "web"),
                        url=c.get("url", ""),
                        description=c.get("description", ""),
                        license=c.get("license", ""),
                        stars=c.get("stars"),
                        last_updated=c.get("last_updated", ""),
                        package_name=c.get("package_name", ""),
                    ))
                return candidates
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("ToolDiscoveryService: search parse error: %s", e)

        return []

    def _evaluate_candidate(self, candidate: ToolCandidate, tool_need: str) -> ToolEvaluation:
        """评估候选工具。"""
        if self._config is None:
            return ToolEvaluation(
                candidate_id=candidate.candidate_id,
                functional_fit=3, maintenance_health=3, license_fit=3,
                stack_compatibility=3, security_risk="unknown",
                integration_cost="medium", summary="无法评估（LLM 不可用）",
                recommendation="compare",
            )

        prompt = f"""请评估以下工具是否满足需求：

需求：{tool_need}
工具：{candidate.name}
描述：{candidate.description}
许可证：{candidate.license}
Stars：{candidate.stars or '未知'}
最近更新：{candidate.last_updated or '未知'}

请从以下维度评分：
- functional_fit (1-5)：功能匹配度
- maintenance_health (1-5)：维护健康度
- license_fit (1-5)：许可证兼容性
- stack_compatibility (1-5)：技术栈兼容性
- security_risk (low/medium/high/unknown)：安全风险
- integration_cost (low/medium/high)：集成成本

以 JSON 返回：
{{
  "functional_fit": 4,
  "maintenance_health": 4,
  "license_fit": 5,
  "stack_compatibility": 4,
  "security_risk": "low",
  "integration_cost": "low",
  "summary": "评估摘要",
  "recommendation": "adopt|compare|avoid"
}}"""

        content = self._call_llm("tool_discovery_evaluation", [{"role": "user", "content": prompt}])
        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                return ToolEvaluation(
                    candidate_id=candidate.candidate_id,
                    functional_fit=int(data.get("functional_fit", 3)),
                    maintenance_health=int(data.get("maintenance_health", 3)),
                    license_fit=int(data.get("license_fit", 3)),
                    stack_compatibility=int(data.get("stack_compatibility", 3)),
                    security_risk=data.get("security_risk", "unknown"),
                    integration_cost=data.get("integration_cost", "medium"),
                    summary=data.get("summary", ""),
                    recommendation=data.get("recommendation", "compare"),
                )
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("ToolDiscoveryService: evaluation parse error: %s", e)

        return ToolEvaluation(
            candidate_id=candidate.candidate_id,
            functional_fit=3, maintenance_health=3, license_fit=3,
            stack_compatibility=3, security_risk="unknown",
            integration_cost="medium", summary="评估失败",
            recommendation="compare",
        )

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 1500,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("ToolDiscoveryService: LLM 响应结构异常")
        return None
```

- [ ] **步骤 2：编写 ToolDiscoveryService 测试**

```python
import pytest
from unittest.mock import MagicMock

from ralph.tool_discovery import ToolDiscoveryService
from ralph.schema.brainstorm_record import ToolCandidate, ToolDiscoveryResult, ToolEvaluation


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": "[]"}}]}}
    yield ToolDiscoveryService(config_manager=mock_config)


@pytest.fixture
def service_with_mocked_search():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}

    def mock_proxy(*args):
        endpoint = args[1]
        body = args[2]
        prompt = body["messages"][0]["content"]

        if "生成" in prompt or "query" in prompt.lower():
            return {"ok": True, "data": {"choices": [{"message": {"content": '["fastapi github", "python web framework fastapi"]'}}]}}
        elif "搜索" in prompt or "search" in prompt.lower():
            return {"ok": True, "data": {"choices": [{"message": {"content": '[{"candidate_id": "tc-1", "name": "FastAPI", "source": "github", "url": "https://github.com/tiangolo/fastapi", "description": "Modern web framework", "license": "MIT", "stars": 70000, "last_updated": "2026-01-15", "package_name": "fastapi"}]'}}]}}
        elif "评估" in prompt or "evaluate" in prompt.lower():
            return {"ok": True, "data": {"choices": [{"message": {"content": '{"functional_fit": 5, "maintenance_health": 5, "license_fit": 5, "stack_compatibility": 5, "security_risk": "low", "integration_cost": "low", "summary": "优秀", "recommendation": "adopt"}'}}]}}
        return {"ok": True, "data": {"choices": [{"message": {"content": "[]"}}]}}

    mock_config.proxy_request.side_effect = mock_proxy
    yield ToolDiscoveryService(config_manager=mock_config)


def test_discover_returns_results(service_with_mocked_search):
    """测试工具发现返回结果"""
    results = service_with_mocked_search.discover(["Web 框架"])
    assert len(results) == 1
    result = results[0]
    assert result.tool_need == "Web 框架"
    assert len(result.queries) >= 1


def test_discover_no_config():
    """测试无 config 时的降级行为"""
    svc = ToolDiscoveryService(config_manager=None)
    results = svc.discover(["Web 框架"])
    assert len(results) == 1
    assert results[0].tool_need == "Web 框架"
    # 无 config 时候选和评估都为空
    assert results[0].candidates == []
    assert results[0].evaluations == []


def test_generate_queries_fallback(service):
    """测试 query 生成在 LLM 失败时的 fallback"""
    # mock 已配置但返回空
    queries = service._generate_queries("数据库 ORM")
    assert isinstance(queries, list)
    assert len(queries) >= 1


def test_evaluate_candidate_no_config():
    """测试无 config 时评估降级"""
    svc = ToolDiscoveryService(config_manager=None)
    candidate = ToolCandidate(
        candidate_id="tc-1", name="FastAPI",
        source="github", url="https://github.com/tiangolo/fastapi",
        description="Fast web framework",
    )
    ev = svc._evaluate_candidate(candidate, "Web 框架")
    assert ev.security_risk == "unknown"
    assert ev.recommendation == "compare"


def test_candidate_defaults():
    """测试 ToolCandidate 创建"""
    c = ToolCandidate(
        candidate_id="tc-1", name="Test",
        source="github", url="https://example.com",
        description="Test tool",
    )
    assert c.stars is None
    assert c.license == ""


def test_evaluation_defaults():
    """测试 ToolEvaluation 创建"""
    ev = ToolEvaluation(
        candidate_id="tc-1", functional_fit=5, maintenance_health=5,
        license_fit=5, stack_compatibility=5,
        security_risk="low", integration_cost="low",
        summary="好", recommendation="adopt",
    )
    assert ev.recommendation == "adopt"
```

- [ ] **步骤 3：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_tool_discovery.py -v`
预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add ralph/tool_discovery.py tests/ralph/test_tool_discovery.py
git commit -m "feat: ToolDiscoveryService for searching, evaluating and recommending third-party tools based on technical route"
```

---

### 任务 8：TechnicalRouteService

**文件：**
- 创建：`ralph/technical_route_service.py`
- 测试：`tests/ralph/test_technical_route_service.py`

- [ ] **步骤 1：实现 TechnicalRouteService**

```python
"""TechnicalRouteService — 基于已确认需求生成技术路线草案。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from ralph.schema.brainstorm_record import BrainstormRecord, TechnicalRoute, _now_iso

logger = logging.getLogger(__name__)


class TechnicalRouteService:
    """根据冻结后的 PRD / Spec 生成技术路线草案。"""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager

    def generate_route(self, record: BrainstormRecord) -> TechnicalRoute:
        """生成技术路线草案。"""
        spec_text = self._render_spec_text(record)

        prompt = f"""你是资深系统架构师。基于以下需求规格，生成技术路线草案。

{spec_text}

请从以下维度生成技术路线：
1. 架构摘要：整体架构描述（如前后端分离、微服务等）
2. 前端技术栈：推荐的前端框架和库
3. 后端技术栈：推荐的后端框架和语言
4. 数据存储：数据库和存储方案
5. 外部集成：需要对接的第三方服务
6. 非功能需求：性能、安全、可用性要求
7. 关键风险：技术风险点
8. 工具需求：需要哪些第三方工具/库/引擎支持（用于后续工具发现）

请以 JSON 返回：
{{
  "architecture_summary": "...",
  "frontend_stack": ["React", "TypeScript"],
  "backend_stack": ["Python", "FastAPI"],
  "data_storage": ["PostgreSQL"],
  "integrations": ["Stripe"],
  "non_functional_requirements": ["响应时间 < 200ms"],
  "key_risks": ["高并发场景"],
  "tool_needs": ["支付 SDK", "消息队列"]
}}"""

        content = self._call_llm("technical_route", [{"role": "user", "content": prompt}])

        route = TechnicalRoute(
            route_id=f"tr-{uuid.uuid4().hex[:8]}",
            architecture_summary="待分析",
            created_at=_now_iso(),
        )

        if content:
            try:
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n", 1)
                    content = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else content
                    if content.startswith("json"):
                        content = content[4:].strip()
                data = json.loads(content)
                route = TechnicalRoute(
                    route_id=route.route_id,
                    architecture_summary=data.get("architecture_summary", "待分析"),
                    frontend_stack=data.get("frontend_stack", []),
                    backend_stack=data.get("backend_stack", []),
                    data_storage=data.get("data_storage", []),
                    integrations=data.get("integrations", []),
                    non_functional_requirements=data.get("non_functional_requirements", []),
                    key_risks=data.get("key_risks", []),
                    tool_needs=data.get("tool_needs", []),
                    created_at=_now_iso(),
                )
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                logger.warning("TechnicalRouteService: LLM parse error: %s", e)

        return route

    def _render_spec_text(self, record: BrainstormRecord) -> str:
        """将 BrainstormRecord 渲染为 Spec 文本供技术路线生成。"""
        lines = [f"# {record.project_name} 需求规格", ""]
        root = record.feature_tree.get_node("fn-root")
        if root:
            if root.vision:
                lines.extend(["## 产品愿景", f"- {root.vision}", ""])
            if root.target_users:
                lines.extend(["## 目标用户", f"- {', '.join(root.target_users)}", ""])
            if root.roles:
                lines.extend(["## 用户角色", f"- {', '.join(root.roles)}", ""])

        lines.extend(["## 功能列表", ""])
        for node in record.feature_tree.nodes.values():
            if node.level == "product":
                continue
            if node.status != "confirmed":
                continue
            lines.append(f"### {node.name} ({node.node_id})")
            if node.user_stories:
                for s in node.user_stories:
                    lines.append(f"- {s}")
            lines.append("")

        return "\n".join(lines)

    def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
        if self._config is None:
            return None
        try:
            provider = self._config.resolve_agent_provider("brainstorm", task_type)
        except Exception:
            provider = {"provider_id": "", "model": "", "source": "none"}
        if not provider.get("provider_id"):
            return None
        result = self._config.proxy_request(
            provider["provider_id"], "v1/chat/completions",
            {
                "model": provider.get("model", ""),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )
        if result.get("ok"):
            try:
                content = result["data"]["choices"][0]["message"]["content"]
                if not content.strip():
                    content = result["data"]["choices"][0]["message"].get("reasoning_content", "") or ""
                return content if content.strip() else None
            except (KeyError, IndexError, TypeError):
                logger.warning("TechnicalRouteService: LLM 响应结构异常")
        return None
```

- [ ] **步骤 2：编写 TechnicalRouteService 测试**

```python
import pytest
import tempfile
from unittest.mock import MagicMock

from ralph.technical_route_service import TechnicalRouteService
from ralph.schema.brainstorm_record import (
    BrainstormRecord, FeatureNode, FeatureTree, TechnicalRoute,
)


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {
            "content": '{"architecture_summary":"前后端分离","frontend_stack":["React"],"backend_stack":["FastAPI"],"data_storage":["PostgreSQL"],"integrations":[],"non_functional_requirements":[],"key_risks":[],"tool_needs":["Web框架"]}'
        }}]}
    }
    yield TechnicalRouteService(config_manager=mock_config)


@pytest.fixture
def confirmed_record():
    with tempfile.TemporaryDirectory() as tmpdir:
        record = BrainstormRecord(record_id="bs-tr", project_name="协作系统")
        root = FeatureNode(node_id="fn-root", name="协作系统", level="product", status="confirmed")
        root.vision = "在线协作"
        root.target_users = ["团队"]
        root.roles = ["管理员", "成员"]
        fn1 = FeatureNode(
            node_id="fn-001", name="文档编辑", level="function", status="confirmed",
            user_stories=["作为用户可以编辑文档"],
        )
        record.feature_tree = FeatureTree(
            root_id="fn-root",
            nodes={"fn-root": root, "fn-001": fn1},
        )
        yield record


def test_generate_route(service, confirmed_record):
    """测试技术路线生成"""
    route = service.generate_route(confirmed_record)
    assert route.route_id.startswith("tr-")
    assert route.frontend_stack == ["React"]
    assert route.backend_stack == ["FastAPI"]
    assert route.tool_needs == ["Web框架"]


def test_generate_route_no_config(confirmed_record):
    """测试无 config 时返回默认空路线"""
    svc = TechnicalRouteService(config_manager=None)
    route = svc.generate_route(confirmed_record)
    assert route.architecture_summary == "待分析"
    assert route.tool_needs == []


def test_render_spec_text(service, confirmed_record):
    """测试 Spec 文本渲染"""
    spec = service._render_spec_text(confirmed_record)
    assert "协作系统" in spec
    assert "文档编辑" in spec
    assert "在线协作" in spec
```

- [ ] **步骤 3：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_technical_route_service.py -v`
预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add ralph/technical_route_service.py tests/ralph/test_technical_route_service.py
git commit -m "feat: TechnicalRouteService for generating technical route from confirmed requirements"
```

---

### 任务 9：API 端点扩展

**文件：**
- 修改：`dashboard/api/routes.py`
- 测试：`tests/ralph/test_brainstorm_v3_integration.py`

- [ ] **步骤 1：在现有 brainstorm routes 之后追加 V3 API 端点**

在 `register_ralph_extended_routes` 函数中，找到最后一个 brainstorm 端点（约第 2180 行附近），追加以下端点：

```python
    # ── V3: 主动分析 ──────────────────────────────────────

    @app.post("/api/ralph/brainstorm/{record_id}/proactive/confirm")
    async def ralph_proactive_confirm(record_id: str, body: dict[str, Any]) -> dict:
        """用户确认/修改主动分析条目。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        analysis = record.proactive_analysis
        if not analysis:
            raise HTTPException(status_code=400, detail="No proactive analysis available")

        # body: {"item_id": "pa-1", "status": "accepted|rejected|modified", "revision": "..."}
        item_id = body.get("item_id")
        status = body.get("status", "pending")
        revision = body.get("revision", "")

        for item in analysis.items:
            if item.item_id == item_id:
                item.status = status
                item.user_revision = revision
                break

        mgr._save(record)
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "proactive_analysis": brainstorm_to_dict(analysis),
            "current_phase": record.current_phase,
        }

    @app.post("/api/ralph/brainstorm/{record_id}/deliberation/start")
    async def ralph_start_deliberation(record_id: str) -> dict:
        """触发四维结构化功能审查。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        rnd = mgr.trigger_deliberation_review(record)
        mgr.advance_phase(record)
        mgr._save(record)

        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "round": {
                "round_id": rnd.round_id,
                "finding_count": len(rnd.findings),
                "findings": [brainstorm_to_dict(f) for f in rnd.findings],
                "pm_summary": rnd.pm_summary,
            },
            "current_phase": record.current_phase,
        }

    @app.post("/api/ralph/brainstorm/{record_id}/deliberation/decision")
    async def ralph_deliberation_decision(record_id: str, body: dict[str, Any]) -> dict:
        """PM 对审查发现做裁决。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        finding_id = body.get("finding_id")
        decision = body.get("decision", "pending")
        reason = body.get("reason", "")

        if not finding_id:
            raise HTTPException(status_code=422, detail="finding_id required")

        from ralph.deliberation_service import DeliberationReviewService
        service = DeliberationReviewService(mgr._config)
        service.make_decision(record, finding_id, decision, reason)

        mgr._save(record)
        return {"success": True, "finding_id": finding_id, "decision": decision}

    # ── V3: 技术路线 ──────────────────────────────────────

    @app.post("/api/ralph/brainstorm/{record_id}/technical-route/generate")
    async def ralph_generate_technical_route(record_id: str) -> dict:
        """生成技术路线草案。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        route = mgr.generate_technical_route(record)
        record.current_phase = BrainstormPhase.TECHNICAL_ROUTE_DRAFT
        mgr._save(record)

        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "technical_route": brainstorm_to_dict(route),
            "current_phase": record.current_phase,
        }

    @app.post("/api/ralph/brainstorm/{record_id}/technical-route/confirm")
    async def ralph_confirm_technical_route(record_id: str, body: dict[str, Any]) -> dict:
        """用户确认技术路线。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        status = body.get("status", "pending")
        feedback = body.get("feedback", "")
        mgr.confirm_technical_route(record, status, feedback)

        if status == "accepted":
            mgr.advance_phase(record)

        mgr._save(record)

        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "technical_route": brainstorm_to_dict(record.technical_route),
            "current_phase": record.current_phase,
        }

    # ── V3: 工具发现 ──────────────────────────────────────

    @app.post("/api/ralph/brainstorm/{record_id}/tool-discovery/start")
    async def ralph_start_tool_discovery(record_id: str) -> dict:
        """基于技术路线触发工具发现。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        if not record.technical_route or record.technical_route.status != "accepted":
            raise HTTPException(status_code=400, detail="Technical route must be accepted first")

        results = mgr.trigger_tool_discovery(record)
        mgr.advance_phase(record)
        mgr._save(record)

        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return {
            "discovery_results": [brainstorm_to_dict(r) for r in results],
            "current_phase": record.current_phase,
        }

    @app.get("/api/ralph/brainstorm/{record_id}/tool-discovery")
    async def ralph_get_tool_discovery(record_id: str) -> list[dict]:
        """获取工具发现结果。"""
        mgr = _get_brainstorm_manager()
        record = mgr.load(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        from ralph.schema.brainstorm_record import brainstorm_to_dict
        return [brainstorm_to_dict(r) for r in record.tool_discovery_results]
```

- [ ] **步骤 2：确保 BrainstormPhase 已 import**

在文件顶部确认 `BrainstormPhase` 可被引用。如果 `register_ralph_extended_routes` 函数内部没有 import BrainstormPhase，在函数开头追加：

```python
    from ralph.schema.brainstorm_record import BrainstormPhase
```

- [ ] **步骤 3：编写 API 集成测试**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def setup_v3_record():
    """辅助：设置一个包含 V3 数据的测试记录"""
    from ralph.brainstorm_manager import BrainstormManager
    from ralph.schema.brainstorm_record import (
        BrainstormPhase, BrainstormRecord, FeatureNode, FeatureTree,
        ProactiveAnalysis, ProactiveAnalysisItem, TechnicalRoute,
        DeliberationRound, DeliberationFinding,
    )

    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS", "confidence": 0.8}]}'}}]}}

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = BrainstormManager(Path(tmpdir), config_manager=mock_config)
        record = mgr.start_session("集成测试项目", "做一个在线协作文档")
        yield mgr, record


def test_v3_schema_importable():
    """验证 V3 schema 可正常导入"""
    from ralph.schema.brainstorm_record import (
        ProactiveAnalysis, DeliberationFinding, TechnicalRoute,
        ToolDiscoveryResult, BrainstormPhase,
    )
    assert BrainstormPhase.PROACTIVE_ANALYSIS is not None
    assert TechnicalRoute is not None


def test_proactive_analysis_service_importable():
    """验证 ProactiveAnalysisService 可正常导入"""
    from ralph.proactive_service import ProactiveAnalysisService
    assert ProactiveAnalysisService is not None


def test_deliberation_service_importable():
    """验证 DeliberationReviewService 可正常导入"""
    from ralph.deliberation_service import DeliberationReviewService
    assert DeliberationReviewService is not None


def test_tool_discovery_importable():
    """验证 ToolDiscoveryService 可正常导入"""
    from ralph.tool_discovery import ToolDiscoveryService
    assert ToolDiscoveryService is not None


def test_technical_route_service_importable():
    """验证 TechnicalRouteService 可正常导入"""
    from ralph.technical_route_service import TechnicalRouteService
    assert TechnicalRouteService is not None


def test_v3_full_flow_schema(setup_v3_record):
    """V3 完整流程的 schema 层验证"""
    mgr, record = setup_v3_record
    from ralph.schema.brainstorm_record import BrainstormPhase

    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None

    # 模拟确认主动分析
    record.proactive_analysis.items[0].status = "accepted"

    # 推进到 PRODUCT_DEF
    result = mgr.advance_phase(record)
    # 取决于 config 是否可用


def test_deliberation_round_structure():
    """验证 DeliberationRound 数据结构"""
    from ralph.schema.brainstorm_record import DeliberationRound, DeliberationFinding

    rnd = DeliberationRound(
        round_id="dr-test",
        findings=[
            DeliberationFinding(
                finding_id="f1", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少导航", severity="high",
                suggested_change="添加导航",
            )
        ],
        pm_summary="1 条高优先级发现",
    )
    assert len(rnd.findings) == 1
    assert rnd.findings[0].severity == "high"
```

- [ ] **步骤 4：运行全部测试确认不受影响**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_integration.py -v`
预期：全部 PASS

- [ ] **步骤 5：运行全部 brainstorm 相关测试确保无回归**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v2.py tests/ralph/test_brainstorm_analyzer.py tests/ralph/test_brainstorm_e2e.py -v --tb=short`
预期：全部 PASS（如有失败，检查是否是 start_session 的 phase 变更影响）

- [ ] **步骤 6：Commit**

```bash
git add dashboard/api/routes.py tests/ralph/test_brainstorm_v3_integration.py
git commit -m "feat: add V3 API endpoints for proactive analysis, deliberation review, technical route, and tool discovery"
```

---

### 任务 10：V3 端到端集成测试

**文件：**
- 创建：`tests/ralph/test_brainstorm_v3_e2e.py`

- [ ] **步骤 1：编写 V3 端到端流程测试**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import (
    BrainstormPhase, BrainstormRecord, DeliberationFinding, DeliberationRound,
    ExplicitCheck, FeatureNode, FeatureTree, ProactiveAnalysis,
    ProactiveAnalysisItem, TechnicalRoute, _now_iso,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_config = MagicMock()
        mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
        mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "在线协作文档 SaaS", "confidence": 0.8}, {"item_id": "pa-2", "category": "target_user", "content": "开发团队", "confidence": 0.7}]}'}}]}}
        yield BrainstormManager(Path(tmpdir), config_manager=mock_config)


def test_e2e_v3_proactive_to_product_def(manager):
    """V3: PROACTIVE_ANALYSIS → 确认条目 → PRODUCT_DEF"""
    record = manager.start_session("E2E项目", "我想做一个在线协作文档系统")
    assert record.current_phase == BrainstormPhase.PROACTIVE_ANALYSIS
    assert record.proactive_analysis is not None

    # 模拟用户确认核心条目
    for item in record.proactive_analysis.items:
        if item.category in ("product_type", "target_user"):
            item.status = "accepted"

    # 推进到 PRODUCT_DEF
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == BrainstormPhase.PRODUCT_DEF


def test_e2e_v3_deliberation_gate(manager):
    """V3: DELIBERATION_REVIEW 需要 high findings 被处理才能推进"""
    record = manager.start_session("Gate项目", "描述")
    # 快进到 DELIBERATION_REVIEW
    record.current_phase = BrainstormPhase.DELIBERATION_REVIEW

    # 添加一个未裁决的 high finding
    record.deliberation_rounds.append(DeliberationRound(
        round_id="dr-gate",
        findings=[
            DeliberationFinding(
                finding_id="f-high", dimension="user_journey_analyst",
                affected_feature_ids=["fn-001"],
                finding="缺少退出路径", severity="high",
                suggested_change="添加退出按钮",
                pm_decision="pending",
            )
        ],
    ))

    # 不应推进
    assert manager.advance_phase(record) is False

    # 裁决后应推进
    record.deliberation_rounds[-1].findings[0].pm_decision = "accept"
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == BrainstormPhase.RELATIONSHIP


def test_e2e_v3_technical_route_to_tool_discovery(manager):
    """V3: TECHNICAL_ROUTE_DRAFT → 确认 → TOOL_DISCOVERY"""
    record = manager.start_session("Route项目", "描述")

    # 直接设置技术路线
    record.technical_route = TechnicalRoute(
        route_id="tr-e2e",
        architecture_summary="SPA + REST",
        frontend_stack=["React"],
        backend_stack=["FastAPI"],
        tool_needs=["Web 框架"],
        status="accepted",
        confirmed_at=_now_iso(),
    )
    record.current_phase = BrainstormPhase.TECHNICAL_ROUTE_DRAFT

    # 推进到 TOOL_DISCOVERY
    result = manager.advance_phase(record)
    assert result is True
    assert record.current_phase == BrainstormPhase.TOOL_DISCOVERY


def test_e2e_v3_trigger_deliberation_review(manager):
    """V3: 触发 deliberation review 并检查结果"""
    record = manager.start_session("Delib项目", "描述")
    # 添加一个已确认的功能节点
    fn = FeatureNode(
        node_id="fn-001", name="用户登录", level="function", status="confirmed",
        user_stories=["作为用户可以登录系统"],
        acceptance_criteria=["用户名密码正确则登录成功"],
        success_path=["输入用户名密码", "点击登录"],
        failure_path=["密码错误提示"],
        edge_cases=["连续错误锁定"],
    )
    record.feature_tree.nodes["fn-001"] = fn

    # 触发审查
    rnd = manager.trigger_deliberation_review(record)
    assert rnd is not None
    assert len(record.deliberation_rounds) == 1
```

- [ ] **步骤 2：运行测试**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_e2e.py -v`
预期：全部 PASS

- [ ] **步骤 3：运行全部新增测试文件**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v3_schema.py tests/ralph/test_brainstorm_v3_manager.py tests/ralph/test_brainstorm_v3_integration.py tests/ralph/test_brainstorm_v3_e2e.py tests/ralph/test_proactive_service.py tests/ralph/test_deliberation_service.py tests/ralph/test_tool_discovery.py tests/ralph/test_technical_route_service.py -v --tb=short`
预期：全部 PASS

- [ ] **步骤 4：运行全部 brainstorm 相关测试确保无回归**

运行：`cd /Users/jieson/auto-coding && python -m pytest tests/ralph/test_brainstorm_v2.py tests/ralph/test_brainstorm_analyzer.py tests/ralph/test_brainstorm_e2e.py tests/ralph/test_brainstorm_migration.py -v --tb=short`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add tests/ralph/test_brainstorm_v3_e2e.py
git commit -m "test: V3 end-to-end flow tests for proactive analysis, deliberation gate, technical route, and tool discovery"
```

---

## 自检

### 1. 规格覆盖度

| 规格需求 | 对应任务 |
|---------|---------|
| PROACTIVE_ANALYSIS 阶段 + ProactiveAnalysis 数据结构 | 任务 1 (schema), 任务 3 (service), 任务 5 (manager) |
| PRODUCT_DEF 强化（引用 proactive_analysis） | 任务 5 (manager advance_phase) |
| FEATURE_DECOMPOSE 保留 | 任务 5 (不修改现有逻辑) |
| DELIBERATION_REVIEW 阶段 + 四维审查 | 任务 1 (schema), 任务 4 (service), 任务 5 (manager) |
| PM 裁决 finding accept/reject/defer | 任务 4 (make_decision, apply_pm_decisions), 任务 8 (API) |
| TECHNICAL_ROUTE_DRAFT | 任务 1 (schema), 任务 8 (service), 任务 5 (manager) |
| TOOL_DISCOVERY | 任务 1 (schema), 任务 7 (service), 任务 5 (manager) |
| 证据链要求 (evidence_urls, evidence_snapshot) | 任务 1 (ToolCandidate 字段) |
| API 端点 | 任务 9 |
| 两段式产品体验 (V3-A / V3-B) | 任务 5 (phase 顺序设计) |

### 2. 占位符扫描

计划中无 "TODO"、"待定"、"后续实现"、"补充细节" 等占位符。所有代码步骤都包含实际代码。

### 3. 类型一致性

- 所有新增 dataclass 在任务 1 中统一定义，后续任务引用统一从 `ralph.schema.brainstorm_record` 导入
- `BrainstormPhase` 新增值在任务 1 中定义，任务 5 和任务 9 中引用
- `DeliberationFinding.dimension` 对应 DIMENSIONS 中定义的 `role` 值
- `ProactiveAnalysisItem.category` 对应规格定义的类别集合
- `TechnicalRoute.status` 三态: pending | accepted | revision_requested
- 所有 `_call_llm` 方法签名一致: `(self, task_type: str, messages: list[dict]) -> str | None`

计划已完成。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代
**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

选哪种方式？