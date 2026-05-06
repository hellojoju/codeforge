/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExecutionControl } from '@/components/execution-control'
import * as hooks from '@/lib/hooks/useDashboardQueries'
import { renderWithQueryClient } from './test-utils'

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
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'idle', thread_alive: false, error: null, available: false },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('未启动')).toBeInTheDocument()
    expect(screen.getByText('启动开发')).toBeInTheDocument()
  })

  it('renders running state with stop button', () => {
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'running', thread_alive: true, error: null, available: true },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('运行中')).toBeInTheDocument()
    expect(screen.getByText('停止')).toBeInTheDocument()
    expect(screen.getByTestId('stop-icon')).toBeInTheDocument()
  })

  it('renders starting state with loader', () => {
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'starting', thread_alive: true, error: null, available: true },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('启动中')).toBeInTheDocument()
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument()
    expect(screen.getByText('停止')).toBeInTheDocument()
  })

  it('renders completed state', () => {
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'completed', thread_alive: false, error: null, available: false },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('启动开发')).toBeInTheDocument()
  })

  it('renders error state', () => {
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'error', thread_alive: false, error: null, available: false },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('错误')).toBeInTheDocument()
  })

  it('shows error message when executionError is set', () => {
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'error', thread_alive: false, error: '连接超时', available: false },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<ExecutionControl />)
    expect(screen.getByText('连接超时')).toBeInTheDocument()
    expect(screen.getByTestId('alert-icon')).toBeInTheDocument()
  })

  it('calls startExecution when start button is clicked', async () => {
    const mutate = vi.fn()
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'idle', thread_alive: false, error: null, available: false },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useStartExecution').mockReturnValue({ mutate, isPending: false } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<ExecutionControl />)
    await user.click(screen.getByText('启动开发'))
    expect(mutate).toHaveBeenCalled()
  })

  it('calls stopExecution when stop button is clicked', async () => {
    const mutate = vi.fn()
    vi.spyOn(hooks, 'useExecutionStatus').mockReturnValue({
      data: { status: 'running', thread_alive: true, error: null, available: true },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useStopExecution').mockReturnValue({ mutate, isPending: false } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<ExecutionControl />)
    await user.click(screen.getByText('停止'))
    expect(mutate).toHaveBeenCalled()
  })
})
