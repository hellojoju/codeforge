/** 看板列组件 — 展示某一列下的 Feature 卡片。 */
'use client'

import type { Feature, Column } from '@/lib/types'

interface KanbanColumnProps {
  column: Column
  features: Feature[]
}

export function KanbanColumn({ column, features }: KanbanColumnProps) {
  const columnFeatures = features.filter((f) => f.status === column.id)

  return (
    <div className={`flex flex-col gap-3 min-w-[260px] w-[280px] border-t-4 ${column.color} rounded-lg bg-gray-50 dark:bg-gray-800 p-3`}>
      <h3 className="font-semibold text-gray-700 dark:text-gray-200 flex items-center justify-between">
        {column.title}
        <span className="text-xs bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-0.5">
          {columnFeatures.length}
        </span>
      </h3>
      <div className="flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-200px)]">
        {columnFeatures.map((feature) => (
          <FeatureCard key={feature.id} feature={feature} />
        ))}
        {columnFeatures.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">暂无任务</p>
        )}
      </div>
    </div>
  )
}

interface FeatureCardProps {
  feature: Feature
}

export function FeatureCard({ feature }: FeatureCardProps) {
  const statusColors: Record<string, string> = {
    pending: 'bg-gray-100 dark:bg-gray-700 border-gray-300',
    in_progress: 'bg-blue-50 dark:bg-blue-900/30 border-blue-300',
    review: 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-300',
    done: 'bg-green-50 dark:bg-green-900/30 border-green-300',
    blocked: 'bg-red-50 dark:bg-red-900/30 border-red-300',
  }

  return (
    <div className={`rounded-lg border p-3 ${statusColors[feature.status] || statusColors.pending}`}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-gray-800 dark:text-gray-100">{feature.description}</h4>
        <span className="text-xs font-mono text-gray-500 shrink-0">{feature.id}</span>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{feature.description}</p>
      {feature.assigned_instance && (
        <div className="mt-2 flex items-center gap-1">
          <span className="text-xs bg-white/60 dark:bg-gray-600/60 rounded px-1.5 py-0.5 font-mono">
            {feature.assigned_instance}
          </span>
        </div>
      )}
    </div>
  )
}
