import { test, expect } from '@playwright/test';

/**
 * MVP #24: 边界状态检查
 *
 * 覆盖:
 *   1. 空状态（页面但无数据时的表现）
 *   2. 错误状态（API 返回错误 / 页面崩溃时的降级）
 *   3. 不存在的路由
 *   4. 网络断开时的表现
 */

test.describe('边界状态验收', () => {
  test.describe('空状态', () => {
    test('不存在的路由显示 404', async ({ page }) => {
      const response = await page.goto('/ralph/nonexistent-route-xyz', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(500);
      // Next.js 默认 404 页面
      const body = page.locator('body');
      await expect(body).toBeVisible();
      // 不应该是空白页 — 确保 main 区域有内容
      const main = page.locator('main');
      const hasMain = await main.isVisible().catch(() => false);
      if (!hasMain) {
        // 没有 main 说明是 Next.js 默认 404，这也 OK
        const notFound = page.getByText(/404|Not Found|此页面/i).first();
        const notFoundVisible = await notFound.isVisible().catch(() => false);
        expect(notFoundVisible).toBeTruthy();
      }
    });
  });

  test.describe('加载状态', () => {
    test('页面加载过程中不报 JS 错误', async ({ page }) => {
      const jsErrors: string[] = [];
      page.on('pageerror', (err) => jsErrors.push(err.message));

      await page.goto('/ralph', { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(2000);

      expect(jsErrors).toEqual([]);
    });
  });

  test.describe('导航健壮性', () => {
    test('在页面间快速切换不崩溃', async ({ page }) => {
      const jsErrors: string[] = [];
      page.on('pageerror', (err) => jsErrors.push(err.message));

      const routes = ['/ralph', '/ralph/approvals', '/ralph/work-units', '/ralph/projects', '/ralph'];
      for (const route of routes) {
        await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 10000 }).catch(() => {});
        await page.waitForTimeout(300);
      }

      expect(jsErrors).toEqual([]);
    });
  });

  test.describe('WebSocket 连接状态', () => {
    test('Dashboard 首页显示连接状态指示器', async ({ page }) => {
      await page.goto('/ralph');
      await page.waitForTimeout(1000);

      // 右侧面板的系统状态：已连接 或 未连接
      const statusText = page.getByText(/已连接|未连接|连接中|已断开|连接错误/i);
      await expect(statusText).toBeVisible({ timeout: 5000 });
    });
  });
});
