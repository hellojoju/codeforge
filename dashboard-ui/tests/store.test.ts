/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useDashboardStore } from '@/lib/store'
import type { DashboardEvent } from '@/lib/types'

// Mock all API imports
vi.mock('@/lib/api', () => ({
  fetchStateSnapshot: vi.fn(),
  getEventsAfter: vi.fn(),
  actions: {
    approve: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
    reject: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
    pause: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
    resume: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
    retry: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
    skip: vi.fn(() => Promise.resolve({ command_id: 'cmd-1' })),
  },
  startExecution: vi.fn(() => Promise.resolve({ success: true, status: 'starting' })),
  stopExecution: vi.fn(() => Promise.resolve({ success: true, status: 'idle' })),
  getExecutionStatus: vi.fn(() => Promise.resolve({ status: 'running', thread_alive: true, error: null })),
  listAgents: vi.fn(() => Promise.resolve({ agents: [], total: 0 })),
  getAgentStatus: vi.fn(),
  sendAgentMessage: vi.fn(),
  interruptAgent: vi.fn(),
  getAgentEvents: vi.fn(() => Promise.resolve([])),
  listBlockingIssues: vi.fn(() => Promise.resolve([])),
}))

describe('DashboardStore', () => {
  /** Test helper: build a minimal DashboardEvent for store logic tests. */
  const makeEvent = (overrides: Partial<DashboardEvent> = {}): DashboardEvent => ({
    schema_version: 1,
    event_id: 1,
    project_id: 'default',
    run_id: '',
    type: 'agent_log',
    timestamp: '2024-01-01T00:00:00Z',
    caused_by_command_id: null,
    payload: {},
    ...overrides,
  })

  beforeEach(() => {
    useDashboardStore.setState({
      projectId: 'default',
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
    })
  })

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useDashboardStore.getState()
      expect(state.projectId).toBe('default')
      expect(state.executionStatus).toBe('idle')
      expect(state.executionError).toBeNull()
      expect(state.agents).toEqual([])
      expect(state.connectionStatus).toBe('connecting')
    })
  })

  describe('setProjectId', () => {
    it('updates projectId', () => {
      useDashboardStore.getState().setProjectId('test-project')
      expect(useDashboardStore.getState().projectId).toBe('test-project')
    })
  })

  describe('setConnectionStatus', () => {
    it('updates connection status', () => {
      useDashboardStore.getState().setConnectionStatus('connected')
      expect(useDashboardStore.getState().connectionStatus).toBe('connected')
    })
  })

  describe('addChatMessage', () => {
    it('appends message to chatHistory', () => {
      const msg = { id: 'msg-1', role: 'user' as const, content: 'hello', timestamp: '2024-01-01', action_triggered: '' }
      useDashboardStore.getState().addChatMessage(msg)
      expect(useDashboardStore.getState().chatHistory).toContainEqual(msg)
    })
  })

  describe('pushEvent', () => {
    it('appends event to events array', () => {
      const event = makeEvent({ event_id: 1, type: 'agent_status_changed', timestamp: '2024-01-01' })
      useDashboardStore.getState().pushEvent(event)
      expect(useDashboardStore.getState().events).toContainEqual(event)
    })
  })

  describe('applyEvent', () => {
    it('updates agent status on agent_status_changed', () => {
      const state = useDashboardStore.getState()
      useDashboardStore.setState({
        agents: [{ id: 'agent-1', role: 'backend_dev', status: 'idle' } as any],
      })
      const event = makeEvent({
        event_id: 1,
        type: 'agent_status_changed',
        payload: { agent_id: 'agent-1', status: 'running' },
        timestamp: '2024-01-01',
      })
      state.applyEvent(event)
      expect(useDashboardStore.getState().agents[0].status).toBe('running')
    })

    it('updates feature status on feature_updated', () => {
      useDashboardStore.setState({
        features: [{ id: 'feat-1', name: 'test', status: 'pending' } as any],
      })
      const event = makeEvent({
        event_id: 1,
        type: 'feature_updated',
        payload: { feature_id: 'feat-1', status: 'in_progress' },
        timestamp: '2024-01-01',
      })
      useDashboardStore.getState().applyEvent(event)
      expect(useDashboardStore.getState().features[0].status).toBe('in_progress')
    })

    it('adds pm_response to chatHistory', () => {
      const event = makeEvent({
        event_id: 1,
        type: 'pm_response',
        payload: { pm_response: { id: 'pm-1', content: '好的', timestamp: '2024-01-01', action_triggered: '' } },
        timestamp: '2024-01-01',
      })
      useDashboardStore.getState().applyEvent(event)
      expect(useDashboardStore.getState().chatHistory.length).toBeGreaterThan(0)
    })
  })

  describe('startExecution', () => {
    it('sets executionStatus to starting on success', async () => {
      await useDashboardStore.getState().startExecution()
      expect(useDashboardStore.getState().executionStatus).toBe('starting')
    })

    it('sets executionError and status to error on failure', async () => {
      const { startExecution } = await import('@/lib/api')
      vi.mocked(startExecution).mockRejectedValueOnce(new Error('连接被拒绝'))
      await useDashboardStore.getState().startExecution()
      const state = useDashboardStore.getState()
      expect(state.executionStatus).toBe('error')
      expect(state.executionError).toBe('连接被拒绝')
    })
  })

  describe('stopExecution', () => {
    it('sets executionStatus to idle on success', async () => {
      await useDashboardStore.getState().stopExecution()
      expect(useDashboardStore.getState().executionStatus).toBe('idle')
    })

    it('sets executionError on failure', async () => {
      const { stopExecution } = await import('@/lib/api')
      vi.mocked(stopExecution).mockRejectedValueOnce(new Error('无法停止'))
      await useDashboardStore.getState().stopExecution()
      expect(useDashboardStore.getState().executionError).toBe('无法停止')
    })
  })

  describe('fetchExecutionStatus', () => {
    it('updates executionStatus from API', async () => {
      await useDashboardStore.getState().fetchExecutionStatus()
      expect(useDashboardStore.getState().executionStatus).toBe('running')
    })
  })

  describe('fetchAgents', () => {
    it('updates agents list from API', async () => {
      const { listAgents } = await import('@/lib/api')
      vi.mocked(listAgents).mockResolvedValueOnce({
        agents: [{ id: 'a1', role: 'backend_dev', status: 'running' } as any],
        total: 1,
      })
      await useDashboardStore.getState().fetchAgents()
      expect(useDashboardStore.getState().agents).toHaveLength(1)
      expect(useDashboardStore.getState().agents[0].id).toBe('a1')
    })
  })

  describe('fetchEvents', () => {
    it('updates eventStream from API', async () => {
      const { getAgentEvents } = await import('@/lib/api')
      vi.mocked(getAgentEvents).mockResolvedValueOnce([{ id: 'e1', agent_id: 'a1', type: 'tool_call', timestamp: new Date().toISOString(), message: 'tool call' }])
      await useDashboardStore.getState().fetchEvents()
      expect(useDashboardStore.getState().eventStream).toHaveLength(1)
    })
  })

  describe('action commands', () => {
    it('approve calls actions.approve', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().approve('feat-1')
      expect(actions.approve).toHaveBeenCalledWith('feat-1', 'default')
    })

    it('reject calls actions.reject', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().reject('feat-1')
      expect(actions.reject).toHaveBeenCalledWith('feat-1', 'default')
    })

    it('pause calls actions.pause', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().pause('agent-1')
      expect(actions.pause).toHaveBeenCalledWith('agent-1', 'default')
    })

    it('resume calls actions.resume', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().resume('agent-1')
      expect(actions.resume).toHaveBeenCalledWith('agent-1', 'default')
    })

    it('retry calls actions.retry', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().retry('feat-1')
      expect(actions.retry).toHaveBeenCalledWith('feat-1', 'default')
    })

    it('skip calls actions.skip', async () => {
      const { actions } = await import('@/lib/api')
      await useDashboardStore.getState().skip('feat-1')
      expect(actions.skip).toHaveBeenCalledWith('feat-1', 'default')
    })
  })

  describe('loadSnapshot', () => {
    it('loads snapshot and updates state on success', async () => {
      const { fetchStateSnapshot } = await import('@/lib/api')
      const snapshot = {
        agents: [{ id: 'a1', role: 'backend_dev', status: 'running' }],
        features: [{ id: 'f1', name: 'auth', status: 'pending' }],
        chat_history: [{ id: 'c1', role: 'user', content: 'hi', timestamp: '2024-01-01', action_triggered: '' }],
        module_assignments: [{ module_id: 'mod-1', role: 'backend_dev', agent_ids: ['a1'] }],
        blocking_issues: [],
        last_event_id: 10,
      }
      vi.mocked(fetchStateSnapshot).mockResolvedValueOnce(snapshot as any)
      await useDashboardStore.getState().loadSnapshot()
      const state = useDashboardStore.getState()
      expect(state.agents).toHaveLength(1)
      expect(state.features).toHaveLength(1)
      expect(state.chatHistory).toHaveLength(1)
      expect(state.moduleAssignments).toHaveLength(1)
      expect(state.blockingIssues).toHaveLength(0)
      expect(state.lastEventId).toBe(10)
      expect(state.connectionStatus).toBe('connected')
    })

    it('sets connectionStatus to error on failure', async () => {
      const { fetchStateSnapshot } = await import('@/lib/api')
      vi.mocked(fetchStateSnapshot).mockRejectedValueOnce(new Error('Network error'))
      await useDashboardStore.getState().loadSnapshot()
      expect(useDashboardStore.getState().connectionStatus).toBe('error')
    })
  })

  describe('loadEvents edge cases', () => {
    it('returns early when lastEventId is 0', async () => {
      const { getEventsAfter } = await import('@/lib/api')
      useDashboardStore.setState({ lastEventId: 0 })
      await useDashboardStore.getState().loadEvents()
      expect(getEventsAfter).not.toHaveBeenCalled()
    })

    it('fetches and applies events when lastEventId > 0', async () => {
      const { getEventsAfter } = await import('@/lib/api')
      useDashboardStore.setState({
        lastEventId: 5,
        projectId: 'test-proj',
        agents: [{ id: 'a1', role: 'backend_dev', status: 'idle' } as any],
      })
      vi.mocked(getEventsAfter).mockResolvedValueOnce([
        makeEvent({ event_id: 6, type: 'agent_status_changed', payload: { agent_id: 'a1', status: 'running' }, timestamp: '2024-01-01' }),
        makeEvent({ event_id: 7, type: 'feature_updated', payload: { feature_id: 'f1', status: 'done' }, timestamp: '2024-01-01' }),
      ])
      await useDashboardStore.getState().loadEvents()
      expect(getEventsAfter).toHaveBeenCalledWith('test-proj', 5)
      expect(useDashboardStore.getState().lastEventId).toBe(7)
    })

    it('does not throw on fetch failure', async () => {
      const { getEventsAfter } = await import('@/lib/api')
      useDashboardStore.setState({ lastEventId: 1 })
      vi.mocked(getEventsAfter).mockRejectedValueOnce(new Error('Network error'))
      await expect(useDashboardStore.getState().loadEvents()).resolves.not.toThrow()
    })

    it('handles empty events array', async () => {
      const { getEventsAfter } = await import('@/lib/api')
      useDashboardStore.setState({ lastEventId: 5, projectId: 'test-proj' })
      vi.mocked(getEventsAfter).mockResolvedValueOnce([])
      await useDashboardStore.getState().loadEvents()
      // lastEventId should remain 5 since no events were returned
      expect(useDashboardStore.getState().lastEventId).toBe(5)
    })
  })

  describe('loadSnapshot edge cases', () => {
    it('loads snapshot with empty module_assignments fallback', async () => {
      const { fetchStateSnapshot } = await import('@/lib/api')
      const snapshot = {
        agents: [],
        features: [],
        chat_history: [],
        blocking_issues: [],
        last_event_id: 0,
      }
      vi.mocked(fetchStateSnapshot).mockResolvedValueOnce(snapshot as any)
      await useDashboardStore.getState().loadSnapshot()
      const state = useDashboardStore.getState()
      expect(state.moduleAssignments).toEqual([])
      expect(state.connectionStatus).toBe('connected')
    })
  })

  describe('applyEvent edge cases', () => {
    it('handles pm_response event with missing optional fields', async () => {
      const event = {
        event_id: 42,
        type: 'pm_response',
        payload: { pm_response: { content: 'hello' } },
        timestamp: '2024-01-01',
      }
      useDashboardStore.getState().applyEvent(event as any)
      const state = useDashboardStore.getState()
      expect(state.chatHistory.some((m) => m.role === 'pm')).toBe(true)
      expect(state.lastEventId).toBe(42)
    })

    it('does not add non-pm_response event to chatHistory', async () => {
      const initialLen = useDashboardStore.getState().chatHistory.length
      const event = makeEvent({
        event_id: 100,
        type: 'agent_status_changed',
        payload: { agent_id: 'nonexistent', status: 'idle' },
        timestamp: '2024-01-01',
      })
      useDashboardStore.getState().applyEvent(event)
      expect(useDashboardStore.getState().chatHistory.length).toBe(initialLen)
    })
  })

  describe('fetchAgentDetail', () => {
    it('fetches and caches agent detail', async () => {
      const { getAgentStatus } = await import('@/lib/api')
      const detail = { id: 'a1', role: 'backend_dev', status: 'running' } as any
      vi.mocked(getAgentStatus).mockResolvedValueOnce(detail)
      await useDashboardStore.getState().fetchAgentDetail('a1')
      expect(useDashboardStore.getState().agentDetails.get('a1')).toBe(detail)
    })

    it('does not throw on fetch failure', async () => {
      const { getAgentStatus } = await import('@/lib/api')
      vi.mocked(getAgentStatus).mockRejectedValueOnce(new Error('Not found'))
      await expect(useDashboardStore.getState().fetchAgentDetail('a1')).resolves.not.toThrow()
    })
  })

  describe('sendMessage', () => {
    it('sends message to agent successfully', async () => {
      const { sendAgentMessage } = await import('@/lib/api')
      vi.mocked(sendAgentMessage).mockResolvedValueOnce({ success: true, agent_id: 'a1' })
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      await useDashboardStore.getState().sendMessage('a1', 'hello')
      expect(sendAgentMessage).toHaveBeenCalledWith('a1', 'hello')
      expect(consoleSpy).not.toHaveBeenCalled()
      consoleSpy.mockRestore()
    })

    it('logs error on failure without throwing', async () => {
      const { sendAgentMessage } = await import('@/lib/api')
      vi.mocked(sendAgentMessage).mockRejectedValueOnce(new Error('Failed'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      await expect(useDashboardStore.getState().sendMessage('a1', 'hi')).resolves.not.toThrow()
      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('interruptAgent', () => {
    it('sends interrupt without force by default', async () => {
      const { interruptAgent } = await import('@/lib/api')
      vi.mocked(interruptAgent).mockResolvedValueOnce({ success: true, agent_id: 'a1', force: false })
      await useDashboardStore.getState().interruptAgent('a1')
      expect(interruptAgent).toHaveBeenCalledWith('a1', { force: false })
    })

    it('sends interrupt with force flag', async () => {
      const { interruptAgent } = await import('@/lib/api')
      vi.mocked(interruptAgent).mockResolvedValueOnce({ success: true, agent_id: 'a1', force: true })
      await useDashboardStore.getState().interruptAgent('a1', true)
      expect(interruptAgent).toHaveBeenCalledWith('a1', { force: true })
    })

    it('logs error on failure without throwing', async () => {
      const { interruptAgent } = await import('@/lib/api')
      vi.mocked(interruptAgent).mockRejectedValueOnce(new Error('Not found'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      await expect(useDashboardStore.getState().interruptAgent('a1')).resolves.not.toThrow()
      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('fetchAgents populates agentDetails cache', () => {
    it('fills agentDetails Map on fetch', async () => {
      const { listAgents } = await import('@/lib/api')
      const agent = { id: 'a1', role: 'backend_dev', status: 'running' }
      vi.mocked(listAgents).mockResolvedValueOnce({ agents: [agent], total: 1 } as any)
      await useDashboardStore.getState().fetchAgents()
      const state = useDashboardStore.getState()
      expect(state.agentDetails.get('a1')).toEqual(agent)
    })

    it('silently fails on API error', async () => {
      const { listAgents } = await import('@/lib/api')
      vi.mocked(listAgents).mockRejectedValueOnce(new Error('Network error'))
      await expect(useDashboardStore.getState().fetchAgents()).resolves.not.toThrow()
    })
  })

  describe('fetchExecutionStatus error handling', () => {
    it('silently fails on API error', async () => {
      const { getExecutionStatus } = await import('@/lib/api')
      vi.mocked(getExecutionStatus).mockRejectedValueOnce(new Error('API unavailable'))
      await expect(useDashboardStore.getState().fetchExecutionStatus()).resolves.not.toThrow()
    })
  })

  describe('fetchEvents error handling', () => {
    it('silently fails on API error', async () => {
      const { getAgentEvents } = await import('@/lib/api')
      vi.mocked(getAgentEvents).mockRejectedValueOnce(new Error('Network error'))
      await expect(useDashboardStore.getState().fetchEvents()).resolves.not.toThrow()
    })
  })

  describe('startExecution non-Error', () => {
    it('uses fallback message for non-Error thrown', async () => {
      const { startExecution } = await import('@/lib/api')
      vi.mocked(startExecution).mockRejectedValueOnce('string error')
      await useDashboardStore.getState().startExecution()
      const state = useDashboardStore.getState()
      expect(state.executionStatus).toBe('error')
      expect(state.executionError).toBe('启动失败')
    })
  })

  describe('stopExecution non-Error', () => {
    it('uses fallback message for non-Error thrown', async () => {
      const { stopExecution } = await import('@/lib/api')
      vi.mocked(stopExecution).mockRejectedValueOnce('string error')
      await useDashboardStore.getState().stopExecution()
      const state = useDashboardStore.getState()
      expect(state.executionError).toBe('停止失败')
    })
  })
})
