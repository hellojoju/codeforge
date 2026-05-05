# 当前 API 基线

## Dashboard Core REST

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/state` | 统一状态快照 |
| GET | `/api/dashboard/state` | 完整快照（旧格式） |
| GET | `/api/events` | 事件列表（支持 agent_id/after_id/limit 过滤） |
| GET | `/api/dashboard/events` | Dashboard 事件列表 |
| POST | `/api/chat` | 用户对话消息 |
| POST | `/api/approve` | 批准待处理操作 |
| POST | `/api/reject` | 驳回待处理操作 |
| POST | `/api/pause` | 暂停 Agent |
| POST | `/api/resume` | 恢复 Agent |
| POST | `/api/retry` | 重试 Feature |
| POST | `/api/skip` | 跳过 Feature |
| GET | `/api/blocking-issues` | 阻塞问题列表 |
| GET | `/api/execution-ledger` | 执行账本 |
| GET | `/api/dashboard/pending-approvals` | 待审批命令列表 |

## Command API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/dashboard/commands` | 创建命令（新接口，带幂等键） |
| GET | `/api/dashboard/commands/{command_id}` | 查询命令状态 |

## Module Assignments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/modules` | 列出模块分配（支持 role 过滤） |
| POST | `/api/dashboard/modules` | 创建/更新模块分配 |
| DELETE | `/api/dashboard/modules/{module_id}` | 删除模块分配 |

## Execution Control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/execution/start` | 启动 PMCoordinator 执行循环 |
| POST | `/api/execution/stop` | 停止 PMCoordinator 执行循环 |
| GET | `/api/execution/status` | 获取当前执行状态 |

## Agent Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | 列出所有 Agent（含静默检测） |
| GET | `/api/agents/{agent_id}/status` | 获取单个 Agent 状态 |
| POST | `/api/agents/{agent_id}/message` | 向 Agent 发送消息 |
| POST | `/api/agents/{agent_id}/interrupt` | 中断 Agent 进程 |

## Feature API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/features/list` | 列出 Features（支持 status 过滤） |
| GET | `/api/features/{feature_id}` | 获取 Feature 详情 |
| POST | `/api/features/{feature_id}/rerun` | 重新执行 Feature |
| POST | `/api/features/{feature_id}/verify` | 运行 Feature 验证 |
| POST | `/api/features/sync-from-prd` | 从 PRD 同步 Feature 清单 |

## Ralph — Work Unit

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/health` | 系统健康检查 |
| GET | `/api/ralph/work-units` | 列出 WorkUnit（支持 status 过滤） |
| GET | `/api/ralph/work-units/{work_id}` | 获取 WorkUnit 详情 |
| GET | `/api/ralph/work-units/{work_id}/evidence` | 获取证据列表 |
| GET | `/api/ralph/work-units/{work_id}/evidence/{file_path}` | 获取证据文件内容（含安全校验） |
| GET | `/api/ralph/work-units/{work_id}/reviews` | 获取审查结果列表 |
| GET | `/api/ralph/work-units/{work_id}/transitions` | 获取状态转换历史 |
| GET | `/api/ralph/work-units/{work_id}/checkpoints` | 获取 checkpoint 列表 |
| POST | `/api/ralph/work-units/{work_id}/checkpoints/{turn}/restore` | 从 checkpoint 恢复 |

## Ralph — Blockers & Actions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/blockers` | 列出阻塞项（支持 work_id/resolved 过滤） |
| GET | `/api/ralph/blocking-issues` | 列出统一阻塞项（支持 status 过滤） |
| GET | `/api/ralph/pending-actions` | 获取待处理审批/干预项汇总 |

## Ralph — State & Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/state-snapshot` | 统一状态快照 |
| GET | `/api/ralph/execution-ledger` | 执行账本 |
| GET | `/api/ralph/summary` | 运行概览统计（含成功率） |

## Ralph — Commands

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ralph/commands` | 创建 Command（带幂等键） |
| GET | `/api/ralph/commands/{command_id}` | 查询 Command 状态 |
| POST | `/api/ralph/commands/{command_id}/cancel` | 取消待处理 Command |
| GET | `/api/ralph/commands` | 列出 Command（支持 status 过滤） |

## Ralph — Events & Tastes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/events` | 查询事件历史 |
| GET | `/api/ralph/tastes` | 获取设计偏好记忆 |
| POST | `/api/ralph/tastes` | 创建 taste 偏好 |
| DELETE | `/api/ralph/tastes/{taste_id}` | 删除 taste 偏好 |

## Ralph — Security

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/security/guard-status` | 获取 Prompt Injection 防护状态 |
| POST | `/api/ralph/security/scan` | 手动扫描注入风险 |

## Ralph — Reports

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/reports` | 列出已生成报告 |
| POST | `/api/ralph/reports/generate` | 生成研发报告 |
| GET | `/api/ralph/reports/{name}` | 获取单个报告内容 |

## Ralph — Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/settings/providers` | 列出 LLM Provider |
| POST | `/api/ralph/settings/providers` | 创建/更新 Provider |
| PUT | `/api/ralph/settings/providers/{provider_id}` | 更新指定 Provider |
| DELETE | `/api/ralph/settings/providers/{provider_id}` | 删除 Provider |
| POST | `/api/ralph/settings/providers/{provider_id}/test` | 测试 Provider 连通性 |
| GET | `/api/ralph/settings/model-assignments` | 列出模型路由规则 |
| PUT | `/api/ralph/settings/model-assignments` | 保存模型路由规则 |
| GET | `/api/ralph/settings/toolchain` | 获取工具链配置 |
| PUT | `/api/ralph/settings/toolchain` | 保存工具链配置 |
| POST | `/api/ralph/settings/toolchain/dispatch-parallel` | 并行执行 ready WorkUnit |
| GET | `/api/ralph/settings/issue-policy` | 获取 Issue 治理策略 |
| PUT | `/api/ralph/settings/issue-policy` | 保存 Issue 治理策略 |

## Ralph — Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/projects` | 列出已知项目 |
| POST | `/api/ralph/projects/open` | 打开/选择项目 |
| POST | `/api/ralph/projects/analyze` | 运行代码库侦察分析 |
| GET | `/api/ralph/projects/analysis` | 获取缓存的分析结果 |
| POST | `/api/ralph/projects/init` | 初始化新项目 |
| POST | `/api/ralph/projects/deep-analyze` | 启动 AI 深度分析（异步） |
| GET | `/api/ralph/projects/analysis-progress` | 获取深度分析进度 |
| GET | `/api/ralph/projects/report` | 获取项目分析报告 |
| GET | `/api/ralph/projects/report/structured` | 获取结构化分析数据 |
| POST | `/api/ralph/projects/browse-directory` | 浏览文件系统目录 |

## Ralph — File Browser

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ralph/files` | 列出目录内容 |
| GET | `/api/ralph/files/content` | 获取文件内容 |

## WebSocket

| Path | Description |
|------|-------------|
| `ws://.../ws/dashboard` | 实时推送 — 首帧 `hello`，后续增量事件 |

**总计：84 REST 端点 + 1 WebSocket 端点**
