 
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatDrawer } from '@/components/chat-drawer'
import { useDashboardStore } from '@/lib/store'

vi.mock('@/lib/store', () => ({
  useDashboardStore: vi.fn(),
}))

// ChatDrawer uses lucide-react icons for X (close), Send, Loader2
vi.mock('lucide-react', () => ({
  X: () => <span data-testid="icon-x">X</span>,
  Send: () => <span data-testid="icon-send">📤</span>,
  Loader2: () => <span data-testid="icon-loader">⏳</span>,
}))

// ChatDrawer uses dynamic import: await import('@/lib/api').then(({ sendChat }) => ...)
vi.mock('@/lib/api', () => ({
  sendChat: vi.fn(),
}))

describe('ChatDrawer', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('returns null when not open', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
    })

    const { container } = render(<ChatDrawer open={false} onClose={() => {}} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders chat history with user and PM messages', () => {
    const chatHistory = [
      { role: 'user' as const, content: '你好' },
      { role: 'pm' as const, content: '有什么可以帮你的？' },
    ]

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory,
      projectId: 'proj-1',
    })

    render(<ChatDrawer open={true} onClose={() => {}} />)
    expect(screen.getByText('你好')).toBeInTheDocument()
    expect(screen.getByText('有什么可以帮你的？')).toBeInTheDocument()
  })

  it('shows empty state when no messages', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
    })

    render(<ChatDrawer open={true} onClose={() => {}} />)
    expect(screen.getByText('暂无消息，发送指令开始与 PM 协作')).toBeInTheDocument()
  })

  it('sends message on button click', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockResolvedValue({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '收到', timestamp: new Date().toISOString(), action_triggered: '' } })

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatDrawer open={true} onClose={() => {}} />)

    // Uses native <input>, not UI component
    const input = screen.getByRole('textbox')
    await user.type(input, '测试消息')

    // Uses native <button> with Send icon
    const sendButton = screen.getByTestId('icon-send')
    await user.click(sendButton)

    expect(sendChat).toHaveBeenCalled()
  })

  it('sends message on Enter key', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockResolvedValue({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '收到', timestamp: new Date().toISOString(), action_triggered: '' } })

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatDrawer open={true} onClose={() => {}} />)

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
    render(<ChatDrawer open={true} onClose={() => {}} />)

    const sendButton = screen.getByTestId('icon-send')
    await user.click(sendButton)

    expect(sendChat).not.toHaveBeenCalled()
  })

  it('shows loading state while sending', async () => {
    const { sendChat } = await import('@/lib/api')
    vi.mocked(sendChat).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ success: true, message_id: 'msg-1', pm_response: { id: 'pm-1', role: 'pm', content: '延迟回复', timestamp: new Date().toISOString(), action_triggered: '' } }), 1000)))

    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
      addChatMessage: vi.fn(),
    })

    const user = userEvent.setup()
    render(<ChatDrawer open={true} onClose={() => {}} />)

    const input = screen.getByRole('textbox')
    await user.type(input, '测试')

    const sendButton = screen.getByTestId('icon-send')
    await user.click(sendButton)

    expect(screen.getByTestId('icon-loader')).toBeInTheDocument()
  })

  it('has overlay that closes drawer', () => {
    const onClose = vi.fn()
    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
    })

    render(<ChatDrawer open={true} onClose={onClose} />)

    // Overlay is a fixed div with bg-slate-900/20
    const overlay = document.querySelector('.fixed.inset-0.bg-slate-900\\/20')
    expect(overlay).toBeInTheDocument()

    // Close button exists
    const closeBtn = screen.getByTestId('icon-x')
    expect(closeBtn).toBeInTheDocument()
  })

  it('has header with title', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      chatHistory: [],
      projectId: 'proj-1',
    })

    render(<ChatDrawer open={true} onClose={() => {}} />)
    expect(screen.getByText('与 PM 对话')).toBeInTheDocument()
  })
})
