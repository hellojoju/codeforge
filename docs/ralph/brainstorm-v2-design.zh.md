# Brainstorm V2 重构方案

> 从扁平 Q&A 升级为 CMMI 级功能分解 Spec Document 生成器
>
> 日期：2026-05-10

---

## 1. 问题诊断

### 1.1 当前系统缺陷

| 问题 | 现状 | 影响 |
|------|------|------|
| 问题与输入脱钩 | 10个固定模板，不管用户说什么返回一样的问题 | 无法针对具体需求深入追问 |
| 颗粒度粗糙 | `completeness_score()` 仅6项布尔检查 | 无法支撑 PRD 要求的"任务颗粒度门禁" |
| 无递归深挖 | 遍历完10个主题就结束 | 每个主题只停留在表层 |
| LLM 未接通 | `routes.py` 实例化时没传 `config_manager` | LLM 路径永远进不去 |
| 无状态追踪 | 扁平的 `confirmed_facts` 列表 | 不知道哪些点已经问透、哪些遗漏 |
| 无关联分析 | 功能之间关系完全没建模 | 无法发现依赖、冲突、流程漏洞 |
| 无独立审查 | 没有"生成者不能验收自己"的机制 | 质量问题无人发现 |
| 中断恢复脆弱 | 只存 round_number | 不知道具体卡在哪个功能点 |

### 1.2 PRD 要求的颗粒度对比

| PRD 要求 | 当前系统 | 差距 |
|----------|----------|------|
| 目标清晰 | 有 topic | 有 topic 但无用户故事格式 |
| 范围明确 | 无 | 完全不建模功能边界 |
| 依赖明确 | 无 | 功能间关系未建模 |
| 验收标准 | 有 topic 匹配 | 无 Given/When/Then 格式 |
| 测试方式 | 无 | 无用户路径验收 |
| 失败回滚 | 无 | 无失败路径建模 |

---

## 2. 核心设计思路

**不是"更好的问答"，而是"用对话逐步构建需求功能树"。**

LLM 只是提取和生成工具，真正的流程控制、状态管理、完整性检查全部由代码层面的状态机负责。

### 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Brainstorm Orchestrator                   │
│                                                              │
│  Phase 1: 产品定义 ────────────────────────────────────────  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 产品愿景  │→│ 目标用户  │→│ 用户角色  │→│ 成功标准  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
│  Phase 2: 功能分解 ────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────┐       │
│  │ 功能树 (Feature Tree)                             │       │
│  │                                                   │       │
│  │  产品                                             │       │
│  │  ├── 模块A                                        │       │
│  │  │   ├── 功能A.1  [status: confirmed]             │       │
│  │  │   │   ├── 用户故事 (≥1条)                      │       │
│  │  │   │   ├── 验收标准 (≥1条)                      │       │
│  │  │   │   ├── 用户路径 (成功/失败/边界)            │       │
│  │  │   │   ├── 数据需求 (实体+字段)                 │       │
│  │  │   │   └── 依赖关系 → [功能B.2]                │       │
│  │  │   ├── 功能A.2  [status: exploring]             │       │
│  │  │   └── 功能A.3  [status: pending]               │       │
│  │  ├── 模块B                                        │       │
│  │  └── 模块C [status: pending]                      │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  Phase 3: 关联分析 ────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────┐       │
│  │ 依赖图 + 冲突检测 + 流程验证                      │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  Phase 4: 独立审查 ────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────┐       │
│  │ 独立审查 Agent（生成者不能验收自己）               │       │
│  │   - 颗粒度检查                                    │       │
│  │   - 完整性检查                                    │       │
│  │   - 一致性检查                                    │       │
│  │   - 流程逻辑检查                                  │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 Phase 枚举

```python
class BrainstormPhase(str, Enum):
    PRODUCT_DEF = "product_def"              # Phase 1: 产品定义
    FEATURE_DECOMPOSE = "feature_decompose"  # Phase 2: 功能分解
    RELATIONSHIP = "relationship"            # Phase 3: 关系分析
    INDEPENDENT_REVIEW = "independent_review" # Phase 4: 独立审查
    CLARIFICATION = "clarification"          # 审查打回后的澄清
    COMPLETE = "complete"                    # 全部完成
```

### 3.2 通用追溯与检查模型

```python
@dataclass
class SourceRef:
    """需求事实的来源追溯。确定需求必须能追溯到用户原话或用户确认。"""
    turn_id: str
    quote: str
    field_name: str
    confidence: float = 1.0


@dataclass
class ExplicitCheck:
    """记录某一维度是否已经问过，避免把「未询问」误判成「不需要」。"""
    field_name: str                         # dependencies / permissions / business_rules / ...
    state: str                              # yes | no | not_applicable | unknown
    reason: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)


@dataclass
class QuestionTask:
    """追问导航单元。系统每次提问都必须绑定到明确的节点和缺失字段。"""
    question_id: str
    node_id: str
    field_name: str                         # 本轮要补齐的字段
    question: str
    reason: str                             # 为什么要问这个问题
    expected_answer_shape: str              # 期望用户回答的结构
    status: str = "pending"                 # pending | asked | answered | skipped
    asked_at: str = ""
    answered_at: str = ""
```

### 3.3 FeatureNode（功能树节点）

```python
@dataclass
class FeatureNode:
    # 标识
    node_id: str                         # "fn-001"
    name: str                            # "用户管理" / "登录功能"
    level: str                           # "product" | "module" | "function" | "sub_function"
    status: str = "exploring"            # exploring | confirmed | pending | needs_clarification
    depth: int = 0                       # 树深度 0-3
    parent_id: str | None = None         # 父节点 ID
    children: list[str] = field(default_factory=list)  # 子节点 ID 列表

    # 产品定义字段（product/module 层主要填充）
    vision: str = ""
    target_users: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    mvp_scope: list[str] = field(default_factory=list)       # 第一版必须做什么
    out_of_scope: list[str] = field(default_factory=list)    # 第一版明确不做什么
    business_rules: list[str] = field(default_factory=list)
    permission_rules: list[str] = field(default_factory=list)

    # 需求字段（function/sub_function 层主要填充）
    user_stories: list[str] = field(default_factory=list)          # "As a X, I want Y, so that Z"
    acceptance_criteria: list[str] = field(default_factory=list)   # "Given/When/Then"
    success_path: list[str] = field(default_factory=list)          # 成功路径步骤
    failure_path: list[str] = field(default_factory=list)          # 失败处理路径
    edge_cases: list[str] = field(default_factory=list)            # 边界场景
    data_requirements: list[str] = field(default_factory=list)     # 数据需求
    dependencies: list[str] = field(default_factory=list)          # 依赖的 node_id
    assumptions: list[str] = field(default_factory=list)           # 待确认假设
    explicit_checks: dict[str, ExplicitCheck] = field(default_factory=dict)
    source_refs: list[SourceRef] = field(default_factory=list)     # 所有确定需求的来源追溯

    # 对话追踪
    conversation_turns: list[dict] = field(default_factory=list)   # [{question, response, timestamp}]
    last_question: str = ""                # 兼容旧 UI；V2 断点恢复以 current_question_id 为准
    review_feedback: list[str] = field(default_factory=list)      # 审查打回意见

    # 元数据
    confirmed_at: str = ""
```

### 3.4 FeatureTree（树容器）

```python
@dataclass
class FeatureTree:
    root_id: str = ""                                  # product 层节点 ID
    nodes: dict[str, FeatureNode] = field(default_factory=dict)
    current_exploring_id: str | None = None            # 当前探索中的节点
    recursion_stack: list[str] = field(default_factory=list)       # DFS 追问路径，用于精准恢复
    question_plan: list[QuestionTask] = field(default_factory=list)
    current_question_id: str | None = None
    unresolved_question_ids: list[str] = field(default_factory=list)

    def get_node(self, node_id: str) -> FeatureNode | None: ...
    def add_child(self, parent_id: str, child: FeatureNode) -> None: ...
    def unconfirmed_leaves(self) -> list[FeatureNode]: ...
    def all_confirmed(self) -> bool: ...
```

### 3.5 RelationshipGraph（关系图谱）

```python
@dataclass
class RelationshipEdge:
    source_id: str
    target_id: str
    edge_type: str         # "depends_on" | "conflicts_with" | "enables" | "mutually_exclusive"
    description: str

@dataclass
class ConflictRecord:
    feature_a: str
    feature_b: str
    description: str
    severity: str          # "critical" | "warning" | "info"

@dataclass
class FlowValidation:
    feature_id: str
    issue_type: str        # "dead_end" | "missing_error_branch" | "circular_dependency"
    description: str

@dataclass
class RelationshipGraph:
    edges: list[RelationshipEdge] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)
    flow_validations: list[FlowValidation] = field(default_factory=list)
    analyzed_at: str = ""
```

### 3.6 ReviewResult（独立审查结果）

```python
@dataclass
class ReviewFinding:
    finding_type: str      # "too_coarse" | "logical_gap" | "inconsistency" | "missing_edge_case" | "traceability_gap"
    feature_id: str
    description: str
    severity: str          # "critical" | "warning"

@dataclass
class ReviewResult:
    passed: bool
    findings: list[ReviewFinding] = field(default_factory=list)
    reviewed_at: str = field(default_factory=_now_iso)
```

### 3.7 TaskHandoffHint（交给任务拆解阶段的提示）

Brainstorm 生成的是需求规格，不直接生成 Claude Code / Codex 的最终执行任务。按照 Ralph Orchestrator 总体设计，PRD 冻结、代码库侦察、耦合分析、接口合同之后，才由 Task Decomposer 生成 `work_unit`、`context_pack` 和 `task_harness`。

Brainstorm V2 只输出交接提示，帮助下游判断哪些功能可能需要继续拆细、哪些技术上下文必须在代码库侦察阶段补齐。

```python
@dataclass
class TaskHandoffHint:
    hint_id: str
    source_feature_id: str
    suggested_task_boundaries: list[str] = field(default_factory=list)
    likely_dependencies: list[str] = field(default_factory=list)
    required_recon_questions: list[str] = field(default_factory=list)  # 需要代码库侦察补齐的问题
    risk_notes: list[str] = field(default_factory=list)
    source_refs: list[SourceRef] = field(default_factory=list)
```

### 3.8 BrainstormRecord V2

```python
@dataclass
class BrainstormRecord:
    record_id: str
    project_name: str
    version: int = 2                           # 新增：版本号
    schema_version: str = "v2"                 # 新增：显式版本标记

    # Phase 状态机
    current_phase: str = "product_def"
    phase_history: list[dict] = field(default_factory=list)

    # 核心数据结构
    feature_tree: FeatureTree = field(default_factory=FeatureTree)
    relationship_graph: RelationshipGraph = field(default_factory=RelationshipGraph)
    review_result: ReviewResult | None = None
    task_handoff_hints: list[TaskHandoffHint] = field(default_factory=list)

    # 兼容 V1 旧字段（保留不删，支持向后兼容）
    round_number: int = 0
    user_message: str = ""
    confirmed_facts: list[ConfirmedFact] = field(default_factory=list)
    open_assumptions: list[OpenAssumption] = field(default_factory=list)
    user_paths: list[UserPath] = field(default_factory=list)

    created_at: str = field(default_factory=_now_iso)
    completed_at: str = ""

    def completeness_score(self) -> float:
        """V2: 基于功能树的加权完整度评分"""
        tree = self.feature_tree
        if not tree.nodes:
            return 0.0
        # 只统计 function/sub_function 层
        leaf_nodes = [n for n in tree.nodes.values() if n.level in ("function", "sub_function")]
        if not leaf_nodes:
            return 0.0
        confirmed = sum(1 for n in leaf_nodes if n.status == "confirmed")
        return confirmed / len(leaf_nodes)

    def to_spec_document(self) -> str:
        """渲染为 Spec Document Markdown"""
```

### 3.9 V1 → V2 向后兼容

V1 JSON 加载时自动迁移：
- `version` 不存在 → 默认 1
- `feature_tree` 不存在 → 从 `confirmed_facts` 构建扁平树
- `current_phase` 不存在 → 默认 `"feature_decompose"`（跳过 Phase 1）
- V1 的 fact 按 topic 分组放入对应 module 的 `user_stories`
- V1 无法追溯来源的字段统一生成 `SourceRef(confidence=0.5)`，并在 review 中标记为低置信来源

---

## 4. 状态机

### 4.1 状态转移

```
PRODUCT_DEF → FEATURE_DECOMPOSE → RELATIONSHIP → INDEPENDENT_REVIEW → COMPLETE
                                                         ↓
                                                    CLARIFICATION → INDEPENDENT_REVIEW (re-review)
```

### 4.2 转移守卫条件

| From | To | Guard Condition |
|------|-----|-----------------|
| PRODUCT_DEF | FEATURE_DECOMPOSE | product 节点 vision + target_users + roles + success_criteria + mvp_scope + out_of_scope 均填充 |
| FEATURE_DECOMPOSE | RELATIONSHIP | 所有 function/sub_function 叶子 status == "confirmed" |
| RELATIONSHIP | INDEPENDENT_REVIEW | relationship_graph.analyzed_at 非空（允许 edges 为空，但必须明确已分析） |
| INDEPENDENT_REVIEW | COMPLETE | review_result.passed == True，且 Spec Document 与 task_handoff_hints 已生成 |
| INDEPENDENT_REVIEW | CLARIFICATION | review_result.passed == False |
| CLARIFICATION | INDEPENDENT_REVIEW | 所有 needs_clarification 节点重新 confirmed |

### 4.3 粒度门控（Granularity Gate）

function/sub_function 节点标记 confirmed 前必须满足：

| 检查项 | 最低要求 |
|--------|----------|
| user_stories | ≥ 1 条 |
| acceptance_criteria | ≥ 1 条 |
| success_path | ≥ 1 条 |
| failure_path | ≥ 1 条 |
| edge_cases | ≥ 1 条 |
| data_requirements | ≥ 1 条 |
| dependencies | 已显式评估（可空但需有评估记录） |
| business_rules | 已显式评估（可空但需有评估记录） |
| permission_rules | 已显式评估（可空但需有评估记录） |
| source_refs | 所有确定需求至少有 1 条用户原话或用户确认来源 |

任一不满足 → status 保持 exploring，继续追问缺失项。

### 4.4 递归探索策略

```
当前在问 feat-A.1 (exploring)
  ↓
用户回答 → LLM 提取事实 → 填充到 node 字段
  ↓
检查粒度门控 → 全部满足？
  ↓ YES
标记 feat-A.1 = confirmed, confirmed_at = now()
  ↓
查找同级下一个 pending/exploring 节点 (feat-A.2)
  ↓ 如果找到
开始探索 feat-A.2
  ↓ 如果同级都完成
回溯到父节点，检查父模块完整性
  ↓ 如果父节点也完整
检查是否有其他模块未完成
  ↓ 全部完成
进入 Phase 3: 关系分析
```

### 4.5 追问导航机制（防止问着问着迷路）

系统不能只保存“最后一个问题”，必须保存“为什么问这个问题、问的是哪个节点、要补哪个字段”。每次进入 `generate_node_questions()` 前，先由规则层生成或更新 `question_plan`：

```text
当前 active_node
  ↓
计算 missing_items
  ↓
按优先级生成 QuestionTask：
  1. 用户故事 / 角色目标
  2. MVP 范围 / 不做什么
  3. 成功路径
  4. 失败路径
  5. 边界场景
  6. 数据需求
  7. 权限规则
  8. 业务规则
  9. 依赖关系
  10. 验收标准
  ↓
选择第一个 pending QuestionTask 作为 current_question_id
  ↓
LLM 只负责把 QuestionTask 渲染成用户听得懂的问题
```

每个问题必须满足：

1. 绑定 `question_id`、`node_id`、`field_name`。
2. 说明 `reason`，即为什么当前必须补这个信息。
3. 定义 `expected_answer_shape`，例如“请给出成功流程步骤”或“请选择是否需要权限限制”。
4. 用户回答后，系统先更新对应字段和 `source_refs`，再更新 `QuestionTask.status`。
5. 恢复 session 时，按 `current_question_id + recursion_stack + unresolved_question_ids` 精确回到断点。

### 4.6 防循环与用户疲劳保护

递归追问必须有硬性退出和降级策略：

| 场景 | 处理 |
|------|------|
| 同一节点连续 3 轮无新增事实 | 停止追问，生成明确假设，请用户确认或标记 unknown |
| 同一字段重复问到相似问题 | 合并问题，避免重复打扰 |
| 用户回答“不确定/先跳过” | 写入 `ExplicitCheck(state="unknown")`，不得静默补全 |
| 用户明确说“不需要” | 写入 `ExplicitCheck(state="not_applicable")` 并记录 source_ref |
| 节点拆分后子功能过多 | 先询问 MVP 优先级，只深入第一版范围内节点 |
| 节点超过最大深度 3 仍 too_coarse | 写入 TaskHandoffHint，交给 Task Decomposer 在技术上下文中继续拆解 |

### 4.7 从需求节点到任务拆解交接

`FeatureNode` 只证明“需求已经问清楚”，不等于可以直接交给 Claude Code / Codex。Brainstorm COMPLETE 前只需要生成 `TaskHandoffHint`，把下游任务拆解需要注意的边界、依赖、风险和待侦察问题交接出去。

| 检查项 | 要求 |
|--------|------|
| suggested_task_boundaries | 给出可能的任务边界，但不承诺最终文件范围 |
| likely_dependencies | 标出功能层面的依赖关系 |
| required_recon_questions | 标出必须由代码库侦察补齐的问题 |
| risk_notes | 标出需求层面的风险和歧义 |
| source_refs | 交接提示必须能追溯用户原话或确认 |

Claude/Codex 单次执行任务、`context_pack`、`task_harness` 和 10-30 分钟任务门禁属于后续 Task Decomposer / WorkUnit Engine 的职责，不在 Brainstorm Manager 内完成。

---

## 5. Manager 方法清单

### 5.1 会话生命周期

| 方法 | 签名 | 职责 |
|------|------|------|
| `start_session` | `(project_name, user_message) -> BrainstormRecord` | V2 创建，初始化 product 根节点，进入 Phase 1 |
| `resume_session` | `(record_id) -> BrainstormRecord | None` | 加载，恢复 phase + active_node |
| `load` | `(record_id) -> BrainstormRecord | None` | 含 V1→V2 自动迁移 |
| `list_sessions` | `() -> list[dict]` | 增加 current_phase, active_node_name |

### 5.2 状态机驱动

| 方法 | 签名 | 职责 |
|------|------|------|
| `advance_phase` | `(record) -> bool` | 检查守卫条件，推进 phase |
| `get_current_phase` | `(record) -> BrainstormPhase` | 返回当前 phase |
| `is_complete` | `(record) -> bool` | V2: current_phase == COMPLETE |

### 5.3 Phase 1: 产品定义

| 方法 | 签名 | 职责 |
|------|------|------|
| `explore_product` | `(record) -> list[str]` | LLM 生成 Phase 1 追问 |
| `confirm_product` | `(record) -> bool` | 检查能否进入 Phase 2 |

### 5.4 Phase 2: 功能分解（核心）

| 方法 | 签名 | 职责 |
|------|------|------|
| `get_active_node` | `(record) -> FeatureNode | None` | 返回当前正在探索的节点 |
| `decompose_node` | `(record, children_names) -> list[FeatureNode]` | LLM 拆分节点为子功能 |
| `build_question_plan` | `(record, node) -> list[QuestionTask]` | 基于缺失项生成追问计划 |
| `select_next_question` | `(record) -> QuestionTask | None` | 选择下一个 pending 问题并设置 current_question_id |
| `generate_node_questions` | `(record) -> list[str]` | 针对 active_node 生成追问 |
| `check_granularity` | `(record) -> list[str]` | 检查粒度门控，返回缺失项 |
| `apply_extracted_facts` | `(record, node, facts) -> None` | 写入结构化事实、显式检查和来源追溯 |
| `confirm_node` | `(record) -> bool` | 标记 confirmed，推进下一节点 |
| `select_next_node` | `(record) -> FeatureNode | None` | DFS 策略选下一节点 |

### 5.5 Phase 3: 关系分析

| 方法 | 签名 | 职责 |
|------|------|------|
| `analyze_relationships` | `(record) -> RelationshipGraph` | LLM 分析依赖/冲突/流验证 |

### 5.6 Phase 4: 独立审查

| 方法 | 签名 | 职责 |
|------|------|------|
| `independent_review` | `(record) -> ReviewResult` | 独立 LLM 审查（不同 provider） |

### 5.7 Clarification

| 方法 | 签名 | 职责 |
|------|------|------|
| `clarify_nodes` | `(record) -> list[str]` | 针对打回节点生成追问 |
| `re_review` | `(record) -> ReviewResult` | 澄清后重新审查 |

### 5.8 任务拆解交接

| 方法 | 签名 | 职责 |
|------|------|------|
| `generate_task_handoff_hints` | `(record) -> list[TaskHandoffHint]` | 从已确认 FeatureNode 生成下游任务拆解提示 |
| `check_handoff_readiness` | `(record) -> list[str]` | 检查是否具备进入 PRD/任务拆解链路的交接条件 |
| `handoff_gaps` | `(record) -> list[str]` | 返回仍需用户澄清的需求层缺口 |

### 5.9 回复处理（重写）

| 方法 | 签名 | 职责 |
|------|------|------|
| `process_response` | `(record, user_response, extracted_facts) -> BrainstormRecord` | 按 phase 路由 |
| `_process_product_response` | `(record, response) -> None` | 处理 Phase 1 回答 |
| `_process_decompose_response` | `(record, response) -> None` | 处理 Phase 2 回答 |
| `_process_relationship_response` | `(record, response) -> None` | 处理 Phase 3 回答 |
| `_process_clarification_response` | `(record, response) -> None` | 处理 Clarification 回答 |

### 5.10 文档生成

| 方法 | 签名 | 职责 |
|------|------|------|
| `generate_spec_document` | `(record) -> str` | 渲染完整 Spec Document |
| `export_spec` | `(record_id, output_path) -> Path` | 导出到文件 |

---

## 6. LLM Prompt 设计

### 6.1 Phase 1: 产品定义追问

```
你是资深产品需求分析师。
项目：{project_name}
用户初步描述：{user_message}
当前已收集：
- 愿景：{vision}
- 目标用户：{target_users}
- 用户角色：{roles}
- MVP 范围：{mvp_scope}
- 明确不做：{out_of_scope}
- 成功标准：{success_criteria}
- 业务规则：{business_rules}
- 权限规则：{permission_rules}

请生成 2-3 个针对性追问，补齐尚未明确的维度。
每个问题要具体，引用用户原话，不要泛泛而问。
严格以 JSON 数组返回: ["问题1", "问题2", ...]
```

### 6.2 QuestionTask 渲染

```
你是资深产品需求分析师。
请把以下追问任务改写成用户听得懂、具体、自然的问题：

项目：{project_name}
当前节点：{node.name}
字段：{question_task.field_name}
追问原因：{question_task.reason}
期望回答形态：{question_task.expected_answer_shape}
相关用户原话：{source_refs}

要求：
1. 不要泛泛而问，必须点明当前功能节点。
2. 一次最多问 2 个问题。
3. 如果用户可能不确定，提供“可以先标记为不确定”的出口。
4. 严格以 JSON 数组返回。
```

### 6.3 Phase 2: 功能分解追问

```
你是资深系统分析师。
当前正在探讨的功能节点：「{node.name}」
层级：{node.level}
已收集信息：
- 用户故事：{node.user_stories}
- 验收标准：{node.acceptance_criteria}
- 成功路径：{node.success_path}
- 失败路径：{node.failure_path}
- 边界场景：{node.edge_cases}
- 数据需求：{node.data_requirements}
- 权限规则：{node.permission_rules}
- 业务规则：{node.business_rules}
- 显式检查：{node.explicit_checks}
- 来源追溯：{node.source_refs}

缺失项：{missing_items}

请针对缺失项生成 2-3 个具体追问。
如果用户故事已收集但缺少失败路径，追问"如果这个操作用户失败了，系统应该怎么响应？"
如果缺少边界场景，追问"极端情况下（网络断开、数据异常、并发操作），这个功能应该如何处理？"
严格以 JSON 数组返回。
```

### 6.4 事实提取

```
从以下用户回复中提取与功能节点「{node.name}」相关的结构化信息。

项目：{project_name}
当前功能节点：{node.name}
当前问题：{question_task.question}
当前要补字段：{question_task.field_name}
用户回复：{user_response}

请以 JSON 返回，只包含从本次回复中能提取到的字段：
{
  "user_stories": ["As a <角色>, 我想 <行为>, 以便 <目的>"],
  "acceptance_criteria": ["Given <前置条件> When <操作> Then <预期结果>"],
  "success_path": ["步骤1", "步骤2", ...],
  "failure_path": ["失败场景", "系统响应", "恢复方式"],
  "edge_cases": ["边界场景1", ...],
  "data_requirements": ["需要存储的数据实体和关键字段"],
  "dependencies": ["依赖的其他功能 node_id"],
  "business_rules": ["业务规则"],
  "permission_rules": ["权限规则"],
  "assumptions": ["需要进一步确认的假设"],
  "explicit_checks": [
    {"field_name": "dependencies", "state": "yes | no | not_applicable | unknown", "reason": "判断依据"}
  ],
  "source_refs": [
    {"field_name": "user_stories", "quote": "用户原话片段", "confidence": 0.0}
  ],
  "suggested_children": ["建议拆分的子功能名称列表"],
  "added_new_fact": true/false
}

注意：
1. 不得把推测写成确定需求。推测只能进入 assumptions。
2. 每个确定需求都必须返回 source_refs。
3. 如果用户表示“不确定/先跳过”，对应 explicit_checks.state 应为 unknown。
```

### 6.5 功能节点拆分

```
你是资深系统架构师。
请将以下功能节点拆分为若干子功能：

功能：{node.name}
描述：{node.user_stories}

拆分原则：
1. 每个子功能应该是独立可开发、可测试的最小单元
2. 子功能之间应该边界清晰
3. 每个子功能应该对应一个明确的用户价值
4. 拆分粒度应该满足：一个 Claude Code agent 能在 10-30 分钟内完成

请以 JSON 数组返回子功能名称列表：["子功能1", "子功能2", ...]
```

### 6.6 粒度门控检查

```
审查以下功能节点是否满足开发任务粒度标准。

功能：{node.name}
用户故事：{node.user_stories}
验收标准：{node.acceptance_criteria}
成功路径：{node.success_path}
失败路径：{node.failure_path}
边界场景：{node.edge_cases}
数据需求：{node.data_requirements}
依赖关系：{node.dependencies}
业务规则：{node.business_rules}
权限规则：{node.permission_rules}
显式检查：{node.explicit_checks}
来源追溯：{node.source_refs}

检查清单：
1. 至少有 1 条用户故事？
2. 至少有 1 条验收标准？
3. 有成功路径？
4. 有失败路径？
5. 有至少 1 个边界场景？
6. 数据需求明确了？
7. 依赖关系已评估？
8. 业务规则已评估？
9. 权限规则已评估？
10. 所有确定需求是否可追溯到用户原话或用户确认？

请以 JSON 返回：
{
  "passed": true/false,
  "missing_items": ["缺失项1", ...],
  "too_coarse": true/false,
  "suggested_split": ["建议拆分方向"] (如果 too_coarse),
  "can_confirm": true/false
}
```

### 6.7 Phase 3: 关系分析

```
你是资深系统架构师。
以下是一个产品的所有已确认功能节点：

{遍历所有 confirmed 节点，输出：node_id, name, level, user_stories, success_path, failure_path, edge_cases, data_requirements, dependencies, business_rules, permission_rules}

请分析：
1. 依赖关系：哪些功能依赖其他功能？（depends_on / enables）
2. 功能冲突：哪些功能之间存在互斥或冲突？（conflicts_with / mutually_exclusive）
3. 流程验证：哪些用户路径存在死胡同？哪些缺少错误分支？是否有循环依赖？

请以 JSON 返回：
{
  "edges": [{"source_id": "...", "target_id": "...", "edge_type": "...", "description": "..."}],
  "conflicts": [{"feature_a": "...", "feature_b": "...", "description": "...", "severity": "..."}],
  "flow_validations": [{"feature_id": "...", "issue_type": "...", "description": "..."}]
}

即使没有发现依赖边，也必须返回空数组并说明已分析，调用方据此写入 analyzed_at。
```

### 6.8 Phase 4: 独立审查

```
你是独立需求质量审查员。你 NOT 参与之前的需求共创对话。
以下是一份完整的产品需求规格草案：

{to_spec_document() 完整输出}

请从以下 6 个维度审查：
1. 粒度：每个功能点是否足够细，能直接拆成开发任务？
2. 逻辑：用户路径是否有死胡同？失败路径是否覆盖所有异常？
3. 一致性：功能之间是否有矛盾或重复？
4. 边界：是否遗漏了重要的边界场景？
5. 完整性：是否所有关键需求领域都已覆盖？
6. 追溯性：每条确定需求是否能追溯用户原话或用户确认？

请以 JSON 返回：
{
  "passed": true/false,
  "findings": [
    {
      "finding_type": "too_coarse | logical_gap | inconsistency | missing_edge_case | incomplete | traceability_gap",
      "feature_id": "...",
      "description": "具体问题描述",
      "severity": "critical | warning"
    }
  ]
}
```

### 6.9 任务拆解交接提示生成

```
你是资深产品到工程交接分析师。
以下是已通过需求审查的功能节点：

{confirmed_feature_nodes}

请为每个功能节点生成 TaskHandoffHint，用于后续 Task Decomposer 在完成 PRD 冻结、代码库侦察、耦合分析和接口合同后继续拆解。

要求：
1. 只能基于需求事实和用户确认生成提示，不要编造文件路径。
2. 标出可能的任务边界，但不要承诺最终 work_unit。
3. 标出功能层依赖和风险。
4. 标出必须由代码库侦察补齐的问题。
5. 每条提示都必须带来源追溯。

请以 JSON 返回：
{
  "hints": [
    {
      "source_feature_id": "...",
      "suggested_task_boundaries": ["..."],
      "likely_dependencies": ["..."],
      "required_recon_questions": ["..."],
      "risk_notes": ["..."],
      "source_refs": [{"turn_id": "...", "quote": "...", "field_name": "...", "confidence": 1.0}]
    }
  ]
}
```

---

## 7. API 变更

### 7.1 修改现有路由

| Method | Path | 变更 |
|--------|------|------|
| GET | `/api/ralph/brainstorm/sessions` | 响应增加 `current_phase`, `active_node_name`, `completed_features` |
| POST | `/api/ralph/brainstorm/start` | 响应增加 `phase`, `feature_tree`, `active_node` |
| POST | `/api/ralph/brainstorm/respond` | 响应增加 `phase`, `active_node`, `current_question`, `granularity_status` (缺失项列表), `spec_preview` |

### 7.2 新增路由

| Method | Path | 描述 |
|--------|------|------|
| GET | `/api/ralph/brainstorm/{record_id}/tree` | 获取完整功能树 |
| GET | `/api/ralph/brainstorm/{record_id}/spec` | 获取 Spec Document Markdown |
| POST | `/api/ralph/brainstorm/{record_id}/resume` | 显式恢复 session |
| POST | `/api/ralph/brainstorm/{record_id}/advance` | 手动推进 phase |
| POST | `/api/ralph/brainstorm/{record_id}/decompose` | 手动触发节点拆分 |
| GET | `/api/ralph/brainstorm/{record_id}/relationships` | 获取关系图谱 |
| POST | `/api/ralph/brainstorm/{record_id}/review` | 手动触发独立审查 |
| GET | `/api/ralph/brainstorm/{record_id}/questions` | 获取追问计划和当前问题 |
| GET | `/api/ralph/brainstorm/{record_id}/handoff` | 获取任务拆解交接提示 |
| POST | `/api/ralph/brainstorm/{record_id}/handoff/generate` | 手动触发交接提示生成 |

### 7.3 Bug 修复

所有 brainstorm 路由必须从 `app.state.config_manager` 获取 config_manager 并传入 BrainstormManager。建议封装辅助函数：

```python
def _get_brainstorm_manager() -> BrainstormManager:
    cfg: RalphConfigManager = app.state.config_manager
    ralph_dir = cfg._dir.parent
    return BrainstormManager(ralph_dir, cfg)
```

---

## 8. 前端变更

### 8.1 布局结构

```
┌──────────────────────────────────────────────┐
│ PhaseIndicator (4步进度条)                     │
├──────────┬──────────────────┬────────────────┤
│ Feature  │  Chat Area       │  NodeDetail    │
│ Tree     │  - 系统问题       │  Card          │
│ Panel    │  - 用户回复       │  (active node) │
│ (可折叠) │  - 输入框        │  或 SpecPreview│
├──────────┴──────────────────┴────────────────┤
│ 底部状态栏：完整度 / 轮次 / 导出 Spec 按钮      │
└──────────────────────────────────────────────┘
```

### 8.2 新增组件

| 组件 | 文件 | 预估行数 | 职责 |
|------|------|----------|------|
| PhaseIndicator | `dashboard-ui/components/ralph/brainstorm/PhaseIndicator.tsx` | ~80 | 4步进度条，当前阶段高亮 |
| FeatureTreePanel | `dashboard-ui/components/ralph/brainstorm/FeatureTreePanel.tsx` | ~120 | 树形展示功能树，支持展开/折叠 |
| NodeDetailCard | `dashboard-ui/components/ralph/brainstorm/NodeDetailCard.tsx` | ~150 | 当前探索节点的详情（用户故事、验收标准等） |
| GranularityBadge | `dashboard-ui/components/ralph/brainstorm/GranularityBadge.tsx` | ~50 | 显示粒度检查结果（通过/缺失项） |
| RelationshipGraph | `dashboard-ui/components/ralph/brainstorm/RelationshipGraph.tsx` | ~120 | Phase 3 的依赖图可视化 |
| SpecPreview | `dashboard-ui/components/ralph/brainstorm/SpecPreview.tsx` | ~100 | Phase 4 通过后的 Spec 预览 |
| QuestionTracePanel | `dashboard-ui/components/ralph/brainstorm/QuestionTracePanel.tsx` | ~80 | 显示当前问题对应节点、字段和追问原因 |
| TaskHandoffPanel | `dashboard-ui/components/ralph/brainstorm/TaskHandoffPanel.tsx` | ~120 | 显示下游任务拆解提示、依赖、风险和待侦察问题 |

### 8.3 API 封装

新增 `dashboard-ui/lib/brainstorm-api.ts` (~60行)：
- `getFeatureTree(recordId)`
- `getSpecDocument(recordId)`
- `resumeSession(recordId)`
- `advancePhase(recordId)`
- `triggerDecompose(recordId, childrenNames)`
- `triggerReview(recordId)`
- `getQuestionPlan(recordId)`
- `getTaskHandoffHints(recordId)`
- `generateTaskHandoffHints(recordId)`

### 8.4 主页面修改

`dashboard-ui/app/ralph/brainstorm/page.tsx` 从 ~170 行增加到 ~250 行：
- 增加 `phase`, `activeNode`, `featureTree` 状态
- 挂载 PhaseIndicator + FeatureTreePanel + NodeDetailCard
- 显示当前追问的目标字段和缺失原因，让用户知道系统为什么问这个问题
- 根据当前 phase 显示不同 UI

---

## 9. 文件清单

| 操作 | 文件 | 预估行数 | 说明 |
|------|------|----------|------|
| 修改 | `ralph/schema/brainstorm_record.py` | 54→380 | 新增 FeatureNode, FeatureTree, RelationshipGraph, ReviewResult 等 |
| 修改 | `ralph/brainstorm_manager.py` | 316→650 | 重写状态机、Phase 1-4、粒度门控、文档生成 |
| 修改 | `dashboard/api/routes.py` | ~1918-1960 | 修复 config_manager 传递 + 新增 brainstorm V2 路由 |
| 修改 | `dashboard-ui/app/ralph/brainstorm/page.tsx` | 170→250 | 挂载新组件，增加 phase 状态 |
| 新增 | `dashboard-ui/components/ralph/brainstorm/PhaseIndicator.tsx` | ~80 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/FeatureTreePanel.tsx` | ~120 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/NodeDetailCard.tsx` | ~150 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/GranularityBadge.tsx` | ~50 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/RelationshipGraph.tsx` | ~120 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/SpecPreview.tsx` | ~100 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/QuestionTracePanel.tsx` | ~80 | |
| 新增 | `dashboard-ui/components/ralph/brainstorm/TaskHandoffPanel.tsx` | ~120 | |
| 新增 | `dashboard-ui/lib/brainstorm-api.ts` | ~60 | |
| 新增 | `tests/ralph/test_brainstorm_v2.py` | ~300 | |
| 新增 | `tests/ralph/test_brainstorm_migration.py` | ~150 | |

**总计新增 ~2200 行，修改 ~260 行。**

---

## 10. 实施顺序

```
Phase A: Schema 先行
  └─ 改 brainstorm_record.py，新增所有 dataclass
  └─ 写 schema 测试
  └─ 写 V1→V2 迁移测试

Phase B: Manager 核心
  └─ 重写 start_session / load / resume_session
  └─ 实现 Phase 1→4 + clarification 状态机
  └─ 实现 question_plan / recursion_stack / source_refs
  └─ 实现粒度门控检查
  └─ 实现递归探索策略
  └─ 实现 Spec Document 生成
  └─ 实现 TaskHandoffHint 生成和交接完整性检查

Phase C: API 路由
  └─ 修复现有 3 个路由的 config_manager bug
  └─ 新增 tree/spec/resume/advance/decompose/relationships/review/questions/handoff 路由
  └─ API 集成测试

Phase D: 前端组件
  └─ 8 个 React 组件
  └─ 主页面改造
  └─ API 封装

Phase E: 全量测试
  └─ 穿插各阶段编写测试
  └─ 端到端流程测试
```

---

## 11. 风险与注意事项

| 风险 | 应对 |
|------|------|
| BrainstormManager 行数超 800 | Phase 3/4 提取到 `brainstorm_analyzer.py` |
| LLM 成本过高 | 粒度检查先用规则判断，减少 LLM 调用；独立审查可用轻量模型 |
| 状态持久化丢失 | 每次 process_response 后必须 _save()；支持 resume |
| JSON 解析失败 | 所有 LLM 返回都有 fallback 路径，降级到规则/静态逻辑 |
| 前端状态复杂 | 用 React Context 管理 brainstorm 状态，避免 props drilling |
| V1 数据不兼容 | load() 中自动迁移，不修改原文件；completeness_score() 保留旧分支 |
| 追问陷入循环 | 使用 QuestionTask 状态、相似问题检测和单节点最大追问轮数 |
| AI 猜测被写成确定需求 | 所有确定需求必须带 SourceRef；review 检查低置信来源 |
| 任务拆解缺少代码库上下文 | Brainstorm 只生成 required_recon_questions，留给代码库侦察和 Task Decomposer 补齐 |

---

## 12. 验收标准

1. 用户输入一段需求描述后，系统进入 Phase 1 产品定义
2. Phase 1 完成后自动进入 Phase 2 功能分解
3. Phase 2 中递归深挖每个功能节点，直到满足粒度门控
4. 每个功能节点有用户故事、验收标准、成功/失败路径、边界场景
5. 所有功能确认后自动进入 Phase 3 关系分析
6. Phase 4 独立审查通过后才标记 COMPLETE
7. 审查不通过的功能点回到 Clarification 继续追问
8. 关闭浏览器重新打开后，能从精确的断点位置恢复
9. 可以导出完整的 Spec Document Markdown
10. 每个问题都能说明正在补哪个功能节点、哪个字段、为什么要问
11. 每条确定需求都能追溯用户原话或用户确认
12. 每个已确认功能能生成 1 个或多个 TaskHandoffHint
13. TaskHandoffHint 明确可能的任务边界、功能依赖、风险和待侦察问题
14. Brainstorm 不生成最终 Claude/Codex work_unit，不编造文件路径、测试命令或修改范围
15. V1 的 brainstorm JSON 文件能正常加载和自动迁移
