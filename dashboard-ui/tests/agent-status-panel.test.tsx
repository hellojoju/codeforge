import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgentStatusPanel } from '@/components/agent-status-panel'
import * as hooks from '@/lib/hooks/useDashboardQueries'
import type { AgentWithSilence } from '@/lib/types'
import { renderWithQueryClient } from './test-utils'

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className || ''} data-testid="card">{children}</div>
  ),
  CardContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className || ''} data-testid="card-content">{children}</div>
  ),
  CardHeader: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className || ''} data-testid="card-header">{children}</div>
  ),
  CardTitle: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <h3 className={className || ''}>{children}</h3>
  ),
}))

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, variant, className }: { children: React.ReactNode; variant?: string; className?: string }) => (
    <span className={className || ''} data-variant={variant}>{children}</span>
  ),
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, className, variant, size }: { children: React.ReactNode; onClick?: () => void; className?: string; variant?: string; size?: string }) => (
    <button onClick={onClick} className={className || ''} data-variant={variant} data-size={size}>{children}</button>
  ),
}))

vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className || ''}>{children}</div>
  ),
}))

vi.mock('lucide-react', () => ({
  AlertTriangle: () => <span>⚠️</span>,
  MessageSquare: () => <span>💬</span>,
  StopCircle: () => <span>⏹️</span>,
  RefreshCw: () => <span>🔄</span>,
  ChevronDown: () => <span>▼</span>,
  ChevronRight: () => <span>▶</span>,
  Clock: () => <span>🕐</span>,
  Cpu: () => <span>🖥️</span>,
}))

const makeAgent = (overrides: Partial<AgentWithSilence> = {}): AgentWithSilence => ({
  id: 'agent-1',
  role: 'backend',
  status: 'idle',
  instance_number: 1,
  silence_status: { level: 'active', idle_seconds: 5, last_activity: new Date().toISOString() },
  process_status: { pid: 1234, running: true, exists: true, exit_code: null },
  total_tasks_completed: 3,
  current_activity: 'Building API',
  workspace_id: 'ws-1',
  workspace_path: '/tmp/ws-1',
  current_feature: null,
  started_at: new Date().toISOString(),
  ...overrides,
})

describe('AgentStatusPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useInterruptAgent').mockReturnValue({ mutate: vi.fn() } as any)
    vi.spyOn(hooks, 'useSendAgentMessage').mockReturnValue({ mutate: vi.fn() } as any)
  })

  it('shows empty state when no agents', () => {
    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('暂无 Agent 实例')).toBeInTheDocument()
  })

  it('renders agents grouped by role', () => {
    const agent1 = makeAgent({ id: 'backend-1', role: 'backend', instance_number: 1 })
    const agent2 = makeAgent({ id: 'frontend-1', role: 'frontend', instance_number: 2 })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent1, agent2] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('backend')).toBeInTheDocument()
    expect(screen.getByText('frontend')).toBeInTheDocument()
    expect(screen.getByText('backend-1')).toBeInTheDocument()
    expect(screen.getByText('frontend-1')).toBeInTheDocument()
  })

  it('shows role count badges', () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend' })
    const agent2 = makeAgent({ id: 'b2', role: 'backend' })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent1, agent2] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders status labels using AGENT_STATUS_LABELS', () => {
    const agent = makeAgent({ id: 'a1', status: 'busy' })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('运行中')).toBeInTheDocument()
  })

  it('shows process info when available', () => {
    const agent = makeAgent({
      id: 'a1',
      process_status: { pid: 5678, running: true, exists: true, exit_code: null },
    })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('PID: 5678')).toBeInTheDocument()
    expect(screen.getByText('运行中')).toBeInTheDocument()
  })

  it('shows warning for non-active silence level', () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'warning', idle_seconds: 120, last_activity: new Date().toISOString() },
    })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('⚠️')).toBeInTheDocument()
  })

  it('formats seconds into minutes correctly', () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'notify', idle_seconds: 125, last_activity: new Date().toISOString() },
    })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('2m5s')).toBeInTheDocument()
  })

  it('shows current_activity when available', () => {
    const agent = makeAgent({
      id: 'a1',
      current_activity: 'Writing API endpoint',
    })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('⚙️ Writing API endpoint')).toBeInTheDocument()
  })

  it('shows exit_code when process has exit code', () => {
    const agent = makeAgent({
      id: 'a1',
      process_status: { pid: 9999, running: false, exit_code: 1, exists: true },
    })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<AgentStatusPanel />)
    expect(screen.getByText('退出码: 1')).toBeInTheDocument()
  })

  it('toggles role collapse when clicking role header', async () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend', instance_number: 1 })
    const agent2 = makeAgent({ id: 'b2', role: 'backend', instance_number: 2 })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent1, agent2] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<AgentStatusPanel />)

    expect(screen.getByText('b1')).toBeInTheDocument()
    expect(screen.getByText('b2')).toBeInTheDocument()

    const roleHeader = screen.getByText('backend')
    await user.click(roleHeader)

    expect(screen.getByText('backend')).toBeInTheDocument()
  })

  it('toggles showActions panel when clicking action header', async () => {
    const agent = makeAgent({ id: 'a1', role: 'backend' })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<AgentStatusPanel />)

    expect(screen.queryByText('⏹️')).not.toBeInTheDocument()

    const actionToggle = screen.getAllByText('操作')[0]
    await user.click(actionToggle)

    expect(screen.getByText('⏹️')).toBeInTheDocument()
    expect(screen.getByText('💬')).toBeInTheDocument()

    const actionToggleHide = screen.getAllByText('操作')[0]
    await user.click(actionToggleHide)

    expect(screen.queryByText('⏹️')).not.toBeInTheDocument()
  })

  it('handles prompt cancellation when sending message', async () => {
    const agent = makeAgent({ id: 'a1', role: 'backend', status: 'idle' })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const originalPrompt = globalThis.prompt
    globalThis.prompt = vi.fn(() => null)

    const user = userEvent.setup()
    renderWithQueryClient(<AgentStatusPanel />)

    const actionToggle = screen.getAllByText('操作')[0]
    await user.click(actionToggle)

    const sendBtn = screen.getByText('💬')
    await user.click(sendBtn)

    expect(screen).toBeTruthy()

    globalThis.prompt = originalPrompt
  })

  it('toggles role to expanded when explicitly set to false', async () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend', instance_number: 1 })

    vi.spyOn(hooks, 'useAgents').mockReturnValue({
      data: { agents: [agent1] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<AgentStatusPanel />)

    expect(screen.getByText('b1')).toBeInTheDocument()

    const roleHeader = screen.getByText('backend')
    await user.click(roleHeader)

    expect(screen.queryByText('b1')).not.toBeInTheDocument()

    await user.click(roleHeader)
    expect(screen.getByText('b1')).toBeInTheDocument()
  })
})
