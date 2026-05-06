'use client'

import { useMemo, useState } from 'react'
import { useExecutionLedger } from '@/lib/hooks/useDashboardQueries'
import { LEDGER_STATUS_LABELS, type LedgerEntryStatus } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function ExecutionLedgerPanel() {
  const [featureId, setFeatureId] = useState('')
  const [agentId, setAgentId] = useState('')
  const [status, setStatus] = useState<LedgerEntryStatus | ''>('')
  const { data: ledger, isLoading, error } = useExecutionLedger({
    featureId: featureId || undefined,
    agentId: agentId || undefined,
    status: status || undefined,
  })

  if (isLoading) {
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
        <CardContent className="px-4 pb-4 text-sm text-red-500">
          {error instanceof Error ? error.message : '加载失败'}
        </CardContent>
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

  const executions = ledger?.executions ?? []
  const featureOptions = useMemo(
    () => Array.from(new Set(executions.map((e) => e.feature_id).filter(Boolean))).sort(),
    [executions],
  )
  const agentOptions = useMemo(
    () => Array.from(new Set(executions.map((e) => e.agent_id).filter(Boolean))).sort(),
    [executions],
  )

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">执行台账</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="grid grid-cols-3 gap-2 px-4 pb-3">
          <select
            value={featureId}
            onChange={(e) => setFeatureId(e.target.value)}
            className="h-8 rounded border px-2 text-xs"
          >
            <option value="">全部 Feature</option>
            {featureOptions.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <select
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            className="h-8 rounded border px-2 text-xs"
          >
            <option value="">全部 Agent</option>
            {agentOptions.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as LedgerEntryStatus | '')}
            className="h-8 rounded border px-2 text-xs"
          >
            <option value="">全部状态</option>
            <option value="started">已启动</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="retrying">重试中</option>
            <option value="blocked">已阻塞</option>
          </select>
        </div>

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
