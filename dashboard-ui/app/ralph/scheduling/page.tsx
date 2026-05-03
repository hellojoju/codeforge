/**
 * 调度面板 — /ralph/scheduling
 */

'use client';

import { useState, useEffect } from 'react';
import { Activity, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getSchedulingStatus, getSchedulingTimeline } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';

export default function SchedulingPage() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [timeline, setTimeline] = useState<Record<string, unknown>[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([
      getSchedulingStatus().catch(() => null),
      getSchedulingTimeline().catch(() => []),
    ]).then(([s, t]) => {
      setStatus(s);
      setTimeline(t as Record<string, unknown>[]);
      setLoaded(true);
    });
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-slate-900">调度面板</h1>
        <p className="text-sm text-slate-500 mt-0.5">执行调度状态与事件时间线</p>
      </div>

      {!loaded ? (
        <div className="text-center py-16 text-slate-400">加载中...</div>
      ) : (
        <div className="space-y-6">
          {/* Status cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: '活跃任务', value: String(status?.active_work_units ?? '-'), icon: <Activity size={16} />, color: 'text-blue-600' },
              { label: '待处理', value: String(status?.pending_features ?? '-'), icon: <Clock size={16} />, color: 'text-slate-600' },
              { label: '已完成', value: String(status?.completed_features ?? '-'), icon: <CheckCircle size={16} />, color: 'text-emerald-600' },
              { label: '阻塞', value: String(status?.blocked_features ?? '-'), icon: <XCircle size={16} />, color: 'text-red-600' },
            ].map((c) => (
              <div key={c.label} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-500">{c.label}</span>
                  <span className="text-slate-400">{c.icon}</span>
                </div>
                <p className={cn('text-2xl font-bold', c.color)}>{c.value}</p>
              </div>
            ))}
          </div>

          {/* Timeline */}
          <div>
            <h2 className="text-sm font-semibold text-slate-800 mb-3">调度事件</h2>
            {timeline.length === 0 ? (
              <p className="text-sm text-slate-400">暂无调度事件</p>
            ) : (
              <div className="space-y-1.5">
                {timeline.map((event, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-md bg-slate-50 text-xs">
                    <span className="w-4 h-4 rounded-full bg-slate-300 flex-shrink-0" />
                    <span className="font-medium text-slate-700 min-w-[80px]">{String(event.event_type || '')}</span>
                    <span className="text-slate-400 flex-1 truncate">{String(event.detail || '')}</span>
                    <span className="text-slate-400">{event.timestamp ? formatDate(String(event.timestamp)) : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
