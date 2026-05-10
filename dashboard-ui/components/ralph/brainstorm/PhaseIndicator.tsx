import { CheckCircle, ArrowRight } from 'lucide-react'

const PHASES = [
  { key: 'product_def', label: '产品定义', icon: '🎯' },
  { key: 'feature_decompose', label: '功能分解', icon: '🔍' },
  { key: 'relationship', label: '关系分析', icon: '🔗' },
  { key: 'independent_review', label: '独立审查', icon: '✅' },
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
    <div className={`flex items-center gap-2 px-4 py-3 bg-slate-900/50 border-b border-slate-700 ${className}`}>
      {PHASES.map((phase, i) => {
        const isActive = i === currentIndex
        const isDone = i < currentIndex || isComplete

        return (
          <div key={phase.key} className="flex items-center">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
              ${isDone ? 'bg-emerald-500/20 text-emerald-400' : ''}
              ${isActive ? 'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/50' : ''}
              ${!isActive && !isDone ? 'text-slate-500' : ''}
            `}>
              <span>{phase.icon}</span>
              <span>{phase.label}</span>
              {isDone && <CheckCircle className="w-3.5 h-3.5" />}
            </div>
            {i < PHASES.length - 1 && (
              <ArrowRight className={`w-4 h-4 mx-1 ${isDone ? 'text-emerald-500' : 'text-slate-600'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
