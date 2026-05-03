/** WebSocket 客户端 — 支持 hello 握手 + 增量事件同步。 */

import type { DashboardEvent, AgentInstance, Feature, ChatMessage, ModuleAssignment, BlockingIssue } from './types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:18753/ws/dashboard'

export interface WsCallbacks {
  onSnapshot: (data: {
    agents: AgentInstance[]
    features: Feature[]
    chatHistory: ChatMessage[]
    moduleAssignments: ModuleAssignment[]
    blockingIssues: BlockingIssue[]
    projectId: string
    lastEventId: number
  }) => void
  onEvent: (event: DashboardEvent) => void
  onDisconnect: () => void
  onReconnect: () => void
}

export function createWebSocket(callbacks: WsCallbacks) {
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      // WebSocket 连接后，后端会自动发送 hello 消息
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'hello') {
          callbacks.onSnapshot({
            agents: data.agents ?? [],
            features: data.features ?? [],
            chatHistory: data.chat_history ?? [],
            moduleAssignments: data.module_assignments ?? [],
            blockingIssues: data.blocking_issues ?? [],
            projectId: data.project_id ?? '',
            lastEventId: data.last_event_id ?? 0,
          })
          return
        }
        // 普通事件广播
        callbacks.onEvent(data as DashboardEvent)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      callbacks.onDisconnect()
      reconnectTimer = setTimeout(() => {
        connect()
        callbacks.onReconnect()
      }, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  connect()

  return {
    close() {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    },
  }
}
