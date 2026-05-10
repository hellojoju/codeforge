'use client'

import { useState } from 'react'
import { ChevronRight, ChevronDown, Circle, CheckCircle, AlertCircle } from 'lucide-react'

interface FeatureNode {
  node_id: string
  name: string
  level: string
  status: string
  children: string[]
}

interface FeatureTreePanelProps {
  nodes: Record<string, FeatureNode>
  rootId: string
  activeNodeId: string
  onNodeClick?: (nodeId: string) => void
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  confirmed: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
  exploring: <Circle className="w-3.5 h-3.5 text-blue-400 animate-pulse" />,
  pending: <Circle className="w-3.5 h-3.5 text-slate-500" />,
  needs_clarification: <AlertCircle className="w-3.5 h-3.5 text-amber-400" />,
}

export default function FeatureTreePanel({ nodes, rootId, activeNodeId, onNodeClick }: FeatureTreePanelProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set([rootId]))

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const renderNode = (nodeId: string, depth = 0) => {
    const node = nodes[nodeId]
    if (!node) return null

    const hasChildren = node.children.length > 0
    const isExpanded = expanded.has(nodeId)
    const isActive = nodeId === activeNodeId

    return (
      <div key={nodeId}>
        <button
          onClick={() => {
            onNodeClick?.(nodeId)
            hasChildren && toggle(nodeId)
          }}
          className={`w-full flex items-center gap-1.5 py-1 px-2 rounded text-sm transition-colors
            ${isActive ? 'bg-blue-500/20 text-blue-300' : 'text-slate-300 hover:bg-slate-700/50'}
          `}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {hasChildren && (
            isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />
          )}
          {!hasChildren && <span className="w-3" />}
          {STATUS_ICONS[node.status]}
          <span className="truncate">{node.name}</span>
        </button>
        {isExpanded && node.children.map(cid => renderNode(cid, depth + 1))}
      </div>
    )
  }

  return (
    <div className="bg-slate-900/30 border-r border-slate-700 p-2 overflow-y-auto max-h-[600px]">
      <h3 className="text-sm font-semibold text-slate-400 px-2 py-2">功能树</h3>
      {renderNode(rootId)}
    </div>
  )
}
