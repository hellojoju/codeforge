interface QuestionTracePanelProps {
  question: string
  nodeName: string
  fieldName: string
  reason: string
}

export default function QuestionTracePanel({ question, nodeName, fieldName, reason }: QuestionTracePanelProps) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-blue-600 font-medium">正在探索</span>
        <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 text-xs">{nodeName}</span>
      </div>
      <p className="text-slate-700 mb-2">{question}</p>
      <div className="text-xs text-slate-500">
        补齐字段：<code className="px-1 py-0.5 bg-slate-100 rounded">{fieldName}</code>
        <span className="ml-2">原因：{reason}</span>
      </div>
    </div>
  )
}
