/**
 * Ralph Runtime Console - Zustand Store
 *
 * 管理 WorkUnits、Tabs、Approvals、WebSocket 连接等状态
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type {
  WorkUnit,
  WorkUnitStatus,
  Tab,
  PendingAction,
  Blocker,
  RunStatus,
  RalphEvent,
  CreateCommandRequest,
  RalphCommand,
} from './ralph-types'
import { generateTabId } from './ralph-utils'

// ==================== State Interface ====================

interface RalphState {
  // WorkUnits
  workUnits: WorkUnit[]
  selectedWorkUnit: WorkUnit | null
  statusFilter: WorkUnitStatus | 'all'

  // Tabs
  tabs: Tab[]
  activeTabId: string | null

  // Approvals
  pendingActions: PendingAction[]
  blockers: Blocker[]

  // Run status
  runStatus: RunStatus | null

  // WebSocket
  connected: boolean
  lastEvent: RalphEvent | null

  // Loading
  loading: boolean

  // Streaming output: work_id -> array of text chunks
  streamChunks: Record<string, string[]>

  // Recent events (FIFO, max 50)
  recentEvents: RalphEvent[]

  // Pending command count (fetched from API)
  pendingCommandCount: number

  // Project state
  currentProject: { name: string; path: string } | null
  recentProjects: { name: string; path: string; last_opened_at: string | null }[]
  projectAnalysis: Record<string, unknown> | null

  // File browser
  fileTree: Record<string, unknown>[]
  currentFilePath: string | null
  fileContent: string | null

  // Pipeline / scheduling
  pipelineStages: Record<string, unknown>[]
  schedulingTimeline: Record<string, unknown>[]
}

interface RalphActions {
  // WorkUnit actions
  setWorkUnits: (units: WorkUnit[]) => void
  updateWorkUnit: (workId: string, updates: Partial<WorkUnit>) => void
  setSelectedWorkUnit: (unit: WorkUnit | null) => void

  // Filter actions
  setStatusFilter: (filter: WorkUnitStatus | 'all') => void
  fetchWorkUnits: () => Promise<void>

  // Tab actions
  addTab: (tab: Omit<Tab, 'id' | 'created_at'>) => void
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void

  // Approval actions
  setPendingActions: (actions: PendingAction[]) => void
  setBlockers: (blockers: Blocker[]) => void
  setRunStatus: (status: RunStatus | null) => void

  // WebSocket actions
  setConnected: (connected: boolean) => void
  handleEvent: (event: RalphEvent) => void

  // Streaming actions
  appendStreamChunk: (workId: string, chunk: string) => void
  clearStreamChunks: (workId: string) => void

  // Command actions
  createCommand: (params: CreateCommandRequest) => Promise<RalphCommand | null>
  refreshAll: () => Promise<void>
  fetchPendingCommandCount: () => Promise<void>

  // Project actions
  setCurrentProject: (project: { name: string; path: string } | null) => void
  setRecentProjects: (projects: { name: string; path: string; last_opened_at: string | null }[]) => void
  setProjectAnalysis: (analysis: Record<string, unknown> | null) => void

  // File actions
  setFileTree: (tree: Record<string, unknown>[]) => void
  openFile: (path: string, content: string) => void
  closeFile: () => void

  // Scheduling/pipeline
  setPipelineStages: (stages: Record<string, unknown>[]) => void
  setSchedulingTimeline: (timeline: Record<string, unknown>[]) => void
}

type RalphStore = RalphState & RalphActions

// ==================== Constants ====================

const MAX_TABS = 8
const TABS_STORAGE_KEY = 'ralph-tabs'

// ==================== Helper Functions ====================

/**
 * 从 localStorage 恢复 tabs
 */
function loadTabsFromStorage(): Tab[] {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const stored = localStorage.getItem(TABS_STORAGE_KEY)
    if (stored) {
      return JSON.parse(stored) as Tab[]
    }
  } catch {
    // 解析失败，忽略
  }
  return []
}

/**
 * 保存 tabs 到 localStorage
 */
function saveTabsToStorage(tabs: Tab[]): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify(tabs))
  } catch {
    // 保存失败，忽略
  }
}

/**
 * 根据 event_type 更新对应数据
 */
function handleRalphEvent(
  event: RalphEvent,
  state: RalphState,
  set: (partial: Partial<RalphState>) => void
): void {
  const { event_type, data, work_id } = event

  // Push to recentEvents (FIFO, max 50)
  const recentEvents = [...state.recentEvents, event]
  if (recentEvents.length > 50) {
    recentEvents.splice(0, recentEvents.length - 50)
  }
  set({ recentEvents })

  switch (event_type) {
    case 'work_unit_created':
      if (data.work_unit) {
        const newUnit = data.work_unit as WorkUnit
        set({
          workUnits: [...state.workUnits, newUnit],
        })
      }
      break

    case 'work_unit_status_changed':
      if (work_id && data.updates) {
        const updates = data.updates as Partial<WorkUnit>
        set({
          workUnits: state.workUnits.map((unit) =>
            unit.work_id === work_id ? { ...unit, ...updates } : unit
          ),
        })
      }
      break

    case 'evidence_saved':
      // 证据保存
      break

    case 'command_applied':
    case 'command_failed':
      // 命令结果，可能需要刷新 pending actions
      break

    case 'review_completed':
      if (work_id && data.review_result) {
        const reviewResult = data.review_result as { conclusion: 'passed' | 'failed' }
        const newStatus = reviewResult.conclusion === 'passed' ? 'accepted' : 'needs_rework'
        set({
          workUnits: state.workUnits.map((unit) =>
            unit.work_id === work_id ? { ...unit, status: newStatus as WorkUnitStatus } : unit
          ),
        })
      }
      break

    case 'blocker_created':
      if (data.blocker) {
        const newBlocker = data.blocker as Blocker
        set({
          blockers: [...state.blockers, newBlocker],
        })
      }
      break

    case 'blocker_resolved':
      if (data.blocker_id) {
        set({
          blockers: state.blockers.map((blocker) =>
            blocker.blocker_id === data.blocker_id ? { ...blocker, resolved: true } : blocker
          ),
        })
      }
      break

    case 'pending_action_created':
      if (data.pending_action) {
        const newAction = data.pending_action as PendingAction
        set({
          pendingActions: [...state.pendingActions, newAction],
        })
      }
      break

    case 'pending_action_resolved':
      if (data.action_id) {
        set({
          pendingActions: state.pendingActions.filter(
            (action) => action.action_id !== data.action_id
          ),
        })
      }
      break

    case 'heartbeat':
      // 心跳事件，更新连接状态
      break

    case 'ralph_stream_chunk':
      if (work_id && data.text) {
        set({
          streamChunks: {
            ...state.streamChunks,
            [work_id]: [...(state.streamChunks[work_id] || []), String(data.text)],
          },
        })
      }
      break

    default:
      // 未知事件类型，忽略
      break
  }
}

// ==================== Store Factory ====================

const createRalphStore = (initialTabs: Tab[] = []) =>
  create<RalphStore>()(
    devtools(
      (set, get) => ({
        // ==================== Initial State ====================
        workUnits: [],
        selectedWorkUnit: null,
        statusFilter: 'all',

        tabs: initialTabs,
        activeTabId: initialTabs.length > 0 ? initialTabs[0].id : null,

        pendingActions: [],
        blockers: [],

        runStatus: null,

        connected: false,
        lastEvent: null,

        loading: false,

        streamChunks: {},

        recentEvents: [],

        pendingCommandCount: 0,

        currentProject: null,
        recentProjects: [],
        projectAnalysis: null,

        fileTree: [],
        currentFilePath: null,
        fileContent: null,

        pipelineStages: [],
        schedulingTimeline: [],

        // ==================== WorkUnit Actions ====================
        setWorkUnits: (units) => {
          set({ workUnits: units })
        },

        updateWorkUnit: (workId, updates) => {
          set((state) => ({
            workUnits: state.workUnits.map((unit) =>
              unit.work_id === workId ? { ...unit, ...updates } : unit
            ),
          }))
        },

        setSelectedWorkUnit: (unit) => {
          set({ selectedWorkUnit: unit })
        },

        // ==================== Filter Actions ====================
        setStatusFilter: (filter) => {
          set({ statusFilter: filter })
          // 自动触发获取数据
          void get().fetchWorkUnits()
        },

        fetchWorkUnits: async () => {
          set({ loading: true })
          try {
            // 动态导入 API 模块（避免循环依赖）
            const { listWorkUnits } = await import('./ralph-api')
            const { statusFilter } = get()
            const status = statusFilter !== 'all' ? statusFilter : undefined
            const units = await listWorkUnits(status)
            set({ workUnits: units, loading: false })
          } catch {
            set({ loading: false })
          }
        },

        // ==================== Tab Actions ====================
        addTab: (tab) => {
          set((state) => {
            // 检查是否已存在相同类型的 tab
            const existingTab = state.tabs.find(
              (t) => t.type === tab.type && t.work_id === tab.work_id
            )
            if (existingTab) {
              // 切换到已存在的 tab
              return { activeTabId: existingTab.id }
            }

            // 检查 tab 数量限制
            if (state.tabs.length >= MAX_TABS) {
              // 移除最旧的未固定 tab
              const nonPinnedTabs = state.tabs.filter((t) => !t.pinned)
              if (nonPinnedTabs.length === 0) {
                // 所有 tab 都是固定的，无法添加新 tab
                return state
              }
              const oldestTab = nonPinnedTabs.reduce((oldest, current) =>
                current.created_at < oldest.created_at ? current : oldest
              )
              const filteredTabs = state.tabs.filter((t) => t.id !== oldestTab.id)
              const newTab: Tab = {
                ...tab,
                id: generateTabId(),
                created_at: Date.now(),
              }
              const newTabs = [...filteredTabs, newTab]
              saveTabsToStorage(newTabs)
              return {
                tabs: newTabs,
                activeTabId: newTab.id,
              }
            }

            const newTab: Tab = {
              ...tab,
              id: generateTabId(),
              created_at: Date.now(),
            }
            const newTabs = [...state.tabs, newTab]
            saveTabsToStorage(newTabs)
            return {
              tabs: newTabs,
              activeTabId: newTab.id,
            }
          })
        },

        closeTab: (tabId) => {
          set((state) => {
            const tabToClose = state.tabs.find((t) => t.id === tabId)
            if (tabToClose?.pinned) {
              // 固定的 tab 不能关闭
              return state
            }
            const newTabs = state.tabs.filter((t) => t.id !== tabId)
            saveTabsToStorage(newTabs)

            // 如果关闭的是当前激活的 tab，切换到其他 tab
            let newActiveTabId = state.activeTabId
            if (state.activeTabId === tabId) {
              const remainingTabs = newTabs
              newActiveTabId = remainingTabs.length > 0 ? remainingTabs[remainingTabs.length - 1].id : null
            }

            return {
              tabs: newTabs,
              activeTabId: newActiveTabId,
            }
          })
        },

        setActiveTab: (tabId) => {
          set({ activeTabId: tabId })
        },

        // ==================== Approval Actions ====================
        setPendingActions: (actions) => {
          set({ pendingActions: actions })
        },

        setBlockers: (blockers) => {
          set({ blockers })
        },

        setRunStatus: (status) => {
          set({ runStatus: status })
        },

        // ==================== WebSocket Actions ====================
        setConnected: (connected) => {
          set({ connected })
        },

        handleEvent: (event) => {
          const state = get()
          handleRalphEvent(event, state, set)
          set({ lastEvent: event })
        },

        // ==================== Streaming Actions ====================
        appendStreamChunk: (workId, chunk) => {
          set((state) => ({
            streamChunks: {
              ...state.streamChunks,
              [workId]: [...(state.streamChunks[workId] || []), chunk],
            },
          }))
        },

        clearStreamChunks: (workId) => {
          set((state) => {
            const { [workId]: _, ...rest } = state.streamChunks
            return { streamChunks: rest }
          })
        },

        // ==================== Command Actions ====================
        createCommand: async (params) => {
          try {
            const { createCommand } = await import('./ralph-api')
            const response = await createCommand(params)
            return response
          } catch {
            return null
          }
        },

        refreshAll: async () => {
          set({ loading: true })
          try {
            const { getSummary, listWorkUnits, listPendingActions, listBlockers, listCommands } =
              await import('./ralph-api')

            const { statusFilter } = get()
            const status = statusFilter !== 'all' ? statusFilter : undefined

            const [units, actions, blockers, summary, pendingCommands] = await Promise.all([
              listWorkUnits(status),
              listPendingActions(),
              listBlockers(),
              getSummary(),
              listCommands('pending'),
            ])

            set({
              workUnits: units,
              pendingActions: actions,
              blockers,
              runStatus: summary,
              pendingCommandCount: pendingCommands.length,
              loading: false,
            })
          } catch {
            set({ loading: false })
          }
        },

        fetchPendingCommandCount: async () => {
          try {
            const { listCommands } = await import('./ralph-api')
            const pending = await listCommands('pending')
            set({ pendingCommandCount: pending.length })
          } catch {
            // silent fail
          }
        },

        // Project actions
        setCurrentProject: (project) => set({ currentProject: project }),
        setRecentProjects: (projects) => set({ recentProjects: projects }),
        setProjectAnalysis: (analysis) => set({ projectAnalysis: analysis }),

        // File actions
        setFileTree: (tree) => set({ fileTree: tree }),
        openFile: (path, content) => set({ currentFilePath: path, fileContent: content }),
        closeFile: () => set({ currentFilePath: null, fileContent: null }),

        // Scheduling/pipeline actions
        setPipelineStages: (stages) => set({ pipelineStages: stages }),
        setSchedulingTimeline: (timeline) => set({ schedulingTimeline: timeline }),
      }),
      { name: 'RalphStore' }
    )
  )

// ==================== Store Instance ====================

let storeInstance: ReturnType<typeof createRalphStore> | null = null

/**
 * 创建 Store 实例（单例模式）
 * 在客户端会尝试从 localStorage 恢复 tabs
 */
function getStoreInstance(): ReturnType<typeof createRalphStore> {
  if (storeInstance === null) {
    // 始终从空 tabs 开始，避免 SSR hydration 不匹配
    // tabs 由 hydrateTabsFromStorage() 在客户端 useEffect 中恢复
    storeInstance = createRalphStore([])
  }
  return storeInstance
}

/**
 * 客户端 mount 后从 localStorage 恢复 tabs
 * 在 RalphLayout 的 useEffect 中调用
 */
export function hydrateTabsFromStorage(): void {
  const stored = loadTabsFromStorage()
  if (stored.length > 0) {
    const state = getStoreInstance().getState()
    // 只在 store 中还没有 tab 时恢复（避免覆盖导航触发的 tab）
    if (state.tabs.length === 0) {
      state.tabs = stored
      state.activeTabId = stored[0]?.id ?? null
      getStoreInstance().setState({ tabs: stored, activeTabId: stored[0]?.id ?? null })
    }
  }
}

/**
 * Zustand Hook — 在 React 组件中使用：
 * ```ts
 * const { workUnits, fetchWorkUnits } = useRalphStore()
 * ```
 *
 * 在非组件代码中获取 store 实例：
 * ```ts
 * useRalphStore.getState().refreshAll()
 * ```
 */
export function useRalphStore() {
  const store = getStoreInstance()
  return store()
}

/**
 * 获取底层 Zustand store 实例（用于 .getState() / .setState() 等非 hook 场景）
 */
useRalphStore.getState = () => getStoreInstance().getState()
useRalphStore.setState = (partial: Partial<RalphState>, replace?: boolean) =>
  getStoreInstance().setState(partial, replace as false)

/**
 * 重置 Store 实例（主要用于测试）
 */
export function resetRalphStore(): void {
  storeInstance = null
}

/**
 * 创建新的 Store 实例（主要用于测试）
 */
export function createRalphStoreForTest(initialTabs: Tab[] = []): ReturnType<typeof createRalphStore> {
  return createRalphStore(initialTabs)
}

// ==================== Selectors ====================

export const selectWorkUnits = (state: RalphStore) => state.workUnits
export const selectSelectedWorkUnit = (state: RalphStore) => state.selectedWorkUnit
export const selectStatusFilter = (state: RalphStore) => state.statusFilter
export const selectTabs = (state: RalphStore) => state.tabs
export const selectActiveTabId = (state: RalphStore) => state.activeTabId
export const selectPendingActions = (state: RalphStore) => state.pendingActions
export const selectBlockers = (state: RalphStore) => state.blockers
export const selectRunStatus = (state: RalphStore) => state.runStatus
export const selectConnected = (state: RalphStore) => state.connected
export const selectLastEvent = (state: RalphStore) => state.lastEvent
export const selectLoading = (state: RalphStore) => state.loading
export const selectStreamChunks = (state: RalphStore) => state.streamChunks
