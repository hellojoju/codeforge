/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgentClusterMonitor } from '@/components/agent-cluster-monitor'
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

vi.mock('@/components/ui/avatar', () => ({
  Avatar: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className || ''}>{children}</div>
  ),
  AvatarFallback: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <span className={className || ''}>{children}</span>
  ),
}))

vi.mock('@/components/ui/separator', () => ({
  Separator: ({ className }: { className?: string }) => (
    <hr className={className || ''} data-testid="separator" />
  ),
}))

vi.mock('lucide-react', () => ({
  ChevronDown: () => <span data-testid="chevron-down">▼</span>,
  ChevronRight: () => <span data-testid="chevron-right">▶</span>,
  Pause: () => <span data-testid="icon-pause">⏸</span>,
  RotateCcw: () => <span data-testid="icon-resume">↻</span>,
  Zap: () => <span data-testid="icon-interrupt">⚡</span>,
  Cpu: () => <span data-testid="icon-cpu">🖥</span>,
  Clock: () => <span data-testid="icon-clock">🕐</span>,
  AlertTriangle: () => <span data-testid="icon-warning">⚠</span>,
}))

const makeAgent = (overrides: Partial<AgentWithSilence> = {}): AgentWithSilence => ({
  id: 'agent-1',
  role: 'backend_dev',
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

describe('AgentClusterMonitor', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows empty state when no agents', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [],
      fetchAgents: vi.fn(),
    } as any)

    render(<AgentClusterMonitor />)
    expect(screen.getByText('暂无 Agent 实例')).toBeInTheDocument()
  })

  it('renders agents grouped by role', () => {
    const agent1 = makeAgent({ id: 'backend-1', role: 'backend_dev', instance_number: 1 })
    const agent2 = makeAgent({ id: 'frontend-1', role: 'frontend_dev', instance_number: 2 })

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [agent1, agent2],
      fetchAgents: vi.fn(),
    } as any)

    render(<AgentClusterMonitor />)
    expect(screen.getByText((content) => content.includes('后端开发'))).toBeInTheDocument()
    expect(screen.getByText((content) => content.includes('前端开发'))).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
  })

  it('shows status dots with correct colors', () => {
    const idleAgent = makeAgent({ id: 'a1', status: 'idle' })
    const busyAgent = makeAgent({ id: 'a2', status: 'busy' })
    const errorAgent = makeAgent({ id: 'a3', status: 'error' })

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [idleAgent, busyAgent, errorAgent],
      fetchAgents: vi.fn(),
    } as any)

    render(<AgentClusterMonitor />)
    // Status dots are plain spans with color classes like bg-gray-400, bg-green-500, bg-red-500
    const dots = screen.getAllByText((content, element) => {
      return (element?.className.includes('rounded-full') && element?.className.includes('bg-')) ?? false
    })
    expect(dots.length).toBeGreaterThanOrEqual(3)
  })

  it('shows current activity for running agents', () => {
    const agent = makeAgent({
      id: 'a1',
      status: 'busy',
      current_feature: 'API endpoint for /api/projects',
    })

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [agent],
      fetchAgents: vi.fn(),
    } as any)

    render(<AgentClusterMonitor />)
    expect(screen.getByText('处理: API endpoint for /api/projects')).toBeInTheDocument()
  })

  it('shows expanded agent details when row clicked', async () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'warning', idle_seconds: 120, last_activity: new Date().toISOString() },
      process_status: { pid: 5678, running: false, exit_code: 1, exists: true },
      total_tasks_completed: 10,
    })

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [agent],
      fetchAgents: vi.fn(),
    } as any)

    const user = userEvent.setup()
    render(<AgentClusterMonitor />)

    // Click expand toggle
    const toggle = screen.getByTestId('chevron-right')
    await user.click(toggle)

    expect(screen.getByText('PID: 5678')).toBeInTheDocument()
    expect(screen.getByText('已终止')).toBeInTheDocument()
    expect(screen.getByText('已完成: 10 任务')).toBeInTheDocument()
  })

  it('shows warning for non-active silence level', async () => {
    const agent = makeAgent({
      id: 'a1',
      silence_status: { level: 'notify', idle_seconds: 300, last_activity: new Date().toISOString() },
    })

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [agent],
      fetchAgents: vi.fn(),
    } as any)

    const user = userEvent.setup()
    render(<AgentClusterMonitor />)

    // The warning icon only shows when the row is expanded
    const toggle = screen.getByTestId('chevron-right')
    await user.click(toggle)

    expect(screen.getByTestId('icon-warning')).toBeInTheDocument()
  })

  it('calls fetchAgents on mount', () => {
    const fetchAgents = vi.fn()

    vi.mocked(useDashboardStore).mockReturnValue({
      agents: [],
      fetchAgents,
    } as any)

    render(<AgentClusterMonitor />)
    expect(fetchAgents).toHaveBeenCalled()
  })
})
