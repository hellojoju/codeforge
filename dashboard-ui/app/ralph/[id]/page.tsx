/**
 * WorkUnit 详情页 — /ralph/[id]
 *
 * 布局：顶部 sticky 操作栏 + 左侧内容区 + 右侧锚点导航
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useRalphStore } from '@/lib/ralph-store';
import { WorkUnitDetail } from '@/components/ralph/work-unit-detail';
import { OperationBar } from '@/components/ralph/operation-bar';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import type { WorkUnit } from '@/lib/ralph-types';

/** 锚点导航条目 */
interface AnchorItem {
  id: string;
  label: string;
}

const ANCHOR_ITEMS: AnchorItem[] = [
  { id: 'section-target', label: '目标' },
  { id: 'section-acceptance', label: '验收标准' },
  { id: 'section-scope', label: '允许/禁止修改' },
  { id: 'section-context-pack', label: 'Context Pack' },
  { id: 'section-harness', label: 'Task Harness' },
  { id: 'section-evidence', label: '证据' },
  { id: 'section-stream-log', label: '执行日志' },
  { id: 'section-reviews', label: '审查结果' },
  { id: 'section-transitions', label: '状态流转' },
  { id: 'section-meta', label: '元信息' },
];

/** 右侧 sticky 锚点导航 */
function AnchorNav({ activeId }: { activeId: string | null }) {
  const handleClick = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <nav className="w-44 flex-shrink-0 hidden xl:block">
      <div className="sticky top-16">
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2">
          页面导航
        </span>
        <ul className="mt-2 space-y-0.5">
          {ANCHOR_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => handleClick(item.id)}
                className={cn(
                  'w-full text-left px-2 py-1 text-xs rounded-md transition-colors',
                  'hover:bg-slate-100 hover:text-slate-800',
                  activeId === item.id
                    ? 'text-slate-900 font-medium bg-slate-100'
                    : 'text-slate-500',
                )}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

export default function WorkUnitDetailPage() {
  const params = useParams();
  const workId = params.id as string;

  const [workUnit, setWorkUnit] = useState<WorkUnit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAnchorId, setActiveAnchorId] = useState<string | null>(null);

  const { workUnits, fetchWorkUnits } = useRalphStore();

  const refreshWorkUnit = useCallback(async () => {
    try {
      await fetchWorkUnits();
      const refreshed = useRalphStore.getState().workUnits.find((u: WorkUnit) => u.work_id === workId);
      if (refreshed) setWorkUnit(refreshed);
    } catch {
      // silent
    }
  }, [workId, fetchWorkUnits]);

  // Load work unit
  useEffect(() => {
    async function loadWorkUnit() {
      setLoading(true);
      setError(null);

      try {
        const fromStore = workUnits.find((u: WorkUnit) => u.work_id === workId);
        if (fromStore) {
          setWorkUnit(fromStore);
          setLoading(false);
          return;
        }

        try {
          const { getWorkUnit } = await import('@/lib/ralph-api');
          const unit = await getWorkUnit(workId);
          setWorkUnit(unit);
        } catch {
          await fetchWorkUnits();
          const refreshed = useRalphStore.getState().workUnits.find((u: WorkUnit) => u.work_id === workId);
          if (refreshed) {
            setWorkUnit(refreshed);
          } else {
            setError('WorkUnit not found');
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load WorkUnit');
      } finally {
        setLoading(false);
      }
    }

    if (workId) {
      void loadWorkUnit();
    }
  }, [workId, workUnits, fetchWorkUnits]);

  // Track visible section for anchor nav
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveAnchorId(entry.target.id);
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 },
    );

    for (const item of ANCHOR_ITEMS) {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, [workUnit]);

  // Loading
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 size={20} className="animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  // Error
  if (error || !workUnit) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertCircle size={32} className="mx-auto mb-2 text-red-500" />
          <p className="text-muted-foreground">{error || 'WorkUnit not found'}</p>
          <Link
            href="/ralph"
            className={cn(
              'inline-flex items-center gap-1 mt-4 text-sm',
              'text-primary hover:underline'
            )}
          >
            <ArrowLeft size={14} />
            返回列表
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      {/* Fixed operation bar */}
      <OperationBar workUnit={workUnit} onCommandSent={refreshWorkUnit} />

      {/* Content area: center + right anchor */}
      <div className="flex justify-center">
        <div className="flex-1 max-w-4xl px-6 py-5">
          <WorkUnitDetail workUnit={workUnit} />
        </div>
        <AnchorNav activeId={activeAnchorId} />
      </div>
    </div>
  );
}
