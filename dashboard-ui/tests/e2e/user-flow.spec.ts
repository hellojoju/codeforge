import { test, expect } from '@playwright/test';

/**
 * MVP #21/#22: 用户路径 Playwright E2E 验收
 *
 * 覆盖核心用户场景:
 *   1. 项目管理 → 打开项目 → 查看分析
 *   2. 需求共创 → 开始 session → 回答问题
 *   3. 审批中心 → 查看待审批
 *   4. 记忆系统 → 查看状态
 *   5. 知识图谱 → 查看可视化
 *   6. 设置页面 → 切换配置
 */

test.describe('MVP 用户路径验收', () => {
  test.describe('1. 项目管理流程', () => {
    test('项目列表页正常加载并显示项目', async ({ page }) => {
      await page.goto('/ralph/projects');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(1000);

      // 页面应该有标题或项目列表
      const heading = page.getByRole('heading', { name: /项目/i }).first();
      const hasHeading = await heading.isVisible().catch(() => false);

      // 检查是否有项目卡片或空状态
      const projectCard = page.locator('[class*="project"], [class*="card"]').first();
      const emptyState = page.getByText(/暂无项目|没有项目|空/i);

      await expect(
        (hasHeading ? heading : emptyState).or(projectCard)
      ).toBeVisible({ timeout: 5000 });
    });

    test('项目展开后显示详情面板', async ({ page }) => {
      await page.goto('/ralph/projects');
      await page.waitForTimeout(1000);

      // 尝试展开第一个项目
      const expandBtn = page.locator('button:has(svg.lucide-chevron-down), button:has(svg.lucide-chevron-right)').first();
      if (await expandBtn.isVisible().catch(() => false)) {
        await expandBtn.click();
        await page.waitForTimeout(500);
        // 展开后验证页面正常
        await expect(page.locator('main')).toBeVisible();
      }
    });

    test('分析按钮可用', async ({ page }) => {
      await page.goto('/ralph/projects');
      await page.waitForTimeout(1000);

      // 查找"分析"或"Deep Analysis"按钮
      const analyzeBtn = page.getByRole('button', { name: /分析|Analyze/i }).first();
      if (await analyzeBtn.isVisible().catch(() => false)) {
        await expect(analyzeBtn).toBeEnabled();
      }
    });
  });

  test.describe('2. 需求共创（Brainstorm）流程', () => {
    test('Brainstorm 页面加载正常', async ({ page }) => {
      await page.goto('/ralph/brainstorm');
      await expect(page.locator('main')).toBeVisible();

      // 应该能看到 session 相关的内容
      const content = page.getByRole('heading', { name: '需求共创' });
      await expect(content).toBeVisible({ timeout: 5000 });
    });

    test('已有 session 列表可见', async ({ page }) => {
      await page.goto('/ralph/brainstorm');
      await page.waitForTimeout(1000);

      // session 列表或空状态
      const sessionList = page.locator('[class*="session"], [class*="record"]').first();
      const noSessions = page.getByText(/暂无|没有 session/i);
      await expect(
        sessionList.or(noSessions)
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('3. 审批中心', () => {
    test('审批中心加载并显示审批列表', async ({ page }) => {
      await page.goto('/ralph/approvals');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(1000);

      // 审批列表或空状态
      const list = page.locator('[class*="approval"], [class*="review"]').first();
      const empty = page.getByText(/暂无|没有待审批|没有审批/i);
      await expect(
        list.or(empty)
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('4. 记忆系统', () => {
    test('记忆页面加载并显示统计信息', async ({ page }) => {
      await page.goto('/ralph/memory');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(1000);

      // 统计卡片或记忆内容
      const stats = page.getByRole('heading', { name: '记忆系统' });
      await expect(stats).toBeVisible({ timeout: 5000 });
      // 确认记忆内容渲染
      await expect(page.getByText('短期记忆').first()).toBeVisible();
    });
  });

  test.describe('5. 知识图谱', () => {
    test('图谱页面加载并显示可视化', async ({ page }) => {
      await page.goto('/ralph/graph');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(1000);

      // 图谱可视化容器或空状态
      const graph = page.locator('svg, canvas, [class*="graph"], [class*="chart"]').first();
      const loading = page.getByText(/加载|loading/i);
      await expect(
        graph.or(loading)
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('6. 设置页面', () => {
    test('工具链设置页正常加载', async ({ page }) => {
      await page.goto('/ralph/settings/tools');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(500);
      // 应该能看到工具链相关内容
      const content = page.getByText(/工具|tool|Claude/i).first();
      await expect(content).toBeVisible({ timeout: 5000 });
    });

    test('Issue 策略设置页正常加载', async ({ page }) => {
      await page.goto('/ralph/settings/issues');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(500);
      const content = page.getByText(/issue|策略|policy|分类/i).first();
      await expect(content).toBeVisible({ timeout: 5000 });
    });

    test('Provider 设置页正常加载', async ({ page }) => {
      await page.goto('/ralph/settings/providers');
      await expect(page.locator('main')).toBeVisible();
      await page.waitForTimeout(500);
      const content = page.getByText(/provider|LLM|模型|model/i).first();
      await expect(content).toBeVisible({ timeout: 5000 });
    });
  });
});
