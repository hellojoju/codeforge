'use client'

import { useState, useRef, useEffect } from 'react'
import { useDashboardStore } from '@/lib/store'
import { sendChat } from '@/lib/api'
import { toast } from 'sonner'
import type { ChatMessage } from '@/lib/types'

export function ChatWindow() {
  const { chatHistory, projectId, addChatMessage } = useDashboardStore()
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  async function handleSend() {
    const content = input.trim()
    if (!content || sending) return

    setSending(true)
    try {
      // 先添加用户消息到 chatHistory
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
        action_triggered: '',
      }
      addChatMessage(userMsg)
      setInput('')

      const result = await sendChat(content, projectId)
      // 如果后端返回了 PM 回复，立即添加到 chatHistory
      if (result.pm_response) {
        const pmMsg: ChatMessage = {
          id: result.pm_response.id,
          role: 'pm',
          content: result.pm_response.content,
          timestamp: result.pm_response.timestamp,
          action_triggered: result.pm_response.action_triggered ?? '',
        }
        addChatMessage(pmMsg)
      }
    } catch (error) {
      toast.error('发送失败', { description: error instanceof Error ? error.message : '未知错误' })
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border flex flex-col">
      {/* 头部 — 可折叠切换 */}
      <div
        className="px-4 py-2 border-b bg-gray-50 dark:bg-gray-750 flex items-center justify-between cursor-pointer select-none"
        onClick={() => setCollapsed(!collapsed)}
      >
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">与 PM 对话</h3>
        <button
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          aria-label={collapsed ? '展开聊天' : '收起聊天'}
        >
          <svg
            className={`h-4 w-4 transition-transform duration-200 ${collapsed ? '' : 'rotate-180'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* 消息列表 — 收起时隐藏 */}
      {!collapsed && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[320px]">
            {chatHistory.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-4">暂无消息，发送指令开始与 PM 协作</p>
            )}
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <span className="text-xs opacity-60 mt-1 block">
                    {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
                  </span>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* 输入区 */}
          <div className="border-t p-3 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="给 PM 发送指令..."
              className="flex-1 text-sm px-3 py-2 rounded border bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={sending}
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sending ? '发送中...' : '发送'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
