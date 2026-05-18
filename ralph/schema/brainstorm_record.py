from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class BrainstormPhase(str, Enum):  # noqa: SIM103  (StrEnum requires py3.11+)
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


# ── V3: 主动分析 ──

@dataclass
class EvidenceRef:
    """外部证据或系统推断的来源追溯。"""
    source_type: str  # user_quote | github | official_docs | package_registry | web | llm_inference
    title: str
    url: str = ""
    quote_or_summary: str = ""
    captured_at: str = ""
    confidence: float = 1.0


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


# ── V3: 多 Agent 产品定义 ──

@dataclass
class ProductDefFinding:
    """单个 Agent 维度的分析发现"""
    finding_id: str
    dimension: str  # product_vision | user_experience | technical_feasibility | business_value
    dimension_name: str  # 展示用名称
    content: str  # 分析内容
    suggestions: list[str] = field(default_factory=list)  # 建议
    questions: list[str] = field(default_factory=list)  # 待用户确认的问题
    confidence: float = 0.8
    status: str = "pending"  # pending | accepted | rejected | modified
    user_revision: str = ""

    pm_decision: str = "pending"  # pending | accept | reject | defer
    pm_reason: str = ""


@dataclass
class ProductDefRound:
    """一轮多 Agent 产品分析"""
    round_id: str
    findings: list[ProductDefFinding] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""
    confirmed_at: str = ""


@dataclass
class ProductDefProgress:
    """多 Agent 产品定义分析的实时进度"""
    total_dimensions: int = 4
    dimensions_analyzed: list[str] = field(default_factory=list)
    current_dimension: str | None = None
    partial_findings: list[ProductDefFinding] = field(default_factory=list)
    started_at: str = ""
    completed_at: str | None = None


@dataclass
class PhaseOutputSnapshot:
    """单个阶段完成时的产出快照。"""
    phase: str  # phase key
    label: str  # 显示名称
    completed_at: str
    confirmed: bool = False
    confirmed_at: str = ""
    summary: str = ""
    detail: dict = field(default_factory=dict)


# ── V3: 结构化审查 ──

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


# ── V3: 技术路线 ──

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


# ── V3: 工具发现 ──

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
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


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


# ── V2 追溯与检查模型 ──

@dataclass
class SourceRef:
    """需求事实的来源追溯"""
    turn_id: str
    quote: str
    field_name: str
    confidence: float = 1.0


@dataclass
class ExplicitCheck:
    """记录某一维度是否已经问过"""
    field_name: str
    state: str  # yes | no | not_applicable | unknown
    reason: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)


@dataclass
class QuestionTask:
    """追问导航单元"""
    question_id: str
    node_id: str
    field_name: str
    question: str
    reason: str
    expected_answer_shape: str
    status: str = "pending"  # pending | asked | answered | skipped
    asked_at: str = ""
    answered_at: str = ""


@dataclass
class FeatureNode:
    node_id: str
    name: str
    level: str  # product | module | function | sub_function
    status: str = "exploring"
    depth: int = 0
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)

    vision: str = ""
    target_users: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    mvp_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    permission_rules: list[str] = field(default_factory=list)

    user_stories: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    success_path: list[str] = field(default_factory=list)
    failure_path: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    data_requirements: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    explicit_checks: dict[str, ExplicitCheck] = field(default_factory=dict)
    source_refs: list[SourceRef] = field(default_factory=list)

    conversation_turns: list[dict] = field(default_factory=list)
    last_question: str = ""
    review_feedback: list[str] = field(default_factory=list)

    confirmed_at: str = ""


@dataclass
class FeatureTree:
    root_id: str = ""
    nodes: dict[str, FeatureNode] = field(default_factory=dict)
    current_exploring_id: str | None = None
    recursion_stack: list[str] = field(default_factory=list)
    question_plan: list[QuestionTask] = field(default_factory=list)
    current_question_id: str | None = None
    unresolved_question_ids: list[str] = field(default_factory=list)

    def get_node(self, node_id: str) -> "FeatureNode | None":
        return self.nodes.get(node_id)

    def add_child(self, parent_id: str, child: "FeatureNode") -> None:
        parent = self.get_node(parent_id)
        if parent:
            parent.children.append(child.node_id)
            child.parent_id = parent_id
            child.depth = parent.depth + 1
        self.nodes[child.node_id] = child

    def unconfirmed_leaves(self) -> list["FeatureNode"]:
        return [n for n in self.nodes.values()
                if n.status in ("exploring", "pending") and not n.children]

    def all_confirmed(self) -> bool:
        leaves = [n for n in self.nodes.values() if n.level in ("function", "sub_function")]
        if not leaves:
            return False
        return all(n.status == "confirmed" for n in leaves)


# ── Relationship 相关 ──

@dataclass
class RelationshipEdge:
    source_id: str
    target_id: str
    edge_type: str
    description: str


@dataclass
class ConflictRecord:
    feature_a: str
    feature_b: str
    description: str
    severity: str


@dataclass
class FlowValidation:
    feature_id: str
    issue_type: str
    description: str


@dataclass
class RelationshipGraph:
    edges: list[RelationshipEdge] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)
    flow_validations: list[FlowValidation] = field(default_factory=list)
    analyzed_at: str = ""


# ── Review & Handoff ──

@dataclass
class ReviewFinding:
    finding_type: str
    feature_id: str
    description: str
    severity: str


@dataclass
class ReviewResult:
    passed: bool
    findings: list[ReviewFinding] = field(default_factory=list)
    reviewed_at: str = ""


# ── V3: 可执行计划 ──

@dataclass
class ExecutionTask:
    """从 BrainstormRecord 功能树生成的可执行任务"""
    task_id: str
    title: str
    description: str
    source_feature_id: str  # 来自哪个 FeatureNode
    action: str  # CREATE | UPDATE | DELETE
    target_files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # task_id 列表
    acceptance_criteria: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)  # 如 "pytest tests/test_x.py"
    estimated_complexity: str = "medium"  # low | medium | high
    status: str = "pending"  # pending | in_progress | completed | blocked


@dataclass
class ExecutablePlan:
    """从 BrainstormRecord 生成的可执行计划（Archon plan.md 的结构化版本）"""
    plan_id: str
    project_name: str
    summary: str = ""
    user_story: str = ""
    problem_statement: str = ""
    solution_statement: str = ""

    # 元数据
    plan_type: str = ""  # feature | bugfix | refactor | new_project
    complexity: str = ""  # small | medium | large
    systems_affected: list[str] = field(default_factory=list)

    # 技术上下文
    architecture_summary: str = ""
    tech_stack: list[str] = field(default_factory=list)
    tool_needs: list[str] = field(default_factory=list)

    # 关键文件
    mandatory_reading: list[str] = field(default_factory=list)  # 实现者必须读的文件
    patterns_to_mirror: list[str] = field(default_factory=list)  # 代码库中可参考的模式

    # 任务列表（按依赖排序）
    tasks: list[ExecutionTask] = field(default_factory=list)

    # 验证
    testing_strategy: str = ""
    validation_commands: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    # 风险
    risks: list[str] = field(default_factory=list)

    created_at: str = ""
    brainstorm_record_id: str = ""


@dataclass
class TaskHandoffHint:
    hint_id: str
    source_feature_id: str
    suggested_task_boundaries: list[str] = field(default_factory=list)
    likely_dependencies: list[str] = field(default_factory=list)
    required_recon_questions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    source_refs: list[SourceRef] = field(default_factory=list)


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
    version: int = 2
    schema_version: str = "v2"

    # Phase 状态机
    current_phase: str = "product_def"
    phase_history: list[dict] = field(default_factory=list)
    phase_outputs: dict[str, PhaseOutputSnapshot] = field(default_factory=dict)

    # V2 核心数据结构
    feature_tree: FeatureTree = field(default_factory=FeatureTree)
    relationship_graph: RelationshipGraph = field(default_factory=RelationshipGraph)
    review_result: ReviewResult | None = None
    task_handoff_hints: list[TaskHandoffHint] = field(default_factory=list)

    # V3: 多 Agent 产品定义
    product_def_rounds: list[ProductDefRound] = field(default_factory=list)
    product_def_progress: ProductDefProgress | None = None
    # V3: 主动分析
    proactive_analysis: ProactiveAnalysis | None = None
    # V3: 多轮审查
    deliberation_rounds: list[DeliberationRound] = field(default_factory=list)
    # V3: 技术路线
    technical_route: TechnicalRoute | None = None
    technical_route_history: list[TechnicalRoute] = field(default_factory=list)
    # V3: 工具发现
    tool_discovery_results: list[ToolDiscoveryResult] = field(default_factory=list)
    # V3: 可执行计划
    executable_plan: ExecutablePlan | None = None

    # V1 兼容字段
    round_number: int = 0
    user_message: str = ""
    confirmed_facts: list[ConfirmedFact] = field(default_factory=list)
    open_assumptions: list[OpenAssumption] = field(default_factory=list)
    user_paths: list[UserPath] = field(default_factory=list)
    system_questions: list[str] = field(default_factory=list)

    created_at: str = field(default_factory=_now_iso)
    completed_at: str = ""

    def completeness_score(self) -> float:
        """需求完整度评分: 0.0-1.0"""
        tree = self.feature_tree
        if not tree.nodes:
            return self._v1_completeness()
        leaf_nodes = [n for n in tree.nodes.values() if n.level in ("function", "sub_function")]
        if not leaf_nodes:
            return self._v1_completeness()
        confirmed = sum(1 for n in leaf_nodes if n.status == "confirmed")
        return confirmed / len(leaf_nodes)

    def to_spec_document(self) -> str:
        """渲染完整 Spec Document Markdown"""
        lines = [f"# {self.project_name} - 需求规格文档", ""]

        # 产品定义
        root = self.feature_tree.get_node("fn-root")
        if root:
            lines.extend([
                "## 产品定义", "",
                f"**愿景：** {root.vision}", "",
                f"**目标用户：** {', '.join(root.target_users) if root.target_users else '待明确'}", "",
                f"**用户角色：** {', '.join(root.roles) if root.roles else '待明确'}", "",
                f"**MVP 范围：** {', '.join(root.mvp_scope) if root.mvp_scope else '待明确'}", "",
                f"**明确不做：** {', '.join(root.out_of_scope) if root.out_of_scope else '无'}", "",
                f"**成功标准：** {', '.join(root.success_criteria) if root.success_criteria else '待明确'}", "",
            ])

        # 功能分解
        lines.extend(["## 功能分解", ""])
        for node in self.feature_tree.nodes.values():
            if node.node_id == "fn-root" or node.level == "product":
                continue
            indent = "  " if node.level == "sub_function" else ""
            status_icons = {
                "confirmed": "✅", "exploring": "\U0001f535",
                "pending": "⬜", "needs_clarification": "⚠️",
            }
            status_icon = status_icons.get(node.status, "⬜")
            lines.extend([
                f"{indent}### {status_icon} {node.name}", "",
                f"{indent}- **状态：** {node.status}", "",
            ])
            if node.user_stories:
                lines.append(f"{indent}- **用户故事：**")
                for s in node.user_stories:
                    lines.append(f"{indent}  - {s}")
                lines.append("")
            if node.acceptance_criteria:
                lines.append(f"{indent}- **验收标准：**")
                for c in node.acceptance_criteria:
                    lines.append(f"{indent}  - {c}")
                lines.append("")
            if node.success_path:
                lines.append(f"{indent}- **成功路径：**")
                for p in node.success_path:
                    lines.append(f"{indent}  - {p}")
                lines.append("")
            if node.failure_path:
                lines.append(f"{indent}- **失败路径：**")
                for p in node.failure_path:
                    lines.append(f"{indent}  - {p}")
                lines.append("")
            if node.edge_cases:
                lines.append(f"{indent}- **边界场景：**")
                for c in node.edge_cases:
                    lines.append(f"{indent}  - {c}")
                lines.append("")
            if node.data_requirements:
                lines.append(f"{indent}- **数据需求：**")
                for d in node.data_requirements:
                    lines.append(f"{indent}  - {d}")
                lines.append("")
            if node.dependencies:
                lines.append(f"{indent}- **依赖：** {', '.join(node.dependencies)}", "")

        # 关系分析
        if self.relationship_graph.edges or self.relationship_graph.conflicts:
            lines.extend(["## 关系分析", ""])
            for edge in self.relationship_graph.edges:
                lines.append(f"- {edge.source_id} {edge.edge_type} {edge.target_id}: {edge.description}")
            lines.append("")

        # 审查结果
        if self.review_result:
            lines.extend(["## 独立审查", ""])
            lines.extend([f"**结果：** {'通过' if self.review_result.passed else '不通过'}", ""])
            for finding in self.review_result.findings:
                lines.append(f"- [{finding.severity}] {finding.description}")
            lines.append("")

        return "\n".join(lines)

    def _v1_completeness(self) -> float:
        checks = [
            len(self.confirmed_facts) >= 3,
            len(self.open_assumptions) == 0,
            len(self.user_paths) >= 1,
            any(f.topic == "目标用户" for f in self.confirmed_facts),
            any(f.topic == "核心功能" for f in self.confirmed_facts),
            any(f.topic == "验收标准" for f in self.confirmed_facts),
        ]
        return sum(1 for c in checks if c) / len(checks)


# ── V1 → V2 Migration ──

def migrate_v1_to_v2(data: dict) -> dict:
    """将 V1 数据迁移到 V2 格式"""
    if data.get("schema_version") == "v2":
        return data

    migrated = dict(data)
    migrated["version"] = migrated.get("version", 1)
    migrated["schema_version"] = "v2"
    migrated.setdefault("current_phase", "feature_decompose")
    migrated.setdefault("phase_history", [])
    migrated.setdefault("feature_tree", {
        "nodes": {}, "root_id": "", "current_exploring_id": None,
        "recursion_stack": [], "question_plan": [],
        "current_question_id": None, "unresolved_question_ids": [],
    })
    migrated.setdefault("relationship_graph", {
        "edges": [], "conflicts": [], "flow_validations": [], "analyzed_at": "",
    })
    migrated.setdefault("review_result", None)
    migrated.setdefault("task_handoff_hints", [])

    # 从 confirmed_facts 构建扁平 FeatureTree
    if not migrated["feature_tree"]["nodes"]:
        root_id = "fn-root"
        migrated["feature_tree"]["root_id"] = root_id
        facts = migrated.get("confirmed_facts", [])

        migrated["feature_tree"]["nodes"][root_id] = {
            "node_id": root_id, "name": migrated.get("project_name", ""),
            "level": "product", "status": "confirmed", "depth": 0,
            "parent_id": None, "children": [],
            "vision": "", "target_users": [], "roles": [], "success_criteria": [],
            "mvp_scope": [], "out_of_scope": [], "business_rules": [], "permission_rules": [],
            "user_stories": [], "acceptance_criteria": [], "success_path": [], "failure_path": [],
            "edge_cases": [], "data_requirements": [], "dependencies": [], "assumptions": [],
            "explicit_checks": {}, "source_refs": [], "conversation_turns": [],
            "last_question": migrated.get("user_message", ""), "review_feedback": [],
            "confirmed_at": migrated.get("created_at", ""),
        }

        # 按 topic 分组 facts 到子节点
        topic_seen: dict[str, str] = {}
        node_counter = 0
        for fact in facts:
            topic = fact.get("topic", "未知")
            if topic not in topic_seen:
                node_id = f"fn-topic-{node_counter}"
                node_counter += 1
                topic_seen[topic] = node_id
                child = {
                    "node_id": node_id, "name": topic, "level": "function",
                    "status": "confirmed", "depth": 1, "parent_id": root_id,
                    "children": [],
                    "user_stories": [fact.get("fact", "")],
                    "source_refs": [{"turn_id": "v1-migrated", "quote": fact.get("source_quote", ""), "field_name": "user_stories", "confidence": 0.5}],
                    "acceptance_criteria": [], "success_path": [], "failure_path": [],
                    "edge_cases": [], "data_requirements": [], "dependencies": [],
                    "assumptions": [], "explicit_checks": {}, "conversation_turns": [],
                    "last_question": "", "review_feedback": [], "confirmed_at": "",
                    "vision": "", "target_users": [], "roles": [], "success_criteria": [],
                    "mvp_scope": [], "out_of_scope": [], "business_rules": [], "permission_rules": [],
                }
                migrated["feature_tree"]["nodes"][node_id] = child
                migrated["feature_tree"]["nodes"][root_id]["children"].append(node_id)
            else:
                # 同一 topic 的 fact 追加到已有节点的 user_stories
                existing_id = topic_seen[topic]
                migrated["feature_tree"]["nodes"][existing_id]["user_stories"].append(fact.get("fact", ""))

    return migrated


def dict_to_brainstorm(data: dict) -> BrainstormRecord:
    """从 dict 反序列化，含 V1→V2 自动迁移"""
    data = migrate_v1_to_v2(data)

    def build_source_refs(refs) -> list[SourceRef]:
        return [SourceRef(**r) for r in refs] if refs else []

    def build_evidence_refs(refs) -> list[EvidenceRef]:
        return [EvidenceRef(**r) for r in refs] if refs else []

    def build_explicit_checks(checks) -> dict[str, ExplicitCheck]:
        result: dict[str, ExplicitCheck] = {}
        for k, v in (checks or {}).items():
            if isinstance(v, dict):
                result[k] = ExplicitCheck(
                    **{kk: vv for kk, vv in v.items() if kk != "source_refs"},
                    source_refs=build_source_refs(v.get("source_refs", [])),
                )
        return result

    def build_feature_nodes(nodes_dict) -> dict[str, FeatureNode]:
        result: dict[str, FeatureNode] = {}
        for nid, ndata in nodes_dict.items():
            result[nid] = FeatureNode(
                **{k: v for k, v in ndata.items() if k not in ("explicit_checks", "source_refs")},
                explicit_checks=build_explicit_checks(ndata.get("explicit_checks")),
                source_refs=build_source_refs(ndata.get("source_refs")),
            )
        return result

    # ── V3 辅助函数 ──

    def build_proactive_items(items_data) -> list[ProactiveAnalysisItem]:
        return [
            ProactiveAnalysisItem(
                **{k: v for k, v in item.items() if k != "source_refs"},
                source_refs=build_source_refs(item.get("source_refs", [])),
            )
            for item in (items_data or [])
        ]

    def build_proactive_analysis(pa_data) -> ProactiveAnalysis | None:
        if not pa_data:
            return None
        return ProactiveAnalysis(
            analysis_id=pa_data["analysis_id"],
            items=build_proactive_items(pa_data.get("items", [])),
            summary=pa_data.get("summary", ""),
            created_at=pa_data.get("created_at", ""),
            confirmed_at=pa_data.get("confirmed_at", ""),
        )

    def build_deliberation_findings(findings_data) -> list[DeliberationFinding]:
        return [DeliberationFinding(**f) for f in (findings_data or [])]

    def build_deliberation_round(round_data) -> DeliberationRound:
        return DeliberationRound(
            round_id=round_data["round_id"],
            findings=build_deliberation_findings(round_data.get("findings", [])),
            pm_summary=round_data.get("pm_summary", ""),
            created_at=round_data.get("created_at", ""),
            completed_at=round_data.get("completed_at", ""),
        )

    def build_technical_route(tr_data) -> TechnicalRoute | None:
        if not tr_data:
            return None
        return TechnicalRoute(**tr_data)

    def build_tool_candidates(tc_data) -> list[ToolCandidate]:
        result: list[ToolCandidate] = []
        for candidate in (tc_data or []):
            result.append(ToolCandidate(
                **{k: v for k, v in candidate.items() if k != "evidence_refs"},
                evidence_refs=build_evidence_refs(candidate.get("evidence_refs", [])),
            ))
        return result

    def build_tool_evaluations(te_data) -> list[ToolEvaluation]:
        return [ToolEvaluation(**e) for e in (te_data or [])]

    def build_tool_discovery(td_data) -> ToolDiscoveryResult:
        return ToolDiscoveryResult(
            discovery_id=td_data["discovery_id"],
            tool_need=td_data["tool_need"],
            queries=td_data.get("queries", []),
            candidates=build_tool_candidates(td_data.get("candidates", [])),
            evaluations=build_tool_evaluations(td_data.get("evaluations", [])),
            selected_candidate_ids=td_data.get("selected_candidate_ids", []),
            created_at=td_data.get("created_at", ""),
        )

    def build_product_def_finding(f_data) -> ProductDefFinding:
        return ProductDefFinding(**f_data)

    def build_product_def_round(r_data) -> ProductDefRound:
        return ProductDefRound(
            round_id=r_data["round_id"],
            findings=[build_product_def_finding(f) for f in r_data.get("findings", [])],
            summary=r_data.get("summary", ""),
            created_at=r_data.get("created_at", ""),
            confirmed_at=r_data.get("confirmed_at", ""),
        )

    def build_product_def_progress(p_data) -> ProductDefProgress | None:
        if not p_data:
            return None
        return ProductDefProgress(
            total_dimensions=p_data.get("total_dimensions", 4),
            dimensions_analyzed=p_data.get("dimensions_analyzed", []),
            current_dimension=p_data.get("current_dimension"),
            partial_findings=[build_product_def_finding(f) for f in p_data.get("partial_findings", [])],
            started_at=p_data.get("started_at", ""),
            completed_at=p_data.get("completed_at"),
        )

    def build_phase_output_snapshot(s_data) -> PhaseOutputSnapshot:
        return PhaseOutputSnapshot(
            phase=s_data["phase"],
            label=s_data["label"],
            completed_at=s_data["completed_at"],
            confirmed=s_data.get("confirmed", False),
            confirmed_at=s_data.get("confirmed_at", ""),
            summary=s_data.get("summary", ""),
            detail=s_data.get("detail", {}),
        )

    def build_execution_task(et_data) -> ExecutionTask:
        return ExecutionTask(**{k: v for k, v in et_data.items()})

    def build_executable_plan(ep_data) -> ExecutablePlan | None:
        if not ep_data:
            return None
        tasks = [build_execution_task(t) for t in ep_data.get("tasks", [])]
        return ExecutablePlan(
            **{k: v for k, v in ep_data.items() if k != "tasks"},
            tasks=tasks,
        )

    # ── 构建现有 V2 字段 ──

    ft_data = data.get("feature_tree", {})
    feature_tree = FeatureTree(
        root_id=ft_data.get("root_id", ""),
        nodes=build_feature_nodes(ft_data.get("nodes", {})),
        current_exploring_id=ft_data.get("current_exploring_id"),
        recursion_stack=ft_data.get("recursion_stack", []),
        question_plan=[QuestionTask(**t) for t in ft_data.get("question_plan", [])],
        current_question_id=ft_data.get("current_question_id"),
        unresolved_question_ids=ft_data.get("unresolved_question_ids", []),
    )

    rg_data = data.get("relationship_graph", {})
    relationship_graph = RelationshipGraph(
        edges=[RelationshipEdge(**e) for e in rg_data.get("edges", [])],
        conflicts=[ConflictRecord(**c) for c in rg_data.get("conflicts", [])],
        flow_validations=[FlowValidation(**f) for f in rg_data.get("flow_validations", [])],
        analyzed_at=rg_data.get("analyzed_at", ""),
    )

    review_data = data.get("review_result")
    review_result: ReviewResult | None = None
    if review_data:
        review_result = ReviewResult(
            passed=review_data["passed"],
            findings=[ReviewFinding(**f) for f in review_data.get("findings", [])],
            reviewed_at=review_data.get("reviewed_at", ""),
        )

    return BrainstormRecord(
        record_id=data["record_id"],
        project_name=data["project_name"],
        version=data.get("version", 2),
        schema_version=data.get("schema_version", "v2"),
        current_phase=data.get("current_phase", "product_def"),
        phase_history=data.get("phase_history", []),
        phase_outputs={k: build_phase_output_snapshot(v) for k, v in data.get("phase_outputs", {}).items()},
        feature_tree=feature_tree,
        relationship_graph=relationship_graph,
        review_result=review_result,
        task_handoff_hints=[TaskHandoffHint(**h) for h in data.get("task_handoff_hints", [])],
        product_def_rounds=[build_product_def_round(r) for r in data.get("product_def_rounds", [])],
        product_def_progress=build_product_def_progress(data.get("product_def_progress")),
        proactive_analysis=build_proactive_analysis(data.get("proactive_analysis")),
        deliberation_rounds=[build_deliberation_round(r) for r in data.get("deliberation_rounds", [])],
        technical_route=build_technical_route(data.get("technical_route")),
        technical_route_history=[
            route for route in (build_technical_route(r) for r in data.get("technical_route_history", []))
            if route is not None
        ],
        tool_discovery_results=[build_tool_discovery(r) for r in data.get("tool_discovery_results", [])],
        executable_plan=build_executable_plan(data.get("executable_plan")),
        round_number=data.get("round_number", 0),
        user_message=data.get("user_message", ""),
        confirmed_facts=[ConfirmedFact(**f) for f in data.get("confirmed_facts", [])],
        open_assumptions=[OpenAssumption(**a) for a in data.get("open_assumptions", [])],
        user_paths=[UserPath(**p) for p in data.get("user_paths", [])],
        system_questions=data.get("system_questions", []),
        created_at=data.get("created_at", ""),
        completed_at=data.get("completed_at", ""),
    )


def brainstorm_to_dict(record: BrainstormRecord) -> dict:
    """将 BrainstormRecord 序列化为 dict"""
    from dataclasses import asdict
    return asdict(record)
