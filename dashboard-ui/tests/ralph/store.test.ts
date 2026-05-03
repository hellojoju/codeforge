/**
 * Ralph Runtime Console - Store Tests
 *
 * 测试 Zustand Store 的所有 actions 和状态管理
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type {
  WorkUnit,
  WorkUnitStatus,
  Tab,
  PendingAction,
  Blocker,
  RunStatus,
  RalphEvent,
  RalphEventType,
  CreateCommandRequest,
} from '../../lib/ralph-types'

// ==================== Mock Setup ====================

const mockListWorkUnits = vi.fn()
const mockCreateCommand = vi.fn()
const mockGetSummary = vi.fn()
const mockListPendingActions = vi.fn()
const mockListBlockers = vi.fn()
const mockListCommands = vi.fn()

vi.mock('../../lib/ralph-api', () => ({
  listWorkUnits: (...args: unknown[]) => mockListWorkUnits(...args),
  createCommand: (...args: unknown[]) => mockCreateCommand(...args),
  getSummary: (...args: unknown[]) => mockGetSummary(...args),
  listPendingActions: (...args: unknown[]) => mockListPendingActions(...args),
  listBlockers: (...args: unknown[]) => mockListBlockers(...args),
  listCommands: (...args: unknown[]) => mockListCommands(...args),
}))

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// ==================== Test Data ====================

const createMockWorkUnit = (id: string, status: WorkUnitStatus = 'draft'): WorkUnit => ({
  work_id: id,
  work_type: 'development',
  title: `Test Work Unit ${id}`,
  status,
  background: 'Test background',
  target: 'Test target',
  scope_allow: [],
  scope_deny: [],
  dependencies: [],
  input_files: [],
  expected_output: 'Test output',
  acceptance_criteria: [],
  test_command: '',
  rollback_strategy: '',
  context_pack: null,
  task_harness: null,
  assumptions: [],
  impact_if_wrong: '',
  risk_notes: '',
  producer_role: 'developer',
  reviewer_role: 'reviewer',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
})

// Helper function for creating mock tabs (kept for future use)
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _createMockTab = (id: string, type: Tab['type'] = 'overview'): Tab => ({
  id,
  label: `Tab ${id}`,
  type,
  pinned: false,
  created_at: Date.now(),
})

const createMockPendingAction = (id: string): PendingAction => ({
  action_id: id,
  action_type: 'manual_intervention',
  work_id: 'work-1',
  description: 'Test pending action',
  context: {},
  created_at: new Date().toISOString(),
})

const createMockBlocker = (id: string): Blocker => ({
  blocker_id: id,
  work_id: 'work-1',
  reason: 'Test blocker',
  category: 'dependency',
  created_at: new Date().toISOString(),
  resolved: false,
})

const createMockRunStatus = (): RunStatus => ({
  total: 10,
  running: 2,
  needs_review: 3,
  blocked: 1,
  accepted: 4,
  failed: 0,
  latest_event: null,
  next_action: 'Continue processing',
})

// ==================== Store Factory for Testing ====================

async function createTestStore(initialTabs: Tab[] = []) {
  // Reset module cache to get fresh store instance
  vi.resetModules()
  const { createRalphStoreForTest, resetRalphStore } = await import('../../lib/ralph-store')
  resetRalphStore()
  return createRalphStoreForTest(initialTabs)
}

// ==================== Test Suite ====================

describe('Ralph Store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
    localStorageMock.setItem.mockImplementation(() => {})
  })

  afterEach(() => {
    vi.resetModules()
  })

  // ==================== WorkUnit Tests ====================

  describe('WorkUnit Actions', () => {
    it('should set work units', async () => {
      const store = await createTestStore()
      const units = [createMockWorkUnit('1'), createMockWorkUnit('2')]

      store.getState().setWorkUnits(units)

      expect(store.getState().workUnits).toHaveLength(2)
      expect(store.getState().workUnits[0].work_id).toBe('1')
    })

    it('should update specific work unit', async () => {
      const store = await createTestStore()
      const units = [createMockWorkUnit('1', 'draft'), createMockWorkUnit('2', 'draft')]
      store.getState().setWorkUnits(units)

      store.getState().updateWorkUnit('1', { status: 'running' })

      expect(store.getState().workUnits[0].status).toBe('running')
      expect(store.getState().workUnits[1].status).toBe('draft')
    })

    it('should set selected work unit', async () => {
      const store = await createTestStore()
      const unit = createMockWorkUnit('1')

      store.getState().setSelectedWorkUnit(unit)

      expect(store.getState().selectedWorkUnit).toEqual(unit)
    })

    it('should clear selected work unit when null is passed', async () => {
      const store = await createTestStore()
      store.getState().setSelectedWorkUnit(createMockWorkUnit('1'))

      store.getState().setSelectedWorkUnit(null)

      expect(store.getState().selectedWorkUnit).toBeNull()
    })
  })

  // ==================== Filter Tests ====================

  describe('Status Filter', () => {
    it('should set status filter', async () => {
      const store = await createTestStore()

      store.getState().setStatusFilter('running')

      expect(store.getState().statusFilter).toBe('running')
    })

    it('should allow "all" as filter value', async () => {
      const store = await createTestStore()

      store.getState().setStatusFilter('all')

      expect(store.getState().statusFilter).toBe('all')
    })

    it('should fetch work units with filter', async () => {
      const store = await createTestStore()
      const units = [createMockWorkUnit('1', 'running')]
      mockListWorkUnits.mockResolvedValue(units)

      store.getState().setStatusFilter('running')
      await store.getState().fetchWorkUnits()

      expect(mockListWorkUnits).toHaveBeenCalledWith('running')
      expect(store.getState().workUnits).toEqual(units)
    })

    it('should fetch work units without filter when all', async () => {
      const store = await createTestStore()
      const units = [createMockWorkUnit('1')]
      mockListWorkUnits.mockResolvedValue(units)

      store.getState().setStatusFilter('all')
      await store.getState().fetchWorkUnits()

      expect(mockListWorkUnits).toHaveBeenCalledWith(undefined)
    })

    it('should handle fetch error gracefully', async () => {
      const store = await createTestStore()
      mockListWorkUnits.mockRejectedValue(new Error('Network error'))

      await store.getState().fetchWorkUnits()

      expect(store.getState().loading).toBe(false)
      expect(store.getState().workUnits).toEqual([])
    })
  })

  // ==================== Tab Tests ====================

  describe('Tab Management', () => {
    it('should add a new tab', async () => {
      const store = await createTestStore()

      store.getState().addTab({ label: 'Test Tab', type: 'overview', pinned: false })

      expect(store.getState().tabs).toHaveLength(1)
      expect(store.getState().tabs[0].label).toBe('Test Tab')
      expect(store.getState().activeTabId).toBe(store.getState().tabs[0].id)
    })

    it('should switch to existing tab with same type and work_id', async () => {
      const store = await createTestStore()
      store.getState().addTab({ label: 'Tab 1', type: 'work_unit', work_id: 'work-1', pinned: false })
      const firstTabId = store.getState().tabs[0].id

      store.getState().addTab({ label: 'Tab 2', type: 'work_unit', work_id: 'work-1', pinned: false })

      expect(store.getState().tabs).toHaveLength(1)
      expect(store.getState().activeTabId).toBe(firstTabId)
    })

    it('should limit tabs to maximum of 8', async () => {
      const store = await createTestStore()

      // Add 8 tabs with different work_ids to avoid deduplication
      for (let i = 0; i < 8; i++) {
        store.getState().addTab({ label: `Tab ${i}`, type: 'work_unit', work_id: `work-${i}`, pinned: false })
      }

      expect(store.getState().tabs).toHaveLength(8)

      // Add 9th tab - should remove oldest non-pinned tab
      store.getState().addTab({ label: 'Tab 9', type: 'work_unit', work_id: 'work-9', pinned: false })

      expect(store.getState().tabs).toHaveLength(8)
      expect(store.getState().tabs.some((t) => t.label === 'Tab 0')).toBe(false)
    })

    it('should not remove pinned tabs when at limit', async () => {
      const store = await createTestStore()

      // Add 7 regular tabs and 1 pinned tab with different work_ids
      for (let i = 0; i < 7; i++) {
        store.getState().addTab({ label: `Tab ${i}`, type: 'work_unit', work_id: `work-${i}`, pinned: false })
      }
      store.getState().addTab({ label: 'Pinned Tab', type: 'work_unit', work_id: 'work-pinned', pinned: true })

      // Add another tab - should remove oldest non-pinned, not pinned
      store.getState().addTab({ label: 'New Tab', type: 'work_unit', work_id: 'work-new', pinned: false })

      expect(store.getState().tabs).toHaveLength(8)
      expect(store.getState().tabs.some((t) => t.label === 'Pinned Tab')).toBe(true)
    })

    it('should not add tab when all tabs are pinned and at limit', async () => {
      const store = await createTestStore()

      // Add 8 pinned tabs with different work_ids
      for (let i = 0; i < 8; i++) {
        store.getState().addTab({ label: `Tab ${i}`, type: 'work_unit', work_id: `work-${i}`, pinned: true })
      }

      // Try to add 9th tab
      store.getState().addTab({ label: 'New Tab', type: 'work_unit', work_id: 'work-new', pinned: false })

      expect(store.getState().tabs).toHaveLength(8)
      expect(store.getState().tabs.some((t) => t.label === 'New Tab')).toBe(false)
    })

    it('should close non-pinned tab', async () => {
      const store = await createTestStore()
      store.getState().addTab({ label: 'Tab 1', type: 'overview', pinned: false })
      const tabId = store.getState().tabs[0].id

      store.getState().closeTab(tabId)

      expect(store.getState().tabs).toHaveLength(0)
    })

    it('should not close pinned tab', async () => {
      const store = await createTestStore()
      store.getState().addTab({ label: 'Tab 1', type: 'overview', pinned: true })
      const tabId = store.getState().tabs[0].id

      store.getState().closeTab(tabId)

      expect(store.getState().tabs).toHaveLength(1)
    })

    it('should switch to another tab when closing active tab', async () => {
      const store = await createTestStore()
      store.getState().addTab({ label: 'Tab 1', type: 'work_unit', work_id: 'work-1', pinned: false })
      store.getState().addTab({ label: 'Tab 2', type: 'work_unit', work_id: 'work-2', pinned: false })
      const firstTabId = store.getState().tabs[0].id
      const secondTabId = store.getState().tabs[1].id

      store.getState().closeTab(secondTabId)

      expect(store.getState().activeTabId).toBe(firstTabId)
    })

    it('should persist tabs to localStorage', async () => {
      const store = await createTestStore()

      store.getState().addTab({ label: 'Test Tab', type: 'overview', pinned: false })

      expect(localStorageMock.setItem).toHaveBeenCalled()
      const [key, value] = localStorageMock.setItem.mock.calls[0]
      expect(key).toBe('ralph-tabs')
      const savedTabs = JSON.parse(value as string)
      expect(savedTabs).toHaveLength(1)
      expect(savedTabs[0].label).toBe('Test Tab')
    })

    it('should set active tab', async () => {
      const store = await createTestStore()
      store.getState().addTab({ label: 'Tab 1', type: 'work_unit', work_id: 'work-1', pinned: false })
      store.getState().addTab({ label: 'Tab 2', type: 'work_unit', work_id: 'work-2', pinned: false })
      const secondTabId = store.getState().tabs[1].id

      store.getState().setActiveTab(secondTabId)

      expect(store.getState().activeTabId).toBe(secondTabId)
    })
  })

  // ==================== Approval Tests ====================

  describe('Approval Actions', () => {
    it('should set pending actions', async () => {
      const store = await createTestStore()
      const actions = [createMockPendingAction('1'), createMockPendingAction('2')]

      store.getState().setPendingActions(actions)

      expect(store.getState().pendingActions).toHaveLength(2)
    })

    it('should set blockers', async () => {
      const store = await createTestStore()
      const blockers = [createMockBlocker('1'), createMockBlocker('2')]

      store.getState().setBlockers(blockers)

      expect(store.getState().blockers).toHaveLength(2)
    })

    it('should set run status', async () => {
      const store = await createTestStore()
      const status = createMockRunStatus()

      store.getState().setRunStatus(status)

      expect(store.getState().runStatus).toEqual(status)
    })

    it('should clear run status when null is passed', async () => {
      const store = await createTestStore()
      store.getState().setRunStatus(createMockRunStatus())

      store.getState().setRunStatus(null)

      expect(store.getState().runStatus).toBeNull()
    })
  })

  // ==================== WebSocket Tests ====================

  describe('WebSocket Actions', () => {
    it('should set connected status', async () => {
      const store = await createTestStore()

      store.getState().setConnected(true)

      expect(store.getState().connected).toBe(true)
    })

    it('should handle work_unit_created event', async () => {
      const store = await createTestStore()
      const newUnit = createMockWorkUnit('new-1')
      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_created',
        work_id: null,
        command_id: null,
        data: { work_unit: newUnit },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().workUnits).toHaveLength(1)
      expect(store.getState().workUnits[0].work_id).toBe('new-1')
      expect(store.getState().lastEvent).toEqual(event)
    })

    it('should handle work_unit_status_changed event', async () => {
      const store = await createTestStore()
      store.getState().setWorkUnits([createMockWorkUnit('1', 'draft')])

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_status_changed',
        work_id: '1',
        command_id: null,
        data: { updates: { status: 'running' } },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().workUnits[0].status).toBe('running')
    })

    it('should handle review_completed event with passed conclusion', async () => {
      const store = await createTestStore()
      store.getState().setWorkUnits([createMockWorkUnit('1', 'needs_review')])

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'review_completed',
        work_id: '1',
        command_id: null,
        data: { review_result: { conclusion: 'passed' } },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().workUnits[0].status).toBe('accepted')
    })

    it('should handle review_completed event with failed conclusion', async () => {
      const store = await createTestStore()
      store.getState().setWorkUnits([createMockWorkUnit('1', 'needs_review')])

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'review_completed',
        work_id: '1',
        command_id: null,
        data: { review_result: { conclusion: 'failed' } },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().workUnits[0].status).toBe('needs_rework')
    })

    it('should handle blocker_created event', async () => {
      const store = await createTestStore()
      const newBlocker = createMockBlocker('block-1')

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'blocker_created',
        work_id: '1',
        command_id: null,
        data: { blocker: newBlocker },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().blockers).toHaveLength(1)
      expect(store.getState().blockers[0].blocker_id).toBe('block-1')
    })

    it('should handle blocker_resolved event', async () => {
      const store = await createTestStore()
      store.getState().setBlockers([createMockBlocker('block-1')])

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'blocker_resolved',
        work_id: '1',
        command_id: null,
        data: { blocker_id: 'block-1' },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().blockers[0].resolved).toBe(true)
    })

    it('should handle pending_action_created event', async () => {
      const store = await createTestStore()
      const newAction = createMockPendingAction('action-1')

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'pending_action_created',
        work_id: '1',
        command_id: null,
        data: { pending_action: newAction },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().pendingActions).toHaveLength(1)
      expect(store.getState().pendingActions[0].action_id).toBe('action-1')
    })

    it('should handle pending_action_resolved event', async () => {
      const store = await createTestStore()
      store.getState().setPendingActions([createMockPendingAction('action-1')])

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'pending_action_resolved',
        work_id: '1',
        command_id: null,
        data: { action_id: 'action-1' },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      expect(store.getState().pendingActions).toHaveLength(0)
    })

    it('should ignore unknown event types', async () => {
      const store = await createTestStore()
      const initialState = store.getState()

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'heartbeat' as RalphEventType,
        work_id: null,
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      }

      store.getState().handleEvent(event)

      // State should remain unchanged (except lastEvent)
      expect(store.getState().workUnits).toEqual(initialState.workUnits)
      expect(store.getState().lastEvent).toEqual(event)
    })
  })

  // ==================== Command Tests ====================

  describe('Command Actions', () => {
    it('should create command successfully', async () => {
      const store = await createTestStore()
      const mockResponse = {
        command_id: 'cmd-1',
        command_type: 'accept_review' as const,
        target_id: 'work-1',
        payload: {},
        status: 'pending' as const,
        idempotency_key: 'idem-1',
        created_at: new Date().toISOString(),
        completed_at: null,
        error: null,
      }
      mockCreateCommand.mockResolvedValue(mockResponse)

      const params: CreateCommandRequest = {
        command_type: 'accept_review',
        target_id: 'work-1',
      }
      const result = await store.getState().createCommand(params)

      expect(mockCreateCommand).toHaveBeenCalledWith(params)
      expect(result).toEqual(mockResponse)
    })

    it('should handle command creation failure', async () => {
      const store = await createTestStore()
      mockCreateCommand.mockRejectedValue(new Error('API error'))

      const params: CreateCommandRequest = {
        command_type: 'accept_review',
        target_id: 'work-1',
      }
      const result = await store.getState().createCommand(params)

      expect(result).toBeNull()
    })

    it('should refresh all data', async () => {
      const store = await createTestStore()
      const units = [createMockWorkUnit('1')]
      const actions = [createMockPendingAction('1')]
      const blockers = [createMockBlocker('1')]
      const status = createMockRunStatus()

      mockListWorkUnits.mockResolvedValue(units)
      mockListPendingActions.mockResolvedValue(actions)
      mockListBlockers.mockResolvedValue(blockers)
      mockGetSummary.mockResolvedValue(status)
      mockListCommands.mockResolvedValue([])

      await store.getState().refreshAll()

      expect(store.getState().workUnits).toEqual(units)
      expect(store.getState().pendingActions).toEqual(actions)
      expect(store.getState().blockers).toEqual(blockers)
      expect(store.getState().runStatus).toEqual(status)
      expect(store.getState().pendingCommandCount).toEqual(0)
      expect(store.getState().loading).toBe(false)
    })

    it('should handle refresh failure gracefully', async () => {
      const store = await createTestStore()
      mockListWorkUnits.mockRejectedValue(new Error('Network error'))

      await store.getState().refreshAll()

      expect(store.getState().loading).toBe(false)
    })

    it('should apply status filter when refreshing', async () => {
      const store = await createTestStore()
      store.getState().setStatusFilter('running')

      mockListWorkUnits.mockResolvedValue([])
      mockListPendingActions.mockResolvedValue([])
      mockListBlockers.mockResolvedValue([])
      mockGetSummary.mockResolvedValue(null)
      mockListCommands.mockResolvedValue([])

      await store.getState().refreshAll()

      expect(mockListWorkUnits).toHaveBeenCalledWith('running')
    })
  })

  // ==================== Loading Tests ====================

  describe('Loading State', () => {
    it('should set loading during fetch operations', async () => {
      const store = await createTestStore()
      mockListWorkUnits.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve([]), 10)))

      const fetchPromise = store.getState().fetchWorkUnits()
      expect(store.getState().loading).toBe(true)

      await fetchPromise
      expect(store.getState().loading).toBe(false)
    })
  })

  // ==================== Selectors ====================

  describe('Selectors', () => {
    it('should export selector functions', async () => {
      // Reset modules to ensure clean import
      vi.resetModules()
      const {
        selectWorkUnits,
        selectSelectedWorkUnit,
        selectStatusFilter,
        selectTabs,
        selectActiveTabId,
        selectPendingActions,
        selectBlockers,
        selectRunStatus,
        selectConnected,
        selectLastEvent,
        selectLoading,
      } = await import('../../lib/ralph-store')

      const mockState = {
        workUnits: [],
        selectedWorkUnit: null,
        statusFilter: 'all' as const,
        tabs: [],
        activeTabId: null,
        pendingActions: [],
        blockers: [],
        runStatus: null,
        connected: false,
        lastEvent: null,
        loading: false,
      } as unknown as Parameters<typeof selectWorkUnits>[0]

      expect(selectWorkUnits(mockState)).toEqual([])
      expect(selectSelectedWorkUnit(mockState)).toBeNull()
      expect(selectStatusFilter(mockState)).toBe('all')
      expect(selectTabs(mockState)).toEqual([])
      expect(selectActiveTabId(mockState)).toBeNull()
      expect(selectPendingActions(mockState)).toEqual([])
      expect(selectBlockers(mockState)).toEqual([])
      expect(selectRunStatus(mockState)).toBeNull()
      expect(selectConnected(mockState)).toBe(false)
      expect(selectLastEvent(mockState)).toBeNull()
      expect(selectLoading(mockState)).toBe(false)
    })
  })
})
