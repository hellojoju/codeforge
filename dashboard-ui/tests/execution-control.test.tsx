/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutionControl } from '@/components/execution-control'
import { useDashboardStore } from '@/lib/store'

// Mock the store
vi.mock('@/lib/store', () => ({
  useDashboardStore: vi.fn(),
}))

// Mock UI components
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>{children}</button>
  ),
}))

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, ...props }: any) => (
    <span {...props}>{children}</span>
  ),
}))

// Mock lucide-react
vi.mock('lucide-react', () => ({
  Play: () => <span data-testid="play-icon" />,
  Square: () => <span data-testid="stop-icon" />,
  Loader2: () => <span data-testid="loader-icon" />,
  AlertTriangle: () => <span data-testid="alert-icon" />,
}))

describe('ExecutionControl', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders idle state with start button', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'idle',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('未启动')).toBeInTheDocument()
    expect(screen.getByText('启动开发')).toBeInTheDocument()
  })

  it('renders running state with stop button', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'running',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('运行中')).toBeInTheDocument()
    expect(screen.getByText('停止')).toBeInTheDocument()
    expect(screen.getByTestId('stop-icon')).toBeInTheDocument()
  })

  it('renders starting state with loader', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'starting',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('启动中')).toBeInTheDocument()
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument()
    expect(screen.getByText('停止')).toBeInTheDocument()
  })

  it('renders completed state', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'completed',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('启动开发')).toBeInTheDocument()
  })

  it('renders error state', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'error',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('错误')).toBeInTheDocument()
  })

  it('shows error message when executionError is set', () => {
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'error',
      executionError: '连接超时',
      startExecution: vi.fn(),
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    expect(screen.getByText('连接超时')).toBeInTheDocument()
    expect(screen.getByTestId('alert-icon')).toBeInTheDocument()
  })

  it('calls startExecution when start button is clicked', () => {
    const startExecution = vi.fn()
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'idle',
      executionError: null,
      startExecution,
      stopExecution: vi.fn(),
    })

    render(<ExecutionControl />)
    screen.getByText('启动开发').click()
    expect(startExecution).toHaveBeenCalled()
  })

  it('calls stopExecution when stop button is clicked', () => {
    const stopExecution = vi.fn()
    vi.mocked(useDashboardStore).mockReturnValue({
      executionStatus: 'running',
      executionError: null,
      startExecution: vi.fn(),
      stopExecution,
    })

    render(<ExecutionControl />)
    screen.getByText('停止').click()
    expect(stopExecution).toHaveBeenCalled()
  })
})
