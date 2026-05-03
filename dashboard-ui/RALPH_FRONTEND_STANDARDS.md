# Ralph Runtime Console 前端开发标准

> 所有子代理必须遵循此标准进行开发

---

## 1. 视觉设计系统

### 1.1 圆角策略（⚠️ 强制）

**核心原则：最小圆角，工业感**

```css
/* 禁止 */
rounded-lg    /* 太圆 */
rounded-xl    /* 太圆 */
rounded-2xl   /* 太圆 */
rounded-full  /* 太圆 */

/* 允许 */
rounded-none  /* 首选 - 直角 */
rounded-sm    /* 0.125rem - 次选 */
```

**组件规范：**
- 卡片/面板：`rounded-none`（直角）
- 按钮：`rounded-sm` 或 `rounded-none`
- 输入框：`rounded-sm`
- 标签/徽章：`rounded-sm` 或 `rounded-none`
- Tab：`rounded-none`（底部边框激活样式）
- 模态框：`rounded-none`

### 1.2 颜色系统

使用 Tailwind CSS 默认调色板，避免自定义颜色：

```typescript
// 状态颜色映射（已封装在 ralph-utils.ts）
statusColor('running')    // → 'text-blue-500'
statusColor('needs_review') // → 'text-yellow-500'
statusColor('blocked')    // → 'text-red-500'
statusColor('accepted')   // → 'text-emerald-500'
statusColor('failed')     // → 'text-red-600'
```

**背景色：**
- 主背景：`bg-background`
- 次级背景：`bg-muted` 或 `bg-muted/20`
- 悬停背景：`hover:bg-muted`

**边框：**
- 默认边框：`border`
- 强调边框：`border-primary`
- 状态边框：`border-green-200`, `border-red-200`

### 1.3 间距系统

```css
/* 页面内边距 */
p-4           /* 16px */

/* 组件间隙 */
gap-2         /* 8px - 紧凑 */
gap-3         /* 12px - 默认 */
gap-4         /* 16px - 宽松 */

/* 区块间距 */
space-y-4     /* 默认区块间距 */
space-y-6     /* 大区块间距 */

/* 组件内边距 */
p-4           /* 卡片默认 */
px-4 py-2     /* 按钮默认 */
px-3 py-1.5   /* 小按钮 */
```

### 1.4 字体排版

```css
/* 标题 */
text-2xl font-bold    /* 页面标题 */
text-xl font-bold     /* 区块标题 */
text-lg font-semibold /* 小标题 */

/* 正文 */
text-sm               /* 默认正文 */
text-xs               /* 辅助文字、元信息 */

/* 等宽字体 */
font-mono text-xs     /* ID、时间戳、代码 */

/* 文字颜色 */
text-foreground       /* 主要文字 */
text-muted-foreground /* 次要文字 */
```

---

## 2. 组件开发标准

### 2.1 文件组织

```
dashboard-ui/
├── app/ralph/              # Ralph 路由页面
│   ├── layout.tsx          # 根布局（Sidebar + Tab）
│   ├── page.tsx            # WorkUnit 列表页
│   ├── [id]/page.tsx       # WorkUnit 详情页
│   └── approvals/page.tsx  # 审批中心
├── components/ralph/       # Ralph 专用组件
│   ├── sidebar.tsx
│   ├── tab-bar.tsx
│   ├── run-status-header.tsx
│   ├── work-unit-list.tsx
│   ├── work-unit-detail.tsx
│   ├── approval-center.tsx
│   └── evidence-viewer.tsx
├── lib/
│   ├── ralph-types.ts      # 类型定义
│   ├── ralph-api.ts        # API 客户端
│   ├── ralph-websocket.ts  # WebSocket
│   ├── ralph-store.ts      # Zustand Store
│   └── ralph-utils.ts      # 工具函数
└── tests/ralph/            # 测试文件
```

### 2.2 组件模板

**新组件必须以此模板开始：**

```typescript
'use client';

import { useRalphStore } from '@/lib/ralph-store';
import { cn } from '@/lib/utils';

interface ComponentNameProps {
  // 明确定义 props
}

export function ComponentName({ ... }: ComponentNameProps) {
  // 1. 从 store 读取状态
  // 2. 定义本地状态
  // 3. 定义事件处理
  
  return (
    <div className="rounded-none border ...">
      {/* 组件内容 */}
    </div>
  );
}
```

### 2.3 样式规范

**必须使用 `cn()` 工具函数合并类名：**

```typescript
import { cn } from '@/lib/utils';

// ✅ 正确
className={cn(
  'flex items-center gap-2 rounded-none border',
  isActive && 'bg-muted',
  isDisabled && 'opacity-50'
)}

// ❌ 错误 - 模板字符串
className={`flex items-center ${isActive ? 'bg-muted' : ''}`}

// ❌ 错误 - 条件类名分散
className={isActive ? 'flex bg-muted' : 'flex'}
```

**状态样式映射：**

```typescript
// 在 ralph-utils.ts 中已定义，直接使用
import { statusColor, statusLabel } from '@/lib/ralph-utils';

<span className={statusColor(workUnit.status)}>
  {statusLabel(workUnit.status)}
</span>
```

### 2.4 图标使用

统一使用 `lucide-react`：

```typescript
import { 
  LayoutDashboard, 
  ListTodo, 
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  X,
  Loader2,
  AlertCircle,
  CheckCircle,
  FileText,
  Code,
  Terminal,
  Image as ImageIcon,
  File,
} from 'lucide-react';

// 使用 size 属性控制大小
<Icon size={16} />  // 小图标
<Icon size={18} />  // 默认
<Icon size={20} />  // 大图标
```

---

## 3. 状态管理标准

### 3.1 Store 使用规范

**读取状态：**

```typescript
const { workUnits, loading, fetchWorkUnits } = useRalphStore();

// 或使用选择器避免重渲染
const workUnits = useRalphStore((state) => state.workUnits);
```

**修改状态：**

```typescript
// ✅ 正确 - 使用 store action
const { addTab, closeTab } = useRalphStore();
addTab({ label: '新标签', type: 'overview', pinned: false });

// ❌ 错误 - 直接修改
useRalphStore.setState({ tabs: [...] });
```

### 3.2 数据获取模式

```typescript
// 1. 页面加载时获取
useEffect(() => {
  fetchWorkUnits();
}, [statusFilter]);

// 2. WebSocket 事件触发更新
useEffect(() => {
  const unsubscribe = ws.on((event) => {
    handleEvent(event);
  });
  return () => unsubscribe();
}, []);
```

---

## 4. API 集成标准

### 4.1 API 调用

**统一使用 ralph-api.ts 封装的方法：**

```typescript
import * as api from '@/lib/ralph-api';

// 获取数据
const units = await api.listWorkUnits('running');
const unit = await api.getWorkUnit('wu-001');

// 创建 Command
await api.createCommand({
  command_type: 'accept_review',
  target_id: 'wu-001',
  reason: '验收通过',
});
```

### 4.2 错误处理

```typescript
try {
  await api.createCommand(params);
  toast.success('操作成功');
} catch (err) {
  toast.error('操作失败');
  console.error('Command creation failed:', err);
}
```

---

## 5. 测试标准

### 5.1 单元测试模板

```typescript
// tests/ralph/component-name.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ComponentName } from '@/components/ralph/component-name';

vi.mock('@/lib/ralph-store', () => ({
  useRalphStore: vi.fn(),
}));

describe('ComponentName', () => {
  it('renders correctly', () => {
    // Arrange
    (useRalphStore as any).mockReturnValue({ ... });
    
    // Act
    render(<ComponentName />);
    
    // Assert
    expect(screen.getByText('expected text')).toBeTruthy();
  });
});
```

### 5.2 E2E 测试

```typescript
// tests/e2e/test_ralph.spec.ts
import { test, expect } from '@playwright/test';

test('feature name', async ({ page }) => {
  await page.goto('/ralph');
  await expect(page.getByText('expected')).toBeVisible();
});
```

---

## 6. 禁止事项

### 6.1 样式禁止

```css
/* ❌ 禁止 - 大圆角 */
rounded-lg, rounded-xl, rounded-2xl, rounded-full

/* ❌ 禁止 - 阴影滥用 */
shadow-lg, shadow-xl

/* ❌ 禁止 - 渐变背景 */
bg-gradient-to-*

/* ❌ 禁止 - 动画过渡滥用 */
transition-all
duration-500+
```

### 6.2 代码禁止

```typescript
// ❌ 禁止 - any 类型
function foo(data: any) { }

// ❌ 禁止 - 空 catch
try { ... } catch { }

// ❌ 禁止 - 直接修改 props
props.value = 'new';

// ❌ 禁止 - 未处理的 Promise
fetchData();  // 不 await 也不 .catch

// ❌ 禁止 - console.log 留在生产代码
console.log('debug');
```

---

## 7. 快速参考

### 常用类名组合

```css
/* 卡片 */
rounded-none border p-4

/* 按钮 */
rounded-sm px-4 py-1.5 text-sm border hover:bg-muted

/* 激活按钮 */
rounded-sm px-4 py-1.5 text-sm bg-primary text-primary-foreground

/* Tab */
rounded-none border-b-2 border-transparent hover:border-muted-foreground
rounded-none border-b-2 border-b-primary  /* 激活 */

/* 输入框 */
rounded-sm border px-3 py-2 text-sm

/* 列表项 */
rounded-none border-b p-3 hover:bg-muted

/* 侧边栏 */
w-60 (展开) / w-16 (收起)
```

### 图标尺寸映射

| 场景 | 尺寸 |
|------|------|
| 导航图标 | 18px |
| 按钮图标 | 14-16px |
| 状态指示 | 16-20px |
| 大图标 | 20-24px |

---

## 8. 验收检查清单

每个组件提交前检查：

- [ ] 没有 `rounded-lg` 或更大的圆角
- [ ] 使用 `cn()` 合并类名
- [ ] Props 有明确类型定义
- [ ] 从 store 读取状态，不直接修改
- [ ] 没有 `console.log`
- [ ] 测试覆盖率 80%+
- [ ] TypeScript 检查通过 (`tsc --noEmit`)
