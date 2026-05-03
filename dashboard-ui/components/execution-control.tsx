'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useDashboardStore } from '@/lib/store'
import { EXECUTION_STATUS_LABELS, EXECUTION_STATUS_COLORS } from '@/lib/types'
import { Play, Square, Loader2, AlertTriangle } from 'lucide-react'

export function ExecutionControl() {
  const { executionStatus, executionError, startExecution, stopExecution } = useDashboardStore()

  const isRunning = executionStatus === 'running' || executionStatus === 'starting'
  const label = EXECUTION_STATUS_LABELS[executionStatus]
  const color = EXECUTION_STATUS_COLORS[executionStatus]

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <Badge variant={isRunning ? 'default' : 'secondary'} className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${color} ${isRunning ? 'animate-pulse' : ''}`} />
          {label}
        </Badge>
        {executionStatus === 'starting' && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {!isRunning ? (
        <Button
          size="sm"
          variant="default"
          onClick={startExecution}
          className="gap-1"
        >
          <Play className="h-3.5 w-3.5" />
          启动开发
        </Button>
      ) : (
        <Button
          size="sm"
          variant="destructive"
          onClick={stopExecution}
          className="gap-1"
        >
          <Square className="h-3.5 w-3.5" />
          停止
        </Button>
      )}

      {executionError && (
        <div className="flex items-center gap-1 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" />
          <span>{executionError}</span>
        </div>
      )}
    </div>
  )
}
