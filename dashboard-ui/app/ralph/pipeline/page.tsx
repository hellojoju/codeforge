/**
 * 执行管道 — /ralph/pipeline
 */

'use client';

import { useEffect, useState } from 'react';
import { useRalphStore } from '@/lib/ralph-store';
import { statusColor, statusLabel, formatDate } from '@/lib/ralph-utils';
import type { WorkUnit } from '@/lib/ralph-types';
import { cn } from '@/lib/utils';
import { GitBranch, CheckCircle, Loader2, XCircle, Clock } from 'lucide-react';
import Link from 'next/link';

const STAGES = [
  { key: 'preflight', label: '前置检查', icon: CheckCircle },
  { key: 'execution', label: '执行中', icon: Loader2 },
  { key: 'evidence', label: '收集证据', icon: Clock },
  { key: 'postflight', label: '后置校验', icon: CheckCircle },
  { key: 'review', label: '审查', icon: GitBranch },
];

export default function PipelinePage() {
  const { workUnits, fetchWorkUnits, loading } = useRalphStore();

  useEffect(() => { void fetchWorkUnits(); }, [fetchWorkUnits]);

  const activeUnits = workUnits.filter((wu) => !['accepted', 'draft'].includes(wu.status));

  return (
    <div className="max-w-5xl mx-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">执行管道</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {activeUnits.length} 个活跃 WorkUnit · 共 {workUnits.length} 个
        </p>
      </div>

      {loading ? (
        <div className="text-center py-16 text-slate-400">加载中...</div>
      ) : activeUnits.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <GitBranch size={24} className="mx-auto mb-2" />
          <p className="text-sm">暂无活跃管道</p>
        </div>
      ) : (
        <div className="space-y-4">
          {activeUnits.map((wu) => (
            <PipelineCard key={wu.work_id} workUnit={wu} />
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineCard({ workUnit }: { workUnit: WorkUnit }) {
  const currentStageIdx = (() => {
    switch (workUnit.status) {
      case 'ready': return 0;
      case 'running': return 1;
      case 'needs_review': return 4;
      case 'failed': return -1;
      default: return -1;
    }
  })();

  return (
    <Link href={`/ralph/${workUnit.work_id}`}
      className="block rounded-lg border border-slate-200 bg-white p-5 hover:border-slate-300 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono text-slate-400">{workUnit.work_id}</code>
            <span className="text-sm font-semibold text-slate-900">{workUnit.title}</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {workUnit.producer_role && `执行: ${workUnit.producer_role} · `}
            {workUnit.reviewer_role && `审查: ${workUnit.reviewer_role}`}
          </p>
        </div>
        <span className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium',
          workUnit.status === 'running' ? 'bg-blue-50 text-blue-700' :
          workUnit.status === 'failed' ? 'bg-red-50 text-red-700' :
          'bg-slate-100 text-slate-600')}>
          <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(workUnit.status))} />
          {statusLabel(workUnit.status)}
        </span>
      </div>

      {/* Stage indicators */}
      <div className="flex items-center gap-1">
        {STAGES.map((stage, idx) => {
          const isDone = currentStageIdx > idx;
          const isCurrent = currentStageIdx === idx;
          const isFailed = workUnit.status === 'failed' && idx === 1;
          return (
            <div key={stage.key} className="flex items-center flex-1">
              <div className={cn(
                'flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium flex-1 justify-center',
                isDone ? 'bg-emerald-50 text-emerald-600' :
                isCurrent ? 'bg-blue-50 text-blue-600' :
                isFailed ? 'bg-red-50 text-red-600' : 'bg-slate-50 text-slate-400',
              )}>
                <stage.icon size={10} className={isCurrent ? 'animate-spin' : ''} />
                <span className="hidden sm:inline">{stage.label}</span>
              </div>
              {idx < STAGES.length - 1 && (
                <div className={cn('h-px w-2', isDone ? 'bg-emerald-300' : 'bg-slate-200')} />
              )}
            </div>
          );
        })}
      </div>
    </Link>
  );
}
