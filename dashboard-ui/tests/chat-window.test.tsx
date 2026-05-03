 
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatWindow } from '@/components/chat-window'
import { useDashboardStore } from '@/lib/store'

vi.mock('@/lib/store', () => ({
  useDashboardStore: vi.fn(),
}))

vi.mock('lucide-react', () => ({
  Send: () => <span data-testid="icon-send">Send</span>,
  Loader2: () => <span data-testid="icon-loader">Loader2</span>,
  MessageSquare: () => <span data-testid="icon-message">MessageSquare</span>,
}))

vi.mock('@/lib/api', () => ({
  sendChat: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}))

describe('ChatWindow', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders chat history', () => {
    const chatHistory = [
      { role: 'user' as const, content: '创建用户系统' },
      { role: 'pm' as const, content: '好的，我来规划一下' },
    ]

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory,
      projectId: 'proj-1',
    })

    render(<ChatWindow />)
    expect(screen.getByText('创建用户系统')).toBeInTheDocument()
    expect(screen.getByText('好的，我来规划一下')).toBeInTheDocument()
  })

  it('shows empty state when no messages', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
    })

    render(<ChatWindow />)
    expect(screen.getByText('与 PM 对话')).toBeInTheDocument()
  })

  it('sends message on button click', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockResolvedValue({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '收到你的消息', timestamp: new Date().toISOString(), action_triggered: '' } })

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatWindow />)

    const input = screen.getByRole('textbox')
    await user.type(input, '开始开发')

    const sendButton = screen.getByRole('button', { name: /发送/ })
    await user.click(sendButton)

    expect(sendChat).toHaveBeenCalledWith('开始开发', 'proj-1')
  })

  it('sends message on Enter key', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockResolvedValue({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '好的', timestamp: new Date().toISOString(), action_triggered: '' } })

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatWindow />)

    const input = screen.getByRole('textbox')
    await user.type(input, '回车发送{enter}')

    expect(sendChat).toHaveBeenCalled()
  })

  it('does not send empty message', async () => {
    const { sendChat } = await import('@/lib/api')

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatWindow />)

    const sendButton = screen.getByRole('button', { name: /发送/ })
    await user.click(sendButton)

    expect(sendChat).not.toHaveBeenCalled()
  })

  it('shows error toast on send failure', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockRejectedValue(new Error('网络错误'))

    const { toast } = await import('sonner')

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatWindow />)

    const input = screen.getByRole('textbox')
    await user.type(input, '测试错误')

    const sendButton = screen.getByRole('button', { name: /发送/ })
    await user.click(sendButton)

    expect(toast.error).toHaveBeenCalled()
  })

  it('shows loading state while sending', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '延迟', timestamp: new Date().toISOString(), action_triggered: '' } }), 1000)))

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatWindow />)

    const input = screen.getByRole('textbox')
    await user.type(input, '测试')

    const sendButton = screen.getByRole('button', { name: /发送/ })
    await user.click(sendButton)

    // Button shows "发送中..." text during loading
    expect(screen.getByText('发送中...')).toBeInTheDocument()
  })
})
