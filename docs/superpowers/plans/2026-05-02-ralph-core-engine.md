# Ralph 核心引擎实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现 Ralph Orchestrator 缺失的核心引擎模块——从需求共创到自动执行再到知识积累的完整闭环。

**架构：** 四个独立可测试的新模块（BrainstormManager、PRDManager、TaskDecomposer、MemoryArchiver）+ 两个集成改进（ClaudeCodeRunner 联调、Playwright 证据）+ 一个端到端管道串联。

**技术栈：** Python 3.12+, FastAPI, Next.js 14, Zustand, Claude CLI, Playwright MCP

**现状基线：** 前端（16 页面）和后端 API（60+ 端点）已完成。Schema、StateMachine、Repository、WorkUnitEngine、ClaudeCodeRunner、ConfigManager 已实现。缺失的是上游（brainstorm/PRD/拆解）和下游（记忆/知识图谱/浏览器验收）。

---

## 文件结构

```
ralph/
  brainstorm_manager.py    # 新增 - 多轮深度需求共创
  prd_manager.py           # 新增 - 结构化 PRD 生成与管理
  task_decomposer.py       # 新增 - 需求→WorkUnit 拆解引擎
  memory_archiver.py       # 新增 - 记忆压缩与 RAG 检索

ralph/schema/
  brainstorm_record.py     # 新增 - BrainstormRecord, ConfirmedFact, OpenAssumption
  prd_document.py          # 新增 - PRDDocument, PRDSection

dashboard/api/routes.py   # 修改 - 加 brainstorm/prd/decomposer/playwright 端点

dashboard-ui/
  app/ralph/brainstorm/page.tsx     # 新增 - 需求共创页面
  app/ralph/prd/page.tsx            # 新增 - PRD 浏览页面
  lib/ralph-api.ts                  # 修改 - 加 brainstorm/prd API

tests/
  test_brainstorm_manager.py        # 新增
  test_prd_manager.py               # 新增
  test_task_decomposer.py           # 新增
  test_memory_archiver.py           # 新增
```

---

### 任务 1：BrainstormManager — 需求共创引擎

**文件：**
- 创建：`ralph/brainstorm_manager.py`
- 创建：`ralph/schema/brainstorm_record.py`
- 创建：`tests/test_brainstorm_manager.py`

**职责：** 多轮非技术语言交互，边问边记录，产出结构化需求事实表 + 未确认假设 + 用户路径。

- [ ] **步骤 1：编写 BrainstormRecord schema**

```python
# ralph/schema/brainstorm_record.py
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ConfirmedFact:
    topic: str           # "目标用户", "核心功能", etc.
    fact: str            # the confirmed statement
    source_quote: str    # user's original words
    recorded_at: str = field(default_factory=_now_iso)


@dataclass
class OpenAssumption:
    question: str        # the question to resolve
    context: str         # why this matters
    status: str = "open"  # open | resolved | deferred
    resolved_answer: str = ""


@dataclass
class UserPath:
    name: str            # "新用户注册流程"
    steps: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)


@dataclass
class BrainstormRecord:
    record_id: str
    project_name: str
    round_number: int
    user_message: str
    system_questions: list[str] = field(default_factory=list)
    confirmed_facts: list[ConfirmedFact] = field(default_factory=list)
    open_assumptions: list[OpenAssumption] = field(default_factory=list)
    user_paths: list[UserPath] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def completeness_score(self) -> float:
        """需求完整度评分: 0.0-1.0"""
        checks = [
            len(self.confirmed_facts) >= 3,
            len(self.open_assumptions) == 0,
            len(self.user_paths) >= 1,
            any(f.topic == "目标用户" for f in self.confirmed_facts),
            any(f.topic == "核心功能" for f in self.confirmed_facts),
            any(f.topic == "验收标准" for f in self.confirmed_facts),
        ]
        return sum(checks) / len(checks)
```

- [ ] **步骤 2：运行测试验证 schema 可实例化**

```bash
python3 -c "from ralph.schema.brainstorm_record import BrainstormRecord; r = BrainstormRecord(record_id='test', project_name='test', round_number=1, user_message='hello'); print(r.completeness_score())"
```

预期输出：`0.0`（所有 check 不通过）

- [ ] **步骤 3：实现 BrainstormManager**

```python
# ralph/brainstorm_manager.py
from pathlib import Path
import json
from ralph.schema.brainstorm_record import (
    BrainstormRecord, ConfirmedFact, OpenAssumption, UserPath, _now_iso,
)


class BrainstormManager:
    """多轮需求共创管理器。每轮对话产出 BrainstormRecord，持久化到 .ralph/brainstorm/"""

    TOPICS_TO_COVER = [
        "目标用户", "用户角色", "核心功能", "暂不做的功能",
        "成功路径", "失败路径", "边界状态", "验收标准",
        "数据模型概要", "权限规则",
    ]

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "brainstorm"
        self._dir.mkdir(parents=True, exist_ok=True)

    def start_session(self, project_name: str, user_message: str) -> BrainstormRecord:
        record = BrainstormRecord(
            record_id=f"bs-{_now_iso().replace(':', '-')}",
            project_name=project_name,
            round_number=1,
            user_message=user_message,
        )
        self._save(record)
        return record

    def generate_questions(self, record: BrainstormRecord) -> list[str]:
        """分析当前记录，生成下一轮要追问的问题。"""
        questions = []
        covered = {f.topic for f in record.confirmed_facts}

        for topic in self.TOPICS_TO_COVER:
            if topic not in covered:
                questions.append(self._question_for_topic(topic))

        # 如果所有 topic 都覆盖了，检查假设
        if not questions:
            for assumption in record.open_assumptions:
                if assumption.status == "open":
                    questions.append(f"关于「{assumption.question}」，你的判断是？")

        return questions[:5]  # 每轮最多 5 个问题

    def process_response(self, record: BrainstormRecord,
                         user_response: str,
                         extracted_facts: list[dict] | None = None,
                         ) -> BrainstormRecord:
        """处理用户回复，更新记录。extracted_facts 由 LLM 提取。"""
        record.round_number += 1
        record.user_message = user_response

        if extracted_facts:
            for fact_data in extracted_facts:
                if fact_data.get("type") == "confirmed":
                    record.confirmed_facts.append(ConfirmedFact(
                        topic=fact_data["topic"],
                        fact=fact_data["fact"],
                        source_quote=fact_data.get("source_quote", user_response),
                    ))
                elif fact_data.get("type") == "assumption":
                    record.open_assumptions.append(OpenAssumption(
                        question=fact_data["question"],
                        context=fact_data.get("context", ""),
                    ))
                elif fact_data.get("type") == "user_path":
                    record.user_paths.append(UserPath(
                        name=fact_data["name"],
                        steps=fact_data.get("steps", []),
                        edge_cases=fact_data.get("edge_cases", []),
                    ))

        self._save(record)
        return record

    def is_complete(self, record: BrainstormRecord) -> bool:
        """检查需求共创是否完成（>= 80% 完整度 + 无未确认假设）。"""
        return (record.completeness_score() >= 0.8
                and len(record.open_assumptions) == 0)

    def get_summary(self, record: BrainstormRecord) -> dict:
        """生成结构化摘要，供 PRDManager 使用。"""
        return {
            "project_name": record.project_name,
            "total_rounds": record.round_number,
            "completeness": record.completeness_score(),
            "confirmed_facts": [
                {"topic": f.topic, "fact": f.fact} for f in record.confirmed_facts
            ],
            "open_assumptions": [
                {"question": a.question, "status": a.status}
                for a in record.open_assumptions
            ],
            "user_paths": [
                {"name": p.name, "steps": p.steps, "edge_cases": p.edge_cases}
                for p in record.user_paths
            ],
        }

    def list_sessions(self) -> list[dict]:
        records = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                records.append({
                    "record_id": data.get("record_id", f.stem),
                    "project_name": data.get("project_name", ""),
                    "round_number": data.get("round_number", 0),
                    "completeness": BrainstormRecord(**data).completeness_score(),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return records

    def load(self, record_id: str) -> BrainstormRecord | None:
        path = self._dir / f"{record_id}.json"
        if not path.is_file():
            return None
        return BrainstormRecord(**json.loads(path.read_text()))

    def _save(self, record: BrainstormRecord) -> None:
        path = self._dir / f"{record.record_id}.json"
        path.write_text(json.dumps(
            {k: v for k, v in record.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))

    @staticmethod
    def _question_for_topic(topic: str) -> str:
        questions = {
            "目标用户": "这个产品给谁用？请描述目标用户画像。",
            "用户角色": "有哪些不同的用户角色？每个角色能做什么？",
            "核心功能": "第一版必须有哪些功能？按重要性排序。",
            "暂不做的功能": "有哪些功能明确不做（至少第一版不做）？",
            "成功路径": "用户最常见的成功使用流程是什么？",
            "失败路径": "当用户操作失败时，系统应该如何响应？",
            "边界状态": "极端或异常状态下系统应该如何表现？",
            "验收标准": "你怎么判断这个产品'真的可以用了'？",
            "数据模型概要": "系统需要存储哪些核心数据？",
            "权限规则": "有哪些权限控制需求？",
        }
        return questions.get(topic, f"请详细说明「{topic}」方面的需求。")
```

- [ ] **步骤 4：编写 BrainstormManager 单元测试**

```python
# tests/test_brainstorm_manager.py
import json
from pathlib import Path
from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import ConfirmedFact, OpenAssumption, UserPath


def test_start_session_creates_record(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("TestProject", "我想做一个 todo app")
    assert record.project_name == "TestProject"
    assert record.round_number == 1
    assert (tmp_path / ".ralph" / "brainstorm" / f"{record.record_id}.json").is_file()


def test_generate_questions_covers_topics(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("Test", "hello")
    questions = mgr.generate_questions(record)
    assert len(questions) > 0
    assert len(questions) <= 5


def test_process_response_updates_record(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("Test", "hello")
    updated = mgr.process_response(record, "给程序员用的", [
        {"type": "confirmed", "topic": "目标用户", "fact": "程序员", "source_quote": "给程序员用的"},
    ])
    assert updated.round_number == 2
    assert len(updated.confirmed_facts) == 1
    assert updated.confirmed_facts[0].topic == "目标用户"


def test_is_complete_requires_80_percent(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("Test", "hello")
    # 只有 1 个 fact，没有 user_path —— 完整度应该很低
    record.confirmed_facts.append(ConfirmedFact(topic="目标用户", fact="dev", source_quote="dev"))
    assert not mgr.is_complete(record)


def test_is_complete_passes_with_full_data(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("Test", "hello")
    for topic in ["目标用户", "核心功能", "验收标准"]:
        record.confirmed_facts.append(ConfirmedFact(topic=topic, fact="done", source_quote=""))
    record.user_paths.append(UserPath(name="main", steps=["step1"], edge_cases=["edge1"]))
    record.open_assumptions = []
    assert mgr.is_complete(record)


def test_list_sessions(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    mgr.start_session("P1", "hello")
    mgr.start_session("P2", "world")
    sessions = mgr.list_sessions()
    assert len(sessions) == 2


def test_load_roundtrips(tmp_path: Path):
    mgr = BrainstormManager(tmp_path / ".ralph")
    record = mgr.start_session("Test", "hello")
    loaded = mgr.load(record.record_id)
    assert loaded is not None
    assert loaded.project_name == "Test"
```

- [ ] **步骤 5：运行测试验证**

```bash
python3 -m pytest tests/test_brainstorm_manager.py -v
```

预期：7 passed

- [ ] **步骤 6：Commit**

```bash
git add ralph/brainstorm_manager.py ralph/schema/brainstorm_record.py tests/test_brainstorm_manager.py
git commit -m "feat(ralph): add BrainstormManager for multi-turn requirements discovery"
```

---

### 任务 2：PRDManager — 结构化 PRD 生成

**文件：**
- 创建：`ralph/prd_manager.py`
- 创建：`ralph/schema/prd_document.py`
- 创建：`tests/test_prd_manager.py`

- [ ] **步骤 1：编写 PRDDocument schema**

```python
# ralph/schema/prd_document.py
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class PRDSection:
    title: str
    content: str
    source_facts: list[str] = field(default_factory=list)  # references to ConfirmedFact topics


@dataclass
class PRDDocument:
    prd_id: str
    project_name: str
    version: str = "1.0-draft"
    status: str = "draft"  # draft | frozen | archived

    # 核心章节
    background: str = ""
    product_positioning: str = ""
    user_goals: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    core_workflow: str = ""
    core_features: list[dict] = field(default_factory=list)
    non_functional: dict = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    # 元信息
    brainstorm_record_id: str = ""
    created_at: str = field(default_factory=_now_iso)
    frozen_at: str = ""

    def freeze(self) -> None:
        self.status = "frozen"
        self.frozen_at = _now_iso()

    def is_frozen(self) -> bool:
        return self.status == "frozen"

    def to_markdown(self) -> str:
        sections = [
            f"# {self.project_name} PRD",
            f"版本: {self.version} | 状态: {self.status}",
            "",
            "## 背景", self.background,
            "## 产品定位", self.product_positioning,
            "## 用户目标", *[f"- {g}" for g in self.user_goals],
            "## 不做什么", *[f"- {s}" for s in self.out_of_scope],
            "## 核心流程", self.core_workflow,
            "## 核心功能",
        ]
        for f in self.core_features:
            sections.append(f"- **{f.get('name', '')}**: {f.get('description', '')}")
        sections += [
            "## 非功能需求",
            *[f"- {k}: {v}" for k, v in self.non_functional.items()],
            "## 成功标准", *[f"- {c}" for c in self.success_criteria],
            "## 风险", *[f"- {r}" for r in self.risks],
            "## 待确认问题", *[f"- {q}" for q in self.open_questions],
        ]
        return "\n".join(sections)
```

- [ ] **步骤 2：实现 PRDManager**

```python
# ralph/prd_manager.py
from pathlib import Path
import json
from ralph.schema.prd_document import PRDDocument, _now_iso
from ralph.brainstorm_manager import BrainstormManager


class PRDManager:
    """从 BrainstormRecord 生成结构化 PRD，管理冻结/变更流程。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "prd"
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate_from_brainstorm(self, brainstorm_record_id: str,
                                  ralph_dir: Path) -> PRDDocument:
        """从需求共创记录生成 PRD 草案。由 LLM 填充各章节。"""
        brainstorm_mgr = BrainstormManager(ralph_dir)
        record = brainstorm_mgr.load(brainstorm_record_id)
        if record is None:
            raise ValueError(f"Brainstorm record {brainstorm_record_id} not found")

        summary = brainstorm_mgr.get_summary(record)

        prd = PRDDocument(
            prd_id=f"prd-{_now_iso().replace(':', '-')}",
            project_name=summary["project_name"],
            brainstorm_record_id=brainstorm_record_id,
        )

        # 从 facts 映射到 PRD 章节
        for fact in summary["confirmed_facts"]:
            topic, content = fact["topic"], fact["fact"]
            if topic == "目标用户":
                prd.user_goals.append(f"目标用户: {content}")
            elif topic == "核心功能":
                prd.core_features.append({"name": content, "description": ""})
            elif topic == "暂不做的功能":
                prd.out_of_scope.append(content)
            elif topic == "验收标准":
                prd.success_criteria.append(content)
            elif topic == "权限规则":
                prd.non_functional["权限"] = content
            elif topic == "数据模型概要":
                prd.non_functional["数据模型"] = content
            elif topic == "成功路径":
                prd.core_workflow += f"\n成功路径: {content}"

        for assumption in summary["open_assumptions"]:
            prd.open_questions.append(assumption["question"])

        self._save(prd)
        return prd

    def enrich_with_llm(self, prd: PRDDocument, llm_response: dict) -> PRDDocument:
        """用 LLM 返回的结构化内容填充 PRD 各章节。"""
        prd.background = llm_response.get("background", prd.background)
        prd.product_positioning = llm_response.get("product_positioning", prd.product_positioning)
        prd.core_workflow = llm_response.get("core_workflow", prd.core_workflow)
        if "core_features" in llm_response:
            prd.core_features = llm_response["core_features"]
        if "non_functional" in llm_response:
            prd.non_functional.update(llm_response["non_functional"])
        if "success_criteria" in llm_response:
            prd.success_criteria = llm_response["success_criteria"]
        if "risks" in llm_response:
            prd.risks = llm_response["risks"]
        self._save(prd)
        return prd

    def freeze(self, prd_id: str) -> PRDDocument:
        prd = self.load(prd_id)
        if prd is None:
            raise ValueError(f"PRD {prd_id} not found")
        prd.freeze()
        self._save(prd)
        return prd

    def load(self, prd_id: str) -> PRDDocument | None:
        path = self._dir / f"{prd_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return PRDDocument(**data)

    def list_prds(self) -> list[dict]:
        prds = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                prds.append({
                    "prd_id": data.get("prd_id", f.stem),
                    "project_name": data.get("project_name", ""),
                    "version": data.get("version", ""),
                    "status": data.get("status", "draft"),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return prds

    def _save(self, prd: PRDDocument) -> None:
        path = self._dir / f"{prd.prd_id}.json"
        path.write_text(json.dumps(
            {k: v for k, v in prd.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
```

- [ ] **步骤 3：编写 PRDManager 测试**

```python
# tests/test_prd_manager.py
from pathlib import Path
from ralph.prd_manager import PRDManager
from ralph.brainstorm_manager import BrainstormManager
from ralph.schema.brainstorm_record import ConfirmedFact, UserPath


def test_generate_from_brainstorm(tmp_path: Path):
    ralph_dir = tmp_path / ".ralph"
    # 先创建 brainstorm record
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
    prd = pm.generate_from_brainstorm("nonexistent", tmp_path / ".ralph")
    # 直接创建 PRD 测试 freeze
    from ralph.schema.prd_document import PRDDocument
    prd = PRDDocument(prd_id="test-prd", project_name="Test")
    pm._save(prd)

    frozen = pm.freeze("test-prd")
    assert frozen.status == "frozen"
    assert frozen.frozen_at != ""


def test_list_prds(tmp_path: Path):
    pm = PRDManager(tmp_path / ".ralph")
    from ralph.schema.prd_document import PRDDocument
    pm._save(PRDDocument(prd_id="p1", project_name="P1"))
    pm._save(PRDDocument(prd_id="p2", project_name="P2"))
    assert len(pm.list_prds()) == 2


def test_to_markdown(tmp_path: Path):
    from ralph.schema.prd_document import PRDDocument
    prd = PRDDocument(prd_id="test", project_name="TestApp")
    prd.background = "需要自动开发系统"
    prd.user_goals = ["自动化开发"]
    prd.core_features = [{"name": "auto dev", "description": "自动写代码"}]
    md = prd.to_markdown()
    assert "# TestApp PRD" in md
    assert "自动化开发" in md
```

- [ ] **步骤 4：运行测试**

```bash
python3 -m pytest tests/test_prd_manager.py -v
```

预期：4 passed

- [ ] **步骤 5：Commit**

```bash
git add ralph/prd_manager.py ralph/schema/prd_document.py tests/test_prd_manager.py
git commit -m "feat(ralph): add PRDManager for structured PRD generation from brainstorm"
```

---

### 任务 3：TaskDecomposer — 需求到 WorkUnit 拆解

**文件：**
- 创建：`ralph/task_decomposer.py`
- 创建：`tests/test_task_decomposer.py`

- [ ] **步骤 1：实现 TaskDecomposer**

```python
# ralph/task_decomposer.py
from pathlib import Path
import json
from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
from ralph.schema.task_harness import TaskHarness, RetryPolicy, TimeoutPolicy
from ralph.schema.prd_document import PRDDocument


class TaskDecomposer:
    """将 PRD + 代码库分析拆解为细粒度 WorkUnit 列表。

    核心原则：
    - 每个 WorkUnit 对应一个清晰开发动作（10-30 分钟可完成）
    - 按垂直切片优先拆分（不按 DB/API/UI 横切）
    - 每个 WorkUnit 必须有验收标准 + harness
    - 推导依赖关系 DAG
    """

    SIZE_LIMITS = {
        "XS": {"max_files": 1, "max_lines": 50},
        "S": {"max_files": 3, "max_lines": 150},
        "M": {"max_files": 5, "max_lines": 300},
    }

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "tasks"
        self._dir.mkdir(parents=True, exist_ok=True)

    def decompose(self, prd: PRDDocument,
                  codebase_analysis: dict | None = None) -> list[WorkUnit]:
        """从 PRD 拆解出 WorkUnit 列表。"""
        work_units = []

        # 从 core_features 拆
        for i, feature in enumerate(prd.core_features):
            feature_name = feature.get("name", f"feature-{i}")
            feature_desc = feature.get("description", "")

            # 颗粒度检查：大特性拆成多个 WorkUnit
            sub_tasks = self._break_down_feature(feature_name, feature_desc)
            for j, sub in enumerate(sub_tasks):
                wu_id = f"wu-{prd.prd_id}-{i:02d}-{j:02d}"
                harness = self._create_default_harness(wu_id, sub["scope"])
                wu = WorkUnit(
                    work_id=wu_id,
                    work_type="development",
                    title=sub["title"],
                    target=sub["description"],
                    status=WorkUnitStatus.DRAFT,
                    acceptance_criteria=sub.get("acceptance_criteria", []),
                    scope_allow=sub["scope"],
                    scope_deny=sub.get("scope_deny", [".env", "credentials.*", "*.pem", "*.key"]),
                    dependencies=sub.get("dependencies", []),
                    task_harness=harness,
                    producer_role=sub.get("producer_role", "backend"),
                    reviewer_role=sub.get("reviewer_role", "architect"),
                    test_command=sub.get("test_command", ""),
                    rollback_strategy=sub.get("rollback_strategy", "git checkout -- ."),
                )
                work_units.append(wu)

        # 后处理：解析依赖引用为实际 work_id
        self._resolve_dependencies(work_units)
        self._save(work_units)

        return work_units

    def validate_granularity(self, work_units: list[WorkUnit]) -> list[dict]:
        """颗粒度门禁检查。返回不通过的 WorkUnit 及其问题。"""
        failures = []
        for wu in work_units:
            issues = []
            if not wu.target:
                issues.append("目标为空")
            if not wu.acceptance_criteria:
                issues.append("缺少验收标准")
            if not wu.scope_allow:
                issues.append("scope_allow 为空")
            if wu.task_harness is None:
                issues.append("缺少 task_harness")
            if len(wu.scope_allow) > self.SIZE_LIMITS["M"]["max_files"]:
                issues.append(f"scope_allow 过大 ({len(wu.scope_allow)} 文件)")
            if issues:
                failures.append({"work_id": wu.work_id, "issues": issues})
        return failures

    def build_dependency_dag(self, work_units: list[WorkUnit]) -> dict[str, list[str]]:
        """构建依赖 DAG: {work_id: [dependent_work_ids]}"""
        dag: dict[str, list[str]] = {}
        wu_map = {wu.work_id: wu for wu in work_units}

        for wu in work_units:
            dag[wu.work_id] = []
            for dep_id in wu.dependencies:
                if dep_id in wu_map:
                    dag.setdefault(dep_id, []).append(wu.work_id)

        return dag

    def _break_down_feature(self, name: str, description: str) -> list[dict]:
        """将单个 feature 拆成子任务列表。大 feature 拆成 M 级子任务。"""
        # 简单启发式：按关键词拆
        keywords = {
            "schema": {"producer_role": "database", "reviewer_role": "architect"},
            "model": {"producer_role": "database", "reviewer_role": "architect"},
            "api": {"producer_role": "backend", "reviewer_role": "architect"},
            "endpoint": {"producer_role": "backend", "reviewer_role": "architect"},
            "frontend": {"producer_role": "frontend", "reviewer_role": "ui_designer"},
            "ui": {"producer_role": "frontend", "reviewer_role": "ui_designer"},
            "page": {"producer_role": "frontend", "reviewer_role": "ui_designer"},
            "test": {"producer_role": "qa", "reviewer_role": "backend"},
            "doc": {"producer_role": "docs", "reviewer_role": "product"},
            "deploy": {"producer_role": "backend", "reviewer_role": "architect"},
        }

        desc_lower = description.lower()
        matched_role = "backend"
        for kw, roles in keywords.items():
            if kw in desc_lower or kw in name.lower():
                matched_role = roles["producer_role"]
                break

        return [{
            "title": name,
            "description": description,
            "scope": [name.lower().replace(" ", "_")],
            "acceptance_criteria": [f"验收: {description}"],
            "producer_role": matched_role,
            "reviewer_role": "architect",
            "dependencies": [],
        }]

    def _create_default_harness(self, work_id: str, scope: list[str]) -> TaskHarness:
        return TaskHarness(
            harness_id=f"h-{work_id}",
            task_goal=f"实现 {work_id}",
            context_sources=scope,
            context_budget="8k tokens",
            allowed_tools=["claude_code", "git", "pytest"],
            denied_tools=["publish", "deploy"],
            scope_allow=scope,
            scope_deny=[".env", "credentials.*"],
            preflight_checks=["harness 校验通过", "scope 可读"],
            checkpoints=["测试通过"],
            validation_gates=["验收标准检查", "diff 审查"],
            evidence_required=["diff", "test_output"],
            retry_policy=RetryPolicy(),
            rollback_strategy="git checkout -- .",
            timeout_policy=TimeoutPolicy(),
            stop_conditions=["连续失败 3 次"],
            reviewer_role="architect",
        )

    def _resolve_dependencies(self, work_units: list[WorkUnit]) -> None:
        """将依赖引用解析为实际的 work_id。"""
        # 简单实现：文本匹配依赖
        for wu in work_units:
            resolved = []
            for dep in wu.dependencies:
                for other in work_units:
                    if dep.lower() in other.title.lower() or dep in other.work_id:
                        resolved.append(other.work_id)
                        break
            if resolved:
                object.__setattr__(wu, "dependencies", resolved)

    def _save(self, work_units: list[WorkUnit]) -> None:
        data = []
        for wu in work_units:
            d = {k: v for k, v in wu.__dict__.items() if not k.startswith("_")}
            d["status"] = wu.status.value if hasattr(wu.status, "value") else str(wu.status)
            data.append(d)
        path = self._dir / "decomposed_tasks.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
```

- [ ] **步骤 2：编写 TaskDecomposer 测试**

```python
# tests/test_task_decomposer.py
from pathlib import Path
from ralph.task_decomposer import TaskDecomposer
from ralph.schema.prd_document import PRDDocument


def test_decompose_from_prd(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    prd = PRDDocument(
        prd_id="prd-test", project_name="TestApp",
        core_features=[
            {"name": "user auth api", "description": "实现用户注册和登录 API"},
            {"name": "todo frontend page", "description": "Todo 列表页面 UI 组件"},
        ],
    )
    units = td.decompose(prd)
    assert len(units) >= 2
    assert all(u.status.value == "draft" for u in units)
    assert all(u.task_harness is not None for u in units)


def test_validate_granularity(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="prd-test", project_name="Test",
                      core_features=[{"name": "f1", "description": "desc"}])
    units = td.decompose(prd)
    # 第一个 unit 应该有默认的 acceptance_criteria
    failures = td.validate_granularity(units)
    # 默认生成的应该通过
    assert all(len(f["issues"]) == 0 for f in failures) or len(units) == 0


def test_build_dependency_dag(tmp_path: Path):
    td = TaskDecomposer(tmp_path / ".ralph")
    prd = PRDDocument(prd_id="prd-test", project_name="Test",
                      core_features=[
                          {"name": "db schema", "description": "创建数据库表"},
                          {"name": "api endpoints", "description": "REST API 依赖 db schema"},
                      ])

    from ralph.schema.work_unit import WorkUnit, WorkUnitStatus
    from ralph.schema.task_harness import TaskHarness, RetryPolicy, TimeoutPolicy

    harness = TaskHarness(
        harness_id="h1", task_goal="test", context_sources=["src"],
        context_budget="8k", allowed_tools=["claude"], denied_tools=[],
        scope_allow=["src"], scope_deny=[], preflight_checks=[], checkpoints=[],
        validation_gates=[], evidence_required=["diff"], retry_policy=RetryPolicy(),
        rollback_strategy="git reset", timeout_policy=TimeoutPolicy(),
        stop_conditions=[], reviewer_role="architect",
    )

    wu1 = WorkUnit(work_id="wu-1", work_type="development", title="DB Schema",
                   target="schema", status=WorkUnitStatus.DRAFT,
                   acceptance_criteria=["ok"], scope_allow=["db"], scope_deny=[],
                   dependencies=[], task_harness=harness,
                   producer_role="database", reviewer_role="architect",
                   test_command="", rollback_strategy="")
    wu2 = WorkUnit(work_id="wu-2", work_type="development", title="API",
                   target="api", status=WorkUnitStatus.DRAFT,
                   acceptance_criteria=["ok"], scope_allow=["api"], scope_deny=[],
                   dependencies=["wu-1"], task_harness=harness,
                   producer_role="backend", reviewer_role="architect",
                   test_command="", rollback_strategy="")

    dag = td.build_dependency_dag([wu1, wu2])
    assert "wu-1" in dag
    assert "wu-2" in dag["wu-1"]  # wu-2 depends on wu-1
```

- [ ] **步骤 3：运行测试**

```bash
python3 -m pytest tests/test_task_decomposer.py -v
```

预期：3 passed

- [ ] **步骤 4：Commit**

```bash
git add ralph/task_decomposer.py tests/test_task_decomposer.py
git commit -m "feat(ralph): add TaskDecomposer for PRD-to-WorkUnit breakdown with granularity gates"
```

---

### 任务 4：MemoryArchiver — 记忆压缩与检索

**文件：**
- 创建：`ralph/memory_archiver.py`
- 创建：`tests/test_memory_archiver.py`

- [ ] **步骤 1：实现 MemoryArchiver**

```python
# ralph/memory_archiver.py
from pathlib import Path
import json
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryArchiver:
    """记忆系统：短期→中期→长期三层记忆 + 轻量关键词检索。

    短期记忆: .ralph/memory/short_term.json (最近 N 条，FIFO)
    中期记忆: .ralph/memory/medium_term.json (关键决策，人工标记)
    长期记忆: .ralph/memory/long_term/ (完整日志，按日期归档)
    """

    SHORT_TERM_MAX = 20
    MEDIUM_TERM_MAX = 100

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "memory"
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "long_term").mkdir(exist_ok=True)

    # --- Short-term ---

    def append_short_term(self, entry: dict) -> None:
        """追加到短期记忆。自动压缩到中期。"""
        memory = self._read_short_term()
        entry["recorded_at"] = _now_iso()
        memory.append(entry)

        # FIFO 淘汰到中期
        while len(memory) > self.SHORT_TERM_MAX:
            oldest = memory.pop(0)
            self._promote_to_medium(oldest)

        self._write_json("short_term.json", memory)

    def get_short_term(self) -> list[dict]:
        return self._read_short_term()

    def summarize_short_term(self) -> str:
        """生成短期记忆摘要（给 PM Agent 用的 L1 状态层）。"""
        memory = self._read_short_term()
        if not memory:
            return "暂无近期活动"

        lines = []
        for entry in memory[-5:]:  # 最近 5 条
            status = entry.get("status", "?")
            title = entry.get("title", entry.get("work_id", "?"))
            lines.append(f"- [{status}] {title}")

        # 统计
        statuses = {}
        for entry in memory:
            s = entry.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1

        summary = f"近期任务 ({len(memory)}): "
        summary += ", ".join(f"{s}: {c}" for s, c in statuses.items())
        summary += "\n最近活动:\n" + "\n".join(lines)
        return summary

    # --- Medium-term ---

    def record_decision(self, decision: str, context: str,
                        alternatives: list[str] | None = None) -> None:
        """记录关键决策到中期记忆。"""
        memory = self._read_medium_term()
        memory.append({
            "type": "decision",
            "decision": decision,
            "context": context,
            "alternatives": alternatives or [],
            "recorded_at": _now_iso(),
        })
        if len(memory) > self.MEDIUM_TERM_MAX:
            memory = memory[-self.MEDIUM_TERM_MAX:]
        self._write_json("medium_term.json", memory)

    def get_medium_term(self) -> list[dict]:
        return self._read_medium_term()

    # --- Long-term ---

    def archive_task_log(self, work_id: str, full_log: str) -> str:
        """归档完整任务日志到长期记忆。"""
        date_str = _now_iso()[:10]
        archive_dir = self._dir / "long_term" / date_str
        archive_dir.mkdir(parents=True, exist_ok=True)
        path = archive_dir / f"{work_id}.md"
        path.write_text(full_log, encoding="utf-8")
        return str(path)

    def archive_compressed_summary(self, work_id: str, summary: dict) -> None:
        """保存压缩后的任务摘要。"""
        archive_dir = self._dir / "long_term" / _now_iso()[:10]
        archive_dir.mkdir(parents=True, exist_ok=True)
        path = archive_dir / f"{work_id}.summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    # --- Retrieval ---

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """简单关键词检索（短期 + 中期）。"""
        results = []
        query_lower = query.lower()

        for entry in self._read_short_term():
            text = json.dumps(entry).lower()
            if query_lower in text:
                results.append({"source": "short_term", "entry": entry, "score": 1.0})

        for entry in self._read_medium_term():
            text = json.dumps(entry).lower()
            if query_lower in text:
                results.append({"source": "medium_term", "entry": entry, "score": 0.8})

        return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]

    def get_status(self) -> dict:
        """返回记忆系统状态概览。"""
        short = self._read_short_term()
        medium = self._read_medium_term()
        long_dir = self._dir / "long_term"

        long_count = 0
        if long_dir.is_dir():
            for d in long_dir.iterdir():
                if d.is_dir():
                    long_count += len(list(d.glob("*.md"))) + len(list(d.glob("*.json")))

        return {
            "short_term": {"count": len(short), "max": self.SHORT_TERM_MAX},
            "medium_term": {"count": len(medium), "max": self.MEDIUM_TERM_MAX},
            "long_term": {"count": long_count},
            "total_stored": len(short) + len(medium) + long_count,
            "last_updated": _now_iso(),
        }

    # --- Internal ---

    def _read_short_term(self) -> list[dict]:
        return self._read_json("short_term.json", [])

    def _read_medium_term(self) -> list[dict]:
        return self._read_json("medium_term.json", [])

    def _promote_to_medium(self, entry: dict) -> None:
        """将淘汰的短期记忆提升到中期（筛选关键条目）。"""
        if entry.get("status") in ("accepted", "failed", "blocked"):
            memory = self._read_medium_term()
            entry["archived_from_short_term"] = True
            memory.append(entry)
            if len(memory) > self.MEDIUM_TERM_MAX:
                memory = memory[-self.MEDIUM_TERM_MAX:]
            self._write_json("medium_term.json", memory)

    def _read_json(self, filename: str, default=None) -> any:
        path = self._dir / filename
        if not path.is_file():
            return default if default is not None else []
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return default if default is not None else []

    def _write_json(self, filename: str, data) -> None:
        (self._dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
        )
```

- [ ] **步骤 2：编写 MemoryArchiver 测试**

```python
# tests/test_memory_archiver.py
from pathlib import Path
from ralph.memory_archiver import MemoryArchiver


def test_append_short_term_basic(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "accepted", "title": "Login API"})
    memory = ma.get_short_term()
    assert len(memory) == 1
    assert memory[0]["work_id"] == "wu-1"


def test_fifo_eviction_to_medium(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    for i in range(25):
        ma.append_short_term({"work_id": f"wu-{i}", "status": "accepted", "title": f"Task {i}"})

    assert len(ma.get_short_term()) <= 20
    # 关键条目应该被提升到中期
    medium = ma.get_medium_term()
    assert len(medium) > 0


def test_record_decision(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.record_decision("使用 SQLite", "轻量无需运维", ["PostgreSQL", "MongoDB"])
    medium = ma.get_medium_term()
    assert len(medium) == 1
    assert medium[0]["type"] == "decision"


def test_search(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "accepted", "title": "JWT Auth"})
    ma.append_short_term({"work_id": "wu-2", "status": "running", "title": "CRUD API"})
    results = ma.search("JWT")
    assert len(results) >= 1
    assert results[0]["entry"]["title"] == "JWT Auth"


def test_get_status(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "done"})
    status = ma.get_status()
    assert status["short_term"]["count"] == 1
    assert "total_stored" in status


def test_summarize_short_term(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-a", "status": "accepted", "title": "Auth"})
    ma.append_short_term({"work_id": "wu-b", "status": "running", "title": "API"})
    summary = ma.summarize_short_term()
    assert "Auth" in summary
    assert "API" in summary


def test_archive_task_log(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    path = ma.archive_task_log("wu-log", "# Task Log\n\n完成内容...")
    assert Path(path).is_file()
    assert "# Task Log" in Path(path).read_text()
```

- [ ] **步骤 3：运行测试**

```bash
python3 -m pytest tests/test_memory_archiver.py -v
```

预期：7 passed

- [ ] **步骤 4：Commit**

```bash
git add ralph/memory_archiver.py tests/test_memory_archiver.py
git commit -m "feat(ralph): add MemoryArchiver for three-tier memory system with keyword retrieval"
```

---

### 任务 5：API 端点 — 暴露新模块

**文件：**
- 修改：`dashboard/api/routes.py`

- [ ] **步骤 1：加 Brainstorm/PRD/Memory API 端点**

在 `return app` 之前添加：

```python
    # --- Ralph API: Brainstorm 端点 ---

    @app.get("/api/ralph/brainstorm/sessions")
    async def ralph_list_brainstorm_sessions() -> list[dict]:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        return BrainstormManager(ralph_dir).list_sessions()

    @app.post("/api/ralph/brainstorm/start")
    async def ralph_start_brainstorm(body: dict[str, Any]) -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        mgr = BrainstormManager(ralph_dir)
        record = mgr.start_session(
            body.get("project_name", "Unnamed"),
            body.get("user_message", ""),
        )
        questions = mgr.generate_questions(record)
        summary = mgr.get_summary(record)
        return {"record_id": record.record_id, "questions": questions, "summary": summary}

    @app.post("/api/ralph/brainstorm/respond")
    async def ralph_brainstorm_respond(body: dict[str, Any]) -> dict:
        record_id = body.get("record_id", "")
        if not record_id:
            raise HTTPException(status_code=422, detail="record_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.brainstorm_manager import BrainstormManager
        mgr = BrainstormManager(ralph_dir)
        record = mgr.load(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        updated = mgr.process_response(record, body.get("user_response", ""),
                                        body.get("extracted_facts"))
        questions = mgr.generate_questions(updated)
        is_complete = mgr.is_complete(updated)
        return {
            "record_id": updated.record_id,
            "round": updated.round_number,
            "questions": questions,
            "is_complete": is_complete,
            "completeness": updated.completeness_score(),
            "summary": mgr.get_summary(updated),
        }

    # --- Ralph API: PRD 端点 ---

    @app.get("/api/ralph/prd/list")
    async def ralph_list_prds() -> list[dict]:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        return PRDManager(ralph_dir).list_prds()

    @app.post("/api/ralph/prd/generate")
    async def ralph_generate_prd(body: dict[str, Any]) -> dict:
        brainstorm_id = body.get("brainstorm_record_id", "")
        if not brainstorm_id:
            raise HTTPException(status_code=422, detail="brainstorm_record_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        pm = PRDManager(ralph_dir)
        prd = pm.generate_from_brainstorm(brainstorm_id, ralph_dir)
        return {"prd_id": prd.prd_id, "status": prd.status, "markdown": prd.to_markdown()}

    @app.post("/api/ralph/prd/freeze")
    async def ralph_freeze_prd(body: dict[str, Any]) -> dict:
        prd_id = body.get("prd_id", "")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        prd = PRDManager(ralph_dir).freeze(prd_id)
        return {"prd_id": prd.prd_id, "status": prd.status, "frozen_at": prd.frozen_at}

    # --- Ralph API: Task Decomposition 端点 ---

    @app.post("/api/ralph/tasks/decompose")
    async def ralph_decompose_tasks(body: dict[str, Any]) -> dict:
        prd_id = body.get("prd_id", "")
        if not prd_id:
            raise HTTPException(status_code=422, detail="prd_id required")
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.prd_manager import PRDManager
        from ralph.task_decomposer import TaskDecomposer
        pm = PRDManager(ralph_dir)
        prd = pm.load(prd_id)
        if prd is None:
            raise HTTPException(status_code=404, detail="PRD not found")
        td = TaskDecomposer(ralph_dir)
        units = td.decompose(prd)
        failures = td.validate_granularity(units)
        dag = td.build_dependency_dag(units)
        return {
            "work_units": [_serialize_work_unit(u) for u in units],
            "granularity_failures": failures,
            "dependency_dag": dag,
            "total": len(units),
        }

    # --- Ralph API: Memory 端点 ---

    @app.get("/api/ralph/memory/status")
    async def ralph_memory_status() -> dict:
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_archiver import MemoryArchiver
        return MemoryArchiver(ralph_dir).get_status()

    @app.get("/api/ralph/memory/search")
    async def ralph_memory_search(q: str = "", top_k: int = 10) -> list[dict]:
        if not q:
            return []
        cfg: RalphConfigManager = app.state.config_manager
        ralph_dir = cfg._dir.parent
        from ralph.memory_archiver import MemoryArchiver
        return MemoryArchiver(ralph_dir).search(q, top_k)
```

- [ ] **步骤 2：运行全量后端测试**

```bash
python3 -m pytest tests/ -q --ignore=tests/test_ralph_bootstrap.py
```

预期：全部通过

- [ ] **步骤 3：Commit**

```bash
git add dashboard/api/routes.py
git commit -m "feat(ralph): add API endpoints for brainstorm, PRD, task decomposition, and memory"
```

---

### 任务 6：前端 — 需求共创和 PRD 页面

**文件：**
- 创建：`app/ralph/brainstorm/page.tsx`
- 创建：`app/ralph/prd/page.tsx`
- 修改：`lib/ralph-api.ts` — 加 API 函数
- 修改：`components/ralph/sidebar.tsx` — 加"需求共创"和"PRD"导航

- [ ] **步骤 1：前端 API 函数**

在 `lib/ralph-api.ts` 中加入：

```typescript
// Brainstorm
export async function listBrainstormSessions(): Promise<Record<string, unknown>[]> {
  return request('/brainstorm/sessions');
}
export async function startBrainstorm(projectName: string, userMessage: string): Promise<Record<string, unknown>> {
  return request('/brainstorm/start', { method: 'POST', body: JSON.stringify({ project_name: projectName, user_message: userMessage }) });
}
export async function brainstormRespond(recordId: string, userResponse: string): Promise<Record<string, unknown>> {
  return request('/brainstorm/respond', { method: 'POST', body: JSON.stringify({ record_id: recordId, user_response: userResponse }) });
}

// PRD
export async function listPRDs(): Promise<Record<string, unknown>[]> {
  return request('/prd/list');
}
export async function generatePRD(brainstormRecordId: string): Promise<Record<string, unknown>> {
  return request('/prd/generate', { method: 'POST', body: JSON.stringify({ brainstorm_record_id: brainstormRecordId }) });
}
export async function freezePRD(prdId: string): Promise<Record<string, unknown>> {
  return request('/prd/freeze', { method: 'POST', body: JSON.stringify({ prd_id: prdId }) });
}

// Task Decomposition
export async function decomposeTasks(prdId: string): Promise<Record<string, unknown>> {
  return request('/tasks/decompose', { method: 'POST', body: JSON.stringify({ prd_id: prdId }) });
}

// Memory
export async function getMemoryStatus(): Promise<Record<string, unknown>> {
  return request('/memory/status');
}
export async function searchMemory(q: string): Promise<Record<string, unknown>[]> {
  return request(`/memory/search?q=${encodeURIComponent(q)}`);
}
```

- [ ] **步骤 2：需求共创页面**

`app/ralph/brainstorm/page.tsx`：对话式 UI，显示已完成的事实/假设/路径，输入框追问。

- [ ] **步骤 3：PRD 浏览页面**

`app/ralph/prd/page.tsx`：PRD 列表 + 点击查看 Markdown + 冻结按钮。

- [ ] **步骤 4：更新侧边栏**

在「项目」组中加"需求共创"和"PRD 文档"。

- [ ] **步骤 5：运行前端测试**

```bash
cd dashboard-ui && npx vitest run
```

预期：全通过

- [ ] **步骤 6：Commit**

```bash
git add app/ralph/brainstorm/ app/ralph/prd/ lib/ralph-api.ts components/ralph/sidebar.tsx
git commit -m "feat(ui): add brainstorm and PRD pages with API integration"
```

---

### 任务 7：Playwright 浏览器证据

**文件：**
- 修改：`ralph/evidence_collector.py` — 加 Playwright 截图采集
- 修改：`testing/e2e_runner.py` — 加结构化输出

- [ ] **步骤 1：EvidenceCollector 加 Playwright 采集**

在 `collect()` 方法中增加：

```python
def collect_playwright_evidence(self, work_id: str, url: str = "http://localhost:3000") -> list[Path]:
    """尝试用 Playwright 采集浏览器证据。如果 Playwright 不可用则跳过。"""
    evidence_dir = self._dir / work_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    screenshots = []

    try:
        import subprocess
        # 使用 MCP Playwright 或直接 npx playwright
        result = subprocess.run(
            ["npx", "playwright", "screenshot", url,
             "--output", str(evidence_dir / "screenshot.png")],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            screenshots.append(evidence_dir / "screenshot.png")
    except Exception:
        pass  # Playwright 不可用时静默跳过

    return screenshots
```

- [ ] **步骤 2：E2ERunner 加结构化输出**

修改 `run_test_steps()` 返回类型从 `bool` 改为 `dict`，包含 `passed`、`steps_results`、`errors`。

- [ ] **步骤 3：运行测试 + Commit**

---

### 任务 8：端到端管道测试

**文件：**
- 创建：`tests/test_ralph_pipeline_e2e.py`

- [ ] **步骤 1：端到端集成测试**

```python
# tests/test_ralph_pipeline_e2e.py
from pathlib import Path
import pytest
from ralph.brainstorm_manager import BrainstormManager
from ralph.prd_manager import PRDManager
from ralph.task_decomposer import TaskDecomposer
from ralph.memory_archiver import MemoryArchiver
from ralph.schema.brainstorm_record import ConfirmedFact, UserPath


def test_full_pipeline_brainstorm_to_workunits(tmp_path: Path):
    """端到端：需求共创 → PRD → 拆解 → 记忆归档。"""
    ralph_dir = tmp_path / ".ralph"

    # 1. Brainstorm
    bm = BrainstormManager(ralph_dir)
    record = bm.start_session("TestApp", "做一个 CLI todo 工具")
    record.confirmed_facts = [
        ConfirmedFact(topic="目标用户", fact="终端用户", source_quote="dev"),
        ConfirmedFact(topic="核心功能", fact="add/list/delete todo", source_quote="crud"),
        ConfirmedFact(topic="验收标准", fact="命令行可交互", source_quote="cli"),
    ]
    record.user_paths = [UserPath(name="main", steps=["todo add", "todo list", "todo delete"], edge_cases=["empty"])]
    record.open_assumptions = []
    bm._save(record)
    assert bm.is_complete(record)

    # 2. PRD
    pm = PRDManager(ralph_dir)
    prd = pm.generate_from_brainstorm(record.record_id, ralph_dir)
    assert prd.status == "draft"
    frozen = pm.freeze(prd.prd_id)
    assert frozen.status == "frozen"

    # 3. Task Decomposition
    td = TaskDecomposer(ralph_dir)
    units = td.decompose(prd)
    assert len(units) >= 1
    failures = td.validate_granularity(units)
    assert len(failures) == 0, f"Granularity failures: {failures}"

    # 4. Memory
    ma = MemoryArchiver(ralph_dir)
    for u in units:
        ma.append_short_term({"work_id": u.work_id, "status": "ready", "title": u.title})
    assert len(ma.get_short_term()) > 0
    assert ma.get_status()["total_stored"] > 0
```

- [ ] **步骤 2：运行端到端测试**

```bash
python3 -m pytest tests/test_ralph_pipeline_e2e.py -v
```

预期：1 passed

- [ ] **步骤 3：Commit**

```bash
git add tests/test_ralph_pipeline_e2e.py ralph/evidence_collector.py testing/e2e_runner.py
git commit -m "feat(ralph): add end-to-end pipeline test from brainstorm to work units"
```

---

## 验证计划

每个任务完成后运行：
1. 单元测试：`python3 -m pytest tests/test_<module>.py -v`
2. 前端类型检查：`cd dashboard-ui && npx tsc --noEmit`
3. 全量测试：`python3 -m pytest -q` + `npx vitest run`

最终验证：
1. 端到端管道测试：`python3 -m pytest tests/test_ralph_pipeline_e2e.py -v`
2. 全部后端测试：`python3 -m pytest -q --ignore=tests/test_ralph_bootstrap.py`
3. 全部前端测试：`cd dashboard-ui && npx vitest run`
4. API 手动冒烟：`curl localhost:18753/api/ralph/brainstorm/sessions`
