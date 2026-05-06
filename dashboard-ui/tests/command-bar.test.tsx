/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CommandBar } from '@/components/command-bar'
import * as hooks from '@/lib/hooks/useDashboardQueries'
import * as sonner from 'sonner'
import { renderWithQueryClient } from './test-utils'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('CommandBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useApprove').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
    vi.spyOn(hooks, 'useReject').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
    vi.spyOn(hooks, 'usePauseFeature').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
    vi.spyOn(hooks, 'useResumeFeature').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
    vi.spyOn(hooks, 'useRetryFeature').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
    vi.spyOn(hooks, 'useSkipFeature').mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) } as any)
  })

  it('renders all command buttons', () => {
    renderWithQueryClient(<CommandBar />)
    expect(screen.getByText('审批通过')).toBeInTheDocument()
    expect(screen.getByText('驳回')).toBeInTheDocument()
    expect(screen.getByText('暂停')).toBeInTheDocument()
    expect(screen.getByText('恢复')).toBeInTheDocument()
    expect(screen.getByText('重试')).toBeInTheDocument()
    expect(screen.getByText('跳过')).toBeInTheDocument()
  })

  it('shows label when no feature is in progress', () => {
    renderWithQueryClient(<CommandBar />)
    expect(screen.getByText('PM 指令：')).toBeInTheDocument()
  })

  it('calls approve action for in_progress feature', async () => {
    const approveAsync = vi.fn().mockResolvedValue({})
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [{ id: 'feat-1', description: 'Test', status: 'in_progress' }],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useApprove').mockReturnValue({ mutateAsync: approveAsync } as any)

    renderWithQueryClient(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))

    expect(approveAsync).toHaveBeenCalledWith('feat-1')
    expect(sonner.toast.success).toHaveBeenCalledWith('命令已发送', { description: '审批通过 操作已提交' })
  })

  it('calls reject action for in_progress feature', async () => {
    const rejectAsync = vi.fn().mockResolvedValue({})
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [{ id: 'feat-1', description: 'Test', status: 'in_progress' }],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useReject').mockReturnValue({ mutateAsync: rejectAsync } as any)

    renderWithQueryClient(<CommandBar />)
    await userEvent.click(screen.getByText('驳回'))
    expect(rejectAsync).toHaveBeenCalledWith('feat-1')
  })

  it('shows loading state during action', async () => {
    let resolvePromise: () => void
    const approveAsync = vi.fn().mockImplementation(
      () => new Promise<void>((resolve) => { resolvePromise = resolve })
    )
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [{ id: 'feat-1', description: 'Test', status: 'in_progress' }],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useApprove').mockReturnValue({ mutateAsync: approveAsync } as any)

    renderWithQueryClient(<CommandBar />)
    fireEvent.click(screen.getByText('审批通过'))

    expect(screen.getByText('发送中...')).toBeInTheDocument()
    expect(screen.getByText('驳回')).toBeDisabled()

    resolvePromise!()
  })

  it('shows error toast on failure', async () => {
    const approveAsync = vi.fn().mockRejectedValue(new Error('Network error'))
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [{ id: 'feat-1', description: 'Test', status: 'in_progress' }],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useApprove').mockReturnValue({ mutateAsync: approveAsync } as any)

    renderWithQueryClient(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))

    expect(sonner.toast.error).toHaveBeenCalledWith('发送失败', { description: 'Network error' })
  })

  it('uses pm as target when no feature is in progress', async () => {
    const approveAsync = vi.fn().mockResolvedValue({})
    vi.spyOn(hooks, 'useFeatures').mockReturnValue({
      data: [{ id: 'f1', description: 'Test', status: 'done' }],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useApprove').mockReturnValue({ mutateAsync: approveAsync } as any)

    renderWithQueryClient(<CommandBar />)
    await userEvent.click(screen.getByText('审批通过'))
    expect(approveAsync).toHaveBeenCalledWith('pm')
  })
})
