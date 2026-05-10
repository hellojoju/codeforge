interface QuestionTracePanelProps {
  question: string
  nodeName: string
  fieldName: string
  reason: string
}

export default function QuestionTracePanel({ question, nodeName, fieldName, reason }: QuestionTracePanelProps) {
  return (
    <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 text-sm">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-blue-400 font-medium">正在探索</span>
        <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 text-xs">{nodeName}</span>
      </div>
      <p className="text-slate-300 mb-2">{question}</p>
      <div className="text-xs text-slate-500">
        补齐字段：<code className="px-1 py-0.5 bg-slate-700 rounded">{fieldName}</code>
        <span className="ml-2">原因：{reason}</span>
      </div>
    </div>
  )
}
