/** PM 对话抽屉 — 从右侧滑出的聊天面板，带执行步骤展示。 */
'use client'

import { useState, useRef, useEffect } from 'react'
import { useDashboardStore } from '@/lib/store'
import { useRalphStore } from '@/lib/ralph-store'
import type { ChatMessage, ChatStep } from '@/lib/types'
import { X, Send, Loader2, ChevronDown, ChevronRight, CheckCircle2, AlertCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface ChatDrawerProps {
  open: boolean
  onClose: () => void
}

// 加载时的占位步骤 — 实时显示 PM 工作状态
const LOADING_STEPS: ChatStep[] = [
  { label: '正在分析意图', status: 'running', detail: '', duration_ms: 0 },
  { label: '正在查询项目数据', status: 'pending', detail: '', duration_ms: 0 },
  { label: '正在向 AI 发送请求', status: 'pending', detail: '', duration_ms: 0 },
]

/** 单个可展开的步骤行 */
function StepRow({ step, isLast }: { step: ChatStep; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false)

  const isPending = step.status === 'pending'
  const isRunning = step.status === 'running'
  const isDone = step.status === 'done'
  const isError = step.status === 'error'
  const hasDetail = step.detail || step.duration_ms > 0

  const icon = (() => {
    if (isPending) return <span className="h-4 w-4 rounded-full border-2 border-slate-300" />
    if (isRunning) return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
    if (isDone) return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    if (isError) return <AlertCircle className="h-4 w-4 text-red-500" />
    return null
  })()

  return (
    <div className={`flex flex-col ${!isLast ? 'border-b border-slate-100' : ''}`}>
      <button
        onClick={() => hasDetail && setExpanded(!expanded)}
        className={`flex items-center gap-2 px-3 py-2 text-sm transition-colors w-full text-left
          ${hasDetail ? 'cursor-pointer hover:bg-slate-50' : 'cursor-default'}
          ${isPending ? 'opacity-40' : ''}`}
      >
        <span className="shrink-0">{icon}</span>
        <span className={`flex-1 text-xs ${isRunning ? 'text-blue-600 font-medium' : 'text-slate-600'}`}>
          {step.label}
          {isRunning && <span className="ml-1 animate-pulse">...</span>}
        </span>
        {step.duration_ms > 0 && (
          <span className="text-[10px] text-slate-400 tabular-nums">
            {step.duration_ms >= 1000 ? `${(step.duration_ms / 1000).toFixed(1)}s` : `${step.duration_ms}ms`}
          </span>
        )}
        {hasDetail && (
          <span className="shrink-0 text-slate-400">
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </span>
        )}
      </button>
      {expanded && hasDetail && (
        <div className="px-3 pb-2 pl-9">
          <p className="text-[11px] text-slate-500 leading-relaxed">{step.detail}</p>
        </div>
      )}
    </div>
  )
}

/** 步骤列表组件 */
function StepsList({ steps }: { steps: ChatStep[] }) {
  return (
    <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 overflow-hidden my-2">
      {steps.map((step, i) => (
        <StepRow key={i} step={step} isLast={i === steps.length - 1} />
      ))}
    </div>
  )
}

export function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  const { chatHistory, projectId, addChatMessage } = useDashboardStore()
  const { currentProject } = useRalphStore()
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingSteps, setLoadingSteps] = useState<ChatStep[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
      })
    }
  }, [chatHistory, open, loadingSteps])

  // 发送消息时动态更新加载步骤
  useEffect(() => {
    if (!sending) {
      setLoadingSteps([])
      return
    }
    // 依次激活加载步骤
    const steps = LOADING_STEPS.map((s) => ({ ...s }))
    setLoadingSteps([...steps])

    const t1 = setTimeout(() => {
      setLoadingSteps((prev) => {
        const next = [...prev]
        if (next[0]) next[0] = { ...next[0], status: 'done' }
        if (next[1]) next[1] = { ...next[1], status: 'running' }
        return next
      })
    }, 600)

    const t2 = setTimeout(() => {
      setLoadingSteps((prev) => {
        const next = [...prev]
        if (next[1]) next[1] = { ...next[1], status: 'done' }
        if (next[2]) next[2] = { ...next[2], status: 'running' }
        return next
      })
    }, 1500)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [sending])

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

      const projectDir = currentProject?.path || projectId
      const result = await import('@/lib/api').then(({ sendChat }) => sendChat(content, projectDir))
      if (result.pm_response) {
        const pmMsg: ChatMessage = {
          id: result.pm_response.id,
          role: 'pm',
          content: result.pm_response.content,
          timestamp: result.pm_response.timestamp,
          action_triggered: result.pm_response.action_triggered ?? '',
          steps: result.steps as ChatStep[] ?? [],
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
      <div className="fixed right-0 top-0 bottom-0 w-[420px] bg-white z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
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
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {chatHistory.length === 0 && !sending && (
            <p className="text-sm text-slate-400 text-center py-8">
              暂无消息，发送指令开始与 PM 协作
            </p>
          )}
          {chatHistory.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[90%] rounded-lg px-3 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-50 text-slate-700 border border-slate-100'
              }`}>
                {msg.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <>
                    <div className="prose prose-sm prose-slate max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-code:text-xs prose-code:bg-black/5 prose-code:rounded prose-code:px-1 prose-code:py-0.5">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    {msg.action_triggered && (
                      <span className="text-[10px] mt-1.5 block opacity-60 font-medium">
                        触发动作: {msg.action_triggered}
                      </span>
                    )}
                    {msg.steps && msg.steps.length > 0 && (
                      <StepsList steps={msg.steps} />
                    )}
                  </>
                )}
                <span className="text-[10px] mt-1 block opacity-40">
                  {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
                </span>
              </div>
            </div>
          ))}

          {/* 加载中的步骤 */}
          {sending && loadingSteps.length > 0 && (
            <div className="flex justify-start">
              <div className="max-w-[90%] rounded-lg px-3 py-2.5 bg-slate-50 border border-slate-100 w-full">
                <p className="text-xs text-slate-500 mb-2 font-medium">PM 正在处理...</p>
                <StepsList steps={loadingSteps} />
              </div>
            </div>
          )}
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
