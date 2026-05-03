/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ModuleAssignmentPanel } from '@/components/module-assignment-panel'
import { useDashboardStore } from '@/lib/store'

vi.mock('@/lib/store', () => ({
  useDashboardStore: vi.fn((selector?: (s: any) => any) => {
    const state = {
      moduleAssignments: [],
      agents: [],
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, variant, className }: { children: React.ReactNode; variant?: string; className?: string }) => (
    <span className={className || ''} data-variant={variant}>{children}</span>
  ),
}))

describe('ModuleAssignmentPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('returns null when no assignments', () => {
    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: [], agents: [] }
      return selector ? selector(state) : state
    })

    const { container } = render(<ModuleAssignmentPanel />)
    expect(container.innerHTML).toBe('')
  })

  it('renders modules grouped by role', () => {
    const assignments = [
      {
        module_id: 'auth',
        module_name: 'auth-module',
        role: 'backend',
        status: 'in_progress',
        description: 'Auth API implementation',
        dependencies: ['database'],
        assigned_agent_id: 'backend-1',
        interface_contract: {},
      },
      {
        module_id: 'login-page',
        module_name: 'login-page',
        role: 'frontend',
        status: 'pending',
        description: 'Login page UI',
        dependencies: [],
        assigned_agent_id: '',
        interface_contract: {},
      },
    ]

    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: assignments, agents: [] }
      return selector ? selector(state) : state
    })

    render(<ModuleAssignmentPanel />)
    expect(screen.getByText('backend')).toBeInTheDocument()
    expect(screen.getByText('frontend')).toBeInTheDocument()
    expect(screen.getByText('auth-module')).toBeInTheDocument()
    expect(screen.getByText('login-page')).toBeInTheDocument()
  })

  it('shows status badges with correct labels', () => {
    const assignments = [
      {
        module_id: 'm1',
        module_name: 'Module 1',
        role: 'backend',
        status: 'completed',
        description: 'Done',
        dependencies: [],
        assigned_agent_id: '',
        interface_contract: {},
      },
      {
        module_id: 'm2',
        module_name: 'Module 2',
        role: 'backend',
        status: 'blocked',
        description: 'Blocked',
        dependencies: ['m1'],
        assigned_agent_id: '',
        interface_contract: {},
      },
    ]

    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: assignments, agents: [] }
      return selector ? selector(state) : state
    })

    render(<ModuleAssignmentPanel />)
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('已阻塞')).toBeInTheDocument()
  })

  it('shows assigned agent info', () => {
    const assignments = [
      {
        module_id: 'api',
        module_name: 'API dev',
        role: 'backend',
        status: 'in_progress',
        description: 'API dev',
        dependencies: [],
        assigned_agent_id: 'backend-1',
        interface_contract: {},
      },
    ]

    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: assignments, agents: [] }
      return selector ? selector(state) : state
    })

    render(<ModuleAssignmentPanel />)
    expect(screen.getByText('→ 未分配')).toBeInTheDocument()
  })

  it('shows dependencies as tags', () => {
    const assignments = [
      {
        module_id: 'api',
        module_name: 'API',
        role: 'backend',
        status: 'pending',
        description: 'API',
        dependencies: ['database', 'auth'],
        assigned_agent_id: '',
        interface_contract: {},
      },
    ]

    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: assignments, agents: [] }
      return selector ? selector(state) : state
    })

    render(<ModuleAssignmentPanel />)
    expect(screen.getByText('database')).toBeInTheDocument()
    expect(screen.getByText('auth')).toBeInTheDocument()
  })

  it('shows role count badges', () => {
    const assignments = [
      { module_id: 'm1', module_name: 'D1', role: 'backend', status: 'pending', description: 'D1', dependencies: [], assigned_agent_id: '', interface_contract: {} },
      { module_id: 'm2', module_name: 'D2', role: 'backend', status: 'pending', description: 'D2', dependencies: [], assigned_agent_id: '', interface_contract: {} },
      { module_id: 'm3', module_name: 'D3', role: 'qa', status: 'pending', description: 'D3', dependencies: [], assigned_agent_id: '', interface_contract: {} },
    ]

    vi.mocked(useDashboardStore).mockImplementation((selector?: (s: any) => any) => {
      const state = { moduleAssignments: assignments, agents: [] }
      return selector ? selector(state) : state
    })

    render(<ModuleAssignmentPanel />)
    expect(screen.getByText('qa')).toBeInTheDocument()
  })
})
