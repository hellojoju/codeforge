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
Phase 1: 可靠顺序执行 ──────────────── 95% ✅
Phase 2: 真实可用性验收 ───────────── 60% ⏳
Phase 3: 隔离并行执行 ──────────────── 0% ❌
Phase 4: 可视化和长期运行 ─────────── 60% ⏳
```

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
| 20-3 | **LLM Provider 密钥加密** | ❌ 后端 proxy 有了，但 api_key 还是明文存 JSON |
| ~~20-4~~ | ~~LLM Provider 后端代理~~ | ✅ `proxy_request()` 路由到 Provider API |
| ~~20-6~~ | ~~LLM Provider 自动降级~~ | ✅ `auto_downgrade()` 按活跃 Provider 列表切换 |
| ~~20-8~~ | ~~LLM Provider 成本统计~~ | ✅ `_record_usage()` + `get_usage_stats()` |
| ~~21-2~~ | ~~Issue GitHub 同步~~ | ✅ `GitHubIssueSource` 通过 GH API 拉取 |
| ~~21-3~~ | ~~Issue 自动分类 LLM~~ | ✅ `classify_with_llm()` 调用 Claude 兜底 |
| 21-4 | **Issue Policy 自动处理** | ❌ 策略定义了但 WorkUnitEngine 不消费 |
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
| 7 | **探索式点击测试** | ❌ 未实现 |

---

## Phase 3: 隔离并行执行 ❌ 0%

| # | 项 | 状态 |
|---|-----|------|
| 1 | **文件级锁** | ❌ |
| 2 | **git worktree 或隔离 workspace** | ❌ |
| 3 | **并行任务调度** | ❌ |
| 4 | **集成队列** | ❌ |
| 5 | **合并冲突处理** | ❌ |
| 6 | **集成后回归测试** | ❌ |

---

## Phase 4: 可视化和长期运行 ⏳ 60%

| # | 项 | 状态 |
|---|-----|------|
| 1 | dashboard | ✅ 22 页面 |
| 2 | 实时日志 | ✅ EventLog |
| 3 | 阻塞项处理界面 | ✅ ApprovalCenter |
| 4 | **成本和耗时统计** | ❌ |
| 5 | **历史项目复盘** | ❌ |
| 6 | 多工具适配器界面 | ✅ ToolAdapter 配置页 |
| 7 | LLM Provider 前端配置 | ✅ 有页面，缺后端代理 |
| 8 | **GitHub Issues 同步 UI** | ❌ |
| 9 | **多 Provider 降级监控** | ❌ |

---

## 执行顺序

按优先级从高到低排：

1. **Phase 1 补齐** — 把各模块缺失的具体能力补上（ToolAdapter 能力匹配、LLM Provider 安全、Issue 自动处理等）
2. **Phase 2 补齐** — 控制台错误捕获、网络错误捕获、探索式点击
3. **Phase 4 补齐** — 成本统计、历史复盘
4. **Phase 3 补齐** — 文件锁、worktree、并行调度（依赖 Phase 1+2 稳定）

---

## 当前步骤

**→ 从 Phase 1 剩余项开始：ToolAdapter 能力匹配 + 生命周期管理 + yaml 配置**
