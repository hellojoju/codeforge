import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Sidebar } from '@/components/ralph/sidebar';
import * as storeModule from '@/lib/ralph-store';
import type { Tab } from '@/lib/ralph-types';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock the store
vi.mock('@/lib/ralph-store', () => ({
  useRalphStore: vi.fn(),
}));

const mockAddTab = vi.fn();
const mockSetActiveTab = vi.fn();

// Mock localStorage for SSR-safe hydration
const mockLocalStorage = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
};

Object.defineProperty(globalThis, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
  configurable: true,
});

const createMockStore = (tabs: Tab[] = []) => ({
  tabs,
  activeTabId: null,
  addTab: mockAddTab,
  closeTab: vi.fn(),
  setActiveTab: mockSetActiveTab,
  pendingActions: [],
  workUnits: [],
  selectedWorkUnit: null,
  statusFilter: 'all' as const,
  blockers: [],
  runStatus: null,
  connected: false,
  lastEvent: null,
  loading: false,
  streamChunks: {},
  recentEvents: [],
  pendingCommandCount: 0,
  currentProject: null,
  recentProjects: [],
  projectAnalysis: null,
  fileTree: [],
  currentFilePath: null,
  fileContent: null,
  pipelineStages: [],
  schedulingTimeline: [],
  setWorkUnits: vi.fn(),
  updateWorkUnit: vi.fn(),
  setSelectedWorkUnit: vi.fn(),
  setStatusFilter: vi.fn(),
  fetchWorkUnits: vi.fn(),
  setPendingActions: vi.fn(),
  setBlockers: vi.fn(),
  setRunStatus: vi.fn(),
  setConnected: vi.fn(),
  handleEvent: vi.fn(),
  createCommand: vi.fn(),
  refreshAll: vi.fn(),
  fetchPendingCommandCount: vi.fn(),
  setCurrentProject: vi.fn(),
  setRecentProjects: vi.fn(),
  setProjectAnalysis: vi.fn(),
  setFileTree: vi.fn(),
  openFile: vi.fn(),
  closeFile: vi.fn(),
  setPipelineStages: vi.fn(),
  setSchedulingTimeline: vi.fn(),
  appendStreamChunk: vi.fn(),
  clearStreamChunks: vi.fn(),
});

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem('ralph-sidebar-collapsed');
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore());
  });

  it('renders with default expanded state', () => {
    render(<Sidebar />);

    // Check navigation items are visible
    expect(screen.getByText('概览')).toBeTruthy();
    expect(screen.getByText('审批中心')).toBeTruthy();

    // Check collapse button is present
    expect(screen.getByLabelText('收起侧边栏')).toBeTruthy();
  });

  it('toggles collapsed state when clicking collapse button', () => {
    render(<Sidebar />);

    const collapseButton = screen.getByLabelText('收起侧边栏');

    // Click to collapse
    fireEvent.click(collapseButton);

    // Should now show expand button
    expect(screen.getByLabelText('展开侧边栏')).toBeTruthy();

    // Labels should be hidden when collapsed
    expect(screen.queryByText('概览')).toBeNull();
  });

  it('calls addTab when clicking navigation item', () => {
    render(<Sidebar />);

    const overviewButton = screen.getByText('概览').closest('button');
    fireEvent.click(overviewButton!);

    expect(mockAddTab).toHaveBeenCalledWith({
      label: '概览',
      type: 'overview',
      work_id: undefined,
      pinned: false,
    });
  });

  it('calls setActiveTab when clicking existing tab type', () => {
    const existingTabs: Tab[] = [
      { id: 'tab-1', label: '概览', type: 'overview', pinned: false, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(existingTabs));

    render(<Sidebar />);

    const overviewButton = screen.getByText('概览').closest('button');
    fireEvent.click(overviewButton!);

    // Should activate existing tab instead of creating new one
    expect(mockSetActiveTab).toHaveBeenCalledWith('tab-1');
    expect(mockAddTab).not.toHaveBeenCalled();
  });

  it('renders with correct width classes', () => {
    const { container } = render(<Sidebar />);

    const aside = container.querySelector('aside');
    expect(aside?.classList.contains('w-60')).toBe(true);
  });

  it('applies custom className', () => {
    const { container } = render(<Sidebar className="custom-class" />);

    const aside = container.querySelector('aside');
    expect(aside?.classList.contains('custom-class')).toBe(true);
  });

  it('renders status indicator in footer', () => {
    render(<Sidebar />);

    // Should show status dot and text when expanded
    expect(screen.getByText('系统运行中')).toBeTruthy();
  });

  it('has smooth transition classes', () => {
    const { container } = render(<Sidebar />);

    const aside = container.querySelector('aside');
    expect(aside?.classList.contains('transition-all')).toBe(true);
    expect(aside?.classList.contains('duration-200')).toBe(true);
  });

  describe('approval badge', () => {
    it('does not render badge when no pending actions', () => {
      vi.mocked(storeModule.useRalphStore).mockReturnValue(
        createMockStore()
      );
      render(<Sidebar />);

      // No red badge elements should exist
      expect(screen.queryByText('0')).toBeNull();
      expect(screen.queryByTestId('approval-badge')).toBeNull();
    });

    it('renders red number badge when expanded with pending actions', () => {
      vi.mocked(storeModule.useRalphStore).mockReturnValue({
        ...createMockStore(),
        pendingActions: [
          { action_id: 'act-1', action_type: 'dangerous_op', work_id: 'wu-1', description: 'Test', context: {}, created_at: '2024-01-01' },
          { action_id: 'act-2', action_type: 'scope_expansion', work_id: 'wu-2', description: 'Test2', context: {}, created_at: '2024-01-01' },
          { action_id: 'act-3', action_type: 'manual_intervention', work_id: 'wu-3', description: 'Test3', context: {}, created_at: '2024-01-01' },
        ],
      });
      render(<Sidebar />);

      // Should show the count "3" as text content
      const badge = screen.getByText('3');
      expect(badge).toBeTruthy();
      // The element itself or its parent has the badge styling
      const badgeElement = badge.tagName === 'SPAN' ? badge : badge.parentElement;
      expect(badgeElement?.classList.contains('bg-red-500')).toBe(true);
    });

    it('renders small red dot badge when collapsed with pending actions', () => {
      vi.mocked(storeModule.useRalphStore).mockReturnValue({
        ...createMockStore(),
        pendingActions: [
          { action_id: 'act-1', action_type: 'dangerous_op', work_id: 'wu-1', description: 'Test', context: {}, created_at: '2024-01-01' },
          { action_id: 'act-2', action_type: 'scope_expansion', work_id: 'wu-2', description: 'Test2', context: {}, created_at: '2024-01-01' },
          { action_id: 'act-3', action_type: 'manual_intervention', work_id: 'wu-3', description: 'Test3', context: {}, created_at: '2024-01-01' },
        ],
      });
      render(<Sidebar />);

      // Click collapse button
      fireEvent.click(screen.getByLabelText('收起侧边栏'));

      // After collapsing, should show small badge with "3" on the approvals icon area
      const smallBadge = screen.getByText('3');
      expect(smallBadge).toBeTruthy();
      // Badge should be a small rounded element
      expect(smallBadge.classList.contains('rounded-full')).toBe(true);
    });
  });
});
