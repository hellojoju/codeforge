'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard, ListTodo, ShieldCheck, Terminal, Radio,
  FileText, Settings, GitBranch, Brain, FolderOpen, FolderTree,
  Play, Activity, MessageCircle, Lock, Clock, ChevronLeft, ChevronRight, ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import type { Tab } from '@/lib/ralph-types';

const SIDEBAR_COLLAPSED_KEY = 'ralph-sidebar-collapsed';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  type: Tab['type'];
  workId?: string;
  route: string;
  badge?: number;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    id: 'project',
    label: '项目',
    items: [
      { id: 'projects', label: '项目管理', icon: <FolderOpen size={18} />, type: 'projects' as Tab['type'], route: '/ralph/projects' },
      { id: 'overview', label: '概览', icon: <LayoutDashboard size={18} />, type: 'overview', route: '/ralph' },
      { id: 'brainstorm', label: '需求共创', icon: <MessageCircle size={18} />, type: 'brainstorm' as Tab['type'], route: '/ralph/brainstorm' },
      { id: 'prd', label: 'PRD 文档', icon: <FileText size={18} />, type: 'prd' as Tab['type'], route: '/ralph/prd' },
      { id: 'specs', label: '规格文档', icon: <FileText size={18} />, type: 'specs' as Tab['type'], route: '/ralph/specs' },
      { id: 'contracts', label: '接口合同', icon: <Lock size={18} />, type: 'contracts' as Tab['type'], route: '/ralph/contracts' },
      { id: 'files', label: '文件浏览', icon: <FolderTree size={18} />, type: 'files' as Tab['type'], route: '/ralph/files' },
    ],
  },
  {
    id: 'execution',
    label: '执行',
    items: [
      { id: 'pipeline', label: '执行管道', icon: <Play size={18} />, type: 'pipeline' as Tab['type'], route: '/ralph/pipeline' },
      { id: 'work-units', label: '工作单元', icon: <ListTodo size={18} />, type: 'work_unit_list', route: '/ralph/work-units' },
      { id: 'scheduling', label: '调度面板', icon: <Activity size={18} />, type: 'scheduling' as Tab['type'], route: '/ralph/scheduling' },
    ],
  },
  {
    id: 'workbench',
    label: '工作台',
    items: [
      { id: 'commands', label: '命令中心', icon: <Terminal size={18} />, type: 'commands', route: '/ralph/commands' },
      { id: 'events', label: '事件日志', icon: <Radio size={18} />, type: 'events', route: '/ralph/events' },
      { id: 'approvals', label: '审批中心', icon: <ShieldCheck size={18} />, type: 'approvals', route: '/ralph/approvals' },
      { id: 'reports', label: '研发报告', icon: <FileText size={18} />, type: 'reports', route: '/ralph/reports' },
    ],
  },
  {
    id: 'system',
    label: '系统',
    items: [
      { id: 'graph', label: '依赖关系', icon: <GitBranch size={18} />, type: 'graph' as Tab['type'], route: '/ralph/graph' },
      { id: 'memory', label: '记忆系统', icon: <Brain size={18} />, type: 'memory' as Tab['type'], route: '/ralph/memory' },
      { id: 'usage', label: 'API 用量', icon: <Activity size={18} />, type: 'usage' as Tab['type'], route: '/ralph/usage' },
      { id: 'history', label: '历史项目', icon: <Clock size={18} />, type: 'history' as Tab['type'], route: '/ralph/history' },
      { id: 'providers', label: 'Provider 监控', icon: <Radio size={18} />, type: 'providers_health' as Tab['type'], route: '/ralph/providers' },
      { id: 'settings', label: '配置中心', icon: <Settings size={18} />, type: 'settings', route: '/ralph/settings' },
    ],
  },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const { setActiveTab, tabs, pendingActions } = useRalphStore();

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored) setCollapsed(stored === 'true');
  }, []);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  const handleNavClick = (item: NavItem) => {
    const existingTab = tabs.find((t) => t.type === item.type && t.work_id === item.workId);
    if (existingTab) {
      setActiveTab(existingTab.id);
    }
    router.push(item.route);
  };

  const toggleSection = (sectionId: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  return (
    <aside className={cn(
      'flex flex-col bg-slate-50/80 border-r border-slate-200 text-slate-900 transition-all duration-200',
      collapsed ? 'w-16' : 'w-60', className,
    )}>
      {/* Header */}
      <div className="flex h-14 items-center gap-2 border-b border-slate-200/70 px-3">
        {!collapsed && (
          <>
            <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 flex-shrink-0">
              <span className="text-[10px] font-bold text-white">C</span>
            </div>
            <span className="text-sm font-semibold text-slate-800 flex-1">CodeForge</span>
          </>
        )}
        <div className={cn('flex', collapsed && 'w-full justify-center')}>
          <button onClick={() => setCollapsed(!collapsed)}
            className="flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-200/70 hover:text-slate-600"
            aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}>
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-auto py-2">
        {NAV_SECTIONS.map((section) => {
          const isSectionCollapsed = collapsedSections.has(section.id);
          return (
            <div key={section.id} className="mb-2">
              {/* Section header */}
              {!collapsed && (
                <button
                  onClick={() => toggleSection(section.id)}
                  className="flex w-full items-center gap-1 px-4 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider hover:text-slate-500"
                >
                  <ChevronDown size={10} className={cn('transition-transform', isSectionCollapsed && '-rotate-90')} />
                  {section.label}
                </button>
              )}
              {/* Items */}
              {(!isSectionCollapsed || collapsed) && (
                <ul className={cn('space-y-0.5', collapsed ? 'px-2' : 'px-2')}>
                  {section.items.map((item) => {
                    const isApproval = item.id === 'approvals';
                    const hasPending = isApproval && pendingActions.length > 0;
                    return (
                      <li key={item.id} className="relative">
                        <button onClick={() => handleNavClick(item)}
                          className={cn(
                            'flex w-full items-center gap-3 rounded-md px-3 py-2',
                            'hover:bg-slate-200/60 transition-colors duration-150',
                            'text-sm font-medium text-slate-600 hover:text-slate-900',
                          )}
                          title={collapsed ? item.label : undefined}>
                          <span className="flex-shrink-0 text-slate-400">{item.icon}</span>
                          {!collapsed && (
                            <span className="flex flex-1 items-center justify-between truncate">
                              <span>{item.label}</span>
                              {hasPending && (
                                <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                                  {pendingActions.length}
                                </span>
                              )}
                            </span>
                          )}
                          {collapsed && hasPending && (
                            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
                              {pendingActions.length > 9 ? '9+' : pendingActions.length}
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-200/70 p-3">
        <div className={cn('flex items-center gap-2.5 rounded-md px-3 py-2 text-xs text-slate-500', collapsed && 'justify-center px-2')}>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          {!collapsed && <span>系统运行中</span>}
        </div>
      </div>
    </aside>
  );
}
