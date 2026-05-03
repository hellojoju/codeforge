/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CommandBar } from '@/components/command-bar'
import * as sonner from 'sonner'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const mockApprove = vi.fn().mockResolvedValue(undefined)
const mockReject = vi.fn().mockResolvedValue(undefined)
const mockPause = vi.fn().mockResolvedValue(undefined)
const mockResume = vi.fn().mockResolvedValue(undefined)
const mockRetry = vi.fn().mockResolvedValue(undefined)
const mockSkip = vi.fn().mockResolvedValue(undefined)

const mockStore = {
  features: [] as any[],
  approve: mockApprove,
  reject: mockReject,
  pause: mockPause,
  resume: mockResume,
  retry: mockRetry,
  skip: mockSkip,
}

vi.mock('@/lib/store', () => {
  const fn = vi.fn((selector?: (s: any) => any) => {
    return selector ? selector(mockStore) : mockStore
  })
  ;(fn as any).getState = () => mockStore
  return { useDashboardStore: fn }
})

describe('CommandBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStore.features = []
    mockStore.approve = mockApprove
    mockStore.reject = mockReject
    mockStore.pause = mockPause
    mockStore.resume = mockResume
    mockStore.retry = mockRetry
    mockStore.skip = mockSkip
  })

  it('renders all command buttons', () => {
    render(<CommandBar />)

    expect(screen.getByText('审批通过')).toBeInTheDocument()
    expect(screen.getByText('驳回')).toBeInTheDocument()
    expect(screen.getByText('暂停')).toBeInTheDocument()
    expect(screen.getByText('恢复')).toBeInTheDocument()
    expect(screen.getByText('重试')).toBeInTheDocument()
    expect(screen.getByText('跳过')).toBeInTheDocument()
  })

  it('shows label when no feature is in progress', () => {
    render(<CommandBar />)
    expect(screen.getByText('PM 指令：')).toBeInTheDocument()
  })

  it('calls approve action for in_progress feature', async () => {
    const feature = { id: 'feat-1', description: 'Test', status: 'in_progress' }
    mockStore.features = [feature]

    render(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))

    expect(mockApprove).toHaveBeenCalledWith('feat-1')
    expect(sonner.toast.success).toHaveBeenCalledWith('命令已发送', { description: '审批通过 操作已提交' })
  })

  it('calls reject action for in_progress feature', async () => {
    const feature = { id: 'feat-1', description: 'Test', status: 'in_progress' }
    mockStore.features = [feature]

    render(<CommandBar />)
    await userEvent.click(screen.getByText('驳回'))

    expect(mockReject).toHaveBeenCalledWith('feat-1')
  })

  it('shows loading state during action', async () => {
    let resolvePromise: () => void
    const approve = vi.fn().mockImplementation(
      () => new Promise<void>((resolve) => { resolvePromise = resolve })
    )
    const feature = { id: 'feat-1', description: 'Test', status: 'in_progress' }
    mockStore.features = [feature]
    mockStore.approve = approve

    render(<CommandBar />)
    fireEvent.click(screen.getByText('审批通过'))

    // The button should show loading state
    expect(screen.getByText('发送中...')).toBeInTheDocument()
    expect(screen.getByText('驳回')).toBeDisabled()

    // Resolve the promise to clean up
    resolvePromise!()
    await vi.waitFor(() => {
      expect(mockApprove).not.toHaveBeenCalled() // approve was replaced, so this won't be called
    })
  })

  it('shows error toast on failure', async () => {
    const approve = vi.fn().mockRejectedValue(new Error('Network error'))
    const feature = { id: 'feat-1', description: 'Test', status: 'in_progress' }
    mockStore.features = [feature]
    mockStore.approve = approve

    render(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))

    expect(sonner.toast.error).toHaveBeenCalledWith('发送失败', { description: 'Network error' })
  })

  it('uses pm as target when no feature is in progress', async () => {
    mockStore.features = [{ id: 'f1', description: 'Test', status: 'done' }]

    render(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))

    expect(mockApprove).toHaveBeenCalledWith('pm')
  })
})
