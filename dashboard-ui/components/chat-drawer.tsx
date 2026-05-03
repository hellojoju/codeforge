/** PM 对话抽屉 — 从右侧滑出的聊天面板。 */
'use client'

import { useState, useRef, useEffect } from 'react'
import { useDashboardStore } from '@/lib/store'
import type { ChatMessage } from '@/lib/types'
import { X, Send, Loader2 } from 'lucide-react'

interface ChatDrawerProps {
  open: boolean
  onClose: () => void
}

export function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  const { chatHistory, projectId, addChatMessage } = useDashboardStore()
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
      })
    }
  }, [chatHistory, open])

  async function handleSend() {
    const content = input.trim()
    if (!content || sending) return

    setSending(true)
    setInput('')
    try {
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
        action_triggered: '',
      }
      addChatMessage(userMsg)

      const result = await import('@/lib/api').then(({ sendChat }) => sendChat(content, projectId))
      if (result.pm_response) {
        const pmMsg: ChatMessage = {
          id: result.pm_response.id,
          role: 'pm',
          content: result.pm_response.content,
          timestamp: result.pm_response.timestamp,
          action_triggered: result.pm_response.action_triggered ?? '',
        }
        addChatMessage(pmMsg)
      } else {
        const sysMsg: ChatMessage = {
          id: `sys-${Date.now()}`,
          role: 'pm',
          content: 'PM 暂未回复，请稍后重试',
          timestamp: new Date().toISOString(),
          action_triggered: '',
        }
        addChatMessage(sysMsg)
      }
    } catch (error) {
      console.error('PM 消息发送失败:', error)
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'pm',
        content: '消息发送失败，请检查后端服务是否正常运行',
        timestamp: new Date().toISOString(),
        action_triggered: '',
      }
      addChatMessage(errorMsg)
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

  if (!open) return null

  return (
    <>
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 bg-slate-900/20 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* 抽屉面板 */}
      <div className="fixed right-0 top-0 bottom-0 w-[380px] bg-white z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
        {/* 头部 */}
        <div className="px-4 py-3.5 border-b border-slate-200 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">与 PM 对话</h2>
            <p className="text-xs text-slate-400 mt-0.5">向 PM 发送指令或提问</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          {chatHistory.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-8">
              暂无消息，发送指令开始与 PM 协作
            </p>
          )}
          {chatHistory.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.action_triggered && (
                  <span className="text-[10px] mt-1.5 block opacity-60 font-medium">
                    触发动作: {msg.action_triggered}
                  </span>
                )}
                <span className="text-[10px] mt-1 block opacity-40">
                  {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
                </span>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="border-t border-slate-200 p-3 shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="给 PM 发送指令..."
              className="flex-1 text-sm px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              disabled={sending}
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              {sending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
