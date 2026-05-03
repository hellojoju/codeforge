'use client';

import { useMemo } from 'react';
import { X, Plus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import { truncateLabel, statusColor } from '@/lib/ralph-utils';
import type { Tab } from '@/lib/ralph-types';

const MAX_TABS = 8;

interface TabBarProps {
  className?: string;
}

function getTabRoute(tab: Tab): string {
  switch (tab.type) {
    case 'overview':
      return '/ralph';
    case 'work_unit':
      return tab.work_id ? `/ralph/${tab.work_id}` : '/ralph';
    case 'approvals':
      return '/ralph/approvals';
    case 'commands':
      return '/ralph/commands';
    case 'events':
      return '/ralph/events';
    case 'reports':
      return '/ralph/reports';
    case 'work_unit_list':
      return '/ralph/work-units';
    case 'settings':
      return '/ralph/settings';
    case 'graph':
      return '/ralph/graph';
    case 'memory':
      return '/ralph/memory';
    case 'projects':
      return '/ralph/projects';
    case 'files':
      return '/ralph/files';
    case 'pipeline':
      return '/ralph/pipeline';
    case 'scheduling':
      return '/ralph/scheduling';
    case 'brainstorm':
      return '/ralph/brainstorm';
    case 'prd':
      return '/ralph/prd';
    case 'specs':
      return '/ralph/specs';
    case 'contracts':
      return '/ralph/contracts';
    case 'usage':
      return '/ralph/usage';
    case 'history':
      return '/ralph/history';
    case 'providers_health':
      return '/ralph/providers';
    default:
      return '/ralph';
  }
}

export function TabBar({ className }: TabBarProps) {
  const router = useRouter();
  const { tabs, activeTabId, setActiveTab, closeTab, addTab, workUnits } = useRalphStore();

  const statusColorMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const wu of workUnits) {
      if (wu.work_id) {
        map.set(wu.work_id, statusColor(wu.status));
      }
    }
    return map;
  }, [workUnits]);

  const getWorkUnitStatusColor = (tab: Tab): string | undefined => {
    if (tab.type !== 'work_unit' || !tab.work_id) return undefined;
    return statusColorMap.get(tab.work_id);
  };

  const handleTabClick = (tab: Tab) => {
    setActiveTab(tab.id);
    router.push(getTabRoute(tab));
  };

  const handleCloseClick = (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    closeTab(tabId);
  };

  const handleAddTab = () => {
    if (tabs.length >= MAX_TABS) return;
    addTab({ label: '新标签', type: 'overview', pinned: false });
  };

  const canAddTab = tabs.length < MAX_TABS;

  return (
    <div className={cn('flex h-9 items-center border-b border-slate-200 bg-slate-50/30', className)}>
      <div className="flex flex-1 items-center overflow-x-auto">
        {tabs.map((tab) => (
          <TabItem
            key={tab.id}
            tab={tab}
            isActive={tab.id === activeTabId}
            onClick={() => handleTabClick(tab)}
            onClose={(e) => handleCloseClick(e, tab.id)}
            statusColorClass={getWorkUnitStatusColor(tab)}
          />
        ))}
      </div>

      <button
        onClick={handleAddTab}
        disabled={!canAddTab}
        className={cn(
          'flex h-7 w-7 items-center justify-center rounded mr-2',
          'text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors',
          'disabled:opacity-30 disabled:cursor-not-allowed'
        )}
        aria-label="添加新标签"
      >
        <Plus size={14} />
      </button>
    </div>
  );
}

interface TabItemProps {
  tab: Tab;
  isActive: boolean;
  onClick: () => void;
  onClose: (e: React.MouseEvent) => void;
  statusColorClass?: string;
}

function TabItem({ tab, isActive, onClick, onClose, statusColorClass }: TabItemProps) {
  const displayLabel = truncateLabel(tab.label, 12);

  return (
    <button
      onClick={onClick}
      className={cn(
        'group relative flex h-9 min-w-[100px] max-w-[160px] items-center justify-between',
        'border-b-[1.5px] px-3 text-xs transition-all duration-150',
        isActive
          ? 'border-b-slate-800 bg-white text-slate-900 font-medium'
          : 'border-b-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-100/60'
      )}
    >
      {statusColorClass && (
        <span className={cn('mr-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full', statusColorClass)} />
      )}
      <span className="truncate pr-1.5">{displayLabel}</span>

      {!tab.pinned && (
        <span
          onClick={onClose}
          className={cn(
            'flex h-3.5 w-3.5 items-center justify-center rounded-sm',
            'opacity-0 group-hover:opacity-100 transition-opacity duration-150',
            'hover:bg-slate-200/80 text-slate-400 hover:text-slate-600'
          )}
          role="button"
          aria-label={`关闭 ${tab.label}`}
        >
          <X size={10} />
        </span>
      )}

      {tab.pinned && (
        <span className="ml-0.5 h-1 w-1 rounded-full bg-slate-300" />
      )}
    </button>
  );
}
