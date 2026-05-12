interface Edge { source_id: string; target_id: string; edge_type: string; description: string }
interface Conflict { feature_a: string; feature_b: string; description: string; severity: string }

interface RelationshipGraphProps {
  edges: Edge[]
  conflicts: Conflict[]
}

const EDGE_COLORS: Record<string, string> = {
  depends_on: 'stroke-blue-400',
  conflicts_with: 'stroke-red-400',
  enables: 'stroke-emerald-400',
  mutually_exclusive: 'stroke-amber-400',
}

export default function RelationshipGraph({ edges, conflicts }: RelationshipGraphProps) {
  if (edges.length === 0 && conflicts.length === 0) {
    return <div className="text-sm text-slate-500 p-4">暂无关系图谱数据</div>
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">关系图谱</h3>
      {edges.length > 0 && (
        <div className="space-y-2">
          {edges.map((edge, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="text-slate-700">{edge.source_id}</span>
              <span className={`px-1.5 py-0.5 rounded text-xs ${EDGE_COLORS[edge.edge_type] || 'stroke-slate-400'} bg-slate-100`}>
                {edge.edge_type}
              </span>
              <span className="text-slate-700">{edge.target_id}</span>
            </div>
          ))}
        </div>
      )}
      {conflicts.length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-xs font-semibold text-red-500">冲突检测</h4>
          {conflicts.map((c, i) => (
            <div key={i} className="text-sm text-red-600 pl-3 border-l-2 border-red-400">
              {c.feature_a} ↔ {c.feature_b}: {c.description}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
