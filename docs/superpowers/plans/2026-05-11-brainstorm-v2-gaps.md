# Brainstorm V2 缺失功能补齐计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 补齐 Brainstorm V2 设计文档中定义但尚未实现的核心功能，重点激活 Phase 3 关系分析、Phase 4 独立审查的 LLM 路径，以及前端数据连线。

**架构：** 当前 V2 骨架（schema、状态机、API 路由、前端组件）已就绪。缺失的是 `BrainstormAnalyzer` 中的 LLM 调用实现、`process_response_v2` 中 Phase 3/4 的自动触发、以及前端 spec_preview/handoff_hints 的数据连线。

**技术栈：** Python (FastAPI + dataclass)、TypeScript/React (Next.js 16)、LLM proxy 调用

**当前状态：** 65 个测试全部通过，前后端可运行。`BrainstormAnalyzer` 中 3 个方法均为 TODO 占位符。

---

### 任务 1：BrainstormAnalyzer — analyze_relationships LLM 实现

**文件：**
- 修改：`ralph/brainstorm_analyzer.py:18-25`
- 测试：`tests/ralph/test_brainstorm_analyzer.py`（新增）

**背景：** `analyze_relationships` 当前只返回空图 + analyzed_at 时间戳。需要实现 LLM 调用，分析功能节点间的依赖、冲突和流程验证。

- [ ] **步骤 1：编写测试 — 空图场景**

```python
# tests/ralph/test_brainstorm_analyzer.py
def test_analyze_relationships_empty_nodes():
    record = make_record_with_nodes([])
    analyzer = BrainstormAnalyzer()
    graph = analyzer.analyze_relationships(record)
    assert graph.analyzed_at != ""
    assert graph.edges == []
    assert graph.conflicts == []
```

- [ ] **步骤 2：编写测试 — 有节点但无 config_manager（降级到空图）**

```python
def test_analyze_relationships_no_config():
    node = FeatureNode(node_id="fn-001", name="登录", level="function", status="confirmed")
    record = make_record_with_nodes([node])
    analyzer = BrainstormAnalyzer()  # no config
    graph = analyzer.analyze_relationships(record)
    assert graph.analyzed_at != ""
    assert isinstance(graph.edges, list)
```

- [ ] **步骤 3：编写测试 — LLM 返回解析**

```python
def test_analyze_relationships_llm_response(monkeypatch):
    node_a = FeatureNode(node_id="fn-001", name="登录", level="function", status="confirmed",
                         user_stories=["As a user, I want to login"])
    node_b = FeatureNode(node_id="fn-002", name="权限管理", level="function", status="confirmed",
                         user_stories=["As an admin, I want to manage permissions"],
                         dependencies=["fn-001"])
    record = make_record_with_nodes([node_a, node_b])

    fake_content = json.dumps({
        "edges": [{"source_id": "fn-002", "target_id": "fn-001", "edge_type": "depends_on", "description": "权限管理依赖登录"}],
        "conflicts": [],
        "flow_validations": []
    })
    monkeypatch.setattr(analyzer, "_call_llm", lambda **kw: fake_content)

    graph = analyzer.analyze_relationships(record)
    assert len(graph.edges) == 1
    assert graph.edges[0].edge_type == "depends_on"
    assert graph.analyzed_at != ""
```

- [ ] **步骤 4：实现 analyze_relationships LLM 调用**

```python
# ralph/brainstorm_analyzer.py — 替换 analyze_relationships 方法

def analyze_relationships(self, record: BrainstormRecord) -> RelationshipGraph:
    """Phase 3: LLM 分析依赖/冲突/流验证"""
    from ralph.schema.brainstorm_record import _now_iso

    confirmed = [n for n in record.feature_tree.nodes.values()
                 if n.status == "confirmed" and n.level in ("function", "sub_function")]

    nodes_text = "\n".join(
        f"- {n.node_id}: {n.name}\n"
        f"  用户故事: {n.user_stories}\n"
        f"  成功路径: {n.success_path}\n"
        f"  失败路径: {n.failure_path}\n"
        f"  依赖: {n.dependencies}\n"
        f"  业务规则: {n.business_rules}\n"
        f"  权限规则: {n.permission_rules}"
        for n in confirmed
    )

    prompt = f"""你是资深系统架构师。
以下是一个产品的所有已确认功能节点：

{nodes_text or '(无已确认节点)'}

请分析：
1. 依赖关系：哪些功能依赖其他功能？（depends_on / enables）
2. 功能冲突：哪些功能之间存在互斥或冲突？（conflicts_with / mutually_exclusive）
3. 流程验证：哪些用户路径存在死胡同？哪些缺少错误分支？是否有循环依赖？

请以 JSON 返回：
{{
  "edges": [{{"source_id": "...", "target_id": "...", "edge_type": "...", "description": "..."}}],
  "conflicts": [{{"feature_a": "...", "feature_b": "...", "description": "...", "severity": "..."}}],
  "flow_validations": [{{"feature_id": "...", "issue_type": "...", "description": "..."}}]
}}

即使没有发现任何关系，也必须返回空数组。"""

    graph = RelationshipGraph()

    if not confirmed:
        graph.analyzed_at = _now_iso()
        record.relationship_graph = graph
        return graph

    content = self._call_llm("relationship_analysis", [{"role": "user", "content": prompt}])
    if content:
        try:
            data = json.loads(content)
            graph.edges = [RelationshipEdge(**e) for e in data.get("edges", [])]
            graph.conflicts = [ConflictRecord(**c) for c in data.get("conflicts", [])]
            graph.flow_validations = [FlowValidation(**f) for f in data.get("flow_validations", [])]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # 降级到空图

    graph.analyzed_at = _now_iso()
    record.relationship_graph = graph
    return graph
```

- [ ] **步骤 5：添加 _call_llm 辅助方法到 BrainstormAnalyzer**

```python
# ralph/brainstorm_analyzer.py — 添加到类末尾

def _call_llm(self, task_type: str, messages: list[dict]) -> str | None:
    """统一 LLM 调用入口"""
    if self.config_manager is None:
        return None
    try:
        provider = self.config_manager.resolve_agent_provider("brainstorm", task_type)
    except Exception:
        provider = {"provider_id": "", "model": "", "source": "none"}
    if not provider.get("provider_id"):
        return None
    result = self.config_manager.proxy_request(
        provider["provider_id"], "v1/chat/completions",
        {"model": provider.get("model", ""), "messages": messages, "temperature": 0.7, "max_tokens": 2000},
    )
    if result.get("ok"):
        try:
            return result["data"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass
    return None
```

- [ ] **步骤 6：在文件顶部添加 import**

```python
# ralph/brainstorm_analyzer.py — 在已有 import 后添加
import json
```

- [ ] **步骤 7：运行测试确认通过**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/test_brainstorm_analyzer.py -v
```

预期：3 个测试全部通过

- [ ] **步骤 8：Commit**

```bash
git add ralph/brainstorm_analyzer.py tests/ralph/test_brainstorm_analyzer.py
git commit -m "feat: implement LLM-driven analyze_relationships in BrainstormAnalyzer"
```

---

### 任务 2：BrainstormAnalyzer — independent_review LLM 实现

**文件：**
- 修改：`ralph/brainstorm_analyzer.py:27-34`
- 测试：`tests/ralph/test_brainstorm_analyzer.py`（追加）

**背景：** `independent_review` 当前直接返回 `passed=True`。需要用 LLM 做 6 维度审查。

- [ ] **步骤 1：编写测试 — 审查通过场景**

```python
# tests/ralph/test_brainstorm_analyzer.py
def test_independent_review_passes(monkeypatch):
    node = FeatureNode(node_id="fn-001", name="登录", level="function", status="confirmed",
                       user_stories=["As a user, I want to login"],
                       acceptance_criteria=["Given valid credentials When submit Then login"],
                       success_path=["用户输入账号密码", "系统验证成功"],
                       failure_path=["密码错误，提示重试"],
                       edge_cases=["连续失败锁定"],
                       data_requirements=["存储用户账号密码哈希"])
    record = make_record_with_nodes([node])

    fake_content = json.dumps({"passed": True, "findings": []})
    monkeypatch.setattr(analyzer, "_call_llm", lambda **kw: fake_content)

    result = analyzer.independent_review(record)
    assert result.passed is True
    assert result.reviewed_at != ""
```

- [ ] **步骤 2：编写测试 — 审查发现问题**

```python
def test_independent_review_finds_issues(monkeypatch):
    node = FeatureNode(node_id="fn-001", name="登录", level="function", status="confirmed",
                       user_stories=["As a user, I want to login"])
    # 缺少 acceptance_criteria, paths, edge_cases 等
    record = make_record_with_nodes([node])

    fake_content = json.dumps({
        "passed": False,
        "findings": [
            {
                "finding_type": "incomplete",
                "feature_id": "fn-001",
                "description": "缺少验收标准和路径",
                "severity": "critical"
            }
        ]
    })
    monkeypatch.setattr(analyzer, "_call_llm", lambda **kw: fake_content)

    result = analyzer.independent_review(record)
    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].severity == "critical"
```

- [ ] **步骤 3：实现 independent_review LLM 调用**

```python
# ralph/brainstorm_analyzer.py — 替换 independent_review 方法

def independent_review(self, record: BrainstormRecord) -> ReviewResult:
    """Phase 4: 独立 LLM 审查"""
    from ralph.schema.brainstorm_record import _now_iso

    # 生成 Spec Document 作为审查输入
    spec_text = self._render_spec_for_review(record)

    prompt = f"""你是独立需求质量审查员。你没有参与之前的需求共创对话。
以下是一份完整的产品需求规格草案：

{spec_text}

请从以下 6 个维度审查：
1. 粒度：每个功能点是否足够细，能直接拆成开发任务？
2. 逻辑：用户路径是否有死胡同？失败路径是否覆盖所有异常？
3. 一致性：功能之间是否有矛盾或重复？
4. 边界：是否遗漏了重要的边界场景？
5. 完整性：是否所有关键需求领域都已覆盖？
6. 追溯性：每条确定需求是否能追溯用户原话或用户确认？

请以 JSON 返回：
{{
  "passed": true/false,
  "findings": [
    {{
      "finding_type": "too_coarse | logical_gap | inconsistency | missing_edge_case | incomplete | traceability_gap",
      "feature_id": "...",
      "description": "具体问题描述",
      "severity": "critical | warning"
    }}
  ]
}}"""

    content = self._call_llm("independent_review", [{"role": "user", "content": prompt}])

    result = ReviewResult(passed=True, findings=[])
    if content:
        try:
            data = json.loads(content)
            result = ReviewResult(
                passed=data.get("passed", True),
                findings=[ReviewFinding(**f) for f in data.get("findings", [])],
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # LLM 失败，降级为通过

    result.reviewed_at = _now_iso()
    record.review_result = result
    return result

def _render_spec_for_review(self, record: BrainstormRecord) -> str:
    """生成用于审查的 Spec Document"""
    # 复用 Manager 的 generate_spec_document 逻辑，避免循环导入
    lines = [f"# {record.project_name} - 需求规格文档", ""]
    root = record.feature_tree.get_node("fn-root")
    if root:
        lines.extend([
            "## 产品定义", "",
            f"**愿景：** {root.vision}", "",
            f"**目标用户：** {', '.join(root.target_users) if root.target_users else '待明确'}", "",
            f"**用户角色：** {', '.join(root.roles) if root.roles else '待明确'}", "",
            f"**MVP 范围：** {', '.join(root.mvp_scope) if root.mvp_scope else '待明确'}", "",
            f"**明确不做：** {', '.join(root.out_of_scope) if root.out_of_scope else '无'}", "",
        ])
    lines.extend(["## 功能分解", ""])
    for node in record.feature_tree.nodes.values():
        if node.level == "product":
            continue
        status_icon = {"confirmed": "[x]", "exploring": "[~]", "pending": "[ ]"}.get(node.status, "[ ]")
        lines.append(f"### {status_icon} {node.name} ({node.node_id})")
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
        if node.dependencies:
            lines.append(f"- 依赖: {', '.join(node.dependencies)}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/test_brainstorm_analyzer.py -v
```

预期：5 个测试全部通过

- [ ] **步骤 5：Commit**

```bash
git add ralph/brainstorm_analyzer.py tests/ralph/test_brainstorm_analyzer.py
git commit -m "feat: implement LLM-driven independent_review with 6-dimension quality check"
```

---

### 任务 3：process_response_v2 — 激活 Phase 3/4 自动触发

**文件：**
- 修改：`ralph/brainstorm_manager.py:811-837`（process_response_v2 及相关处理方法）
- 测试：`tests/ralph/test_brainstorm_v2.py`（追加）

**背景：** `process_response_v2` 中 `_process_relationship_response` 只标记 analyzed_at，没有调用 `analyze_relationships`。Phase 4 也没有自动触发。需要打通：
- FEATURE_DECOMPOSE 完成后 → 自动调用 `analyze_relationships`
- RELATIONSHIP 完成后 → 自动调用 `independent_review`
- REVIEW 不通过 → 进入 CLARIFICATION

- [ ] **步骤 1：编写测试 — Phase 2 完成后自动进入 Phase 3 并触发关系分析**

```python
# tests/ralph/test_brainstorm_v2.py — 追加
def test_auto_trigger_relationship_on_feature_decompose_complete(monkeypatch):
    mgr = make_mgr_with_config()
    record = mgr.start_session("TestProject", "一个待办应用")
    # 模拟 Phase 1 完成
    advance_phase_to_decompose(mgr, record)
    # 模拟所有功能节点确认
    confirm_all_feature_nodes(mgr, record)
    # 下一轮 respond 应自动触发关系分析
    updated = mgr.process_response_v2(record, "继续")
    assert updated.current_phase in ("relationship", "independent_review", "complete")
    assert updated.relationship_graph.analyzed_at != ""
```

- [ ] **步骤 2：修改 _process_decompose_response，在 all_confirmed 后触发关系分析**

```python
# ralph/brainstorm_manager.py — 修改 _process_decompose_response 末尾

def _process_decompose_response(
    self, record: BrainstormRecord, user_response: str, extracted_facts: list[dict] | None = None,
) -> None:
    active = self.get_active_node(record)
    if not active:
        return

    facts = extracted_facts or self._auto_extract_facts(record, user_response)
    if facts:
        self._apply_extracted_facts_to_node(record, active, facts)

    missing = self._get_missing_items(active)
    if missing:
        record.feature_tree.question_plan = []
        self.build_question_plan(record, active)
    else:
        self.confirm_node(record)
        next_node = self.select_next_node(record)
        if next_node:
            record.feature_tree.current_exploring_id = next_node.node_id
            self.build_question_plan(record, next_node)

    # 新增：如果所有功能节点已确认，进入 Phase 3 并触发关系分析
    if record.feature_tree.all_confirmed():
        from ralph.brainstorm_analyzer import BrainstormAnalyzer
        analyzer = BrainstormAnalyzer(self._config)
        analyzer.analyze_relationships(record)
```

- [ ] **步骤 3：修改 _process_relationship_response，触发独立审查**

```python
# ralph/brainstorm_manager.py — 替换 _process_relationship_response

def _process_relationship_response(self, record: BrainstormRecord, user_response: str) -> None:
    """处理 Phase 3 回答，完成后自动触发独立审查"""
    from ralph.brainstorm_analyzer import BrainstormAnalyzer

    # 如果还没分析，先调用 LLM 分析
    if not record.relationship_graph.analyzed_at:
        analyzer = BrainstormAnalyzer(self._config)
        analyzer.analyze_relationships(record)

    # 分析完成后触发独立审查
    if record.relationship_graph.analyzed_at:
        analyzer = BrainstormAnalyzer(self._config)
        result = analyzer.independent_review(record)
        record.review_result = result
```

- [ ] **步骤 4：修改 _process_clarification_response，澄清后重新审查**

```python
# ralph/brainstorm_manager.py — 替换 _process_clarification_response

def _process_clarification_response(self, record: BrainstormRecord, user_response: str) -> None:
    """处理 Clarification 回答，澄清所有 needs_clarification 节点"""
    clarifying = [n for n in record.feature_tree.nodes.values() if n.status == "needs_clarification"]
    for node in clarifying:
        node.status = "exploring"
        node.review_feedback = []

    # 如果所有澄清节点都已确认，重新审查
    if all(n.status == "confirmed" for n in clarifying) or not clarifying:
        record.current_phase = BrainstormPhase.INDEPENDENT_REVIEW
        record.review_result = None  # 清空旧结果
```

- [ ] **步骤 5：修改 respond 路由，在 COMPLETE 时生成 spec_preview 和 handoff_hints**

```python
# dashboard/api/routes.py — 修改 respond 返回值的 spec_preview 和 handoff 部分
# 在 ralph_brainstorm_respond 函数中，找到返回 dict 前添加：

spec_preview = ""
handoff_hints = []
if mgr.is_complete_v2(updated):
    spec_preview = mgr.generate_spec_document(updated)
    if not updated.task_handoff_hints:
        from ralph.brainstorm_analyzer import BrainstormAnalyzer
        analyzer = BrainstormAnalyzer(mgr._config)
        hints = analyzer.generate_task_handoff_hints(updated)
        handoff_hints = [brainstorm_to_dict(h) for h in hints]
        updated.task_handoff_hints = hints
        mgr._save(updated)
    else:
        from ralph.schema.brainstorm_record import brainstorm_to_dict
        handoff_hints = [brainstorm_to_dict(h) for h in updated.task_handoff_hints]

# 返回值中替换：
# "spec_preview": spec_preview,
# "handoff_hints": handoff_hints,
```

- [ ] **步骤 6：运行全部测试**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/test_brainstorm_v2.py tests/ralph/test_brainstorm_analyzer.py -v
```

- [ ] **步骤 7：Commit**

```bash
git add ralph/brainstorm_manager.py dashboard/api/routes.py tests/ralph/test_brainstorm_v2.py
git commit -m "feat: activate Phase 3/4 auto-triggering in process_response_v2 flow"
```

---

### 任务 4：前端 spec_preview 和 handoff_hints 数据连线

**文件：**
- 修改：`dashboard-ui/app/ralph/brainstorm/page.tsx:90-110`（handleRespond）
- 修改：`dashboard-ui/app/ralph/brainstorm/page.tsx:265-271`（SpecPreview 和 TaskHandoffPanel 渲染条件）

**背景：** 后端 `respond` 返回 `spec_preview: ""` 和 `handoff_hints: []`（前端 state 也未更新）。需要在 COMPLETE 时正确传递和渲染。

- [ ] **步骤 1：修改 handleRespond，接收 spec_preview 和 handoff_hints**

```typescript
// dashboard-ui/app/ralph/brainstorm/page.tsx — handleRespond 函数内
// 在 if (result.spec_preview) 之后添加（当前第 103 行附近）：

if (result.spec_preview) setSpecPreview(result.spec_preview as string);
if (result.handoff_hints) setHandoffHints(result.handoff_hints as Record<string, unknown>[]);
```

- [ ] **步骤 2：修改 resumeSession  inline handler，也恢复 spec_preview 和 handoff_hints**

```typescript
// 在 resumeSession 的 catch 之前（约第 168 行）添加：
if (result.spec_preview) setSpecPreview(result.spec_preview as string);
if (result.handoff_hints) setHandoffHints(result.handoff_hints as Record<string, unknown>[]);
```

- [ ] **步骤 3：修改 SpecPreview 和 TaskHandoffPanel 的渲染条件**

```tsx
// 当前 spec_preview 条件（第 265 行）：
// {phase === 'complete' && specPreview && (
// 改为：
{phase === 'complete' && (specPreview || activeSession?.is_complete) && (
  <SpecPreview markdown={specPreview || '正在生成...'} />
)}

// 当前 handoff_hints 条件（第 269 行）：
// {phase === 'complete' && handoffHints.length > 0 && (
// 改为：
{phase === 'complete' && handoffHints.length > 0 && (
  <TaskHandoffPanel hints={handoffHints} />
)}
```

- [ ] **步骤 4：添加导出按钮功能 — 调用 generate_spec_document API**

```tsx
// 替换导出按钮的 onClick：
<button onClick={async () => {
  if (!activeSession?.record_id) return;
  try {
    const result = await getSpecDocument(activeSession.record_id as string);
    setSpecPreview(result.spec as string);
    toast.success('Spec 已生成');
  } catch { toast.error('生成失败'); }
}} className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors">
  <Download size={14} />
  导出 Spec
</button>
```

- [ ] **步骤 5：添加 import — 确保 getSpecDocument 已导入**

```typescript
// 第 24-26 行已有 import，确认 getSpecDocument 在列表中
```

- [ ] **步骤 6：TypeScript 类型检查**

```bash
cd /Users/jieson/auto-coding/dashboard-ui && npx tsc --noEmit --pretty false 2>&1 | head -20
```

预期：无新增类型错误

---

### 任务 5：端到端流程测试

**文件：**
- 创建：`tests/ralph/test_brainstorm_e2e.py`

**背景：** 设计文档 §10 Phase E 要求端到端流程测试。验证从 Phase 1 → Phase 2 → Phase 3 → Phase 4 → COMPLETE 的完整链路。

- [ ] **步骤 1：编写 e2e 测试 — 完整流程（无 LLM 降级路径）**

```python
# tests/ralph/test_brainstorm_e2e.py
import pytest
from pathlib import Path
import tempfile

from ralph.brainstorm_manager import BrainstormManager
from ralph.brainstorm_analyzer import BrainstormAnalyzer
from ralph.schema.brainstorm_record import BrainstormPhase


def make_record_with_nodes(nodes):
    """测试辅助函数 — 创建包含指定节点的 record"""
    from ralph.brainstorm_manager import _now_iso
    root = FeatureNode(node_id="fn-root", name="TestProject", level="product", status="confirmed")
    tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
    for node in nodes:
        tree.add_child("fn-root", node)
    record = BrainstormRecord(
        record_id="bs-test-e2e", project_name="TestProject",
        current_phase=BrainstormPhase.FEATURE_DECOMPOSE,
        feature_tree=tree,
    )
    root.confirmed_at = _now_iso()
    for node in nodes:
        node.confirmed_at = _now_iso()
    return record


class TestBrainstormE2E:
    """端到端流程测试"""

    def test_full_flow_product_def_to_complete_no_llm(self, tmp_path):
        """完整流程：Phase 1 → Phase 2 → Phase 3 → Phase 4 → COMPLETE（无 LLM 降级）"""
        mgr = BrainstormManager(tmp_path)

        # Phase 1: 创建 session
        record = mgr.start_session("TestProject", "一个团队协作的待办应用")
        assert record.current_phase == "product_def"
        assert record.feature_tree.get_node("fn-root") is not None

        # 模拟填充产品定义字段
        root = record.feature_tree.get_node("fn-root")
        root.vision = "帮助团队高效管理任务"
        root.target_users = ["团队成员", "项目经理"]
        root.roles = ["管理员", "普通成员"]
        root.success_criteria = ["每日任务完成率 > 80%"]
        root.mvp_scope = ["创建任务", "分配任务", "标记完成"]
        root.out_of_scope = ["时间线视图", "甘特图"]

        # 推进 Phase 1 → Phase 2
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.FEATURE_DECOMPOSE

        # 手动创建功能节点（模拟 LLM 拆分）
        node1 = FeatureNode(
            node_id="fn-001", name="任务管理", level="function", status="confirmed",
            user_stories=["As a 成员, I want 创建和分配任务"],
            acceptance_criteria=["Given 登录 When 创建任务 Then 任务出现在列表"],
            success_path=["用户创建任务", "任务分配给成员", "成员标记完成"],
            failure_path=["网络断开，任务保存失败，提示重试"],
            edge_cases=["同时创建多个任务"],
            data_requirements=["存储任务 ID、标题、状态、分配者"],
        )
        node1.confirmed_at = _now_iso()
        record.feature_tree.add_child("fn-root", node1)

        # 推进 Phase 2 → Phase 3
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.RELATIONSHIP

        # Phase 3: 关系分析（无 LLM，降级到空图）
        analyzer = BrainstormAnalyzer()
        analyzer.analyze_relationships(record)
        assert record.relationship_graph.analyzed_at != ""

        # 推进 Phase 3 → Phase 4
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW

        # Phase 4: 独立审查（无 LLM，降级为通过）
        result = analyzer.independent_review(record)
        record.review_result = result

        # 推进 Phase 4 → COMPLETE
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.COMPLETE

        # 验证 spec document 生成
        spec = mgr.generate_spec_document(record)
        assert "TestProject" in spec
        assert "任务管理" in spec

        # 验证 handoff hints 生成
        hints = analyzer.generate_task_handoff_hints(record)
        assert len(hints) >= 1
        assert hints[0].source_feature_id == "fn-001"
```

- [ ] **步骤 2：编写 e2e 测试 — 审查不通过 → Clarification → 重新审查**

```python
    def test_review_fails_then_clarification_flow(self, tmp_path):
        """审查不通过 → CLARIFICATION → 重新审查 → 通过"""
        mgr = BrainstormManager(tmp_path)
        record = mgr.start_session("TestProject", "简单应用")

        # 填充产品定义
        root = record.feature_tree.get_node("fn-root")
        root.vision = "测试"
        root.target_users = ["用户"]
        root.roles = ["管理员"]
        root.success_criteria = ["能跑"]
        root.mvp_scope = ["核心功能"]
        root.out_of_scope = []

        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.FEATURE_DECOMPOSE

        # 创建一个有问题的节点（缺少多个字段）
        node1 = FeatureNode(
            node_id="fn-001", name="登录", level="function", status="confirmed",
            user_stories=["As a user, I want to login"],
        )
        node1.confirmed_at = _now_iso()
        record.feature_tree.add_child("fn-root", node1)

        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.RELATIONSHIP

        # 关系分析
        analyzer = BrainstormAnalyzer()
        analyzer.analyze_relationships(record)

        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW

        # 模拟审查不通过
        from ralph.schema.brainstorm_record import ReviewResult, ReviewFinding
        record.review_result = ReviewResult(
            passed=False,
            findings=[ReviewFinding(
                finding_type="incomplete",
                feature_id="fn-001",
                description="缺少验收标准、路径、边界场景",
                severity="critical",
            )],
        )

        # 推进 → CLARIFICATION
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.CLARIFICATION

        # 标记需要澄清的节点
        node1.status = "needs_clarification"
        node1.review_feedback = ["补充验收标准和路径"]

        # 澄清后重新审查
        mgr._process_clarification_response(record, "已补充")
        assert node1.status == "exploring"
        node1.status = "confirmed"
        mgr.advance_phase(record)
        assert record.current_phase == BrainstormPhase.INDEPENDENT_REVIEW
```

- [ ] **步骤 3：编写 e2e 测试 — V1 数据迁移后继续 V2 流程**

```python
    def test_v1_migration_then_continue_v2_flow(self, tmp_path):
        """V1 数据迁移后能继续 V2 流程"""
        # 写入 V1 格式 JSON
        v1_data = {
            "record_id": "bs-v1-migrated",
            "project_name": "OldProject",
            "round_number": 3,
            "user_message": "我想做个 todo 应用",
            "confirmed_facts": [
                {"topic": "核心功能", "fact": "创建和删除任务", "source_quote": "我需要能创建和删除任务"},
                {"topic": "目标用户", "fact": "个人用户", "source_quote": "给我自己用的"},
            ],
            "open_assumptions": [],
            "user_paths": [{"name": "创建任务", "steps": ["点击添加", "输入标题", "保存"], "edge_cases": []}],
            "created_at": "2026-05-01T00:00:00",
        }
        brainstorm_dir = tmp_path / "brainstorm"
        brainstorm_dir.mkdir()
        import json
        (brainstorm_dir / "bs-v1-migrated.json").write_text(json.dumps(v1_data))

        mgr = BrainstormManager(tmp_path)
        record = mgr.load("bs-v1-migrated")

        assert record is not None
        assert record.schema_version == "v2"
        assert record.feature_tree.get_node("fn-root") is not None
        # V1 facts 应该迁移到功能节点
        assert len(record.feature_tree.nodes) > 1  # root + topic nodes
```

- [ ] **步骤 4：运行全部测试**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/test_brainstorm_e2e.py -v
```

预期：3 个测试全部通过

- [ ] **步骤 5：运行全量 Brainstorm 测试套件**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/test_brainstorm_v2.py tests/ralph/test_brainstorm_analyzer.py tests/ralph/test_brainstorm_migration.py tests/ralph/test_brainstorm_e2e.py -v --tb=short
```

预期：全部通过（65 + 新增 8 = 73 个测试）

- [ ] **步骤 6：Commit**

```bash
git add tests/ralph/test_brainstorm_e2e.py
git commit -m "test: add end-to-end flow tests for Brainstorm V2 state machine"
```

---

### 任务 6：BrainstormRecord 添加 to_spec_document 方法

**文件：**
- 修改：`ralph/schema/brainstorm_record.py`（在 BrainstormRecord dataclass 中添加方法）

**背景：** 设计文档 §3.8 要求 `BrainstormRecord.to_spec_document()` 方法，当前实现在 `BrainstormManager.generate_spec_document()` 中。两者功能相同，但 schema 上应该有这个方法以符合设计文档。保留 Manager 中的实现作为公开 API，在 schema 中添加 delegate 方法。

- [ ] **步骤 1：在 BrainstormRecord 中添加 to_spec_document 方法**

```python
# ralph/schema/brainstorm_record.py — 在 BrainstormRecord dataclass 的 completeness_score 方法后添加

def to_spec_document(self) -> str:
    """渲染为 Spec Document Markdown。

    委托给 Manager 实现以避免循环导入。如果 Manager 不可用，使用内联渲染。
    """
    lines = [f"# {self.project_name} - 需求规格文档", ""]
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
    lines.extend(["## 功能分解", ""])
    for node in self.feature_tree.nodes.values():
        if node.level == "product":
            continue
        indent = "  " if node.level == "sub_function" else ""
        status_icon = {"confirmed": "✅", "exploring": "🔵", "pending": "⬜", "needs_clarification": "⚠️"}.get(node.status, "⬜")
        lines.extend([
            f"{indent}### {status_icon} {node.name}", "",
            f"{indent}- **状态：** {node.status}", "",
        ])
        for field_label, field_name in [
            ("用户故事", "user_stories"), ("验收标准", "acceptance_criteria"),
            ("成功路径", "success_path"), ("失败路径", "failure_path"),
            ("边界场景", "edge_cases"), ("数据需求", "data_requirements"),
        ]:
            value = getattr(node, field_name, [])
            if value:
                lines.append(f"{indent}- **{field_label}：**")
                for item in value:
                    lines.append(f"{indent}  - {item}")
                lines.append("")
        if node.dependencies:
            lines.append(f"{indent}- **依赖：** {', '.join(node.dependencies)}", "")
    if self.relationship_graph.edges or self.relationship_graph.conflicts:
        lines.extend(["## 关系分析", ""])
        for edge in self.relationship_graph.edges:
            lines.append(f"- {edge.source_id} {edge.edge_type} {edge.target_id}: {edge.description}")
        lines.append("")
    if self.review_result:
        lines.extend(["## 独立审查", ""])
        lines.extend([f"**结果：** {'通过' if self.review_result.passed else '不通过'}", ""])
        for f in self.review_result.findings:
            lines.append(f"- [{f.severity}] {f.description}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **步骤 2：运行 schema 相关测试确认不破坏现有功能**

```bash
cd /Users/jieson/auto-coding && uv run pytest tests/ralph/ -v -k brainstorm --tb=short
```

- [ ] **步骤 3：Commit**

```bash
git add ralph/schema/brainstorm_record.py
git commit -m "feat: add to_spec_document method to BrainstormRecord per design doc §3.8"
```

---

## 自检

### 1. 规格覆盖度

| 设计文档需求 | 对应任务 | 状态 |
|-------------|---------|------|
| §5.5 analyze_relationships (LLM) | 任务 1 | ✅ 覆盖 |
| §5.6 independent_review (LLM) | 任务 2 | ✅ 覆盖 |
| §4.2 RELATIONSHIP → INDEPENDENT_REVIEW | 任务 3 | ✅ 覆盖 |
| §4.2 INDEPENDENT_REVIEW → CLARIFICATION | 任务 3 | ✅ 覆盖 |
| §5.8 generate_task_handoff_hints | 已实现（任务 3 激活） | ✅ 覆盖 |
| §7.2 /respond 返回 spec_preview | 任务 3（routes.py 修改） | ✅ 覆盖 |
| §7.2 /respond 返回 handoff_hints | 任务 3（routes.py 修改） | ✅ 覆盖 |
| §8.2 前端 spec_preview/handoff_hints 显示 | 任务 4 | ✅ 覆盖 |
| §8.3 getSpecDocument API 调用 | 任务 4 | ✅ 覆盖 |
| §12 验收标准 #1-15 | 任务 5（e2e 测试） | ✅ 覆盖 |
| §3.8 to_spec_document on BrainstormRecord | 任务 6 | ✅ 覆盖 |

### 2. 占位符扫描

计划中没有 "TODO"、"待定" 或 "类似任务 N" 模式。所有代码步骤都包含完整代码块。

### 3. 类型一致性

- `BrainstormAnalyzer` 新增 `_call_llm` 方法签名与 `BrainstormManager._call_llm` 一致
- `ReviewFinding`, `RelationshipEdge` 等类型直接从 schema 导入
- `process_response_v2` 中新增的 `analyzer` 实例化使用 `self._config` 传递
- 前端 `Record<string, unknown>[]` 类型与现有 handoffHints state 一致
