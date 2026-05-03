import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('概览页面正常加载', async ({ page }) => {
    await page.goto('/ralph');
    await expect(page.getByRole('heading', { name: '概览' })).toBeVisible();
  });

  test('统计卡片可见', async ({ page }) => {
    await page.goto('/ralph');
    for (const label of ['工作单元', '运行中', '成功率', '待审批', '阻塞项', '待命令']) {
      await expect(page.getByText(label).first()).toBeVisible();
    }
  });

  test('系统状态面板可见', async ({ page }) => {
    await page.goto('/ralph');
    await expect(page.getByText('系统状态')).toBeVisible();
    // 连接状态（已连接或未连接）
    const connectionStatus = page.getByText(/已连接|未连接/);
    await expect(connectionStatus).toBeVisible({ timeout: 5000 });
  });

  test('状态分布面板可见', async ({ page }) => {
    await page.goto('/ralph');
    await expect(page.getByText('状态分布')).toBeVisible();
  });

  test('最近活动面板可见', async ({ page }) => {
    await page.goto('/ralph');
    await expect(page.getByText('最近活动')).toBeVisible();
  });
});
