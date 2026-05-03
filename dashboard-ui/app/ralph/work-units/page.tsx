/**
 * 工作单元列表 — /ralph/work-units
 *
 * 独立列表页：搜索 + 排序 + 状态过滤 + 分页
 */

'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Search, ListTodo, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import { statusLabel, statusColor, formatDate } from '@/lib/ralph-utils';
import type { WorkUnit, WorkUnitStatus } from '@/lib/ralph-types';

const ALL_FILTERS: (WorkUnitStatus | 'all')[] = [
  'all', 'running', 'needs_review', 'accepted', 'needs_rework', 'blocked', 'failed', 'ready',
];

const PAGE_SIZE = 15;
type SortField = 'updated_at' | 'created_at' | 'status' | 'title';
type SortDir = 'asc' | 'desc';

function getFilterLabel(f: WorkUnitStatus | 'all'): string {
  return f === 'all' ? '全部' : statusLabel(f);
}

function StatusPill({ status }: { status: WorkUnitStatus }) {
  const colorMap: Record<WorkUnitStatus, string> = {
    draft: 'bg-slate-100 text-slate-600', ready: 'bg-slate-100 text-slate-700',
    running: 'bg-blue-50 text-blue-700', needs_review: 'bg-violet-50 text-violet-700',
    accepted: 'bg-emerald-50 text-emerald-700', needs_rework: 'bg-orange-50 text-orange-700',
    blocked: 'bg-amber-50 text-amber-700', failed: 'bg-red-50 text-red-700',
  };
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium', colorMap[status])}>
      <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(status))} />
      {statusLabel(status)}
    </span>
  );
}

export default function WorkUnitsPage() {
  const router = useRouter();
  const { workUnits, statusFilter, setStatusFilter, fetchWorkUnits, loading, addTab } = useRalphStore();

  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(0);

  useEffect(() => {
    void fetchWorkUnits();
  }, [statusFilter, fetchWorkUnits]);

  // Filter + search + sort
  const processed = useMemo(() => {
    let list = [...workUnits];

    // Client-side search
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((wu) =>
        wu.work_id.toLowerCase().includes(q) ||
        wu.title.toLowerCase().includes(q) ||
        wu.target.toLowerCase().includes(q)
      );
    }

    // Sort
    list.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'updated_at': cmp = a.updated_at.localeCompare(b.updated_at); break;
        case 'created_at': cmp = a.created_at.localeCompare(b.created_at); break;
        case 'status': cmp = a.status.localeCompare(b.status); break;
        case 'title': cmp = a.title.localeCompare(b.title); break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });

    return list;
  }, [workUnits, search, sortField, sortDir]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  const paged = processed.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Reset page when filter/search changes
  useEffect(() => { setPage(0); }, [search, statusFilter]);

  const handleClick = (wu: WorkUnit) => {
    addTab({ label: wu.title, type: 'work_unit', work_id: wu.work_id, pinned: false });
    router.push(`/ralph/${wu.work_id}`);
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return null;
    return <span className="text-[10px] ml-0.5">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">工作单元</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {processed.length} 个单元
          {search && ` · 搜索 "${search}"`}
        </p>
      </div>

      {/* Toolbar: search + sort */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索 ID/标题/目标..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400 placeholder:text-slate-400"
          />
        </div>
        <div className="flex items-center gap-1">
          {(['updated_at', 'title', 'status'] as SortField[]).map((f) => (
            <button
              key={f}
              onClick={() => toggleSort(f)}
              className={cn(
                'flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md transition-colors',
                sortField === f ? 'bg-slate-100 text-slate-800 font-medium' : 'text-slate-500 hover:bg-slate-50',
              )}
            >
              {f === 'updated_at' ? '更新时间' : f === 'title' ? '标题' : '状态'}
              {sortIndicator(f)}
            </button>
          ))}
        </div>
      </div>

      {/* Status filters */}
      <div className="flex items-center gap-1 flex-wrap mb-4">
        {ALL_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={cn(
              'px-3 py-1.5 text-xs rounded-md transition-all duration-150',
              f === statusFilter
                ? 'bg-slate-800 text-white font-medium shadow-sm'
                : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100',
            )}
          >
            {getFilterLabel(f)}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-sm text-slate-400">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-pulse mr-2" />
          加载中...
        </div>
      )}

      {/* Empty */}
      {!loading && paged.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center mb-3">
            <ListTodo size={20} className="text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">暂无工作单元</p>
          <p className="text-xs text-slate-400 mt-1">
            {search ? '尝试调整搜索条件' : '当有新的工作单元创建时，将在这里显示'}
          </p>
        </div>
      )}

      {/* List */}
      {!loading && paged.length > 0 && (
        <>
          <div className="space-y-2">
            {paged.map((wu) => (
              <button
                key={wu.work_id}
                onClick={() => handleClick(wu)}
                className={cn(
                  'w-full text-left rounded-lg border border-slate-200 bg-white p-4',
                  'hover:border-slate-300 hover:shadow-sm hover:bg-slate-50/50',
                  'transition-all duration-150',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 mb-1">
                      <code className="font-mono text-[11px] text-slate-400">{wu.work_id}</code>
                      <span className="text-sm font-medium text-slate-900 truncate">{wu.title}</span>
                    </div>
                    {wu.target && (
                      <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">{wu.target}</p>
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-1 mt-6">
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={cn(
                    'h-8 min-w-8 px-2 text-xs rounded-md transition-colors',
                    i === page
                      ? 'bg-slate-800 text-white font-medium'
                      : 'text-slate-500 hover:bg-slate-100',
                  )}
                >
                  {i + 1}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
