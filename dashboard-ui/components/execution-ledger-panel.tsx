'use client'

import { useEffect, useState } from 'react'
import { fetchExecutionLedger } from '@/lib/api'
import type { ExecutionLedger } from '@/lib/types'
import { LEDGER_STATUS_LABELS, LEDGER_STATUS_COLORS } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function ExecutionLedgerPanel() {
  const [ledger, setLedger] = useState<ExecutionLedger | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchExecutionLedger()
      .then(setLedger)
      .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">执行台账</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 text-sm text-muted-foreground">加载中...</CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">执行台账</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 text-sm text-red-500">{error}</CardContent>
      </Card>
    )
  }

  const summary = ledger?.summary
  const executions = ledger?.executions ?? []
  const summaryItems = summary
    ? [
        { label: '总执行', value: summary.total_executions, color: 'bg-slate-500' },
        { label: '完成', value: summary.completed, color: 'bg-green-500' },
        { label: '失败', value: summary.failed, color: 'bg-red-500' },
        { label: '阻塞', value: summary.blocked, color: 'bg-orange-500' },
        { label: '重试', value: summary.retrying, color: 'bg-yellow-500' },
      ]
    : []

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">执行台账</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {/* Summary bar */}
        {summaryItems.length > 0 && (
          <div className="grid grid-cols-5 gap-2 px-4 pb-3">
            {summaryItems.map((item) => (
              <div key={item.label} className="rounded-md bg-slate-50 p-2 text-center">
                <p className="text-lg font-bold">{item.value}</p>
                <p className="text-[10px] text-muted-foreground">{item.label}</p>
              </div>
            ))}
          </div>
        )}

        {executions.length === 0 ? (
          <div className="px-4 pb-4 text-sm text-muted-foreground">暂无执行记录。</div>
        ) : (
          <ScrollArea className="h-[260px] px-4 pb-4">
            <div className="space-y-2">
              {[...executions].reverse().map((entry, idx) => (
                <div key={`${entry.feature_id}-${idx}`} className="rounded-lg border p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <code className="font-mono text-xs font-medium">{entry.feature_id}</code>
                    <Badge
                      variant="secondary"
                      className={cn(
                        'text-[10px]',
                        entry.status === 'blocked' || entry.status === 'failed'
                          ? 'bg-red-100 text-red-700'
                          : entry.status === 'retrying'
                            ? 'bg-yellow-100 text-yellow-700'
                            : entry.status === 'completed'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-blue-100 text-blue-700',
                      )}
                    >
                      {LEDGER_STATUS_LABELS[entry.status]}
                    </Badge>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                    <span>Agent: {entry.agent_id || '-'}</span>
                    <span>{entry.started_at ? new Date(entry.started_at).toLocaleString() : '-'}</span>
                  </div>
                  {entry.error && (
                    <p className="mt-1 text-[11px] text-red-500 truncate">{entry.error}</p>
                  )}
                  {entry.files_changed && entry.files_changed.length > 0 && (
                    <p className="mt-0.5 text-[10px] text-muted-foreground truncate">
                      变更: {entry.files_changed.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
