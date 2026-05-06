/** Agent 状态面板增强版 — 展示详细 Agent 状态、静默检测、当前活动。 */
'use client'

import { useState } from 'react'
import type { AgentWithSilence } from '@/lib/types'
import {
  SILENCE_LEVEL_LABELS,
  SILENCE_LEVEL_COLORS,
  AGENT_STATUS_LABELS,
} from '@/lib/types'
import { useAgents, useInterruptAgent, useSendAgentMessage } from '@/lib/hooks/useDashboardQueries'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  MessageSquare,
  StopCircle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
} from 'lucide-react'

const ROLE_ICONS: Record<string, string> = {
  backend: '⚙️',
  frontend: '🖥️',
  database: '🗄️',
  qa: '🧪',
  security: '🔒',
  ui: '🎨',
  docs: '📝',
  architect: '📐',
  pm: '👑',
}

const STATUS_DOT: Record<string, string> = {
  idle: 'bg-green-400',
  busy: 'bg-blue-500 animate-pulse',
  paused: 'bg-yellow-400',
  error: 'bg-red-500',
  waiting_approval: 'bg-orange-500 animate-pulse',
  waiting_pm: 'bg-purple-500 animate-pulse',
}

export function AgentStatusPanel() {
  const { data: agentsData } = useAgents()
  const agents = agentsData?.agents || []
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({})

  const roleGroups = agents.reduce<Record<string, AgentWithSilence[]>>((acc, a) => {
    const role = a.role || 'unknown'
    if (!acc[role]) acc[role] = []
    acc[role].push(a)
    return acc
  }, {})

  const toggleRole = (role: string) => {
    setExpandedRoles((prev) => ({ ...prev, [role]: !(prev[role] ?? true) }))
  }

  const qc = useQueryClient()
  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ['agents'] })
    qc.invalidateQueries({ queryKey: ['events'] })
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Agent 集群监控</CardTitle>
          <Button variant="ghost" size="sm" onClick={refreshAll} className="h-6 w-6 p-0">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-2">
          <div className="space-y-2">
            {Object.entries(roleGroups).map(([role, instances]) => {
              const expanded = expandedRoles[role] ?? true
              return (
                <div key={role} className="border rounded-md">
                  <button
                    className="flex items-center gap-2 w-full px-2 py-1.5 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-t-md"
                    onClick={() => toggleRole(role)}
                  >
                    {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    <span>{ROLE_ICONS[role] || '🤖'}</span>
                    <span className="capitalize">{role}</span>
                    <Badge variant="secondary" className="ml-auto text-[10px] px-1.5 py-0 h-4">
                      {instances.length}
                    </Badge>
                  </button>

                  {expanded && (
                    <div className="px-2 pb-2 space-y-1.5">
                      {instances.map((agent) => (
                        <AgentCard key={agent.id} agent={agent} />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}

            {agents.length === 0 && (
              <p className="text-center text-xs text-muted-foreground py-6">
                暂无 Agent 实例
              </p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

function AgentCard({ agent }: { agent: AgentWithSilence }) {
  const interruptMutation = useInterruptAgent()
  const sendMessageMutation = useSendAgentMessage()
  const [showActions, setShowActions] = useState(false)

  const status = agent.status as string
  const silence = agent.silence_status
  const process = agent.process_status
  const role = agent.role || 'unknown'

  const silenceLevel = silence?.level ?? 'active'
  const isSilentWarning = silenceLevel !== 'active'

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}m${s}s`
  }

  const currentActivity = agent.current_activity || null

  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-md p-2 text-xs space-y-1.5">
      {/* 标题行 */}
      <div className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${STATUS_DOT[status] || STATUS_DOT.idle}`} />
        <span className="font-mono font-medium truncate flex-1">{agent.id}</span>
        <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
          {AGENT_STATUS_LABELS[status as keyof typeof AGENT_STATUS_LABELS] || status}
        </Badge>
      </div>

      {/* 静默状态 */}
      {isSilentWarning && silence && (
        <div className={`flex items-center gap-1 ${SILENCE_LEVEL_COLORS[silenceLevel]}`}>
          <AlertTriangle className="h-3 w-3" />
          <span>{SILENCE_LEVEL_LABELS[silenceLevel]}</span>
          <span className="text-muted-foreground ml-auto">
            <Clock className="h-3 w-3 inline mr-0.5" />
            {formatTime(silence.idle_seconds)}
          </span>
        </div>
      )}

      {/* 进程信息 */}
      {process && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Cpu className="h-3 w-3" />
          <span>PID: {process.pid ?? '-'}</span>
          <span className={process.running ? 'text-green-500' : 'text-gray-400'}>
            {process.running ? '运行中' : '已停止'}
          </span>
          {process.exit_code != null && (
            <span>退出码: {process.exit_code}</span>
          )}
        </div>
      )}

      {/* 当前活动 */}
      {currentActivity && (
        <div className="text-muted-foreground truncate">
          {ROLE_ICONS[role] || '🤖'} {currentActivity}
        </div>
      )}

      {/* 操作按钮 */}
      <div>
        <button
          className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-0.5"
          onClick={() => setShowActions(!showActions)}
        >
          {showActions ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          操作
        </button>

        {showActions && (
          <div className="flex gap-1 mt-1">
            <Button
              variant="outline"
              size="sm"
              className="h-6 text-[10px] px-2 gap-1"
              onClick={() => interruptMutation.mutate({ agentId: agent.id })}
            >
              <StopCircle className="h-3 w-3" />
              中断
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-6 text-[10px] px-2 gap-1"
              onClick={() => {
                const msg = prompt('输入要发送给 Agent 的消息:')
                if (msg) sendMessageMutation.mutate({ agentId: agent.id, message: msg })
              }}
            >
              <MessageSquare className="h-3 w-3" />
              发消息
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
