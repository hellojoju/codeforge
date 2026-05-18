/**
 * RunStatusHeader - 运行状态头部组件
 *
 * 展示连接状态、各状态 WorkUnit 数量、下一步行动建议和刷新按钮
 */

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { statusColor, statusLabel } from "@/lib/ralph-utils"
import { RefreshCw } from "lucide-react"

interface HeaderRunStatus {
  running: number
  needs_review: number
  blocked: number
  accepted: number
  failed: number
  next_action: string | null
}

interface RunStatusHeaderProps {
  connected: boolean
  runStatus: HeaderRunStatus | null
  loading: boolean
  onRefresh: () => void
  className?: string
}

/**
 * 连接状态指示器
 */
function ConnectionIndicator({ connected }: { connected: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-block size-2 rounded-none",
          connected ? "bg-emerald-500" : "bg-red-500"
        )}
        aria-hidden="true"
      />
      <span className="text-sm text-muted-foreground">
        {connected ? "已连接" : "未连接"}
      </span>
    </div>
  )
}

/**
 * 状态计数项
 */
function StatusCountItem({
  status,
  count,
}: {
  status: string
  count: number
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm text-muted-foreground">{statusLabel(status)}</span>
      <span className={cn("text-sm font-medium", statusColor(status))}>
        {count}
      </span>
    </div>
  )
}

/**
 * 状态计数列表
 */
function StatusCounts({ runStatus }: { runStatus: HeaderRunStatus | null }) {
  if (!runStatus) {
    return (
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        暂无数据
      </div>
    )
  }

  const statusItems = [
    { status: "running", count: runStatus.running },
    { status: "needs_review", count: runStatus.needs_review },
    { status: "blocked", count: runStatus.blocked },
    { status: "accepted", count: runStatus.accepted },
    { status: "failed", count: runStatus.failed },
  ]

  return (
    <div className="flex flex-wrap items-center gap-4">
      {statusItems.map((item) => (
        <StatusCountItem
          key={item.status}
          status={item.status}
          count={item.count}
        />
      ))}
    </div>
  )
}

/**
 * 下一步行动建议
 */
function NextAction({ action }: { action: string | null }) {
  if (!action) return null

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">下一步:</span>
      <span className="font-medium text-foreground">{action}</span>
    </div>
  )
}

/**
 * 刷新按钮
 */
function RefreshButton({
  loading,
  onRefresh,
}: {
  loading: boolean
  onRefresh: () => void
}) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onRefresh}
      disabled={loading}
      className="rounded-sm"
    >
      <RefreshCw
        className={cn(
          "size-4 mr-1.5",
          loading && "animate-spin"
        )}
      />
      {loading ? "刷新中..." : "刷新"}
    </Button>
  )
}

/**
 * RunStatusHeader 组件
 *
 * 展示连接状态、各状态 WorkUnit 数量、下一步行动建议和刷新按钮
 */
export function RunStatusHeader({
  connected,
  runStatus,
  loading,
  onRefresh,
  className,
}: RunStatusHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 p-4 border-b border-border bg-card",
        className
      )}
    >
      {/* 第一行：连接状态和刷新按钮 */}
      <div className="flex items-center justify-between">
        <ConnectionIndicator connected={connected} />
        <RefreshButton loading={loading} onRefresh={onRefresh} />
      </div>

      {/* 第二行：状态计数 */}
      <StatusCounts runStatus={runStatus} />

      {/* 第三行：下一步行动建议 */}
      {runStatus?.next_action && (
        <NextAction action={runStatus.next_action} />
      )}
    </div>
  )
}

export default RunStatusHeader
