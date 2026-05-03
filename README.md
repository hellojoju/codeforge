<div align="center">

# 🏗️ AI Dev Platform · AI 全自动开发平台

**人类当甲方，AI 干所有活**  
*Humans as clients, AI does all the work*

---

[![GitHub stars](https://img.shields.io/badge/dynamic/json?logo=github&label=Stars&style=flat-square&color=%23FF6B35&query=%24.stars&url=https%3A%2F%2Fapi.star-history.com%2Fv1%2Fstars%3Fowner%3Djieson%26repo%3Dauto-coding)](https://github.com/jieson/auto-coding/stargazers)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white&style=flat-square)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![Ralph Engine](https://img.shields.io/badge/Ralph-Orchestrator-8B5CF6?style=flat-square)](#-ralph-engine)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

</div>

---

## 👋 这是什么？

> 说人话：**你说需求，AI 写代码、跑测试、修 Bug，你只管点头或摇头。**

AI Dev Platform 是一个端到端的 AI 驱动软件开发平台。你只需要用自然语言描述想要什么，系统就会：

1. 🧠 **多轮追问**你的需求，直到理解透彻
2. 👨‍💻 **派出 AI 工程师团队**（架构师、后端、前端、QA、安全……）并行干活
3. 🔍 **自动审查代码**，发现问题直接返工
4. ✅ **等你审批**，点头才合并
5. 📊 **实时看板**让你全程围观 AI 干活

不再是你写代码让 AI 补全，而是 **AI 写代码，你当甲方**。

---

## ✨ 能做什么？

| 场景 | 以前 | 现在 |
|------|------|------|
| **新项目启动** | 写 PRD → 设计架构 → 搭脚手架 → 编码……折腾几周 | 说一句话，AI 自动产出 PRD + 架构 + 完整代码 |
| **加个功能** | 理解代码库 → 设计实现 → 写代码 → 测试 → 部署 | 说"加个XX功能"，AI 完成全链路 |
| **修 Bug** | 复现 → 定位根因 → 修 → 验证 | AI 自动排查、修复、验证 |
| **Code Review** | 等人 Review → 反复修改 | AI 安全审查 + 代码质量检查并行完成 |
| **多角色协作** | 前端等后端接口、后端等数据库设计，互相阻塞 | 9 个 AI 角色并行工作，接口契约驱动 |

---

## 🖼️ 看看效果

| 概览仪表盘 | 工作单元列表 |
|:---:|:---:|
| ![概览](docs/ralph-overview.png) | ![工作单元](docs/ralph-work-units.png) |

| 审批中心 | 系统设置 |
|:---:|:---:|
| ![审批中心](docs/ralph-approvals.png) | ![设置](docs/ralph-settings.png) |

---

## 🚀 3 步上手

### 前置条件

- Python 3.12+
- Node.js 20+
- 一个 [Anthropic API Key](https://console.anthropic.com)

### 1️⃣ 启动后端

```bash
# 安装依赖
uv sync

# 启动 Dashboard 服务
uv run python cli.py dashboard --port 18753
```

### 2️⃣ 启动前端

```bash
cd dashboard-ui
npm install
npm run dev
```

### 3️⃣ 打开浏览器

访问 [http://localhost:3000](http://localhost:3000) —— 看到 Ralph Console 就说明跑起来了。

或者直接用 CLI 模式：

```bash
# 初始化项目（会多轮追问需求）
uv run python cli.py init

# 跑起来
uv run python cli.py run

# 看状态
uv run python cli.py status
```

---

## 🏛️ 架构一览

```
┌─────────────────────────────────────────────────────┐
│                   你（人类甲方）                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  CLI/Term │  │ Dashboard│  │ 审批闸门 (Approve)│   │
│  └─────┬────┘  └─────┬────┘  └────────┬─────────┘   │
└────────┼──────────────┼───────────────┼──────────────┘
         ▼              ▼               ▼
┌─────────────────────────────────────────────────────┐
│                  PMCoordinator                        │
│        审批/驳回/暂停/恢复  执行编排                     │
└───────────┬─────────────────────────────┬───────────┘
            │                             │
            ▼                             ▼
┌────────────────────┐   ┌────────────────────────────┐
│   BrainstormManager│──▶│  Feature Tracker           │
│   (多轮需求探索)     │   │  (功能拆解 + 优先级排序)    │
└────────────────────┘   └────────────┬───────────────┘
                                      │
            ┌─────────────────────────┼──────────────┐
            ▼                         ▼              ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Agent Pool      │  │   Agent Pool     │  │   Agent Pool     │
│   🏗️ 架构师      │  │  👨‍💻 后端开发    │  │  🎨 前端开发     │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│   🔐 安全工程师  │  │  🗄️ 数据库专家  │  │  🧪 QA 测试     │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│   📖 文档工程师  │  │  🎭 UI 设计师   │  │  📋 产品经理    │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────┐
│                    Ralph Engine                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ State    │  │ Repository│  │ WorkUnit Engine   │    │
│  │ Machine  │  │ (原子写入) │  │ (状态机 + 证据)  │    │
│  └──────────┘  └──────────┘  └──────────────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ Evidence │  │ Blocker  │  │ Transition Log    │    │
│  │ Collector│  │ Tracker  │  │ (全审计追踪)      │    │
│  └──────────┘  └──────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### 数据流

```
需求输入 → 多轮追问 → PRD生成 → 功能拆解 → 并行派发
  ↓
Agent执行 → 证据收集 → 自动审查 → 等待审批
  ↓
通过 → 验收测试 → 代码合并 → Git提交
驳回 → 退回重做
```

---

## 🧠 Ralph Engine

Ralph 是这个项目的核心编排引擎，名字来源于"Random Autonomous Leader for Programming Help"。它负责：

### WorkUnit 状态机

```
DRAFT ──▶ READY ──▶ RUNNING ──▶ NEEDS_REVIEW ──▶ ACCEPTED (终态)
                │                │                    ▲
                │                ├──▶ NEEDS_REWORK ───┘
                │                │
                ▼                ▼
             BLOCKED ←──────── FAILED
```

- 每个状态转换都有**角色权限校验**
- 所有转换记录 JSONL **审计日志**
- 支持**强制覆盖**（管理员模式）

### 9 个 AI 角色

| 角色 | 职责 | 并发上限 |
|------|------|---------|
| 🏗️ 架构师 | 系统设计、技术选型 | 1 |
| 👨‍💻 后端开发 | API、业务逻辑 | 3 |
| 🎨 前端开发 | UI、交互 | 3 |
| 🗄️ 数据库专家 | Schema、迁移、优化 | 1 |
| 🧪 QA 测试 | 自动化测试、边界测试 | 1 |
| 🔐 安全工程师 | 安全审查、漏洞扫描 | 1 |
| 🎭 UI 设计师 | 组件设计、视觉风格 | 1 |
| 📖 文档工程师 | 文档、API 参考 | 1 |
| 📋 产品经理 | 需求澄清、PRD 编写 | 1 |

---

## 📋 功能全景

### Ralph Runtime Console (前端)

| 模块 | 页面 | 功能 |
|------|------|------|
| **仪表盘** | `/ralph` | 统计卡片、WorkUnit 列表、系统状态 |
| **执行** | `/ralph/work-units` | 搜索/排序/筛选/分页 WorkUnit 列表 |
| | `/ralph/[id]` | 详情页 + 锚点导航 + 操作栏 |
| | `/ralph/pipeline` | 执行管道可视化 |
| | `/ralph/scheduling` | 调度面板 |
| **工作台** | `/ralph/commands` | 命令中心 |
| | `/ralph/events` | 实时事件流 |
| | `/ralph/approvals` | 审批中心 |
| | `/ralph/reports` | 研发报告 |
| **产品** | `/ralph/brainstorm` | 多轮需求共创聊天 |
| | `/ralph/prd` | PRD 文档管理 |
| | `/ralph/specs` | 规格文档 |
| | `/ralph/contracts` | 接口合同 |
| **系统** | `/ralph/graph` | 依赖关系 DAG |
| | `/ralph/memory` | 记忆系统状态 |
| | `/ralph/settings/*` | 配置中心（Provider、工具链、Issue 策略、Agent） |

### Dashboard 后端 API

| 端点组 | 数量 | 说明 |
|--------|------|------|
| `GET /api/ralph/*` | 11 | Ralph 只读 API（WorkUnit、Evidence、Review、Blocker） |
| `POST /api/ralph/*` | 3 | Ralph 命令 API |
| `GET /api/dashboard/*` | 6 | Dashboard 状态、模块、审批 |
| `POST /api/*` | 10 | 控制命令（approve/reject/pause/resume/retry/skip） |
| `GET /api/agents/*` | 4 | Agent 管理和状态 |
| `POST /api/execution/*` | 3 | 执行控制（start/stop/status） |
| `WebSocket /ws/dashboard` | 1 | 实时推送 |

---

## 🛡️ 安全性

- **路径遍历防护** — Evidence 文件读取多层校验
- **敏感信息 redaction** — API Key、密码、Token 自动脱敏
- **文件锁冲突检测** — 多 Agent 并发写文件防冲突
- **审批闸门** — 关键操作必须人工确认
- **CORS 配置** — 开发期宽松，生产期可收紧

---

## 🧪 测试

```
后端 Python:  94 passed,  0 failed  (pytest)
前端 Vitest: 374 passed,  1 failed  (Vitest)  
前端 E2E:     80 passed, 18 failed  (Playwright)
```

> 🚧 测试覆盖率工具正在接入中。

---

## 🛠️ 技术栈

| 层 | 技术 |
|------|--------|
| **运行时** | Python 3.12+ · Node.js 20+ |
| **后端框架** | FastAPI · Uvicorn · Typer |
| **前端框架** | Next.js 16 · React 19 · TypeScript 5 |
| **UI 组件** | Tailwind CSS v4 · shadcn/ui · Lucide Icons |
| **状态管理** | Zustand 5 · Event Sourcing |
| **AI 接口** | Anthropic API · MCP Protocol |
| **数据库** | SQLite · JSON 持久化（原子写入） |
| **自动化** | Playwright |
| **包管理** | uv (Python) · npm (前端) |
| **代码质量** | Ruff · ESLint · Vitest · Playwright |

---

## 📦 项目结构

```
auto-coding/
├── cli.py                 # CLI 入口 (Typer + Rich)
├── agents/                # 9 种 AI 角色实现
│   ├── base_agent.py      # Agent 基类
│   ├── pool.py            # Agent 池 + 文件锁
│   └── product_manager.py # PM 角色
├── core/                  # 核心引擎
│   ├── project_manager.py # 项目管理器
│   ├── feature_tracker.py # 功能追踪
│   ├── task_queue.py      # 任务队列
│   └── execution_ledger.py# 执行台账
├── ralph/                 # Ralph 编排引擎
│   ├── repository.py      # 持久化层
│   ├── state_machine.py   # 状态机
│   ├── brainstorm_manager.py # 需求探索
│   └── command_handler.py # 命令处理
├── dashboard/             # FastAPI 后端
│   ├── api/routes.py      # REST + WebSocket
│   ├── coordinator.py     # PM 协同器
│   ├── consumer.py        # 命令消费者
│   └── state_repository.py# 状态仓库
├── dashboard-ui/          # Next.js 前端
│   ├── app/ralph/         # 23 个路由页面
│   ├── lib/               # Store + API + WebSocket
│   └── components/        # UI 组件
└── tests/                 # 测试
```

---

## 🤝 如何贡献

1. Fork 这个项目
2. 创建你的特性分支 (`git checkout -b feature/amazing`)
3. 提交你的改动 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing`)
5. 创建一个 Pull Request

> 我们欢迎任何形式的贡献 —— 提 Issue、修 Bug、加功能、写文档，都行。

---

## 📜 License

[MIT](LICENSE) © 2026

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jieson/auto-coding&type=Date)](https://star-history.com/#jieson/auto-coding&Date)

---

<div align="center">

**如果这个项目对你有帮助，点个 ⭐ 就是最大的支持**

**Built with ❤️ by Claude Code & Human**

</div>
