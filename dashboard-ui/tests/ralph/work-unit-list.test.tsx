/**
 * WorkUnitList 组件测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WorkUnitList } from '@/components/ralph/work-unit-list';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock the ralph store
const mockFetchWorkUnits = vi.fn();
const mockSetStatusFilter = vi.fn();
const mockAddTab = vi.fn();

// Create a mock store that returns state directly (matching new useRalphStore pattern)
const createMockStore = (overrides = {}) => {
  const defaultState = {
    workUnits: [],
    statusFilter: 'all' as const,
    setStatusFilter: mockSetStatusFilter,
    fetchWorkUnits: mockFetchWorkUnits,
    addTab: mockAddTab,
    loading: false,
    streamChunks: {},
  };
  return { ...defaultState, ...overrides };
};

let mockStore = createMockStore();

vi.mock('@/lib/ralph-store', () => ({
  useRalphStore: () => mockStore,
}));

// Mock the utils
vi.mock('@/lib/ralph-utils', () => ({
  statusLabel: (status: string) => {
    const labels: Record<string, string> = {
      all: '全部',
      ready: '就绪',
      running: '运行中',
      needs_review: '待审查',
      accepted: '已验收',
      needs_rework: '需返工',
      blocked: '已阻塞',
      failed: '已失败',
    };
    return labels[status] || status;
  },
  statusColor: () => 'text-gray-500',
  formatDate: () => '刚刚',
}));

describe('WorkUnitList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore = createMockStore();
  });

  it('renders empty state when no work units', () => {
    render(<WorkUnitList />);
    expect(screen.getByText('暂无工作单元')).toBeTruthy();
  });

  it('renders filter buttons', () => {
    render(<WorkUnitList />);
    expect(screen.getByText('全部')).toBeTruthy();
    expect(screen.getByText('就绪')).toBeTruthy();
    expect(screen.getByText('运行中')).toBeTruthy();
    expect(screen.getByText('待审查')).toBeTruthy();
    expect(screen.getByText('已验收')).toBeTruthy();
    expect(screen.getByText('需返工')).toBeTruthy();
    expect(screen.getByText('已阻塞')).toBeTruthy();
    expect(screen.getByText('已失败')).toBeTruthy();
  });

  it('calls fetchWorkUnits on mount', () => {
    render(<WorkUnitList />);
    expect(mockFetchWorkUnits).toHaveBeenCalled();
  });

  it('shows loading state', () => {
    mockStore = createMockStore({ loading: true });
    render(<WorkUnitList />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('renders work units when data exists', () => {
    mockStore = createMockStore({
      workUnits: [
        {
          work_id: 'wu-001',
          title: '测试工作单元',
          status: 'running',
          work_type: 'development',
          target: '实现某个功能',
          dependencies: ['wu-000'],
          updated_at: new Date().toISOString(),
        },
      ],
    });
    render(<WorkUnitList />);
    expect(screen.getByText('wu-001')).toBeTruthy();
    expect(screen.getByText('测试工作单元')).toBeTruthy();
    expect(screen.getByText('development')).toBeTruthy();
  });

  it('calls setStatusFilter when filter button clicked', () => {
    render(<WorkUnitList />);
    const runningFilter = screen.getByText('运行中');
    fireEvent.click(runningFilter);
    expect(mockSetStatusFilter).toHaveBeenCalledWith('running');
  });

  it('calls addTab when work unit clicked', () => {
    mockStore = createMockStore({
      workUnits: [
        {
          work_id: 'wu-001',
          title: '测试工作单元',
          status: 'running',
          work_type: 'development',
          target: '实现某个功能',
          dependencies: [],
          updated_at: new Date().toISOString(),
        },
      ],
    });
    render(<WorkUnitList />);
    const workUnitButton = screen.getByTestId('workunit-wu-001');
    fireEvent.click(workUnitButton);
    expect(mockAddTab).toHaveBeenCalledWith({
      label: '测试工作单元',
      type: 'work_unit',
      work_id: 'wu-001',
      pinned: false,
    });
  });

  it('shows dependencies when work unit has them', () => {
    mockStore = createMockStore({
      workUnits: [
        {
          work_id: 'wu-001',
          title: '测试工作单元',
          status: 'running',
          work_type: 'development',
          target: '实现某个功能',
          dependencies: ['wu-000', 'wu-002'],
          updated_at: new Date().toISOString(),
        },
      ],
    });
    render(<WorkUnitList />);
    expect(screen.getByText(/依赖:/)).toBeTruthy();
    expect(screen.getByText(/wu-000, wu-002/)).toBeTruthy();
  });
});
