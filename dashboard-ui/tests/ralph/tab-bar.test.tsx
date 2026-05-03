import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TabBar } from '@/components/ralph/tab-bar';
import * as storeModule from '@/lib/ralph-store';
import type { Tab } from '@/lib/ralph-types';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/ralph',
}));

// Mock the store
vi.mock('@/lib/ralph-store', () => ({
  useRalphStore: vi.fn(),
}));

const mockAddTab = vi.fn();
const mockCloseTab = vi.fn();
const mockSetActiveTab = vi.fn();

const createMockStore = (tabs: Tab[] = [], activeTabId: string | null = null) => ({
  tabs,
  activeTabId,
  addTab: mockAddTab,
  closeTab: mockCloseTab,
  setActiveTab: mockSetActiveTab,
  workUnits: [],
  selectedWorkUnit: null,
  statusFilter: 'all' as const,
  pendingActions: [],
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

describe('TabBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty tab bar', () => {
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore());
    render(<TabBar />);

    // Should have add button
    expect(screen.getByLabelText('添加新标签')).toBeTruthy();
  });

  it('renders tabs correctly', () => {
    const tabs: Tab[] = [
      { id: 'tab-1', label: '概览', type: 'overview', pinned: false, created_at: Date.now() },
      { id: 'tab-2', label: '这是一个很长很长的标签文本', type: 'work_unit', work_id: 'wu-1', pinned: false, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    expect(screen.getByText('概览')).toBeTruthy();
    expect(screen.getByText('这是一个很长很长的标签…')).toBeTruthy(); // Truncated to 12 chars
  });

  it('activates tab on click', () => {
    const tabs: Tab[] = [
      { id: 'tab-1', label: 'Tab 1', type: 'overview', pinned: false, created_at: Date.now() },
      { id: 'tab-2', label: 'Tab 2', type: 'overview', pinned: false, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    const tab2 = screen.getByText('Tab 2');
    fireEvent.click(tab2);

    expect(mockSetActiveTab).toHaveBeenCalledWith('tab-2');
  });

  it('closes tab when clicking X', () => {
    const tabs: Tab[] = [
      { id: 'tab-1', label: 'Tab 1', type: 'overview', pinned: false, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    const closeButton = screen.getByLabelText('关闭 Tab 1');
    fireEvent.click(closeButton);

    expect(mockCloseTab).toHaveBeenCalledWith('tab-1');
  });

  it('does not show close button for pinned tabs', () => {
    const tabs: Tab[] = [
      { id: 'tab-1', label: 'Pinned Tab', type: 'overview', pinned: true, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    // Should not have close button for pinned tab
    expect(screen.queryByLabelText('关闭 Pinned Tab')).toBeNull();
    // Should show pinned indicator
    expect(screen.getByText('Pinned Tab').parentElement?.querySelector('.bg-slate-300')).toBeTruthy();
  });

  it('adds new tab when clicking + button', () => {
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore());

    render(<TabBar />);

    const addButton = screen.getByLabelText('添加新标签');
    fireEvent.click(addButton);

    expect(mockAddTab).toHaveBeenCalledWith({
      label: '新标签',
      type: 'overview',
      pinned: false,
    });
  });

  it('disables add button when MAX_TABS reached', () => {
    const tabs: Tab[] = Array.from({ length: 8 }, (_, i) => ({
      id: `tab-${i}`,
      label: `Tab ${i}`,
      type: 'overview',
      pinned: false,
      created_at: Date.now(),
    }));
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    const addButton = screen.getByLabelText('添加新标签');
    expect(addButton.hasAttribute('disabled')).toBe(true);
  });

  it('shows active tab with correct styling', () => {
    const tabs: Tab[] = [
      { id: 'tab-1', label: 'Active', type: 'overview', pinned: false, created_at: Date.now() },
      { id: 'tab-2', label: 'Inactive', type: 'overview', pinned: false, created_at: Date.now() },
    ];
    vi.mocked(storeModule.useRalphStore).mockReturnValue(createMockStore(tabs, 'tab-1'));

    render(<TabBar />);

    const activeTab = screen.getByText('Active').parentElement;
    expect(activeTab?.classList.contains('border-b-slate-800')).toBe(true);
  });
});
