'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { CheckCircle, ChevronDown, ChevronRight, RotateCcw, Circle } from 'lucide-react'

interface PhaseOutputSnapshot {
  phase: string
  label: string
  completed_at: string
  confirmed: boolean
  confirmed_at: string
  summary: string
  detail: Record<string, unknown>
}

interface PhaseHistoryPanelProps {
  phaseOutputs: Record<string, PhaseOutputSnapshot>
  currentPhase: string
  onRollback: (targetPhase: string) => void
}

const PHASE_ORDER = [
  'proactive_analysis',
  'product_def',
  'feature_decompose',
  'deliberation_review',
  'relationship',
  'independent_review',
  'clarification',
  'requirements_ready',
  'technical_route_draft',
  'tool_discovery',
  'execution_plan_ready',
  'complete',
]

export default function PhaseHistoryPanel({
  phaseOutputs,
  currentPhase,
  onRollback,
}: PhaseHistoryPanelProps) {
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null)

  const currentPhaseIndex = PHASE_ORDER.indexOf(currentPhase)
  const phases = PHASE_ORDER.filter((p, idx) => p in phaseOutputs || idx <= currentPhaseIndex)

  if (phases.length === 0) {
    return (
      <div className="text-xs text-slate-400 text-center py-4">
        暂无阶段产出
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {phases.map((phaseKey) => {
        const snapshot = phaseOutputs[phaseKey]
        const isCurrent = phaseKey === currentPhase
        const isPast = !!snapshot
        const isConfirmed = snapshot?.confirmed ?? false
        const isExpanded = expandedPhase === phaseKey

        return (
          <div key={phaseKey}>
            <button
              className={cn(
                'w-full flex items-center gap-2 py-1.5 text-xs transition-colors rounded px-1',
                isCurrent && !isPast && 'text-blue-600 font-medium',
                isPast && 'text-slate-700 hover:bg-slate-50',
                !isCurrent && !isPast && 'text-slate-300',
              )}
              onClick={() => {
                if (isPast) setExpandedPhase(isExpanded ? null : phaseKey)
              }}
            >
              {isConfirmed ? (
                <CheckCircle size={12} className="text-emerald-500 flex-shrink-0" />
              ) : isPast ? (
                <Circle size={12} className="text-amber-500 flex-shrink-0" />
              ) : isCurrent ? (
                <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />
              ) : (
                <Circle size={12} className="text-slate-300 flex-shrink-0" />
              )}
              <span className="flex-1 text-left truncate">
                {snapshot?.label ?? getPhaseLabel(phaseKey)}
              </span>
              {isPast && (
                <>
                  {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </>
              )}
            </button>

            {isExpanded && snapshot && (
              <div className="ml-4 pl-2 border-l border-slate-200 space-y-1.5">
                {snapshot.summary && (
                  <p className="text-[11px] text-slate-500 leading-relaxed">{snapshot.summary}</p>
                )}
                <button
                  className="flex items-center gap-1 rounded border border-amber-200 px-2 py-1 text-[10px] text-amber-700 hover:bg-amber-50 transition-colors"
                  onClick={() => onRollback(phaseKey)}
                >
                  <RotateCcw size={10} /> 回退到本阶段
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function getPhaseLabel(key: string): string {
  const labels: Record<string, string> = {
    proactive_analysis: '主动分析',
    product_def: '产品定义',
    feature_decompose: '功能分解',
    deliberation_review: '结构化审查',
    relationship: '关系分析',
    independent_review: '独立审查',
    clarification: '需求澄清',
    requirements_ready: '需求就绪',
    technical_route_draft: '技术路线',
    tool_discovery: '工具发现',
    execution_plan_ready: '执行计划',
    complete: '完成',
  }
  return labels[key] ?? key
}
