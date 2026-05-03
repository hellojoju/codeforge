/**
 * 事件日志 — /ralph/events
 *
 * 实时 WebSocket 事件流查看器，支持暂停、过滤、展开详情
 */

'use client';

import { EventLog } from '@/components/ralph/event-log';

export default function EventsPage() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-5 h-full flex flex-col">
      <div className="mb-5 flex-shrink-0">
        <h1 className="text-lg font-semibold text-slate-900">事件日志</h1>
        <p className="text-sm text-slate-500 mt-0.5">实时 WebSocket 事件流，支持暂停和过滤</p>
      </div>
      <div className="flex-1 min-h-0">
        <EventLog />
      </div>
    </div>
  );
}
