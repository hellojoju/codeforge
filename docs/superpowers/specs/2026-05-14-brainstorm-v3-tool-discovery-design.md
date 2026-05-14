# 需求共创 V3 与开发工具发现能力设计

> 两个增强功能：需求共创阶段增加系统主动分析与多智能体辩论，开发阶段增加工具发现能力。

## 一、需求共创三步走

### 现状问题

Brainstorm V2 是纯问答驱动的——系统按模板提问 → 用户回答 → 提取事实。系统没有自己的判断，用户说一句它记一句。实际需求共创中，用户往往只有模糊想法，需要系统先给出方向性分析，引导用户思考。

### 新流程：三步走

```
用户模糊需求 → 系统主动分析 → 沟通确认大方向 → 多 agent 功能辩论 → PM 汇总 → 用户确认/修改（循环）
```

#### 阶段 A：系统主动分析（新增 `PROACTIVE_ANALYSIS` 阶段）

- 用户抛出模糊需求后，系统先用 LLM 自行分析：
  - 这个需求大概属于什么产品类型
  - 可能的技术选型方向
  - 关键功能模块推测
  - 潜在风险点
- 系统以"我认为应该这么做"的姿态输出分析结果
- 用户在系统框架上调整，而不是从零开始想
- 几轮沟通确认大方向

#### 阶段 B：多智能体功能辩论（新增 `MULTI_AGENT_DELIBERATION` 阶段）

- 大方向确认后，PM spawn 多个子 agent，**每个都从功能需求的不同维度审视**：

| Agent 维度 | 关注点 |
|-----------|--------|
| **用户行为路径** | 用户进来之后的操作路径顺不顺，漏了什么交互环节，路径是否自然 |
| **功能完整性** | 主流程有了但分支流程呢？异常情况的功能兜底呢？CRUD 之外缺了什么 |
| **竞品/行业经验** | 这类产品通常有哪些默认功能？我们少了什么？行业标准功能覆盖如何 |
| **场景组合** | 用户可能同时有多个需求，现有功能能否组合覆盖？是否需要新增组合功能 |

- 每个 agent 从自己的角度挑战和完善需求功能清单
- PM 作为组织者和评判者，判断哪些讨论有实质价值，汇总结论

#### 阶段 C：用户确认循环

- 把多 agent 讨论后形成的清晰需求给用户看
- 用户提出调整意见
- 系统根据用户意见修改
- 循环直到用户满意

### 现有系统需要的改动

1. **Brainstorm V2 增加两个新 Phase**：
   - `PROACTIVE_ANALYSIS`：在 `PRODUCT_DEF` 之前，系统先输出自己的分析
   - `MULTI_AGENT_DELIBERATION`：在 `FEATURE_DECOMPOSE` 之后、`RELATIONSHIP` 之前

2. **新增 4 个功能审视维度的 Agent 角色定义**：
   - `user_journey_analyst` — 用户行为路径分析
   - `feature_completeness_reviewer` — 功能完整性审查
   - `industry_benchmark_analyst` — 竞品/行业经验对标
   - `scenario_combiner` — 场景组合分析

3. **PM Agent 升级**：具备主持多 agent 辩论的能力——spawn 子 agent、收集各方观点、判断讨论价值、汇总结论

---

## 二、开发中的工具发现能力

### 流程

```
需求明确 → PM 思考技术路线 → 提交用户确认 → 识别工具需求 → 互联网/GitHub 搜索 → 评估推荐 → 交给子 agent 集成
```

### 步骤详述

1. **PM 制定技术路线**：根据已确认的需求，PM 分析并制定技术实现方案
2. **用户确认技术路线**：PM 将技术路线交给用户审阅，用户确认或提出调整意见后再开干
3. **PM 识别工具需求**：技术路线确定后，PM 分析哪些环节需要第三方工具/库/引擎支撑
4. **PM 搜索工具**：通过 WebSearch / GitHub API 搜索：
   - 互联网上的开源工具（游戏引擎、SDK 等）
   - GitHub 上类似项目，评估是否可改造复用
5. **评估与交付**：PM 对候选工具做功能匹配度、活跃度、兼容性评估，将选定的工具信息交给子 agent 去集成

### 需要新增的基础设施

1. **PM Agent 新增能力**：
   - `decide_technical_route` — 制定技术路线
   - `decide_tool_search` — 判断是否需要搜索工具、生成搜索关键词
   - 提交技术路线给用户确认的交互机制

2. **`ToolDiscoveryService`**：封装搜索、评估、推荐的逻辑
   - WebSearch 搜索开源工具
   - GitHub API 搜索类似项目
   - 评估维度：功能匹配度、社区活跃度、许可证、与当前技术栈兼容性

3. **Agent 配置扩展**：增加 WebSearch / GitHub 搜索作为 PM 可选工具

---

## 三、改动总结

| 改动项 | 文件/模块 | 说明 |
|--------|-----------|------|
| 新增 PROACTIVE_ANALYSIS 阶段 | `ralph/brainstorm_manager.py` | 系统主动分析模糊需求 |
| 新增 MULTI_AGENT_DELIBERATION 阶段 | `ralph/brainstorm_manager.py` | 多 agent 功能辩论 |
| 新增 4 个 Agent 角色 | `agents/.ralph/config/agent-definitions.json` | 功能审视维度 |
| PM 主持多 agent 辩论 | `ralph/pm_agent.py` | spawn、收集、判断、汇总 |
| PM 技术路线制定与确认 | `ralph/pm_agent.py` | 技术路线输出 + 用户确认流程 |
| ToolDiscoveryService | `ralph/tool_discovery.py`（新文件） | 工具搜索、评估、推荐 |
| WebSearch 工具接入 | `ralph/config_manager.py` | PM 可选工具配置 |
