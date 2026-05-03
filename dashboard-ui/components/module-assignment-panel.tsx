/** 模块分配面板 — 展示各角色 Agent 的模块分配、接口契约和依赖关系。 */
'use client'

import { useDashboardStore } from '@/lib/store'
import type { ModuleAssignment } from '@/lib/types'
import { Badge } from '@/components/ui/badge'

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  in_progress: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  blocked: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待分配',
  in_progress: '开发中',
  blocked: '已阻塞',
  completed: '已完成',
}

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

export function ModuleAssignmentPanel() {
  const moduleAssignments = useDashboardStore((s) => s.moduleAssignments)

  if (moduleAssignments.length === 0) {
    return null
  }

  const roleGroups = moduleAssignments.reduce<Record<string, ModuleAssignment[]>>((acc, m) => {
    if (!acc[m.role]) acc[m.role] = []
    acc[m.role].push(m)
    return acc
  }, {})

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border p-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">模块分配</h3>
      <div className="space-y-3">
        {Object.entries(roleGroups).map(([role, modules]) => (
          <div key={role}>
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-sm">{ROLE_ICONS[role] || '🤖'}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{role}</span>
            </div>
            <div className="space-y-1.5 pl-6">
              {modules.map((mod) => (
                <ModuleCard key={mod.module_id} assignment={mod} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ModuleCard({ assignment }: { assignment: ModuleAssignment }) {
  const agents = useDashboardStore((s) => s.agents)
  const assignedAgent = agents.find((a) => a.id === assignment.assigned_agent_id)
  const statusColor = STATUS_COLORS[assignment.status] || STATUS_COLORS.pending
  const statusLabel = STATUS_LABELS[assignment.status] || assignment.status

  return (
    <div className="border rounded-md p-2.5 bg-gray-50 dark:bg-gray-900/50 text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-medium text-gray-800 dark:text-gray-100 truncate">
            {assignment.module_name}
          </span>
          <Badge variant="outline" className={statusColor}>{statusLabel}</Badge>
        </div>
        <span className="text-gray-500 dark:text-gray-400 shrink-0" title={assignedAgent?.id || '未分配'}>
          {assignedAgent ? `→ ${assignedAgent.id.slice(0, 8)}` : '→ 未分配'}
        </span>
      </div>
      {assignment.description && (
        <p className="text-gray-500 dark:text-gray-400 mt-1 line-clamp-1">{assignment.description}</p>
      )}
      {assignment.dependencies.length > 0 && (
        <div className="flex items-center gap-1 mt-1.5">
          <span className="text-gray-400">依赖:</span>
          {assignment.dependencies.map((dep) => (
            <span key={dep} className="bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded px-1.5 py-0.5 text-[10px]">
              {dep}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
