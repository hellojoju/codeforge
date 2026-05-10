interface HandoffHint {
  hint_id: string
  source_feature_id: string
  suggested_task_boundaries: string[]
  likely_dependencies: string[]
  required_recon_questions: string[]
  risk_notes: string[]
}

interface TaskHandoffPanelProps {
  hints: HandoffHint[]
}

export default function TaskHandoffPanel({ hints }: TaskHandoffPanelProps) {
  if (hints.length === 0) {
    return <div className="text-sm text-slate-500 p-4">暂无任务交接提示</div>
  }

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">任务交接提示</h3>
      <div className="space-y-3">
        {hints.map(hint => (
          <div key={hint.hint_id} className="p-3 bg-slate-700/30 rounded border border-slate-600">
            <h4 className="text-sm font-medium text-slate-200 mb-2">{hint.source_feature_id}</h4>
            {hint.suggested_task_boundaries.length > 0 && (
              <div className="text-xs text-slate-400 mb-1">
                任务边界：{hint.suggested_task_boundaries.join(', ')}
              </div>
            )}
            {hint.likely_dependencies.length > 0 && (
              <div className="text-xs text-blue-400 mb-1">
                依赖：{hint.likely_dependencies.join(', ')}
              </div>
            )}
            {hint.risk_notes.length > 0 && (
              <div className="text-xs text-amber-400">
                风险：{hint.risk_notes.join('; ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
