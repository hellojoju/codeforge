# Auto-Coding 执行工作流

## 执行原则

1. 一次执行只处理一个明确的 Feature 子目标（单次执行边界）。
2. 执行前必须明确输入上下文：PRD 摘要、依赖上下文、当前目标。
3. 执行后必须产生可观测结果：状态、事件、台账、必要时阻塞问题。

## Feature / Task / Command

| 概念 | 定义 | 生命周期 |
|------|------|----------|
| **Feature** | 面向用户需求的业务项。一个 Feature 对应一个完整功能。 | pending → running → done / blocked / failed |
| **Task** | Feature 下可执行的工程单元。一个 Feature 可拆为多个 Task。 | pending → running → needs_review → accepted / failed / blocked |
| **Command** | 人类对系统的控制指令。 | pending → processing → completed / rejected |

关系：`Feature 1:N Task`，`Command` 独立于 Feature/Task 作为控制通道。

## 标准执行流程

1. 选择下一个可执行 Feature（按优先级 + 依赖顺序）。
2. 分配 Agent 实例并记录开始事件到 `RalphRepository`。
3. Agent 执行单次目标，返回标准 `AgentResult`。
4. 成功时进入 `needs_review`，等待审批或验收。
5. 验收通过后标记完成，写入 `execution-plan.json` 台账。
6. 失败时根据重试次数决定重试或创建 `BlockingIssue`。

## 阻塞协议

### 阻塞类型枚举

| 类型 | 说明 | 人工介入方式 |
|------|------|-------------|
| `missing_env` | 缺少环境变量 | 在 `.env` 中配置 |
| `missing_credentials` | 缺少 API 凭据 | 配置 API Key |
| `external_service_down` | 外部服务不可用 | 等待或切换服务 |
| `manual_decision_required` | 需要人工决策 | 在 Dashboard 审批 |
| `test_unavailable` | 测试不可用 | 修复测试环境 |
| `unexpected_runtime_error` | 运行时未知错误 | 查看日志诊断 |
| `dependency_not_met` | 依赖 Feature 未完成 | 等待依赖完成 |
| `code_error` | 代码执行错误 | 修复代码后重试 |
| `resource_exhausted` | 资源耗尽 | 清理资源或扩容 |
| `scope_violation` | 超出允许修改范围 | 审核修改内容 |
| `review_failed` | 评审未通过 | 修复评审指出的问题 |

### 阻塞上报

Agent 执行结果中必须包含标准阻塞结构：

```json
{
  "success": false,
  "blocked": true,
  "blocking_type": "missing_env",
  "blocking_message": "缺少 OPENAI_API_KEY",
  "required_human_action": "请在 .env 中配置 OPENAI_API_KEY"
}
```

系统自动将阻塞写入 `RalphRepository`（UnifiedBlockingIssue），并通过 WebSocket 广播。

### 阻塞处理

1. Agent 上报阻塞 → 系统自动创建 `BlockingIssue`。
2. 前端 Dashboard 展示阻塞面板，显示类型、原因、人工介入方式。
3. 人工解除阻塞 → `BlockingIssue.status → resolved`。
4. 关联的 Task/Feature 重新进入排队。

## 如何判断完成

- **语法检查失败** → 不能算完成，必须修复。
- **有 `test_steps` 但没跑 E2E** → 不能标记完成。
- **有未解决的 `BlockingIssue`** → 不能继续推进。
- **审批拒绝** → 返回 `needs_rework`，不能进入 `accepted`。
- **所有验收标准通过 + 审批通过** → 进入 `accepted`。

## 单次执行边界

- 一次 Agent 调用只执行一个 Task 或一个明确子目标。
- 不允许一次执行同时修改不相关的多个模块。
- 执行目标在执行前必须写入 `ExecutionRun` 记录。
