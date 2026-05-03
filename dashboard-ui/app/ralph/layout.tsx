'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { MessageCircle, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Sidebar } from '@/components/ralph/sidebar';
import { TabBar } from '@/components/ralph/tab-bar';
import { RalphWebSocket } from '@/lib/ralph-websocket';
import { useRalphStore, hydrateTabsFromStorage } from '@/lib/ralph-store';
import type { Tab } from '@/lib/ralph-types';
import { ChatDrawer } from '@/components/chat-drawer';
import { GlobalSearch } from '@/components/ralph/global-search';

export default function RalphLayout({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false);
  const pathname = usePathname();
  const wsRef = useRef<RalphWebSocket | null>(null);

  // 客户端 hydration: 从 localStorage 恢复 tabs（避免 SSR 不匹配）
  useEffect(() => {
    hydrateTabsFromStorage();
  }, []);

  // WebSocket 连接
  useEffect(() => {
    const ws = new RalphWebSocket('/ws/dashboard');
    wsRef.current = ws;

    ws.connect();

    const unsubscribe = ws.on((event) => {
      useRalphStore.getState().handleEvent(event);
    });

    return () => {
      unsubscribe();
      ws.disconnect();
      wsRef.current = null;
    };
  }, []);

  // 路由同步到 Tab：路由变化时创建或激活对应 tab
  useEffect(() => {
    const state = useRalphStore.getState();
    const { tabs, addTab, setActiveTab } = state;

    let targetTabId: string | null = null;

    if (pathname === '/ralph/work-units') {
      const wuListTab = tabs.find((t) => t.type === 'work_unit_list');
      if (wuListTab) targetTabId = wuListTab.id;
      else targetTabId = addTabAndReturnId({ label: '工作单元', type: 'work_unit_list', pinned: false });
    } else if (pathname === '/ralph' || pathname === '/ralph/') {
      const overviewTab = tabs.find((t) => t.type === 'overview');
      if (overviewTab) {
        targetTabId = overviewTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '概览', type: 'overview', pinned: false });
      }
    } else if (pathname === '/ralph/commands') {
      const commandsTab = tabs.find((t) => t.type === 'commands');
      if (commandsTab) {
        targetTabId = commandsTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '命令中心', type: 'commands', pinned: false });
      }
    } else if (pathname === '/ralph/events') {
      const eventsTab = tabs.find((t) => t.type === 'events');
      if (eventsTab) {
        targetTabId = eventsTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '事件日志', type: 'events', pinned: false });
      }
    } else if (pathname === '/ralph/approvals') {
      const approvalsTab = tabs.find((t) => t.type === 'approvals');
      if (approvalsTab) {
        targetTabId = approvalsTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '审批中心', type: 'approvals', pinned: false });
      }
    } else if (pathname === '/ralph/reports') {
      const reportsTab = tabs.find((t) => t.type === 'reports');
      if (reportsTab) {
        targetTabId = reportsTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '研发报告', type: 'reports', pinned: false });
      }
    } else if (pathname.startsWith('/ralph/settings')) {
      const settingsTab = tabs.find((t) => t.type === 'settings');
      if (settingsTab) {
        targetTabId = settingsTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '配置中心', type: 'settings', pinned: false });
      }
    } else if (pathname === '/ralph/graph') {
      const graphTab = tabs.find((t) => t.type === 'graph');
      if (graphTab) {
        targetTabId = graphTab.id;
      } else {
        targetTabId = addTabAndReturnId({ label: '依赖关系', type: 'graph', pinned: false });
      }
    } else if (pathname === '/ralph/memory') {
      const memoryTab = tabs.find((t) => t.type === 'memory');
      if (memoryTab) targetTabId = memoryTab.id;
      else targetTabId = addTabAndReturnId({ label: '记忆系统', type: 'memory', pinned: false });
    } else if (pathname === '/ralph/projects') {
      const tab = tabs.find((t) => t.type === 'projects');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '项目管理', type: 'projects', pinned: false });
    } else if (pathname === '/ralph/files') {
      const tab = tabs.find((t) => t.type === 'files');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '文件浏览', type: 'files', pinned: false });
    } else if (pathname === '/ralph/pipeline') {
      const tab = tabs.find((t) => t.type === 'pipeline');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '执行管道', type: 'pipeline', pinned: false });
    } else if (pathname === '/ralph/scheduling') {
      const tab = tabs.find((t) => t.type === 'scheduling');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '调度面板', type: 'scheduling', pinned: false });
    } else if (pathname === '/ralph/brainstorm') {
      const tab = tabs.find((t) => t.type === 'brainstorm');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '需求共创', type: 'brainstorm', pinned: false });
    } else if (pathname === '/ralph/prd') {
      const tab = tabs.find((t) => t.type === 'prd');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: 'PRD 文档', type: 'prd', pinned: false });
    } else if (pathname === '/ralph/specs') {
      const tab = tabs.find((t) => t.type === 'specs');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '规格文档', type: 'specs', pinned: false });
    } else if (pathname === '/ralph/contracts') {
      const tab = tabs.find((t) => t.type === 'contracts');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '接口合同', type: 'contracts', pinned: false });
    } else if (pathname === '/ralph/usage') {
      const tab = tabs.find((t) => t.type === 'usage');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: 'API 用量', type: 'usage', pinned: false });
    } else if (pathname === '/ralph/history') {
      const tab = tabs.find((t) => t.type === 'history');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: '历史项目', type: 'history', pinned: false });
    } else if (pathname === '/ralph/providers') {
      const tab = tabs.find((t) => t.type === 'providers_health');
      if (tab) targetTabId = tab.id;
      else targetTabId = addTabAndReturnId({ label: 'Provider 监控', type: 'providers_health', pinned: false });
    } else if (pathname.startsWith('/ralph/')) {
      const workId = pathname.split('/').pop();
      const reservedPaths = ['approvals', 'commands', 'events', 'reports', 'work-units', 'settings', 'graph', 'memory', 'projects', 'files', 'pipeline', 'scheduling', 'brainstorm', 'prd', 'specs', 'contracts', 'usage', 'history', 'providers'];
      if (workId && !reservedPaths.includes(workId)) {
        const workTab = tabs.find((t) => t.type === 'work_unit' && t.work_id === workId);
        if (workTab) {
          targetTabId = workTab.id;
        } else {
          targetTabId = addTabAndReturnId({ label: `工作单元 ${workId}`, type: 'work_unit', work_id: workId, pinned: false });
        }
      }
    }

    if (targetTabId) {
      setActiveTab(targetTabId);
    }
  }, [pathname]);

  // 辅助函数：添加 tab 并返回新 tab 的 id
  function addTabAndReturnId(tab: Omit<Tab, 'id' | 'created_at'>): string | null {
    const state = useRalphStore.getState();
    // 检查是否已存在
    const existing = state.tabs.find((t) => t.type === tab.type && t.work_id === tab.work_id);
    if (existing) return existing.id;
    // 添加新 tab
    state.addTab(tab as any);
    // 获取新 tab 的 id
    const newState = useRalphStore.getState();
    const newTab = newState.tabs.find((t) => t.type === tab.type && t.work_id === tab.work_id);
    return newTab?.id ?? null;
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-100">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden bg-white">
        {/* Tab bar */}
        <TabBar />

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>

      {/* Global search */}
      <GlobalSearch />

      {/* Chat drawer */}
      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />

      {/* Floating chat button */}
      <button
        onClick={() => setChatOpen(true)}
        className={cn(
          'fixed bottom-6 right-6 z-30 flex items-center gap-2 h-11 pl-3.5 pr-4',
          'bg-slate-900 text-white rounded-full shadow-lg',
          'hover:bg-slate-800 hover:shadow-xl hover:scale-105',
          'transition-all duration-200 active:scale-95'
        )}
        aria-label="打开对话"
      >
        <MessageCircle size={18} />
        <span className="text-sm font-medium">对话</span>
        <ChevronRight size={14} className="text-slate-400" />
      </button>
    </div>
  );
}
