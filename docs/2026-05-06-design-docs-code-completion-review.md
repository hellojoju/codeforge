# 设计文档与代码完成度对照评估（2026-05-06）

> 目标：对照 `docs/` 下设计类文档，评估当前代码落地情况，并给出待完善清单。  
> 评估范围：`ARCHITECTURE.md`、`WORKFLOW.md`、`state-model.md`、`three-project-roadmap.md`、`DASHBOARD_ARCHITECTURE.md`、`docs/ralph/*.md`、`docs/superpowers/specs/*.md`、`docs/superpowers/plans/*.md`。

---

## 1. 结论总览

当前项目属于“**主链路可用，但二期扩展和一致性仍有缺口**”状态：

1. **主链路已具备**：核心编排、统一状态仓库、阻塞闭环、执行台账、Dashboard 基础能力、Ralph 基础工作流整体可用。
2. **设计与实现存在偏差**：部分文档标记为“已完成”的能力，在代码中仍是占位或未落地。
3. **最大风险点**：`dashboard/api/routes.py` 暴露了大量高级端点，但依赖模块缺失，存在运行时失败风险。

---

## 2. 已完成（与设计一致度高）

### 2.1 架构与状态主线（对应 `three-project-roadmap.md` Phase 1/3/4/6/7/8）

- 已有 `ProjectStateRepository` 作为统一状态写入口，覆盖 feature/agent/command/event/chat/blocking/execution。
- 已有阻塞对象与闭环：阻塞创建、查询、解除、事件广播、CLI `blocked/unblock`。
- 已有服务拆分：`FeatureExecutionService`、`FeatureVerificationService`、`GitService` 已落地。
- 已有操作入口：`Makefile`、`cli.py` 的 `plan/explain-state/blocked/doctor` 命令。
- 已有执行台账 API：`/api/execution-ledger` 与前端面板基础展示。

### 2.2 Ralph 基础能力（对应 PRD/MVP checklist 的一期主能力）

- Brainstorm、PRD、Task Decompose、Spec/Contract、Verification、Report、Issue Source、Tool Adapter、Provider 配置等基础模块和 API 入口已存在。
- Ralph 前端路由体系基本齐全（work-units、events、approvals、settings、projects、pipeline、specs、contracts 等）。

---

## 3. 待完善清单（按优先级）

## P0（建议先做，直接影响稳定性）

1. **Ralph 高级端点“可见但不可运行”**
- `dashboard/api/routes.py` 依赖 14 个缺失模块：
  - `context_engine`
  - `graphify_service`
  - `issue_command_parser`
  - `issue_sync_protocol`
  - `knowledge_graph`
  - `memory_manager`
  - `pipeline`
  - `pm_agent`
  - `project_analyzer`
  - `recovery`
  - `retrieval_pipeline`
  - `ship_service`
  - `taste_memory`
  - `turn_engine`
- 现状影响：对应 API 一旦被调用会在运行时失败。

2. **`routes.py` 中存在明显实现不一致**
- `create_dashboard_app()` 中使用了未定义变量 `project_dir`。
- `app.state` 写入的是 `ralph_engine`，但安全端点读取的是 `work_unit_engine`，命名不一致。
- 现状影响：部分路径会直接抛异常，不符合“可视化控制台可稳定运行”目标。

3. **文档“已完成”与代码现状不一致**
- `docs/superpowers/plans/MASTER_ROADMAP.md` 将多项能力标注为完成，但代码中并未完整落地（见上方缺失模块）。
- 建议把该文档改为“真实完成态”，避免误导后续开发决策。

## P1（建议第二批，影响体验与可维护性）

1. **前端状态治理仍未完全完成（Phase 5 收尾）**
- 仍保留大量 Zustand 直连与局部 `fetch` 页面，TanStack Query 尚未全量接入。
- `ExecutionLedgerPanel` 仅展示，缺少按 agent/feature/status 过滤（对应 `TODO.md` T-009）。

2. **Dashboard 架构目标与现代码并存**
- `DASHBOARD_ARCHITECTURE.md` 定义“纯 Ralph 化”，但当前旧 Feature 流程组件和接口仍在并行使用。
- 建议明确“兼容期截止点”和“下线路径”，避免长期双轨维护。

3. **架构契约工具链未闭环**
- `ARCHITECTURE.md` 声称 `scripts/check_architecture.py` 可自动检测，但仓库中不存在该脚本。

4. **状态术语不统一**
- `WORKFLOW.md` 使用 `running/needs_review/accepted`，部分核心模型/实现使用 `in_progress/review/done`。
- 建议统一术语字典并在 API 层做明确映射。

## P2（建议第三批，提升工程质量）

1. **状态一致性测试未补齐**
- 与 `three-project-roadmap.md`、`TODO.md` 对齐：缺少状态迁移、单一事实源约束、快照一致性测试组合。

2. **API 文档与事件契约文档不足**
- REST 返回结构与 WebSocket 事件契约缺少统一对外文档，前后端协作成本较高。

3. **流式输出链路未闭环**
- TODO 中的“Agent 执行流式输出到终端/dashboard”仍未完成。

---

## 4. 文档间冲突与建议

1. **Roadmap 与 Master Roadmap 状态定义冲突**
- 一份强调仍有未完成项，一份写成 100%。建议收敛为一份权威状态文档。

2. **设计前瞻 vs 代码现实混写**
- `phase2-design` 中大量“未来态”（记忆/图谱/PM 调度）与现代码混在同一实现状态描述中。
- 建议拆分为“已落地 / 进行中 / 规划中”三栏，减少认知偏差。

3. **API 设计文档需按“已发布契约”维护**
- 建议以 `dashboard/api/routes.py` + `dashboard-ui/lib/ralph-api.ts` 自动生成/半自动校验契约清单。

---

## 5. 建议执行顺序（可直接排期）

1. **第一周（稳定性修复）**
- 修复 `routes.py` 中 `project_dir` 与 `work_unit_engine` 命名问题。
- 对缺失模块相关端点做“临时降级”：未实现时返回 501，避免 500。
- 更新 `MASTER_ROADMAP.md` 为真实状态。

2. **第二周（一致性与收口）**
- 完成 Phase 5 前端 Query 全量迁移关键页面。
- 增加执行台账过滤（agent/feature/status）。
- 补 `check_architecture.py` 或下调文档承诺。

3. **第三周（测试与文档）**
- 补齐状态一致性测试套件。
- 输出统一 API + WS 事件契约文档。
- 明确“旧 Feature 流程下线计划”。

---

## 6. 最终判断

项目不是“未完成”，而是“**核心可运行 + 扩展能力宣称超前**”：

- 如果目标是稳定交付，应先做 **P0 稳定性与真实状态对齐**。
- 如果目标是推进 Ralph Phase 2，应先补齐缺失模块或关闭对应端点，避免“看起来有，实际上不可用”。
