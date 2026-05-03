import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ApprovalCenter } from '@/components/ralph/approval-center';
import * as ralphStore from '@/lib/ralph-store';
import * as ralphApi from '@/lib/ralph-api';
import { toast } from 'sonner';
import type { PendingAction, Blocker } from '@/lib/ralph-types';

// Mock dependencies
vi.mock('@/lib/ralph-store', () => ({
  useRalphStore: vi.fn(),
}));

vi.mock('@/lib/ralph-api', () => ({
  createCommand: vi.fn(),
}));

vi.mock('@/lib/ralph-utils', () => ({
  generateIdempotencyKey: vi.fn(() => 'test-idempotency-key'),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  ShieldCheck: () => <span data-testid="icon-shield-check">Shield</span>,
  AlertTriangle: () => <span data-testid="icon-alert">Alert</span>,
  Expand: () => <span data-testid="icon-expand">Expand</span>,
  MessageSquare: () => <span data-testid="icon-message">Message</span>,
  PackageX: () => <span data-testid="icon-package">Package</span>,
  XCircle: () => <span data-testid="icon-x">XCircle</span>,
  Hand: () => <span data-testid="icon-hand">Hand</span>,
  Clock: () => <span data-testid="icon-clock">Clock</span>,
}));

describe('ApprovalCenter', () => {
  const mockRefreshAll = vi.fn();

  const mockPendingActions: PendingAction[] = [
    {
      action_id: 'action-1',
      action_type: 'dangerous_op',
      work_id: 'work-123',
      description: 'This is a dangerous operation requiring approval',
      context: { risk_level: 'high' },
      created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
    },
    {
      action_id: 'action-2',
      action_type: 'scope_expansion',
      work_id: 'work-456',
      description: 'Scope expansion request for additional features',
      context: { new_scope: ['feature-a', 'feature-b'] },
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    },
    {
      action_id: 'action-3',
      action_type: 'manual_intervention',
      work_id: 'work-789',
      description: 'Manual intervention required for complex decision',
      context: {},
      created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 minutes ago
    },
  ];

  const mockBlockers: Blocker[] = [
    {
      blocker_id: 'blocker-1',
      work_id: 'work-blocker-1',
      reason: 'Missing required permission for file access',
      category: 'permission',
      created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      resolved: false,
    },
    {
      blocker_id: 'blocker-2',
      work_id: 'work-blocker-2',
      reason: 'Dependency package not found in registry',
      category: 'dependency',
      created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      resolved: false,
    },
    {
      blocker_id: 'blocker-3',
      work_id: 'work-999',
      reason: 'Resolved blocker',
      category: 'resource',
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
      resolved: true, // Should not be displayed
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ralphStore.useRalphStore).mockReturnValue({
      pendingActions: mockPendingActions,
      blockers: mockBlockers,
      refreshAll: mockRefreshAll,
      workUnits: [],
    } as unknown as ReturnType<typeof ralphStore.useRalphStore>);
  });

  describe('Rendering', () => {
    it('renders header with correct counts', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('审批中心')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument(); // pendingActions.length
      expect(screen.getByText('2')).toBeInTheDocument(); // unresolved blockers
    });

    it('renders pending actions section', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('待处理审批')).toBeInTheDocument();
      expect(screen.getByText('危险操作')).toBeInTheDocument();
      expect(screen.getByText('范围扩展')).toBeInTheDocument();
      expect(screen.getByText('人工干预')).toBeInTheDocument();
    });

    it('renders action descriptions', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('This is a dangerous operation requiring approval')).toBeInTheDocument();
      expect(screen.getByText('Scope expansion request for additional features')).toBeInTheDocument();
      expect(screen.getByText('Manual intervention required for complex decision')).toBeInTheDocument();
    });

    it('renders work IDs', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('ID: work-123')).toBeInTheDocument();
      expect(screen.getByText('ID: work-456')).toBeInTheDocument();
      expect(screen.getByText('ID: work-789')).toBeInTheDocument();
    });

    it('renders approve and reject buttons for each action', () => {
      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });

      expect(approveButtons).toHaveLength(3);
      expect(rejectButtons).toHaveLength(3);
    });

    it('renders blockers section', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('阻塞项')).toBeInTheDocument();
      expect(screen.getByText('权限')).toBeInTheDocument();
      expect(screen.getByText('依赖')).toBeInTheDocument();
    });

    it('renders blocker reasons', () => {
      render(<ApprovalCenter />);

      expect(screen.getByText('Missing required permission for file access')).toBeInTheDocument();
      expect(screen.getByText('Dependency package not found in registry')).toBeInTheDocument();
      expect(screen.getByText('ID: work-blocker-1')).toBeInTheDocument();
      expect(screen.getByText('ID: work-blocker-2')).toBeInTheDocument();
    });

    it('does not render resolved blockers', () => {
      render(<ApprovalCenter />);

      expect(screen.queryByText('Resolved blocker')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('renders empty state when no pending actions', () => {
      vi.mocked(ralphStore.useRalphStore).mockReturnValue({
        pendingActions: [],
        blockers: [],
        refreshAll: mockRefreshAll,
        workUnits: [],
      } as unknown as ReturnType<typeof ralphStore.useRalphStore>);

      render(<ApprovalCenter />);

      expect(screen.getByText('暂无待处理的审批事项')).toBeInTheDocument();
      expect(screen.getByText('所有审批请求都已处理完毕')).toBeInTheDocument();
    });

    it('does not render blockers section when no unresolved blockers', () => {
      vi.mocked(ralphStore.useRalphStore).mockReturnValue({
        pendingActions: mockPendingActions,
        blockers: [{ ...mockBlockers[2] }], // Only resolved blocker
        refreshAll: mockRefreshAll,
        workUnits: [],
      } as unknown as ReturnType<typeof ralphStore.useRalphStore>);

      render(<ApprovalCenter />);

      expect(screen.queryByText('阻塞项')).not.toBeInTheDocument();
    });
  });

  describe('Approval Actions', () => {
    it('calls createCommand with correct params when approving dangerous_op', async () => {
      vi.mocked(ralphApi.createCommand).mockResolvedValueOnce({
        command_id: 'cmd-1',
        command_type: 'dangerous_op_confirm',
        target_id: 'work-123',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      fireEvent.click(approveButtons[0]); // First action is dangerous_op

      await waitFor(() => {
        expect(ralphApi.createCommand).toHaveBeenCalledWith({
          command_type: 'dangerous_op_confirm',
          target_id: 'work-123',
          payload: {
            action_id: 'action-1',
            context: { risk_level: 'high' },
          },
          idempotency_key: 'test-idempotency-key',
        });
      });
    });

    it('calls createCommand with correct params when approving scope_expansion', async () => {
      vi.mocked(ralphApi.createCommand).mockResolvedValueOnce({
        command_id: 'cmd-2',
        command_type: 'expand_scope',
        target_id: 'work-456',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      fireEvent.click(approveButtons[1]); // Second action is scope_expansion

      await waitFor(() => {
        expect(ralphApi.createCommand).toHaveBeenCalledWith({
          command_type: 'expand_scope',
          target_id: 'work-456',
          payload: {
            action_id: 'action-2',
            context: { new_scope: ['feature-a', 'feature-b'] },
          },
          idempotency_key: 'test-idempotency-key',
        });
      });
    });

    it('calls createCommand with cancel_work_unit when rejecting', async () => {
      vi.mocked(ralphApi.createCommand).mockResolvedValueOnce({
        command_id: 'cmd-3',
        command_type: 'cancel_work_unit',
        target_id: 'work-123',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });

      render(<ApprovalCenter />);

      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });
      fireEvent.click(rejectButtons[0]);

      await waitFor(() => {
        expect(ralphApi.createCommand).toHaveBeenCalledWith({
          command_type: 'cancel_work_unit',
          target_id: 'work-123',
          payload: {
            action_id: 'action-1',
            context: { risk_level: 'high' },
            reason: 'rejected_by_user',
          },
          idempotency_key: 'test-idempotency-key',
        });
      });
    });

    it('shows success toast and refreshes data after approval', async () => {
      vi.mocked(ralphApi.createCommand).mockResolvedValueOnce({
        command_id: 'cmd-1',
        command_type: 'dangerous_op_confirm',
        target_id: 'work-123',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      fireEvent.click(approveButtons[0]);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('已批准', {
          description: '危险操作 已批准处理',
        });
      });

      expect(mockRefreshAll).toHaveBeenCalled();
    });

    it('shows success toast and refreshes data after rejection', async () => {
      vi.mocked(ralphApi.createCommand).mockResolvedValueOnce({
        command_id: 'cmd-1',
        command_type: 'cancel_work_unit',
        target_id: 'work-123',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });

      render(<ApprovalCenter />);

      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });
      fireEvent.click(rejectButtons[0]);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('已拒绝', {
          description: '危险操作 已被拒绝',
        });
      });

      expect(mockRefreshAll).toHaveBeenCalled();
    });

    it('shows error toast when approval fails', async () => {
      vi.mocked(ralphApi.createCommand).mockRejectedValueOnce(new Error('API Error'));

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      fireEvent.click(approveButtons[0]);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('批准失败', {
          description: 'API Error',
        });
      });
    });

    it('shows error toast when rejection fails', async () => {
      vi.mocked(ralphApi.createCommand).mockRejectedValueOnce(new Error('Network Error'));

      render(<ApprovalCenter />);

      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });
      fireEvent.click(rejectButtons[0]);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('拒绝失败', {
          description: 'Network Error',
        });
      });
    });

    it('disables buttons while loading', async () => {
      // Create a promise that never resolves to keep loading state
      vi.mocked(ralphApi.createCommand).mockImplementationOnce(() => new Promise(() => {}));

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });

      fireEvent.click(approveButtons[0]);

      await waitFor(() => {
        expect(approveButtons[0]).toBeDisabled();
        expect(rejectButtons[0]).toBeDisabled();
      });
    });

    it('shows loading text on buttons while processing', async () => {
      // Create a deferred promise to control when it resolves
      let resolvePromise: (value: unknown) => void;
      const deferredPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(ralphApi.createCommand).mockImplementationOnce(() => deferredPromise as Promise<never>);

      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      fireEvent.click(approveButtons[0]);

      // Wait for loading state to appear
      await waitFor(() => {
        const loadingButtons = screen.getAllByText('处理中...');
        expect(loadingButtons.length).toBeGreaterThan(0);
      });

      // Clean up by resolving the promise
      resolvePromise!({
        command_id: 'cmd-1',
        command_type: 'dangerous_op_confirm',
        target_id: 'work-123',
        payload: {},
        status: 'pending',
        idempotency_key: 'test-idempotency-key',
        issued_by: 'user',
        issued_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: {},
      });
    });
  });

  describe('Date Formatting', () => {
    it('displays relative time for recent actions', () => {
      render(<ApprovalCenter />);

      // Should show "30分钟前", "2小时前", "5分钟前" etc.
      // Multiple elements may match, so use getAllByText
      const timeElements = screen.getAllByText(/分钟前|小时前/);
      expect(timeElements.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('buttons are accessible via role', () => {
      render(<ApprovalCenter />);

      const approveButtons = screen.getAllByRole('button', { name: '批准' });
      const rejectButtons = screen.getAllByRole('button', { name: '拒绝' });

      expect(approveButtons.length).toBeGreaterThan(0);
      expect(rejectButtons.length).toBeGreaterThan(0);
    });
  });
});
