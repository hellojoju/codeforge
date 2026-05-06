# TODO — 待办工作清单

> 最后更新：2026-05-06
> 状态标记：✅ 已完成 / 🔄 进行中 / ⏳ 待开始 / ❌ 阻塞

---

## 已完成 ✅

### 1. 修复 `--allowedTools` 无效参数
- **状态**：✅ 已完成

### 2. 修复 workspace 验证不匹配
- **状态**：✅ 已完成（2026-04-24）

### 3. 拆分 FeatureExecutionService
- **状态**：✅ 已完成

### 4. Dashboard 修复系列
- **状态**：✅ 已完成

### 5. 统一状态源（Phase 3）
- **状态**：✅ 已完成
- TaskQueue 已删除，`features.json` 退化为审计副本
- `ProjectStateRepository` 成为唯一长期事实源

### 6. 架构契约文档（Phase 1）
- **状态**：✅ 已完成

### 7. 服务拆分（Phase 8）
- **状态**：✅ 已完成

### 8. 阻塞处理完整闭环（Phase 4）
- **状态**：✅ 已完成（2026-05-06）
- Agent 阻塞上报路径集成到 PM 执行流程
- `_mark_feature_blocked` 通过 EventBus 广播 WebSocket 事件
- CLI `blocked` / `unblock` 命令可用
- PM 支持 `event_bus` 依赖注入

### 9. 执行台账（Phase 7 基础）
- **状态**：✅ 已完成

### 10. ProgressLogger 集成
- **状态**：✅ 已完成

### 11. Ralph Runtime Console 前端
- **状态**：✅ 已完成

### 12. 操作入口（Phase 6）
- **状态**：✅ 已完成
- Makefile、CLI `doctor`/`plan`/`blocked`/`explain-state` 命令
- `scripts/doctor.py` 环境健康检查

### 13. 前端状态治理基础（Phase 5）
- **状态**：✅ 已完成（2026-05-06）
- `dashboard-ui/lib/query-client.ts` + `query-provider.tsx`
- `dashboard-ui/lib/hooks/useDashboardQueries.ts` — 8 个 Query hooks
- Zustand → Query 迁移路径已建立

### 14. 核心断层修复
- **状态**：✅ 已完成（2026-05-05/06）
- `core/state_models.py` — 15 个模型权威定义
- `core/ralph_paths.py` — Ralph 目录解析
- `core/project_initializer.py` — PRD + Feature 生成
- `ralph/schema/retro_record.py` + `review_dimension.py`
- `agents/review_agent.py`

### 15. AgentPool 测试 + 死锁修复
- **状态**：✅ 已完成（2026-05-06）
- `tests/test_agent_pool.py` — 22 个测试用例
- 修复 `get_status()` 嵌套锁死锁

---

## 待办事项 ⏳

### 中优先级

#### T-003: 前端组件全面接入 TanStack Query（Phase 5 主体）
- **状态**：✅ 已完成（2026-05-06）
- **说明**：所有数据消费组件从 Zustand 迁移到 TanStack Query
- **已完成**：
  - ✅ `execution-control.tsx` — useExecutionStatus / useStartExecution / useStopExecution
  - ✅ `blocking-issues-panel.tsx` — useBlockingIssues / useResolveBlockingIssue
  - ✅ `command-bar.tsx` — useApprove / useReject / usePauseFeature / useResumeFeature / useRetryFeature / useSkipFeature
  - ✅ `agent-cluster-monitor.tsx` — useAgents / useInterruptAgent
  - ✅ `agent-status-panel.tsx` — useAgents / useInterruptAgent / useSendAgentMessage
  - ✅ `module-assignment-panel.tsx` — useModuleAssignments / useAgents
  - ✅ 新增 hooks：usePauseFeature, useResumeFeature, useRetryFeature, useSkipFeature, useInterruptAgent, useSendAgentMessage, useModuleAssignments
  - ✅ 测试全部重写：374 个测试全绿
- **保留 Zustand**：chat-window/chat-drawer（纯客户端聊天状态）
- **涉及**：`dashboard-ui/lib/hooks/useDashboardQueries.ts`, `dashboard-ui/components/`, `dashboard-ui/tests/`

#### T-008: 补状态一致性测试
- **状态**：✅ 已完成（2026-05-06）
- **说明**：21 个测试用例，覆盖深拷贝隔离、状态变更事件校验、磁盘原子写入、工作区隔离、内存/磁盘一致性、阻塞问题生命周期、并发写入、状态往返、命令幂等性、依赖解析

### 低优先级

#### T-009: 任务账本过滤功能（Phase 7 收尾）
- **状态**：✅ 已完成（2026-05-06）
- **说明**：按 Agent / Feature / 状态过滤
- **已完成**：
  - ✅ 后端 API 支持 `feature_id`、`agent_id`、`status` 三参数过滤
  - ✅ 前端 `useExecutionLedger` hook + `execution-ledger-panel.tsx` 三个 select 下拉框

#### T-010: 补 API 文档
- **状态**：✅ 已完成（2026-05-06）
- **说明**：`docs/dashboard-api-contract.md` 已补充 Agent 管理、Agent 控制、模块管理、用户聊天端点

#### T-011: 流式输出
- **状态**：⏳ 待开始（新 Phase）
- **说明**：Agent 执行时实时显示子进程输出到终端/dashboard
- **涉及**：`agents/base_agent.py`（subprocess.run → asyncio.subprocess）、`dashboard/event_bus.py`（output_chunk 事件）、`dashboard/api/routes.py`（WebSocket 输出流）、`cli.py`（实时输出显示）
- **架构分析**：当前所有子进程使用 `subprocess.run(capture_output=True)` 缓冲式捕获，无实时流式能力。需替换为 `asyncio.subprocess.Popen` + 逐行读取 + EventBus 广播 + WebSocket 推送

---

## 技术债

### 已知问题
（无 — 之前的问题全部已修复）

### 架构风险

1. **Agent 健康检测缺失**：AgentPool 无实例心跳机制
2. **并发安全未验证**：多 Agent 并行 acquire/release 未做压力测试

---

## 下次启动清单

运行项目前确认：
- [x] `pytest tests/` 全绿（50 passed）
- [x] `npx vitest run` 全绿（374 passed）
- [ ] `uv sync` 依赖最新
- [ ] 环境变量 `ANTHROPIC_API_KEY` 已设置（如需要实际执行）
