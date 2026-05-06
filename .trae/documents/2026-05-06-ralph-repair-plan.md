# Ralph 问题修复计划（最终交付版）

## 结果总览

本轮“稳定性与可运行性”收口已完成，核心目标达成：
- Dashboard/Ralph API 可稳定启动，不再因缺失模块直接崩溃。
- 之前声明但未落地的模块已补齐最小可运行实现。
- 高级端点已挂载并可调用，不再出现“代码存在但路由未注册”的 404 假象。
- 提供了可重复执行的一键端点验收脚本。

---

## 已完成事项

### P0 稳定性

1. 启动链路修复：
- `dashboard/api/routes.py` 中 `create_dashboard_app()` 返回与路由注册路径已修复。

2. 缺失模块补齐：
- 已补齐 Ralph 缺失模块与连带依赖（memory/context/pm/turn/knowledge/retrieval/pipeline/issue/sync/ship/recovery 等）。

3. 高级端点可访问：
- 关键端点（memory/context/pm/knowledge/search/pipeline/issues/ship/recovery/budget/workspaces）已可返回 200 或预期业务响应。

### P1 一致性与结构

4. 扩展路由模块化：
- 新增 `dashboard/api/ralph_extended_routes.py`，将高阶路由集中管理并由主应用挂载。

5. 预算配置更新能力补齐：
- 补齐 `RalphConfigManager.update_budget_config()`，使 `PUT /api/ralph/budget` 可用。

### P2 验收与工程化

6. 自动验收脚本：
- 新增 `scripts/verify_ralph_endpoints.py`，用于一键 smoke test 关键 Ralph 端点。

---

## 当前验收标准（已满足）

- `create_dashboard_app()` 可构建应用实例。
- 关键端点可调用且返回可预期状态码：
  - health/capabilities
  - memory（status/search/l1/config/compact）
  - context（pm/incremental）
  - pm（status/context/schedule）
  - knowledge graph（status/data/impact）
  - retrieval search
  - projects（deep-analyze/analysis-progress/report/structured/pipeline）
  - executions
  - issues（config/sync/sync-status/webhook）
  - ship（ship/releases）
  - budget（get/put）
  - workspaces
  - recovery-report

---

## 剩余建议（非阻塞）

1. 路由继续拆分（可维护性优化）：
- 当前主干已可用，后续可按域继续拆分 `routes.py` 的基础端点。

2. 前端状态治理持续优化：
- Query 统一改造可继续推进，但不影响本轮后端稳定交付。

3. 增加 CI 门禁：
- 将 `scripts/verify_ralph_endpoints.py` 纳入 CI 的 smoke 阶段，避免未来回归。
