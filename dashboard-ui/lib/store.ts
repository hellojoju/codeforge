/** Dashboard 全局状态 store (Zustand) — 对接后端真实数据。

 * TanStack Query 已引入（见 lib/query-client.ts + hooks/），
 * 新组件请优先使用 useFeatures()、useBlockingIssues() 等 hooks。
 *
 * 此 store 保留 WebSocket 实时更新 + 向后兼容。
 */

import { create } from 'zustand'
import type { AgentWithSilence, Feature, DashboardEvent, ChatMessage, Command, ModuleAssignment, ExecutionStatus, EventStreamItem, BlockingIssue } from './types'
import {
  fetchStateSnapshot,
  getEventsAfter,
  actions,
  startExecution,
  stopExecution,
  getExecutionStatus,
  listAgents,
  getAgentStatus,
  sendAgentMessage,
  interruptAgent,
  getAgentEvents,
  listBlockingIssues,
} from './api'
import { queryClient } from '@/lib/query-client'
import { queryKeys } from '@/lib/query-keys'

interface DashboardState {
  projectId: string
  lastEventId: number
  agents: AgentWithSilence[]
  features: Feature[]
  chatHistory: ChatMessage[]
  events: DashboardEvent[]
  recentCommands: Map<string, Command>
  moduleAssignments: ModuleAssignment[]
  blockingIssues: BlockingIssue[]
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  executionStatus: ExecutionStatus
  executionError: string | null
  agentDetails: Map<string, AgentWithSilence>
  eventStream: EventStreamItem[]

  setProjectId: (id: string) => void
  loadSnapshot: () => Promise<void>
  loadEvents: () => Promise<void>
  applyEvent: (event: DashboardEvent) => void
  pushEvent: (event: DashboardEvent) => void
  setConnectionStatus: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void

  approve: (targetId: string) => Promise<{ command_id: string }>
  reject: (targetId: string) => Promise<{ command_id: string }>
  pause: (targetId: string) => Promise<{ command_id: string }>
  resume: (targetId: string) => Promise<{ command_id: string }>
  retry: (targetId: string) => Promise<{ command_id: string }>
  skip: (targetId: string) => Promise<{ command_id: string }>

  startExecution: () => Promise<void>
  stopExecution: () => Promise<void>
  fetchExecutionStatus: () => Promise<void>
  fetchAgents: () => Promise<void>
  fetchAgentDetail: (agentId: string) => Promise<void>
  sendMessage: (agentId: string, message: string) => Promise<void>
  interruptAgent: (agentId: string, force?: boolean) => Promise<void>
  fetchEvents: (agentId?: string) => Promise<void>
  fetchBlockingIssues: () => Promise<void>
  addChatMessage: (message: ChatMessage) => void
}

const DEFAULT_PROJECT_ID = 'default'

export const useDashboardStore = create<DashboardState>((set, get) => ({
  projectId: DEFAULT_PROJECT_ID,
  lastEventId: 0,
  agents: [],
  features: [],
  chatHistory: [],
  events: [],
  recentCommands: new Map(),
  moduleAssignments: [],
  blockingIssues: [],
  connectionStatus: 'connecting',
  executionStatus: 'idle',
  executionError: null,
  agentDetails: new Map(),
  eventStream: [],

  setProjectId: (id) => set({ projectId: id }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  loadSnapshot: async () => {
    try {
      const { projectId } = get()
      const snapshot = await fetchStateSnapshot(projectId)
      set({
        agents: snapshot.agents,
        features: snapshot.features,
        chatHistory: snapshot.chat_history,
        moduleAssignments: snapshot.module_assignments ?? [],
        blockingIssues: snapshot.blocking_issues ?? [],
        lastEventId: snapshot.last_event_id,
        connectionStatus: 'connected',
      })
    } catch {
      set({ connectionStatus: 'error' })
    }
  },

  loadEvents: async () => {
    const { projectId, lastEventId } = get()
    if (lastEventId === 0) return
    try {
      const events = await getEventsAfter(projectId, lastEventId)
      for (const event of events) {
        applyEventToState(event, set)
      }
      if (events.length > 0) {
        set({ lastEventId: events[events.length - 1].event_id })
      }
    } catch {
      // ignore transient fetch errors
    }
  },

  pushEvent: (event) => set((state) => ({
    events: [...state.events, event].slice(-200),
  })),

  applyEvent: (event) => {
    applyEventToState(event, set)
    // 同时 invalidate TanStack Query keys，使 hooks 自动刷新
    invalidateQueriesForEvent(event)
  },

  approve: (targetId) => actions.approve(targetId, get().projectId),
  reject: (targetId) => actions.reject(targetId, get().projectId),
  pause: (targetId) => actions.pause(targetId, get().projectId),
  resume: (targetId) => actions.resume(targetId, get().projectId),
  retry: (targetId) => actions.retry(targetId, get().projectId),
  skip: (targetId) => actions.skip(targetId, get().projectId),

  startExecution: async () => {
    try {
      set({ executionError: null })
      await startExecution()
      set({ executionStatus: 'starting' })
    } catch (error) {
      set({
        executionError: error instanceof Error ? error.message : '启动失败',
        executionStatus: 'error',
      })
    }
  },

  stopExecution: async () => {
    try {
      set({ executionError: null })
      await stopExecution()
      set({ executionStatus: 'idle' })
    } catch (error) {
      set({
        executionError: error instanceof Error ? error.message : '停止失败',
      })
    }
  },

  fetchExecutionStatus: async () => {
    try {
      const result = await getExecutionStatus()
      set({ executionStatus: result.status, executionError: result.error })
    } catch {
      // 后端可能未配置 coordinator
    }
  },

  fetchAgents: async () => {
    try {
      const { agents: apiAgents } = await listAgents()
      set({ agents: apiAgents })
      set((state) => {
        const next = new Map(state.agentDetails)
        for (const agent of apiAgents) {
          next.set(agent.id, agent)
        }
        return { agentDetails: next }
      })
    } catch {
      // 后端可能未启动
    }
  },

  fetchAgentDetail: async (agentId: string) => {
    try {
      const detail = await getAgentStatus(agentId)
      set((state) => {
        const next = new Map(state.agentDetails)
        next.set(agentId, detail)
        return { agentDetails: next }
      })
    } catch {
      // 静默失败
    }
  },

  sendMessage: async (agentId: string, message: string) => {
    try {
      await sendAgentMessage(agentId, message)
    } catch (error) {
      console.error(`发送消息给 Agent ${agentId} 失败:`, error)
    }
  },

  interruptAgent: async (agentId: string, force = false) => {
    try {
      await interruptAgent(agentId, { force })
    } catch (error) {
      console.error(`中断 Agent ${agentId} 失败:`, error)
    }
  },

  fetchEvents: async (agentId?: string) => {
    try {
      const events = await getAgentEvents(agentId ?? null, null, 100)
      set({ eventStream: events })
    } catch {
      // 静默失败
    }
  },

  fetchBlockingIssues: async () => {
    try {
      const issues = await listBlockingIssues(undefined, false)
      set({ blockingIssues: issues })
    } catch {
      // ignore transient fetch errors
    }
  },

  addChatMessage: (message) => {
    set((state) => ({
      chatHistory: [...state.chatHistory, message],
    }))
  },
}))

function invalidateQueriesForEvent(event: DashboardEvent) {
  switch (event.type) {
    case 'feature_updated':
    case 'feature_status_changed':
      queryClient.invalidateQueries({ queryKey: queryKeys.features() })
      break
    case 'agent_status_changed':
      queryClient.invalidateQueries({ queryKey: queryKeys.agents() })
      break
    case 'blocking_issue_created':
    case 'blocking_issue_resolved':
      queryClient.invalidateQueries({ queryKey: queryKeys.blockingIssues() })
      break
    case 'execution_status_changed':
      queryClient.invalidateQueries({ queryKey: queryKeys.executionStatus() })
      queryClient.invalidateQueries({ queryKey: queryKeys.ralphSnapshot() })
      break
    default:
      queryClient.invalidateQueries({ queryKey: queryKeys.stateSnapshot() })
  }
}

function applyEventToState(
  event: DashboardEvent,
  set: (partial: Partial<DashboardState> | ((s: DashboardState) => Partial<DashboardState>)) => void,
) {
  set((state): Partial<DashboardState> => {
    let agents = state.agents
    let features = state.features
    let chatHistory = state.chatHistory
    let blockingIssues = state.blockingIssues
    let events = state.events

    if (event.type === 'agent_status_changed' && event.payload.agent_id) {
      agents = state.agents.map((a) =>
        a.id === event.payload.agent_id
          ? { ...a, status: (event.payload.status ?? a.status) as typeof a.status }
          : a
      )
    }

    if (event.type === 'feature_updated' && event.payload.feature_id) {
      features = state.features.map((f) =>
        f.id === event.payload.feature_id
          ? {
              ...f,
              status: (event.payload.status ?? f.status) as typeof f.status,
              blocking_issues: Array.isArray(event.payload.blocking_issues)
                ? (event.payload.blocking_issues as string[])
                : f.blocking_issues,
            }
          : f
      )
    }

    if (event.type === 'blocking_issue_created' && event.payload.issue_id) {
      const issue: BlockingIssue = {
        issue_id: String(event.payload.issue_id),
        issue_type: String(event.payload.issue_type ?? 'code_error'),
        feature_id: String(event.payload.feature_id ?? ''),
        detected_by: String(event.payload.detected_by ?? 'system'),
        detected_at: event.timestamp,
        description: String(event.payload.description ?? '阻塞问题已创建'),
        context: typeof event.payload.context === 'object' && event.payload.context !== null
          ? (event.payload.context as Record<string, unknown>)
          : {},
        resolved: false,
        resolved_at: '',
        resolution: '',
      }
      blockingIssues = [
        ...state.blockingIssues.filter((item) => item.issue_id !== issue.issue_id),
        issue,
      ]
    }

    if (event.type === 'blocking_issue_resolved' && event.payload.issue_id) {
      blockingIssues = state.blockingIssues.map((issue) =>
        issue.issue_id === event.payload.issue_id
          ? {
              ...issue,
              resolved: true,
              resolved_at: event.timestamp,
              resolution: String(event.payload.resolution ?? ''),
            }
          : issue
      )
    }

    if (event.type === 'pm_response' && event.payload.pm_response) {
      const pm = event.payload.pm_response as Record<string, string | undefined>
      const pmMsg: ChatMessage = {
        id: pm.id ?? `pm-${event.event_id}`,
        role: 'pm',
        content: pm.content ?? '',
        timestamp: pm.timestamp ?? event.timestamp,
        action_triggered: pm.action_triggered ?? '',
      }
      chatHistory = [...state.chatHistory, pmMsg]
    } else {
      events = [...state.events, event].slice(-200)
    }

    return {
      agents,
      features,
      chatHistory,
      blockingIssues,
      lastEventId: Math.max(state.lastEventId, event.event_id),
      events,
    }
  })
}
