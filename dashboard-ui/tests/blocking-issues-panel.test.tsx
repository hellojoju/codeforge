/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BlockingIssuesPanel } from '@/components/blocking-issues-panel'
import * as hooks from '@/lib/hooks/useDashboardQueries'
import { renderWithQueryClient } from './test-utils'

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  CardContent: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  CardHeader: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  CardTitle: ({ children, ...props }: any) => <h2 {...props}>{children}</h2>,
}))

vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children, ...props }: any) => <div {...props}>{children}</div>,
}))

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>{children}</button>
  ),
}))

vi.mock('lucide-react', () => ({
  AlertTriangle: () => <span data-testid="alert-icon" />,
  CheckCircle2: () => <span data-testid="check-icon" />,
  Loader2: () => <span data-testid="loader-icon" />,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const mockIssues = [
  {
    issue_id: 'issue-1',
    feature_id: 'F001',
    issue_type: 'missing_env',
    description: '缺少 ANTHROPIC_API_KEY',
    resolved: false,
    resolution: null,
    resolved_at: null,
    context: {},
  },
  {
    issue_id: 'issue-2',
    feature_id: 'F002',
    issue_type: 'code_error',
    description: '编译失败',
    resolved: true,
    resolution: '已修复',
    resolved_at: '2026-05-06T10:00:00Z',
    context: {},
  },
]

describe('BlockingIssuesPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders empty state when no issues', () => {
    vi.spyOn(hooks, 'useBlockingIssues').mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<BlockingIssuesPanel />)
    expect(screen.getByText('当前没有阻塞问题。')).toBeInTheDocument()
  })

  it('renders blocking issues', () => {
    vi.spyOn(hooks, 'useBlockingIssues').mockReturnValue({
      data: mockIssues,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    renderWithQueryClient(<BlockingIssuesPanel />)
    expect(screen.getByText('缺少环境变量')).toBeInTheDocument()
    expect(screen.getByText('阻塞中')).toBeInTheDocument()
    expect(screen.getByText('已解决')).toBeInTheDocument()
    expect(screen.getByText('缺少 ANTHROPIC_API_KEY')).toBeInTheDocument()
  })

  it('calls resolveBlockingIssue when resolve button is clicked', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ success: true })
    vi.spyOn(hooks, 'useBlockingIssues').mockReturnValue({
      data: mockIssues,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.spyOn(hooks, 'useResolveBlockingIssue').mockReturnValue({
      mutateAsync,
      isPending: false,
    } as any)

    const user = userEvent.setup()
    renderWithQueryClient(<BlockingIssuesPanel />)
    const resolveBtn = screen.getByText('标记已解决')
    await user.click(resolveBtn)
    expect(mutateAsync).toHaveBeenCalledWith({
      issueId: 'issue-1',
      resolution: '人工确认已处理',
    })
  })
})
