# CodeForge / Ralph 架构契约

> 本文档定义系统的模块边界、状态归属、导入规则和禁止事项。
> 所有新增代码必须遵守本契约。违反规则将通过 `scripts/check_architecture.py` 自动检测。

---

## 一、模块依赖规则

**核心原则**：导入方向必须单向流动。`core/` 不依赖上层，`dashboard/` 可以依赖 `core/` 和 `ralph/`，`ralph/` 不依赖 `dashboard/`。

| 来源模块 | 可导入 | 禁止导入 |
|----------|--------|---------|
| `core/*` | 自身模块 + `core/state_models`（类型） | `dashboard/*`, `ralph/*` |
| `agents/*` | `core/state_models`（仅类型引用） | `dashboard/*`, `ralph/*` |
| `dashboard/*` | `core/*`, `ralph/*`, `agents/*` | — |
| `ralph/*` | `core/state_models`（仅 Command 类型） | `dashboard/*` |
| `dashboard-ui/*` | HTTP API + WebSocket 端点 | 任何后端 Python 模块 |

**TYPE_CHECKING 例外**：在 `if TYPE_CHECKING:` 块内的类型提示导入不受限制，因为仅在静态检查时生效。

---

## 二、状态归属矩阵

所有状态变更必须通过指定的 Repository 写入。禁止绕过 Repository 直接操作文件。

| 实体 | 写入者 | 读取者 | 存储位置 | 缓存位置 |
|------|--------|--------|---------|---------|
| Feature | `ProjectStateRepository` | `FeatureTracker`（只读视图） | `data/dashboard/state.json` | 前端 Query Cache |
| AgentInstance | `ProjectStateRepository` | `AgentPool`（内存实时） | `data/dashboard/state.json` | WebSocket 广播 |
| Command | `ProjectStateRepository` | `CommandConsumer` | `data/dashboard/state.json` | 无 |
| Event | `ProjectStateRepository.append_event()` | EventBus, WebSocket | `data/dashboard/state.json` | 无 |
| BlockingIssue | `ProjectStateRepository` | `BlockingTracker`（只读视图） | `data/dashboard/state.json` | 前端 Query Cache |
| ChatMessage | `ProjectStateRepository` | PM Chat | `data/dashboard/state.json` | 无 |
| ModuleAssignment | `ProjectStateRepository` | 配置管理 | `data/dashboard/state.json` | 无 |
| ApprovalRequest | `ProjectStateRepository` | 审批流程 | `data/dashboard/state.json` | 无 |
| WorkUnit | `RalphRepository` | RalphCommandHandler | `.ralph/work_units/` | 无 |
| Evidence | `RalphRepository` | EvidenceCollector | `.ralph/evidence/` | 无 |
| ReviewResult | `RalphRepository` | ReviewManager | `.ralph/reviews/` | 无 |
| RetroRecord | `RalphRepository` | RetroAgent | `.ralph/retros/` | 无 |
| Blocker | `RalphRepository` | RalphCommandHandler | `.ralph/blockers/` | 无 |
| TasteRecord | `RalphRepository` | MemoryManager | `.ralph/tastes/` | 无 |
| 知识图谱 | `KnowledgeGraphService` | RetrievalPipeline | `.ralph/knowledge-graph/` | 无 |
| 记忆数据 | `MemoryManager` | ContextEngine | `.ralph/memory/` | 无 |
| 配置数据 | `RalphConfigManager` | 各模块 | `.ralph/config/` | 内存缓存 |
| UI 状态（抽屉/开关/选中） | Zustand | 前端组件 | 浏览器内存 | 无 |

---

## 三、状态写入规则

1. **所有业务状态变更必须走 Repository**。禁止直接修改 JSON 文件、SQLite 或其他存储。
2. **状态变化必须伴随事件**。每次状态转换后调用 `append_event()` 生成审计事件。
3. **ExecutionLedger 停止双写**。当提供 repository 时，只写入 repository，不再写本地文件。
4. **FeatureTracker 是只读视图 + 业务逻辑**。它提供 `get_next_ready()` 等排序方法，但不持有最终状态。
5. **TaskQueue 已删除**。所有任务调度通过 `ProjectStateRepository` 管理。

---

## 四、前后端边界

1. **通信方式**：前端与后端仅通过 HTTP/JSON 和 WebSocket/JSON 通信。
2. **API 响应格式**：由后端定义，前端消费。前端不推断业务状态。
3. **后端不推 UI 状态**：后端不发送抽屉开关、选中项、滚动位置等纯 UI 状态。
4. **前端不复写状态机**：前端只展示和触发操作，不自行推导业务状态转换。
5. **WebSocket 仅做增量更新**：前端初始加载通过 HTTP snapshot 获取全量状态，后续通过 WebSocket 事件增量更新。

---

## 五、事件流规则

```
业务状态变更 → Repository 写入 → append_event() → EventBus 发布 → WebSocket 广播 → 前端缓存更新
```

1. **事件生成**：事件仅由 `ProjectStateRepository.append_event()` 生成。EventBus 是内存中的发布订阅，不是持久存储。
2. **事件不可变**：一旦写入，事件不得修改或删除。
3. **事件不替代状态**：当前状态是事实源，事件历史是审计轨迹。查询"现在是什么状态"走 Repository，查询"怎么变成这样的"走事件历史。

---

## 六、命令流规则

```
前端 POST /api/commands → CommandProcessor 校验 → Repository 持久化(pending)
→ CommandConsumer 轮询 → RalphCommandHandler 执行 → Repository 更新状态 → 事件广播
```

1. **命令创建**：前端通过 API 创建命令，状态为 `pending`。
2. **命令消费**：`CommandConsumer` 轮询待处理命令，交由对应 Handler 执行。
3. **命令结果**：Handler 执行完成后，更新命令状态（accepted/applied/rejected/failed），并生成事件。

---

## 七、禁止事项

1. **禁止一个业务事实同时存在两套长期真源**。（状态统一后，不再有 `features.json` + `state.json` + `tasks.db` 三源并存）
2. **禁止 `core/` 导入 `dashboard/` 或 `ralph/`**。（通过 `scripts/check_architecture.py` 自动检测）
3. **禁止 `ralph/` 导入 `dashboard/`**。（Command 类型除外，走 `core/state_models`）
4. **禁止在 `ProjectManager` 中直接堆叠新的 API/WebSocket 逻辑**。（PM 只负责编排，不处理传输层）
5. **禁止 Dashboard API 绕过 Repository 直接写文件**。（所有配置通过 `RalphConfigManager`，所有状态通过 `ProjectStateRepository`）
6. **禁止在 routes.py 中新增超过 200 行的 handler 函数**。（拆分到独立路由模块）
7. **禁止把 WebSocket 广播当长期状态存储**。
8. **禁止前端复写后端状态机**。
9. **禁止 Agent 直接修改 SQLite 或 JSON 文件**。（所有变更走 Repository）
10. **禁止新增无对应测试的业务逻辑**。（新 Feature 必须附带测试）

---

## 八、模块职责详表

### `core/` — 编排引擎

| 文件 | 职责 |
|------|------|
| `project_manager.py` | 执行循环编排：选任务 → 派发 AgentPool → 等待结果 → 推进状态 |
| `feature_tracker.py` | Feature 排序 + 优先级计算（只读视图） |
| `blocking_tracker.py` | 阻塞问题检测与追踪 |
| `execution_ledger.py` | 执行历史审计（委托 repository 写入） |
| `permission_guard.py` | 命令/操作权限校验 |
| `feature_execution_service.py` | Feature 执行逻辑 |
| `feature_verification_service.py` | Feature 验收逻辑 |
| `git_service.py` | Git 操作封装 |
| `config.py` | 全局常量与路径定义 |
| `state_models.py` | **权威数据模型定义**（所有模块共享） |

### `ralph/` — WorkUnit 全生命周期

| 文件 | 职责 |
|------|------|
| `command_handler.py` | WorkUnit 命令路由：accept/review/retry/cancel 等 |
| `repository.py` | Ralph 级状态存储（WorkUnit/Evidence/Review/Retro 等） |
| `config_manager.py` | LLM Provider / 工具链 / Agent 定义等配置管理 |
| `work_unit_engine.py` | WorkUnit 生成、分解、执行 |
| `memory_manager.py` | 三层记忆（短/中/长期）+ Compaction |
| `context_engine.py` | Context Pack 分层构建（L0/L1/L2/L3） |
| `knowledge_graph.py` | 项目知识图谱 |
| `retrieval_pipeline.py` | 三层检索（结构化 + 图谱 + 语义） |
| `parallel_executor.py` | 并发控制 + Git worktree 隔离 |
| `pipeline.py` | 分析管道编排 |
| `state_adapter.py` | 主状态源 ↔ Ralph 状态的桥接转换 |

### `dashboard/` — API + 命令处理 + 事件广播

| 文件 | 职责 |
|------|------|
| `state_repository.py` | **主状态源**（Feature/Agent/Command/Event/BlockingIssue 等） |
| `coordinator.py` | 包装 PM 执行流程，插入审批闸门 |
| `command_processor.py` | 命令状态机（pending → accepted → applied） |
| `consumer.py` | 命令轮询 + 分发到 RalphCommandHandler |
| `event_bus.py` | 内存事件总线 |
| `agent_pool.py` | 多实例 Agent 管理 |
| `agent_process_manager.py` | Agent 进程管理 |
| `silence_detector.py` | Agent 静默检测 |
| `api/routes.py` | REST API 入口（应按功能域拆分） |

### `agents/` — 角色执行器

| 文件 | 职责 |
|------|------|
| `pool.py` | Agent 实例生命周期 + workspace 创建 |
| `base_agent.py` | Agent 基类（claude -p 调用封装） |
| `*_agent.py` | 各专业角色（backend/frontend/qa/pm 等） |

### `dashboard-ui/` — 前端展示

Next.js 15 + TypeScript + Zustand + WebSocket。负责数据展示、用户交互、API 调用。

---

## 九、数据流向图

```
┌──────────┐
│  前端 UI  │
└────┬─────┘
     │ HTTP POST/GET + WebSocket
     ▼
┌──────────────────────────────────────────────────────┐
│                    dashboard/                         │
│  ┌──────────────┐  ┌───────────────────────────────┐ │
│  │  api/routes   │  │  coordinator → project_manager│ │
│  │  (REST+WS)    │  │      ↓                        │ │
│  └──────┬───────┘  │  AgentPool → agents/*         │ │
│         │          └───────────────────────────────┘ │
│         │                                            │
│         ▼                                            │
│  ┌──────────────────┐    ┌────────────────────────┐  │
│  │ state_repository │◄───│ command_processor      │  │
│  │ (主状态源)       │    │ consumer               │  │
│  │                  │    │ event_bus              │  │
│  └────────┬─────────┘    └────────────────────────┘  │
│           │                                          │
└───────────┼──────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────┐
│                    ralph/                             │
│  ┌──────────────────┐    ┌────────────────────────┐  │
│  │ command_handler  │    │ work_unit_engine       │  │
│  │ repository       │    │ memory_manager         │  │
│  │ config_manager   │    │ knowledge_graph        │  │
│  │ parallel_executor│    │ retrieval_pipeline     │  │
│  └──────────────────┘    └────────────────────────┘  │
└──────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────┐
│                    core/                              │
│  state_models.py（权威模型）                          │
│  feature_tracker / blocking_tracker / execution_ledger│
│  permission_guard / config                           │
└──────────────────────────────────────────────────────┘
```
