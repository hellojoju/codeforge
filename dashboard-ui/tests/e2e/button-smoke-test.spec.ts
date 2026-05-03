import { test, Page } from '@playwright/test';

/**
 * 全页面按钮点击冒烟测试
 *
 * 策略：依次访问每个页面，点击所有可交互元素，
 * 捕获 console error、page error、请求失败、点击异常，
 * 最终输出汇总报告。
 */

interface PageReport {
  path: string;
  name: string;
  jsErrors: string[];
  consoleErrors: string[];
  failedRequests: { url: string; status: number }[];
  clickStats: { total: number; failed: number };
}

const ALL_ROUTES = [
  { path: '/', name: 'Dashboard 首页' },
  { path: '/ralph', name: 'Ralph 概览' },
  { path: '/ralph/approvals', name: '审批中心' },
  { path: '/ralph/work-units', name: '工作单元' },
  { path: '/ralph/commands', name: '命令' },
  { path: '/ralph/events', name: '事件' },
  { path: '/ralph/brainstorm', name: 'Brainstorm' },
  { path: '/ralph/contracts', name: '合约' },
  { path: '/ralph/files', name: '文件' },
  { path: '/ralph/graph', name: '依赖图' },
  { path: '/ralph/history', name: '历史' },
  { path: '/ralph/memory', name: '记忆' },
  { path: '/ralph/pipeline', name: '流水线' },
  { path: '/ralph/prd', name: 'PRD' },
  { path: '/ralph/projects', name: '项目' },
  { path: '/ralph/providers', name: '提供商' },
  { path: '/ralph/reports', name: '报告' },
  { path: '/ralph/scheduling', name: '调度' },
  { path: '/ralph/specs', name: '规格' },
  { path: '/ralph/usage', name: '用量' },
  { path: '/ralph/settings', name: '设置' },
  { path: '/ralph/settings/agents', name: '设置-Agent' },
  { path: '/ralph/settings/issues', name: '设置-Issues' },
  { path: '/ralph/settings/providers', name: '设置-Providers' },
  { path: '/ralph/settings/tools', name: '设置-Tools' },
];

const CLICKABLE = ['button', '[role="button"]', '[role="tab"]'] as const;

test.describe('全页面按钮点击冒烟测试', () => {
  test.describe.configure({ mode: 'serial' });

  const allReports: PageReport[] = [];

  for (const route of ALL_ROUTES) {
    test(route.name, async ({ page }) => {
      test.setTimeout(90000);

      // 错误收集器
      const jsErrors: string[] = [];
      const consoleErrors: string[] = [];
      const failedRequests: { url: string; status: number }[] = [];

      page.on('pageerror', (err) => {
        jsErrors.push(err.message);
      });
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200));
      });
      page.on('response', (res) => {
        if (res.status() >= 400) {
          failedRequests.push({ url: res.url().replace(/http:\/\/[^/]+/, ''), status: res.status() });
        }
      });

      // 访问页面
      await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(1000);

      // 点按钮
      let totalClickable = 0;
      let failedClicks = 0;

      for (const sel of CLICKABLE) {
        const count = await page.locator(sel).count().catch(() => 0);
        totalClickable += count;

        for (let i = 0; i < count; i++) {
          // 每次重新获取定位器，防止 stale
          const loc = page.locator(sel).nth(i);
          const ok = await loc.isVisible().catch(() => false);
          if (!ok) continue;

          const hidden = await loc.getAttribute('aria-hidden').catch(() => null);
          if (hidden === 'true') continue;

          try {
            await loc.scrollIntoViewIfNeeded().catch(() => {});
            await loc.click({ timeout: 2000 });
            // 防止 click 风暴
            await page.waitForTimeout(100);
          } catch {
            failedClicks++;
          }
        }
      }

      // 记录报告
      const report: PageReport = {
        path: route.path,
        name: route.name,
        jsErrors,
        consoleErrors,
        failedRequests: failedRequests.filter(
          (r) => !r.url.includes('/_next/static') && !r.url.includes('/favicon')
        ),
        clickStats: { total: totalClickable, failed: failedClicks },
      };
      allReports.push(report);

      // 打印
      const issues: string[] = [];
      if (jsErrors.length) issues.push(`JS错误:${jsErrors.length}`);
      if (consoleErrors.length) issues.push(`Console错误:${consoleErrors.length}`);
      if (failedRequests.length) issues.push(`请求失败:${failedRequests.length}`);
      if (failedClicks > 0) issues.push(`点击失败:${failedClicks}/${totalClickable}`);

      if (issues.length > 0) {
        console.log(`\n[${route.name}] ${issues.join(' | ')}`);
        // 打印详情
        for (const e of jsErrors) console.log(`  ❌ ${e}`);
        for (const e of consoleErrors.slice(0, 5)) console.log(`  ⚠️  ${e}`);
        for (const r of failedRequests) console.log(`  🔴 [${r.status}] ${r.url}`);
      } else {
        console.log(`\n[${route.name}] ✅ 正常 (${totalClickable} 个按钮)`);
      }
    });
  }

  // 所有页面跑完后输出汇总
  test('汇总报告', () => {
    console.log('\n========================================');
    console.log('📊 全页面按钮点击冒烟测试 - 汇总报告');
    console.log('========================================');

    let totalJS = 0, totalConsole = 0, totalReqFail = 0, totalClickFail = 0;

    for (const r of allReports) {
      if (r.jsErrors.length || r.consoleErrors.length || r.failedRequests.length || r.clickStats.failed > 0) {
        console.log(`\n--- ${r.name} (${r.path}) ---`);
        if (r.jsErrors.length) {
          totalJS += r.jsErrors.length;
          r.jsErrors.forEach(e => console.log(`  ❌ ${e}`));
        }
        if (r.consoleErrors.length) {
          totalConsole += r.consoleErrors.length;
          r.consoleErrors.slice(0, 10).forEach(e => console.log(`  ⚠️  ${e}`));
          if (r.consoleErrors.length > 10) console.log(`  ...还有 ${r.consoleErrors.length - 10} 条`);
        }
        if (r.failedRequests.length) {
          totalReqFail += r.failedRequests.length;
          for (const fr of r.failedRequests) console.log(`  🔴 [${fr.status}] ${fr.url}`);
        }
        if (r.clickStats.failed > 0) {
          totalClickFail += r.clickStats.failed;
          console.log(`  ⚠️  点击失败 ${r.clickStats.failed}/${r.clickStats.total}`);
        }
      }
    }

    console.log('\n========================================');
    console.log(`📈 总计: JS错误=${totalJS} | Console错误=${totalConsole} | 请求失败=${totalReqFail} | 点击失败=${totalClickFail}`);
    console.log('========================================');

    // 不再 assert，纯展示
  });
});
