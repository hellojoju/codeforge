/**
 * EventLog — 实时事件日志流组件
 *
 * 支持暂停/继续、事件类型过滤、清空、自动滚动
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { Pause, Play, Trash2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import { formatDate } from '@/lib/ralph-utils';
import type { RalphEvent, RalphEventType } from '@/lib/ralph-types';

const EVENT_TYPE_CONFIG: Record<RalphEventType, { label: string; color: string; dot: string }> = {
  work_unit_created:         { label: 'WorkUnit 创建',   color: 'text-blue-600',   dot: 'bg-blue-400' },
  work_unit_status_changed:  { label: '状态变更',         color: 'text-slate-600',  dot: 'bg-slate-400' },
  evidence_saved:            { label: '证据保存',         color: 'text-slate-500',  dot: 'bg-slate-300' },
  review_completed:          { label: '审查完成',         color: 'text-purple-600', dot: 'bg-purple-400' },
  command_applied:           { label: '命令应用',         color: 'text-emerald-600',dot: 'bg-emerald-400' },
  command_failed:            { label: '命令失败',         color: 'text-red-600',    dot: 'bg-red-400' },
  blocker_created:           { label: '阻塞创建',         color: 'text-red-600',    dot: 'bg-red-400' },
  blocker_resolved:          { label: '阻塞解除',         color: 'text-emerald-600',dot: 'bg-emerald-400' },
  pending_action_created:    { label: '待审批',           color: 'text-amber-600',  dot: 'bg-amber-400' },
  pending_action_resolved:   { label: '审批完成',         color: 'text-slate-500',  dot: 'bg-slate-300' },
  heartbeat:                 { label: '心跳',             color: 'text-slate-300',  dot: 'bg-slate-200' },
  ralph_stream_chunk:        { label: '流输出',           color: 'text-slate-400',  dot: 'bg-slate-300' },
};

const EVENT_TYPES = Object.keys(EVENT_TYPE_CONFIG) as RalphEventType[];

interface EventLogProps {
  className?: string;
}

export function EventLog({ className }: EventLogProps) {
  const { recentEvents, connected } = useRalphStore();
  const [paused, setPaused] = useState(false);
  const [typeFilter, setTypeFilter] = useState<Set<RalphEventType>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  // Filter events
  const displayEvents = paused ? [...recentEvents] : [...recentEvents];
  displayEvents.reverse(); // newest first

  const filteredEvents = typeFilter.size > 0
    ? displayEvents.filter((e) => typeFilter.has(e.event_type))
    : displayEvents;

  // Auto-scroll
  useEffect(() => {
    if (!paused && autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [paused, recentEvents.length]);

  const toggleFilter = (type: RalphEventType) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        {/* Pause/Resume */}
        <button
          onClick={() => setPaused(!paused)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors',
            paused
              ? 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100'
              : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200',
          )}
        >
          {paused ? <Play size={12} /> : <Pause size={12} />}
          {paused ? '继续' : '暂停'}
        </button>

        {/* Event count */}
        <span className="text-xs text-slate-400">
          {filteredEvents.length}/{recentEvents.length} 条
        </span>

        {/* Connection status */}
        <span className={cn(
          'flex items-center gap-1 text-xs',
          connected ? 'text-emerald-600' : 'text-slate-400',
        )}>
          <span className={cn('h-1.5 w-1.5 rounded-full', connected ? 'bg-emerald-500' : 'bg-slate-300')} />
          {connected ? '实时' : '离线'}
        </span>
      </div>

      {/* Type filters */}
      <div className="flex items-center gap-1 flex-wrap mb-3">
        {EVENT_TYPES.map((type) => {
          const config = EVENT_TYPE_CONFIG[type];
          const selected = typeFilter.size === 0 || typeFilter.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleFilter(type)}
              className={cn(
                'px-2 py-0.5 text-[10px] rounded transition-colors',
                selected
                  ? 'bg-slate-200 text-slate-700 font-medium'
                  : 'text-slate-400 hover:text-slate-600',
              )}
            >
              <span className={cn('inline-block h-1 w-1 rounded-full mr-1', config.dot)} />
              {config.label}
            </button>
          );
        })}
      </div>

      {/* Event list */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto rounded-lg border border-slate-200 bg-white"
      >
        {filteredEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <AlertCircle size={24} className="text-slate-300 mb-3" />
            <p className="text-sm text-slate-400">暂无事件</p>
            <p className="text-xs text-slate-400 mt-1">等待 WebSocket 推送...</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {filteredEvents.map((event) => (
              <EventItem key={`${event.sequence}-${event.event_type}-${event.timestamp}`} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** 单条事件 */
function EventItem({ event }: { event: RalphEvent }) {
  const [expanded, setExpanded] = useState(false);
  const config = EVENT_TYPE_CONFIG[event.event_type] ?? { label: event.event_type, color: 'text-slate-500', dot: 'bg-slate-300' };
  const isAbnormal = event.event_type === 'command_failed' || event.event_type === 'blocker_created';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className={cn(
        'px-3 py-2 text-xs cursor-pointer transition-colors hover:bg-slate-50',
        isAbnormal && 'bg-red-50/30',
      )}
    >
      <div className="flex items-center gap-2.5">
        <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', config.dot)} />
        <span className={cn('font-medium flex-shrink-0 min-w-[72px]', config.color)}>
          {config.label}
        </span>
        {event.work_id && (
          <code className="font-mono text-slate-500 truncate flex-1">{event.work_id}</code>
        )}
        {!event.work_id && <span className="flex-1" />}
        <span className="text-slate-400 flex-shrink-0">{formatDate(event.timestamp)}</span>
        <span className="text-[10px] font-mono text-slate-300 flex-shrink-0">#{event.sequence}</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-2 pl-5 space-y-1.5">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
            <div>
              <span className="text-slate-400">Event ID</span>
              <p className="font-mono text-slate-600 truncate">{event.event_id}</p>
            </div>
            <div>
              <span className="text-slate-400">Source</span>
              <p className="text-slate-600">{event.source}</p>
            </div>
            {event.command_id && (
              <div>
                <span className="text-slate-400">Command ID</span>
                <p className="font-mono text-slate-600 truncate">{event.command_id}</p>
              </div>
            )}
            {event.correlation_id && (
              <div>
                <span className="text-slate-400">Correlation ID</span>
                <p className="font-mono text-slate-600 truncate">{event.correlation_id}</p>
              </div>
            )}
            {event.agent_name && (
              <div>
                <span className="text-slate-400">Agent</span>
                <p className="text-slate-600">{event.agent_name}</p>
              </div>
            )}
          </div>
          {Object.keys(event.data).length > 0 && (
            <div>
              <span className="text-[11px] text-slate-400">Data</span>
              <pre className="mt-0.5 text-[11px] font-mono bg-slate-50 rounded p-2 overflow-auto max-h-32">
                {JSON.stringify(event.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default EventLog;
