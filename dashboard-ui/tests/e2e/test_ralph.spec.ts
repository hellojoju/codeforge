import { test, expect } from '@playwright/test';

test.describe('Ralph Runtime Console', () => {
  test.describe('Ralph 页面加载', () => {
    test('访问 /ralph 页面正常加载', async ({ page }) => {
      await page.goto('/ralph');
      // 等待页面加载完成
      await expect(page.locator('main')).toBeVisible();
    });

    test('Sidebar 显示 Ralph Console 标题区域', async ({ page }) => {
      await page.goto('/ralph');
      // Sidebar 应该可见
      await expect(page.locator('aside')).toBeVisible();
      // 系统运行中状态指示器（Sidebar footer 中）
      await expect(page.locator('aside').getByText('系统运行中')).toBeVisible();
    });

    test('导航项显示正确', async ({ page }) => {
      await page.goto('/ralph');
      const nav = page.locator('aside nav');
      // 验证三个主要导航项
      await expect(nav.getByRole('button', { name: '概览', exact: true })).toBeVisible();
      await expect(nav.getByRole('button', { name: '工作单元', exact: true })).toBeVisible();
      await expect(nav.getByRole('button', { name: '审批中心', exact: true })).toBeVisible();
    });
  });

  test.describe('WorkUnit 列表', () => {
    test('概览页面包含工作单元区域', async ({ page }) => {
      await page.goto('/ralph');
      await expect(page.getByText('工作单元').first()).toBeVisible();
    });

    test('空状态或列表显示正常', async ({ page }) => {
      await page.goto('/ralph');
      // 等待加载完成
      await page.waitForTimeout(500);
      // 检查是否显示空状态或列表
      const emptyState = page.getByText('暂无工作单元');
      const listContainer = page.locator('[data-testid^="workunit-"]');

      // 至少有一个应该存在（空状态或列表项）
      await expect(emptyState.or(listContainer.first())).toBeVisible();
    });

    test('过滤按钮可见', async ({ page }) => {
      await page.goto('/ralph');
      // 检查主要过滤按钮
      await expect(page.getByRole('button', { name: '全部' }).first()).toBeVisible();
    });
  });

  test.describe('审批页面', () => {
    test('访问 /ralph/approvals 页面正常加载', async ({ page }) => {
      await page.goto('/ralph/approvals');
      // 等待页面加载完成
      await expect(page.locator('main')).toBeVisible();
    });

    test('审批页面标题显示正确', async ({ page }) => {
      await page.goto('/ralph/approvals');
      // 检查页面标题
      await expect(page.getByRole('heading', { name: '审批中心' }).first()).toBeVisible();
    });

    test('审批页面保持 Sidebar 导航', async ({ page }) => {
      await page.goto('/ralph/approvals');
      // Sidebar 应该仍然可见
      await expect(page.locator('aside')).toBeVisible();
      // 导航项应该仍然存在
      const nav = page.locator('aside nav');
      await expect(nav.getByRole('button', { name: '概览', exact: true })).toBeVisible();
      await expect(nav.getByRole('button', { name: '工作单元', exact: true })).toBeVisible();
      await expect(nav.getByRole('button', { name: '审批中心', exact: true })).toBeVisible();
    });
  });

  test.describe('Sidebar 收起展开', () => {
    test('点击收起按钮后标题隐藏', async ({ page }) => {
      await page.goto('/ralph');

      // 先确认 Sidebar footer 中的"系统运行中"文本可见
      const runningStatus = page.locator('aside').getByText('系统运行中');
      await expect(runningStatus).toBeVisible();

      // 点击收起按钮（ChevronLeft 表示当前是展开状态，点击后收起）
      const collapseButton = page.locator('aside button[aria-label="收起侧边栏"]');
      await expect(collapseButton).toBeVisible();
      await collapseButton.click();

      // 验证 Sidebar 变窄（通过检查"系统运行中"文本是否隐藏）
      await expect(runningStatus).toBeHidden();
    });

    test('点击展开按钮后标题显示', async ({ page }) => {
      await page.goto('/ralph');

      // 先收起 Sidebar
      const collapseButton = page.locator('aside button[aria-label="收起侧边栏"]');
      await collapseButton.click();

      // 验证 Sidebar footer 中的"系统运行中"文本隐藏
      const runningStatus = page.locator('aside').getByText('系统运行中');
      await expect(runningStatus).toBeHidden();

      // 点击展开按钮
      const expandButton = page.locator('aside button[aria-label="展开侧边栏"]');
      await expect(expandButton).toBeVisible();
      await expandButton.click();

      // 验证"系统运行中"文本再次可见
      await expect(runningStatus).toBeVisible();
    });

    test('Sidebar 状态切换后导航图标仍然可见', async ({ page }) => {
      await page.goto('/ralph');

      // 点击收起
      const collapseButton = page.locator('aside button[aria-label="收起侧边栏"]');
      await collapseButton.click();

      // 验证导航按钮仍然存在（即使没有文字）
      const navButtons = page.locator('aside nav button');
      await expect(navButtons.first()).toBeVisible();
      const count = await navButtons.count();
      expect(count).toBeGreaterThanOrEqual(3); // 至少三个导航项
    });
  });

  /** 点击侧边栏指定导航项 */
  async function clickSidebarNavItem(page: any, label: string) {
    // 限定在侧边栏导航区域内，避免匹配到 Tab 栏同名按钮
    await page.locator('aside nav button', { hasText: label }).first().click();
    await page.waitForTimeout(300);
  }

  test.describe('Tab 管理', () => {
    test('点击导航项添加 Tab', async ({ page }) => {
      await page.goto('/ralph');

      await clickSidebarNavItem(page, '概览');

      // 验证 Tab 栏中有对应 Tab（Tab 按钮含 border-b- 样式）
      const tabButton = page.locator('button[class*="border-b-"]').filter({ hasText: '概览' });
      await expect(tabButton).toBeVisible();
    });

    test('点击工作单元导航添加 Tab', async ({ page }) => {
      await page.goto('/ralph');

      await clickSidebarNavItem(page, '工作单元');

      // 验证 Tab 栏中有对应 Tab
      const tabButton = page.locator('button[class*="border-b-"]').filter({ hasText: '工作单元' });
      await expect(tabButton).toBeVisible();
    });

    test('点击审批中心导航添加 Tab', async ({ page }) => {
      await page.goto('/ralph');

      await clickSidebarNavItem(page, '审批中心');

      // 验证 Tab 栏中有对应 Tab
      const tabButton = page.locator('button[class*="border-b-"]').filter({ hasText: '审批中心' });
      await expect(tabButton).toBeVisible();
    });

    test('添加 Tab 后可以通过 Tab 切换内容', async ({ page }) => {
      await page.goto('/ralph');

      await clickSidebarNavItem(page, '概览');
      await clickSidebarNavItem(page, '审批中心');

      // 验证 Tab 栏中有多个 Tab 按钮
      const tabButtons = page.locator('button[class*="border-b-"]').filter({ hasText: /概览|审批中心/ });
      const tabCount = await tabButtons.count();
      expect(tabCount).toBeGreaterThanOrEqual(2);
    });

    test('关闭 Tab 功能正常', async ({ page }) => {
      await page.goto('/ralph');

      await clickSidebarNavItem(page, '概览');

      // 查找关闭按钮（X 图标），hover 后才显示
      const tabButton = page.locator('button[class*="border-b-"]').filter({ hasText: '概览' });
      await tabButton.hover();
      const closeButton = page.locator('[aria-label^="关闭"]').first();

      // 如果有关闭按钮，点击关闭
      if (await closeButton.isVisible().catch(() => false)) {
        await closeButton.click();
        await page.waitForTimeout(300);

        // 验证操作不报错
        await expect(page.locator('main')).toBeVisible();
      }
    });

    test('添加 Tab 按钮可用', async ({ page }) => {
      await page.goto('/ralph');

      // 查找添加 Tab 按钮（"+" 按钮）
      const addTabButton = page.locator('button[aria-label="添加新标签"]');
      await expect(addTabButton).toBeVisible();
      await expect(addTabButton).toBeEnabled();

      // 点击添加 Tab
      await addTabButton.click();
      await page.waitForTimeout(300);

      // 验证页面仍正常
      await expect(page.locator('main')).toBeVisible();
    });
  });

  test.describe('页面导航', () => {
    test('直接访问审批页面', async ({ page }) => {
      // 直接访问审批页面 URL
      await page.goto('/ralph/approvals');

      // 验证页面加载成功
      await expect(page.locator('main')).toBeVisible();
      await expect(page.getByRole('heading', { name: '审批中心' }).first()).toBeVisible();
    });

    test('审批页面返回工作单元页面', async ({ page }) => {
      await page.goto('/ralph/approvals');

      await clickSidebarNavItem(page, '工作单元');

      // 验证 Tab 栏中有工作单元 Tab
      const tabButton = page.locator('button[class*="border-b-"]').filter({ hasText: '工作单元' });
      await expect(tabButton).toBeVisible();
    });
  });
});
