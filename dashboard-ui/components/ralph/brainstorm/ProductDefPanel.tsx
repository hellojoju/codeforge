'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Check, X, Edit2, RefreshCw } from 'lucide-react'

interface ProductDefFinding {
  finding_id: string
  dimension: string
  dimension_name: string
  content: string
  suggestions: string[]
  questions: string[]
  confidence: number
  status: string
  user_revision: string
  pm_decision: string
  pm_reason: string
}

interface ProductDefRound {
  round_id: string
  findings: ProductDefFinding[]
  summary: string
  created_at: string
  confirmed_at: string
}

interface ProductDefPanelProps {
  rounds: ProductDefRound[]
  loadingProgress?: import('@/lib/ralph-types').ProductDefProgress
  onConfirm: (findingId: string, decision: 'accept' | 'reject' | 'defer', reason?: string, revision?: string) => void
}

const DIMENSION_ICONS: Record<string, string> = {
  product_vision: '🎯',
  user_experience: '🎨',
  technical_feasibility: '⚙️',
  business_value: '💰',
}

export default function ProductDefPanel({ rounds, loadingProgress, onConfirm }: ProductDefPanelProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const latest = rounds.length > 0 ? rounds[rounds.length - 1] : null

  // Show loading placeholders when no rounds yet but progress exists
  if (!latest && loadingProgress) {
    return <LoadingProgressView progress={loadingProgress} />
  }

  if (!latest) return null

  const acceptedCount = latest.findings.filter(f => f.pm_decision === 'accept').length
  const total = latest.findings.length
  const progress = total > 0 ? Math.round((acceptedCount / total) * 100) : 0

  const handleDecision = (findingId: string, decision: 'accept' | 'reject' | 'defer') => {
    if (decision === 'defer') {
      const finding = latest.findings.find(f => f.finding_id === findingId)
      if (finding) {
        setEditingId(findingId)
        setEditText(finding.content)
      }
      return
    }
    onConfirm(findingId, decision)
  }

  const handleSaveEdit = () => {
    if (editingId && editText.trim()) {
      onConfirm(editingId, 'defer', '', editText.trim())
      setEditingId(null)
      setEditText('')
    }
  }

  return (
    <div className="rounded border border-slate-200 p-3">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-700">多 Agent 产品分析</h3>
        <span className="text-[10px] text-slate-400">{progress}% 已确认</span>
      </div>

      {/* Progress bar */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[10px] text-slate-400">{acceptedCount}/{total}</span>
      </div>

      {/* Summary */}
      {latest.summary && (
        <p className="mb-3 text-xs text-slate-500 leading-relaxed whitespace-pre-line">{latest.summary}</p>
      )}

      {/* Findings by dimension */}
      <div className="space-y-3">
        {latest.findings.map(finding => (
          <FindingCard
            key={finding.finding_id}
            finding={finding}
            isEditing={editingId === finding.finding_id}
            editText={editText}
            onEditTextChange={setEditText}
            onSaveEdit={handleSaveEdit}
            onCancelEdit={() => { setEditingId(null); setEditText('') }}
            onDecision={handleDecision}
          />
        ))}
      </div>

      {/* Questions section */}
      {latest.findings.some(f => f.questions.length > 0) && (
        <div className="mt-4">
          <h4 className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-2">待确认问题</h4>
          <div className="space-y-2">
            {latest.findings.flatMap(f =>
              f.questions.map((q, i) => (
                <div key={`${f.finding_id}-q-${i}`} className="rounded border border-amber-200 bg-amber-50/50 p-2 text-xs">
                  <p className="font-medium text-slate-700 mb-1">{q}</p>
                  <p className="text-[10px] text-slate-400">来自: {f.dimension_name}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface FindingCardProps {
  finding: ProductDefFinding
  isEditing: boolean
  editText: string
  onEditTextChange: (v: string) => void
  onSaveEdit: () => void
  onCancelEdit: () => void
  onDecision: (findingId: string, decision: 'accept' | 'reject' | 'defer') => void
}

function FindingCard({ finding, isEditing, editText, onEditTextChange, onSaveEdit, onCancelEdit, onDecision }: FindingCardProps) {
  const isConfirmed = finding.pm_decision !== 'pending'

  const borderColor = isConfirmed
    ? finding.pm_decision === 'accept' ? 'border-emerald-200 bg-emerald-50'
    : finding.pm_decision === 'reject' ? 'border-rose-200 bg-rose-50'
    : 'border-blue-200 bg-blue-50'
    : 'border-slate-200 bg-white'

  const icon = DIMENSION_ICONS[finding.dimension] || '📋'

  return (
    <div className={cn('rounded border p-2.5 text-xs', borderColor)}>
      {/* Dimension header */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="font-medium text-slate-700">
          <span className="mr-1">{icon}</span>
          {finding.dimension_name}
        </span>
        <span className={cn(
          'rounded px-1.5 py-0.5 text-[10px]',
          isConfirmed
            ? finding.pm_decision === 'accept' ? 'bg-emerald-100 text-emerald-700'
            : finding.pm_decision === 'reject' ? 'bg-rose-100 text-rose-700'
            : 'bg-blue-100 text-blue-700'
            : 'bg-amber-100 text-amber-700'
        )}>
          {isConfirmed
            ? finding.pm_decision === 'accept' ? '已接受'
            : finding.pm_decision === 'reject' ? '已拒绝'
            : '已修改'
            : '待确认'}
        </span>
      </div>

      {/* Content */}
      {isEditing ? (
        <div className="space-y-2">
          <textarea
            className="w-full rounded border border-slate-300 p-1.5 text-xs resize-none"
            rows={3}
            value={editText}
            onChange={e => onEditTextChange(e.target.value)}
          />
          <div className="flex gap-1.5">
            <button
              className="rounded bg-blue-600 px-2 py-1 text-[10px] text-white hover:bg-blue-500"
              onClick={onSaveEdit}
            >保存</button>
            <button
              className="rounded border border-slate-300 px-2 py-1 text-[10px] text-slate-600 hover:bg-slate-50"
              onClick={onCancelEdit}
            >取消</button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-slate-600 leading-relaxed">{finding.content}</p>

          {finding.suggestions.length > 0 && (
            <div className="mt-1.5">
              <p className="text-[10px] font-semibold text-slate-500 mb-1">建议:</p>
              <ul className="space-y-0.5">
                {finding.suggestions.map((s, i) => (
                  <li key={i} className="text-[11px] text-slate-600">• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {finding.user_revision && (
            <p className="mt-1.5 text-blue-600 leading-relaxed">修改后: {finding.user_revision}</p>
          )}

          {/* Action buttons */}
          {!isConfirmed && (
            <div className="mt-2 flex gap-1">
              <button
                className="flex items-center gap-1 rounded border border-emerald-200 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-50"
                onClick={() => onDecision(finding.finding_id, 'accept')}
              >
                <Check size={10} /> 接受
              </button>
              <button
                className="flex items-center gap-1 rounded border border-blue-200 px-2 py-1 text-[11px] text-blue-700 hover:bg-blue-50"
                onClick={() => onDecision(finding.finding_id, 'defer')}
              >
                <Edit2 size={10} /> 修改
              </button>
              <button
                className="flex items-center gap-1 rounded border border-rose-200 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-50"
                onClick={() => onDecision(finding.finding_id, 'reject')}
              >
                <X size={10} /> 拒绝
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const DIMENSION_META: { role: string; name: string; icon: string }[] = [
  { role: 'product_vision', name: '产品愿景分析', icon: '🎯' },
  { role: 'user_experience', name: '用户体验分析', icon: '🎨' },
  { role: 'technical_feasibility', name: '技术可行性分析', icon: '⚙️' },
  { role: 'business_value', name: '商业价值分析', icon: '💰' },
]

function LoadingProgressView({ progress }: { progress: import('@/lib/ralph-types').ProductDefProgress }) {
  const analyzed = progress.dimensions_analyzed ?? []
  const current = progress.current_dimension
  const total = progress.total_dimensions ?? 4
  const pct = Math.round((analyzed.length / total) * 100)
  const partialFindings = progress.partial_findings ?? []

  return (
    <div className="rounded border border-slate-200 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-700">多 Agent 产品分析</h3>
        <span className="text-[10px] text-slate-400">分析中... {pct}%</span>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[10px] text-slate-400">{analyzed.length}/{total}</span>
      </div>

      {/* Render completed findings with full content */}
      <div className="space-y-3">
        {partialFindings.map(finding => (
          <FindingCard
            key={finding.finding_id}
            finding={finding}
            isEditing={false}
            editText=""
            onEditTextChange={() => {}}
            onSaveEdit={() => {}}
            onCancelEdit={() => {}}
            onDecision={() => {}}
          />
        ))}
      </div>

      {/* Placeholder for current and pending dimensions */}
      <div className="mt-3 space-y-3">
        {DIMENSION_META.filter(dim => !analyzed.includes(dim.role)).map((dim) => {
          const isCurrent = current === dim.role
          const isPending = !isCurrent

          return (
            <div
              key={dim.role}
              className={cn(
                'rounded border p-2.5 text-xs',
                isCurrent && 'border-blue-200 bg-blue-50',
                isPending && 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-medium text-slate-700">
                  <span className="mr-1">{dim.icon}</span>
                  {dim.name}
                </span>
                {isCurrent && (
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-700 flex items-center gap-1">
                    <RefreshCw size={10} className="animate-spin" /> 分析中...
                  </span>
                )}
                {isPending && (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-400">等待中</span>
                )}
              </div>
              {isCurrent && (
                <p className="text-slate-400 animate-pulse">正在调用 AI 分析中...</p>
              )}
              {isPending && (
                <p className="text-slate-300">等待分析</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
