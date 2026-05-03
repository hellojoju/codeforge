/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { startExecution, stopExecution, getExecutionStatus, listAgents, getAgentStatus, sendAgentMessage, interruptAgent, getAgentEvents, actions, fetchStateSnapshot, getEventsAfter, createCommand, getCommand, sendChat, listModules, upsertModule, listPendingApprovals, listBlockingIssues } from '@/lib/api'

global.fetch = vi.fn()

describe('API Client', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  describe('startExecution', () => {
    it('calls POST /api/execution/start and returns result on success', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, status: 'starting' }))
      )
      const result = await startExecution()
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/execution/start'),
        { method: 'POST' }
      )
      expect(result.success).toBe(true)
    })

    it('throws on failure with detail message', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: '执行已在运行中' }), { status: 409 })
      )
      await expect(startExecution()).rejects.toThrow('执行已在运行中')
    })

    it('throws generic error when detail is missing', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(startExecution()).rejects.toThrow('启动失败')
    })
  })

  describe('stopExecution', () => {
    it('calls POST /api/execution/stop and returns result', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, status: 'idle' }))
      )
      const result = await stopExecution()
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/execution/stop'),
        { method: 'POST' }
      )
      expect(result.success).toBe(true)
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: '无法停止' }), { status: 409 })
      )
      await expect(stopExecution()).rejects.toThrow('无法停止')
    })
  })

  describe('getExecutionStatus', () => {
    it('returns status data on success', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'running', thread_alive: true, error: null }))
      )
      const result = await getExecutionStatus()
      expect(result.status).toBe('running')
      expect(result.thread_alive).toBe(true)
    })

    it('returns idle on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 503 }))
      const result = await getExecutionStatus()
      expect(result.status).toBe('idle')
      expect(result.available).toBe(false)
    })
  })

  describe('listAgents', () => {
    it('returns agents list and total', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ agents: [{ id: 'agent-1', role: 'backend_dev', status: 'running' }], total: 1 }))
      )
      const result = await listAgents()
      expect(result.total).toBe(1)
      expect(result.agents).toHaveLength(1)
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(listAgents()).rejects.toThrow('Failed to list agents')
    })
  })

  describe('getAgentStatus', () => {
    it('returns flat agent detail from nested response', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({
          agent: { id: 'agent-1', role: 'backend_dev', status: 'running' },
          silence_status: { level: 'active', idle_seconds: 0, last_activity: '2024-01-01' },
        }))
      )
      const result = await getAgentStatus('agent-1')
      expect(result.id).toBe('agent-1')
      expect(result.silence_status?.level).toBe('active')
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 404 }))
      await expect(getAgentStatus('nonexistent')).rejects.toThrow('Failed to get agent status')
    })
  })

  describe('sendAgentMessage', () => {
    it('sends POST with message body', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, agent_id: 'agent-1' }))
      )
      await sendAgentMessage('agent-1', 'hello')
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agents/agent-1/message'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ message: 'hello' }),
        })
      )
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Agent 不存在' }), { status: 404 })
      )
      await expect(sendAgentMessage('bad', 'hi')).rejects.toThrow('Agent 不存在')
    })
  })

  describe('interruptAgent', () => {
    it('sends interrupt without force by default', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, agent_id: 'a1', force: false }))
      )
      const result = await interruptAgent('a1')
      expect(result.success).toBe(true)
    })

    it('sends force flag when provided', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, agent_id: 'a1', force: true }))
      )
      await interruptAgent('a1', { force: true })
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agents/a1/interrupt'),
        expect.objectContaining({ body: JSON.stringify({ force: true }) })
      )
    })
  })

  describe('fetchStateSnapshot', () => {
    it('returns snapshot data on success', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({
          agents: [],
          features: [],
          chat_history: [],
          module_assignments: [],
          blocking_issues: [],
          last_event_id: 42,
        }))
      )
      const result = await fetchStateSnapshot('test-project')
      expect(result.last_event_id).toBe(42)
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(fetchStateSnapshot('bad')).rejects.toThrow('Failed to fetch state')
    })
  })

  describe('getEventsAfter', () => {
    it('returns events array on success', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ events: [{ event_id: 1, type: 'test', payload: {}, timestamp: '2024-01-01' }] }))
      )
      const result = await getEventsAfter('test-project', 0)
      expect(result).toHaveLength(1)
      expect(result[0].event_id).toBe(1)
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(getEventsAfter('bad', 0)).rejects.toThrow('Failed to fetch events')
    })
  })

  describe('createCommand', () => {
    it('sends POST with correct body', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-1', status: 'accepted' }))
      )
      const result = await createCommand('approve_decision', 'feat-1', { feature_id: 'feat-1' }, 'proj-1')
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/dashboard/commands'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ project_id: 'proj-1', run_id: '', type: 'approve_decision', target_id: 'feat-1', payload: { feature_id: 'feat-1' } }),
        })
      )
      expect(result.command_id).toBe('cmd-1')
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(createCommand('bad')).rejects.toThrow('Failed to create command')
    })
  })

  describe('getCommand', () => {
    it('returns command data', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ command_id: 'cmd-1', status: 'completed' }))
      )
      const result = await getCommand('cmd-1')
      expect(result.command_id).toBe('cmd-1')
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 404 }))
      await expect(getCommand('nonexistent')).rejects.toThrow('Failed to get command')
    })
  })

  describe('sendChat', () => {
    it('sends POST with correct body and returns response', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: 'OK', timestamp: '2024-01-01', action_triggered: '' } }))
      )
      const result = await sendChat('build the app', 'proj-1')
      expect(result.success).toBe(true)
      expect(result.message_id).toBe('msg-1')
    })

    it('throws timeout error on abort', async () => {
      vi.useFakeTimers()
      vi.mocked(fetch).mockImplementationOnce(() => {
        return new Promise((_, reject) => {
          setTimeout(() => reject(new DOMException('Aborted', 'AbortError')), 30000)
        }) as any
      })
      const promise = sendChat('hello')
      vi.advanceTimersByTime(30000)
      await expect(promise).rejects.toThrow('请求超时，请稍后重试')
      vi.useRealTimers()
    })

    it('throws generic error on non-abort failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(sendChat('hi')).rejects.toThrow('Failed to send chat')
    })
  })

  describe('listModules', () => {
    it('returns modules array', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ modules: [{ module_id: 'mod-1', role: 'backend_dev', agent_ids: ['a1'] }] }))
      )
      const result = await listModules()
      expect(result).toHaveLength(1)
    })

    it('adds role filter when provided', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ modules: [] }))
      )
      await listModules('backend_dev')
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('role=backend_dev')
      )
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(listModules()).rejects.toThrow('Failed to fetch modules')
    })
  })

  describe('upsertModule', () => {
    it('sends POST and returns assignment', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ assignment: { module_id: 'mod-1', role: 'qa', agent_ids: ['a1'] } }))
      )
      const result = await upsertModule({ module_id: 'mod-1', role: 'qa', assigned_agent_id: 'a1' } as any)
      expect(result.module_id).toBe('mod-1')
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(upsertModule({} as any)).rejects.toThrow('Failed to upsert module')
    })
  })

  describe('listPendingApprovals', () => {
    it('returns approvals array', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ approvals: [{ id: 'pa-1' }] }))
      )
      const result = await listPendingApprovals()
      expect(result).toHaveLength(1)
    })

    it('throws on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      await expect(listPendingApprovals()).rejects.toThrow('Failed to fetch pending approvals')
    })
  })

  describe('actions helpers', () => {
    it('approve calls createCommand with approve_decision', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-1', status: 'accepted' }))
      )
      const result = await actions.approve('feat-1', 'proj-1')
      expect(result.command_id).toBe('cmd-1')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'proj-1', run_id: '', type: 'approve_decision', target_id: 'feat-1', payload: { feature_id: 'feat-1' } }),
        })
      )
    })

    it('reject calls createCommand with reject_decision', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-2', status: 'accepted' }))
      )
      await actions.reject('feat-2')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'default', run_id: '', type: 'reject_decision', target_id: 'feat-2', payload: { feature_id: 'feat-2' } }),
        })
      )
    })

    it('pause calls createCommand with pause_run', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-3', status: 'accepted' }))
      )
      await actions.pause('agent-1')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'default', run_id: '', type: 'pause_run', target_id: 'agent-1', payload: { agent_id: 'agent-1' } }),
        })
      )
    })

    it('resume calls createCommand with resume_run', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-4', status: 'accepted' }))
      )
      await actions.resume('agent-1')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'default', run_id: '', type: 'resume_run', target_id: 'agent-1', payload: { agent_id: 'agent-1' } }),
        })
      )
    })

    it('retry calls createCommand with retry_feature', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-5', status: 'accepted' }))
      )
      await actions.retry('feat-3')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'default', run_id: '', type: 'retry_feature', target_id: 'feat-3', payload: { feature_id: 'feat-3' } }),
        })
      )
    })

    it('skip calls createCommand with skip_feature', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 1, command_id: 'cmd-6', status: 'accepted' }))
      )
      await actions.skip('feat-4')
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ project_id: 'default', run_id: '', type: 'skip_feature', target_id: 'feat-4', payload: { feature_id: 'feat-4' } }),
        })
      )
    })
  })

  describe('getAgentEvents', () => {
    it('returns events from {events: [...]} response', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ events: [{ id: '1' }, { id: '2' }] }))
      )
      const result = await getAgentEvents()
      expect(result).toHaveLength(2)
    })

    it('returns events from bare array response', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: '1' }]))
      )
      const result = await getAgentEvents()
      expect(result).toHaveLength(1)
    })

    it('returns empty array on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }))
      const result = await getAgentEvents()
      expect(result).toEqual([])
    })
  })

  describe('listBlockingIssues', () => {
    it('returns blocking issues array', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ issues: [{ issue_id: 'i1', issue_type: 'code_error', feature_id: 'F1' }] }))
      )
      const result = await listBlockingIssues()
      expect(result).toHaveLength(1)
      expect(result[0].issue_id).toBe('i1')
    })
  })
})
