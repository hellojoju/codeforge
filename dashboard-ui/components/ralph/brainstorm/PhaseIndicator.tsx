import { CheckCircle, ArrowRight } from 'lucide-react'

const PHASES = [
  { key: 'proactive_analysis', label: '主动分析', icon: '💡' },
  { key: 'product_def', label: '产品定义', icon: '🎯' },
  { key: 'feature_decompose', label: '功能分解', icon: '🔍' },
  { key: 'deliberation_review', label: '结构化审查', icon: '🧭' },
  { key: 'relationship', label: '关系分析', icon: '🔗' },
  { key: 'independent_review', label: '独立审查', icon: '✅' },
  { key: 'requirements_ready', label: '需求就绪', icon: '📄' },
  { key: 'technical_route_draft', label: '技术路线', icon: '🗺️' },
  { key: 'tool_discovery', label: '工具发现', icon: '🔍' },
  { key: 'execution_plan_ready', label: '执行计划', icon: '📋' },
  { key: 'complete', label: '完成', icon: '🎉' },
]

interface PhaseIndicatorProps {
  currentPhase: string
  className?: string
}

export default function PhaseIndicator({ currentPhase, className = '' }: PhaseIndicatorProps) {
  const currentIndex = PHASES.findIndex(p => p.key === currentPhase)
  const isComplete = currentPhase === 'complete'

  return (
    <div className={`flex items-center gap-2 px-4 py-3 bg-white border-b border-slate-200 ${className}`}>
      {PHASES.map((phase, i) => {
        const isActive = i === currentIndex
        const isDone = i < currentIndex || isComplete

        return (
          <div key={phase.key} className="flex items-center">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
              ${isDone ? 'bg-emerald-50 text-emerald-600' : ''}
              ${isActive ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : ''}
              ${!isActive && !isDone ? 'text-slate-400' : ''}
            `}>
              <span>{phase.icon}</span>
              <span>{phase.label}</span>
              {isDone && <CheckCircle className="w-3.5 h-3.5" />}
            </div>
            {i < PHASES.length - 1 && (
              <ArrowRight className={`w-4 h-4 mx-1 ${isDone ? 'text-emerald-400' : 'text-slate-300'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
