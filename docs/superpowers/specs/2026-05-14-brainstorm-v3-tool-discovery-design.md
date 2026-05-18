# 需求共创 V3 与工具发现能力设计

> 目标：把 Brainstorm V2 从“问答式信息采集”升级为“主动产品共创 + 结构化功能审查”，并在开发前增加技术路线确认与第三方工具发现，减少盲目手写轮子。

## 一、核心判断

Brainstorm V2 当前主要是系统提问、用户回答、系统提取事实。这个流程适合补齐字段，但不适合用户只有模糊想法的早期共创场景。真正有价值的产品经理能力应该是：

1. 先给用户一个可反驳的产品框架，而不是让用户从零描述。
2. 把系统推测明确标记为“假设”，等用户确认后再进入正式需求。
3. 用多个审查视角挑战功能清单，但所有结论必须结构化、可追溯、可采纳/拒绝。
4. 在需求稳定后先确认技术路线，再做工具发现，避免实现 agent 盲目手搓已有成熟方案。

## 二、V3 总体流程

```text
用户模糊需求
→ PROACTIVE_ANALYSIS：系统生成假设草案
→ 用户确认/修改大方向
→ PRODUCT_DEF：补齐产品定义字段
→ FEATURE_DECOMPOSE：功能树拆解与粒度追问
→ DELIBERATION_REVIEW：四维结构化功能审查
→ PM 汇总并更新功能树
→ RELATIONSHIP：功能依赖、冲突、流程关系分析
→ INDEPENDENT_REVIEW：最终独立审查
→ REQUIREMENTS_READY：需求共创完成，可生成 PRD / Spec
→ TECHNICAL_ROUTE_DRAFT：基于冻结后的 PRD / Spec 生成技术路线草案
→ TOOL_DISCOVERY：基于确认后的技术路线搜索、评估、推荐第三方工具
→ EXECUTION_PLAN_READY：进入执行计划 / WorkUnit 生成
```

关键原则：

- 主动分析不是事实，它是带置信度的假设草案。
- 多 agent “辩论”不要做成自由聊天，而要做成多维结构化审查。
- Brainstorm V3 的边界是“把需求问清楚并审查通过”，不是把架构、选型、执行计划都塞进需求共创。
- 技术路线和工具发现属于开发前准备阶段，应接在 PRD / Spec 冻结之后。
- PM 不直接承载所有复杂逻辑，PM 负责组织和裁决，具体能力由 service 承担。
- 工具推荐必须带证据链和风险判断。

### 2.1 两段式产品体验

为了避免流程过长，V3 不应该一次性把所有确认步骤压给用户。建议拆成两段：

| 阶段 | 目标 | 用户感受 |
|------|------|----------|
| V3-A：需求共创增强 | 主动分析、产品定义、功能拆解、结构化审查、独立审查 | “系统帮我把想法变清楚” |
| V3-B：开发前准备 | 技术路线草案、第三方工具发现、执行计划前置判断 | “系统帮我决定怎么做，避免重复造轮子” |

V3-A 完成后，系统可以先生成 PRD / Spec。V3-B 在用户准备进入开发前触发，而不是强制每个 brainstorm session 都跑完整工具发现。

## 三、需求共创 V3

### 3.1 新增 `PROACTIVE_ANALYSIS` 阶段

位置：在 `PRODUCT_DEF` 之前。

用户抛出模糊需求后，系统先基于 LLM 生成一份产品假设草案，包括：

- 产品类型判断
- 目标用户猜测
- 核心场景推测
- 关键功能模块推测
- 可能的技术方向
- 主要风险点
- 需要用户优先确认的问题

注意：这些内容默认都是 `assumption`，不能直接写入 `FeatureNode` 的正式字段。只有用户确认或修改后，才能转成 `confirmed_facts` 或写入功能树。

建议新增数据结构：

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

`BrainstormRecord` 增加：

```python
proactive_analysis: ProactiveAnalysis | None = None
```

阶段守卫：

- `PROACTIVE_ANALYSIS → PRODUCT_DEF`：用户至少确认或修改核心产品类型、目标用户、核心场景。
- 被拒绝的假设不进入正式需求，但保留为决策记录。

### 3.2 保留并强化 `PRODUCT_DEF`

`PRODUCT_DEF` 继续负责补齐产品定义字段：

- `vision`
- `target_users`
- `roles`
- `success_criteria`
- `mvp_scope`
- `out_of_scope`

变化点：

- 问题生成时优先引用 `proactive_analysis` 中已接受或已修改的条目。
- 如果用户已经在主动分析阶段确认了某些字段，不重复追问。
- 每个字段仍需要来源追溯，避免系统脑补污染正式需求。

### 3.3 保留 `FEATURE_DECOMPOSE`

`FEATURE_DECOMPOSE` 继续负责功能树拆解和粒度门控。当前 V2 的 `FeatureTree`、`FeatureNode`、`QuestionTask` 可以继续使用。

需要调整：

- 自动拆分功能时，应同时参考已接受的 `ProactiveAnalysisItem`。
- 每个功能节点必须保留用户确认来源或 PM 采纳来源。
- LLM 自动拆出的功能默认状态为 `exploring`，不能直接 `confirmed`。

### 3.4 新增 `DELIBERATION_REVIEW` 阶段

原设计中的“多 agent 功能辩论”调整为结构化多维审查。

位置：`FEATURE_DECOMPOSE` 之后、`RELATIONSHIP` 之前。

四个审查维度：

| 角色 | 关注点 |
|------|--------|
| `user_journey_analyst` | 用户行为路径是否自然，是否漏掉关键交互环节 |
| `feature_completeness_reviewer` | 主流程、分支流程、异常兜底、CRUD 之外的功能缺口 |
| `industry_benchmark_analyst` | 同类产品默认功能、行业标准能力、竞品常见模式 |
| `scenario_combiner` | 多场景组合使用时是否能覆盖，是否需要组合功能 |

每个 reviewer 输出统一结构：

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

`BrainstormRecord` 增加：

```python
deliberation_rounds: list[DeliberationRound] = field(default_factory=list)
```

PM 的职责：

- 并行触发四个审查角色。
- 汇总所有 `DeliberationFinding`。
- 对每条建议做 `accept/reject/defer` 裁决。
- 被 `accept` 的建议写回功能树，或生成新的追问任务。
- 被 `reject/defer` 的建议必须保留理由。

阶段守卫：

- `DELIBERATION_REVIEW → RELATIONSHIP`：所有 high severity finding 必须被 `accept/reject/defer` 明确处理。
- 如果有 accepted finding 需要用户确认，则回到用户确认循环，不直接进入 `RELATIONSHIP`。

## 四、技术路线确认与工具发现

### 4.1 新增 `TECHNICAL_ROUTE_DRAFT`

位置：Brainstorm V3 需求审查通过、PRD / Spec 生成并冻结后，生成 WorkUnit 前。

PM 根据冻结后的 PRD / Spec 生成技术路线草案，并提交用户确认。这个阶段不属于 Brainstorm 的核心问答流程，而是开发前准备流程。

边界说明：

- Brainstorm 负责澄清“要做什么、为什么做、做到什么程度”。
- 技术路线负责澄清“准备怎么做、采用什么架构、有哪些技术风险”。
- 工具发现负责澄清“是否已有成熟第三方方案可以采用或参考”。
- WorkUnit 生成只能在需求和技术路线都确认后进行。

建议数据结构：

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

阶段守卫：

- 用户确认技术路线后才能进入 `TOOL_DISCOVERY`。
- 如果用户要求修改，更新路线草案并保留旧版本。
- 如果用户跳过技术路线确认，只能生成人工待确认的执行计划，不能直接交给执行 agent。

### 4.2 新增 `TOOL_DISCOVERY`

工具发现只在技术路线确认后触发，避免需求和技术方向未稳定时污染判断。

`ToolDiscoveryService` 职责：

- 根据 `TechnicalRoute.tool_needs` 生成搜索 query。
- 通过 WebSearch / GitHub API 搜索第三方库、SDK、引擎、类似项目。
- 对候选工具进行结构化评估。
- 生成推荐结果，交给后续 WorkUnit 或执行 agent。

工具发现默认是“开发前检查”，不是“自动安装依赖”。推荐结果需要进入技术路线或执行计划确认，执行 agent 不能因为搜索结果存在就自动采用。

建议数据结构：

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
    evidence_snapshot: str = ""  # 摘要或短摘录，避免以后网页变化后无法复盘


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

评估维度：

- 功能匹配度
- 社区活跃度与维护健康度
- 许可证兼容性，尤其注意 GPL / AGPL
- 与当前技术栈兼容性
- 安全风险，包括敏感权限、已知漏洞、来源可信度
- 集成成本，包括依赖体积、运行时要求、平台限制
- 证据链，包括 URL、stars、更新时间、license、官方文档或 README

工具发现结果不应自动安装依赖。它只生成推荐和集成建议，是否采用由技术路线/执行计划确认。

### 4.3 证据链要求

工具发现的证据不能只写在 LLM 上下文里，必须持久化。建议为外部证据新增通用结构，和用户对话来源区分开：

```python
@dataclass
class EvidenceRef:
    source_type: str  # user_quote | github | official_docs | package_registry | web | llm_inference
    title: str
    url: str = ""
    quote_or_summary: str = ""
    captured_at: str = ""
    confidence: float = 1.0
```

`SourceRef` 继续用于用户原话追溯，`EvidenceRef` 用于外部资料、工具搜索结果、审查依据和 LLM 推断依据。

## 五、职责边界

不要把所有能力都塞进 `PMAgent`。

建议模块划分：

| 模块 | 职责 |
|------|------|
| `ralph/brainstorm_manager.py` | Brainstorm 状态机、用户回复路由、阶段守卫 |
| `ralph/brainstorm_analyzer.py` | 关系分析、独立审查、可复用的需求分析能力 |
| `ralph/deliberation_service.py` | 四维结构化审查、reviewer 调用、PM 裁决辅助 |
| `ralph/technical_route_service.py` | 基于冻结 PRD / Spec 生成技术路线、版本保存、用户确认状态 |
| `ralph/tool_discovery.py` | 搜索、候选工具评估、推荐结果生成 |
| `ralph/search_provider.py` | Web / GitHub / package registry 搜索抽象、缓存、超时和失败降级 |
| `ralph/pm_agent.py` | WorkUnit 调度与 PM 编排入口，不承载所有业务细节 |
| `.ralph/config/agent-definitions.json` | 新增审查角色定义 |
| `.ralph/config/toolchain.json` | 继续配置执行工具和任务分配 |
| `.ralph/config/search-providers.json` | 配置 WebSearch / GitHub / package registry 等搜索能力 |

## 六、API 与 UI 需要补齐

### 6.1 后端 API

建议新增或扩展接口：

| 接口 | 作用 |
|------|------|
| `POST /api/ralph/brainstorm/{id}/proactive-analysis` | 生成主动分析草案 |
| `POST /api/ralph/brainstorm/{id}/proactive-analysis/confirm` | 用户确认、修改或拒绝分析条目 |
| `POST /api/ralph/brainstorm/{id}/deliberation` | 触发四维结构化审查 |
| `POST /api/ralph/brainstorm/{id}/deliberation/decide` | PM 或用户处理审查建议 |
| `POST /api/ralph/specs/{id}/technical-route` | 基于冻结 Spec 生成技术路线草案 |
| `POST /api/ralph/technical-routes/{id}/confirm` | 用户确认或要求修改技术路线 |
| `POST /api/ralph/technical-routes/{id}/tool-discovery` | 根据技术路线触发工具发现 |
| `GET /api/ralph/technical-routes/{id}/tool-discovery` | 查看工具候选与评估结果 |

耗时接口建议返回异步任务：

- `POST /deliberation` 返回 `job_id`，前端轮询或订阅任务状态。
- `POST /tool-discovery` 返回 `job_id`，搜索完成后再读取结果。
- 任务必须支持失败状态和部分成功状态，外部搜索失败不能阻断需求共创完成。

### 6.2 前端 UI

Brainstorm 页面需要新增几个面板，但不要把所有内容都塞进聊天侧栏：

- **主动分析草案**：逐条展示假设，支持接受、修改、拒绝。
- **功能审查结果**：按四个维度展示 finding，显示 PM 裁决和理由。
- **确认操作区**：用户可以确认进入下一阶段，也可以要求修改。

UI 不应只显示一段 Markdown。关键条目必须可单独确认、修改、拒绝。

技术路线和工具发现建议放在 Spec / Plan / Execution 准备页面，而不是 Brainstorm 主页面。Brainstorm 页面重点保持为：

- 左侧：功能树和当前节点。
- 中间：对话和追问。
- 右侧或 Tab：主动假设、审查 finding、需求完整度。

开发前准备页面重点展示：

- 技术路线草案。
- 工具发现结果。
- 采用 / 不采用 / 待比较的选择。
- 对执行计划和 WorkUnit 的影响。

## 七、配置与 Agent 定义

新增 4 个审查角色到 `.ralph/config/agent-definitions.json`：

- `user_journey_analyst` — 用户行为路径分析
- `feature_completeness_reviewer` — 功能完整性审查
- `industry_benchmark_analyst` — 竞品/行业经验对标
- `scenario_combiner` — 场景组合分析

每个角色可以先使用 `agent_class: "base"`，配独立 prompt。后续如果需要更强控制，再引入专用 agent class。

工具配置扩展：

- 新增 `.ralph/config/search-providers.json`，配置 `web_search`、`github_search`、`package_registry` 等能力开关、token、rate limit 和超时。
- PM 或 `ToolDiscoveryService` 只能在 `TOOL_DISCOVERY` 阶段使用搜索能力。
- 搜索结果必须写入持久化记录，不能只留在 LLM 上下文里。
- `.ralph/config/toolchain.json` 继续表示执行工具链，不建议混入搜索 provider，避免“执行工具”和“资料搜索”两个概念混在一起。

## 八、实施顺序

建议分两期实现，避免一次性改穿整个系统。

### 8.1 V3-A：需求共创增强

目标：验证“主动假设 + 结构化审查”是否真正提高需求质量。

1. **Schema + 状态机**：新增 `PROACTIVE_ANALYSIS`、`DELIBERATION_REVIEW`、`REQUIREMENTS_READY`，新增 `ProactiveAnalysis`、`DeliberationRound`。
2. **主动分析闭环**：实现生成、确认、修改、拒绝；只有用户确认或修改后的内容才能进入正式需求。
3. **结构化多维审查**：实现四个 reviewer 的统一输出和 PM 裁决。
4. **审查回写机制**：accepted finding 只能写入功能树或生成追问任务，不能直接变成 confirmed 需求。
5. **需求完成出口**：审查通过后进入 `REQUIREMENTS_READY`，允许生成 PRD / Spec。

### 8.2 V3-B：开发前准备

目标：在进入执行前确认技术路线并减少重复造轮子。

1. **技术路线确认**：基于冻结 PRD / Spec 生成路线草案，支持用户确认和修订记录。
2. **搜索 provider 抽象**：新增 Web / GitHub / package registry 搜索能力、缓存、超时和失败降级。
3. **工具发现服务**：根据 `tool_needs` 搜索候选、评估风险、生成推荐。
4. **执行计划接入**：把已采用 / 待比较 / 避免的工具结论传给执行计划和 WorkUnit。
5. **人工降级路径**：搜索失败时仍可继续人工确认技术路线，不能卡死流程。

每一步都需要补测试：

- phase 守卫测试
- schema 序列化/反序列化测试
- 用户确认后才写入正式需求的测试
- finding 裁决后才能推进阶段的测试
- 工具候选评估结果持久化测试
- 外部搜索失败时仍能继续人工确认技术路线的测试

## 九、改动总结

| 改动项 | 文件/模块 | 说明 |
|--------|-----------|------|
| 新增 `PROACTIVE_ANALYSIS` 阶段 | `ralph/schema/brainstorm_record.py`, `ralph/brainstorm_manager.py` | 系统主动分析模糊需求，生成可确认假设草案 |
| 新增主动分析数据结构 | `ralph/schema/brainstorm_record.py` | `ProactiveAnalysis`、`ProactiveAnalysisItem` |
| 新增 `DELIBERATION_REVIEW` 阶段 | `ralph/schema/brainstorm_record.py`, `ralph/brainstorm_manager.py` | 四维结构化功能审查 |
| 新增审查结果数据结构 | `ralph/schema/brainstorm_record.py` | `DeliberationRound`、`DeliberationFinding` |
| 新增 4 个审查 Agent 角色 | `.ralph/config/agent-definitions.json`, `prompts/` | 用户路径、功能完整性、行业对标、场景组合 |
| 新增审查编排服务 | `ralph/deliberation_service.py` | 调用 reviewer、汇总 finding、辅助 PM 裁决 |
| 新增技术路线草案 | `ralph/technical_route_service.py` | 基于冻结 PRD / Spec 生成技术路线并等待用户确认 |
| 新增工具发现服务 | `ralph/tool_discovery.py` | 搜索、评估、推荐第三方工具 |
| WebSearch / GitHub 搜索接入 | `ralph/search_provider.py`, `.ralph/config/search-providers.json` | 配置搜索能力、缓存、超时和失败降级 |
| Brainstorm API 扩展 | `dashboard/api/routes.py` | 新增主动分析、结构化审查接口 |
| 技术路线 / 工具发现 API | `dashboard/api/routes.py` | 新增 Spec 后续的技术路线和工具发现接口 |
| Brainstorm UI 扩展 | `dashboard-ui/app/ralph/brainstorm/page.tsx`, `dashboard-ui/components/ralph/brainstorm/` | 增加主动假设和审查 finding 面板 |
| 开发前准备 UI | `dashboard-ui/app/ralph/specs/` 或 `dashboard-ui/app/ralph/plan/` | 展示技术路线、工具发现结果和采用决策 |

## 十、风险与约束

- 主动分析可能引导用户，但也可能误导用户，所以必须以“假设”形式呈现。
- 多 agent 审查可能增加成本，第一版可以只在用户点击“运行多维审查”时触发。
- 流程过长会压垮用户，因此 V3-A 和 V3-B 必须拆开；需求共创完成后不强制立刻做技术路线和工具发现。
- 工具发现依赖外部网络和 API，必须支持失败降级：无搜索结果时继续走人工/默认技术路线。
- 工具推荐不能等同于自动安装，执行前仍需进入计划确认。
- 所有 LLM 生成内容都需要持久化证据链，否则无法调试、回放和评审。
