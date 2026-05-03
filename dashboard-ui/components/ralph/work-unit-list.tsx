/**
 * WorkUnitList — 工作单元列表
 *
 * 筛选 → 加载/空 → 卡片列表
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ListTodo } from 'lucide-react';
import { useRalphStore } from '@/lib/ralph-store';
import { statusLabel, statusColor, formatDate } from '@/lib/ralph-utils';
import type { WorkUnitStatus } from '@/lib/ralph-types';
import { cn } from '@/lib/utils';

const ALL_FILTERS: (WorkUnitStatus | 'all')[] = [
  'all',
  'running',
  'needs_review',
  'accepted',
  'needs_rework',
  'blocked',
  'failed',
  'ready',
];

function getFilterLabel(filter: WorkUnitStatus | 'all'): string {
  if (filter === 'all') return '全部';
  return statusLabel(filter);
}

/** 状态标记 */
function StatusDot({ status }: { status: WorkUnitStatus }) {
  return <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', statusColor(status))} />;
}

/** 状态标签 */
function StatusPill({ status }: { status: WorkUnitStatus }) {
  const colorMap: Record<WorkUnitStatus, string> = {
    draft: 'bg-slate-100 text-slate-600',
    ready: 'bg-slate-100 text-slate-700',
    running: 'bg-blue-50 text-blue-700',
    needs_review: 'bg-violet-50 text-violet-700',
    accepted: 'bg-emerald-50 text-emerald-700',
    needs_rework: 'bg-orange-50 text-orange-700',
    blocked: 'bg-amber-50 text-amber-700',
    failed: 'bg-red-50 text-red-700',
  };
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium leading-none', colorMap[status])}>
      <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(status))} />
      {statusLabel(status)}
    </span>
  );
}

export function WorkUnitList() {
  const router = useRouter();
  const {
    workUnits,
    statusFilter,
    setStatusFilter,
    fetchWorkUnits,
    addTab,
    loading,
  } = useRalphStore();

  const handleWorkUnitClick = (wu: { work_id: string; title: string }) => {
    addTab({
      label: wu.title,
      type: 'work_unit',
      work_id: wu.work_id,
      pinned: false,
    });
    router.push(`/ralph/${wu.work_id}`);
  };

  useEffect(() => {
    void fetchWorkUnits();
  }, [statusFilter, fetchWorkUnits]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-1 flex-wrap">
        {ALL_FILTERS.map((f) => (
          <button
            key={f}
            data-testid={`filter-${f}`}
            onClick={() => setStatusFilter(f)}
            className={cn(
              'px-3 py-1.5 text-xs rounded-md transition-all duration-150',
              f === statusFilter
                ? 'bg-slate-800 text-white font-medium shadow-sm'
                : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
            )}
          >
            {getFilterLabel(f)}
          </button>
        ))}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex items-center gap-2.5 text-sm text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-pulse" />
            加载中...
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && workUnits.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center mb-3">
            <ListTodo size={20} className="text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">暂无工作单元</p>
          <p className="text-xs text-slate-400 mt-1">当有新的工作单元创建时，将在这里显示</p>
        </div>
      )}

      {/* List */}
      {!loading && workUnits.length > 0 && (
        <div className="space-y-2">
          {workUnits.map((wu) => (
            <button
              key={wu.work_id}
              data-testid={`workunit-${wu.work_id}`}
              onClick={() => handleWorkUnitClick(wu)}
              className={cn(
                'w-full text-left rounded-lg border border-slate-200 bg-white p-4',
                'hover:border-slate-300 hover:shadow-sm hover:bg-slate-50/50',
                'transition-all duration-150'
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 mb-1">
                    <span className="font-mono text-[11px] text-slate-400 leading-none">
                      {wu.work_id}
                    </span>
                    <span className="text-xs text-slate-300">/</span>
                    <span className="text-sm font-medium text-slate-900 truncate">
                      {wu.title}
                    </span>
                  </div>
                  {wu.target && (
                    <p className="text-xs text-slate-500 leading-relaxed line-clamp-2 mt-0.5">
                      {wu.target}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-400">
                    <span>{wu.work_type}</span>
                    <span className="text-slate-200">|</span>
                    <span>{formatDate(wu.updated_at)}</span>
                    {wu.dependencies.length > 0 && (
                      <>
                        <span className="text-slate-200">|</span>
                        <span className="truncate">依赖: {wu.dependencies.join(', ')}</span>
                      </>
                    )}
                  </div>
                </div>
                <StatusPill status={wu.status} />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
