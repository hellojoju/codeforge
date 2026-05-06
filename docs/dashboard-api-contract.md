# Dashboard API / WS 契约（当前实现）

## 1) 状态与事件

- `GET /api/dashboard/state`
- `GET /api/dashboard/events?after_event_id=<id>&limit=<n>`
- `GET /api/events?agent_id=<id>&after_id=<id>&limit=<n>`

返回约定：
- 状态快照返回 `Snapshot` 结构（agents/features/chat_history/module_assignments/blocking_issues）。
- 事件接口返回事件列表（部分接口为 `{ events: [...] }` 包裹结构）。

## 2) 执行与阻塞

- `GET /api/execution/status`
- `POST /api/execution/start`
- `POST /api/execution/stop`
- `GET /api/execution-ledger?feature_id=&agent_id=&status=`
- `GET /api/blocking-issues?feature_id=&resolved=`
- `POST /api/blocking-issues/{issue_id}/resolve`

返回约定：
- 执行台账返回 `{ executions: [...], summary: {...} }`。
- `summary` 按当前过滤条件聚合。

## 3) 命令与审批

- `POST /api/dashboard/commands` — 创建命令（返回 202）
- `GET /api/dashboard/commands/{command_id}` — 查询命令状态
- `GET /api/dashboard/pending-approvals` — 待审批列表
- `POST /api/approve` — 审批通过（创建 approve_decision 命令）
- `POST /api/reject` — 审批拒绝（创建 reject_decision 命令）

返回约定：
- 命令创建返回 `202`，包含 `command_id` 和 `status`。

## 4) Agent 管理

- `GET /api/agents` — 列出所有 Agent（含静默检测状态）
- `GET /api/agents/{agent_id}/status` — 单个 Agent 详细状态
- `POST /api/agents/{agent_id}/message` — 通过 stdin 向 Agent 发送消息（body: `{ "message": "..." }`）
- `POST /api/agents/{agent_id}/interrupt` — 中断正在运行的 Agent（body: `{ "force": true/false }`，可选）

## 5) Agent 控制（Feature 操作）

- `POST /api/pause` — 暂停指定 Agent（body: `{ "agent_id": "..." }`）
- `POST /api/resume` — 恢复已暂停的 Agent（body: `{ "agent_id": "..." }`）
- `POST /api/retry` — 重试 Feature 执行（body: `{ "feature_id": "..." }`）
- `POST /api/skip` — 跳过当前执行（body: `{}`）

## 6) 模块管理

- `GET /api/dashboard/modules` — 列出模块定义（可选 `?role=backend` 过滤）
- `POST /api/dashboard/modules` — 创建/更新模块（返回 201）
- `DELETE /api/dashboard/modules/{module_id}` — 删除模块定义

## 7) 用户聊天

- `POST /api/chat` — 发送用户消息，触发 PM 响应（body: `{ "content": "..." }`）

## 8) Ralph 端点状态说明

已可用（核心）：
- `GET /api/ralph/health`
- `GET /api/ralph/work-units`
- `GET /api/ralph/work-units/{work_id}`
- `GET /api/ralph/work-units/{work_id}/evidence`
- `GET /api/ralph/reports`

降级策略：
- 若端点依赖未落地模块（`ralph.*`），统一返回 `501`：
  - `detail: "Feature not implemented: missing module <module>"`
  - `error_type: "module_not_available"`

## 5) WebSocket 契约

- `WS /ws/dashboard`

首帧：
- `type: "hello"`
- 包含 `schema_version/project_id/last_event_id/agents/features/chat_history/module_assignments/blocking_issues`

增量帧：
- 与 `Event` 对齐，含 `event_id/type/payload/timestamp/caused_by_command_id`。
