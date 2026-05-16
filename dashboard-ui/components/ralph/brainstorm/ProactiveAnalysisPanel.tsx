'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  ProactiveAnalysis,
  ProactiveAnalysisItem,
  ProactiveItemStatus,
} from '@/lib/ralph-types'

const CATEGORY_LABELS: Record<string, string> = {
  product_type: '产品类型',
  target_user: '目标用户',
  core_scenario: '核心场景',
  module: '功能模块',
  tech_direction: '技术方向',
  risk: '风险点',
  question: '待确认问题',
}

const STATUS_LABELS: Record<ProactiveItemStatus, string> = {
  pending: '待确认',
  accepted: '已接受',
  rejected: '已拒绝',
  modified: '已修改',
}

interface ProactiveAnalysisPanelProps {
  analysis: ProactiveAnalysis
  onConfirm: (itemId: string, status: ProactiveItemStatus, revision?: string) => void
}

export default function ProactiveAnalysisPanel({ analysis, onConfirm }: ProactiveAnalysisPanelProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const handleStatus = (itemId: string, status: ProactiveItemStatus) => {
    if (status === 'modified') {
      setEditingId(itemId)
      const item = analysis.items.find(i => i.item_id === itemId)
      setEditText(item?.content ?? '')
      return
    }
    onConfirm(itemId, status)
  }

  const handleSaveEdit = () => {
    if (editingId) {
      onConfirm(editingId, 'modified', editText)
      setEditingId(null)
      setEditText('')
    }
  }

  const acceptedCount = analysis.items.filter(i => i.status === 'accepted' || i.status === 'modified').length
  const total = analysis.items.length
  const progress = total > 0 ? Math.round((acceptedCount / total) * 100) : 0

  return (
    <div className="rounded border border-slate-200 p-3">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-700">主动分析</h3>
        <span className="text-[10px] text-slate-400">{progress}% 已确认</span>
      </div>

      {/* Progress bar */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[10px] text-slate-400">{acceptedCount}/{total}</span>
      </div>

      {/* Summary */}
      {analysis.summary && (
        <p className="mb-3 text-xs text-slate-500 leading-relaxed">{analysis.summary}</p>
      )}

      {/* Non-question items */}
      <div className="space-y-2">
        {analysis.items
          .filter(item => item.category !== 'question')
          .map(item => (
            <ProactiveItemRow
              key={item.item_id}
              item={item}
              isEditing={editingId === item.item_id}
              editText={editText}
              onEditTextChange={setEditText}
              onSaveEdit={handleSaveEdit}
              onCancelEdit={() => { setEditingId(null); setEditText('') }}
              onStatus={handleStatus}
            />
          ))}
      </div>

      {/* Question items — user answers these */}
      {analysis.items.filter(item => item.category === 'question').length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">需要确认的问题</h4>
          {analysis.items
            .filter(item => item.category === 'question')
            .map(item => (
              <QuestionItemRow
                key={item.item_id}
                item={item}
                onSubmit={(itemId, answer) => onConfirm(itemId, 'accepted', answer)}
              />
            ))}
        </div>
      )}
    </div>
  )
}

interface ProactiveItemRowProps {
  item: ProactiveAnalysisItem
  isEditing: boolean
  editText: string
  onEditTextChange: (v: string) => void
  onSaveEdit: () => void
  onCancelEdit: () => void
  onStatus: (itemId: string, status: ProactiveItemStatus) => void
}

interface QuestionItemRowProps {
  item: ProactiveAnalysisItem
  onSubmit: (itemId: string, answer: string) => void
}

function QuestionItemRow({ item, onSubmit }: QuestionItemRowProps) {
  const [answer, setAnswer] = useState('')
  const submitted = item.status !== 'pending'

  if (submitted) {
    return (
      <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs">
        <p className="font-medium text-slate-700 mb-1">{item.content}</p>
        <p className="text-blue-600 leading-relaxed">你的回答：{item.user_revision || '（未填写）'}</p>
      </div>
    )
  }

  return (
    <div className="rounded border border-amber-200 bg-amber-50/50 p-2 text-xs">
      <p className="font-medium text-slate-700 mb-2">{item.content}</p>
      <textarea
        className="w-full rounded border border-slate-300 p-1.5 text-xs resize-none bg-white"
        rows={2}
        placeholder="输入你的回答..."
        value={answer}
        onChange={e => setAnswer(e.target.value)}
      />
      <button
        className="mt-1.5 rounded bg-blue-600 px-2 py-1 text-[10px] text-white hover:bg-blue-500 disabled:opacity-50"
        disabled={!answer.trim()}
        onClick={() => {
          if (answer.trim()) {
            onSubmit(item.item_id, answer.trim())
            setAnswer('')
          }
        }}
      >提交回答</button>
    </div>
  )
}

function ProactiveItemRow({ item, isEditing, editText, onEditTextChange, onSaveEdit, onCancelEdit, onStatus }: ProactiveItemRowProps) {
  const statusColor = {
    accepted: 'border-emerald-200 bg-emerald-50',
    rejected: 'border-rose-200 bg-rose-50',
    modified: 'border-blue-200 bg-blue-50',
    pending: 'border-slate-200 bg-white',
  }[item.status]

  const categoryLabel = CATEGORY_LABELS[item.category] ?? item.category
  const statusLabel = STATUS_LABELS[item.status]

  return (
    <div className={cn('rounded border p-2 text-xs', statusColor)}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-slate-700">{categoryLabel}</span>
        <span className={cn(
          'rounded px-1.5 py-0.5 text-[10px]',
          item.status === 'accepted' ? 'bg-emerald-100 text-emerald-700' :
          item.status === 'rejected' ? 'bg-rose-100 text-rose-700' :
          item.status === 'modified' ? 'bg-blue-100 text-blue-700' :
          'bg-slate-100 text-slate-500'
        )}>{statusLabel}</span>
      </div>

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
          <p className="text-slate-600 leading-relaxed">{item.content}</p>
          {item.user_revision && (
            <p className="mt-1 text-blue-600 leading-relaxed">{item.user_revision}</p>
          )}
          {item.status === 'pending' && (
            <div className="mt-2 flex gap-1">
              <button
                className="rounded border border-emerald-200 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-50"
                onClick={() => onStatus(item.item_id, 'accepted')}
              >接受</button>
              <button
                className="rounded border border-blue-200 px-2 py-1 text-[11px] text-blue-700 hover:bg-blue-50"
                onClick={() => onStatus(item.item_id, 'modified')}
              >修改</button>
              <button
                className="rounded border border-rose-200 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-50"
                onClick={() => onStatus(item.item_id, 'rejected')}
              >拒绝</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
