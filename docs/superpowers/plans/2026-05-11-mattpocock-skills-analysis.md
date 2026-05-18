# Matt Pocock Skills 借鉴实现计划

> 目标：将 mattpocock/skills 的核心理念落地到 CodeForge
> 级别：程序员可直接按此文档写代码

---

## TL;DR

| # | 改造项 | 难度 | 收益 | 工作量 |
|---|--------|------|------|--------|
| 1 | CONTEXT.md — 统一领域语言 | ★☆☆ | 高 | 0.5天 |
| 2 | ADR 决策记录系统 | ★☆☆ | 中 | 0.5天 |
| 3 | Caveman 紧凑输出模式 | ★☆☆ | 高 | 0.5天 |
| 4 | 大文件渐进披露拆分 | ★★★ | 高 | 3-5天 |
| 5 | .out-of-scope 拒绝记录 | ★☆☆ | 低 | 0.5天 |
| 6 | 子会话隔离执行 | ★★☆ | 高 | 2-3天 |

---

## 1. CONTEXT.md — 统一领域语言

### 问题

目前 10 个 Agent 各有各的 prompt 文件，但使用了不一致的术语。例如有的地方叫 "feature"，有的叫 "work unit"，有的地方叫 "task"。Agent 之间缺乏共享的领域词典。

### 实现

**文件路径：** `/Users/jieson/auto-coding/CONTEXT.md`

**文件内容：**

```markdown
# CodeForge 领域统一语言

> 此文件定义 CodeForge 系统中所有术语的精确含义。
> 所有 Agent、prompt、文档必须使用此文件定义的术语。
> 变更此文件 = 变更架构契约，需要团队评审。

## 核心概念

| 术语 | 含义 | 别名（禁用） |
|------|------|-------------|
| Feature | 最小可交付功能单元，有验收标准 | task, todo, 功能点 |
| WorkUnit | 执行一个 Feature 的一次尝试，包含 agent 执行记录 | job, run, 执行单元 |
| Spec | 某一领域的详细规格设计（架构/后端/前端/数据库） | design doc, 设计文档 |
| Brainstorm Session | 从模糊想法到结构化 PRD 的探索对话 | 需求讨论, 头脑风暴 |
| PRD | 产品需求文档，最终输出的需求规格 | 需求文档 |
| Agent | 一个 AI 角色实例（架构师/后端/前端等） | worker, bot, 机器人 |
| Agent Pool | 管理所有 Agent 实例生命周期 | 线程池, 进程池 |
| Contract | 接口契约，前后端/模块间 API 定义 | interface, 接口文档 |
| Approval Gate | 需要人工审批才能继续的检查点 | 审批节点 |
| State Machine | WorkUnit 的状态流转机（DRAFT → READY → RUNNING → ...） | 状态机 |
| Event | 系统中发生的一件事，通过 WebSocket 推送到前端 | 消息, 通知 |
| Command | 用户或系统发出的指令（pause/resume/approve/reject） | 指令 |

## 状态定义

### WorkUnit 状态

```
DRAFT → READY → RUNNING → NEEDS_REVIEW → ACCEPTED
                          → NEEDS_REWORK → (回 RUNNING)
                          → FAILED / BLOCKED
```

| 状态 | 含义 | 谁可以转换 |
|------|------|-----------|
| DRAFT | 已创建但未就绪 | PM |
| READY | 可以分配给 Agent | PM |
| RUNNING | Agent 正在执行 | 系统 |
| NEEDS_REVIEW | 执行完成，等待审核 | PM / 用户 |
| ACCEPTED | 审核通过，终态 | 用户 |
| NEEDS_REWORK | 需要返工 | 用户 / Reviewer |
| FAILED | 执行失败 | 系统 |
| BLOCKED | 被阻塞 | 系统 |

### Brainstorm Session 阶段

```
INIT → EXPLORE → REFINE → SPEC_GENERATE → REVIEW → COMPLETE
```

## 命名规范

| 场景 | 规范 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `brainstorm_manager.py` |
| TypeScript 文件 | kebab-case | `work-unit-detail.tsx` |
| API 路由 | kebab-case | `/api/v1/work-units` |
| JSON key | snake_case | `work_unit_id` |
| 数据库表 | snake_case | `brainstorm_sessions` |
| CSS class | kebab-case | `work-unit-card` |
| Git 分支 | kebab-case | `feat/brainstorm-v2` |
```

### 检查点

- [ ] CONTEXT.md 文件创建
- [ ] 所有 Agent prompt 文件头部引用：`> 领域术语定义见 CONTEXT.md`
- [ ] 通知团队此文件生效

---

## 2. ADR 决策记录系统

### 问题

架构决策散落在设计文档、commit message 和对话记录中。新加入的 Agent 或开发者无法快速了解"为什么这么做"。

### 实现

**目录结构：**

```
docs/adr/
├── README.md            ← 索引 + 模板说明
├── ADR-001-agent-workflow.md
├── ADR-002-brainstorm-v2-architecture.md
└── ...
```

**文件模板** `docs/adr/README.md`：

```markdown
# 架构决策记录 (ADR)

## 格式

每个 ADR 文件包含：

```markdown
# ADR-NNN: 标题

- **日期：** YYYY-MM-DD
- **状态：** [提议中 | 已接受 | 已废弃 | 已替代]
- **提出人：** [角色]

## 背景

为什么需要这个决策？

## 方案

选择了什么方案？

## 被否决的方案

| 方案 | 否决理由 |
|------|---------|

## 影响

正面影响和负面影响。
```

## 索引

| ADR | 标题 | 状态 | 日期 |
|-----|------|------|------|
| 001 | 待创建 | - | - |
```

### 实施步骤

1. 创建 `docs/adr/README.md`（索引+模板）
2. 将已有的关键架构决策迁移为 ADR 文件（从设计文档中提取）

**首批待迁移的决策（必须至少有 1 个 ADR）：**

**ADR-001: Agent 工作流协议**
- 来源：`CLAUDE.md` + `docs/AGENTS.md`
- 内容：Agent 执行步骤（读取任务→理解上下文→实现→验证→报告）
- 核心决策理由：确保多个 Agent 按一致流程执行

**ADR-002: WorkUnit 状态机设计**
- 来源：`ralph/state_machine.py`
- 内容：DRAFT → READY → RUNNING → NEEDS_REVIEW → ACCEPTED 链
- 核心决策理由：每个状态必须有明确的拥有者和转换条件

**ADR-003: Brainstorm V2 架构**
- 来源：`docs/ralph/brainstorm-v2-design.zh.md`
- 内容：为何从 V1 升级到 V2，V2 的状态机设计
- 核心决策理由：V1 缺少独立审查环节

### 代码改动

仅新建文件，不修改现有代码。

### 检查点

- [ ] `docs/adr/README.md` 创建
- [ ] 至少 1 个 ADR 文件已完成
- [ ] Agent prompt 中引用："架构决策记录见 docs/adr/"

---

## 3. Caveman 紧凑输出模式

### 问题

Agent 对话中存在大量客套话、重复解释、格式化输出，浪费 token。
参照 Matt Pocock 的 caveman 模式，可节省约 75% 的通信 token。

### 实现

**修改文件：** `prompts/project_manager.md` 等所有 Agent prompt 文件

**在每个 prompt 文件末尾追加以下代码块（中文版）：**

```markdown
## 紧凑模式（默认启用）

按以下规则约束输出：

1. **去掉所有客套话**：不打招呼、不道歉、不表忠心、不总结
2. **一句话原则**：能一句话说清的事绝对不说两句
3. **去掉填充词**：不用"首先/其次/然后/总的来说/值得注意的是/简单来说"
4. **去掉冠词和修饰词**：中文的"的/了/吗/呢"，英文的 the/a/an
5. **用符号代替文字**：用 → 代替"接下来"，用 ✓ 代替"已完成"，用 ✗ 代替"失败"
6. **特殊情况才出声**：只有成功、失败、需要决策时才主动报告；正常执行中保持沉默
7. **拒绝凑行数**：输出结构优先用单行，不强行分段

### 示例对比

❌ 冗余模式：
"好的，我现在开始分析这个需求。首先，让我查看一下相关的文件。然后，我会根据分析结果来制定计划。值得注意的是，这个过程可能需要一些时间。总的来说，我会尽快完成。首先让我们从 PRD 开始分析..."

✅ 紧凑模式：
分析需求中。读取 PRD... 找到 3 个 Feature。依赖关系：feat-2 → feat-1。
从 feat-1 开始。
```

### 注意事项

- 紧凑模式是**默认模式**，Agent 不需要征求用户同意
- 用户通过 `/caveman off` 可以关闭紧凑模式（恢复到正常输出风格）
- 这个开关需要在 `state_models.py` 中新增一个字段

**state_models.py 改动：**

在对话状态模型中加入 compact_mode 标志：

```python
@dataclass
class ConversationState:
    """对话状态"""
    # ... 现有字段 ...
    compact_mode: bool = True  # 默认开启紧凑模式
```

**command_handler.py 改动：**

在命令分发中增加 `/caveman` 命令处理：

```python
COMMAND_MAP = {
    # ... 现有命令 ...
    "/caveman": {
        "on": lambda: set_compact_mode(True),
        "off": lambda: set_compact_mode(False),
    }
}
```

### 检查点

- [ ] 每个 prompt 文件追加了紧凑模式约束
- [ ] state_models.py 新增 compact_mode 字段
- [ ] command_handler.py 支持 /caveman on|off
- [ ] 验证：PM 对话输出明显变短

---

## 4. 大文件渐进披露拆分

### 问题

核心痛点文件：

| 文件 | 行数 | 问题 |
|------|------|------|
| `ralph/brainstorm_manager.py` | ~42,000 | 一个文件包含状态机、LLM 调用、数据持久化、事件发送 |
| `ralph/work_unit_engine.py` | ~29,000 | 工作单元引擎与所有子逻辑耦合 |
| `ralph/command_handler.py` | ~34,000 | 命令处理逻辑全部集中 |
| `dashboard-ui/app/ralph/page.tsx` | ~17,000 | 大盘页面组件 |
| `dashboard-ui/components/ralph/work-unit-detail.tsx` | ~23,000 | 组件过大 |
| `dashboard/api/routes.py` | ~2,955 | 路由文件过长 |

### 原则

参照 Matt 的 L1/L2/L3 分层哲学：

| 层级 | 内容 | 加载时机 | 目标大小 |
|------|------|---------|---------|
| L1 入口 | 类定义、方法签名、import | 始终加载 | <300 行 |
| L2 实现 | 核心业务逻辑 | 按模块按需导入 | <800 行/模块 |
| L3 参考 | 复杂算法、数据表、配置常量 | 按方法调用触发 | <500 行/文件 |

### 4.1 brainstorm_manager.py 拆分方案

**当前：** 42,000 行单体

**目标结构：**

```
ralph/brainstorm/
├── __init__.py              ← L1: 导出 BrainstormManager 类, ~50 行
├── manager.py               ← L1: BrainstormManager 类定义 + 方法调度, ~300 行
├── session.py               ← L2: 会话生命周期（创建/加载/保存）, ~500 行
├── state_machine.py         ← L2: 阶段状态机（INIT→EXPLORE→...）, ~400 行
├── llm_gateway.py           ← L2: LLM 调用封装（生成问题/分析回复）, ~600 行
├── spec_generator.py        ← L2: 规格文档生成逻辑, ~500 行
├── review.py                ← L2: 独立审查逻辑, ~500 行
├── migration.py             ← L2: V1→V2 迁移逻辑, ~300 行
└── constants.py             ← L3: prompt 模板、配置常量, ~200 行
```

**具体实现：**

**`brainstorm/__init__.py`：**

```python
"""Brainstorm V2 需求探索模块。"""
from .manager import BrainstormManager

__all__ = ["BrainstormManager"]
```

**`brainstorm/manager.py`：**

```python
"""BrainstormManager 入口类。方法签名分发到子模块。"""
from __future__ import annotations

from .session import SessionManager
from .state_machine import BrainstormStateMachine
from .llm_gateway import LLMGateway
from .spec_generator import SpecGenerator
from .review import IndependentReview

class BrainstormManager:
    """Brainstorm 会话管理器。"""

    def __init__(self, ...):
        self.session = SessionManager(...)
        self.state_machine = BrainstormStateMachine(...)
        self.llm = LLMGateway(...)
        self.spec = SpecGenerator(...)
        self.review = IndependentReview(...)

    def start_session(self, project_id, mode="v2"):
        return self.session.create(project_id, mode)

    def respond(self, session_id, message):
        session = self.session.load(session_id)
        phase = self.state_machine.current(session)
        if phase == Phase.EXPLORE:
            return self.llm.generate_questions(session, message)
        elif phase == Phase.SPEC_GENERATE:
            return self.spec.generate(session)
        ...

    def trigger_review(self, session_id):
        session = self.session.load(session_id)
        return self.review.analyze(session)
```

> 关键规则：现有 `BrainstormManager` 类的所有**公有方法签名**保持不变。调用方不需要知道重构。

### 4.2 work_unit_engine.py 拆分方案

**当前：** ~29,000 行，职责混合（状态管理 + Agent 分配 + 执行 + 超时 + 审计）

**目标结构：**

```
ralph/work_unit/
├── __init__.py      ← 导出 WorkUnitEngine
├── engine.py        ← L1: 主类 + 方法分发
├── executor.py      ← L2: Agent 执行逻辑
├── scheduler.py     ← L2: 调度/排队/并发控制
└── audit.py         ← L2: 执行日志/审计追踪
```

### 4.3 前端大组件拆分

**`work-unit-detail.tsx`（23,000 行）：**

拆分为：

```
components/ralph/work-unit/
├── index.tsx                 ← L1: 主容器组件
├── status-header.tsx         ← L2: 状态头/进度条
├── evidence-viewer.tsx       ← L2: 证据查看器（已有但内联）
├── approval-panel.tsx        ← L2: 审批面板
├── execution-log.tsx         ← L2: 执行日志
├── agent-selector.tsx        ← L2: Agent 选择器
└── blocker-dialog.tsx        ← L2: 阻塞问题弹窗
```

### 实施顺序

| 优先级 | 文件 | 风险 | 建议策略 |
|--------|------|------|---------|
| P0 | brainstorm_manager.py | 高 | 新建目录，逐步迁移，每个方法做一次 git mv |
| P1 | work_unit_engine.py | 高 | 同上策略 |
| P2 | command_handler.py | 中 | 按命令类别拆分文件 |
| P3 | 前端大组件 | 低 | 顺序拆分，每拆一个验证一次 |

### 大文件拆分通用步骤

```bash
# Step 1: 创建目标目录
mkdir -p ralph/brainstorm/

# Step 2: 用 git mv 移动方法到子模块（保持 git 历史）
# 先在子模块中实现方法，然后在原文件中 import 并代理

# Step 3: 每移动 3-5 个方法后运行完整测试
uv run pytest tests/ -x

# Step 4: 验证 import 链
uv run python -c "from ralph.brainstorm import BrainstormManager; print('OK')"

# Step 5: 重复 Step 2-4 直到原文件只剩入口类
```

### 禁止行为

- ❌ 不允许一次性重构整个文件（风险太高）
- ❌ 不允许修改方法签名或行为
- ❌ 不允许在拆分过程中优化代码逻辑
- ✅ 严格保持行为一致，只改变文件组织

### 检查点

- [ ] brainstorm_manager.py 拆分为 brainstorm/ 包
- [ ] 拆分后所有测试通过（`uv run pytest tests/ -x`）
- [ ] 旧导入路径兼容（创建 `brainstorm_manager.py` 的 shim：`from ralph.brainstorm import BrainstormManager`）
- [ ] 行数确认：拆分后最大文件 < 1,000 行

---

## 5. .out-of-scope 拒绝记录

### 问题

features.json 只记录待办和已完成功能，不记录被拒绝的需求和理由。
导致同一需求可能被多次提出，浪费讨论时间。

### 实现

**目录结构：**

```
.ralph/out-of-scope/
├── README.md
├── 2026-05-01_支持-GitLab-作为代码仓库.md
└── ...
```

**README.md 内容：**

```markdown
# 范围外需求记录

> 此目录记录被拒绝或推迟的需求及拒绝理由。
> 在提出新需求前，先检查是否已被拒绝过。

## 格式

文件名：`YYYY-MM-DD_标题.md`

内容：
```markdown
# 需求标题

- **提出日期：** YYYY-MM-DD
- **拒绝日期：** YYYY-MM-DD
- **提出人：** [谁提的]
- **拒绝人：** [谁否的]
- **状态：** [已拒绝 | 已推迟]

## 需求描述

一句话说明想要什么。

## 拒绝理由

为什么不做。客观、具体。

## 替代方案

如果有更好的解决方案，写在这里。
```
```

### 代码改动

在 PM 的 prompt 文件末尾追加：

```markdown
## 范围外管理

当用户提出一个明确被拒绝过的需求时，先引用 `.ralph/out-of-scope/` 中的记录说明理由。
如果是一个全新的被否决需求，在 `.ralph/out-of-scope/` 中创建记录。
```

### 检查点

- [ ] `.ralph/out-of-scope/README.md` 创建
- [ ] PM prompt 追加范围外管理指令

---

## 6. 子会话隔离执行

### 问题

当前多 Agent 执行时，每个 Agent 的执行过程（LLM 来回、中间思考、失败重试）都在主会话中进行，消耗主会话上下文窗口，且 Agent 间的上下文相互污染。

### 原理

参照 Matt 的"上下文分叉"模式：

```
主会话（L1 调度层）        子会话（L2 执行层）
    │                           │
    ├── 分发 WorkUnit ──────→  ├── Agent 执行
    │                           │   ├── 读文件
    │                           │   ├── 写代码
    │ ←── 结果摘要 ────────│   ├── 运行测试
    │                           │   └── 输出报告
    ├── 分发 WorkUnit ──────→  │
    │ ←── 结果摘要 ────────│
    │                           │
```

### 实现

**修改文件：** `ralph/parallel_executor.py` + `ralph/work_unit_engine.py`

**核心接口设计：**

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SubSessionResult:
    """子会话执行结果。只有摘要回到主会话。"""
    work_unit_id: str
    success: bool
    summary: str  # 执行摘要（<500 chars），不回传完整日志
    files_changed: list[str]
    test_passed: bool
    error: str | None = None
    artifacts_path: str | None = None  # 完整日志的外部路径

class SubSessionExecutor:
    """子会话执行器。每个 WorkUnit 在隔离会话中执行。"""

    def __init__(self, session_dir: str):
        self.session_dir = session_dir

    def execute(
        self,
        work_unit_id: str,
        agent_role: str,
        context: dict[str, Any],
        timeout_minutes: int = 30,
    ) -> SubSessionResult:
        """在隔离子会话中执行一个 WorkUnit。

        实现方式（两种方案选一）：
        
        方案 A（推荐）：在同一进程中创建独立的 LLM 调用链
        - 创建一个新的对话上下文（空 message list）
        - 注入 agent prompt + work unit context
        - 执行 LLM 循环（thinking + tool use）
        - 收集结果，生成摘要
        - 销毁子会话上下文
        
        方案 B：启动子进程
        - 用 subprocess 启动新的 CLI 实例
        - 通过 CLI 参数传递 context
        - 通过 stdout JSON 获取结果
        """
        # TODO: 具体实现
        raise NotImplementedError

    def cleanup(self):
        """清理所有已完成子会话的临时数据"""
        pass
```

**集成到 WorkUnitEngine：**

```python
class WorkUnitEngine:
    def __init__(self, ..., sub_session: bool = False):
        self.sub_session = sub_session
        if sub_session:
            self.sub_executor = SubSessionExecutor(session_dir=".ralph/sub_sessions/")

    async def execute_work_unit(self, work_unit_id: str) -> WorkUnitResult:
        if self.sub_session:
            # 隔离执行
            result = self.sub_executor.execute(
                work_unit_id=work_unit_id,
                agent_role=self._get_agent_role(work_unit_id),
                context=self._build_context(work_unit_id),
            )
            # 只回填摘要到主会话
            return WorkUnitResult(
                work_unit_id=work_unit_id,
                success=result.success,
                summary=result.summary,
                files_changed=result.files_changed,
            )
        else:
            # 当前的内联执行方式（保持向后兼容）
            return await self._execute_inline(work_unit_id)
```

### 配置开关

在 `agent-definitions.json` 或 `toolchain.json` 中加入：

```json
{
  "execution": {
    "sub_session": {
      "enabled": false,
      "timeout_minutes": 30,
      "max_concurrent": 3
    }
  }
}
```

默认关闭，通过配置中心开启。

### 风险与防范

| 风险 | 防范措施 |
|------|---------|
| 子会话状态丢失 | 每个子会话的完整日志写入 `.ralph/sub_sessions/{work_unit_id}/` |
| 超时 | 硬超时 30 分钟，超时后标记为 FAILED |
| 文件冲突 | 子会话通过 git worktree 隔离文件系统 |
| 调试困难 | 保留完整日志路径在 SubSessionResult.artifacts_path |

### 检查点

- [ ] SubSessionExecutor 接口定义
- [ ] WorkUnitEngine 集成（配置开关控制）
- [ ] 子会话上下文隔离验证
- [ ] 主会话 token 消耗降低 >= 30%

---

## 汇总实施路线图

### Phase 1：零成本高收益（1-2 天）

```
Day 1:
  ├── 创建 CONTEXT.md
  ├── 创建 docs/adr/README.md + ADR-001
  └── 所有 prompt 追加紧凑模式约束

Day 2:
  ├── state_models.py + command_handler.py 的 /caveman 开关
  ├── 创建 .ralph/out-of-scope/README.md
  └── PM prompt 追加范围外管理指令
```

### Phase 2：大文件拆分（3-5 天，高收益高风险）

```
Day 3-5:
  ├── brainstorm_manager.py → ralph/brainstorm/ 包拆分
  │   每步验证：git mv → 测试 → 确认
  ├── work_unit_engine.py → ralph/work_unit/ 包
  └── 前端大组件拆分
```

### Phase 3：子会话隔离（2-3 天，基建级改造）

```
Day 6-8:
  ├── SubSessionExecutor 实现
  ├── WorkUnitEngine 集成
  ├── 配置开关 + 超时机制
  └── 全量回归测试
```

---

## 验收标准总表

| 项目 | 验收标准 |
|------|---------|
| CONTEXT.md | 所有新 Agent 启动时在 prompt 头部引用 |
| ADR | 新增架构决策必须在 2 天内写 ADR |
| Caveman 模式 | PM 对话 token 数降低 >= 50%（可量化对比） |
| 大文件拆分 | 拆分后最大 Python 文件 <= 1,000 行 |
| Out-of-scope | 拒绝的需求在 `.ralph/out-of-scope/` 有记录 |
| 子会话 | 主会话 token 消耗降低 >= 30% |
