import { test, expect } from '@playwright/test';

/**
 * MVP #23: 多尺寸截图验收
 *
 * 在 4 个关键 breakpoints 截取主要页面截图:
 *   320px  - 小屏手机
 *   768px  - 平板竖屏
 *   1024px - 桌面小屏
 *   1440px - 桌面宽屏
 */

const VIEWPORTS = [
  { width: 320, height: 568, name: 'mobile' },
  { width: 768, height: 1024, name: 'tablet' },
  { width: 1024, height: 768, name: 'desktop' },
  { width: 1440, height: 900, name: 'wide' },
] as const;

const SCREENSHOT_PAGES = [
  { path: '/ralph', name: '概览' },
  { path: '/ralph/projects', name: '项目' },
  { path: '/ralph/brainstorm', name: '需求共创' },
  { path: '/ralph/approvals', name: '审批中心' },
  { path: '/ralph/work-units', name: '工作单元' },
  { path: '/ralph/memory', name: '记忆' },
  { path: '/ralph/graph', name: '图谱' },
  { path: '/ralph/settings', name: '设置' },
] as const;

test.describe('多尺寸截图验收', () => {
  for (const page of SCREENSHOT_PAGES) {
    for (const viewport of VIEWPORTS) {
      test(`截图: ${page.name} @ ${viewport.name}(${viewport.width}x${viewport.height})`, async ({ browser }) => {
        const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
        const p = await context.newPage();

        // 收集错误
        const jsErrors: string[] = [];
        const failedRequests: { url: string; status: number }[] = [];
        p.on('pageerror', (err) => jsErrors.push(err.message));
        p.on('response', (res) => {
          if (res.status() >= 400) {
            failedRequests.push({ url: res.url().replace(/http:\/\/[^/]+/, ''), status: res.status() });
          }
        });

        await p.goto(page.path, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
        await p.waitForTimeout(1000);

        // 截图
        await p.screenshot({
          path: `test-results/screenshots/${page.name}_${viewport.name}.png`,
          fullPage: true,
        });

        // 断言：没有 JS 错误
        expect(jsErrors).toEqual([]);
        // 断言：没有 500 错误
        const serverErrors = failedRequests.filter(r => r.status >= 500);
        expect(serverErrors).toEqual([]);

        await context.close();
      });
    }
  }
});
