'use client'

import { cn } from '@/lib/utils'
import {
  DeliberationRound,
  DeliberationFinding,
  DeliberationDecision,
  DIMENSION_DISPLAY_NAMES,
} from '@/lib/ralph-types'

interface DeliberationFindingsPanelProps {
  rounds: DeliberationRound[]
  showTrigger?: boolean
  onTrigger?: () => void
  onDecide: (findingId: string, decision: DeliberationDecision, reason?: string) => void
  loading?: boolean
}

const SEVERITY_COLORS: Record<string, string> = {
  high: 'bg-rose-100 text-rose-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-slate-100 text-slate-500',
}

const SEVERITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const DECISION_LABELS: Record<DeliberationDecision, string> = {
  pending: '待裁决',
  accept: '已采纳',
  reject: '已拒绝',
  defer: '已延后',
}

export default function DeliberationFindingsPanel({ rounds, showTrigger, onTrigger, onDecide, loading }: DeliberationFindingsPanelProps) {
  if (rounds.length === 0) {
    return (
      <div className="rounded border border-slate-200 p-3">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">多维审查</h3>
        {showTrigger ? (
          <>
            <p className="text-xs text-slate-400 mb-3">四个审查维度将并行分析功能完整性</p>
            <button
              className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs hover:bg-blue-500 transition-colors disabled:opacity-50"
              onClick={onTrigger}
              disabled={loading}
            >运行多维审查</button>
          </>
        ) : (
          <p className="text-xs text-slate-400">尚未触发审查</p>
        )}
      </div>
    )
  }

  const latestRound = rounds[rounds.length - 1]
  const pendingCount = (latestRound.findings || []).filter(f => f.pm_decision === 'pending').length
  const highPending = (latestRound.findings || []).filter(f => f.severity === 'high' && f.pm_decision === 'pending').length

  return (
    <div className="rounded border border-slate-200 p-3">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-700">多维审查</h3>
        {pendingCount > 0 && (
          <span className="text-[10px] text-amber-600">
            {pendingCount} 条待裁决{highPending > 0 ? `（${highPending} 条高优）` : ''}
          </span>
        )}
      </div>

      {/* PM Summary */}
      {latestRound.pm_summary && (
        <p className="mb-3 text-xs text-slate-500 leading-relaxed">{latestRound.pm_summary}</p>
      )}

      {/* Findings grouped by dimension */}
      <div className="space-y-3">
        {groupByDimension(latestRound.findings || []).map(({ dimension, findings }) => (
          <div key={dimension} className="space-y-2">
            <h4 className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              {DIMENSION_DISPLAY_NAMES[dimension] ?? dimension}
              <span className="ml-1 font-normal text-slate-400">({findings.length})</span>
            </h4>
            {findings.map(finding => (
              <DeliberationFindingCard
                key={finding.finding_id}
                finding={finding}
                onDecide={onDecide}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function groupByDimension(findings: DeliberationFinding[]) {
  const groups: { dimension: string; findings: DeliberationFinding[] }[] = []
  for (const f of findings) {
    let group = groups.find(g => g.dimension === f.dimension)
    if (!group) {
      group = { dimension: f.dimension, findings: [] }
      groups.push(group)
    }
    group.findings.push(f)
  }
  return groups
}

interface DeliberationFindingCardProps {
  finding: DeliberationFinding
  onDecide: (findingId: string, decision: DeliberationDecision, reason?: string) => void
}

function DeliberationFindingCard({ finding, onDecide }: DeliberationFindingCardProps) {
  const decided = finding.pm_decision !== 'pending'

  return (
    <div className={cn(
      'rounded border p-2 text-xs',
      decided ? 'border-slate-100 bg-slate-50' : 'border-amber-200 bg-amber-50/50'
    )}>
      <div className="flex items-center justify-between mb-1">
        <span className={cn('rounded px-1.5 py-0.5 text-[10px]', SEVERITY_COLORS[finding.severity])}>
          {SEVERITY_LABELS[finding.severity]}
        </span>
        <span className="text-[10px] text-slate-400">{DECISION_LABELS[finding.pm_decision]}</span>
      </div>

      <p className="text-slate-700 leading-relaxed mb-1">{finding.finding}</p>

      {finding.suggested_change && (
        <p className="text-blue-600 leading-relaxed mb-1">建议：{finding.suggested_change}</p>
      )}

      {finding.evidence && (
        <p className="text-slate-400 text-[11px] leading-relaxed mb-1">依据：{finding.evidence}</p>
      )}

      {finding.pm_reason && (
        <p className="text-slate-500 text-[11px] leading-relaxed">裁决理由：{finding.pm_reason}</p>
      )}

      {!decided && finding.severity === 'high' && (
        <div className="mt-2 flex gap-1">
          <button
            className="rounded border border-emerald-200 px-2 py-1 text-[10px] text-emerald-700 hover:bg-emerald-50"
            onClick={() => onDecide(finding.finding_id, 'accept')}
          >采纳</button>
          <button
            className="rounded border border-rose-200 px-2 py-1 text-[10px] text-rose-700 hover:bg-rose-50"
            onClick={() => onDecide(finding.finding_id, 'reject')}
          >拒绝</button>
          <button
            className="rounded border border-slate-300 px-2 py-1 text-[10px] text-slate-600 hover:bg-slate-50"
            onClick={() => onDecide(finding.finding_id, 'defer')}
          >延后</button>
        </div>
      )}

      {!decided && finding.severity !== 'high' && (
        <div className="mt-2 flex gap-1">
          {(['accept', 'reject', 'defer'] as const).map(d => (
            <button
              key={d}
              className="rounded border border-slate-200 px-2 py-1 text-[10px] text-slate-500 hover:bg-white"
              onClick={() => onDecide(finding.finding_id, d)}
            >{DECISION_LABELS[d]}</button>
          ))}
        </div>
      )}
    </div>
  )
}
