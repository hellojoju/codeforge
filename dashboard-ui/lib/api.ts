/** REST API 客户端 — 对接 FastAPI Dashboard 后端。 */

import type { Snapshot, DashboardEvent, Command, ModuleAssignment, ExecutionStatus, AgentWithSilence, EventStreamItem, BlockingIssue, ExecutionLedger } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18753'

/** 获取项目状态快照。 */
export async function fetchStateSnapshot(projectId: string, runId = ''): Promise<Snapshot> {
  const url = `${API_BASE}/api/dashboard/state?project_id=${encodeURIComponent(projectId)}&run_id=${encodeURIComponent(runId)}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch state: ${res.status} ${res.statusText}`)
  return res.json()
}

/** 获取增量事件。 */
export async function getEventsAfter(
  projectId: string,
  afterEventId: number,
  limit = 200,
): Promise<DashboardEvent[]> {
  const url = `${API_BASE}/api/dashboard/events?project_id=${encodeURIComponent(projectId)}&after_event_id=${afterEventId}&limit=${limit}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status} ${res.statusText}`)
  const data = await res.json()
  return data.events as DashboardEvent[]
}

/** 创建命令，返回 202 Accepted。 */
export async function createCommand(
  type: string,
  targetId = '',
  payload: Record<string, unknown> = {},
  projectId = 'default',
  runId = '',
): Promise<{ schema_version: number; command_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/dashboard/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, run_id: runId, type, target_id: targetId, payload }),
  })
  if (!res.ok) throw new Error(`Failed to create command: ${res.status}`)
  return res.json()
}

/** 查询单个命令状态。 */
export async function getCommand(commandId: string): Promise<Command> {
  const res = await fetch(`${API_BASE}/api/dashboard/commands/${commandId}`)
  if (!res.ok) throw new Error(`Failed to get command: ${res.status}`)
  return res.json()
}

/** 发送 PM 对话消息。 */
export async function sendChat(
  content: string,
  projectId = 'default',
  runId = '',
): Promise<{ success: boolean; message_id: string; pm_response: { id: string; role: string; content: string; timestamp: string; action_triggered: string } }> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30s 超时
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, run_id: runId, content }),
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(`Failed to send chat: ${res.status}`)
    return res.json()
  } catch (error) {
    clearTimeout(timeoutId)
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求超时，请稍后重试')
    }
    throw error
  }
}

/** 快捷命令工厂。 */
export const actions = {
  approve: (featureId: string, projectId = 'default', runId = '') =>
    createCommand('approve_decision', featureId, { feature_id: featureId }, projectId, runId),

  reject: (featureId: string, projectId = 'default', runId = '') =>
    createCommand('reject_decision', featureId, { feature_id: featureId }, projectId, runId),

  pause: (agentId: string, projectId = 'default', runId = '') =>
    createCommand('pause_run', agentId, { agent_id: agentId }, projectId, runId),

  resume: (agentId: string, projectId = 'default', runId = '') =>
    createCommand('resume_run', agentId, { agent_id: agentId }, projectId, runId),

  retry: (featureId: string, projectId = 'default', runId = '') =>
    createCommand('retry_feature', featureId, { feature_id: featureId }, projectId, runId),

  skip: (featureId: string, projectId = 'default', runId = '') =>
    createCommand('skip_feature', featureId, { feature_id: featureId }, projectId, runId),
}

/** 获取所有模块分配。 */
export async function listModules(role?: string): Promise<ModuleAssignment[]> {
  const params = new URLSearchParams()
  if (role) params.set('role', role)
  const url = `${API_BASE}/api/dashboard/modules?${params.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch modules: ${res.status}`)
  const data = await res.json()
  return data.modules as ModuleAssignment[]
}

/** 创建或更新模块分配。 */
export async function upsertModule(
  assignment: Omit<ModuleAssignment, 'interface_contract'> & {
    interface_contract?: Record<string, unknown>
  },
): Promise<ModuleAssignment> {
  const res = await fetch(`${API_BASE}/api/dashboard/modules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assignment),
  })
  if (!res.ok) throw new Error(`Failed to upsert module: ${res.status}`)
  const data = await res.json()
  return data.assignment as ModuleAssignment
}

/** 获取待审批列表。 */
export async function listPendingApprovals(): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${API_BASE}/api/dashboard/pending-approvals`)
  if (!res.ok) throw new Error(`Failed to fetch pending approvals: ${res.status}`)
  const data = await res.json()
  return data.approvals as Record<string, unknown>[]
}

/** 启动执行循环。 */
export async function startExecution(): Promise<{ success: boolean; status?: string }> {
  const res = await fetch(`${API_BASE}/api/execution/start`, { method: 'POST' })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || '启动失败')
  }
  return res.json()
}

/** 停止执行循环。 */
export async function stopExecution(): Promise<{ success: boolean; status?: string }> {
  const res = await fetch(`${API_BASE}/api/execution/stop`, { method: 'POST' })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || '停止失败')
  }
  return res.json()
}

/** 获取执行状态。 */
export async function getExecutionStatus(): Promise<{
  status: ExecutionStatus
  thread_alive: boolean
  error: string | null
  available: boolean
}> {
  const res = await fetch(`${API_BASE}/api/execution/status`)
  if (!res.ok) {
    return { status: 'idle', thread_alive: false, error: null, available: false }
  }
  return res.json()
}

// ============================================================================
// Agent 管理 API
// ============================================================================

/** 列出所有 Agent 实例及其状态（含静默检测）。 */
export async function listAgents(): Promise<{
  agents: AgentWithSilence[]
  total: number
}> {
  const res = await fetch(`${API_BASE}/api/agents`)
  if (!res.ok) throw new Error(`Failed to list agents: ${res.status}`)
  return res.json()
}

/** 获取单个 Agent 的详细状态，包括静默检测。 */
export async function getAgentStatus(agentId: string): Promise<AgentWithSilence> {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}/status`)
  if (!res.ok) throw new Error(`Failed to get agent status: ${res.status}`)
  const data = await res.json()
  if (data.agent && typeof data.agent === 'object') {
    return {
      ...data.agent,
      silence_status: data.silence_status,
      process_status: data.process_status,
    } as AgentWithSilence
  }
  return data as AgentWithSilence
}

/** 向 Agent 发送消息（通过 stdin）。 */
export async function sendAgentMessage(
  agentId: string,
  message: string,
): Promise<{ success: boolean; agent_id: string }> {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || '发送消息失败')
  }
  return res.json()
}

/** 中断 Agent 进程。 */
export async function interruptAgent(
  agentId: string,
  options: { force?: boolean } = {},
): Promise<{ success: boolean; agent_id: string; force: boolean }> {
  const body = options.force ? { force: true } : undefined
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}/interrupt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || '中断 Agent 失败')
  }
  return res.json()
}

/** 获取事件流（增量）。 */
export async function getAgentEvents(
  agentId: string | null = null,
  afterId: string | null = null,
  limit = 100,
): Promise<EventStreamItem[]> {
  const params = new URLSearchParams()
  if (agentId) params.set('agent_id', agentId)
  if (afterId) params.set('after_id', afterId)
  params.set('limit', String(limit))
  const res = await fetch(`${API_BASE}/api/events?${params.toString()}`)
  if (!res.ok) return []
  const data = await res.json()
  // /api/events 可能返回裸数组或 {events: [...]}
  return Array.isArray(data) ? data : data.events || []
}

/** 获取阻塞问题列表。 */
export async function listBlockingIssues(
  featureId?: string,
  resolved?: boolean,
): Promise<BlockingIssue[]> {
  const params = new URLSearchParams()
  if (featureId) params.set('feature_id', featureId)
  if (typeof resolved === 'boolean') params.set('resolved', String(resolved))
  const res = await fetch(`${API_BASE}/api/blocking-issues?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch blocking issues: ${res.status}`)
  const data = await res.json()
  return data.issues as BlockingIssue[]
}

export async function fetchExecutionLedger(params?: {
  featureId?: string
  agentId?: string
  status?: 'started' | 'completed' | 'failed' | 'retrying' | 'blocked'
}): Promise<ExecutionLedger> {
  const query = new URLSearchParams()
  if (params?.featureId) query.set('feature_id', params.featureId)
  if (params?.agentId) query.set('agent_id', params.agentId)
  if (params?.status) query.set('status', params.status)
  const qs = query.toString()
  const url = `${API_BASE}/api/execution-ledger${qs ? `?${qs}` : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch execution ledger: ${res.status}`)
  return res.json()
}

export async function resolveBlockingIssue(issueId: string, resolution: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/blocking-issues/${encodeURIComponent(issueId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution }),
  })
  if (!res.ok) throw new Error(`Failed to resolve blocking issue: ${res.status}`)
  return res.json()
}
