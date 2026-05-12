interface FeatureNode {
  node_id: string
  name: string
  level: string
  status: string
  user_stories: string[]
  acceptance_criteria: string[]
  success_path: string[]
  failure_path: string[]
  edge_cases: string[]
  data_requirements: string[]
  dependencies: string[]
  assumptions: string[]
  business_rules: string[]
  permission_rules: string[]
  vision?: string
  target_users?: string[]
  roles?: string[]
  success_criteria?: string[]
  mvp_scope?: string[]
  out_of_scope?: string[]
}

interface NodeDetailCardProps {
  node: FeatureNode
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mb-3">
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{title}</h4>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-slate-700 pl-3 border-l-2 border-slate-200">{item}</li>
        ))}
      </ul>
    </div>
  )
}

export default function NodeDetailCard({ node }: NodeDetailCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-900">{node.name}</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium
          ${node.status === 'confirmed' ? 'bg-emerald-50 text-emerald-600' :
            node.status === 'exploring' ? 'bg-blue-50 text-blue-600' :
            node.status === 'needs_clarification' ? 'bg-amber-50 text-amber-600' :
            'bg-slate-100 text-slate-500'}`}>
          {node.status}
        </span>
      </div>

      {node.level === 'product' ? (
        <>
          {node.vision && <Section title="愿景" items={[node.vision]} />}
          {node.target_users && <Section title="目标用户" items={node.target_users} />}
          {node.roles && <Section title="用户角色" items={node.roles} />}
          {node.success_criteria && <Section title="成功标准" items={node.success_criteria} />}
          {node.mvp_scope && <Section title="MVP 范围" items={node.mvp_scope} />}
          {node.out_of_scope && <Section title="明确不做" items={node.out_of_scope} />}
        </>
      ) : (
        <>
          <Section title="用户故事" items={node.user_stories} />
          <Section title="验收标准" items={node.acceptance_criteria} />
          <Section title="成功路径" items={node.success_path} />
          <Section title="失败路径" items={node.failure_path} />
          <Section title="边界场景" items={node.edge_cases} />
          <Section title="数据需求" items={node.data_requirements} />
          <Section title="依赖" items={node.dependencies} />
          <Section title="业务规则" items={node.business_rules} />
          <Section title="权限规则" items={node.permission_rules} />
        </>
      )}
    </div>
  )
}
