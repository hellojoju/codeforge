'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  generateTechnicalRoute,
  confirmTechnicalRoute,
  triggerToolDiscovery,
} from '@/lib/brainstorm-api'
import type {
  TechnicalRoute,
  ToolDiscoveryResult,
  ToolCandidate,
  ToolEvaluation,
  TechnicalRouteStatus,
} from '@/lib/ralph-types'

const STATUS_LABELS: Record<TechnicalRouteStatus, string> = {
  pending: '待确认',
  accepted: '已采纳',
  revision_requested: '要求修改',
}

const RECOMMENDATION_COLORS: Record<string, string> = {
  adopt: 'bg-emerald-100 text-emerald-700',
  compare: 'bg-amber-100 text-amber-700',
  avoid: 'bg-rose-100 text-rose-700',
}

const RECOMMENDATION_LABELS: Record<string, string> = {
  adopt: '推荐采用',
  compare: '待比较',
  avoid: '不建议',
}

const SCORE_BARS = [
  { key: 'functional_fit', label: '功能匹配' },
  { key: 'maintenance_health', label: '维护健康' },
  { key: 'license_fit', label: '许可证兼容' },
  { key: 'stack_compatibility', label: '栈兼容性' },
] as const

export default function SpecDetailPage() {
  const params = useParams()
  const router = useRouter()
  const recordId = params.id as string

  const [technicalRoute, setTechnicalRoute] = useState<TechnicalRoute | null>(null)
  const [toolDiscoveryResults, setToolDiscoveryResults] = useState<ToolDiscoveryResult[]>([])
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState('')
  const [generating, setGenerating] = useState(false)
  const [discovering, setDiscovering] = useState(false)

  useEffect(() => {
    loadState()
  }, [recordId])

  async function loadState() {
    try {
      const res = await fetch(`/api/ralph/brainstorm/${recordId}`)
      const data = await res.json()
      if (data.technical_route) setTechnicalRoute(data.technical_route)
      if (data.tool_discovery_results) setToolDiscoveryResults(data.tool_discovery_results)
    } catch (e) {
      console.error('Failed to load spec state', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerateRoute() {
    setGenerating(true)
    try {
      const result = await generateTechnicalRoute(recordId)
      setTechnicalRoute(result.technical_route)
    } catch (e) {
      console.error('Failed to generate route', e)
    } finally {
      setGenerating(false)
    }
  }

  async function handleConfirm(status: 'accepted' | 'revision_requested') {
    if (!technicalRoute) return
    try {
      const result = await confirmTechnicalRoute(technicalRoute.route_id, status, feedback)
      setTechnicalRoute(result.technical_route)
    } catch (e) {
      console.error('Failed to confirm route', e)
    }
  }

  async function handleDiscoverTools() {
    if (!technicalRoute) return
    setDiscovering(true)
    try {
      const result = await triggerToolDiscovery(technicalRoute.route_id)
      setToolDiscoveryResults(result.discovery_results)
    } catch (e) {
      console.error('Failed to discover tools', e)
    } finally {
      setDiscovering(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-sm text-slate-400">加载中...</span>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-5 space-y-6">
      {/* Back link */}
      <button onClick={() => router.push('/ralph/specs')} className="text-sm text-blue-600 hover:underline">
        ← 返回列表
      </button>

      {/* Technical Route Section */}
      <section className="rounded border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">技术路线</h2>
          {!technicalRoute && (
            <button
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-500 disabled:opacity-50 transition-colors"
              onClick={handleGenerateRoute}
              disabled={generating}
            >
              {generating ? '生成中...' : '生成技术路线'}
            </button>
          )}
          {technicalRoute && (
            <span className={cn(
              'rounded px-2 py-1 text-xs',
              technicalRoute.status === 'accepted' ? 'bg-emerald-100 text-emerald-700' :
              technicalRoute.status === 'revision_requested' ? 'bg-rose-100 text-rose-700' :
              'bg-amber-100 text-amber-700'
            )}>
              {STATUS_LABELS[technicalRoute.status]}
            </span>
          )}
        </div>

        {technicalRoute && (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-1">架构概要</h3>
              <p className="text-sm text-slate-600 leading-relaxed">{technicalRoute.architecture_summary}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StackList label="前端技术栈" items={technicalRoute.frontend_stack} />
              <StackList label="后端技术栈" items={technicalRoute.backend_stack} />
              <StackList label="数据存储" items={technicalRoute.data_storage} />
              <StackList label="外部集成" items={technicalRoute.integrations} />
            </div>

            {technicalRoute.non_functional_requirements.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-1">非功能性要求</h3>
                <ul className="list-disc list-inside text-sm text-slate-600 space-y-0.5">
                  {technicalRoute.non_functional_requirements.map((nfr, i) => (
                    <li key={i}>{nfr}</li>
                  ))}
                </ul>
              </div>
            )}

            {technicalRoute.key_risks.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-1">关键风险</h3>
                <ul className="list-disc list-inside text-sm text-rose-600 space-y-0.5">
                  {technicalRoute.key_risks.map((risk, i) => (
                    <li key={i}>{risk}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Confirmation controls */}
            {technicalRoute.status === 'pending' && (
              <div className="border-t border-slate-100 pt-4 space-y-3">
                <textarea
                  className="w-full rounded border border-slate-300 p-2 text-sm resize-none"
                  rows={2}
                  placeholder="反馈（可选）..."
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    className="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-500 transition-colors"
                    onClick={() => handleConfirm('accepted')}
                  >确认路线</button>
                  <button
                    className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50 transition-colors"
                    onClick={() => handleConfirm('revision_requested')}
                  >要求修改</button>
                </div>
              </div>
            )}
          </div>
        )}

        {!technicalRoute && (
          <p className="text-sm text-slate-400">需求冻结后可生成技术路线</p>
        )}
      </section>

      {/* Tool Discovery Section */}
      {technicalRoute?.status === 'accepted' && (
        <section className="rounded border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-800">工具发现</h2>
            {toolDiscoveryResults.length === 0 && (
              <button
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-500 disabled:opacity-50 transition-colors"
                onClick={handleDiscoverTools}
                disabled={discovering}
              >
                {discovering ? '搜索中...' : '触发工具发现'}
              </button>
            )}
          </div>

          {toolDiscoveryResults.length === 0 && technicalRoute.tool_needs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">待发现工具需求</h3>
              <ul className="list-disc list-inside text-sm text-slate-600 space-y-0.5">
                {technicalRoute.tool_needs.map((need, i) => (
                  <li key={i}>{need}</li>
                ))}
              </ul>
            </div>
          )}

          {toolDiscoveryResults.map(result => (
            <ToolDiscoveryCard key={result.discovery_id} result={result} />
          ))}
        </section>
      )}
    </div>
  )
}

function StackList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">{label}</h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span key={i} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{item}</span>
        ))}
      </div>
    </div>
  )
}

function ToolDiscoveryCard({ result }: { result: ToolDiscoveryResult }) {
  return (
    <div className="mb-4 rounded border border-slate-200 p-4 last:mb-0">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">{result.tool_need}</h3>

      {result.candidates.map(candidate => {
        const evaluation = result.evaluations.find(e => e.candidate_id === candidate.candidate_id)
        return (
          <ToolCandidateRow key={candidate.candidate_id} candidate={candidate} evaluation={evaluation} />
        )
      })}

      {result.candidates.length === 0 && (
        <p className="text-xs text-slate-400">未找到候选工具</p>
      )}
    </div>
  )
}

function ToolCandidateRow({ candidate, evaluation }: { candidate: ToolCandidate; evaluation?: ToolEvaluation }) {
  if (!evaluation) return null

  return (
    <div className="rounded border border-slate-100 p-3 mb-2 last:mb-0">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <a href={candidate.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-blue-600 hover:underline">
            {candidate.name}
          </a>
          <span className="text-[10px] text-slate-400">{candidate.source}</span>
          {candidate.stars != null && (
            <span className="text-[10px] text-slate-400">{candidate.stars} stars</span>
          )}
        </div>
        <span className={cn('rounded px-1.5 py-0.5 text-[10px]', RECOMMENDATION_COLORS[evaluation.recommendation])}>
          {RECOMMENDATION_LABELS[evaluation.recommendation]}
        </span>
      </div>

      <p className="text-xs text-slate-600 mb-2">{candidate.description}</p>

      {/* Score bars */}
      <div className="grid grid-cols-4 gap-2 mb-2">
        {SCORE_BARS.map(({ key, label }) => {
          const score = evaluation[key]
          return (
            <div key={key}>
              <span className="text-[10px] text-slate-400">{label}</span>
              <div className="flex gap-0.5 mt-0.5">
                {[1, 2, 3, 4, 5].map(n => (
                  <div
                    key={n}
                    className={cn(
                      'h-1.5 flex-1 rounded-full',
                      n <= score ? (score >= 4 ? 'bg-emerald-500' : score >= 3 ? 'bg-amber-500' : 'bg-rose-500') : 'bg-slate-100'
                    )}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-3 text-[10px] text-slate-400">
        <span>安全风险: {evaluation.security_risk}</span>
        <span>集成成本: {evaluation.integration_cost}</span>
        {candidate.license && <span>License: {candidate.license}</span>}
      </div>

      {evaluation.summary && (
        <p className="mt-2 text-xs text-slate-500 leading-relaxed">{evaluation.summary}</p>
      )}
    </div>
  )
}
