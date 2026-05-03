/** 实时日志流组件 — 展示 Event 实时滚动。 */
'use client'

import type { DashboardEvent } from '@/lib/types'

interface LogStreamProps {
  events: DashboardEvent[]
}

export function LogStream({ events }: LogStreamProps) {
  const eventIcons: Record<string, string> = {
    agent_status_changed: '🔄',
    agent_log: '📋',
    feature_completed: '✅',
    error_occurred: '❌',
    pm_decision: '👑',
  }

  return (
    <div className="p-3">
      <div className="overflow-y-auto max-h-[200px] space-y-1 font-mono text-xs">
        {events.length === 0 && (
          <p className="text-gray-400 text-center py-4">等待事件...</p>
        )}
        {events.slice(-50).reverse().map((event, i) => (
          <div key={event.event_id || i} className="flex items-start gap-2 py-1 border-b border-gray-100 dark:border-gray-700 last:border-0">
            <span>{eventIcons[event.type] || '📌'}</span>
            <span className="text-gray-500 shrink-0">{event.timestamp?.slice(11, 19) || '--:--:--'}</span>
            <span className="text-blue-600 dark:text-blue-400 shrink-0 w-[80px] truncate">{(event.payload.agent_id as string) || '-'}</span>
            <span className="text-gray-700 dark:text-gray-300">{(event.payload.message as string) || event.type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
