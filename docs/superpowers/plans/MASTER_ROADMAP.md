# Ralph Orchestrator 主路线图

> 文档目的：完整呈现项目的总体计划、当前完成状态、剩余工作。按阶段推进，每个阶段完成后更新此文档。

**基于文档：**
- PRD: `Ralph docs/auto-coding-ralph-orchestrator-prd.zh.md`
- 实施方案: `Ralph docs/auto-coding-ralph-orchestrator-implementation-plan.zh.md`
- MVP 验收清单: `Ralph docs/auto-coding-ralph-orchestrator-mvp-checklist.zh.md`
- AI 协议: `Ralph docs/auto-coding-ralph-orchestrator-ai-protocol.zh.md`
- Phase 2 设计: `Ralph docs/auto-coding-ralph-orchestrator-phase2-design.zh.md`

---

## 总览

```
Phase 0: 基础设施 ─────────────────── 100% ✅
Phase 1: 可靠顺序执行 ──────────────── 85% ⚠️
Phase 2: 真实可用性验收 ───────────── 30% ⏳
Phase 3: 隔离并行执行 ──────────────── 100% ✅
Phase 4: 可视化和长期运行 ─────────── 70% ⚠️
```

> 说明：当前状态已按代码真实可用性回写，不再使用“端点已存在=能力已完成”的统计口径。

---

## Phase 0: 基础设施 ✅

| 模块 | 状态 | 说明 |
|------|------|------|
| `.ralph/` 目录结构 | ✅ | 所有子目录已创建 |
| WorkUnit schema | ✅ | 8 状态 + 20+ 字段 |
| TaskHarness schema | ✅ | 17 字段 + Retry/TimeoutPolicy |
| StateMachine | ✅ | 角色权限 + transitions.jsonl |
| RalphRepository | ✅ | 原子写入 + CRUD |
| EventBus + WebSocket | ✅ | 实时事件推送 |
| Dashboard API 框架 | ✅ | 46 端点 |
| 前端框架 (Next.js) | ✅ | 22 页面 |
| 测试基础设施 | ✅ | 994 测试 |

---

## Phase 1: 可靠顺序执行 ⚠️ 85%

### ❌ 未完成项

| # | 项 | 缺什么 |
|---|-----|--------|
| ~~13-6~~ | ~~ToolAdapter 能力匹配~~ | ✅ `match()` 按 streaming/mcp/context 需求匹配 |
| ~~13-7~~ | ~~ToolAdapter 生命周期~~ | ✅ `health_check_all()` + `downgrade()` |
| ~~13-8~~ | ~~ToolAdapter config~~ | ✅ `ToolchainConfigLoader` 读写 .ralph/config/toolchain.json |
| ~~20-3~~ | ~~LLM Provider 密钥加密~~ | ✅ `_encrypt_api_key`/`_decrypt_api_key` + `.key` 文件 |
| ~~20-4~~ | ~~LLM Provider 后端代理~~ | ✅ `proxy_request()` 路由到 Provider API |
| ~~20-6~~ | ~~LLM Provider 自动降级~~ | ✅ `auto_downgrade()` 按活跃 Provider 列表切换 |
| ~~20-8~~ | ~~LLM Provider 成本统计~~ | ✅ `_record_usage()` + `get_usage_stats()` |
| ~~21-2~~ | ~~Issue GitHub 同步~~ | ✅ `GitHubIssueSource` 通过 GH API 拉取 |
| ~~21-3~~ | ~~Issue 自动分类 LLM~~ | ✅ `classify_with_llm()` 调用 Claude 兜底 |
| ~~21-4~~ | ~~Issue Policy 自动处理~~ | ✅ `issues_to_work_units()` 按策略生成 WorkUnit |
| ~~9-2~~ | ~~Decision Log superseded~~ | ✅ `record_decision()` 自动 supersede 旧决策 |

---

## Phase 2: 真实可用性验收 ⏳ 30%

| # | 项 | 状态 |
|---|-----|------|
| 1 | 用户路径验收 | ✅ VerificationManager 有定义 |
| 2 | Playwright 真实点击 | ⚠️ 代码有，macOS沙箱拦截 |
| 3 | 多尺寸截图 | ⚠️ 代码有，macOS沙箱拦截 |
| ~~4~~ | ~~控制台错误捕获~~ | ✅ `capture_console_errors()` |
| ~~5~~ | ~~网络错误捕获~~ | ✅ `capture_network_errors()` |
| 6 | 边界状态检查 | ✅ VerificationManager 有定义 |
| ~~7~~ | ~~探索式点击测试~~ | ✅ `exploratory_click_test()` |

---

## Phase 3: 隔离并行执行 ✅ 100%

| # | 项 | 状态 |
|---|-----|------|
| ~~1~~ | ~~文件级锁~~ | ✅ `FileLock` 进程安全锁 |
| ~~2~~ | ~~git worktree 隔离~~ | ✅ `WorktreeManager` |
| ~~3~~ | ~~并行任务调度~~ | ✅ `ParallelExecutor` 拓扑排序 + 并发控制 |
| ~~4~~ | ~~集成队列~~ | ✅ `IntegrationQueue` FIFO |
| ~~5~~ | ~~合并冲突处理~~ | ✅ `MergeHandler` |
| ~~6~~ | ~~集成后回归测试~~ | ✅ `RegressionTester` |

---

## Phase 4: 可视化和长期运行 ⚠️ 70%

| # | 项 | 状态 |
|---|-----|------|
| 1 | dashboard | ✅ 22 页面 |
| 2 | 实时日志 | ✅ EventLog |
| 3 | 阻塞项处理界面 | ✅ ApprovalCenter |
| 4 | **成本和耗时统计** | ⚠️ 部分（后端有基础统计，前端整合不足） |
| 5 | **历史项目复盘** | ⚠️ 部分（有基础接口，闭环与可视化不足） |
| 6 | 多工具适配器界面 | ✅ ToolAdapter 配置页 |
| 7 | LLM Provider 前端配置 | ⚠️ 有页面，端到端能力不完整 |
| 8 | **GitHub Issues 同步 UI** | ❌ |
| 9 | **多 Provider 降级监控** | ❌ |

### 当前关键缺口（影响稳定性）

1. `dashboard/api/routes.py` 中部分高级端点依赖未落地模块，现已增加 capability 门禁并统一返回 `501`，待后续逐步实现。
2. 执行台账过滤能力已支持 `agent/feature/status`，仍需补充真实场景验证与文档示例。
3. 架构契约脚本 `scripts/check_architecture.py` 已提供最小实现，后续可继续增强规则覆盖。

---

## 执行顺序

按优先级从高到低排：

1. **P0 稳定性修复** — routes 启动问题、缺失模块端点降级、文档口径对齐
2. **P1 一致性收口** — 执行台账 Query 化与过滤、架构契约检查脚本
3. **P2 质量补强** — 状态一致性测试、API/WS 契约文档补齐

---

## 当前步骤

**→ 从 Phase 1 剩余项开始：ToolAdapter 能力匹配 + 生命周期管理 + yaml 配置**
