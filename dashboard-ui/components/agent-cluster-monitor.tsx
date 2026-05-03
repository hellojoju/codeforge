'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useDashboardStore } from '@/lib/store'
import type { AgentWithSilence } from '@/lib/types'
import { SILENCE_LEVEL_LABELS, SILENCE_LEVEL_COLORS } from '@/lib/types'
import { Pause, RotateCcw, Zap, Cpu, Clock, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'

const ROLE_LABELS: Record<string, string> = {
  backend: '后端开发',
  backend_dev: '后端开发',
  frontend: '前端开发',
  frontend_dev: '前端开发',
  qa: 'QA 测试',
  qa_tester: 'QA 测试',
  architect: '架构师',
  database: '数据库专家',
  database_expert: '数据库专家',
  security: '安全审查',
  security_reviewer: '安全审查',
  ui_designer: 'UI 设计师',
  docs: '文档撰写',
  docs_writer: '文档撰写',
  product: '产品经理',
  product_manager: '产品经理',
}

const STATUS_LABELS: Record<string, string> = {
  idle: '空闲',
  busy: '运行中',
  paused: '已暂停',
  error: '错误',
  waiting_approval: '等待审批',
  waiting_pm: '等待PM指令',
}

const STATUS_COLORS: Record<string, string> = {
  idle: 'bg-gray-400',
  busy: 'bg-green-500',
  paused: 'bg-yellow-500',
  error: 'bg-red-500',
  waiting_approval: 'bg-orange-500',
  waiting_pm: 'bg-blue-500',
}

function AgentRow({ agent }: { agent: AgentWithSilence }) {
  const { pause, resume, interruptAgent } = useDashboardStore()
  const [expanded, setExpanded] = useState(false)

  const roleLabel = ROLE_LABELS[agent.role] || agent.role
  void roleLabel
  const statusLabel = STATUS_LABELS[agent.status] || agent.status
  const statusColor = STATUS_COLORS[agent.status] || 'bg-gray-400'
  const isRunning = agent.status === 'busy'
  const isPaused = agent.status === 'paused'

  const silence = agent.silence_status
  const process = agent.process_status
  const silenceLevel = silence?.level || 'active'
  const silenceLabel = SILENCE_LEVEL_LABELS[silenceLevel]
  const silenceColor = SILENCE_LEVEL_COLORS[silenceLevel]

  const currentTask = agent.current_feature
    ? `处理: ${agent.current_feature}`
    : agent.status === 'idle'
      ? '等待分配'
      : '待命中'

  const initials = (agent.role || 'AG').substring(0, 2).toUpperCase()

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 py-1.5">
        <button
          onClick={() => setExpanded(!expanded)}
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>

        <Avatar className="h-6 w-6">
          <AvatarFallback className="text-[10px]">{initials}</AvatarFallback>
        </Avatar>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-sm">
            <span className="font-medium truncate">#{agent.instance_number}</span>
            <span className={`h-2 w-2 rounded-full ${statusColor} ${isRunning ? 'animate-pulse' : ''}`} />
            <span className="text-muted-foreground text-xs">{statusLabel}</span>
          </div>
          <p className="text-xs text-muted-foreground truncate">{currentTask}</p>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {isRunning && (
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6"
              onClick={() => pause(agent.id)}
            >
              <Pause className="h-3 w-3" />
            </Button>
          )}
          {isPaused && (
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6"
              onClick={() => resume(agent.id)}
            >
              <RotateCcw className="h-3 w-3" />
            </Button>
          )}
          {(isRunning || isPaused) && (
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6 text-destructive hover:text-destructive"
              onClick={() => interruptAgent(agent.id)}
            >
              <Zap className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="ml-6 pl-4 border-l text-xs space-y-1.5 py-1">
          {silence && (
            <div className="flex items-center gap-1.5">
              <AlertTriangle className={`h-3 w-3 ${silenceColor}`} />
              <span>静默: {silenceLabel}</span>
              <span className="text-muted-foreground">({silence.idle_seconds}s)</span>
            </div>
          )}
          {process?.pid && (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Cpu className="h-3 w-3" />
              <span>PID: {process.pid}</span>
              <span className={process.running ? 'text-green-500' : 'text-red-500'}>
                {process.running ? '运行中' : '已终止'}
              </span>
            </div>
          )}
          {silence?.last_activity && (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>最后活动: {new Date(silence.last_activity).toLocaleTimeString()}</span>
            </div>
          )}
          <div className="text-muted-foreground">
            已完成: {agent.total_tasks_completed} 任务
          </div>
        </div>
      )}
    </div>
  )
}

export function AgentClusterMonitor() {
  const { agents, fetchAgents } = useDashboardStore()

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const grouped = agents.reduce<Record<string, AgentWithSilence[]>>((acc, agent) => {
    const role = agent.role || 'unknown'
    if (!acc[role]) acc[role] = []
    acc[role].push(agent)
    return acc
  }, {})

  if (agents.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Agent 集群</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">暂无 Agent 实例</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Agent 集群</CardTitle>
          <Badge variant="secondary" className="text-xs">
            {agents.length} 实例
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[400px] px-3">
          <div className="space-y-3 pb-3">
            {Object.entries(grouped).map(([role, roleAgents], index) => (
              <div key={role}>
                {index > 0 && <Separator className="my-2" />}
                <div className="space-y-0.5">
                  <div className="text-xs font-medium text-muted-foreground px-1 py-1">
                    {ROLE_LABELS[role] || role} ({roleAgents.length})
                  </div>
                  {roleAgents.map((agent) => (
                    <AgentRow key={agent.id} agent={agent} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
