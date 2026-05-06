# Ralph Orchestrator 三期 + 四期 技术方案

版本：v1.0 草案
日期：2026-05-06
文档语言：中文
依赖文档：
- docs/auto-coding-ralph-orchestrator-prd.zh.md
- docs/auto-coding-ralph-orchestrator-implementation-plan.zh.md
- docs/auto-coding-ralph-orchestrator-phase2-design.zh.md

---

## 1. 背景与定位

### 1.1 现状

一期（可靠顺序执行）和二期（可持续自动化推进）的核心模块已全部落地：
- 状态机、harness、review、证据收集等基础能力完整
- 记忆系统（短期/中期/长期）、Context 四层模型、多轮 Continuation 完整实现
- 双层知识图谱（graphify + KnowledgeGraphService）完整实现
- PM Agent 空记忆调度模式已实现
- 并发控制（Semaphore + TokenBudget）和 git worktree 隔离已实现
- Dashboard 有 70+ API 端点和多页面 UI

### 1.2 三期定位：生产级并行执行

从"能并行"升级到"并行可靠、冲突可解、集成可验"。

重点解决：
- 多 agent 并发修改同一文件时的冲突检测与自动合并
- 集成队列管理和回归测试
- 并行执行的可观测性和故障恢复

### 1.3 四期定位：产品化运营平台

从"CLI + 基础 UI"升级到"完整的可视化运营平台"。

重点解决：
- 完整 Dashboard（看板、成本、权限、Issue 治理界面）
- 多工具适配器生态
- LLM Provider 管理和自动降级
- 长期运行的可维护性（复盘、归档、成本控制）

---

## 2. 三期：生产级并行执行

### 2.1 当前现状分析

| 组件 | 现状 | 三期差距 |
|------|------|----------|
| `ParallelOrchestrator` | 已实现，支持 topological sort 调度和 worktree 隔离 | 缺少集成队列、冲突自动合并、并行可观测性 |
| `WorktreeManager` | 已实现 git worktree 创建和 merge back | 缺少冲突自动检测、冲突回滚、多分支合并策略 |
| `ConcurrencyController` | Semaphore + TokenBudget 已实现 | 缺少动态并发调整、队列优先级、死锁检测 |
| `state_machine.py` | 单任务状态机完整 | 缺少集成态（integrating / integration_failed） |
| Dashboard | 有基础 API 和 UI | 缺少并行执行可视化、冲突告警、集成队列看板 |

### 2.2 集成队列（Integration Queue）

#### 2.2.1 设计目标

并行执行不是"各自做完就完了"，而是要有一个集成阶段来验证所有变更合并后仍然可用。

#### 2.2.2 状态机扩展

在现有状态机中新增集成相关状态：

```
accepted（任务级）→ pending_integration（等待集成）
  → integrating（集成中）
    → integrated（集成成功）→ needs_review（集成后回归 review）
    → integration_failed（集成冲突）→ conflict_resolution（冲突解决中）
      → merged（手动合并完成）→ integrated
```

#### 2.2.3 IntegrationQueue 设计

```python
@dataclass
class IntegrationJob:
    work_ids: list[str]           # 需要集成的 work unit 列表
    target_branch: str             # 目标分支（默认 main/master）
    strategy: str                  # "sequential" | "batch" | "incremental"
    status: IntegrationStatus
    created_at: str
    conflict_details: list[ConflictRecord] | None = None

@dataclass
class ConflictRecord:
    file_path: str
    work_id_a: str
    work_id_b: str
    conflict_type: str             # "content" | "semantic" | "import"
    resolution_hint: str | None    # AI 建议的解决方式
    resolved_by: str               # "auto" | "manual" | "user"
```

```python
class IntegrationQueue:
    def __init__(self, ralph_dir: Path):
        self.queue: list[IntegrationJob] = []
        self.completed: list[IntegrationJob] = []

    def enqueue(self, work_ids: list[str], strategy: str = "incremental") -> str:
        """把已 accepted 的 work units 加入集成队列"""

    async def process_next(self) -> IntegrationResult:
        """处理队列中的下一个集成任务"""

    async def resolve_conflict(self, conflict_id: str, resolution: str) -> bool:
        """解决一个集成冲突（自动或标记为手动）"""

    def get_queue_status(self) -> dict:
        """返回队列当前状态"""
```

#### 2.2.4 集成策略

| 策略 | 适用场景 | 实现方式 |
|------|----------|----------|
| **sequential** | 修改文件不重叠的任务 | 依次 apply patch，每次只合并一个 worktree |
| **batch** | 修改完全不相关的模块 | 一次性 merge 所有 worktree 分支 |
| **incremental** | 默认策略 | 按拓扑排序顺序逐个集成，每步做回归测试 |

### 2.3 冲突自动检测与合并

#### 2.3.1 预冲突检测（Pre-Merge Check）

在真正 merge 之前，先检测是否会冲突：

```python
class ConflictDetector:
    def detect_potential_conflicts(self, work_units: list[WorkUnit]) -> list[ConflictRecord]:
        """基于修改文件集合和 git diff 预检测冲突"""
        # 1. 文件级冲突：多个 work unit 修改了同一个文件
        # 2. 导入级冲突：一个删除了导入，另一个还在用
        # 3. 语义级冲突：修改了同一个接口的不同部分（调用 graphify 查询）
```

检测流程：
```
WorkUnit A 修改了 [auth.py, utils.py]
WorkUnit B 修改了 [auth.py, config.py]
                          ↓
              文件级冲突：auth.py
                          ↓
         调用 graphify 检查冲突行是否重叠
                          ↓
              重叠 → ConflictRecord（需人工）
              不重叠 → 可自动合并
```

#### 2.3.2 自动合并策略

```python
class MergeExecutor:
    async def auto_merge(self, integration_job: IntegrationJob) -> MergeResult:
        """执行自动合并"""
        # 1. 对无冲突的文件：直接 git merge
        # 2. 对非重叠修改的文件（同一文件不同行）：git merge -s recursive -X ours/theirs
        # 3. 对真正冲突的文件：
        #    a. 调用 LLM 分析冲突上下文
        #    b. 生成合并建议
        #    c. 如果置信度 > 0.8，自动应用
        #    d. 否则标记为 manual，进入 conflict_resolution 状态
```

#### 2.3.3 集成回归测试

集成完成后，必须运行回归测试：

```python
class IntegrationVerifier:
    async def verify(self, integration_job: IntegrationJob) -> VerificationResult:
        """集成后回归验证"""
        # 1. 运行全量测试套件（不是单任务的测试，而是全部）
        # 2. 运行 build/typecheck
        # 3. 运行 Playwright 用户路径测试
        # 4. 检查控制台错误和网络请求
        # 5. 验证接口合同是否仍然一致
```

### 2.4 并行执行可观测性

#### 2.4.1 并行执行快照

```python
@dataclass
class ParallelSnapshot:
    timestamp: str
    active_worktrees: list[WorktreeInfo]
    running_work_units: list[WorkUnitProgress]
    integration_queue_length: int
    conflicts_detected: int
    token_usage_rate: float          # 当前速率 / 上限
    semaphore_usage: int             # 当前并发数 / max_concurrent

@dataclass
class WorkUnitProgress:
    work_id: str
    turn_number: int
    current_phase: str               # "executing" | "reviewing" | "integrating"
    elapsed_seconds: float
    token_usage: dict
    file_changes_count: int
    health_status: str               # "healthy" | "warning" | "failing"
```

#### 2.4.2 死锁检测

```python
class DeadlockDetector:
    def detect(self, active_work_units: list[WorkUnit]) -> list[DeadlockCycle]:
        """检测并行任务之间的死锁"""
        # 1. 构建等待图：A 等待文件 X，B 持有文件 X 的锁
        # 2. 寻找环
        # 3. 返回死锁循环和打破建议
```

### 2.5 三期数据流

```
[TaskDecomposer] 生成并行任务集合
  │
  ▼
[ConcurrencyController] 检查 token budget 和 semaphore
  │
  ▼
[ParallelOrchestrator] 创建 worktree + 分配任务
  │
  ├── [WorkUnit A] → worktree-A → Turn-based execution → accepted
  ├── [WorkUnit B] → worktree-B → Turn-based execution → accepted
  └── [WorkUnit C] → worktree-C → Turn-based execution → accepted
  │
  ▼
[IntegrationQueue] 收集所有 accepted 的任务
  │
  ▼
[ConflictDetector] 预检测冲突
  │
  ├── 无冲突 → [MergeExecutor] 自动合并
  ├── 非重叠 → [MergeExecutor] 策略合并
  └── 有冲突 → [ConflictResolver] LLM 辅助 / 人工介入
  │
  ▼
[IntegrationVerifier] 全量回归测试
  │
  ├── 通过 → integrated → 进入下一批
  └── 失败 → integration_failed → 回滚冲突任务
```

### 2.6 三期新增模块清单

| 模块 | 文件 | 优先级 |
|------|------|--------|
| 集成队列管理 | `ralph/integration_queue.py` | P0 |
| 冲突检测器 | `ralph/conflict_detector.py` | P0 |
| 合并执行器 | `ralph/merge_executor.py` | P0 |
| 集成验证器 | `ralph/integration_verifier.py` | P0 |
| 死锁检测器 | `ralph/deadlock_detector.py` | P1 |
| 并行快照服务 | `ralph/parallel_snapshot.py` | P1 |
| 状态机扩展（集成态） | `ralph/state_machine.py`（修改） | P0 |
| Dashboard API 扩展 | `dashboard/api/routes.py`（修改） | P1 |
| Dashboard UI 扩展 | `dashboard-ui/app/ralph/integration/` | P1 |

---

## 3. 四期：产品化运营平台

### 3.1 完整 Dashboard

#### 3.1.1 现状与差距

| 模块 | 现状 | 四期目标 |
|------|------|----------|
| Work Units 列表 | ✅ 已有 | 增强：集成态展示、并行进度 |
| 命令管理 | ✅ 已有 | 无大变化 |
| 审批管理 | ✅ 已有 | 增强：Issue 治理审批流 |
| 调度面板 | ✅ 已有 | 增强：PM Agent 调度日志 |
| 记忆管理 | ✅ 已有 | 增强：图谱可视化 |
| 知识图谱 | ✅ 已有 | 增强：交互式查询 |
| 合同管理 | ✅ 已有 | 无大变化 |
| Provider 配置 | ✅ 已有 | 增强：连通性测试、降级配置 |
| **Issue 治理** | ❌ 无独立页面 | 新增：issue 列表、分类结果、策略配置、审批流 |
| **成本分析** | ❌ 无页面 | 新增：成本趋势、按任务/agent/Provider 拆分、预算告警 |
| **权限管理** | ❌ 无页面 | 新增：用户管理、角色分配、操作审计 |
| **项目复盘** | ❌ 无页面 | 新增：历史项目对比、成功率统计、瓶颈分析 |
| **实时日志** | ✅ WebSocket 已有 | 增强：日志搜索、过滤、导出 |

#### 3.1.2 Issue 治理界面

```
/app/ralph/issues/
├── page.tsx                    # Issue 列表（支持过滤、搜索、分组）
├── [id]/page.tsx               # Issue 详情（分类结果、处理历史、关联 WorkUnit）
├── policies/page.tsx           # Issue 策略配置（CRUD）
└── sync/page.tsx               # 同步状态（GitHub ↔ Ralph 双向同步状态）
```

核心功能：
1. Issue 列表按分类/严重级别/处理状态分组
2. 每条 issue 显示分类置信度和匹配的策略
3. 用户可覆盖自动决策（auto_fix → require_approval）
4. 同步状态看板：哪些 issue 已回写 label/comment，哪些待同步
5. 策略配置可视化编辑器

#### 3.1.3 成本分析界面

```
/app/ralph/costs/
├── page.tsx                    # 成本总览（今日/本周/本月趋势）
├── breakdown/page.tsx          # 按维度拆分（Provider/agent/task_type）
├── budget/page.tsx             # 预算配置和告警
└── history/page.tsx            # 历史项目成本对比
```

数据源：
```python
class CostRecorder:
    def record_execution(self, work_id: str, token_usage: dict, model: str) -> None:
        """记录单次执行的 token 消耗和成本"""

    def get_cost_summary(self, period: str) -> CostSummary:
        """按时间段汇总成本"""

    def get_breakdown(self, dimension: str) -> list[CostBreakdown]:
        """按维度拆分（provider / agent / task_type / project）"""

    def check_budget(self) -> BudgetStatus:
        """检查当前是否超预算"""
```

成本计算：
```python
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},   # $/1M tokens
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    # ... 动态从 config_manager 读取
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens / 1_000_000) * pricing["input"] + \
           (output_tokens / 1_000_000) * pricing["output"]
```

#### 3.1.4 权限管理界面

```
/app/ralph/permissions/
├── page.tsx                    # 权限策略总览
├── users/page.tsx              # 用户管理（如果有认证系统）
├── guard-config/page.tsx       # Permission Guard 规则配置
└── audit-log/page.tsx          # 操作审计日志
```

> 注：四期不一定需要完整的多用户认证系统，但至少要有：
> - 操作审计日志（谁在什么时间触发了什么操作）
> - Permission Guard 规则可视化配置（哪些操作自动允许、哪些需要审批）

### 3.2 多工具适配器生态

#### 3.2.1 新增适配器

在现有 `ClaudeCodeAdapter` 基础上，新增：

| 适配器 | 文件 | 能力 |
|--------|------|------|
| CodexAdapter | `ralph/adapters/codex_adapter.py` | OpenAI Codex CLI，支持 session resume |
| AiderAdapter | `ralph/adapters/aider_adapter.py` | Aider CLI，支持多模型、git 集成 |
| ClineAdapter | `ralph/adapters/cline_adapter.py` | VS Code Cline 扩展（通过 API 调用） |
| OpenClawAdapter | `ralph/adapters/openclaw_adapter.py` | OpenClaw CLI |

#### 3.2.2 统一适配器基类

已有的 `ToolAdapter` 抽象基类已经定义了统一接口，新增适配器只需实现：

```python
class NewAdapter(ToolAdapter):
    NAME = "new_tool"
    CAPABILITIES = {
        "mcp_support": True,
        "session_resume": False,
        "stream_output": True,
        "tool_use": True,
        "sandbox_mode": False,
        "timeout_configurable": True,
        "credential_injection": True,
    }

    async def execute(self, options: ExecOptions) -> Result:
        # 1. 把 Ralph 的 ExecOptions 翻译为工具原生命令
        # 2. 启动子进程
        # 3. 捕获 stdout/stderr
        # 4. 解析文件变更（git diff 或工具特有方式）
        # 5. 构造统一 Result 返回
```

#### 3.2.3 适配器能力可视化

Dashboard 新增页面：

```
/app/ralph/settings/toolchain/
├── page.tsx                    # 已注册适配器列表 + 能力矩阵
├── [adapter]/page.tsx          # 适配器详情（健康状态、执行历史）
└── dispatch/page.tsx           # 调度策略配置（什么任务用什么工具）
```

### 3.3 LLM Provider 管理和自动降级

#### 3.3.1 自动降级策略

```python
class ProviderDegradationManager:
    def __init__(self, config: ToolchainConfig):
        self.providers = config.providers       # 按优先级排序
        self.health_cache: dict[str, HealthStatus] = {}
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    async def get_active_provider(self, task_type: str) -> LLMProvider:
        """根据任务类型选择 Provider，主 Provider 不可用时自动降级"""
        model_assignment = self._get_model_assignment(task_type)
        primary = model_assignment.primary_provider

        if await self._is_healthy(primary):
            return primary

        # 主 Provider 不可用，按优先级尝试备用
        for fallback in model_assignment.fallback_providers:
            if await self._is_healthy(fallback):
                self._record_degradation(primary, fallback)
                return fallback

        raise ProviderUnavailableError(f"所有 Provider 都不可用: {primary.name}")

    async def _is_healthy(self, provider: LLMProvider) -> bool:
        """健康检查：HTTP 连通性 + 最近错误率"""
        # 1. 检查 circuit breaker 状态
        cb = self.circuit_breakers[provider.name]
        if cb.is_open():
            return False

        # 2. 快速连通性测试（缓存结果 60s）
        if provider.name in self.health_cache:
            cached = self.health_cache[provider.name]
            if (time.time() - cached.checked_at) < 60:
                return cached.healthy

        # 3. 实际测试
        healthy = await provider.test_connectivity()
        self.health_cache[provider.name] = HealthStatus(healthy, time.time())

        if not healthy:
            cb.record_failure()

        return healthy
```

#### 3.3.2 负载均衡

```python
class LoadBalancer:
    def __init__(self, providers: list[LLMProvider], strategy: str = "least_loaded"):
        self.providers = providers
        self.strategy = strategy
        self.request_counts: dict[str, int] = defaultdict(int)

    def select(self, task_type: str) -> LLMProvider:
        """根据负载均衡策略选择 Provider"""
        if self.strategy == "least_loaded":
            return min(
                [p for p in self.providers if p.supports(task_type)],
                key=lambda p: self.request_counts[p.name]
            )
        elif self.strategy == "round_robin":
            # 轮询
            ...
```

#### 3.3.3 Dashboard Provider 管理

在现有 `/api/ralph/settings/providers` 基础上增强：

| 新端点 | 方法 | 说明 |
|--------|------|------|
| `/api/ralph/settings/providers/{id}/test` | POST | 连通性测试 |
| `/api/ralph/settings/providers/{id}/degradation` | PUT | 配置降级优先级 |
| `/api/ralph/settings/providers/health` | GET | 所有 Provider 健康状态 |
| `/api/ralph/settings/providers/load` | GET | 负载分布情况 |
| `/api/ralph/settings/providers/degradation-events` | GET | 降级事件历史 |

### 3.4 Issue 治理完整实现

#### 3.4.1 双向同步接线

在二期 `IssueSyncProtocol` 基础上，把未接线的回调接上：

```python
# 修改 command_handler.py 或 pm_coordinator.py
class StateChangeHook:
    def __init__(self, issue_sync: IssueSyncProtocol):
        self.issue_sync = issue_sync

    async def on_work_unit_status_change(self, work_unit: WorkUnit) -> None:
        """WorkUnit 状态变化时自动同步回 issue tracker"""
        if work_unit.issue_id:
            await self.issue_sync.on_ralph_status_change(work_unit)
```

集成到状态机：
```python
# 在 state_machine.py 的 transition() 方法中
class ExtendedStateMachine(StateMachine):
    def __init__(self, ..., status_change_hooks: list[StateChangeHook] | None = None):
        super().__init__(...)
        self.status_change_hooks = status_change_hooks or []

    def transition(self, work_id: str, to_state: str, ...) -> None:
        super().transition(work_id, to_state, ...)
        # 触发所有状态变化 hook
        work_unit = self.repository.get_work_unit(work_id)
        for hook in self.status_change_hooks:
            asyncio.create_task(hook.on_work_unit_status_change(work_unit))
```

#### 3.4.2 Webhook 真实接入

```python
# dashboard/api/ralph_extended_routes.py 中的 webhook 端点增强
@router.post("/api/ralph/issues/webhook")
async def handle_github_webhook(request: Request):
    """接收 GitHub webhook 事件"""
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    if event_type == "issue_comment":
        # 解析 /ralph 命令
        command = parse_issue_command(payload["comment"]["body"])
        if command:
            return await execute_command(command)

    elif event_type == "issues":
        # issue 创建/关闭/重新打开
        action = payload["action"]
        if action == "opened":
            # 自动拉取新 issue 并分类
            await auto_fetch_and_classify(payload["issue"]["id"])
        elif action == "closed":
            # 标记 Ralph 中关联的 work unit
            await mark_related_work_units_closed(payload["issue"]["id"])

    return {"status": "ok"}
```

GitHub 侧配置（用户需要在仓库 Settings → Webhooks 中添加）：
```
Payload URL: https://<ralph-host>/api/ralph/issues/webhook
Content type: application/json
Events: Issues, Issue comments
Secret: <webhook_secret>
```

### 3.5 历史项目复盘

#### 3.5.1 复盘数据结构

```python
@dataclass
class ProjectRetrospective:
    project_id: str
    period: dict                    # {"start": "...", "end": "..."}
    summary: dict                   # {"total_tasks": N, "accepted": N, ...}
    success_rate: float             # accepted / (accepted + failed + needs_rework)
    avg_turns_per_task: float
    avg_time_per_task_seconds: float
    total_cost: float
    total_tokens: dict
    blocker_analysis: list[dict]    # 最常出现的阻塞项
    rework_analysis: list[dict]     # 最常需要返工的任务类型
    bottleneck_tasks: list[dict]    # 耗时最长的任务
    quality_metrics: dict           # review 通过率、测试覆盖率、Playwright 通过率
    comparisons: list[dict] | None  # 与历史项目的对比
```

#### 3.5.2 复盘 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ralph/reports/retrospective/{project_id}` | GET | 获取项目复盘报告 |
| `/api/ralph/reports/compare` | POST | 对比两个项目 |
| `/api/ralph/reports/trends` | GET | 趋势分析（多项目） |

#### 3.5.3 复盘 UI

```
/app/ralph/reports/
├── page.tsx                    # 复盘报告列表
├── [id]/page.tsx               # 单个项目复盘详情
└── compare/page.tsx            # 项目对比
```

### 3.6 长期运行可维护性

#### 3.6.1 会话归档策略

二期 ADR 提到完整会话日志不可压缩但会膨胀。四期需要实现：

```python
class SessionArchiver:
    def __init__(self, ralph_dir: Path, retention_days: int = 30):
        self.ralph_dir = ralph_dir
        self.retention_days = retention_days

    async def archive_old_sessions(self) -> ArchiveResult:
        """归档超过 retention_days 的会话日志"""
        # 1. 扫描 .ralph/sessions/ 目录
        # 2. 对超过 retention_days 的会话：
        #    a. 压缩为 .tar.gz（内容保持完整，不做摘要压缩）
        #    b. 移动到 .ralph/sessions/archive/YYYY-MM/
        #    c. 更新索引文件
        # 3. 对超过 180 天的归档：提示用户下载后可删除
```

#### 3.6.2 定期健康检查

```python
class HealthChecker:
    async def run_periodic_check(self) -> HealthReport:
        """定期运行健康检查"""
        return HealthReport(
            disk_usage=self._check_disk_usage(),         # .ralph/ 目录大小
            session_count=self._count_sessions(),         # 未归档会话数
            stuck_tasks=self._find_stuck_tasks(),         # running 超过 2 小时的 task
            failed_integrations=self._count_failed_integrations(),
            provider_health=await self._check_providers(),
            budget_status=self._check_budget(),
            memory_size=self._check_memory_size(),        # 短期/中期记忆文件大小
        )
```

#### 3.6.3 定期清理定时任务

```python
# 使用 asyncio 定时任务或 cron-like 调度
class PeriodicTasks:
    async def start(self):
        while True:
            await self._run_cleanup()           # 每 6 小时
            await self._run_archiver()           # 每 24 小时
            await self._run_graphify_update()    # 每 12 小时
            await self._run_memory_compact()     # 每 4 小时
            await asyncio.sleep(3600)            # 每小时循环一次
```

---

## 4. 实施路线图

### 4.1 三期时间线（预计 3-4 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| **W1** | 集成队列 + 状态机扩展 | `integration_queue.py`、状态机新增集成态 |
| **W2** | 冲突检测 + 自动合并 | `conflict_detector.py`、`merge_executor.py` |
| **W3** | 集成验证 + 死锁检测 | `integration_verifier.py`、`deadlock_detector.py` |
| **W4** | Dashboard 集成 + 测试 | 并行执行可视化、集成队列看板、端到端测试 |

### 4.2 四期时间线（预计 5-6 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| **W1-2** | Issue 治理完整实现 + 双向同步接线 | Issue 页面、webhook 接入、`StateChangeHook` |
| **W3** | 成本分析 + 预算告警 | `CostRecorder`、成本页面、预算配置 |
| **W4** | 多工具适配器 | CodexAdapter、AiderAdapter 等 2-3 个新适配器 |
| **W5** | Provider 自动降级 + 负载均衡 | `ProviderDegradationManager`、健康检查、连通性测试 |
| **W6** | 项目复盘 + 长期运行维护 | 复盘 API/UI、会话归档、定期健康检查 |

---

## 5. 数据模型变更

### 5.1 WorkUnit 扩展（三期）

```python
# 新增字段（向后兼容，都是可选）
@dataclass
class WorkUnit:
    # ... 现有字段不变 ...
    integration_status: str | None = None          # pending_integration / integrating / integrated / integration_failed
    integration_job_id: str | None = None           # 关联的 IntegrationJob ID
    merge_conflicts: list[ConflictRecord] | None = None
    workspace_branch: str | None = None             # git worktree 分支名
```

### 5.2 新增数据表

| 文件 | 内容 |
|------|------|
| `.ralph/integration_queue.jsonl` | 集成任务队列 |
| `.ralph/conflicts.jsonl` | 冲突记录 |
| `.ralph/costs.jsonl` | 成本记录 |
| `.ralph/degradation_events.jsonl` | Provider 降级事件 |
| `.ralph/health_reports.jsonl` | 定期健康检查报告 |
| `.ralph/retrospectives/` | 项目复盘报告 |

---

## 6. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 并行冲突检测误报 | 不必要的合并阻塞 | 默认保守策略，允许用户手动 override |
| LLM 辅助合并引入错误 | 合并后的代码有 bug | 合并后必须运行集成验证，不通过则回滚 |
| 成本记录开销 | 大量小任务的记录写入 I/O | 批量写入 + 异步落盘 |
| Provider 降级导致质量下降 | 降级到弱模型可能影响任务质量 | 降级时记录事件并通知用户，关键任务禁止降级到 Haiku |
| 会话归档误删数据 | 归档后无法排查问题 | 归档 = 物理移动 + 压缩，不是删除；删除需要用户确认 |
| webhook 安全 | 伪造 webhook 事件 | 验证 HMAC 签名、只接受配置仓库的 webhook |

---

## 7. 与现有架构的兼容性

### 7.1 三期向后兼容

| 一期/二期组件 | 三期变化 | 兼容性 |
|--------------|---------|--------|
| `state_machine.py` | 新增集成态 | 兼容，新状态不改变已有状态流转 |
| `parallel_executor.py` | 增加 IntegrationQueue 集成 | API 不变，增加后置步骤 |
| `WorkUnit` schema | 新增可选字段 | 兼容，旧数据无需迁移 |
| Dashboard API | 新增集成相关端点 | 新增，不影响旧端点 |

### 7.2 四期向后兼容

| 一期/二期/三期组件 | 四期变化 | 兼容性 |
|-------------------|---------|--------|
| `config_manager.py` | 新增成本/Provider 降级配置 | 兼容，新增可选字段 |
| Dashboard | 新增页面和 API | 新增，不影响已有页面 |
| `issue_sync_protocol.py` | 接线回调 | 兼容，回调是新增的调用点 |
| `tool_adapter.py` | 新增适配器实现 | 兼容，注册表模式 |

---

## 8. 成功标准

### 三期成功标准

1. 3 个 WorkUnit 并行执行后能自动集成，无需人工介入
2. 文件级冲突检测准确率 > 90%（不误报、不漏报）
3. 非重叠修改的自动合并成功率 > 95%
4. 集成回归测试能捕获因合并引入的 bug
5. 死锁检测能识别并报告并行任务之间的循环等待
6. Dashboard 能实时显示并行执行进度和集成队列状态

### 四期成功标准

1. Issue 从 GitHub 创建到 Ralph 自动分类到生成 WorkUnit，全程 < 30 秒
2. Ralph 状态变化（accepted/failed）在 60 秒内同步回 GitHub issue
3. 成本分析页面能按 Provider/任务类型/时间维度查看消费趋势
4. 主 Provider 不可用时，系统在 60 秒内自动降级到备用 Provider
5. 新适配器（Codex/Aider）能正确执行任务并返回统一格式的 Result
6. 项目复盘页面能直观展示成功率、瓶颈、成本趋势
7. 系统连续运行 7 天后，磁盘使用量在可控范围内（会话归档生效）
