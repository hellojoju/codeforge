'use client'

import { ArrowRight, RotateCcw } from 'lucide-react'

interface PhaseConfirmationCardProps {
  phaseLabel: string
  summary: string
  onConfirm: () => void
  onRollback: () => void
  loading?: boolean
}

export default function PhaseConfirmationCard({
  phaseLabel,
  summary,
  onConfirm,
  onRollback,
  loading,
}: PhaseConfirmationCardProps) {
  return (
    <div className="rounded border border-amber-200 bg-amber-50/50 p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-700 bg-amber-100 rounded px-1.5 py-0.5">
          {phaseLabel} 已完成
        </span>
      </div>
      {summary && (
        <p className="text-xs text-slate-600 leading-relaxed mb-2">{summary}</p>
      )}
      <div className="flex gap-2">
        <button
          className="flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
          onClick={onConfirm}
          disabled={loading}
        >
          <ArrowRight size={12} /> 确认并进入下一阶段
        </button>
        <button
          className="flex items-center gap-1.5 rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          onClick={onRollback}
          disabled={loading}
        >
          <RotateCcw size={12} /> 回退修订
        </button>
      </div>
    </div>
  )
}
