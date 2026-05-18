'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  ChevronLeft, ChevronRight, ChevronDown, FolderOpen, Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';

const SIDEBAR_COLLAPSED_KEY = 'ralph-sidebar-collapsed';

interface NavItem {
  id: string;
  label: string;
  icon: string;
  route: string;
  badge?: number;
}

interface NavSection {
  id: string;
  label: string;
  icon: string;
  items: NavItem[];
  defaultCollapsed?: boolean;
}

type NavEntry = NavSection | { id: string; label: string; icon: string; route: string };

function isSection(entry: NavEntry): entry is NavSection {
  return 'items' in entry;
}

const NAV_ENTRIES: NavEntry[] = [
  { id: 'home', label: '概览', icon: '🏠', route: '/ralph' },
  {
    id: 'requirements',
    label: '需求',
    icon: '📋',
    items: [
      { id: 'brainstorm', label: '需求共创', icon: '💬', route: '/ralph/brainstorm' },
      { id: 'prd', label: 'PRD 文档', icon: '📄', route: '/ralph/prd' },
      { id: 'specs', label: '规格文档', icon: '📝', route: '/ralph/specs' },
      { id: 'contracts', label: '接口定义', icon: '🔗', route: '/ralph/contracts' },
    ],
  },
  { id: 'features', label: '功能看板', icon: '📊', route: '/ralph/features' },
  { id: 'execution', label: '执行', icon: '⚡', route: '/ralph/execution' },
  {
    id: 'quality',
    label: '质量',
    icon: '✅',
    items: [
      { id: 'approvals', label: '审批中心', icon: '🛡️', route: '/ralph/approvals' },
      { id: 'retro', label: '经验回顾', icon: '🔍', route: '/ralph/retro' },
      { id: 'releases', label: '发布记录', icon: '📦', route: '/ralph/releases' },
      { id: 'reports', label: '研发报告', icon: '📊', route: '/ralph/reports' },
    ],
  },
  { id: 'settings', label: '设置', icon: '⚙️', route: '/ralph/settings' },
  {
    id: 'advanced',
    label: '高级',
    icon: '🔧',
    defaultCollapsed: true,
    items: [
      { id: 'graph', label: '依赖图谱', icon: '🔀', route: '/ralph/graph' },
      { id: 'memory', label: '记忆系统', icon: '🧠', route: '/ralph/memory' },
      { id: 'usage', label: 'API 用量', icon: '📈', route: '/ralph/usage' },
      { id: 'events', label: '事件日志', icon: '📡', route: '/ralph/events' },
    ],
  },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set(['advanced']));
  const { pendingActions, currentProject, recentProjects, setCurrentProject } = useRalphStore();
  const [showProjectList, setShowProjectList] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored) setCollapsed(stored === 'true');
  }, []);

  // Load recent projects on mount
  useEffect(() => {
    if (recentProjects.length > 0) return;
    const load = async () => {
      try {
        const { listRecentProjects } = await import('@/lib/ralph-api');
        const projects = await listRecentProjects();
        if (projects.length > 0) {
          useRalphStore.setState({ recentProjects: projects });
        }
      } catch {
        // silent
      }
    };
    void load();
  }, []);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  // Close project list on outside click
  useEffect(() => {
    if (!showProjectList) return;
    const handler = () => setShowProjectList(false);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, [showProjectList]);

  const isActiveRoute = (route: string) => {
    if (route === '/ralph') return pathname === '/ralph';
    if (route === '/ralph/execution') return pathname === '/ralph/pipeline' || pathname.startsWith('/ralph/work-units') || pathname === '/ralph/scheduling';
    if (route === '/ralph/features') return pathname.startsWith('/ralph/features');
    if (route.startsWith('/ralph/settings')) return pathname.startsWith('/ralph/settings');
    if (route === '/ralph/approvals') return pathname === '/ralph/approvals';
    if (route === '/ralph/retro') return pathname === '/ralph/retro';
    if (route === '/ralph/releases') return pathname === '/ralph/releases';
    if (route === '/ralph/reports') return pathname === '/ralph/reports';
    if (route === '/ralph/graph') return pathname === '/ralph/graph';
    if (route === '/ralph/memory') return pathname === '/ralph/memory';
    if (route === '/ralph/usage') return pathname === '/ralph/usage';
    if (route === '/ralph/events') return pathname === '/ralph/events';
    if (route === '/ralph/requirements') return pathname === '/ralph/requirements';
    return pathname === route;
  };

  const toggleSection = (sectionId: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  const handleSwitchProject = async (projectPath: string, projectName: string) => {
    try {
      const { openProject } = await import('@/lib/ralph-api');
      await openProject(projectPath);
      setCurrentProject({ name: projectName, path: projectPath });
      setShowProjectList(false);
      router.push('/ralph');
    } catch {
      // silent fail
    }
  };

  return (
    <aside className={cn(
      'flex flex-col bg-slate-50/80 border-r border-slate-200 text-slate-900 transition-all duration-200',
      collapsed ? 'w-16' : 'w-60', className,
    )}>
      {/* Header */}
      <div className="flex h-12 items-center gap-2 border-b border-slate-200/70 px-3">
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
        {NAV_ENTRIES.map((entry) => {
          if (isSection(entry)) {
            const isSectionCollapsed = collapsedSections.has(entry.id);
            const active = entry.items.some((item) => isActiveRoute(item.route));

            return (
              <div key={entry.id} className="mb-1">
                {!collapsed && (
                  <button
                    onClick={() => toggleSection(entry.id)}
                    className={cn(
                      'flex w-full items-center gap-1.5 px-3 py-1.5 text-xs font-semibold tracking-wider',
                      active ? 'text-blue-700' : 'text-slate-400 hover:text-slate-600',
                    )}
                  >
                    <span className="text-sm">{entry.icon}</span>
                    <span className="flex-1 text-left">{entry.label}</span>
                    {entry.defaultCollapsed && (
                      <ChevronDown size={10} className={cn('transition-transform', !isSectionCollapsed && 'rotate-180')} />
                    )}
                  </button>
                )}

                {collapsed && (
                  <div className="px-2 py-1 text-center text-xs text-slate-400">{entry.icon}</div>
                )}

                {(!isSectionCollapsed) && (
                  <ul className={cn('space-y-0.5', collapsed ? 'px-2' : 'px-2')}>
                    {entry.items.map((item) => {
                      const isActive = isActiveRoute(item.route);
                      const isApproval = item.id === 'approvals';
                      const hasPending = isApproval && pendingActions.length > 0;

                      return (
                        <li key={item.id}>
                          <button
                            onClick={() => router.push(item.route)}
                            className={cn(
                              'flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors duration-150',
                              isActive
                                ? 'bg-blue-50 text-blue-700 font-medium'
                                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                            )}
                            title={collapsed ? item.label : undefined}
                          >
                            <span className="flex-shrink-0 text-sm">{item.icon}</span>
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
          }

          // Direct nav item (no sub-items)
          const isActive = isActiveRoute(entry.route);
          return (
            <div key={entry.id} className="mb-1">
              <button
                onClick={() => router.push(entry.route)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors duration-150',
                  collapsed ? 'justify-center px-2' : 'px-3',
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )}
                title={collapsed ? entry.label : undefined}
              >
                <span className="flex-shrink-0 text-sm">{entry.icon}</span>
                {!collapsed && <span>{entry.label}</span>}
              </button>
            </div>
          );
        })}
      </nav>

      {/* Footer — Project switcher */}
      {mounted && (
        <div className="border-t border-slate-200/70 p-3">
          {currentProject ? (
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); !collapsed && setShowProjectList(!showProjectList); }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-xs text-slate-600 hover:bg-slate-100',
                collapsed && 'justify-center px-2',
              )}
            >
              <FolderOpen size={12} className="text-blue-500 flex-shrink-0" />
              {!collapsed && (
                <span className="flex flex-1 items-center justify-between truncate">
                  <span className="truncate font-medium text-slate-700">{currentProject.name}</span>
                  <ChevronDown size={10} className={cn('ml-1 text-slate-400 transition-transform', showProjectList && 'rotate-180')} />
                </span>
              )}
            </button>
            {!collapsed && showProjectList && (
              <div className="absolute bottom-full left-0 right-0 mb-1 rounded-lg border border-slate-200 bg-white p-1 shadow-lg" onClick={(e) => e.stopPropagation()}>
                <p className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase">切换项目</p>
                {recentProjects
                  .filter((p) => p.path !== currentProject.path)
                  .slice(0, 8)
                  .map((p) => (
                    <button
                      key={p.path}
                      onClick={() => handleSwitchProject(p.path, p.name)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      <FolderOpen size={12} className="text-slate-400 flex-shrink-0" />
                      <span className="truncate">{p.name}</span>
                    </button>
                  ))}
                <div className="my-1 border-t border-slate-100" />
                <button
                  onClick={() => router.push('/ralph/projects')}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-blue-600 hover:bg-blue-50"
                >
                  <Plus size={12} />
                  <span>项目管理</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => router.push('/ralph/projects')}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-xs text-slate-500 hover:bg-slate-100',
              collapsed && 'justify-center px-2',
            )}
          >
            <Plus size={12} />
            {!collapsed && <span>新建/打开项目</span>}
          </button>
        )}
        </div>
      )}
    </aside>
  );
}
