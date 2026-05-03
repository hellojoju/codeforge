 
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgentStatusPanel } from '@/components/agent-status-panel'
import { useDashboardStore } from '@/lib/store'
import type { AgentWithSilence } from '@/lib/types'

vi.mock('@/lib/store', () => ({
  useDashboardStore: vi.fn(),
}))

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
  })

  it('shows empty state when no agents', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails: new Map(),
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('暂无 Agent 实例')).toBeInTheDocument()
  })

  it('renders agents grouped by role', () => {
    const agent1 = makeAgent({ id: 'backend-1', role: 'backend', instance_number: 1 })
    const agent2 = makeAgent({ id: 'frontend-1', role: 'frontend', instance_number: 2 })
    const agentDetails = new Map([['backend-1', agent1], ['frontend-1', agent2]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('backend')).toBeInTheDocument()
    expect(screen.getByText('frontend')).toBeInTheDocument()
    expect(screen.getByText('backend-1')).toBeInTheDocument()
    expect(screen.getByText('frontend-1')).toBeInTheDocument()
  })

  it('shows role count badges', () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend' })
    const agent2 = makeAgent({ id: 'b2', role: 'backend' })
    const agentDetails = new Map([['b1', agent1], ['b2', agent2]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders status labels using AGENT_STATUS_LABELS', () => {
    const agent = makeAgent({ id: 'a1', status: 'busy' })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    // busy should map to "运行中"
    expect(screen.getByText('运行中')).toBeInTheDocument()
  })

  it('shows process info when available', () => {
    const agent = makeAgent({
      id: 'a1',
      process_status: { pid: 5678, running: true, exists: true, exit_code: null },
    })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('PID: 5678')).toBeInTheDocument()
    expect(screen.getByText('运行中')).toBeInTheDocument()
  })

  it('shows warning for non-active silence level', () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'warning', idle_seconds: 120, last_activity: new Date().toISOString() },
    })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('⚠️')).toBeInTheDocument()
  })

  it('calls fetchAgents and fetchEvents on refresh', async () => {
    const fetchAgents = vi.fn()
    const fetchEvents = vi.fn()
    const agent = makeAgent({ id: 'a1' })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents,
      fetchEvents,
    })

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    const refreshBtn = screen.getByText('🔄')
    await user.click(refreshBtn)

    expect(fetchAgents).toHaveBeenCalled()
    expect(fetchEvents).toHaveBeenCalled()
  })

  it('calls interruptAgent when interrupt button clicked', async () => {
    const interruptAgentFn = vi.fn()
    const agent = makeAgent({ id: 'a1', status: 'busy' })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      interruptAgent: interruptAgentFn,
      sendMessage: vi.fn(),
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    // Expand actions to show buttons
    const actionToggle = screen.getAllByText('操作')[0]
    await user.click(actionToggle)

    const interruptBtn = screen.getByText('⏹️')
    await user.click(interruptBtn)

    expect(interruptAgentFn).toHaveBeenCalledWith('a1')
  })

  it('formats seconds into minutes correctly', () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'notify', idle_seconds: 125, last_activity: new Date().toISOString() },
    })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    // 125s = 2m5s
    expect(screen.getByText('2m5s')).toBeInTheDocument()
  })

  it('toggles role collapse when clicking role header', async () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend', instance_number: 1 })
    const agent2 = makeAgent({ id: 'b2', role: 'backend', instance_number: 2 })
    const agentDetails = new Map([['b1', agent1], ['b2', agent2]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    // Roles are expanded by default - verify agent IDs visible
    expect(screen.getByText('b1')).toBeInTheDocument()
    expect(screen.getByText('b2')).toBeInTheDocument()

    // Click the role header to collapse
    const roleHeader = screen.getByText('backend')
    await user.click(roleHeader)

    // After collapse, the count badge should still be visible but individual agent cards hidden
    // The role header toggle exercises the setExpandedRoles branch
    expect(screen.getByText('backend')).toBeInTheDocument()
  })

  it('toggles showActions panel when clicking action header', async () => {
    const agent = makeAgent({ id: 'a1', role: 'backend' })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    // Action buttons are hidden by default (inside showActions && block)
    expect(screen.queryByText('⏹️')).not.toBeInTheDocument()

    // Click "操作" button to show actions (ChevronRight shows ▶ when collapsed)
    const actionToggle = screen.getAllByText('操作')[0]
    await user.click(actionToggle)

    // After toggling, action buttons should be visible
    expect(screen.getByText('⏹️')).toBeInTheDocument()
    expect(screen.getByText('💬')).toBeInTheDocument()

    // Click again to hide (ChevronDown shows ▼ when expanded, exercises setShowActions toggle branch)
    const actionToggleHide = screen.getAllByText('操作')[0]
    await user.click(actionToggleHide)

    // Action buttons should be hidden again
    expect(screen.queryByText('⏹️')).not.toBeInTheDocument()
  })

  it('handles prompt cancellation when sending message', async () => {
    const sendMessage = vi.fn()
    const agent = makeAgent({ id: 'a1', role: 'backend', status: 'idle' })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      sendMessage,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    // Mock prompt to return null (user cancelled)
    const originalPrompt = globalThis.prompt
    globalThis.prompt = vi.fn(() => null)

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    // Expand actions to show buttons
    const actionToggle = screen.getAllByText('操作')[0]
    await user.click(actionToggle)

    // Click send message button
    const sendBtn = screen.getByText('💬')
    await user.click(sendBtn)

    // sendMessage should NOT have been called since prompt returned null
    expect(sendMessage).not.toHaveBeenCalled()

    // Restore original prompt
    globalThis.prompt = originalPrompt
  })

  it('shows current_activity when available', () => {
    const agent = makeAgent({
      id: 'a1',
      current_activity: 'Writing API endpoint',
    })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('⚙️ Writing API endpoint')).toBeInTheDocument()
  })

  it('shows exit_code when process has exit code', () => {
    const agent = makeAgent({
      id: 'a1',
      process_status: { pid: 9999, running: false, exit_code: 1, exists: true },
    })
    const agentDetails = new Map([['a1', agent]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    render(<AgentStatusPanel />)
    expect(screen.getByText('退出码: 1')).toBeInTheDocument()
  })

  it('toggles role to expanded when explicitly set to false', async () => {
    const agent1 = makeAgent({ id: 'b1', role: 'backend', instance_number: 1 })
    const agent2 = makeAgent({ id: 'b2', role: 'backend', instance_number: 2 })
    const agentDetails = new Map([['b1', agent1], ['b2', agent2]])

    vi.mocked(useDashboardStore).mockReturnValue({
      agentDetails,
      fetchAgents: vi.fn(),
      fetchEvents: vi.fn(),
    })

    const user = userEvent.setup()
    render(<AgentStatusPanel />)

    // Initially expanded (default ?? true) - agent IDs visible
    expect(screen.getByText('b1')).toBeInTheDocument()

    // Click to collapse
    const roleHeader = screen.getByText('backend')
    await user.click(roleHeader)

    // Should be collapsed - individual agent cards hidden
    expect(screen.queryByText('b1')).not.toBeInTheDocument()

    // Click again to expand (exercises the false -> true toggle path)
    await user.click(roleHeader)
    expect(screen.getByText('b1')).toBeInTheDocument()
  })
})
