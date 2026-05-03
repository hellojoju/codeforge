# Ralph Dashboard - 前端页面元素清单

## 一、整体布局架构

### 1.1 根布局 (`app/ralph/layout.tsx`)

| 元素 | 类型 | 说明 |
|------|------|------|
| 外层容器 | flex 容器 | `h-screen w-full overflow-hidden` |
| Sidebar | `<Sidebar />` | 左侧导航栏，可折叠 |
| 主内容区 | flex-col 容器 | `flex-1 flex-col overflow-hidden` |
| TabBar | `<TabBar />` | 浏览器风格标签栏 |
| 页面内容区 | `<main>` | `flex-1 overflow-auto p-4` |
| WebSocket 连接 | RalphWebSocket | 全局实时数据连接 |

### 1.2 首页 (`app/page.tsx`)

| 元素 | 类型 | 说明 |
|------|------|------|
| 重定向逻辑 | useRouter | 自动重定向到 `/ralph` |

---

## 二、概览页 (`app/ralph/page.tsx`)

### 2.1 页面标题

| 元素 | 类型 | 说明 |
|------|------|------|
| 标题文本 | h1 | "Ralph 控制台" |

### 2.2 状态摘要 (StatusSummary)

| 元素 | 类型 | 说明 |
|------|------|------|
| 连接状态 | 状态标签 | 已连接(绿色Wifi图标) / 未连接(灰色WifiOff图标) |
| 统计卡片 - 总计 | 数字卡片 | 大数字 + "总计"标签 |
| 统计卡片 - 运行中 | 数字卡片 | 蓝色大数字 + "运行中"标签 |
| 统计卡片 - 待审批 | 数字卡片 | 琥珀色大数字(有数据时) + Shield图标 + "待审批" |
| 统计卡片 - 阻塞项 | 数字卡片 | 红色大数字(有数据时) + AlertTriangle图标 + "阻塞项" |
| 状态分布 | 标签列表 | 各状态的小圆点 + 中文名 + 数量 |

### 2.3 工作单元列表 (WorkUnitList)

| 元素 | 类型 | 说明 |
|------|------|------|
| 过滤栏 | 按钮组 | "全部" + 各状态按钮(可切换高亮) |
| 加载状态 | 文本 | "加载中..." |
| 空状态 | 文本 | "暂无工作单元" |
| 工作单元卡片 | 可点击卡片 | 每条包含： |
| ├─ work_id | 等宽文本 | 灰色小字 |
| ├─ title | 粗体文本 | 标题 |
| ├─ status | 状态标签 | 带颜色的状态文字 |
| ├─ target | 描述文本 | 截断显示 |
| ├─ work_type | 小字 | 工作类型 |
| ├─ updated_at | 小字 | 更新时间 |
| └─ dependencies | 小字 | 依赖列表(有则显示) |

---

## 三、工作单元详情页 (`app/ralph/[id]/page.tsx`)

### 3.1 页面级元素

| 元素 | 类型 | 说明 |
|------|------|------|
| 返回链接 | Link | "← 返回列表" |
| 加载状态 | Spinner | Loader2旋转 + "加载中..." |
| 错误状态 | 错误提示 | AlertCircle图标 + 错误信息 + 返回链接 |

### 3.2 WorkUnitDetail 组件

| 元素 | 类型 | 说明 |
|------|------|------|
| **头部卡片** | 卡片容器 | |
| ├─ work_id | 等宽小字 | 灰色 |
| ├─ title | h1 大字 | 粗体 |
| ├─ StatusBadge | 状态徽章 | 带颜色的小标签 |
| └─ background | 描述文本 | 灰色小字(有则显示) |
| **目标卡片** | 卡片容器 | |
| ├─ Target图标 + "目标" | 标题 | |
| └─ target | 正文 | |
| **验收标准卡片** | 卡片容器 | (有则显示) |
| ├─ CheckCircle图标 + "验收标准" | 标题 | |
| └─ 标准列表 | 圆点列表 | 每条标准 |
| **范围双栏** | 2列grid | |
| ├─ 允许修改(绿色边框) | 卡片 | CheckCircle图标 + 绿色标题 + 允许列表 |
| └─ 禁止修改(红色边框) | 卡片 | AlertCircle图标 + 红色标题 + 禁止列表 |
| **Context Pack** | 卡片容器 | (有则显示) |
| ├─ Package图标 + "Context Pack" | 标题 | |
| ├─ task_goal | 文本 | |
| ├─ upstream_summary | 灰色文本 | |
| ├─ known_risks | 橙色风险列表 | AlertCircle图标 |
| └─ related_files | 等宽文件列表 | 灰色背景 |
| **Task Harness** | 卡片容器 | (有则显示) |
| ├─ Shield图标 + "Task Harness" | 标题 | |
| ├─ task_goal | 文本 | |
| ├─ reviewer_role + context_budget | 2列并排 | |
| ├─ preflight_checks | 圆点列表 | (有则显示) |
| └─ validation_gates | 圆点列表 | (有则显示) |
| **证据查看器** | EvidenceViewer | 双栏布局(见下方) |
| **审查结果** | ReviewCard列表 | (有则显示，见下方) |
| **状态流转时间线** | 横向时间线 | 状态→状态→状态的箭头链 |
| **元信息** | 4列grid卡片 | |
| ├─ 创建时间 | Clock图标 + 日期 | |
| ├─ 更新时间 | Clock图标 + 日期 | |
| ├─ 执行者 | User图标 + 角色名 | |
| └─ 审查者 | Shield图标 + 角色名 | |

### 3.3 EvidenceViewer 组件

| 元素 | 类型 | 说明 |
|------|------|------|
| 外层容器 | 双栏flex | `h-[500px]`，左1/3右2/3 |
| **左侧：文件列表** | 滚动区域 | |
| ├─ 标题栏 | "证据文件" + N个文件 | |
| ├─ 文件列表项 | 可点击按钮 | 文件类型图标 + 文件名 + 类型标签 + 大小 |
| ├─ 加载状态 | "加载中..." | |
| └─ 错误状态 | 红色错误提示 | |
| **右侧：内容预览** | 滚动区域 | |
| ├─ 标题栏 | 文件名 + 类型标签·大小 | |
| ├─ 图片预览 | img | base64截图，居中显示 |
| ├─ 文本预览 | pre > code | 等宽字体，可滚动 |
| ├─ 加载状态 | "加载中..." | |
| └─ 空状态 | "选择文件查看内容" | |

### 3.4 ReviewCard 组件

| 元素 | 类型 | 说明 |
|------|------|------|
| 标题 | FileText图标 + "审查结果" | |
| 结论徽章 | 通过(绿色) / 不通过(红色) | |
| 审查类型 | 小字 | |
| 验收标准列表 | ✓/✗ + 标准文字 | 绿色✓ / 红色✗ |
| 问题列表 | 黄色边框卡片 | [严重级别] + 描述 + 建议(有则显示) |
| 建议操作 | 小字 | recommended_action(有则显示) |

---

## 四、审批中心页 (`app/ralph/approvals/page.tsx`)

### 4.1 页面级元素

| 元素 | 类型 | 说明 |
|------|------|------|
| 内容容器 | flex-col | `h-full` |

### 4.2 ApprovalCenter 组件

| 元素 | 类型 | 说明 |
|------|------|------|
| **头部栏** | 横栏 | |
| ├─ ShieldCheck图标 + "审批中心" | 标题 | |
| ├─ "待处理: N" | 计数 | |
| └─ "阻塞: N" | 计数 | |
| **待处理审批区** | 滚动区域 | |
| ├─ 区标题 | "待处理审批" | 大写小字 |
| ├─ 空状态 | EmptyState | ShieldCheck图标 + "暂无待处理的审批事项" |
| └─ ApprovalCard列表 | 卡片列表 | 每张包含： |
|   ├─ 类型徽章 | 彩色标签 | 危险操作/范围扩展/审查争议/缺失依赖/执行错误/人工干预 |
|   ├─ 时间 | Clock图标 + 相对时间 | |
|   ├─ 描述 | 正文 | action.description |
|   ├─ work_id | 等宽小字 | |
|   ├─ 批准按钮 | 绿色Button | "批准" / "处理中..." |
|   └─ 拒绝按钮 | 红色outline Button | "拒绝" / "处理中..." |
| **阻塞项区** | 滚动区域 | (有未解决阻塞项时显示) |
| ├─ 区标题 | "阻塞项" | 大写小字 |
| └─ BlockerCard列表 | 灰色卡片列表 | 每张包含： |
|   ├─ 类别徽章 | 彩色标签 | 权限/范围/配置/依赖/资源 |
|   ├─ 时间 | Clock图标 + 相对时间 | |
|   ├─ 原因 | 正文 | blocker.reason |
|   └─ work_id | 等宽小字 | |

---

## 五、侧边栏 (`components/ralph/sidebar.tsx`)

| 元素 | 类型 | 说明 |
|------|------|------|
| 外层容器 | aside | 可折叠 `w-60` / `w-16` |
| **头部区** | 横栏 | |
| └─ 折叠按钮 | 按钮 | ChevronLeft / ChevronRight 图标 |
| **导航区** | nav > ul | |
| ├─ 概览 | 按钮 | LayoutDashboard图标 + "概览" |
| ├─ 工作单元 | 按钮 | ListTodo图标 + "工作单元" |
| └─ 审批中心 | 按钮 | ShieldCheck图标 + "审批中心" + 红色待审批角标 |
| **底部区** | footer | |
| └─ 运行状态 | 绿色圆点 + "运行中"(展开时) | |

---

## 六、标签栏 (`components/ralph/tab-bar.tsx`)

| 元素 | 类型 | 说明 |
|------|------|------|
| 外层容器 | flex 横栏 | `h-10` |
| **Tab列表** | 可滚动区域 | |
| └─ TabItem | 可点击标签 | |
|   ├─ 状态圆点 | 彩色小圆点 | work_unit类型tab的状态色 |
|   ├─ 标签文字 | 截断文本 | 最大12字符 |
|   ├─ 关闭按钮 | X图标 | hover显示(非固定标签) |
|   └─ 固定指示器 | 小方块 | 固定标签的标记 |
| **添加按钮** | Plus图标 | 最多8个tab，超限时禁用 |

---

## 七、RunStatusHeader (`components/ralph/run-status-header.tsx`)

> 当前未在页面中直接使用，但代码中存在

| 元素 | 类型 | 说明 |
|------|------|------|
| 连接状态指示器 | 绿色/红色圆点 + 文字 | "已连接" / "未连接" |
| 状态计数列表 | 横排 | running/needs_review/blocked/accepted/failed |
| 下一步行动建议 | 文字 | "下一步: xxx" |
| 刷新按钮 | outline Button | RefreshCw图标，加载中时旋转 |

---

## 八、UI 组件库 (shadcn)

| 组件 | 用途 |
|------|------|
| Button | 所有按钮(批准/拒绝/刷新/导航) |
| Card | 卡片容器(未直接使用shadcn Card，手动实现) |
| Badge | 状态标签(手动实现，未用shadcn Badge) |
| Input | 暂未使用 |
| Tabs | 暂未使用(shadcn Tabs，当前TabBar是自定义) |
| Avatar | 暂未使用 |
| Progress | 暂未使用 |
| Separator | 暂未使用 |
| ScrollArea | 暂未使用 |
| Sonner | Toast通知(审批操作的成功/失败提示) |

---

## 九、状态系统

### 9.1 工作单元状态

| 状态 | 中文名 | 颜色 |
|------|--------|------|
| ready | 就绪 | 灰色 |
| running | 运行中 | 蓝色 |
| needs_review | 待审查 | 紫色 |
| accepted | 已接受 | 绿色 |
| needs_rework | 需返工 | 橙色 |
| blocked | 已阻塞 | 黄色 |
| failed | 已失败 | 红色 |

### 9.2 审批类型

| 类型 | 中文名 | 颜色 |
|------|--------|------|
| dangerous_op | 危险操作 | 红色 |
| scope_expansion | 范围扩展 | 琥珀色 |
| review_dispute | 审查争议 | 紫色 |
| missing_dep | 缺失依赖 | 蓝色 |
| execution_error | 执行错误 | 橙色 |
| manual_intervention | 人工干预 | 灰色 |

### 9.3 阻塞项类别

| 类别 | 中文名 | 颜色 |
|------|--------|------|
| permission | 权限 | 红色 |
| scope | 范围 | 琥珀色 |
| harness | 配置 | 紫色 |
| dependency | 依赖 | 蓝色 |
| resource | 资源 | 灰色 |

### 9.4 证据文件类型

| 类型 | 中文名 | 图标 |
|------|--------|------|
| diff | 代码差异 | Code |
| test_output | 测试结果 | Terminal |
| lint | 代码检查 | Terminal |
| screenshot | 截图 | Image |
| log | 日志 | FileText |
| other | 其他 | File |
