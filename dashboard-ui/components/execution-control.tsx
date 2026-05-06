'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useExecutionStatus, useStartExecution, useStopExecution } from '@/lib/hooks/useDashboardQueries'
import { EXECUTION_STATUS_LABELS, EXECUTION_STATUS_COLORS } from '@/lib/types'
import { Play, Square, Loader2, AlertTriangle } from 'lucide-react'

export function ExecutionControl() {
  const { data: execStatus } = useExecutionStatus()
  const startMutation = useStartExecution()
  const stopMutation = useStopExecution()

  const status = execStatus?.status || 'idle'
  const error = execStatus?.error
  const isRunning = status === 'running' || status === 'starting'
  const label = EXECUTION_STATUS_LABELS[status]
  const color = EXECUTION_STATUS_COLORS[status]

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <Badge variant={isRunning ? 'default' : 'secondary'} className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${color} ${isRunning ? 'animate-pulse' : ''}`} />
          {label}
        </Badge>
        {status === 'starting' && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {!isRunning ? (
        <Button
          size="sm"
          variant="default"
          onClick={() => startMutation.mutate()}
          disabled={startMutation.isPending}
          className="gap-1"
        >
          {startMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          启动开发
        </Button>
      ) : (
        <Button
          size="sm"
          variant="destructive"
          onClick={() => stopMutation.mutate()}
          disabled={stopMutation.isPending}
          className="gap-1"
        >
          {stopMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Square className="h-3.5 w-3.5" />}
          停止
        </Button>
      )}

      {error && (
        <div className="flex items-center gap-1 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
